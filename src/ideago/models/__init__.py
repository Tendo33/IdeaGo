"""Data models using Pydantic for validation.

This module provides base models and example implementations using Pydantic v2
for data validation and configuration management.

提供使用Pydantic v2进行数据验证和配置管理的基础模型和示例实现。
"""

from .base import BaseModel, TimestampMixin
from .examples import ApiResponse, ConfigModel, PaginatedResponse, User
from .research import (
    CommercialSignal,
    Competitor,
    ConfidenceMetrics,
    CostBreakdown,
    EvidenceCategory,
    EvidenceItem,
    EvidenceSummary,
    Intent,
    LlmFaultToleranceMeta,
    OpportunityScoreBreakdown,
    PainSignal,
    Platform,
    QueryFamily,
    QueryGroup,
    QueryPlan,
    QueryRewrite,
    RawResult,
    RelevanceKind,
    ReportMeta,
    ResearchReport,
    SearchQuery,
    SourceResult,
    SourceStatus,
    WhitespaceOpportunity,
)

__all__ = [
    "BaseModel",
    "TimestampMixin",
    "User",
    "ApiResponse",
    "PaginatedResponse",
    "ConfigModel",
    "Platform",
    "QueryFamily",
    "QueryGroup",
    "QueryPlan",
    "QueryRewrite",
    "RelevanceKind",
    "RawResult",
    "SearchQuery",
    "Intent",
    "Competitor",
    "PainSignal",
    "CommercialSignal",
    "WhitespaceOpportunity",
    "OpportunityScoreBreakdown",
    "SourceStatus",
    "SourceResult",
    "ConfidenceMetrics",
    "EvidenceCategory",
    "EvidenceItem",
    "EvidenceSummary",
    "CostBreakdown",
    "LlmFaultToleranceMeta",
    "ReportMeta",
    "ResearchReport",
]
