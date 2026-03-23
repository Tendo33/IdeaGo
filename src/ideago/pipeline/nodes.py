"""LangGraph node implementations for the research pipeline."""

from __future__ import annotations

import asyncio
import time
from collections import deque
from datetime import datetime, timezone
from math import ceil
from typing import Any

from ideago.cache.base import ReportRepository
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
from ideago.pipeline.merger import merge_competitors
from ideago.pipeline.pre_filter import filter_raw_results
from ideago.pipeline.query_builder import build_queries
from ideago.sources.registry import SourceRegistry
from ideago.utils.text_utils import decode_entities_and_strip_html

logger = get_logger(__name__)
_EXTRACTION_DEGRADED_MSG = "Extraction unavailable; showing raw results."
_DEFAULT_ADAPTIVE_WINDOW_SIZE = 6
_DEGRADE_CONSECUTIVE_FAILURES = 2
_RECOVERY_SUCCESS_STREAK = 3


def _is_zh(output_language: str) -> bool:
    return output_language == "zh"


def _localized_text(output_language: str, zh: str, en: str) -> str:
    return zh if _is_zh(output_language) else en


def _extraction_degraded_message(output_language: str) -> str:
    return _localized_text(
        output_language,
        "结构化提取暂不可用，当前展示原始结果。",
        _EXTRACTION_DEGRADED_MSG,
    )


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


class _SourceAdaptiveController:
    """In-memory adaptive budget controller for source querying."""

    def __init__(
        self,
        *,
        runtime_metrics: dict[str, dict[str, Any]],
        source_timeout: int,
        window_size: int = _DEFAULT_ADAPTIVE_WINDOW_SIZE,
    ) -> None:
        self._runtime_metrics = runtime_metrics
        self._source_timeout = source_timeout
        self._window_size = max(4, window_size)

    def get_budget(
        self,
        *,
        platform_name: str,
        queries: list[str],
        default_source_query_concurrency: int,
    ) -> tuple[list[str], int]:
        if not queries:
            return [], max(1, default_source_query_concurrency)
        state = self._ensure_state(platform_name)
        level = int(state.get("degrade_level", 0))
        if level <= 0:
            return queries, max(1, default_source_query_concurrency)

        reduced_query_count = max(1, ceil(len(queries) / 2))
        reduced_concurrency = max(1, default_source_query_concurrency // 2)
        return queries[:reduced_query_count], reduced_concurrency

    def record(
        self,
        *,
        platform_name: str,
        status: SourceStatus,
        duration_ms: int,
    ) -> None:
        state = self._ensure_state(platform_name)
        history: deque[dict[str, Any]] = state["history"]
        history.append({"status": status.value, "duration_ms": max(0, duration_ms)})
        if len(history) > self._window_size:
            history.popleft()
        self._recompute_state(platform_name, state)

    def _ensure_state(self, platform_name: str) -> dict[str, Any]:
        existing = self._runtime_metrics.get(platform_name)
        if existing is None:
            existing = {
                "history": deque(),
                "degrade_level": 0,
                "failure_streak": 0,
                "success_streak": 0,
            }
            self._runtime_metrics[platform_name] = existing
        return existing

    def _recompute_state(self, platform_name: str, state: dict[str, Any]) -> None:
        history: deque[dict[str, Any]] = state["history"]
        if not history:
            return
        latest_status = SourceStatus(history[-1]["status"])
        is_failure = latest_status in {SourceStatus.FAILED, SourceStatus.TIMEOUT}
        is_success = latest_status == SourceStatus.OK

        state["failure_streak"] = (
            int(state.get("failure_streak", 0)) + 1 if is_failure else 0
        )
        state["success_streak"] = (
            int(state.get("success_streak", 0)) + 1 if is_success else 0
        )

        timeout_count = sum(
            1 for item in history if item["status"] == SourceStatus.TIMEOUT.value
        )
        fail_count = sum(
            1
            for item in history
            if item["status"] in {SourceStatus.TIMEOUT.value, SourceStatus.FAILED.value}
        )
        duration_values = sorted(int(item["duration_ms"]) for item in history)
        p95_index = max(0, ceil(0.95 * len(duration_values)) - 1)
        p95_duration_ms = duration_values[p95_index] if duration_values else 0
        timeout_like = self._source_timeout * 1000

        should_degrade = (
            int(state.get("failure_streak", 0)) >= _DEGRADE_CONSECUTIVE_FAILURES
            or (len(history) >= 3 and (timeout_count / len(history)) >= 0.5)
            or (len(history) >= 4 and p95_duration_ms >= int(timeout_like * 0.9))
        )
        should_recover = (
            int(state.get("success_streak", 0)) >= _RECOVERY_SUCCESS_STREAK
            and (fail_count / len(history)) <= 0.34
            and p95_duration_ms <= int(timeout_like * 0.7)
        )

        level_before = int(state.get("degrade_level", 0))
        if should_degrade:
            state["degrade_level"] = 1
        elif level_before > 0 and should_recover:
            state["degrade_level"] = 0

        level_after = int(state.get("degrade_level", 0))
        if level_after != level_before:
            action = "enabled" if level_after > level_before else "disabled"
            logger.info(
                "Adaptive degradation {} for {}: failure_streak={}, timeout_ratio={}, p95_ms={}",
                action,
                platform_name,
                int(state.get("failure_streak", 0)),
                round(timeout_count / len(history), 3),
                p95_duration_ms,
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
        cache: ReportRepository,
        callback: ProgressCallback | None,
        source_timeout: int,
        extraction_timeout: int,
        max_results_per_source: int,
        max_concurrent_llm: int,
        source_global_concurrency: int,
        source_runtime_metrics: dict[str, dict[str, Any]],
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
        self._source_semaphore = asyncio.Semaphore(max(1, source_global_concurrency))
        self._adaptive = _SourceAdaptiveController(
            runtime_metrics=source_runtime_metrics,
            source_timeout=source_timeout,
        )

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
        user_id = state.get("user_id", "")

        cached = await self._cache.get(intent.cache_key, user_id=user_id)
        if cached is None:
            return {"is_cache_hit": False}

        logger.info("Cache hit for key {}", intent.cache_key)
        if report_id and cached.id != report_id:
            cached = cached.model_copy(update={"id": report_id})
            await self._cache.put(cached, user_id=user_id)
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
            base_queries = build_queries(
                platform=source.platform,
                intent=intent,
            )
            default_query_concurrency = _safe_get_source_query_concurrency(source)
            queries, runtime_query_concurrency = self._adaptive.get_budget(
                platform_name=platform_name,
                queries=base_queries,
                default_source_query_concurrency=default_query_concurrency,
            )
            _safe_set_source_query_concurrency(source, runtime_query_concurrency)

            try:
                async with self._source_semaphore:
                    results = await asyncio.wait_for(
                        source.search(queries, limit=self._max_results),
                        timeout=self._source_timeout,
                    )
                duration_ms = int((time.monotonic() - start) * 1000)
                raw_by_source[platform_name] = results
                diagnostics = _safe_consume_source_diagnostics(source)
                has_partial_failure = bool(diagnostics.get("partial_failure", False))
                used_public_fallback = bool(
                    diagnostics.get("used_public_fallback", False)
                )
                failed_queries = diagnostics.get("failed_queries", [])
                timed_out_queries = diagnostics.get("timed_out_queries", [])
                status = (
                    SourceStatus.DEGRADED
                    if has_partial_failure or used_public_fallback
                    else SourceStatus.OK
                )
                error_msg = None
                if has_partial_failure:
                    partial_reason = (
                        f"Partial source failure ({len(failed_queries)} failed, "
                        f"{len(timed_out_queries)} timed out queries)"
                    )
                    error_msg = partial_reason
                    logger.warning(
                        "Source partial failure: platform={}, failed_queries={}, timed_out_queries={}",
                        platform_name,
                        failed_queries,
                        timed_out_queries,
                    )
                elif used_public_fallback:
                    fallback_reason = str(
                        diagnostics.get("fallback_reason", "missing_credentials")
                    )
                    error_msg = (
                        f"Using public Reddit fallback (reason={fallback_reason})"
                    )
                await _emit(
                    self._callback,
                    EventType.SOURCE_COMPLETED,
                    f"{platform_name}_search",
                    f"Found {len(results)} results from {platform_name}",
                    {"platform": platform_name, "count": len(results)},
                )
                source_result = SourceResult(
                    platform=source.platform,
                    status=status,
                    raw_count=len(results),
                    error_msg=error_msg,
                    duration_ms=duration_ms,
                )
                self._adaptive.record(
                    platform_name=platform_name,
                    status=source_result.status,
                    duration_ms=duration_ms,
                )
                return source_result
            except asyncio.TimeoutError:
                duration_ms = int((time.monotonic() - start) * 1000)
                logger.warning("{} search timed out", platform_name)
                await _emit(
                    self._callback,
                    EventType.SOURCE_FAILED,
                    f"{platform_name}_search",
                    f"{platform_name} search timed out",
                )
                source_result = SourceResult(
                    platform=source.platform,
                    status=SourceStatus.TIMEOUT,
                    error_msg="Timeout",
                    duration_ms=duration_ms,
                )
                self._adaptive.record(
                    platform_name=platform_name,
                    status=source_result.status,
                    duration_ms=duration_ms,
                )
                return source_result
            except Exception as exc:
                duration_ms = int((time.monotonic() - start) * 1000)
                logger.warning("{} search failed: {}", platform_name, exc)
                await _emit(
                    self._callback,
                    EventType.SOURCE_FAILED,
                    f"{platform_name}_search",
                    f"{platform_name} search failed",
                )
                source_result = SourceResult(
                    platform=source.platform,
                    status=SourceStatus.FAILED,
                    error_msg=str(exc),
                    duration_ms=duration_ms,
                )
                self._adaptive.record(
                    platform_name=platform_name,
                    status=source_result.status,
                    duration_ms=duration_ms,
                )
                return source_result

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

    async def pre_filter_node(self, state: GraphState) -> GraphState:
        """Rank and truncate raw results per source using quality signals."""
        raw_by_source = state.get("raw_by_source", {})
        filtered = filter_raw_results(
            raw_by_source,
            max_per_source=self._max_results,
        )
        total_before = sum(len(v) for v in raw_by_source.values())
        total_after = sum(len(v) for v in filtered.values())
        logger.info(
            "Pre-filter: {} → {} results across {} sources",
            total_before,
            total_after,
            len(filtered),
        )
        return {"filtered_by_source": filtered}

    async def extract_map_node(self, state: GraphState) -> GraphState:
        """Extract competitors from raw source results concurrently."""
        raw_by_source = state.get("filtered_by_source") or state.get(
            "raw_by_source", {}
        )
        intent = state["intent"]
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
                        self._extractor.extract(raw_results, intent),
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
                degraded = _degrade_raw_to_competitors(
                    raw_results,
                    output_language=intent.output_language,
                )
                for source_result in source_results:
                    if source_result.platform.value == platform_name:
                        source_result.status = SourceStatus.DEGRADED
                        source_result.error_msg = _extraction_degraded_message(
                            intent.output_language
                        )
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

    async def merge_node(self, state: GraphState) -> GraphState:
        """Deterministic dedup + score adjustment (no LLM)."""
        all_competitors = state.get("all_competitors", [])
        merged = merge_competitors(all_competitors)
        logger.info(
            "Merge: {} raw → {} unique competitors",
            len(all_competitors),
            len(merged),
        )
        return {"merged_competitors": merged}

    async def analyze_node(self, state: GraphState) -> GraphState:
        """LLM-only market analysis on pre-merged competitors."""
        merged = state.get("merged_competitors", [])
        query = state["query"]
        output_language = state["intent"].output_language
        llm_usage = _normalize_llm_usage(state.get("llm_usage"))

        await _emit(
            self._callback,
            EventType.AGGREGATION_STARTED,
            "aggregation",
            "Analyzing market landscape...",
        )

        agg_started_at = time.monotonic()
        try:
            async with self._llm_semaphore:
                agg_result = await asyncio.wait_for(
                    self._aggregator.analyze(
                        merged,
                        query,
                        output_language=output_language,
                    ),
                    timeout=self._extraction_timeout,
                )
            llm_usage = _merge_llm_usage(
                llm_usage,
                _safe_pop_task_llm_metrics(self._aggregator),
            )
        except (AggregationError, asyncio.TimeoutError) as exc:
            elapsed = time.monotonic() - agg_started_at
            logger.warning(
                "Analysis failed: {} (type={}, elapsed={}s), using merged competitors without analysis",
                exc,
                type(exc).__name__,
                round(elapsed, 2),
            )
            agg_result = AggregationResult(
                competitors=merged,
                market_summary=_localized_text(
                    output_language,
                    "分析失败，当前展示的是未深度加工的结果。",
                    "Analysis failed - showing unprocessed results.",
                ),
                go_no_go=_localized_text(
                    output_language,
                    "暂时无法给出明确结论，原因是分析阶段出错。",
                    "Unable to determine - analysis error.",
                ),
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

    async def aggregate_node(self, state: GraphState) -> GraphState:
        """Backward-compatible: merge + analyze in one step."""
        merge_result = await self.merge_node(state)
        combined_state: GraphState = {**state, **merge_result}  # type: ignore[typeddict-item]
        return await self.analyze_node(combined_state)

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
            output_language=state["intent"].output_language,
        )
        recommendation_type, go_no_go, quality_warnings = (
            _apply_recommendation_quality_guard(
                recommendation_type=agg_result.recommendation_type,
                go_no_go=agg_result.go_no_go,
                confidence=confidence,
                output_language=state["intent"].output_language,
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
            output_language=state["intent"].output_language,
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
        user_id = state.get("user_id", "")
        await self._cache.put(report, user_id=user_id)
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


def _degrade_raw_to_competitors(
    raw_results: list[RawResult],
    output_language: str = "en",
) -> list[Competitor]:
    """Convert raw results to minimal Competitor objects when LLM fails.

    Enriches degraded competitors with platform-specific metadata to produce
    higher quality fallback data than a bare title + URL.
    """
    from ideago.pipeline.pre_filter import _quality_score, _safe_int

    result: list[Competitor] = []
    for raw in raw_results:
        if not raw.url:
            continue
        normalized_description = decode_entities_and_strip_html(raw.description)
        one_liner = (
            normalized_description[:200]
            if normalized_description
            else _localized_text(
                output_language,
                "暂无可用描述",
                "No description available",
            )
        )
        relevance = max(0.1, round(_quality_score(raw) * 0.6, 2))

        features: list[str] = []
        rd = raw.raw_data
        if raw.platform == Platform.GITHUB:
            lang = rd.get("language")
            if lang:
                features.append(lang)
            stars = _safe_int(rd.get("stargazers_count", 0))
            if stars:
                features.append(
                    _localized_text(
                        output_language,
                        f"{stars} 星标",
                        f"{stars} stars",
                    )
                )
        elif raw.platform == Platform.APPSTORE:
            genre = rd.get("primary_genre_name")
            if genre:
                features.append(genre)
            price = rd.get("price_label")
            if price:
                features.append(price)
        elif raw.platform == Platform.REDDIT:
            subreddit = rd.get("subreddit")
            if subreddit:
                features.append(f"r/{subreddit}")
            score = _safe_int(rd.get("score", 0))
            if score:
                features.append(
                    _localized_text(
                        output_language,
                        f"{score} 赞同",
                        f"{score} upvotes",
                    )
                )
            comments = _safe_int(rd.get("num_comments", 0))
            if comments:
                features.append(
                    _localized_text(
                        output_language,
                        f"{comments} 条评论",
                        f"{comments} comments",
                    )
                )

        result.append(
            Competitor(
                name=raw.title or "Unknown",
                links=[raw.url],
                one_liner=one_liner,
                features=features,
                source_platforms=[raw.platform],
                source_urls=[raw.url],
                relevance_score=relevance,
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
    output_language: str = "en",
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
        freshness_hint=_build_relative_freshness_hint(
            reference_time,
            now,
            output_language=output_language,
        ),
        score=max(0, min(100, score)),
    )


def _build_relative_freshness_hint(
    created_at: datetime,
    now: datetime,
    output_language: str = "en",
) -> str:
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
        return _localized_text(output_language, "刚刚生成", "Generated just now")
    if delta_seconds < 3600:
        minutes = max(1, delta_seconds // 60)
        return _localized_text(
            output_language,
            f"{minutes} 分钟前生成",
            f"Generated {minutes}m ago",
        )
    if delta_seconds < 86400:
        hours = max(1, delta_seconds // 3600)
        return _localized_text(
            output_language,
            f"{hours} 小时前生成",
            f"Generated {hours}h ago",
        )
    if delta_seconds < 7 * 86400:
        days = max(1, delta_seconds // 86400)
        return _localized_text(
            output_language,
            f"{days} 天前生成",
            f"Generated {days}d ago",
        )
    return _localized_text(
        output_language,
        f"生成于 {created_ts.date().isoformat()}",
        f"Generated on {created_ts.date().isoformat()}",
    )


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
    output_language: str = "en",
) -> tuple[RecommendationType, str, list[str]]:
    warnings: list[str] = []
    adjusted_type = recommendation_type
    adjusted_text = (
        go_no_go.strip()
        if go_no_go.strip()
        else _localized_text(
            output_language,
            "建议待补充。",
            "Recommendation pending.",
        )
    )

    low_evidence = (
        confidence.sample_size == 0
        or confidence.source_success_rate < 0.4
        or confidence.score < 40
    )
    if low_evidence:
        warnings.append(
            _localized_text(
                output_language,
                "当前证据置信度较低，建议保守解读本次结论。",
                "Low evidence confidence: recommendation is calibrated conservatively.",
            )
        )

    if low_evidence and recommendation_type == RecommendationType.GO:
        adjusted_type = RecommendationType.CAUTION
        warnings.append(
            _localized_text(
                output_language,
                "由于证据不足，建议已从 GO 下调为 CAUTION。",
                "Recommendation downgraded from GO to CAUTION due to insufficient evidence.",
            )
        )
    elif low_evidence and recommendation_type == RecommendationType.NO_GO:
        adjusted_type = RecommendationType.CAUTION
        warnings.append(
            _localized_text(
                output_language,
                "由于证据不足，建议已从 NO_GO 放宽为 CAUTION。",
                "Recommendation softened from NO_GO to CAUTION due to insufficient evidence.",
            )
        )

    if adjusted_type != recommendation_type:
        guardrail_note = _localized_text(
            output_language,
            "由于当前证据不足，这条建议已做保守调整；在做最终判断前，建议先补充更多已验证竞品。",
            "This recommendation is adjusted due to insufficient evidence; collect more validated competitors before making a final decision.",
        )
        if guardrail_note not in adjusted_text:
            adjusted_text = f"{adjusted_text} {guardrail_note}".strip()

    return adjusted_type, adjusted_text, warnings


def _truncate_text(value: str, limit: int) -> str:
    text = value.strip()
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3].rstrip()}..."


def _safe_get_source_query_concurrency(source: DataSource) -> int:
    value = getattr(source, "_max_concurrent_queries", 2)
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return 2


def _safe_set_source_query_concurrency(source: DataSource, value: int) -> None:
    setter = getattr(source, "set_runtime_max_concurrent_queries", None)
    if callable(setter):
        setter(max(1, value))


def _safe_consume_source_diagnostics(source: DataSource) -> dict[str, Any]:
    consumer = getattr(source, "consume_last_search_diagnostics", None)
    if not callable(consumer):
        return {}
    payload = consumer()
    return payload if isinstance(payload, dict) else {}
