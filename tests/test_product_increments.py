"""Product increments: force refresh and idempotent quota warnings."""

from __future__ import annotations

import pytest

from ideago.api.routes import analyze as analyze_route
from ideago.api.schemas import AnalyzeRequest
from ideago.pipeline.graph_state import GraphState


class TestForceRefresh:
    """Re-running an idea for fresh evidence was impossible without rewording it.

    A cache hit short-circuits the pipeline, so the only way to get current
    evidence was to phrase the query differently until the cache key changed.
    """

    def test_defaults_to_using_the_cache(self) -> None:
        assert AnalyzeRequest(query="a perfectly good idea").force_refresh is False

    def test_can_be_requested(self) -> None:
        request = AnalyzeRequest(query="a perfectly good idea", force_refresh=True)
        assert request.force_refresh is True

    @pytest.mark.asyncio
    async def test_cache_lookup_is_skipped_when_requested(self, monkeypatch) -> None:
        looked_up: list[str] = []

        class _Cache:
            async def get(self, cache_key, *, user_id=""):
                looked_up.append(cache_key)
                return None

        from ideago.pipeline.nodes import PipelineNodes

        nodes = object.__new__(PipelineNodes)
        nodes._cache = _Cache()
        nodes._callback = None

        from ideago.models.research import Intent, Platform, SearchQuery

        state: GraphState = {
            "intent": Intent(
                keywords_en=["x"],
                app_type="web",
                target_scenario="s",
                search_queries=[SearchQuery(platform=Platform.GITHUB, queries=["x"])],
                cache_key="key-1",
            ),
            "report_id": "r-1",
            "user_id": "u-1",
            "force_refresh": True,
        }

        result = await PipelineNodes.cache_lookup_node(nodes, state)

        assert result == {"is_cache_hit": False}
        assert looked_up == [], "force_refresh must not even consult the cache"

    @pytest.mark.asyncio
    async def test_cache_is_consulted_by_default(self) -> None:
        looked_up: list[str] = []

        class _Cache:
            async def get(self, cache_key, *, user_id=""):
                looked_up.append(cache_key)
                return None

        from ideago.models.research import Intent, Platform, SearchQuery
        from ideago.pipeline.nodes import PipelineNodes

        nodes = object.__new__(PipelineNodes)
        nodes._cache = _Cache()
        nodes._callback = None

        state: GraphState = {
            "intent": Intent(
                keywords_en=["x"],
                app_type="web",
                target_scenario="s",
                search_queries=[SearchQuery(platform=Platform.GITHUB, queries=["x"])],
                cache_key="key-2",
            ),
            "report_id": "r-2",
            "user_id": "u-1",
        }

        result = await PipelineNodes.cache_lookup_node(nodes, state)

        assert result == {"is_cache_hit": False}
        assert looked_up == ["key-2"]


class TestQuotaWarningIsIdempotent:
    """Once usage crossed the threshold, every further analysis sent an email."""

    def setup_method(self) -> None:
        analyze_route._quota_warning_sent.clear()

    def teardown_method(self) -> None:
        analyze_route._quota_warning_sent.clear()

    def test_only_the_first_claim_of_the_day_succeeds(self) -> None:
        assert analyze_route._claim_quota_warning("u1", today="2026-08-18") is True
        assert analyze_route._claim_quota_warning("u1", today="2026-08-18") is False
        assert analyze_route._claim_quota_warning("u1", today="2026-08-18") is False

    def test_a_new_day_allows_a_new_warning(self) -> None:
        assert analyze_route._claim_quota_warning("u1", today="2026-08-18") is True
        assert analyze_route._claim_quota_warning("u1", today="2026-08-19") is True

    def test_users_are_tracked_independently(self) -> None:
        assert analyze_route._claim_quota_warning("u1", today="2026-08-18") is True
        assert analyze_route._claim_quota_warning("u2", today="2026-08-18") is True
        assert analyze_route._claim_quota_warning("u1", today="2026-08-18") is False

    def test_anonymous_user_never_claims(self) -> None:
        assert analyze_route._claim_quota_warning("", today="2026-08-18") is False

    def test_memory_is_bounded(self) -> None:
        for index in range(analyze_route._QUOTA_WARNING_MAX_ENTRIES + 100):
            analyze_route._claim_quota_warning(f"u{index}", today="2026-08-18")
        assert (
            len(analyze_route._quota_warning_sent)
            <= analyze_route._QUOTA_WARNING_MAX_ENTRIES
        )

    def test_stale_days_are_evicted_before_clearing_everything(self) -> None:
        for index in range(analyze_route._QUOTA_WARNING_MAX_ENTRIES):
            analyze_route._claim_quota_warning(f"old{index}", today="2026-08-17")

        # A new day's claim should reclaim space from yesterday's entries.
        assert analyze_route._claim_quota_warning("fresh", today="2026-08-18") is True
        assert analyze_route._quota_warning_sent.get("fresh") == "2026-08-18"
