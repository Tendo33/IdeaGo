from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from ideago.api.errors import AppError, DependencyUnavailableError
from ideago.api.routes import analyze as analyze_route
from ideago.observability.metrics import metrics as app_metrics


@pytest.mark.asyncio
async def test_start_analysis_rolls_back_when_processing_status_cannot_persist() -> (
    None
):
    user = analyze_route.AuthUser(id="user-1", email="user@example.com")
    request = analyze_route.AnalyzeRequest(query="build a useful app")
    quota_ok = type(
        "Quota",
        (),
        {"allowed": True, "plan_limit": 5, "plan": "daily", "usage_count": 1},
    )()
    cache = type("Cache", (), {})()
    cache.put_status = AsyncMock(
        side_effect=DependencyUnavailableError(
            "report_status_persist_failed",
            dependency="supabase_report_status",
        )
    )
    refund = AsyncMock(return_value=True)
    release = AsyncMock(return_value=None)

    app_metrics.reset()
    with (
        patch(
            "ideago.api.routes.analyze.reserve_processing_report",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "ideago.api.routes.analyze.check_quota_available",
            new=AsyncMock(return_value=quota_ok),
        ),
        patch(
            "ideago.api.routes.analyze.check_and_increment_quota",
            new=AsyncMock(return_value=quota_ok),
        ),
        patch("ideago.api.routes.analyze.get_cache", return_value=cache),
        patch(
            "ideago.api.routes.analyze.refund_quota_charge",
            new=refund,
        ),
        patch(
            "ideago.api.routes.analyze.release_processing_report",
            new=release,
        ),
        pytest.raises(AppError) as exc,
    ):
        await analyze_route.start_analysis(request, user)

    assert exc.value.status_code == 503
    assert exc.value.detail == {
        "code": "DEPENDENCY_UNAVAILABLE",
        "message": "Unable to persist analysis status. Please retry.",
        "dependency": "supabase_report_status",
        "reason": "report_status_persist_failed",
    }
    refund.assert_awaited_once_with(user.id)
    release.assert_awaited_once()
    metrics = app_metrics.snapshot()
    assert metrics["event_counts"]["analysis_status_persist_failed"] == 1
    assert metrics["event_reasons"]["analysis_status_persist_failed"] == {
        "supabase_report_status": 1
    }


@pytest.mark.asyncio
async def test_terminal_status_persist_failure_is_observable_but_non_fatal() -> None:
    cache = type("Cache", (), {})()
    cache.put_status = AsyncMock(
        side_effect=DependencyUnavailableError(
            "report_status_persist_failed",
            dependency="supabase_report_status",
        )
    )

    app_metrics.reset()
    with patch("ideago.api.routes.analyze.get_cache", return_value=cache):
        await analyze_route._persist_terminal_status(
            "report-1",
            "failed",
            "query",
            error_code="PIPELINE_FAILURE",
            message="Pipeline failed. Please retry.",
            user_id="user-1",
        )

    metrics = app_metrics.snapshot()
    assert metrics["event_counts"]["analysis_status_persist_failed"] == 1
    assert metrics["event_reasons"]["analysis_status_persist_failed"] == {
        "terminal_failed": 1
    }
