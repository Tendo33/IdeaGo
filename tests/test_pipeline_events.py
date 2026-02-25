"""Tests for pipeline event models."""

from __future__ import annotations

import json

from ideago.pipeline.events import EventType, PipelineEvent


def test_event_type_values() -> None:
    assert EventType.INTENT_STARTED == "intent_started"
    assert EventType.SOURCE_STARTED == "source_started"
    assert EventType.REPORT_READY == "report_ready"
    assert EventType.ERROR == "error"


def test_pipeline_event_creation() -> None:
    e = PipelineEvent(
        type=EventType.SOURCE_COMPLETED,
        stage="github_search",
        message="Found 8 results from GitHub",
        data={"platform": "github", "count": 8},
    )
    assert e.stage == "github_search"
    assert e.data["count"] == 8
    assert e.timestamp is not None


def test_pipeline_event_to_sse_format() -> None:
    e = PipelineEvent(
        type=EventType.INTENT_PARSED,
        stage="intent_parsing",
        message="Intent parsed successfully",
    )
    sse = e.to_sse()
    parsed = json.loads(sse)
    assert parsed["type"] == "intent_parsed"
    assert parsed["stage"] == "intent_parsing"


def test_pipeline_event_default_data_empty() -> None:
    e = PipelineEvent(
        type=EventType.ERROR,
        stage="pipeline",
        message="Something failed",
    )
    assert e.data == {}
