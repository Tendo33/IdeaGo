"""Tests for ideago.pipeline.pre_filter."""

from __future__ import annotations

import pytest

from ideago.models.research import Platform, RawResult
from ideago.pipeline.pre_filter import (
    _quality_score,
    _safe_float,
    _safe_int,
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


class TestQualityScore:
    def test_github_high_stars(self) -> None:
        r = _raw(Platform.GITHUB, stargazers_count=1000, forks_count=50)
        score = _quality_score(r)
        assert score > 0.5

    def test_github_zero_stars(self) -> None:
        r = _raw(Platform.GITHUB, stargazers_count=0, forks_count=0, description="")
        score = _quality_score(r)
        assert score == pytest.approx(0.0, abs=0.01)

    def test_hackernews_high_points(self) -> None:
        r = _raw(Platform.HACKERNEWS, points=300, num_comments=60)
        score = _quality_score(r)
        assert score > 0.7

    def test_appstore_rating(self) -> None:
        r = _raw(Platform.APPSTORE, user_rating_count=10000, average_user_rating=4.5)
        score = _quality_score(r)
        assert score > 0.5

    def test_producthunt_votes(self) -> None:
        r = _raw(Platform.PRODUCT_HUNT, votes_count=500)
        score = _quality_score(r)
        assert score > 0.5

    def test_tavily_score(self) -> None:
        r = _raw(Platform.TAVILY, score=0.8)
        score = _quality_score(r)
        assert score > 0.5

    def test_unknown_platform_with_description(self) -> None:
        r = _raw(Platform.GOOGLE_TRENDS, description="something")
        score = _quality_score(r)
        assert score == pytest.approx(0.5, abs=0.01)


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
