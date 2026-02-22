"""Tests for logger utility module."""

from __future__ import annotations

from pathlib import Path

from python_template.observability.log_config import (
    configure_json_logging,
    get_default_logger,
    get_logger,
    setup_logging,
)


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
