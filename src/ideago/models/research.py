"""Research domain models.

竞品调研领域模型：Platform、RawResult、Intent、Competitor、SourceResult、ResearchReport。
"""

import hashlib
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import Field

from ideago.models.base import BaseModel, TimestampMixin


class Platform(str, Enum):
    """Supported data source platforms / 支持的数据源平台。"""

    GITHUB = "github"
    TAVILY = "tavily"
    HACKERNEWS = "hackernews"
    APPSTORE = "appstore"
    PRODUCT_HUNT = "producthunt"
    GOOGLE_TRENDS = "google_trends"


class RawResult(BaseModel):
    """Single raw result from a data source / 数据源返回的单条原始结果。"""

    title: str = Field(description="Result title / 结果标题")
    description: str = Field(default="", description="Result description / 结果描述")
    url: str = Field(description="Source URL, mandatory / 来源链接（必填）")
    platform: Platform = Field(description="Source platform / 来源平台")
    raw_data: dict[str, Any] = Field(
        default_factory=dict,
        description="Raw API response preserved for debugging / 原始响应备份",
    )
    fetched_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Fetch timestamp / 抓取时间",
    )


class SearchQuery(BaseModel):
    """Platform-specific search queries / 平台定制搜索词。"""

    platform: Platform = Field(description="Target platform / 目标平台")
    queries: list[str] = Field(
        min_length=1,
        description="Search query strings tailored for this platform",
    )


class Intent(BaseModel):
    """Parsed user intent with per-platform search queries / 解析后的用户意图。"""

    keywords_en: list[str] = Field(
        min_length=1,
        description="English keywords extracted from user input",
    )
    keywords_zh: list[str] = Field(
        default_factory=list,
        description="Chinese keywords if applicable",
    )
    app_type: str = Field(
        description="App form: web / mobile / browser-extension / cli / api / desktop",
    )
    target_scenario: str = Field(
        description="One-sentence target scenario description",
    )
    search_queries: list[SearchQuery] = Field(
        description="Per-platform tailored search queries",
    )
    cache_key: str = Field(
        default="",
        description="Normalized cache key derived from sorted keywords + app_type",
    )

    def compute_cache_key(self) -> str:
        """Generate a deterministic cache key from keywords + app_type.

        Same keywords in different order produce the same key.
        """
        normalized = sorted(k.lower().strip() for k in self.keywords_en)
        raw = f"{self.app_type.lower()}::{'|'.join(normalized)}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]


class Competitor(BaseModel):
    """A competitor product identified during research / 调研中发现的竞品。"""

    name: str = Field(description="Product or project name / 产品名称")
    links: list[str] = Field(
        min_length=1,
        description="URLs — at least 1 required, no link = not recorded",
    )
    one_liner: str = Field(description="One-sentence positioning / 一句话定位")
    features: list[str] = Field(
        default_factory=list,
        description="Key features / 主要功能",
    )
    pricing: str | None = Field(
        default=None,
        description="Pricing info if available / 定价信息",
    )
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    relevance_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="0-1 relevance score, higher = more relevant",
    )
    source_platforms: list[Platform] = Field(
        description="Platforms where this competitor was found",
    )
    source_urls: list[str] = Field(
        description="Original pages where info was extracted from",
    )


class RecommendationType(str, Enum):
    """Structured recommendation type / 结构化推荐类型。"""

    GO = "go"
    CAUTION = "caution"
    NO_GO = "no_go"


class SourceStatus(str, Enum):
    """Status of a data source query / 数据源查询状态。"""

    OK = "ok"
    FAILED = "failed"
    CACHED = "cached"
    TIMEOUT = "timeout"
    DEGRADED = "degraded"


class SourceResult(BaseModel):
    """Result from one data source including status / 单个数据源结果（含状态）。"""

    platform: Platform
    status: SourceStatus
    raw_count: int = Field(
        default=0,
        description="Number of raw results fetched / 抓取到的原始结果数",
    )
    competitors: list[Competitor] = Field(default_factory=list)
    error_msg: str | None = Field(default=None)
    duration_ms: int = Field(
        default=0,
        description="Time taken for this source in milliseconds",
    )


class ConfidenceMetrics(BaseModel):
    """Confidence metrics for report quality and source reliability."""

    sample_size: int = Field(default=0, ge=0)
    source_coverage: int = Field(default=0, ge=0)
    source_success_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    freshness_hint: str = Field(default="Generated moments ago")
    score: int = Field(default=0, ge=0, le=100)


class EvidenceItem(BaseModel):
    """Single evidence item attached to report conclusion."""

    title: str = Field(default="")
    url: str = Field(default="")
    platform: str = Field(default="")
    snippet: str = Field(default="")


class EvidenceSummary(BaseModel):
    """Evidence summary section for transparency."""

    top_evidence: list[str] = Field(default_factory=list)
    evidence_items: list[EvidenceItem] = Field(default_factory=list)


class CostBreakdown(BaseModel):
    """Cost and latency telemetry of one report run."""

    llm_calls: int = Field(default=0, ge=0)
    llm_retries: int = Field(default=0, ge=0)
    endpoint_failovers: int = Field(default=0, ge=0)
    source_calls: int = Field(default=0, ge=0)
    pipeline_latency_ms: int = Field(default=0, ge=0)
    tokens_prompt: int = Field(default=0, ge=0)
    tokens_completion: int = Field(default=0, ge=0)


class LlmFaultToleranceMeta(BaseModel):
    """LLM fault-tolerance metadata for this report."""

    fallback_used: bool = Field(default=False)
    endpoints_tried: list[str] = Field(default_factory=list)
    last_error_class: str = Field(default="")


class ReportMeta(BaseModel):
    """Additional report metadata for observability and debugging."""

    llm_fault_tolerance: LlmFaultToleranceMeta = Field(
        default_factory=LlmFaultToleranceMeta
    )
    quality_warnings: list[str] = Field(
        default_factory=list,
        description="Quality guardrail notes for recommendation reliability.",
    )


class ResearchReport(TimestampMixin):
    """Complete research report / 完整调研报告。"""

    id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique report ID / 报告唯一标识",
    )
    query: str = Field(
        description="User's original natural language input / 用户原始输入"
    )
    intent: Intent
    source_results: list[SourceResult] = Field(default_factory=list)
    competitors: list[Competitor] = Field(
        default_factory=list,
        description="Globally deduplicated competitor list / 全局去重竞品列表",
    )
    market_summary: str = Field(
        default="",
        description="LLM-generated market analysis / 市场分析摘要",
    )
    go_no_go: str = Field(
        default="",
        description="Go/No-Go recommendation with reasoning / 推荐建议",
    )
    recommendation_type: RecommendationType = Field(
        default=RecommendationType.GO,
        description="Structured recommendation: go / caution / no_go",
    )
    differentiation_angles: list[str] = Field(
        default_factory=list,
        description="Suggested differentiation points / 差异化切入点",
    )
    confidence: ConfidenceMetrics = Field(default_factory=ConfidenceMetrics)
    evidence_summary: EvidenceSummary = Field(default_factory=EvidenceSummary)
    cost_breakdown: CostBreakdown = Field(default_factory=CostBreakdown)
    report_meta: ReportMeta = Field(default_factory=ReportMeta)
