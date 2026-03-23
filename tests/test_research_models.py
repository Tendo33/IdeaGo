"""Tests for research domain models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ideago.models.research import (
    Competitor,
    ConfidenceMetrics,
    CostBreakdown,
    EvidenceSummary,
    Intent,
    Platform,
    RawResult,
    RecommendationType,
    ReportMeta,
    ResearchReport,
    SearchQuery,
    SourceResult,
    SourceStatus,
)

# --- Platform ---


def test_platform_enum_values() -> None:
    assert Platform.GITHUB == "github"
    assert Platform.TAVILY == "tavily"
    assert Platform.HACKERNEWS == "hackernews"
    assert Platform.APPSTORE == "appstore"
    assert Platform.PRODUCT_HUNT == "producthunt"


# --- RawResult ---


def test_raw_result_valid() -> None:
    r = RawResult(
        title="Test Repo",
        url="https://github.com/test/repo",
        platform=Platform.GITHUB,
    )
    assert r.title == "Test Repo"
    assert r.description == ""
    assert r.url == "https://github.com/test/repo"
    assert r.raw_data == {}


def test_raw_result_requires_url() -> None:
    with pytest.raises(ValidationError):
        RawResult(title="No URL", platform=Platform.GITHUB)  # type: ignore[call-arg]


def test_raw_result_serialization_roundtrip() -> None:
    r = RawResult(
        title="Test",
        url="https://example.com",
        platform=Platform.GITHUB,
    )
    data = r.model_dump(mode="json")
    assert data["platform"] == "github"
    assert "fetched_at" in data
    r2 = RawResult.model_validate(data)
    assert r2.title == r.title


# --- SearchQuery ---


def test_search_query_valid() -> None:
    sq = SearchQuery(
        platform=Platform.GITHUB,
        queries=["markdown notes extension stars:>50"],
    )
    assert sq.platform == Platform.GITHUB
    assert len(sq.queries) == 1


def test_search_query_requires_at_least_one_query() -> None:
    with pytest.raises(ValidationError):
        SearchQuery(platform=Platform.GITHUB, queries=[])


# --- Intent ---


def test_intent_valid() -> None:
    intent = Intent(
        keywords_en=["markdown", "notes", "browser extension"],
        app_type="browser-extension",
        target_scenario="Take markdown notes on web pages",
        output_language="en",
        search_queries=[
            SearchQuery(platform=Platform.GITHUB, queries=["markdown notes extension"]),
        ],
    )
    assert len(intent.keywords_en) == 3
    assert intent.keywords_zh == []
    assert intent.output_language == "en"
    assert intent.cache_key == ""


def test_intent_requires_at_least_one_keyword() -> None:
    with pytest.raises(ValidationError):
        Intent(
            keywords_en=[],
            app_type="web",
            target_scenario="test",
            output_language="en",
            search_queries=[SearchQuery(platform=Platform.GITHUB, queries=["t"])],
        )


def test_intent_cache_key_deterministic() -> None:
    intent = Intent(
        keywords_en=["notes", "markdown", "browser extension"],
        app_type="browser-extension",
        target_scenario="test",
        output_language="en",
        search_queries=[SearchQuery(platform=Platform.GITHUB, queries=["test"])],
    )
    key = intent.compute_cache_key()
    assert len(key) == 16

    intent2 = Intent(
        keywords_en=["browser extension", "markdown", "notes"],
        app_type="browser-extension",
        target_scenario="totally different text",
        output_language="zh",
        search_queries=[SearchQuery(platform=Platform.TAVILY, queries=["other"])],
    )
    assert intent2.compute_cache_key() == key


# --- Competitor ---


def test_competitor_valid() -> None:
    c = Competitor(
        name="Markdownify",
        links=["https://markdownify.app"],
        one_liner="Convert web pages to Markdown",
        source_platforms=[Platform.TAVILY],
        source_urls=["https://google.com/search?q=test"],
    )
    assert c.name == "Markdownify"
    assert c.relevance_score == 0.5
    assert c.pricing is None
    assert c.features == []


def test_competitor_requires_at_least_one_link() -> None:
    with pytest.raises(ValidationError):
        Competitor(
            name="No Link",
            links=[],
            one_liner="test",
            source_platforms=[Platform.GITHUB],
            source_urls=["https://example.com"],
        )


def test_competitor_relevance_score_bounds() -> None:
    with pytest.raises(ValidationError):
        Competitor(
            name="T",
            links=["https://a.com"],
            one_liner="t",
            source_platforms=[Platform.GITHUB],
            source_urls=["https://a.com"],
            relevance_score=1.5,
        )
    with pytest.raises(ValidationError):
        Competitor(
            name="T",
            links=["https://a.com"],
            one_liner="t",
            source_platforms=[Platform.GITHUB],
            source_urls=["https://a.com"],
            relevance_score=-0.1,
        )


# --- SourceResult ---


def test_source_status_values() -> None:
    assert SourceStatus.OK == "ok"
    assert SourceStatus.DEGRADED == "degraded"
    assert SourceStatus.TIMEOUT == "timeout"


def test_source_result_ok() -> None:
    sr = SourceResult(platform=Platform.GITHUB, status=SourceStatus.OK, raw_count=8)
    assert sr.error_msg is None
    assert sr.competitors == []
    assert sr.duration_ms == 0


def test_source_result_failed() -> None:
    sr = SourceResult(
        platform=Platform.TAVILY,
        status=SourceStatus.FAILED,
        error_msg="API key invalid",
    )
    assert sr.error_msg == "API key invalid"


# --- ResearchReport ---


def _make_intent() -> Intent:
    return Intent(
        keywords_en=["test"],
        app_type="web",
        target_scenario="test scenario",
        output_language="en",
        search_queries=[SearchQuery(platform=Platform.GITHUB, queries=["test"])],
    )


def test_report_auto_generates_id() -> None:
    r = ResearchReport(query="test idea", intent=_make_intent())
    assert len(r.id) > 0
    assert r.competitors == []
    assert r.market_summary == ""
    assert r.go_no_go == ""
    assert r.confidence == ConfidenceMetrics()
    assert r.evidence_summary == EvidenceSummary()
    assert r.cost_breakdown == CostBreakdown()
    assert r.report_meta == ReportMeta()


def test_report_serialization_roundtrip() -> None:
    r = ResearchReport(query="test", intent=_make_intent(), go_no_go="Go")
    data = r.model_dump(mode="json")
    r2 = ResearchReport.model_validate(data)
    assert r2.id == r.id
    assert r2.go_no_go == "Go"
    assert r2.created_at == r.created_at
    assert r2.confidence.score == 0
    assert r2.evidence_summary.top_evidence == []
    assert r2.cost_breakdown.llm_calls == 0
    assert r2.report_meta.llm_fault_tolerance.fallback_used is False


# --- RecommendationType ---


def test_recommendation_type_enum_values() -> None:
    assert RecommendationType.GO == "go"
    assert RecommendationType.CAUTION == "caution"
    assert RecommendationType.NO_GO == "no_go"


def test_report_default_recommendation_type() -> None:
    r = ResearchReport(query="test", intent=_make_intent())
    assert r.recommendation_type == RecommendationType.GO


def test_report_with_explicit_recommendation_type() -> None:
    r = ResearchReport(
        query="test",
        intent=_make_intent(),
        recommendation_type=RecommendationType.CAUTION,
    )
    assert r.recommendation_type == RecommendationType.CAUTION
    data = r.model_dump(mode="json")
    assert data["recommendation_type"] == "caution"
    r2 = ResearchReport.model_validate(data)
    assert r2.recommendation_type == RecommendationType.CAUTION
