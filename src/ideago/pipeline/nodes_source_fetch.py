"""Source fetch helpers for pipeline nodes."""

from __future__ import annotations

import asyncio
import time
from collections import deque
from math import ceil
from typing import Any

from ideago.contracts.protocols import DataSource
from ideago.models.research import RawResult, SourceStatus
from ideago.observability.log_config import get_logger
from ideago.pipeline.nodes_extraction import (
    safe_consume_source_diagnostics,
    safe_set_source_query_concurrency,
)

logger = get_logger(__name__)
_DEFAULT_ADAPTIVE_WINDOW_SIZE = 6
_DEGRADE_CONSECUTIVE_FAILURES = 2
_RECOVERY_SUCCESS_STREAK = 3


class SourceAdaptiveController:
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


def build_runtime_orchestration_summary(
    *,
    orchestration_payload: dict[str, Any],
    queries: list[str],
    default_query_concurrency: int,
    runtime_query_concurrency: int,
) -> dict[str, Any]:
    return {
        "source_role": str(orchestration_payload.get("source_role", "general")),
        "source_cap": max(1, int(orchestration_payload.get("source_cap", 1))),
        "role_cap": max(1, int(orchestration_payload.get("role_cap", 1))),
        "effective_cap": max(1, int(orchestration_payload.get("effective_cap", 1))),
        "selected_query_count": len(queries),
        "selected_family_counts": {},
        "default_query_concurrency": default_query_concurrency,
        "runtime_query_concurrency": runtime_query_concurrency,
    }


async def execute_source_search(
    *,
    source: DataSource,
    queries: list[str],
    fetch_max_results: int,
    source_timeout: int,
    source_semaphore: asyncio.Semaphore,
    runtime_query_concurrency: int,
) -> tuple[list[RawResult], dict[str, Any], int]:
    start = time.monotonic()
    safe_set_source_query_concurrency(source, runtime_query_concurrency)
    try:
        async with source_semaphore:
            results = await asyncio.wait_for(
                source.search(queries, limit=fetch_max_results),
                timeout=source_timeout,
            )
    finally:
        safe_set_source_query_concurrency(source, None)

    duration_ms = int((time.monotonic() - start) * 1000)
    diagnostics = safe_consume_source_diagnostics(source)
    return results, diagnostics, duration_ms
