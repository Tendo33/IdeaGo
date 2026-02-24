"""Pipeline orchestrator — coordinates intent parsing, source fetching, extraction, aggregation.

管道总调度器：协调意图解析、数据源抓取、竞品提取、聚合分析。
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from loguru import logger

from ideago.cache.file_cache import FileCache
from ideago.contracts.protocols import DataSource, ProgressCallback
from ideago.models.research import (
    Competitor,
    RawResult,
    ResearchReport,
    SourceResult,
    SourceStatus,
)
from ideago.pipeline.aggregator import Aggregator
from ideago.pipeline.events import EventType, PipelineEvent
from ideago.pipeline.exceptions import (
    AggregationError,
    ExtractionError,
    IntentParsingError,
)
from ideago.pipeline.extractor import Extractor
from ideago.pipeline.intent_parser import IntentParser
from ideago.sources.registry import SourceRegistry


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
                type=event_type, stage=stage, message=message, data=data or {}
            )
        )


class Orchestrator:
    """Coordinates the full research pipeline from query to report."""

    def __init__(
        self,
        intent_parser: IntentParser,
        extractor: Extractor,
        aggregator: Aggregator,
        registry: SourceRegistry,
        cache: FileCache,
        source_timeout: int = 30,
        extraction_timeout: int = 60,
        max_results_per_source: int = 10,
        max_concurrent_llm: int = 3,
    ) -> None:
        self._intent_parser = intent_parser
        self._extractor = extractor
        self._aggregator = aggregator
        self._registry = registry
        self._cache = cache
        self._source_timeout = source_timeout
        self._extraction_timeout = extraction_timeout
        self._max_results = max_results_per_source
        self._llm_semaphore = asyncio.Semaphore(max_concurrent_llm)

    def get_all_sources(self) -> list[DataSource]:
        """Return all registered source plugins."""
        return self._registry.get_all()

    def get_source_availability(self) -> dict[str, bool]:
        """Return source availability map for health checks."""
        return {
            source.platform.value: source.is_available()
            for source in self._registry.get_all()
        }

    async def run(
        self,
        query: str,
        callback: ProgressCallback | None = None,
        report_id: str | None = None,
    ) -> ResearchReport:
        """Execute the full research pipeline.

        Args:
            query: User's natural language startup idea description.
            callback: Optional callback for SSE progress events.
            report_id: Optional client-assigned report ID for consistent referencing.

        Returns:
            Complete ResearchReport.
        """
        # 1. Parse intent
        await _emit(
            callback,
            EventType.INTENT_PARSED,
            "intent_parsing",
            "Analyzing your idea...",
        )
        try:
            intent = await self._intent_parser.parse(query)
        except IntentParsingError:
            logger.exception("Intent parsing failed")
            await _emit(
                callback,
                EventType.ERROR,
                "intent_parsing",
                "Failed to analyze your idea",
            )
            raise

        await _emit(
            callback,
            EventType.INTENT_PARSED,
            "intent_parsing",
            f"Identified: {intent.app_type} — {', '.join(intent.keywords_en)}",
            {"keywords": intent.keywords_en, "app_type": intent.app_type},
        )

        # 2. Check cache
        cached = await self._cache.get(intent.cache_key)
        if cached:
            logger.info("Cache hit for key {}", intent.cache_key)
            if report_id and cached.id != report_id:
                cached = cached.model_copy(update={"id": report_id})
                await self._cache.put(cached)
            await _emit(
                callback,
                EventType.REPORT_READY,
                "cache",
                "Found cached report",
                {"report_id": cached.id},
            )
            return cached

        # 3. Concurrent source fetching
        sources = self._registry.get_available()
        source_results: list[SourceResult] = []
        raw_by_source: dict[str, list[RawResult]] = {}

        async def _fetch_source(source: DataSource) -> SourceResult:
            platform_name = source.platform.value
            await _emit(
                callback,
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
                    callback,
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
                    callback,
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
                    callback,
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
            *[_fetch_source(s) for s in sources],
            return_exceptions=True,
        )
        for r in fetch_results:
            if isinstance(r, SourceResult):
                source_results.append(r)
            elif isinstance(r, Exception):
                logger.error("Unexpected fetch error: {}", r)

        # 4. Concurrent extraction (Map)
        all_competitors: list[Competitor] = []

        async def _extract_for_source(
            platform_name: str, raw_results: list[RawResult]
        ) -> tuple[str, list[Competitor]]:
            await _emit(
                callback,
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
                    callback,
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
                for sr in source_results:
                    if sr.platform.value == platform_name:
                        sr.status = SourceStatus.DEGRADED
                        sr.error_msg = f"LLM extraction failed: {exc}"
                return platform_name, degraded

        extraction_tasks = [
            _extract_for_source(pname, raws)
            for pname, raws in raw_by_source.items()
            if raws
        ]
        extraction_results = await asyncio.gather(
            *extraction_tasks, return_exceptions=True
        )
        for ext_r in extraction_results:
            if isinstance(ext_r, tuple):
                pname, comps = ext_r
                all_competitors.extend(comps)
                for sr in source_results:
                    if sr.platform.value == pname:
                        sr.competitors = comps
            elif isinstance(ext_r, Exception):
                logger.error("Unexpected extraction error: {}", ext_r)

        # 5. Aggregation (Reduce)
        await _emit(
            callback,
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
            from ideago.pipeline.aggregator import AggregationResult

            agg_result = AggregationResult(
                competitors=all_competitors,
                market_summary="Aggregation failed — showing unprocessed results.",
                go_no_go="Unable to determine — aggregation error.",
            )

        await _emit(
            callback,
            EventType.AGGREGATION_COMPLETED,
            "aggregation",
            f"Found {len(agg_result.competitors)} unique competitors",
            {"count": len(agg_result.competitors)},
        )

        # 6. Assemble report
        report_kwargs: dict[str, Any] = dict(
            query=query,
            intent=intent,
            source_results=source_results,
            competitors=agg_result.competitors,
            market_summary=agg_result.market_summary,
            go_no_go=agg_result.go_no_go,
            recommendation_type=agg_result.recommendation_type,
            differentiation_angles=agg_result.differentiation_angles,
        )
        if report_id:
            report_kwargs["id"] = report_id
        report = ResearchReport(**report_kwargs)

        await self._cache.put(report)
        await _emit(
            callback,
            EventType.REPORT_READY,
            "complete",
            "Report ready",
            {"report_id": report.id},
        )

        return report


def _degrade_raw_to_competitors(raw_results: list[RawResult]) -> list[Competitor]:
    """Convert raw results to minimal Competitor objects when LLM fails."""
    result: list[Competitor] = []
    for r in raw_results:
        if r.url:
            result.append(
                Competitor(
                    name=r.title or "Unknown",
                    links=[r.url],
                    one_liner=r.description[:200]
                    if r.description
                    else "No description available",
                    source_platforms=[r.platform],
                    source_urls=[r.url],
                    relevance_score=0.3,
                )
            )
    return result
