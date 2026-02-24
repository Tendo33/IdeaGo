"""LangGraph state schema for the research pipeline."""

from __future__ import annotations

from typing import TypedDict

from ideago.models.research import (
    Competitor,
    Intent,
    RawResult,
    ResearchReport,
    SourceResult,
)
from ideago.pipeline.aggregator import AggregationResult


class GraphState(TypedDict, total=False):
    """Shared state across all LangGraph pipeline nodes."""

    query: str
    report_id: str

    intent: Intent
    raw_by_source: dict[str, list[RawResult]]
    source_results: list[SourceResult]
    all_competitors: list[Competitor]
    aggregation_result: AggregationResult
    report: ResearchReport

    is_cache_hit: bool
    error_code: str
    cancelled: bool
