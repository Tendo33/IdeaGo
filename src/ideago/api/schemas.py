"""API request/response schemas.

API 请求/响应模型。
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator

from ideago.models.base import BaseModel
from ideago.models.research import (
    CommercialSignal,
    Competitor,
    ConfidenceMetrics,
    CostBreakdown,
    EvidenceSummary,
    Intent,
    OpportunityScoreBreakdown,
    PainSignal,
    RecommendationType,
    ReportMeta,
    SourceResult,
    WhitespaceOpportunity,
)


class AnalyzeRequest(BaseModel):
    """Request body for the analyze endpoint."""

    query: str = Field(
        min_length=5,
        max_length=1000,
        description="Natural language startup idea description",
    )

    @field_validator("query")
    @classmethod
    def sanitize_query(cls, v: str) -> str:
        """Collapse whitespace and reject garbage input."""
        v = re.sub(r"\s+", " ", v).strip()
        if len(v) < 5:
            raise ValueError("Query too short after whitespace normalization")
        if not any(c.isalpha() for c in v):
            raise ValueError("Query must contain alphabetic characters")
        semantic_count = sum(1 for c in v if c.isalnum())
        if semantic_count < 4:
            raise ValueError("Query must contain enough meaningful characters")
        symbol_count = sum(1 for c in v if not c.isalnum() and not c.isspace())
        if len(v) > 0 and symbol_count / len(v) > 0.5:
            raise ValueError("Query contains too many symbols")
        return v


class AnalyzeResponse(BaseModel):
    """Response from the analyze endpoint."""

    report_id: str = Field(description="Unique ID for the report")


class ReportListItem(BaseModel):
    """Summary item for the reports list endpoint."""

    id: str
    query: str
    created_at: datetime
    competitor_count: int = 0


class PaginatedReportList(BaseModel):
    """Paginated response for the reports list endpoint."""

    items: list[ReportListItem]
    total: int
    limit: int | None = None
    offset: int = 0


class ReportRuntimeStatus(BaseModel):
    """Runtime status payload for report processing state."""

    status: Literal["processing", "failed", "cancelled", "complete", "not_found"]
    report_id: str
    error_code: str | None = None
    message: str | None = None
    updated_at: datetime | None = None
    query: str | None = None


class ReportDetailV2(BaseModel):
    """Explicit API contract for report detail payloads."""

    id: str = Field(description="Unique report ID")
    query: str = Field(description="Original user query")
    intent: Intent = Field(description="Parsed research intent")
    source_results: list[SourceResult] = Field(
        default_factory=list,
        description="Per-source execution status and extraction results",
    )
    competitors: list[Competitor] = Field(
        default_factory=list,
        description="Deduplicated competitors in the final report",
    )
    pain_signals: list[PainSignal] = Field(
        default_factory=list,
        description="Decision-first pain signals",
    )
    commercial_signals: list[CommercialSignal] = Field(
        default_factory=list,
        description="Decision-first commercial signals",
    )
    whitespace_opportunities: list[WhitespaceOpportunity] = Field(
        default_factory=list,
        description="Whitespace opportunities and entry wedges",
    )
    opportunity_score: OpportunityScoreBreakdown = Field(
        default_factory=OpportunityScoreBreakdown,
        description="Deterministic opportunity score breakdown",
    )
    market_summary: str = Field(default="", description="Market synthesis summary")
    go_no_go: str = Field(default="", description="Recommendation narrative")
    recommendation_type: RecommendationType = Field(
        default=RecommendationType.GO,
        description="Structured recommendation outcome",
    )
    differentiation_angles: list[str] = Field(
        default_factory=list,
        description="Suggested differentiation angles",
    )
    confidence: ConfidenceMetrics = Field(
        default_factory=ConfidenceMetrics,
        description="Trust/confidence metrics for the report",
    )
    evidence_summary: EvidenceSummary = Field(
        default_factory=EvidenceSummary,
        description="Evidence summary with trust-oriented UI fields",
    )
    cost_breakdown: CostBreakdown = Field(
        default_factory=CostBreakdown,
        description="Pipeline/runtime cost breakdown",
    )
    report_meta: ReportMeta = Field(
        default_factory=ReportMeta,
        description="Supplemental report metadata",
    )
    created_at: datetime = Field(description="Report creation timestamp")
    updated_at: datetime = Field(description="Report last update timestamp")
