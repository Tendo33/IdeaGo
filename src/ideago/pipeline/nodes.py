"""LangGraph node implementations for the research pipeline."""

from __future__ import annotations

import asyncio
import inspect
import time
from collections import Counter, deque
from collections.abc import Callable
from datetime import datetime, timezone
from math import ceil
from typing import Any, TypeVar, cast

from ideago.cache.base import ReportRepository
from ideago.config.settings import get_settings
from ideago.contracts.protocols import DataSource, ProgressCallback
from ideago.models.research import (
    CommercialSignal,
    Competitor,
    ConfidenceMetrics,
    CostBreakdown,
    EvidenceItem,
    EvidenceSummary,
    Intent,
    LlmFaultToleranceMeta,
    PainSignal,
    Platform,
    RawResult,
    RecommendationType,
    ReportMeta,
    ResearchReport,
    SourceResult,
    SourceStatus,
)
from ideago.observability.log_config import emit_observability_event, get_logger
from ideago.pipeline.aggregator import AggregationResult, Aggregator
from ideago.pipeline.events import EventType, PipelineEvent
from ideago.pipeline.exceptions import (
    AggregationError,
    ExtractionError,
    IntentParsingError,
)
from ideago.pipeline.extractor import ExtractionOutput as TypedExtractionOutput
from ideago.pipeline.extractor import Extractor
from ideago.pipeline.graph_state import GraphState
from ideago.pipeline.intent_parser import IntentParser
from ideago.pipeline.merger import merge_competitors
from ideago.pipeline.pre_filter import filter_raw_results
from ideago.pipeline.query_builder import (
    QueryString,
    build_query_families,
    infer_query_family,
)
from ideago.sources.registry import SourceRegistry
from ideago.utils.text_utils import decode_entities_and_strip_html

logger = get_logger(__name__)
_EXTRACTION_DEGRADED_MSG = "Extraction unavailable; showing raw results."
_DEFAULT_ADAPTIVE_WINDOW_SIZE = 6
_DEGRADE_CONSECUTIVE_FAILURES = 2
_RECOVERY_SUCCESS_STREAK = 3
_DEFAULT_SOURCE_QUERY_CAP = 5
_DEFAULT_ROLE_QUERY_BUDGET = 4
_DEFAULT_QUERY_FAMILY_WEIGHT = 1.0
_MANDATORY_QUERY_FAMILIES = {"competitor_discovery"}
_SOURCE_ROLE_BY_PLATFORM: dict[Platform, str] = {
    Platform.GITHUB: "builder_signal",
    Platform.TAVILY: "market_scan",
    Platform.APPSTORE: "user_feedback",
    Platform.REDDIT: "user_feedback",
    Platform.PRODUCT_HUNT: "launch_signal",
    Platform.HACKERNEWS: "discussion_signal",
}
_QueryTextT = TypeVar("_QueryTextT", bound=str)


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
        settings = get_settings()
        self._source_query_caps = settings.get_source_query_caps()
        self._family_default_weights = settings.get_query_family_default_weights()
        self._orchestration_profiles = settings.get_orchestration_profiles()

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
        runtime_orchestration_by_source: dict[str, dict[str, Any]] = {}
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
            base_queries, orchestration_payload = self._build_orchestrated_queries(
                platform=source.platform,
                intent=intent,
            )
            default_query_concurrency = _safe_get_source_query_concurrency(source)
            queries, runtime_query_concurrency = self._adaptive.get_budget(
                platform_name=platform_name,
                queries=base_queries,
                default_source_query_concurrency=default_query_concurrency,
            )
            runtime_orchestration_by_source[platform_name] = {
                "source_role": str(orchestration_payload.get("source_role", "general")),
                "source_cap": max(1, int(orchestration_payload.get("source_cap", 1))),
                "role_cap": max(1, int(orchestration_payload.get("role_cap", 1))),
                "effective_cap": max(
                    1, int(orchestration_payload.get("effective_cap", 1))
                ),
                "selected_query_count": len(queries),
                "selected_family_counts": _build_query_family_coverage(queries),
                "default_query_concurrency": default_query_concurrency,
                "runtime_query_concurrency": runtime_query_concurrency,
            }
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

        query_family_coverage: dict[str, int] = {}
        source_role_budget_usage: dict[str, dict[str, Any]] = {}
        for platform_name, payload in runtime_orchestration_by_source.items():
            family_counts = payload.get("selected_family_counts", {})
            if isinstance(family_counts, dict):
                for family_name, raw_count in family_counts.items():
                    family_key = str(family_name).strip()
                    if not family_key:
                        continue
                    query_family_coverage[family_key] = query_family_coverage.get(
                        family_key, 0
                    ) + max(0, int(raw_count))
            source_role_budget_usage[platform_name] = {
                "source_role": str(payload.get("source_role", "general")),
                "source_cap": max(1, int(payload.get("source_cap", 1))),
                "role_cap": max(1, int(payload.get("role_cap", 1))),
                "effective_cap": max(1, int(payload.get("effective_cap", 1))),
                "selected_query_count": max(
                    0, int(payload.get("selected_query_count", 0))
                ),
                "default_query_concurrency": max(
                    1, int(payload.get("default_query_concurrency", 1))
                ),
                "runtime_query_concurrency": max(
                    1, int(payload.get("runtime_query_concurrency", 1))
                ),
            }

        degraded_like_count = sum(
            1
            for result in source_results
            if result.status
            in {SourceStatus.DEGRADED, SourceStatus.FAILED, SourceStatus.TIMEOUT}
        )
        total_sources = len(source_results)
        degraded_ratio = (
            (degraded_like_count / total_sources) if total_sources > 0 else 0.0
        )
        status_counts = dict(Counter(result.status.value for result in source_results))
        emit_observability_event(
            logger,
            "retrieval_orchestration_summary",
            {
                "query_family_coverage": query_family_coverage,
                "source_role_budget_usage": source_role_budget_usage,
                "degraded_ratio": round(degraded_ratio, 3),
                "status_counts": status_counts,
            },
        )

        return {
            "source_results": source_results,
            "raw_by_source": raw_by_source,
        }

    def _build_orchestrated_queries(
        self,
        *,
        platform: Platform,
        intent: Intent,
    ) -> tuple[list[str], dict[str, Any]]:
        families = build_query_families(platform=platform, intent=intent)
        if not families:
            return [], {
                "source_role": _SOURCE_ROLE_BY_PLATFORM.get(platform, "general"),
                "source_cap": _DEFAULT_SOURCE_QUERY_CAP,
                "role_cap": _DEFAULT_ROLE_QUERY_BUDGET,
                "effective_cap": 1,
                "selected_query_count": 0,
                "selected_family_counts": {},
            }

        profile = self._resolve_orchestration_profile(intent.app_type)
        source_role = _SOURCE_ROLE_BY_PLATFORM.get(platform, "general")
        source_cap = self._source_query_caps.get(
            platform.value, _DEFAULT_SOURCE_QUERY_CAP
        )
        role_cap = self._resolve_role_budget(profile, source_role)
        effective_cap = max(1, min(source_cap, role_cap))
        family_weights = self._merge_family_weights(profile)
        trim_threshold = _safe_non_negative_float(
            profile.get("family_trim_threshold"),
            fallback=0.0,
        )
        trimmed_families = self._trim_query_families(
            families=families,
            family_weights=family_weights,
            trim_threshold=trim_threshold,
        )
        queries = self._weighted_family_queries(
            families=trimmed_families,
            family_weights=family_weights,
            max_queries=effective_cap,
        )
        selected_family_counts = _build_query_family_coverage(queries)
        observability_payload = {
            "source_role": source_role,
            "source_cap": source_cap,
            "role_cap": role_cap,
            "effective_cap": effective_cap,
            "selected_query_count": len(queries),
            "selected_family_counts": selected_family_counts,
        }
        logger.debug(
            "Orchestration profile: platform={}, role={}, app_type={}, selected_queries={}, cap={}",
            platform.value,
            source_role,
            intent.app_type,
            len(queries),
            effective_cap,
        )
        return queries, observability_payload

    def _resolve_orchestration_profile(self, app_type: str) -> dict[str, Any]:
        app_key = app_type.strip().lower()
        profile = self._orchestration_profiles.get(app_key)
        if isinstance(profile, dict):
            return profile
        fallback = self._orchestration_profiles.get("default", {})
        return fallback if isinstance(fallback, dict) else {}

    def _resolve_role_budget(self, profile: dict[str, Any], source_role: str) -> int:
        role_budgets = profile.get("role_query_budgets", {})
        if not isinstance(role_budgets, dict):
            return _DEFAULT_ROLE_QUERY_BUDGET
        role_cap = _safe_positive_int(role_budgets.get(source_role))
        if role_cap is not None:
            return role_cap
        general_cap = _safe_positive_int(role_budgets.get("general"))
        if general_cap is not None:
            return general_cap
        return _DEFAULT_ROLE_QUERY_BUDGET

    def _merge_family_weights(self, profile: dict[str, Any]) -> dict[str, float]:
        merged: dict[str, float] = {
            key: _safe_non_negative_float(value, fallback=_DEFAULT_QUERY_FAMILY_WEIGHT)
            for key, value in self._family_default_weights.items()
        }
        raw_overrides = profile.get("family_weight_overrides", {})
        if not isinstance(raw_overrides, dict):
            return merged
        for family_name, raw_weight in raw_overrides.items():
            family_key = str(family_name).strip().lower()
            if family_key not in merged:
                continue
            merged[family_key] = _safe_non_negative_float(
                raw_weight,
                fallback=merged[family_key],
            )
        return merged

    def _trim_query_families(
        self,
        *,
        families: dict[str, list[_QueryTextT]],
        family_weights: dict[str, float],
        trim_threshold: float,
    ) -> dict[str, list[_QueryTextT]]:
        trimmed: dict[str, list[_QueryTextT]] = {}
        for family_name, queries in families.items():
            weight = family_weights.get(family_name, _DEFAULT_QUERY_FAMILY_WEIGHT)
            if weight >= trim_threshold or family_name in _MANDATORY_QUERY_FAMILIES:
                trimmed[family_name] = queries
        if trimmed:
            return trimmed
        best_family = max(
            families.keys(),
            key=lambda name: family_weights.get(name, _DEFAULT_QUERY_FAMILY_WEIGHT),
        )
        return {best_family: families[best_family]}

    def _weighted_family_queries(
        self,
        *,
        families: dict[str, list[_QueryTextT]],
        family_weights: dict[str, float],
        max_queries: int,
    ) -> list[str]:
        if max_queries <= 0:
            return []
        ordered_families = [
            (name, queries)
            for name, queries in families.items()
            if queries and any(query.strip() for query in queries)
        ]
        if not ordered_families:
            return []

        sort_indexes = {name: index for index, (name, _) in enumerate(ordered_families)}
        sorted_family_names = sorted(
            [name for name, _ in ordered_families],
            key=lambda name: (
                -family_weights.get(name, _DEFAULT_QUERY_FAMILY_WEIGHT),
                sort_indexes[name],
            ),
        )
        query_offsets = {name: 0 for name in sorted_family_names}
        source_queries = {name: families[name] for name in sorted_family_names}

        weighted_cycle: list[str] = []
        for family_name in sorted_family_names:
            weight = family_weights.get(family_name, _DEFAULT_QUERY_FAMILY_WEIGHT)
            tickets = max(1, min(6, int(round(weight * 2))))
            weighted_cycle.extend([family_name] * tickets)
        if not weighted_cycle:
            return []

        result: list[str] = []
        seen: set[str] = set()
        while len(result) < max_queries:
            progressed = False
            for family_name in weighted_cycle:
                offset = query_offsets[family_name]
                queries = source_queries[family_name]
                while offset < len(queries):
                    original_candidate = queries[offset]
                    offset += 1
                    candidate = _normalize_query_object(original_candidate)
                    candidate_text = candidate.strip()
                    if not candidate_text:
                        continue
                    lowered = candidate_text.lower()
                    if lowered in seen:
                        continue
                    seen.add(lowered)
                    result.append(candidate)
                    progressed = True
                    break
                query_offsets[family_name] = offset
                if len(result) >= max_queries:
                    break
            if not progressed:
                break
        return result

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
        extracted_pain_signals: list[PainSignal] = []
        extracted_commercial_signals: list[CommercialSignal] = []
        extracted_evidence_items: list[EvidenceItem] = []
        extracted_count_by_source: dict[str, int] = {}
        llm_usage = _normalize_llm_usage(state.get("llm_usage"))

        async def _extract_for_source(
            platform_name: str,
            raw_results: list[RawResult],
        ) -> tuple[
            str,
            list[Competitor],
            list[PainSignal],
            list[CommercialSignal],
            list[EvidenceItem],
            dict[str, Any],
        ]:
            await _emit(
                self._callback,
                EventType.EXTRACTION_STARTED,
                f"{platform_name}_extraction",
                f"Extracting insights from {platform_name}...",
            )
            try:
                async with self._llm_semaphore:
                    structured = await asyncio.wait_for(
                        _extract_typed_output(self._extractor, raw_results, intent),
                        timeout=self._extraction_timeout,
                    )
                logger.info(
                    "Extracted {} structured competitors from {}",
                    len(structured.competitors),
                    platform_name,
                )
                await _emit(
                    self._callback,
                    EventType.EXTRACTION_COMPLETED,
                    f"{platform_name}_extraction",
                    f"Extracted {len(structured.competitors)} competitors from {platform_name}",
                    {"platform": platform_name, "count": len(structured.competitors)},
                )
                return (
                    platform_name,
                    structured.competitors,
                    structured.pain_signals,
                    structured.commercial_signals,
                    [*structured.evidence_items, *structured.migration_signals],
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
                    [],
                    [],
                    [],
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
                (
                    platform_name,
                    competitors,
                    pain_signals,
                    commercial_signals,
                    evidence_items,
                    extractor_metrics,
                ) = extraction_result
                all_competitors.extend(competitors)
                extracted_pain_signals.extend(pain_signals)
                extracted_commercial_signals.extend(commercial_signals)
                extracted_evidence_items.extend(evidence_items)
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
            "extracted_pain_signals": extracted_pain_signals,
            "extracted_commercial_signals": extracted_commercial_signals,
            "extracted_evidence_items": extracted_evidence_items,
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
        extracted_pain_signals = state.get("extracted_pain_signals", [])
        extracted_commercial_signals = state.get("extracted_commercial_signals", [])
        extracted_evidence_items = state.get("extracted_evidence_items", [])
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
                analyze_kwargs = _build_aggregator_analyze_kwargs(
                    self._aggregator.analyze,
                    output_language=output_language,
                    pain_signals=extracted_pain_signals,
                    commercial_signals=extracted_commercial_signals,
                    evidence_items=extracted_evidence_items,
                )
                agg_result = await asyncio.wait_for(
                    self._aggregator.analyze(
                        merged,
                        query,
                        **analyze_kwargs,
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
                pain_signals=list(extracted_pain_signals),
                commercial_signals=list(extracted_commercial_signals),
                evidence_items=list(extracted_evidence_items),
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
        report_pain_signals = (
            list(agg_result.pain_signals)
            if agg_result.pain_signals
            else list(state.get("extracted_pain_signals", []))
        )
        report_commercial_signals = (
            list(agg_result.commercial_signals)
            if agg_result.commercial_signals
            else list(state.get("extracted_commercial_signals", []))
        )
        report_evidence_items = (
            list(agg_result.evidence_items)
            if agg_result.evidence_items
            else list(state.get("extracted_evidence_items", []))
        )
        confidence = _build_confidence_metrics(
            all_competitors,
            source_results,
            evidence_items=report_evidence_items,
            pain_signals=report_pain_signals,
            commercial_signals=report_commercial_signals,
            uncertainty_notes=agg_result.uncertainty_notes,
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
        evidence_summary = _build_evidence_summary(
            agg_result.competitors,
            evidence_items=report_evidence_items,
            source_results=source_results,
            uncertainty_notes=agg_result.uncertainty_notes,
        )
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
            "pain_signals": report_pain_signals,
            "commercial_signals": report_commercial_signals,
            "whitespace_opportunities": agg_result.whitespace_opportunities,
            "opportunity_score": agg_result.opportunity_score,
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
        degraded_like_count = sum(
            1
            for source_result in source_results
            if source_result.status
            in {SourceStatus.DEGRADED, SourceStatus.FAILED, SourceStatus.TIMEOUT}
        )
        total_sources = len(source_results)
        degraded_ratio = (
            (degraded_like_count / total_sources) if total_sources > 0 else 0.0
        )
        emit_observability_event(
            logger,
            "report_trust_summary",
            {
                "report_id": report.id,
                "degraded_ratio": round(degraded_ratio, 3),
                "confidence_score": report.confidence.score,
                "degradation_penalty": report.confidence.degradation_penalty,
                "contradiction_penalty": report.confidence.contradiction_penalty,
                "confidence_penalty_reasons": _build_confidence_penalty_reasons(
                    confidence=report.confidence,
                    source_results=source_results,
                    uncertainty_notes=agg_result.uncertainty_notes,
                    output_language=state["intent"].output_language,
                ),
            },
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


def _build_aggregator_analyze_kwargs(
    analyze_method: object,
    *,
    output_language: str,
    pain_signals: list[PainSignal],
    commercial_signals: list[CommercialSignal],
    evidence_items: list[EvidenceItem],
) -> dict[str, Any]:
    """Build kwargs for aggregator.analyze while preserving backward compatibility."""
    fallback = {"output_language": output_language}
    if not callable(analyze_method):
        return fallback
    try:
        signature = inspect.signature(cast(Callable[..., Any], analyze_method))
    except (TypeError, ValueError):
        return fallback

    params = signature.parameters
    supports_kwargs = any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in params.values()
    )
    if supports_kwargs:
        return {
            "output_language": output_language,
            "pain_signals": pain_signals,
            "commercial_signals": commercial_signals,
            "evidence_items": evidence_items,
        }

    kwargs: dict[str, Any] = {}
    if "output_language" in params:
        kwargs["output_language"] = output_language
    if "pain_signals" in params:
        kwargs["pain_signals"] = pain_signals
    if "commercial_signals" in params:
        kwargs["commercial_signals"] = commercial_signals
    if "evidence_items" in params:
        kwargs["evidence_items"] = evidence_items
    return kwargs


def _build_confidence_metrics(
    all_competitors: list[Competitor],
    source_results: list[SourceResult],
    *,
    evidence_items: list[EvidenceItem] | None = None,
    pain_signals: list[PainSignal] | None = None,
    commercial_signals: list[CommercialSignal] | None = None,
    uncertainty_notes: list[str] | None = None,
    generated_at: datetime | None = None,
    output_language: str = "en",
) -> ConfidenceMetrics:
    normalized_evidence_items = _dedupe_evidence_items(evidence_items or [])
    normalized_pain_signals = list(pain_signals or [])
    normalized_commercial_signals = list(commercial_signals or [])
    normalized_uncertainty_notes = [
        note.strip() for note in (uncertainty_notes or []) if note.strip()
    ]

    sample_size = max(
        len(all_competitors),
        len(normalized_evidence_items),
        len(normalized_pain_signals) + len(normalized_commercial_signals),
    )
    total_sources = len(source_results)
    source_coverage = sum(
        1
        for source_result in source_results
        if source_result.status
        in {SourceStatus.OK, SourceStatus.CACHED, SourceStatus.DEGRADED}
    )
    effective_success = sum(
        1.0
        if source_result.status in {SourceStatus.OK, SourceStatus.CACHED}
        else 0.7
        if source_result.status == SourceStatus.DEGRADED
        else 0.0
        for source_result in source_results
    )
    source_success_rate = (
        (effective_success / total_sources) if total_sources > 0 else 0.0
    )
    source_diversity = _count_supporting_platforms(
        source_results=source_results,
        evidence_items=normalized_evidence_items,
        pain_signals=normalized_pain_signals,
        commercial_signals=normalized_commercial_signals,
    )
    evidence_density = _build_evidence_density_score(
        evidence_items=normalized_evidence_items,
        pain_signals=normalized_pain_signals,
        commercial_signals=normalized_commercial_signals,
    )
    now = datetime.now(timezone.utc)
    reference_time = generated_at or now
    recency_score = _build_recency_score(
        normalized_evidence_items,
        source_results=source_results,
        now=reference_time,
    )
    degradation_penalty = _build_degradation_penalty(source_results)
    contradiction_penalty = _build_contradiction_penalty(
        pain_signals=normalized_pain_signals,
        commercial_signals=normalized_commercial_signals,
        uncertainty_notes=normalized_uncertainty_notes,
    )
    sample_size_score = min(1.0, sample_size / 6.0) if sample_size > 0 else 0.0
    diversity_score = min(1.0, source_diversity / 4.0) if source_diversity > 0 else 0.0
    base_score = (
        diversity_score * 0.22
        + evidence_density * 0.18
        + recency_score * 0.12
        + source_success_rate * 0.28
        + sample_size_score * 0.20
    ) * 100
    penalty_points = degradation_penalty * 24 + contradiction_penalty * 26
    score = int(round(max(0.0, min(100.0, base_score - penalty_points))))
    return ConfidenceMetrics(
        sample_size=sample_size,
        source_coverage=source_coverage,
        source_success_rate=round(source_success_rate, 3),
        source_diversity=source_diversity,
        evidence_density=round(evidence_density, 3),
        recency_score=round(recency_score, 3),
        degradation_penalty=round(degradation_penalty, 3),
        contradiction_penalty=round(contradiction_penalty, 3),
        reasons=_build_confidence_reasons(
            source_diversity=source_diversity,
            evidence_density=evidence_density,
            recency_score=recency_score,
            degradation_penalty=degradation_penalty,
            contradiction_penalty=contradiction_penalty,
            source_results=source_results,
            uncertainty_notes=normalized_uncertainty_notes,
            output_language=output_language,
        ),
        freshness_hint=_build_relative_freshness_hint(
            reference_time,
            now,
            output_language=output_language,
        ),
        score=max(0, min(100, score)),
    )


def _count_supporting_platforms(
    *,
    source_results: list[SourceResult],
    evidence_items: list[EvidenceItem],
    pain_signals: list[PainSignal],
    commercial_signals: list[CommercialSignal],
) -> int:
    supporting_platforms = {
        item.platform for item in evidence_items if item.platform is not None
    }
    for signal in pain_signals:
        supporting_platforms.update(signal.source_platforms)
    for commercial_signal in commercial_signals:
        supporting_platforms.update(commercial_signal.source_platforms)
    supporting_platforms.update(
        source_result.platform
        for source_result in source_results
        if source_result.status in {SourceStatus.OK, SourceStatus.CACHED}
    )
    return len(supporting_platforms)


def _build_evidence_density_score(
    *,
    evidence_items: list[EvidenceItem],
    pain_signals: list[PainSignal],
    commercial_signals: list[CommercialSignal],
) -> float:
    unique_urls = {item.url.strip() for item in evidence_items if item.url.strip()}
    density_points = (
        len(evidence_items) * 1.0
        + len(unique_urls) * 0.5
        + len(pain_signals) * 0.5
        + len(commercial_signals) * 0.5
    )
    return max(0.0, min(1.0, density_points / 10.0))


def _build_recency_score(
    evidence_items: list[EvidenceItem],
    *,
    source_results: list[SourceResult],
    now: datetime,
) -> float:
    freshness_scores = [
        _score_freshness_hint(item.freshness_hint, now=now)[0]
        for item in evidence_items
        if item.freshness_hint.strip()
    ]
    if not freshness_scores:
        if evidence_items:
            return 0.35
        has_recent_observation = any(
            source_result.status in {SourceStatus.OK, SourceStatus.CACHED}
            and source_result.raw_count > 0
            for source_result in source_results
        )
        return 0.4 if has_recent_observation else 0.0
    return max(0.0, min(1.0, sum(freshness_scores) / len(freshness_scores)))


def _build_degradation_penalty(source_results: list[SourceResult]) -> float:
    if not source_results:
        return 0.0
    penalty_points = 0.0
    for source_result in source_results:
        if source_result.status == SourceStatus.DEGRADED:
            penalty_points += 0.18
        elif source_result.status in {SourceStatus.FAILED, SourceStatus.TIMEOUT}:
            penalty_points += 0.35
    return max(0.0, min(1.0, penalty_points / len(source_results)))


def _build_contradiction_penalty(
    *,
    pain_signals: list[PainSignal],
    commercial_signals: list[CommercialSignal],
    uncertainty_notes: list[str],
) -> float:
    penalty = 0.0
    for note in uncertainty_notes:
        lower_note = note.lower()
        penalty += (
            0.2
            if any(
                token in lower_note
                for token in ("conflict", "contradict", "mixed", "inconsistent")
            )
            else 0.1
        )
        if any(token in lower_note for token in ("weak", "sparse", "limited")):
            penalty += 0.05
    return max(0.0, min(1.0, penalty))


def _build_confidence_reasons(
    *,
    source_diversity: int,
    evidence_density: float,
    recency_score: float,
    degradation_penalty: float,
    contradiction_penalty: float,
    source_results: list[SourceResult],
    uncertainty_notes: list[str],
    output_language: str,
) -> list[str]:
    reasons: list[str] = []
    if source_diversity >= 3:
        reasons.append(
            _localized_text(
                output_language,
                f"证据覆盖 {source_diversity} 个独立来源平台。",
                f"Evidence spans {source_diversity} distinct source platforms.",
            )
        )
    if evidence_density >= 0.6:
        reasons.append(
            _localized_text(
                output_language,
                "证据密度较高，痛点与商业信号互相印证。",
                "Evidence density is strong with corroborating pain and commercial signals.",
            )
        )
    if recency_score >= 0.75:
        reasons.append(
            _localized_text(
                output_language,
                "关键证据较新，时效性较好。",
                "Key evidence is recent enough to support current-market interpretation.",
            )
        )

    degraded_count = sum(
        1
        for source_result in source_results
        if source_result.status
        in {SourceStatus.DEGRADED, SourceStatus.FAILED, SourceStatus.TIMEOUT}
    )
    if degraded_count > 0 and degradation_penalty > 0:
        reasons.append(
            _localized_text(
                output_language,
                f"{degraded_count} 个来源出现降级或失败，已下调置信度。",
                f"{degraded_count} sources were degraded or failed, reducing confidence.",
            )
        )
    if contradiction_penalty > 0 and uncertainty_notes:
        reasons.append(
            _localized_text(
                output_language,
                "存在冲突或不确定证据，已下调置信度。",
                "Conflicting or uncertain evidence reduced confidence.",
            )
        )
    return reasons


def _build_confidence_penalty_reasons(
    *,
    confidence: ConfidenceMetrics,
    source_results: list[SourceResult],
    uncertainty_notes: list[str] | None,
    output_language: str,
) -> list[str]:
    reasons: list[str] = []
    degraded_count = sum(
        1
        for source_result in source_results
        if source_result.status
        in {SourceStatus.DEGRADED, SourceStatus.FAILED, SourceStatus.TIMEOUT}
    )
    if degraded_count > 0 and confidence.degradation_penalty > 0:
        reasons.append(
            _localized_text(
                output_language,
                f"{degraded_count} 个来源出现降级或失败，已下调置信度。",
                f"{degraded_count} sources were degraded or failed, reducing confidence.",
            )
        )

    normalized_uncertainty_notes = [
        note.strip() for note in (uncertainty_notes or []) if note.strip()
    ]
    if confidence.contradiction_penalty > 0 and normalized_uncertainty_notes:
        reasons.append(
            _localized_text(
                output_language,
                "存在冲突或不确定证据，已下调置信度。",
                "Conflicting or uncertain evidence reduced confidence.",
            )
        )
    return reasons


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


def _build_evidence_summary(
    competitors: list[Competitor],
    *,
    evidence_items: list[EvidenceItem] | None = None,
    source_results: list[SourceResult] | None = None,
    uncertainty_notes: list[str] | None = None,
) -> EvidenceSummary:
    ranked = sorted(competitors, key=lambda item: item.relevance_score, reverse=True)
    normalized_evidence_items = _dedupe_evidence_items(evidence_items or [])

    top_evidence = [
        _truncate_text(
            f"{item.title}: {item.snippet}"
            if item.snippet
            else f"{item.title}: {item.url}",
            140,
        )
        for item in normalized_evidence_items[:4]
        if item.title or item.snippet or item.url
    ]
    if not top_evidence:
        top_evidence = [
            _truncate_text(f"{competitor.name}: {competitor.one_liner}", 140)
            for competitor in ranked[:4]
            if competitor.name or competitor.one_liner
        ]
    category_counts = _build_evidence_category_counts(normalized_evidence_items)
    freshness_distribution = _build_freshness_distribution(normalized_evidence_items)
    return EvidenceSummary(
        top_evidence=top_evidence,
        evidence_items=normalized_evidence_items,
        category_counts=category_counts,
        source_platforms=_sorted_platforms(
            {
                item.platform
                for item in normalized_evidence_items
                if item.platform is not None
            }
        ),
        freshness_distribution=freshness_distribution,
        degraded_sources=_sorted_platforms(
            {
                source_result.platform
                for source_result in (source_results or [])
                if source_result.status
                in {SourceStatus.DEGRADED, SourceStatus.FAILED, SourceStatus.TIMEOUT}
            }
        ),
        uncertainty_notes=list(uncertainty_notes or []),
    )


def _dedupe_evidence_items(evidence_items: list[EvidenceItem]) -> list[EvidenceItem]:
    deduped: list[EvidenceItem] = []
    seen: set[tuple[str, str, str, str, str]] = set()
    for item in evidence_items:
        key = (
            item.url.strip().lower(),
            item.category.value,
            item.platform.value if item.platform is not None else "",
            item.title.strip().lower(),
            item.snippet.strip().lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _build_freshness_distribution(
    evidence_items: list[EvidenceItem],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    now = datetime.now(timezone.utc)
    for item in evidence_items:
        _, bucket = _score_freshness_hint(item.freshness_hint, now=now)
        counts[bucket] = counts.get(bucket, 0) + 1
    return counts


def _score_freshness_hint(
    freshness_hint: str,
    *,
    now: datetime,
) -> tuple[float, str]:
    normalized_hint = freshness_hint.strip()
    if not normalized_hint:
        return 0.0, "unknown"

    parsed_timestamp = _parse_iso_datetime(normalized_hint)
    if parsed_timestamp is not None:
        age_days = max(0.0, (now - parsed_timestamp).total_seconds() / 86400.0)
        if age_days <= 30:
            return 1.0, "recent"
        if age_days <= 365:
            return 0.55, "aging"
        if age_days <= 730:
            return 0.3, "stale"
        return 0.15, "stale"

    lower_hint = normalized_hint.lower()
    if any(
        token in lower_hint for token in ("just now", "moments ago", "recent", "new")
    ):
        return 0.8, "recent"
    if any(token in lower_hint for token in ("week", "month", "day")):
        return 0.5, "aging"
    return 0.35, "unknown"


def _parse_iso_datetime(value: str) -> datetime | None:
    normalized = value.strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _sorted_platforms(platforms: set[Platform]) -> list[Platform]:
    return sorted(platforms, key=lambda platform: platform.value)


def _build_evidence_category_counts(
    evidence_items: list[EvidenceItem],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in evidence_items:
        category_key = item.category.value
        counts[category_key] = counts.get(category_key, 0) + 1
    return counts


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


def _build_query_family_coverage(queries: list[str]) -> dict[str, int]:
    coverage: dict[str, int] = {}
    for query in queries:
        family = infer_query_family(query).strip().lower()
        if not family:
            continue
        coverage[family] = coverage.get(family, 0) + 1
    return coverage


def _normalize_query_object(value: str) -> str:
    """Trim query text while preserving string-subclass metadata when possible."""
    normalized = value.strip()
    if normalized == value:
        return value

    query_family = getattr(value, "query_family", None)
    if isinstance(query_family, str) and query_family:
        return QueryString(normalized, query_family=query_family)
    return normalized


def _safe_positive_int(value: object) -> int | None:
    if isinstance(value, bool):
        return 1 if value else None
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, float):
        parsed = int(value)
    elif isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            parsed = int(stripped)
        except ValueError:
            return None
    else:
        return None
    if parsed <= 0:
        return None
    return parsed


def _safe_non_negative_float(value: object, *, fallback: float) -> float:
    if isinstance(value, int | float):
        parsed = float(value)
    elif isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return fallback
        try:
            parsed = float(stripped)
        except ValueError:
            return fallback
    else:
        return fallback
    if parsed < 0:
        return fallback
    return parsed


async def _extract_typed_output(
    extractor: Extractor,
    raw_results: list[RawResult],
    intent: Intent,
) -> TypedExtractionOutput:
    """Consume typed extractor contract while keeping competitors-only compatibility."""
    extract_structured = getattr(extractor, "extract_structured", None)
    if callable(extract_structured):
        structured = await extract_structured(raw_results, intent)
        if isinstance(structured, TypedExtractionOutput):
            return structured
        raise ExtractionError(
            "Extractor.extract_structured() must return typed ExtractionOutput"
        )

    competitors = await extractor.extract(raw_results, intent)
    typed_competitors = [item for item in competitors if isinstance(item, Competitor)]
    if len(typed_competitors) != len(competitors):
        raise ExtractionError("Extractor.extract() returned invalid competitor entries")

    pop_structured_output = getattr(
        extractor, "pop_structured_output_for_current_task", None
    )
    if callable(pop_structured_output):
        structured = pop_structured_output()
        if isinstance(structured, TypedExtractionOutput):
            if structured.competitors:
                return structured
            return structured.model_copy(update={"competitors": typed_competitors})

    return TypedExtractionOutput(competitors=typed_competitors)


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
