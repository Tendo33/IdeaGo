"""LangGraph node implementations for the research pipeline."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from ideago.cache.file_cache import FileCache
from ideago.contracts.protocols import DataSource, ProgressCallback
from ideago.models.research import (
    Competitor,
    RawResult,
    ResearchReport,
    SourceResult,
    SourceStatus,
)
from ideago.observability.log_config import get_logger
from ideago.pipeline.aggregator import AggregationResult, Aggregator
from ideago.pipeline.events import EventType, PipelineEvent
from ideago.pipeline.exceptions import (
    AggregationError,
    ExtractionError,
    IntentParsingError,
)
from ideago.pipeline.extractor import Extractor
from ideago.pipeline.graph_state import GraphState
from ideago.pipeline.intent_parser import IntentParser
from ideago.sources.registry import SourceRegistry

logger = get_logger(__name__)


async def _emit(
    callback: ProgressCallback | None,
    event_type: EventType,
    stage: str,
    message: str,
    data: dict[str, Any] | None = None,
) -> None:
    if callback:
        await callback.on_event(
            PipelineEvent(
                type=event_type,
                stage=stage,
                message=message,
                data=data or {},
            )
        )


class PipelineNodes:
    """Node implementation bundle bound to runtime dependencies."""

    def __init__(
        self,
        *,
        intent_parser: IntentParser,
        extractor: Extractor,
        aggregator: Aggregator,
        registry: SourceRegistry,
        cache: FileCache,
        callback: ProgressCallback | None,
        source_timeout: int,
        extraction_timeout: int,
        max_results_per_source: int,
        max_concurrent_llm: int,
    ) -> None:
        self._intent_parser = intent_parser
        self._extractor = extractor
        self._aggregator = aggregator
        self._registry = registry
        self._cache = cache
        self._callback = callback
        self._source_timeout = source_timeout
        self._extraction_timeout = extraction_timeout
        self._max_results = max_results_per_source
        self._llm_semaphore = asyncio.Semaphore(max_concurrent_llm)

    async def parse_intent_node(self, state: GraphState) -> GraphState:
        """Parse natural language query into structured intent."""
        query = state["query"]
        await _emit(
            self._callback,
            EventType.INTENT_PARSED,
            "intent_parsing",
            "Analyzing your idea...",
        )
        try:
            intent = await self._intent_parser.parse(query)
        except IntentParsingError:
            logger.exception("Intent parsing failed")
            await _emit(
                self._callback,
                EventType.ERROR,
                "intent_parsing",
                "Failed to analyze your idea",
            )
            raise

        await _emit(
            self._callback,
            EventType.INTENT_PARSED,
            "intent_parsing",
            f"Identified: {intent.app_type} — {', '.join(intent.keywords_en)}",
            {"keywords": intent.keywords_en, "app_type": intent.app_type},
        )
        return {"intent": intent}

    async def cache_lookup_node(self, state: GraphState) -> GraphState:
        """Resolve cache hit/miss for parsed intent."""
        intent = state["intent"]
        report_id = state.get("report_id")

        cached = await self._cache.get(intent.cache_key)
        if cached is None:
            return {"is_cache_hit": False}

        logger.info("Cache hit for key {}", intent.cache_key)
        if report_id and cached.id != report_id:
            cached = cached.model_copy(update={"id": report_id})
            await self._cache.put(cached)
        await _emit(
            self._callback,
            EventType.REPORT_READY,
            "cache",
            "Found cached report",
            {"report_id": cached.id},
        )
        return {"is_cache_hit": True, "report": cached}

    async def fetch_sources_node(self, state: GraphState) -> GraphState:
        """Fetch raw results from all available sources concurrently."""
        intent = state["intent"]
        source_results: list[SourceResult] = []
        raw_by_source: dict[str, list[RawResult]] = {}
        sources = self._registry.get_available()

        async def _fetch_source(source: DataSource) -> SourceResult:
            platform_name = source.platform.value
            await _emit(
                self._callback,
                EventType.SOURCE_STARTED,
                f"{platform_name}_search",
                f"Searching {platform_name}...",
            )
            start = time.monotonic()
            queries = []
            for sq in intent.search_queries:
                if sq.platform == source.platform:
                    queries = sq.queries
                    break
            if not queries:
                queries = intent.keywords_en

            try:
                results = await asyncio.wait_for(
                    source.search(queries, limit=self._max_results),
                    timeout=self._source_timeout,
                )
                duration_ms = int((time.monotonic() - start) * 1000)
                raw_by_source[platform_name] = results
                await _emit(
                    self._callback,
                    EventType.SOURCE_COMPLETED,
                    f"{platform_name}_search",
                    f"Found {len(results)} results from {platform_name}",
                    {"platform": platform_name, "count": len(results)},
                )
                return SourceResult(
                    platform=source.platform,
                    status=SourceStatus.OK,
                    raw_count=len(results),
                    duration_ms=duration_ms,
                )
            except asyncio.TimeoutError:
                duration_ms = int((time.monotonic() - start) * 1000)
                logger.warning("{} search timed out", platform_name)
                await _emit(
                    self._callback,
                    EventType.SOURCE_FAILED,
                    f"{platform_name}_search",
                    f"{platform_name} search timed out",
                )
                return SourceResult(
                    platform=source.platform,
                    status=SourceStatus.TIMEOUT,
                    error_msg="Timeout",
                    duration_ms=duration_ms,
                )
            except Exception as exc:
                duration_ms = int((time.monotonic() - start) * 1000)
                logger.warning("{} search failed: {}", platform_name, exc)
                await _emit(
                    self._callback,
                    EventType.SOURCE_FAILED,
                    f"{platform_name}_search",
                    f"{platform_name} search failed",
                )
                return SourceResult(
                    platform=source.platform,
                    status=SourceStatus.FAILED,
                    error_msg=str(exc),
                    duration_ms=duration_ms,
                )

        fetch_results = await asyncio.gather(
            *[_fetch_source(source) for source in sources],
            return_exceptions=True,
        )
        for result in fetch_results:
            if isinstance(result, SourceResult):
                source_results.append(result)
            elif isinstance(result, Exception):
                logger.error("Unexpected fetch error: {}", result)

        return {
            "source_results": source_results,
            "raw_by_source": raw_by_source,
        }

    async def extract_map_node(self, state: GraphState) -> GraphState:
        """Extract competitors from raw source results concurrently."""
        raw_by_source = state.get("raw_by_source", {})
        query = state["query"]
        source_results = state.get("source_results", [])
        all_competitors: list[Competitor] = []

        async def _extract_for_source(
            platform_name: str,
            raw_results: list[RawResult],
        ) -> tuple[str, list[Competitor]]:
            await _emit(
                self._callback,
                EventType.EXTRACTION_STARTED,
                f"{platform_name}_extraction",
                f"Extracting insights from {platform_name}...",
            )
            try:
                async with self._llm_semaphore:
                    competitors = await asyncio.wait_for(
                        self._extractor.extract(raw_results, query),
                        timeout=self._extraction_timeout,
                    )
                await _emit(
                    self._callback,
                    EventType.EXTRACTION_COMPLETED,
                    f"{platform_name}_extraction",
                    f"Extracted {len(competitors)} competitors from {platform_name}",
                    {"platform": platform_name, "count": len(competitors)},
                )
                return platform_name, competitors
            except (ExtractionError, asyncio.TimeoutError) as exc:
                logger.warning(
                    "Extraction failed for {}: {}, degrading to raw results",
                    platform_name,
                    exc,
                )
                degraded = _degrade_raw_to_competitors(raw_results)
                for source_result in source_results:
                    if source_result.platform.value == platform_name:
                        source_result.status = SourceStatus.DEGRADED
                        source_result.error_msg = f"LLM extraction failed: {exc}"
                return platform_name, degraded

        extraction_tasks = [
            _extract_for_source(platform_name, raw_results)
            for platform_name, raw_results in raw_by_source.items()
            if raw_results
        ]
        extraction_results = await asyncio.gather(
            *extraction_tasks,
            return_exceptions=True,
        )
        for extraction_result in extraction_results:
            if isinstance(extraction_result, tuple):
                platform_name, competitors = extraction_result
                all_competitors.extend(competitors)
                for source_result in source_results:
                    if source_result.platform.value == platform_name:
                        source_result.competitors = competitors
            elif isinstance(extraction_result, Exception):
                logger.error("Unexpected extraction error: {}", extraction_result)

        return {
            "all_competitors": all_competitors,
            "source_results": source_results,
        }

    async def aggregate_node(self, state: GraphState) -> GraphState:
        """Aggregate/deduplicate competitor list and generate analysis."""
        all_competitors = state.get("all_competitors", [])
        query = state["query"]

        await _emit(
            self._callback,
            EventType.AGGREGATION_STARTED,
            "aggregation",
            "Analyzing and deduplicating...",
        )

        try:
            async with self._llm_semaphore:
                agg_result = await asyncio.wait_for(
                    self._aggregator.aggregate(all_competitors, query),
                    timeout=self._extraction_timeout,
                )
        except (AggregationError, asyncio.TimeoutError) as exc:
            logger.warning("Aggregation failed: {}, using raw competitors", exc)
            agg_result = AggregationResult(
                competitors=all_competitors,
                market_summary="Aggregation failed — showing unprocessed results.",
                go_no_go="Unable to determine — aggregation error.",
            )

        await _emit(
            self._callback,
            EventType.AGGREGATION_COMPLETED,
            "aggregation",
            f"Found {len(agg_result.competitors)} unique competitors",
            {"count": len(agg_result.competitors)},
        )
        return {"aggregation_result": agg_result}

    async def assemble_report_node(self, state: GraphState) -> GraphState:
        """Assemble final report object from graph state."""
        agg_result = state["aggregation_result"]
        report_kwargs: dict[str, Any] = {
            "query": state["query"],
            "intent": state["intent"],
            "source_results": state.get("source_results", []),
            "competitors": agg_result.competitors,
            "market_summary": agg_result.market_summary,
            "go_no_go": agg_result.go_no_go,
            "recommendation_type": agg_result.recommendation_type,
            "differentiation_angles": agg_result.differentiation_angles,
        }
        if state.get("report_id"):
            report_kwargs["id"] = state["report_id"]
        report = ResearchReport(**report_kwargs)
        return {"report": report}

    async def persist_report_node(self, state: GraphState) -> GraphState:
        """Persist report to cache and emit terminal ready event."""
        report = state["report"]
        await self._cache.put(report)
        await _emit(
            self._callback,
            EventType.REPORT_READY,
            "complete",
            "Report ready",
            {"report_id": report.id},
        )
        return {}

    async def terminal_error_node(self, state: GraphState) -> GraphState:
        """Terminal node for graph-level controlled failures."""
        error_code = state.get("error_code", "PIPELINE_FAILURE")
        raise RuntimeError(error_code)


def _degrade_raw_to_competitors(raw_results: list[RawResult]) -> list[Competitor]:
    """Convert raw results to minimal Competitor objects when LLM fails."""
    result: list[Competitor] = []
    for raw in raw_results:
        if raw.url:
            result.append(
                Competitor(
                    name=raw.title or "Unknown",
                    links=[raw.url],
                    one_liner=raw.description[:200]
                    if raw.description
                    else "No description available",
                    source_platforms=[raw.platform],
                    source_urls=[raw.url],
                    relevance_score=0.3,
                )
            )
    return result
