"""LangGraph state schema for the research pipeline."""

from __future__ import annotations

from typing import TypedDict

from ideago.models.research import (
    CommercialSignal,
    Competitor,
    EvidenceItem,
    Intent,
    PainSignal,
    QueryPlan,
    RawResult,
    ResearchReport,
    SourceResult,
)
from ideago.pipeline.aggregator import AggregationResult


class GraphState(TypedDict, total=False):
    """Shared state across all LangGraph pipeline nodes."""

    query: str
    report_id: str
    user_id: str

    intent: Intent
    query_plan: QueryPlan
    raw_by_source: dict[str, list[RawResult]]
    filtered_by_source: dict[str, list[RawResult]]
    source_results: list[SourceResult]
    all_competitors: list[Competitor]
    merged_competitors: list[Competitor]
    extracted_pain_signals: list[PainSignal]
    extracted_commercial_signals: list[CommercialSignal]
    extracted_evidence_items: list[EvidenceItem]
    aggregation_result: AggregationResult
    report: ResearchReport
    pipeline_started_at_ms: int
    llm_usage: dict[str, object]

    is_cache_hit: bool
    error_code: str
    cancelled: bool
