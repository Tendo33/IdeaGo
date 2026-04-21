from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from ideago.api import dependencies as deps
from ideago.api.errors import AppError
from ideago.api.routes import analyze as analyze_route
from ideago.cache.file_cache import FileCache
from ideago.observability.metrics import metrics as app_metrics
from tests.test_api import reset_runtime_state  # noqa: F401


@pytest.mark.asyncio
async def test_start_analysis_quota_and_existing_report_paths(tmp_path) -> None:
    user = analyze_route.AuthUser(id="user-1", email="user@example.com")
    request = analyze_route.AnalyzeRequest(query="  build a useful app  ")
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=24)
    quota_denied = type(
        "Quota",
        (),
        {"allowed": False, "plan_limit": 5, "plan": "daily", "usage_count": 5},
    )()
    quota_warn = type(
        "Quota",
        (),
        {"allowed": True, "plan_limit": 5, "plan": "daily", "usage_count": 4},
    )()
    quota_low = type(
        "Quota",
        (),
        {"allowed": True, "plan_limit": 5, "plan": "daily", "usage_count": 1},
    )()

    with (
        patch(
            "ideago.api.routes.analyze.reserve_processing_report",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "ideago.api.routes.analyze.release_processing_report",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "ideago.api.routes.analyze.check_quota_available",
            new=AsyncMock(return_value=quota_denied),
        ),
        patch(
            "ideago.api.routes.analyze.check_and_increment_quota",
            new=AsyncMock(return_value=quota_denied),
        ),
        pytest.raises(AppError) as quota_exc,
    ):
        await analyze_route.start_analysis(request, user)
    assert quota_exc.value.status_code == 429
    assert "5 analyses per day" in quota_exc.value.detail["message"]

    with (
        patch(
            "ideago.api.routes.analyze.check_quota_available",
            new=AsyncMock(return_value=quota_low),
        ),
        patch(
            "ideago.api.routes.analyze.check_and_increment_quota",
            new=AsyncMock(return_value=quota_low),
        ),
        patch(
            "ideago.api.routes.analyze.reserve_processing_report",
            new=AsyncMock(return_value="existing-report"),
        ),
        patch(
            "ideago.api.routes.analyze._confirm_existing_report_is_active",
            new=AsyncMock(return_value=True),
        ),
    ):
        existing = await analyze_route.start_analysis(request, user)
    assert existing.report_id == "existing-report"

    fake_task = object()

    def fake_create_task(coro):
        coro.close()
        return fake_task

    with (
        patch(
            "ideago.api.routes.analyze.check_quota_available",
            new=AsyncMock(return_value=quota_warn),
        ),
        patch(
            "ideago.api.routes.analyze.check_and_increment_quota",
            new=AsyncMock(return_value=quota_warn),
        ),
        patch(
            "ideago.api.routes.analyze.reserve_processing_report",
            new=AsyncMock(return_value=None),
        ),
        patch("ideago.api.routes.analyze.get_cache", return_value=cache),
        patch(
            "ideago.api.routes.analyze.get_or_create_report_run",
            return_value=deps.get_or_create_report_run("created-report"),
        ),
        patch(
            "ideago.api.routes.analyze.notify_quota_warning",
            new=AsyncMock(side_effect=RuntimeError("mail failed")),
        ) as quota_warning,
        patch(
            "ideago.api.routes.analyze.asyncio.create_task",
            side_effect=fake_create_task,
        ),
        patch(
            "ideago.api.routes.analyze.register_pipeline_task",
            new=AsyncMock(return_value=None),
        ) as register_task,
    ):
        created = await analyze_route.start_analysis(request, user)

    status = await cache.get_status(created.report_id)
    assert status is not None
    assert status["status"] == "processing"
    quota_warning.assert_awaited_once()
    register_task.assert_awaited_once_with(created.report_id, fake_task)


@pytest.mark.asyncio
async def test_start_analysis_records_metric_when_reservation_cannot_be_obtained() -> (
    None
):
    user = analyze_route.AuthUser(id="user-1", email="user@example.com")
    request = analyze_route.AnalyzeRequest(query="build a useful app")
    app_metrics.reset()

    with (
        patch(
            "ideago.api.routes.analyze.reserve_processing_report",
            new=AsyncMock(side_effect=["stale-1", "stale-2", "stale-3"]),
        ),
        patch(
            "ideago.api.routes.analyze._confirm_existing_report_is_active",
            new=AsyncMock(return_value=False),
        ),
        pytest.raises(AppError) as reserve_exc,
    ):
        await analyze_route.start_analysis(request, user)

    assert reserve_exc.value.status_code == 503
    metrics = app_metrics.snapshot()
    assert metrics["event_counts"]["analysis_start_failed"] == 1
    assert metrics["event_reasons"]["analysis_start_failed"] == {
        "reservation_failed": 1
    }


@pytest.mark.asyncio
async def test_start_analysis_fails_closed_when_dedup_store_is_unavailable() -> None:
    user = analyze_route.AuthUser(id="user-1", email="user@example.com")
    request = analyze_route.AnalyzeRequest(query="build a useful app")
    quota_check = AsyncMock()

    with (
        patch(
            "ideago.api.routes.analyze.reserve_processing_report",
            new=AsyncMock(
                side_effect=deps.DedupReservationUnavailableError("dedup unavailable")
            ),
        ),
        patch(
            "ideago.api.routes.analyze.check_and_increment_quota",
            new=quota_check,
        ),
        pytest.raises(AppError) as exc,
    ):
        await analyze_route.start_analysis(request, user)

    assert exc.value.status_code == 503
    assert "reserve analysis slot" in exc.value.detail["message"].lower()
    quota_check.assert_not_awaited()
