"""Tests for deterministic per-platform query builder."""

from __future__ import annotations

import pytest

from ideago.models.research import Intent, Platform
from ideago.pipeline.query_builder import (
    _clean_keywords,
    _slugify,
    build_queries,
    build_query_families,
    infer_query_family,
)
from ideago.pipeline.query_planning import (
    adapt_query_plan_for_platform,
    build_query_plan,
)


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

    def test_supports_review_problem_category_phrasing(self) -> None:
        families = build_query_families(
            Platform.APPSTORE,
            _make_intent(app_type="mobile"),
        )
        workflow_queries = families.get("workflow_discovery", [])
        pain_queries = families.get("pain_discovery", [])
        assert "lifestyle" in workflow_queries or "utilities" in workflow_queries
        assert any("review" in query for query in pain_queries)
        assert any("problem" in query for query in pain_queries)

    def test_build_queries_preserves_review_problem_phrasing_under_cap(self) -> None:
        queries = build_queries(
            Platform.APPSTORE,
            _make_intent(app_type="mobile"),
        )
        assert any("review" in query for query in queries)
        assert any("problem" in query for query in queries)

    def test_build_queries_preserves_pain_family_metadata_under_cap(self) -> None:
        queries = build_queries(
            Platform.APPSTORE,
            _make_intent(app_type="mobile"),
        )
        review_query = next(query for query in queries if "review" in query)
        assert isinstance(review_query, str)
        assert review_query.query_family == "pain_discovery"
        assert infer_query_family(review_query) == "pain_discovery"


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

    def test_supports_launch_and_positioning_phrasing(self) -> None:
        families = build_query_families(Platform.PRODUCT_HUNT, _make_intent())
        launch_queries = families.get("launch_discovery", [])
        positioning_queries = families.get("positioning_discovery", [])
        assert launch_queries
        assert any("positioning" in query for query in positioning_queries)

    def test_build_queries_preserves_positioning_under_cap(self) -> None:
        queries = build_queries(Platform.PRODUCT_HUNT, _make_intent())
        assert any("positioning" in query for query in queries)

    def test_build_queries_preserves_positioning_metadata_under_cap(self) -> None:
        queries = build_queries(Platform.PRODUCT_HUNT, _make_intent())
        positioning_query = next(query for query in queries if "positioning" in query)
        assert isinstance(positioning_query, str)
        assert positioning_query.query_family == "positioning_discovery"
        assert infer_query_family(positioning_query) == "positioning_discovery"


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
    def test_builds_explicit_research_intent_families(self) -> None:
        families = build_query_families(Platform.TAVILY, _make_intent())
        assert "competitor_discovery" in families
        assert "alternative_discovery" in families
        assert "pain_discovery" in families
        assert "workflow_discovery" in families
        assert "commercial_discovery" in families

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
    def test_reddit_query_families_cover_pain_alternative_and_migration(self) -> None:
        families = build_query_families(Platform.REDDIT, _make_intent())
        assert "pain_discovery" in families
        assert "alternative_discovery" in families
        assert "migration_discovery" in families

    def test_tavily_gets_broader_family_coverage_than_github(self) -> None:
        tavily_families = build_query_families(Platform.TAVILY, _make_intent())
        github_families = build_query_families(Platform.GITHUB, _make_intent())
        assert len(tavily_families) > len(github_families)

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


class TestQueryPlanningRewriting:
    def test_build_query_plan_preserves_exact_entities_and_comparison_anchors(
        self,
    ) -> None:
        intent = Intent(
            keywords_en=["visual editor", "agent IDE"],
            keywords_zh=["可视化编辑器"],
            app_type="web",
            target_scenario="为 Claude Code 提供可视化界面",
            output_language="zh",
            exact_entities=["Claude Code"],
            comparison_anchors=["Cursor"],
            search_goal="find_direct_competitors",
            cache_key="query-plan",
        )

        plan = build_query_plan(intent)

        assert plan.query_groups
        direct_group = next(
            group for group in plan.query_groups if group.family == "direct_competitor"
        )
        assert "Claude Code" in direct_group.anchor_terms
        assert "Cursor" in direct_group.comparison_anchors
        assert any(
            "claude code" in rewrite.query.lower()
            for rewrite in direct_group.rewritten_queries
        )

    def test_platform_adaptation_generates_repo_and_product_discovery_queries(
        self,
    ) -> None:
        intent = Intent(
            keywords_en=["visual editor", "agent IDE"],
            app_type="web",
            target_scenario="为 Claude Code 提供可视化界面",
            output_language="en",
            exact_entities=["Claude Code"],
            comparison_anchors=["Cursor"],
            search_goal="find_direct_competitors",
            cache_key="query-plan",
        )
        plan = build_query_plan(intent)

        github_queries = adapt_query_plan_for_platform(Platform.GITHUB, plan, intent)
        tavily_queries = adapt_query_plan_for_platform(Platform.TAVILY, plan, intent)

        assert any(
            "claude code" in query.lower()
            for query in github_queries["competitor_discovery"]
        )
        assert any(
            "topic:" in query or "gui" in query.lower()
            for query in github_queries["workflow_discovery"]
        )
        assert any(
            "visual interface for claude code" in query.lower()
            or "claude code gui" in query.lower()
            for query in tavily_queries["competitor_discovery"]
        )

    def test_query_builder_does_not_run_implicit_planning_without_query_plan(
        self,
    ) -> None:
        intent = Intent(
            keywords_en=["visual editor"],
            app_type="web",
            target_scenario="为 Claude Code 提供可视化界面",
            output_language="zh",
            exact_entities=["Claude Code"],
            comparison_anchors=["Cursor"],
            search_goal="find_direct_competitors",
            cache_key="query-plan",
        )

        families = build_query_families(Platform.TAVILY, intent, query_plan=None)

        competitor_queries = families.get("competitor_discovery", [])
        assert competitor_queries
        assert all("claude code" not in query.lower() for query in competitor_queries)


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
