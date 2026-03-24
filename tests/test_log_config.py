"""Tests for logger utility module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from ideago.observability.log_config import (
    configure_json_logging,
    emit_observability_event,
    get_default_logger,
    get_logger,
    setup_logging,
)
from ideago.observability.metrics import _Metrics


def test_setup_logging_writes_to_custom_file(tmp_path: Path) -> None:
    """setup_logging should write logs to an explicit file path."""
    log_file = tmp_path / "app.log"
    setup_logging(
        level="INFO",
        log_file=str(log_file),
        backtrace=False,
        diagnose=False,
        enqueue=False,
        serialize=False,
    )

    logger = get_logger("tests.logger")
    logger.info("hello-from-setup-logging")

    assert log_file.exists()
    assert "hello-from-setup-logging" in log_file.read_text(encoding="utf-8")


def test_configure_json_logging_writes_structured_entry(tmp_path: Path) -> None:
    """configure_json_logging should include custom extra fields in output."""
    log_file = tmp_path / "json.log"
    configure_json_logging(
        level="INFO",
        log_file=str(log_file),
        extra_fields={"service": "unit-tests"},
    )

    logger = get_logger("tests.json")
    logger.info("hello-json-logging")

    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert "hello-json-logging" in content
    assert "unit-tests" in content


def test_get_default_logger_returns_bound_logger() -> None:
    """get_default_logger should lazily initialize and return a logger."""
    logger = get_default_logger()
    logger.debug("default-logger-ready")
    assert logger is not None


def test_emit_observability_event_emits_structured_payload() -> None:
    logger = MagicMock()
    payload = {
        "query_family_coverage": {"pain_discovery": 2},
        "degraded_ratio": 0.5,
    }

    emit_observability_event(logger, "retrieval_orchestration_summary", payload)

    logger.info.assert_called_once_with(
        "observability_event={} payload={}",
        "retrieval_orchestration_summary",
        payload,
    )


def test_metrics_record_snapshot_and_reset() -> None:
    metrics = _Metrics()
    metrics.record("/api/v1/health", 200, 10.5)
    metrics.record("/api/v1/analyze", 500, 30.0)

    snapshot = metrics.snapshot()
    assert snapshot["request_count"] == 2
    assert snapshot["error_count"] == 1
    assert snapshot["avg_latency_ms"] == 20.25
    assert snapshot["max_latency_ms"] == 30.0
    assert snapshot["status_codes"] == {200: 1, 500: 1}
    assert snapshot["top_paths"]["/api/v1/health"] == 1

    metrics.reset()
    reset_snapshot = metrics.snapshot()
    assert reset_snapshot["request_count"] == 0
    assert reset_snapshot["error_count"] == 0
    assert reset_snapshot["avg_latency_ms"] == 0
