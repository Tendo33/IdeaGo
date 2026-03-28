"""Tests for research domain models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

import ideago.models as exported_models
from ideago.models.research import (
    CommercialSignal,
    Competitor,
    ConfidenceMetrics,
    CostBreakdown,
    EvidenceCategory,
    EvidenceItem,
    EvidenceSummary,
    Intent,
    OpportunityScoreBreakdown,
    PainSignal,
    Platform,
    QueryFamily,
    QueryGroup,
    QueryPlan,
    QueryRewrite,
    RawResult,
    RecommendationType,
    RelevanceKind,
    ReportMeta,
    ResearchReport,
    SearchQuery,
    SourceResult,
    SourceStatus,
    WhitespaceOpportunity,
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
        exact_entities=["Browser Extension"],
        comparison_anchors=["Notion Web Clipper"],
        search_goal="find_direct_competitors",
        search_queries=[
            SearchQuery(platform=Platform.GITHUB, queries=["markdown notes extension"]),
        ],
    )
    assert len(intent.keywords_en) == 3
    assert intent.keywords_zh == []
    assert intent.output_language == "en"
    assert intent.exact_entities == ["Browser Extension"]
    assert intent.comparison_anchors == ["Notion Web Clipper"]
    assert intent.search_goal == "find_direct_competitors"
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
        search_goal="find_direct_competitors",
        search_queries=[SearchQuery(platform=Platform.GITHUB, queries=["test"])],
    )
    key = intent.compute_cache_key()
    assert len(key) == 16

    intent2 = Intent(
        keywords_en=["browser extension", "markdown", "notes"],
        app_type="browser-extension",
        target_scenario="test",
        output_language="en",
        search_goal="find_direct_competitors",
        search_queries=[SearchQuery(platform=Platform.TAVILY, queries=["other"])],
    )
    assert intent2.compute_cache_key() == key


def test_intent_cache_key_changes_when_report_semantics_change() -> None:
    base_intent = Intent(
        keywords_en=["notes", "markdown", "browser extension"],
        app_type="browser-extension",
        target_scenario="take markdown notes",
        output_language="en",
        search_goal="find_direct_competitors",
        search_queries=[SearchQuery(platform=Platform.GITHUB, queries=["test"])],
    )

    zh_intent = base_intent.model_copy(update={"output_language": "zh"})
    scenario_intent = base_intent.model_copy(
        update={"target_scenario": "capture team knowledge"}
    )
    goal_intent = base_intent.model_copy(update={"search_goal": "find_market_evidence"})

    assert zh_intent.compute_cache_key() != base_intent.compute_cache_key()
    assert scenario_intent.compute_cache_key() != base_intent.compute_cache_key()
    assert goal_intent.compute_cache_key() != base_intent.compute_cache_key()


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
    assert c.relevance_kind == RelevanceKind.DIRECT
    assert c.pricing is None
    assert c.features == []


def test_competitor_supports_adjacent_relevance_kind() -> None:
    competitor = Competitor(
        name="Cursor",
        links=["https://cursor.com"],
        one_liner="AI-first code editor",
        relevance_kind="adjacent",
        source_platforms=[Platform.TAVILY],
        source_urls=["https://cursor.com"],
    )

    assert competitor.relevance_kind == RelevanceKind.ADJACENT


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
    assert r.pain_signals == []
    assert r.commercial_signals == []
    assert r.whitespace_opportunities == []
    assert r.opportunity_score == OpportunityScoreBreakdown()
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


def test_evidence_category_enum_values() -> None:
    assert EvidenceCategory.COMPETITOR == "competitor"
    assert EvidenceCategory.PAIN == "pain"
    assert EvidenceCategory.COMMERCIAL == "commercial"
    assert EvidenceCategory.MIGRATION == "migration"
    assert EvidenceCategory.WHITESPACE == "whitespace"
    assert EvidenceCategory.MARKET == "market"


def test_pain_signal_validation_bounds() -> None:
    with pytest.raises(ValidationError):
        PainSignal(theme="onboarding friction", intensity=1.1)
    with pytest.raises(ValidationError):
        PainSignal(theme="onboarding friction", frequency=-0.1)


def test_commercial_signal_validation_bounds() -> None:
    with pytest.raises(ValidationError):
        CommercialSignal(theme="high intent", intent_strength=1.5)


def test_whitespace_opportunity_validation_bounds() -> None:
    with pytest.raises(ValidationError):
        WhitespaceOpportunity(
            title="SMB workflow wedge",
            potential_score=-0.01,
        )
    with pytest.raises(ValidationError):
        WhitespaceOpportunity(
            title="SMB workflow wedge",
            confidence=1.01,
        )


def test_opportunity_score_breakdown_validation_bounds() -> None:
    with pytest.raises(ValidationError):
        OpportunityScoreBreakdown(solution_gap=2.0)
    with pytest.raises(ValidationError):
        OpportunityScoreBreakdown(score=-0.1)


def test_opportunity_score_breakdown_roundtrip_payload() -> None:
    breakdown = OpportunityScoreBreakdown(
        pain_intensity=0.72,
        solution_gap=0.64,
        commercial_intent=0.51,
        freshness=0.88,
        competition_density=0.27,
        score=0.69,
    )

    payload = breakdown.model_dump(mode="json")
    restored = OpportunityScoreBreakdown.model_validate(payload)

    assert restored == breakdown


def test_richer_evidence_item_defaults() -> None:
    item = EvidenceItem()
    assert item.title == ""
    assert item.url == ""
    assert item.platform is None
    assert item.snippet == ""
    assert item.category == EvidenceCategory.MARKET
    assert item.freshness_hint == ""
    assert item.matched_query == ""
    assert item.query_family == ""


def test_query_plan_models_are_typed() -> None:
    rewrite = QueryRewrite(
        query='"claude code" gui',
        family=QueryFamily.DIRECT_COMPETITOR,
        purpose="Find direct GUI wrappers around Claude Code.",
    )
    group = QueryGroup(
        family=QueryFamily.DIRECT_COMPETITOR,
        anchor_terms=["Claude Code"],
        comparison_anchors=["Cursor"],
        rewritten_queries=[rewrite],
    )
    plan = QueryPlan(query_groups=[group])

    assert plan.query_groups[0].family == QueryFamily.DIRECT_COMPETITOR
    assert plan.query_groups[0].anchor_terms == ["Claude Code"]
    assert plan.query_groups[0].comparison_anchors == ["Cursor"]
    assert plan.query_groups[0].rewritten_queries[0].query == '"claude code" gui'


def test_richer_evidence_summary_defaults() -> None:
    summary = EvidenceSummary()
    assert summary.top_evidence == []
    assert summary.evidence_items == []
    assert summary.category_counts == {}
    assert summary.source_platforms == []
    assert summary.freshness_distribution == {}
    assert summary.degraded_sources == []
    assert summary.uncertainty_notes == []


def test_richer_confidence_metrics_defaults() -> None:
    metrics = ConfidenceMetrics()
    assert metrics.sample_size == 0
    assert metrics.source_coverage == 0
    assert metrics.source_success_rate == 0.0
    assert metrics.source_diversity == 0
    assert metrics.evidence_density == 0.0
    assert metrics.recency_score == 0.0
    assert metrics.degradation_penalty == 0.0
    assert metrics.contradiction_penalty == 0.0
    assert metrics.reasons == []
    assert metrics.score == 0


def test_research_report_additive_compatibility_with_legacy_payload() -> None:
    report = ResearchReport(query="legacy payload", intent=_make_intent())
    payload = report.model_dump(mode="json")

    payload.pop("pain_signals", None)
    payload.pop("commercial_signals", None)
    payload.pop("whitespace_opportunities", None)
    payload.pop("opportunity_score", None)

    confidence = payload.get("confidence", {})
    confidence.pop("source_diversity", None)
    confidence.pop("evidence_density", None)
    confidence.pop("recency_score", None)
    confidence.pop("degradation_penalty", None)
    confidence.pop("contradiction_penalty", None)
    confidence.pop("reasons", None)
    payload["confidence"] = confidence

    evidence_summary = payload.get("evidence_summary", {})
    evidence_summary.pop("category_counts", None)
    evidence_summary.pop("source_platforms", None)
    evidence_summary.pop("freshness_distribution", None)
    evidence_summary.pop("degraded_sources", None)
    evidence_summary.pop("uncertainty_notes", None)
    payload["evidence_summary"] = evidence_summary

    restored = ResearchReport.model_validate(payload)
    assert restored.pain_signals == []
    assert restored.commercial_signals == []
    assert restored.whitespace_opportunities == []
    assert restored.opportunity_score == OpportunityScoreBreakdown()
    assert restored.confidence.source_diversity == 0
    assert restored.confidence.evidence_density == 0.0
    assert restored.confidence.recency_score == 0.0
    assert restored.confidence.degradation_penalty == 0.0
    assert restored.confidence.contradiction_penalty == 0.0
    assert restored.confidence.reasons == []
    assert restored.evidence_summary.category_counts == {}
    assert restored.evidence_summary.source_platforms == []
    assert restored.evidence_summary.freshness_distribution == {}
    assert restored.evidence_summary.degraded_sources == []
    assert restored.evidence_summary.uncertainty_notes == []


def test_legacy_nested_evidence_items_payload_compatibility() -> None:
    payload = ResearchReport(query="legacy evidence", intent=_make_intent()).model_dump(
        mode="json"
    )
    payload["evidence_summary"] = {
        "top_evidence": ["legacy item"],
        "evidence_items": [
            {
                "title": "GitHub discussion",
                "url": "https://github.com/org/repo/issues/1",
                "platform": "github",
                "snippet": "users complain about onboarding",
            },
            {
                "title": "Legacy no-platform evidence",
                "url": "https://example.com/thread",
                "platform": "",
                "snippet": "legacy exporter omitted normalized platform",
            },
        ],
    }

    restored = ResearchReport.model_validate(payload)
    assert len(restored.evidence_summary.evidence_items) == 2
    assert restored.evidence_summary.evidence_items[0].platform == Platform.GITHUB
    assert restored.evidence_summary.evidence_items[1].platform is None
    assert (
        restored.evidence_summary.evidence_items[0].category == EvidenceCategory.MARKET
    )
    assert restored.evidence_summary.category_counts == {}
    assert restored.evidence_summary.source_platforms == []
    assert restored.evidence_summary.freshness_distribution == {}
    assert restored.evidence_summary.degraded_sources == []
    assert restored.evidence_summary.uncertainty_notes == []


def test_new_models_exported_from_models_package() -> None:
    assert exported_models.PainSignal is PainSignal
    assert exported_models.CommercialSignal is CommercialSignal
    assert exported_models.WhitespaceOpportunity is WhitespaceOpportunity
    assert exported_models.OpportunityScoreBreakdown is OpportunityScoreBreakdown
    assert exported_models.EvidenceCategory is EvidenceCategory


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
