"""LangGraph node implementations for the research pipeline."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any

from ideago.cache.file_cache import FileCache
from ideago.contracts.protocols import DataSource, ProgressCallback
from ideago.models.research import (
    Competitor,
    ConfidenceMetrics,
    CostBreakdown,
    EvidenceItem,
    EvidenceSummary,
    LlmFaultToleranceMeta,
    Platform,
    RawResult,
    RecommendationType,
    ReportMeta,
    ResearchReport,
    SourceResult,
    SourceStatus,
)
from ideago.observability.log_config import get_logger
from ideago.pipeline.aggregator import AggregationResult, Aggregator, fuse_competitors
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
from ideago.utils.text_utils import decode_entities_and_strip_html

logger = get_logger(__name__)
_EXTRACTION_DEGRADED_MSG = "Extraction unavailable; showing raw results."
_QUERY_FALLBACK_PLATFORMS = {Platform.GITHUB, Platform.PRODUCT_HUNT}


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
        started_at_ms = int(
            state.get("pipeline_started_at_ms", int(time.monotonic() * 1000))
        )
        llm_usage = _normalize_llm_usage(state.get("llm_usage"))
        await _emit(
            self._callback,
            EventType.INTENT_STARTED,
            "intent_parsing",
            "Analyzing your idea...",
        )
        try:
            intent = await self._intent_parser.parse(query)
            llm_usage = _merge_llm_usage(
                llm_usage,
                _safe_pop_task_llm_metrics(self._intent_parser),
            )
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
            f"Identified: {intent.app_type} - {', '.join(intent.keywords_en)}",
            {
                "keywords": intent.keywords_en,
                "app_type": intent.app_type,
                "target_scenario": intent.target_scenario,
            },
        )
        return {
            "intent": intent,
            "pipeline_started_at_ms": started_at_ms,
            "llm_usage": llm_usage,
        }

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
            source_queries: list[str] = []
            for sq in intent.search_queries:
                if sq.platform == source.platform:
                    source_queries = sq.queries
                    break
            queries = _resolve_queries_for_source(
                platform=source.platform,
                source_queries=source_queries,
                fallback_keywords=intent.keywords_en,
            )

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
        extracted_count_by_source: dict[str, int] = {}
        llm_usage = _normalize_llm_usage(state.get("llm_usage"))

        async def _extract_for_source(
            platform_name: str,
            raw_results: list[RawResult],
        ) -> tuple[str, list[Competitor], dict[str, Any]]:
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
                logger.info(
                    "Extracted {} structured competitors from {}",
                    len(competitors),
                    platform_name,
                )
                await _emit(
                    self._callback,
                    EventType.EXTRACTION_COMPLETED,
                    f"{platform_name}_extraction",
                    f"Extracted {len(competitors)} competitors from {platform_name}",
                    {"platform": platform_name, "count": len(competitors)},
                )
                return (
                    platform_name,
                    competitors,
                    _safe_pop_task_llm_metrics(self._extractor),
                )
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
                        source_result.error_msg = _EXTRACTION_DEGRADED_MSG
                logger.info(
                    "Falling back to {} degraded competitors from {}",
                    len(degraded),
                    platform_name,
                )
                return (
                    platform_name,
                    degraded,
                    _safe_pop_task_llm_metrics(self._extractor),
                )

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
                platform_name, competitors, extractor_metrics = extraction_result
                all_competitors.extend(competitors)
                extracted_count_by_source[platform_name] = len(competitors)
                for source_result in source_results:
                    if source_result.platform.value == platform_name:
                        source_result.competitors = competitors
                llm_usage = _merge_llm_usage(llm_usage, extractor_metrics)
            elif isinstance(extraction_result, Exception):
                logger.error("Unexpected extraction error: {}", extraction_result)
        if extracted_count_by_source:
            logger.info(
                "Per-source extracted content counts: {}",
                extracted_count_by_source,
            )

        return {
            "all_competitors": all_competitors,
            "source_results": source_results,
            "llm_usage": llm_usage,
        }

    async def aggregate_node(self, state: GraphState) -> GraphState:
        """Aggregate/deduplicate competitor list and generate analysis."""
        all_competitors = state.get("all_competitors", [])
        query = state["query"]
        llm_usage = _normalize_llm_usage(state.get("llm_usage"))

        await _emit(
            self._callback,
            EventType.AGGREGATION_STARTED,
            "aggregation",
            "Analyzing and deduplicating...",
        )

        agg_started_at = time.monotonic()
        try:
            async with self._llm_semaphore:
                agg_result = await asyncio.wait_for(
                    self._aggregator.aggregate(all_competitors, query),
                    timeout=self._extraction_timeout,
                )
            llm_usage = _merge_llm_usage(
                llm_usage,
                _safe_pop_task_llm_metrics(self._aggregator),
            )
        except (AggregationError, asyncio.TimeoutError) as exc:
            elapsed = time.monotonic() - agg_started_at
            logger.warning(
                "Aggregation failed: {} (type={}, elapsed={}s), using raw competitors",
                exc,
                type(exc).__name__,
                round(elapsed, 2),
            )
            fused_fallback = fuse_competitors(all_competitors)
            agg_result = AggregationResult(
                competitors=fused_fallback,
                market_summary="Aggregation failed - showing unprocessed results.",
                go_no_go="Unable to determine - aggregation error.",
            )
            llm_usage = _merge_llm_usage(
                llm_usage,
                _safe_pop_task_llm_metrics(self._aggregator),
            )

        await _emit(
            self._callback,
            EventType.AGGREGATION_COMPLETED,
            "aggregation",
            f"Found {len(agg_result.competitors)} unique competitors",
            {"count": len(agg_result.competitors)},
        )
        return {"aggregation_result": agg_result, "llm_usage": llm_usage}

    async def assemble_report_node(self, state: GraphState) -> GraphState:
        """Assemble final report object from graph state."""
        agg_result = state["aggregation_result"]
        source_results = state.get("source_results", [])
        all_competitors = state.get("all_competitors", [])
        llm_usage = _normalize_llm_usage(state.get("llm_usage"))
        started_at_ms = int(
            state.get("pipeline_started_at_ms", int(time.monotonic() * 1000))
        )
        pipeline_latency_ms = max(0, int(time.monotonic() * 1000) - started_at_ms)
        confidence = _build_confidence_metrics(
            all_competitors,
            source_results,
            generated_at=datetime.now(timezone.utc),
        )
        recommendation_type, go_no_go, quality_warnings = (
            _apply_recommendation_quality_guard(
                recommendation_type=agg_result.recommendation_type,
                go_no_go=agg_result.go_no_go,
                confidence=confidence,
            )
        )
        evidence_summary = _build_evidence_summary(agg_result.competitors)
        cost_breakdown = _build_cost_breakdown(
            llm_usage=llm_usage,
            source_results=source_results,
            pipeline_latency_ms=pipeline_latency_ms,
        )
        report_meta = _build_report_meta(llm_usage, quality_warnings=quality_warnings)
        report_kwargs: dict[str, Any] = {
            "query": state["query"],
            "intent": state["intent"],
            "source_results": source_results,
            "competitors": agg_result.competitors,
            "market_summary": agg_result.market_summary,
            "go_no_go": go_no_go,
            "recommendation_type": recommendation_type,
            "differentiation_angles": agg_result.differentiation_angles,
            "confidence": confidence,
            "evidence_summary": evidence_summary,
            "cost_breakdown": cost_breakdown,
            "report_meta": report_meta,
        }
        if state.get("report_id"):
            report_kwargs["id"] = state["report_id"]
        report = ResearchReport(**report_kwargs)
        freshness_hint = _build_relative_freshness_hint(
            created_at=report.created_at,
            now=datetime.now(timezone.utc),
        )
        report = report.model_copy(
            update={
                "confidence": report.confidence.model_copy(
                    update={"freshness_hint": freshness_hint}
                )
            }
        )
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
            normalized_description = decode_entities_and_strip_html(raw.description)
            result.append(
                Competitor(
                    name=raw.title or "Unknown",
                    links=[raw.url],
                    one_liner=normalized_description[:200]
                    if normalized_description
                    else "No description available",
                    source_platforms=[raw.platform],
                    source_urls=[raw.url],
                    relevance_score=0.3,
                )
            )
    return result


def _empty_llm_usage() -> dict[str, Any]:
    return {
        "llm_calls": 0,
        "llm_retries": 0,
        "endpoint_failovers": 0,
        "tokens_prompt": 0,
        "tokens_completion": 0,
        "fallback_used": False,
        "endpoints_tried": [],
        "last_error_class": "",
    }


def _normalize_llm_usage(raw: object) -> dict[str, Any]:
    usage = _empty_llm_usage()
    if not isinstance(raw, dict):
        return usage
    usage["llm_calls"] = max(0, int(raw.get("llm_calls", 0) or 0))
    usage["llm_retries"] = max(0, int(raw.get("llm_retries", 0) or 0))
    usage["endpoint_failovers"] = max(0, int(raw.get("endpoint_failovers", 0) or 0))
    usage["tokens_prompt"] = max(0, int(raw.get("tokens_prompt", 0) or 0))
    usage["tokens_completion"] = max(0, int(raw.get("tokens_completion", 0) or 0))
    usage["fallback_used"] = bool(raw.get("fallback_used", False))
    endpoints = raw.get("endpoints_tried", [])
    if isinstance(endpoints, list):
        usage["endpoints_tried"] = [
            str(item) for item in endpoints if str(item).strip()
        ]
    usage["last_error_class"] = str(raw.get("last_error_class", "") or "")
    return usage


def _normalize_llm_metrics(raw: object) -> dict[str, Any]:
    metrics = _empty_llm_usage()
    if not isinstance(raw, dict):
        return metrics
    metrics["llm_calls"] = max(0, int(raw.get("llm_calls", 0) or 0))
    metrics["llm_retries"] = max(0, int(raw.get("llm_retries", 0) or 0))
    metrics["endpoint_failovers"] = max(0, int(raw.get("endpoint_failovers", 0) or 0))
    metrics["tokens_prompt"] = max(0, int(raw.get("tokens_prompt", 0) or 0))
    metrics["tokens_completion"] = max(0, int(raw.get("tokens_completion", 0) or 0))
    metrics["fallback_used"] = bool(raw.get("fallback_used", False))
    endpoints = raw.get("endpoints_tried", [])
    if isinstance(endpoints, list):
        metrics["endpoints_tried"] = [
            str(item) for item in endpoints if str(item).strip()
        ]
    metrics["last_error_class"] = str(raw.get("last_error_class", "") or "")
    return metrics


def _merge_llm_usage(current: object, incoming: object) -> dict[str, Any]:
    lhs = _normalize_llm_usage(current)
    rhs = _normalize_llm_metrics(incoming)
    merged = _empty_llm_usage()
    merged["llm_calls"] = int(lhs["llm_calls"]) + int(rhs["llm_calls"])
    merged["llm_retries"] = int(lhs["llm_retries"]) + int(rhs["llm_retries"])
    merged["endpoint_failovers"] = int(lhs["endpoint_failovers"]) + int(
        rhs["endpoint_failovers"]
    )
    merged["tokens_prompt"] = int(lhs["tokens_prompt"]) + int(rhs["tokens_prompt"])
    merged["tokens_completion"] = int(lhs["tokens_completion"]) + int(
        rhs["tokens_completion"]
    )
    merged["fallback_used"] = bool(lhs["fallback_used"]) or bool(rhs["fallback_used"])
    merged["endpoints_tried"] = list(
        dict.fromkeys([*lhs["endpoints_tried"], *rhs["endpoints_tried"]])
    )
    merged["last_error_class"] = (
        str(rhs["last_error_class"]) or str(lhs["last_error_class"]) or ""
    )
    return merged


def _safe_pop_task_llm_metrics(target: object) -> dict[str, Any]:
    pop_method = getattr(target, "pop_llm_metrics_for_current_task", None)
    if not callable(pop_method):
        return {}
    payload = pop_method()
    return payload if isinstance(payload, dict) else {}


def _build_confidence_metrics(
    all_competitors: list[Competitor],
    source_results: list[SourceResult],
    generated_at: datetime | None = None,
) -> ConfidenceMetrics:
    sample_size = len(all_competitors)
    total_sources = len(source_results)
    source_coverage = sum(
        1
        for source_result in source_results
        if source_result.status in {SourceStatus.OK, SourceStatus.DEGRADED}
    )
    effective_success = sum(
        1.0
        if source_result.status == SourceStatus.OK
        else 0.7
        if source_result.status == SourceStatus.DEGRADED
        else 0.0
        for source_result in source_results
    )
    source_success_rate = (
        (effective_success / total_sources) if total_sources > 0 else 0.0
    )
    score = int(min(100, sample_size * 2.5 + source_success_rate * 60))
    now = datetime.now(timezone.utc)
    reference_time = generated_at or now
    return ConfidenceMetrics(
        sample_size=sample_size,
        source_coverage=source_coverage,
        source_success_rate=round(source_success_rate, 3),
        freshness_hint=_build_relative_freshness_hint(reference_time, now),
        score=max(0, min(100, score)),
    )


def _build_relative_freshness_hint(created_at: datetime, now: datetime) -> str:
    created_ts = (
        created_at.replace(tzinfo=timezone.utc)
        if created_at.tzinfo is None
        else created_at.astimezone(timezone.utc)
    )
    now_ts = (
        now.replace(tzinfo=timezone.utc)
        if now.tzinfo is None
        else now.astimezone(timezone.utc)
    )
    delta_seconds = max(0, int((now_ts - created_ts).total_seconds()))
    if delta_seconds < 60:
        return "Generated just now"
    if delta_seconds < 3600:
        minutes = max(1, delta_seconds // 60)
        return f"Generated {minutes}m ago"
    if delta_seconds < 86400:
        hours = max(1, delta_seconds // 3600)
        return f"Generated {hours}h ago"
    if delta_seconds < 7 * 86400:
        days = max(1, delta_seconds // 86400)
        return f"Generated {days}d ago"
    return f"Generated on {created_ts.date().isoformat()}"


def _build_evidence_summary(competitors: list[Competitor]) -> EvidenceSummary:
    ranked = sorted(competitors, key=lambda item: item.relevance_score, reverse=True)
    top_evidence = [
        _truncate_text(f"{competitor.name}: {competitor.one_liner}", 140)
        for competitor in ranked[:4]
        if competitor.name or competitor.one_liner
    ]
    evidence_items: list[EvidenceItem] = []
    for competitor in ranked[:6]:
        first_link = competitor.links[0] if competitor.links else ""
        platform = (
            competitor.source_platforms[0].value
            if competitor.source_platforms
            else "unknown"
        )
        evidence_items.append(
            EvidenceItem(
                title=competitor.name,
                url=first_link,
                platform=platform,
                snippet=_truncate_text(competitor.one_liner, 180),
            )
        )
    return EvidenceSummary(top_evidence=top_evidence, evidence_items=evidence_items)


def _build_cost_breakdown(
    *,
    llm_usage: dict[str, Any],
    source_results: list[SourceResult],
    pipeline_latency_ms: int,
) -> CostBreakdown:
    return CostBreakdown(
        llm_calls=max(0, int(llm_usage.get("llm_calls", 0) or 0)),
        llm_retries=max(0, int(llm_usage.get("llm_retries", 0) or 0)),
        endpoint_failovers=max(0, int(llm_usage.get("endpoint_failovers", 0) or 0)),
        source_calls=len(source_results),
        pipeline_latency_ms=max(0, int(pipeline_latency_ms)),
        tokens_prompt=max(0, int(llm_usage.get("tokens_prompt", 0) or 0)),
        tokens_completion=max(0, int(llm_usage.get("tokens_completion", 0) or 0)),
    )


def _build_report_meta(
    llm_usage: dict[str, Any], *, quality_warnings: list[str]
) -> ReportMeta:
    endpoints = llm_usage.get("endpoints_tried", [])
    endpoint_names = (
        [str(item) for item in endpoints if str(item).strip()]
        if isinstance(endpoints, list)
        else []
    )
    return ReportMeta(
        llm_fault_tolerance=LlmFaultToleranceMeta(
            fallback_used=bool(llm_usage.get("fallback_used", False)),
            endpoints_tried=endpoint_names,
            last_error_class=str(llm_usage.get("last_error_class", "") or ""),
        ),
        quality_warnings=quality_warnings,
    )


def _apply_recommendation_quality_guard(
    *,
    recommendation_type: RecommendationType,
    go_no_go: str,
    confidence: ConfidenceMetrics,
) -> tuple[RecommendationType, str, list[str]]:
    warnings: list[str] = []
    adjusted_type = recommendation_type
    adjusted_text = go_no_go.strip() if go_no_go.strip() else "Recommendation pending."

    low_evidence = (
        confidence.sample_size == 0
        or confidence.source_success_rate < 0.4
        or confidence.score < 40
    )
    if low_evidence:
        warnings.append(
            "Low evidence confidence: recommendation is calibrated conservatively."
        )

    if low_evidence and recommendation_type == RecommendationType.GO:
        adjusted_type = RecommendationType.CAUTION
        warnings.append(
            "Recommendation downgraded from GO to CAUTION due to insufficient evidence."
        )
    elif low_evidence and recommendation_type == RecommendationType.NO_GO:
        adjusted_type = RecommendationType.CAUTION
        warnings.append(
            "Recommendation softened from NO_GO to CAUTION due to insufficient evidence."
        )

    if adjusted_type != recommendation_type:
        guardrail_note = (
            "This recommendation is adjusted due to insufficient evidence; "
            "collect more validated competitors before making a final decision."
        )
        if guardrail_note not in adjusted_text:
            adjusted_text = f"{adjusted_text} {guardrail_note}".strip()

    return adjusted_type, adjusted_text, warnings


def _truncate_text(value: str, limit: int) -> str:
    text = value.strip()
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3].rstrip()}..."


def _resolve_queries_for_source(
    *,
    platform: Platform,
    source_queries: list[str],
    fallback_keywords: list[str],
) -> list[str]:
    primary = _normalize_queries(source_queries)
    fallback = _normalize_queries(fallback_keywords)
    if platform in _QUERY_FALLBACK_PLATFORMS:
        merged = [*primary, *fallback]
        deduped = list(dict.fromkeys(merged))
        if deduped:
            return deduped
    if primary:
        return primary
    if fallback:
        return fallback
    return []


def _normalize_queries(queries: list[str]) -> list[str]:
    normalized = [query.strip() for query in queries if query.strip()]
    return list(dict.fromkeys(normalized))
