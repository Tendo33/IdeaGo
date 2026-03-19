"""Tests for ideago.pipeline.merger."""

from __future__ import annotations

from ideago.models.research import Competitor, Platform
from ideago.pipeline.merger import merge_competitors


def _comp(
    name: str,
    url: str = "https://example.com/default",
    platforms: list[Platform] | None = None,
    score: float = 0.5,
    features: list[str] | None = None,
    pricing: str | None = None,
    strengths: list[str] | None = None,
) -> Competitor:
    return Competitor(
        name=name,
        links=[url],
        one_liner=f"{name} description",
        features=features or [],
        pricing=pricing,
        strengths=strengths or [],
        weaknesses=[],
        source_platforms=platforms or [Platform.GITHUB],
        source_urls=[url],
        relevance_score=score,
    )


class TestMergeCompetitors:
    def test_empty_list(self) -> None:
        assert merge_competitors([]) == []

    def test_no_duplicates(self) -> None:
        result = merge_competitors(
            [
                _comp("A", "https://a.com"),
                _comp("B", "https://b.com"),
            ]
        )
        assert len(result) == 2

    def test_exact_url_dedup(self) -> None:
        result = merge_competitors(
            [
                _comp("A", "https://github.com/org/repo", score=0.6),
                _comp("A copy", "https://github.com/org/repo", score=0.8),
            ]
        )
        assert len(result) == 1
        assert result[0].relevance_score == 0.8

    def test_url_normalization_strips_trailing_slash(self) -> None:
        result = merge_competitors(
            [
                _comp("A", "https://example.com/path/"),
                _comp("B", "https://example.com/path"),
            ]
        )
        assert len(result) == 1

    def test_url_normalization_strips_www(self) -> None:
        result = merge_competitors(
            [
                _comp("A", "https://www.example.com"),
                _comp("B", "https://example.com"),
            ]
        )
        assert len(result) == 1

    def test_same_domain_different_paths_are_deduplicated(self) -> None:
        result = merge_competitors(
            [
                _comp("A", "https://acme.com"),
                _comp("A pricing", "https://acme.com/pricing"),
            ]
        )
        assert len(result) == 1

    def test_multi_tenant_host_keeps_distinct_entities(self) -> None:
        result = merge_competitors(
            [
                _comp("Repo A", "https://github.com/org/repo-a"),
                _comp("Repo B", "https://github.com/org/repo-b"),
            ]
        )
        assert len(result) == 2

    def test_fuzzy_name_merge(self) -> None:
        result = merge_competitors(
            [
                _comp("Markdownify", "https://site-a.com", score=0.6),
                _comp("markdownify", "https://site-a.com/pricing", score=0.7),
            ]
        )
        assert len(result) == 1
        assert result[0].relevance_score >= 0.7

    def test_fuzzy_name_without_signal_not_merged(self) -> None:
        result = merge_competitors(
            [
                _comp("Markdownify", "https://site-a.com", score=0.6),
                _comp("markdownify", "https://site-b.com", score=0.7),
            ]
        )
        assert len(result) == 2

    def test_dissimilar_names_not_merged(self) -> None:
        result = merge_competitors(
            [
                _comp("React", "https://react.dev"),
                _comp("Vue", "https://vuejs.org"),
            ]
        )
        assert len(result) == 2

    def test_multi_platform_boost(self) -> None:
        result = merge_competitors(
            [
                _comp("Tool", "https://tool.com", [Platform.GITHUB], score=0.5),
                _comp("Tool", "https://tool.com", [Platform.TAVILY], score=0.5),
            ]
        )
        assert len(result) == 1
        assert result[0].relevance_score > 0.5

    def test_completeness_boost(self) -> None:
        result = merge_competitors(
            [
                _comp(
                    "Tool",
                    "https://tool.com",
                    [Platform.GITHUB, Platform.TAVILY],
                    score=0.5,
                    features=["a", "b"],
                    pricing="Free",
                    strengths=["fast"],
                ),
            ]
        )
        assert len(result) == 1
        assert result[0].relevance_score > 0.5

    def test_sorted_by_score_descending(self) -> None:
        result = merge_competitors(
            [
                _comp("Low", "https://low.com", score=0.2),
                _comp("High", "https://high.com", score=0.9),
                _comp("Mid", "https://mid.com", score=0.5),
            ]
        )
        scores = [c.relevance_score for c in result]
        assert scores == sorted(scores, reverse=True)

    def test_features_merged(self) -> None:
        result = merge_competitors(
            [
                _comp("A", "https://a.com", features=["x", "y"]),
                _comp("A clone", "https://a.com", features=["y", "z"]),
            ]
        )
        assert len(result) == 1
        assert set(result[0].features) == {"x", "y", "z"}

    def test_pricing_carried_over(self) -> None:
        result = merge_competitors(
            [
                _comp("A", "https://a.com", pricing=None),
                _comp("A", "https://a.com", pricing="$10/mo"),
            ]
        )
        assert len(result) == 1
        assert result[0].pricing == "$10/mo"
