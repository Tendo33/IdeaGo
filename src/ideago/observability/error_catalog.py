"""Centralized error-code logging policy for observability."""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from typing import Any


class AlertLevel(str, Enum):
    """Alerting severity used by structured logging."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


ERROR_LEVEL_BY_CODE: dict[str, AlertLevel] = {
    "RATE_LIMIT_PG_CLEANUP_FAILED": AlertLevel.WARNING,
    "RATE_LIMIT_PG_CLEANUP_TIMEOUT": AlertLevel.WARNING,
    "RATE_LIMIT_PG_CLEANUP_HTTP_ERROR": AlertLevel.ERROR,
    "RATE_LIMIT_PG_CLEANUP_UNEXPECTED": AlertLevel.ERROR,
    "RATE_LIMIT_PG_RPC_FAILED": AlertLevel.WARNING,
    "RATE_LIMIT_PG_RPC_TIMEOUT": AlertLevel.WARNING,
    "RATE_LIMIT_PG_RPC_HTTP_ERROR": AlertLevel.ERROR,
    "RATE_LIMIT_PG_RPC_UNEXPECTED": AlertLevel.ERROR,
    "RATE_LIMIT_USER_RESOLVE_FAILED": AlertLevel.WARNING,
    "CACHE_CLEANUP_FAILED": AlertLevel.WARNING,
    "DEDUP_PG_RESERVE_FAILED": AlertLevel.WARNING,
    "DEDUP_PG_RESERVE_TIMEOUT": AlertLevel.WARNING,
    "DEDUP_PG_RESERVE_HTTP_ERROR": AlertLevel.ERROR,
    "DEDUP_PG_RESERVE_UNEXPECTED": AlertLevel.ERROR,
    "DEDUP_PG_RELEASE_TIMEOUT": AlertLevel.WARNING,
    "DEDUP_PG_RELEASE_HTTP_ERROR": AlertLevel.ERROR,
    "DEDUP_PG_RELEASE_UNEXPECTED": AlertLevel.ERROR,
    "DEDUP_PG_IS_PROCESSING_FAILED": AlertLevel.WARNING,
    "DEDUP_PG_IS_PROCESSING_TIMEOUT": AlertLevel.WARNING,
    "DEDUP_PG_IS_PROCESSING_HTTP_ERROR": AlertLevel.ERROR,
    "DEDUP_PG_IS_PROCESSING_UNEXPECTED": AlertLevel.ERROR,
    "ANALYSIS_STATUS_PERSIST_FAILED": AlertLevel.ERROR,
    "ANALYSIS_TERMINAL_STATUS_PERSIST_FAILED": AlertLevel.ERROR,
    "ACCOUNT_DELETE_ROLLBACK_TRIGGERED": AlertLevel.WARNING,
    "ACCOUNT_DELETE_STUCK_PENDING": AlertLevel.ERROR,
}


def resolve_alert_level(error_code: str) -> AlertLevel:
    return ERROR_LEVEL_BY_CODE.get(error_code, AlertLevel.ERROR)


def log_error_event(
    logger: Any,
    *,
    error_code: str,
    subsystem: str,
    trace_id: str = "",
    message: str = "",
    details: Mapping[str, object] | None = None,
    include_exception: bool = False,
    alert_level: AlertLevel | None = None,
) -> None:
    """Emit one structured error log line for consistent downstream aggregation."""
    normalized_code = error_code.strip() or "UNKNOWN_ERROR"
    normalized_subsystem = subsystem.strip() or "unknown"
    normalized_trace_id = trace_id.strip()
    normalized_details = dict(details or {})
    normalized_message = message.strip()
    level = alert_level or resolve_alert_level(normalized_code)
    effective_logger = logger
    if include_exception:
        opt = getattr(logger, "opt", None)
        if callable(opt):
            effective_logger = opt(exception=True)
    method = getattr(effective_logger, level.value, None)
    if not callable(method):
        method = getattr(logger, "error", None)
    if not callable(method):
        return
    method(
        "error_event code={} subsystem={} trace_id={} message={} details={}",
        normalized_code,
        normalized_subsystem,
        normalized_trace_id,
        normalized_message,
        normalized_details,
    )
