"""Tests for pipeline exception types."""

from __future__ import annotations

from ideago.pipeline.exceptions import (
    AggregationError,
    ExtractionError,
    IntentParsingError,
    PipelineError,
)


def test_pipeline_error_hierarchy() -> None:
    assert issubclass(IntentParsingError, PipelineError)
    assert issubclass(ExtractionError, PipelineError)
    assert issubclass(AggregationError, PipelineError)


def test_intent_parsing_error_message() -> None:
    err = IntentParsingError("LLM returned invalid JSON")
    assert str(err) == "LLM returned invalid JSON"
    assert isinstance(err, PipelineError)
    assert isinstance(err, Exception)


def test_extraction_error_catch_as_pipeline() -> None:
    try:
        raise ExtractionError("timeout")
    except PipelineError as e:
        assert "timeout" in str(e)


def test_aggregation_error_catch_as_pipeline() -> None:
    try:
        raise AggregationError("rate limited")
    except PipelineError as e:
        assert "rate limited" in str(e)
