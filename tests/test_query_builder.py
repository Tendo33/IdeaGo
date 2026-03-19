"""Tests for deterministic per-platform query builder."""

from __future__ import annotations

import pytest

from ideago.models.research import Intent, Platform
from ideago.pipeline.query_builder import _clean_keywords, _slugify, build_queries


def _make_intent(
    *,
    keywords_en: list[str] | None = None,
    keywords_zh: list[str] | None = None,
    app_type: str = "web",
) -> Intent:
    return Intent(
        keywords_en=keywords_en or ["markdown", "notes", "browser extension"],
        keywords_zh=keywords_zh or [],
        app_type=app_type,
        target_scenario="Test scenario",
        cache_key="test-key",
    )


class TestBuildQueriesGitHub:
    def test_produces_joined_keywords(self) -> None:
        queries = build_queries(Platform.GITHUB, _make_intent())
        assert any("markdown" in q and "notes" in q for q in queries)

    def test_produces_topic_qualifiers(self) -> None:
        queries = build_queries(Platform.GITHUB, _make_intent())
        assert any("topic:" in q for q in queries)

    def test_includes_app_type_extra(self) -> None:
        queries = build_queries(
            Platform.GITHUB,
            _make_intent(app_type="browser-extension"),
        )
        assert any("chrome extension" in q for q in queries)

    def test_respects_max_cap(self) -> None:
        intent = _make_intent(
            keywords_en=["a", "b", "c", "d", "e", "f", "g"],
        )
        queries = build_queries(Platform.GITHUB, intent)
        assert len(queries) <= 5


class TestBuildQueriesAppStore:
    def test_produces_short_queries(self) -> None:
        queries = build_queries(Platform.APPSTORE, _make_intent())
        for q in queries:
            assert len(q.split()) <= 3 or q in {"productivity"}

    def test_includes_genre_from_app_type(self) -> None:
        queries = build_queries(
            Platform.APPSTORE,
            _make_intent(app_type="browser-extension"),
        )
        assert "productivity" in queries

    def test_individual_keywords_present(self) -> None:
        queries = build_queries(Platform.APPSTORE, _make_intent())
        assert "markdown" in queries
        assert "notes" in queries


class TestBuildQueriesProductHunt:
    def test_includes_topic_slugs_from_app_type(self) -> None:
        queries = build_queries(
            Platform.PRODUCT_HUNT,
            _make_intent(app_type="browser-extension"),
        )
        assert "browser-extensions" in queries
        assert "chrome-extensions" in queries

    def test_includes_broad_keywords(self) -> None:
        queries = build_queries(Platform.PRODUCT_HUNT, _make_intent())
        assert "markdown" in queries

    def test_uses_default_hints_for_unknown_app_type(self) -> None:
        queries = build_queries(
            Platform.PRODUCT_HUNT,
            _make_intent(app_type="quantum-computing"),
        )
        assert "productivity" in queries or "developer-tools" in queries


class TestBuildQueriesHackerNews:
    def test_produces_joined_query(self) -> None:
        queries = build_queries(Platform.HACKERNEWS, _make_intent())
        assert any("markdown" in q and "notes" in q for q in queries)

    def test_produces_keyword_pairs(self) -> None:
        queries = build_queries(
            Platform.HACKERNEWS,
            _make_intent(keywords_en=["api", "monitoring", "alerts"]),
        )
        pairs = [q for q in queries if len(q.split()) == 2]
        assert len(pairs) >= 2

    def test_includes_app_type_extra(self) -> None:
        queries = build_queries(
            Platform.HACKERNEWS,
            _make_intent(app_type="cli"),
        )
        assert "cli tool" in queries


class TestBuildQueriesTavily:
    def test_produces_alternative_query(self) -> None:
        queries = build_queries(Platform.TAVILY, _make_intent())
        assert any("alternative" in q for q in queries)

    def test_produces_competitor_query(self) -> None:
        queries = build_queries(Platform.TAVILY, _make_intent())
        assert any("competitor" in q for q in queries)

    def test_produces_best_of_query(self) -> None:
        queries = build_queries(Platform.TAVILY, _make_intent())
        assert any(q.startswith("best ") for q in queries)

    def test_includes_chinese_query_when_zh_keywords_present(self) -> None:
        queries = build_queries(
            Platform.TAVILY,
            _make_intent(keywords_zh=["笔记", "浏览器扩展"]),
        )
        assert any("竞品" in q for q in queries)

    def test_no_chinese_query_when_zh_keywords_absent(self) -> None:
        queries = build_queries(
            Platform.TAVILY,
            _make_intent(keywords_zh=[]),
        )
        assert all("竞品" not in q for q in queries)


class TestBuildQueriesEdgeCases:
    def test_empty_keywords_returns_empty(self) -> None:
        intent = Intent(
            keywords_en=[""],
            keywords_zh=[],
            app_type="web",
            target_scenario="Test",
            cache_key="k",
        )
        queries = build_queries(Platform.GITHUB, intent)
        assert queries == []

    def test_deduplicates_queries(self) -> None:
        intent = _make_intent(keywords_en=["notes", "notes", "NOTES"])
        queries = build_queries(Platform.GITHUB, intent)
        lowered = [q.lower() for q in queries]
        assert len(lowered) == len(set(lowered))

    def test_unknown_platform_returns_generic(self) -> None:
        queries = build_queries(Platform.GOOGLE_TRENDS, _make_intent())
        assert len(queries) >= 1
        assert "markdown" in queries[0]


class TestHelpers:
    def test_clean_keywords_deduplicates(self) -> None:
        result = _clean_keywords(["Markdown", "markdown", "MARKDOWN"])
        assert result == ["markdown"]

    def test_clean_keywords_strips(self) -> None:
        result = _clean_keywords(["  notes  ", "  api  "])
        assert result == ["notes", "api"]

    def test_slugify_basic(self) -> None:
        assert _slugify("browser extension") == "browser-extension"
        assert _slugify("Real-Time API") == "real-time-api"
        assert _slugify("markdown") == "markdown"

    @pytest.mark.parametrize(
        ("app_type", "platform", "min_queries"),
        [
            ("web", Platform.GITHUB, 2),
            ("mobile", Platform.APPSTORE, 3),
            ("browser-extension", Platform.PRODUCT_HUNT, 3),
            ("cli", Platform.HACKERNEWS, 2),
            ("api", Platform.TAVILY, 3),
            ("desktop", Platform.GITHUB, 2),
        ],
    )
    def test_all_app_types_produce_queries(
        self, app_type: str, platform: Platform, min_queries: int
    ) -> None:
        queries = build_queries(platform, _make_intent(app_type=app_type))
        assert len(queries) >= min_queries
