"""Tests for ideago.pipeline.pre_filter."""

from __future__ import annotations

import pytest

from ideago.models.research import OpportunityScoreBreakdown, Platform, RawResult
from ideago.pipeline.pre_filter import (
    _quality_score,
    _safe_float,
    _safe_int,
    build_opportunity_score_breakdown,
    filter_raw_results,
)


def _raw(
    platform: Platform,
    title: str = "Test",
    description: str = "desc",
    url: str = "https://example.com",
    **raw_data: object,
) -> RawResult:
    return RawResult(
        title=title,
        description=description,
        url=url,
        platform=platform,
        raw_data=dict(raw_data),
    )


class TestFilterRawResults:
    def test_empty_input_returns_empty(self) -> None:
        assert filter_raw_results({}) == {}

    def test_caps_results_per_source(self) -> None:
        results = [_raw(Platform.GITHUB, title=f"r{i}") for i in range(10)]
        filtered = filter_raw_results({"github": results}, max_per_source=3)
        assert len(filtered["github"]) == 3

    def test_keeps_top_15_ranked_results_for_extractor_budget(self) -> None:
        results = [_raw(Platform.GITHUB, title=f"r{i}") for i in range(20)]
        filtered = filter_raw_results({"github": results}, max_per_source=15)
        assert len(filtered["github"]) == 15

    def test_sorts_by_quality_descending(self) -> None:
        low = _raw(Platform.GITHUB, title="low", stargazers_count=1)
        high = _raw(Platform.GITHUB, title="high", stargazers_count=5000)
        filtered = filter_raw_results({"github": [low, high]}, max_per_source=2)
        assert filtered["github"][0].title == "high"

    def test_skips_empty_source_lists(self) -> None:
        filtered = filter_raw_results({"github": [], "tavily": [_raw(Platform.TAVILY)]})
        assert "github" not in filtered
        assert "tavily" in filtered

    def test_max_per_source_minimum_one(self) -> None:
        results = [_raw(Platform.GITHUB)]
        filtered = filter_raw_results({"github": results}, max_per_source=0)
        assert len(filtered["github"]) == 1

    @pytest.mark.parametrize(
        ("query_family", "matched_query", "description", "expected_component"),
        [
            (
                "pain_discovery",
                "api monitoring pain complaints",
                "Teams complain the setup is brittle and noisy.",
                "pain_intensity",
            ),
            (
                "alternative_discovery",
                "notion alternative",
                "Users are actively looking for replacements and better options.",
                "solution_gap",
            ),
            (
                "commercial_discovery",
                "team wiki pricing",
                "Buyers discuss budget, pricing, and paid upgrade demand.",
                "commercial_intent",
            ),
        ],
    )
    def test_signal_rich_results_can_outrank_popularity_only_results(
        self,
        query_family: str,
        matched_query: str,
        description: str,
        expected_component: str,
    ) -> None:
        popularity_only = _raw(
            Platform.TAVILY,
            title="Best Team Wiki Competitors",
            description="Roundup of popular competitors.",
            matched_query="best team wiki competitor",
            query_family="competitor_discovery",
            source_native_score=0.98,
            engagement_proxy=0.98,
            freshness_timestamp="2026-03-20T00:00:00Z",
        )
        signal_rich = _raw(
            Platform.TAVILY,
            title="Need a Better Team Wiki",
            description=description,
            matched_query=matched_query,
            query_family=query_family,
            source_native_score=0.24,
            engagement_proxy=0.24,
            freshness_timestamp="2026-03-20T00:00:00Z",
        )

        filtered = filter_raw_results(
            {"tavily": [popularity_only, signal_rich]},
            max_per_source=2,
        )

        assert filtered["tavily"][0].title == "Need a Better Team Wiki"
        breakdown = OpportunityScoreBreakdown.model_validate(
            signal_rich.raw_data["opportunity_score_breakdown"]
        )
        popularity_breakdown = OpportunityScoreBreakdown.model_validate(
            popularity_only.raw_data["opportunity_score_breakdown"]
        )
        assert getattr(breakdown, expected_component) > 0.55
        assert breakdown.score >= 0.52
        assert popularity_breakdown.score <= 0.45
        assert breakdown.score - popularity_breakdown.score >= 0.15


class TestQualityScore:
    def test_github_high_stars(self) -> None:
        r = _raw(Platform.GITHUB, stargazers_count=1000, forks_count=50)
        score = _quality_score(r)
        assert score > 0.15

    def test_github_zero_stars(self) -> None:
        r = _raw(Platform.GITHUB, stargazers_count=0, forks_count=0, description="")
        score = _quality_score(r)
        assert score == pytest.approx(0.0, abs=0.01)

    def test_hackernews_high_points(self) -> None:
        r = _raw(Platform.HACKERNEWS, points=300, num_comments=60)
        score = _quality_score(r)
        assert score > 0.2

    def test_appstore_rating(self) -> None:
        r = _raw(Platform.APPSTORE, user_rating_count=10000, average_user_rating=4.5)
        score = _quality_score(r)
        assert score > 0.15

    def test_producthunt_votes(self) -> None:
        r = _raw(Platform.PRODUCT_HUNT, votes_count=500)
        score = _quality_score(r)
        assert score > 0.15

    def test_tavily_score(self) -> None:
        r = _raw(Platform.TAVILY, score=0.8)
        score = _quality_score(r)
        assert score > 0.15

    def test_unknown_platform_with_description(self) -> None:
        r = _raw(Platform.GOOGLE_TRENDS, description="something")
        score = _quality_score(r)
        assert score == pytest.approx(0.5, abs=0.01)

    def test_quality_score_populates_breakdown_in_raw_data(self) -> None:
        result = _raw(
            Platform.REDDIT,
            title="Switching from Tool A",
            description="Switch from Tool A because the workflow breaks often.",
            matched_query="switch from tool a",
            query_family="migration_discovery",
            score=42,
            num_comments=18,
            freshness_timestamp="2026-03-22T00:00:00Z",
        )

        score = _quality_score(result)

        assert score > 0.0
        breakdown = OpportunityScoreBreakdown.model_validate(
            result.raw_data["opportunity_score_breakdown"]
        )
        assert breakdown.solution_gap > 0.5
        assert breakdown.pain_intensity > 0.3
        assert result.raw_data["opportunity_score"] == pytest.approx(breakdown.score)

    def test_build_opportunity_score_breakdown_penalizes_popularity_only_density(
        self,
    ) -> None:
        result = _raw(
            Platform.GITHUB,
            title="Popular Repo",
            description="Well-known developer tool",
            matched_query="best developer tool competitor",
            query_family="competitor_discovery",
            stargazers_count=4800,
            forks_count=600,
            freshness_timestamp="2026-03-22T00:00:00Z",
        )

        breakdown = build_opportunity_score_breakdown(result)

        assert breakdown.competition_density > 0.7
        assert breakdown.pain_intensity < 0.2
        assert breakdown.solution_gap < 0.2
        assert breakdown.commercial_intent == pytest.approx(0.0)
        assert breakdown.score <= 0.4


class TestSafeConversions:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (42, 42),
            (3.7, 3),
            ("100", 100),
            ("bad", 0),
            (None, 0),
            (True, 0),
        ],
    )
    def test_safe_int(self, value: object, expected: int) -> None:
        assert _safe_int(value) == expected

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (3.14, 3.14),
            (7, 7.0),
            ("2.5", 2.5),
            ("bad", 0.0),
            (None, 0.0),
            (True, 0.0),
        ],
    )
    def test_safe_float(self, value: object, expected: float) -> None:
        assert _safe_float(value) == pytest.approx(expected)
