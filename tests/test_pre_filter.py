"""Tests for ideago.pipeline.pre_filter."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from ideago.models.research import OpportunityScoreBreakdown, Platform, RawResult
from ideago.pipeline.pre_filter import (
    _freshness_signal,
    _parse_iso8601,
    _quality_score,
    _safe_float,
    _safe_int,
    build_opportunity_score_breakdown,
    filter_raw_results,
)

# The freshness component is f(raw_data["freshness_timestamp"], RawResult.fetched_at).
# RawResult.fetched_at defaults to wall-clock now(), so leaving it unset makes every
# scoring assertion below drift with the calendar and eventually fail on its own.
# Pin the anchor, and place fixture timestamps 60 days before it so they land in the
# ">30d, <=90d" bucket (freshness 0.8) these assertions were originally written against.
_FIXED_FETCHED_AT = datetime(2026, 5, 19, tzinfo=timezone.utc)
_RECENT_TIMESTAMP = "2026-03-20T00:00:00Z"


def _raw(
    platform: Platform,
    title: str = "Test",
    description: str = "desc",
    url: str = "https://example.com",
    fetched_at: datetime = _FIXED_FETCHED_AT,
    **raw_data: object,
) -> RawResult:
    return RawResult(
        title=title,
        description=description,
        url=url,
        platform=platform,
        raw_data=dict(raw_data),
        fetched_at=fetched_at,
    )


def test_fixture_fetched_at_is_pinned() -> None:
    """Guard: fixtures must not inherit wall-clock fetched_at, or scoring tests rot."""
    assert _raw(Platform.TAVILY).fetched_at == _FIXED_FETCHED_AT


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
            freshness_timestamp=_RECENT_TIMESTAMP,
        )
        signal_rich = _raw(
            Platform.TAVILY,
            title="Need a Better Team Wiki",
            description=description,
            matched_query=matched_query,
            query_family=query_family,
            source_native_score=0.24,
            engagement_proxy=0.24,
            freshness_timestamp=_RECENT_TIMESTAMP,
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
        # Locks the pinned anchor: if someone drops fetched_at back to wall-clock
        # now(), this fails immediately instead of rotting silently months later.
        assert breakdown.freshness == pytest.approx(0.8)
        assert breakdown.score > popularity_breakdown.score
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
        # Not exactly zero: an undated result now carries the neutral freshness
        # prior (0.3) rather than being scored as ancient.
        assert score == pytest.approx(0.027, abs=0.005)

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
            freshness_timestamp=_RECENT_TIMESTAMP,
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
            freshness_timestamp=_RECENT_TIMESTAMP,
        )

        breakdown = build_opportunity_score_breakdown(result)

        assert breakdown.competition_density > 0.7
        assert breakdown.pain_intensity < 0.2
        assert breakdown.solution_gap < 0.2
        assert breakdown.commercial_intent == pytest.approx(0.0)
        assert breakdown.score <= 0.4


class TestFreshnessSignal:
    """Freshness bucketing, exercised deterministically.

    These buckets used to be covered only incidentally, by whatever distance the
    real calendar happened to put between a fixture timestamp and wall-clock now().
    That made both the assertions and the coverage itself date-dependent. Every
    case below pins the anchor explicitly.
    """

    @pytest.mark.parametrize(
        ("age_days", "expected"),
        [
            (0, 1.0),
            (30, 1.0),
            (31, 0.8),
            (90, 0.8),
            (91, 0.6),
            (180, 0.6),
            (181, 0.4),
            (365, 0.4),
            (366, 0.2),
            (730, 0.2),
            (731, 0.0),
            (5000, 0.0),
        ],
    )
    def test_buckets_by_age(self, age_days: int, expected: float) -> None:
        published = _FIXED_FETCHED_AT - timedelta(days=age_days)
        signal = _freshness_signal(published.isoformat(), _FIXED_FETCHED_AT)
        assert signal == pytest.approx(expected)

    def test_future_timestamp_clamps_to_newest_bucket(self) -> None:
        """A source reporting a future date must not produce a negative age."""
        published = _FIXED_FETCHED_AT + timedelta(days=10)
        assert _freshness_signal(published.isoformat(), _FIXED_FETCHED_AT) == 1.0

    @pytest.mark.parametrize("value", [None, "", "   ", "not-a-date", 12345, {}])
    def test_unknown_timestamp_gets_a_neutral_prior(self, value: object) -> None:
        """Unknown age is not evidence of staleness.

        Returning 0.0 here scored "we cannot tell how old this is" *worse* than
        ">2 years old" (0.2). Tavily's general search returns no date at all, so
        every one of its results paid that penalty — the source supplying ~39%
        of evidence and ~94% of competitor matches.
        """
        assert _freshness_signal(value, _FIXED_FETCHED_AT) == pytest.approx(0.3)

    def test_unknown_scores_between_ancient_and_recent(self) -> None:
        ancient = _freshness_signal(
            (_FIXED_FETCHED_AT - timedelta(days=1200)).isoformat(), _FIXED_FETCHED_AT
        )
        recent = _freshness_signal(
            (_FIXED_FETCHED_AT - timedelta(days=10)).isoformat(), _FIXED_FETCHED_AT
        )
        unknown = _freshness_signal(None, _FIXED_FETCHED_AT)
        assert ancient < unknown < recent

    def test_naive_timestamp_is_treated_as_utc(self) -> None:
        assert _parse_iso8601("2026-05-19T00:00:00") == _FIXED_FETCHED_AT

    def test_zulu_suffix_is_parsed(self) -> None:
        assert _parse_iso8601("2026-05-19T00:00:00Z") == _FIXED_FETCHED_AT

    def test_offset_timestamp_is_normalized_to_utc(self) -> None:
        assert _parse_iso8601("2026-05-19T08:00:00+08:00") == _FIXED_FETCHED_AT

    def test_fetched_at_in_other_timezone_is_normalized(self) -> None:
        """The anchor is normalized to UTC before the age subtraction."""
        anchor = _FIXED_FETCHED_AT.astimezone(timezone(timedelta(hours=9)))
        published = _FIXED_FETCHED_AT - timedelta(days=100)
        assert _freshness_signal(published.isoformat(), anchor) == pytest.approx(0.6)


class TestPlannerFamilyAliases:
    """The LLM planner speaks QueryFamily; the scorer speaks its own vocabulary.

    Three of the six names differ. An unmatched family gets no signal baseline
    at all, so those results end up ranked on popularity alone — which reads as
    "alternative discovery quietly stopped working" once the planner is live.
    """

    @pytest.mark.parametrize(
        ("planner_family", "scoring_family"),
        [
            ("direct_competitor", "competitor_discovery"),
            ("adjacent_analogy", "alternative_discovery"),
            ("workflow_interface", "workflow_discovery"),
        ],
    )
    def test_planner_family_scores_like_its_native_equivalent(
        self, planner_family: str, scoring_family: str
    ) -> None:
        def build(family: str) -> float:
            return build_opportunity_score_breakdown(
                _raw(
                    Platform.TAVILY,
                    title="Zotero",
                    description="A free reference manager for researchers",
                    matched_query="reference manager alternative",
                    query_family=family,
                    score=0.6,
                    engagement_proxy=0.6,
                )
            ).score

        assert build(planner_family) == pytest.approx(build(scoring_family))

    def test_every_planner_family_is_understood(self) -> None:
        """No QueryFamily value may fall through to a zero signal baseline."""
        from ideago.models.research import QueryFamily
        from ideago.pipeline.pre_filter import (
            _FAMILY_BASE_COMPONENTS,
            _canonical_family,
        )

        unmapped = [
            family.value
            for family in QueryFamily
            if _canonical_family(family.value) not in _FAMILY_BASE_COMPONENTS
        ]
        assert not unmapped, (
            f"planner families with no scoring baseline: {unmapped}. "
            "Add an alias in _PLANNER_FAMILY_ALIASES or a baseline entry."
        )

    def test_unknown_family_passes_through_unchanged(self) -> None:
        from ideago.pipeline.pre_filter import _canonical_family

        assert _canonical_family("pain_discovery") == "pain_discovery"
        assert _canonical_family("something_new") == "something_new"


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
