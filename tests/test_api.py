"""Tests for FastAPI application and routes."""

from __future__ import annotations

import asyncio
import concurrent.futures
import contextlib
import hashlib
import json
import threading
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import jwt
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from ideago.api import app as app_module
from ideago.api import dependencies as deps
from ideago.api.app import create_app
from ideago.api.routes import analyze as analyze_route
from ideago.auth import dependencies as auth_deps
from ideago.auth import supabase_admin
from ideago.cache.base import ReportIndex
from ideago.cache.file_cache import FileCache
from ideago.models.research import (
    Competitor,
    Intent,
    Platform,
    ResearchReport,
    SearchQuery,
)
from ideago.pipeline.events import EventType, PipelineEvent


@pytest.fixture(autouse=True)
def reset_runtime_state() -> None:
    app_module._rate_limit_store.clear()
    asyncio.run(deps.shutdown_runtime_state())
    yield
    app_module._rate_limit_store.clear()
    asyncio.run(deps.shutdown_runtime_state())


@pytest.fixture
def client():
    auth_secret = "test-session-secret-0123456789abcdef"
    token = jwt.encode(
        {
            "sub": "test-user-id",
            "email": "test@example.com",
            "aud": "ideago-auth",
        },
        auth_secret,
        algorithm="HS256",
    )
    fake_settings = type(
        "Settings",
        (),
        {
            "auth_session_secret": auth_secret,
            "supabase_jwt_secret": "",
            "supabase_url": "",
            "supabase_anon_key": "",
        },
    )()
    app = create_app()
    with (
        patch("ideago.auth.dependencies.get_settings", return_value=fake_settings),
        TestClient(
            app,
            headers={
                "X-Requested-With": "IdeaGo",
                "Authorization": f"Bearer {token}",
            },
        ) as test_client,
    ):
        yield test_client


@pytest.mark.asyncio
async def test_shutdown_runtime_state_cancels_tasks_and_clears_maps() -> None:
    async def never_finishes() -> None:
        await asyncio.sleep(10)

    task = asyncio.create_task(never_finishes())
    deps.set_pipeline_task("shutdown-report", task)
    deps._processing_reports["shutdown-query"] = "shutdown-report"
    deps.get_or_create_report_run("shutdown-report")

    await deps.shutdown_runtime_state()

    assert "shutdown-report" not in deps._pipeline_tasks
    assert "shutdown-query" not in deps._processing_reports
    assert deps.get_report_run("shutdown-report") is None
    assert task.cancelled() or task.done()


def test_shutdown_runtime_state_handles_tasks_from_different_event_loop() -> None:
    async def never_finishes() -> None:
        await asyncio.sleep(10)

    foreign_loop = asyncio.new_event_loop()
    task = foreign_loop.create_task(never_finishes())
    foreign_loop.run_until_complete(asyncio.sleep(0))
    deps.set_pipeline_task("foreign-loop-report", task)

    try:
        asyncio.run(deps.shutdown_runtime_state())
    finally:
        deps._pipeline_tasks.clear()
        deps._processing_reports.clear()
        deps._report_runs.clear()
        if not task.done():
            task.cancel()
            foreign_loop.run_until_complete(
                asyncio.gather(task, return_exceptions=True)
            )
        foreign_loop.close()

    assert "foreign-loop-report" not in deps._pipeline_tasks


def test_health_endpoint(client) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "sources" not in data
    assert "dependencies" not in data


def test_analyze_endpoint_returns_report_id(client) -> None:
    response = client.post(
        "/api/v1/analyze",
        json={"query": "I want to build a markdown notes extension"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "report_id" in data
    assert len(data["report_id"]) > 0


def test_analyze_endpoint_validates_short_query(client) -> None:
    response = client.post("/api/v1/analyze", json={"query": "hi"})
    assert response.status_code == 422


def test_analyze_endpoint_rejects_garbage_query(client) -> None:
    response = client.post("/api/v1/analyze", json={"query": "12345 67890 !!!"})
    assert response.status_code == 422


def test_analyze_endpoint_normalizes_whitespace(client) -> None:
    response = client.post(
        "/api/v1/analyze",
        json={"query": "I  want   to  build   a   markdown   notes   tool"},
    )
    assert response.status_code == 200


def test_analyze_endpoint_accepts_non_latin_query(client) -> None:
    response = client.post(
        "/api/v1/analyze",
        json={"query": "一个可以自动整理会议纪要的AI工具"},
    )
    assert response.status_code == 200


def test_analyze_endpoint_deduplicates_concurrent_same_query(client) -> None:
    query = "I want to build a markdown notes extension for teams"
    start_barrier = threading.Barrier(parties=8)

    async def fake_run_pipeline(
        _query: str, _report_id: str, _user_id: str = "", **_kwargs: object
    ) -> None:
        await asyncio.sleep(1)

    with patch("ideago.api.routes.analyze._run_pipeline", new=fake_run_pipeline):

        def send_request() -> str:
            with contextlib.suppress(threading.BrokenBarrierError):
                start_barrier.wait(timeout=0.5)
            response = client.post("/api/v1/analyze", json={"query": query})
            assert response.status_code == 200
            return response.json()["report_id"]

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            report_ids = list(pool.map(lambda _i: send_request(), range(8)))

    assert len(set(report_ids)) == 1


def test_cancel_analysis_not_found(client) -> None:
    response = client.delete("/api/v1/reports/nonexistent-id/cancel")
    assert response.status_code == 404


def _make_test_report() -> ResearchReport:
    intent = Intent(
        keywords_en=["test"],
        app_type="web",
        target_scenario="test",
        search_queries=[SearchQuery(platform=Platform.GITHUB, queries=["test"])],
        cache_key="test_cache_key",
    )
    return ResearchReport(
        query="test idea",
        intent=intent,
        competitors=[
            Competitor(
                name="TestProduct",
                links=["https://test.com"],
                one_liner="A test product",
                source_platforms=[Platform.GITHUB],
                source_urls=["https://github.com/test/test"],
                relevance_score=0.8,
            )
        ],
        market_summary="Test market summary.",
        go_no_go="Go",
    )


def test_get_report_found(client, tmp_path) -> None:
    report = _make_test_report()
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=24)

    import asyncio

    asyncio.run(cache.put(report, user_id="test-user-id"))

    with (
        patch("ideago.api.dependencies._cache", cache),
        patch("ideago.api.dependencies.get_cache", return_value=cache),
    ):
        response = client.get(f"/api/v1/reports/{report.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "test idea"
    assert len(data["competitors"]) == 1


def test_get_report_not_found(client) -> None:
    mock_cache = AsyncMock(spec=FileCache)
    mock_cache.get_report_user_id = AsyncMock(return_value="test-user-id")
    mock_cache.get_by_id = AsyncMock(return_value=None)
    mock_cache.get_status = AsyncMock(return_value=None)

    with patch("ideago.api.routes.reports.get_cache", return_value=mock_cache):
        response = client.get("/api/v1/reports/nonexistent-id")
    assert response.status_code == 404


def test_get_report_status_complete(client, tmp_path) -> None:
    report = _make_test_report()
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=24)
    asyncio.run(cache.put(report, user_id="test-user-id"))

    with (
        patch("ideago.api.dependencies._cache", cache),
        patch("ideago.api.dependencies.get_cache", return_value=cache),
    ):
        response = client.get(f"/api/v1/reports/{report.id}/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "complete"
    assert payload["report_id"] == report.id
    assert payload["query"] == report.query


def test_get_report_status_reads_runtime_status_payload(client, tmp_path) -> None:
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=24)
    report_id = "report-failed-status"
    asyncio.run(
        cache.put_status(
            report_id,
            "failed",
            "query text",
            error_code="PIPELINE_FAILURE",
            message="Pipeline failed. Please retry.",
            user_id="test-user-id",
        )
    )

    with patch("ideago.api.routes.reports.get_cache", return_value=cache):
        response = client.get(f"/api/v1/reports/{report_id}/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["report_id"] == report_id
    assert payload["error_code"] == "PIPELINE_FAILURE"
    assert payload["message"] == "Pipeline failed. Please retry."
    assert payload["query"] == "query text"


def test_get_report_status_not_found(client, tmp_path) -> None:
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=24)

    with patch("ideago.api.routes.reports.get_cache", return_value=cache):
        response = client.get("/api/v1/reports/nonexistent-id/status")

    assert response.status_code == 404


def test_get_report_status_processing_from_runtime_map(client, tmp_path) -> None:
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=24)
    report_id = "processing-report"
    deps._processing_reports["query-hash"] = report_id
    asyncio.run(
        cache.put_status(report_id, "processing", "query text", user_id="test-user-id")
    )

    with patch("ideago.api.routes.reports.get_cache", return_value=cache):
        response = client.get(f"/api/v1/reports/{report_id}/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "processing"
    assert payload["report_id"] == report_id


def test_get_report_status_cancelled_from_status_file(client, tmp_path) -> None:
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=24)
    report_id = "cancelled-report"
    asyncio.run(
        cache.put_status(
            report_id,
            "cancelled",
            "query text",
            error_code="PIPELINE_CANCELLED",
            message="Analysis cancelled by user",
            user_id="test-user-id",
        )
    )

    with patch("ideago.api.routes.reports.get_cache", return_value=cache):
        response = client.get(f"/api/v1/reports/{report_id}/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "cancelled"
    assert payload["report_id"] == report_id
    assert payload["error_code"] == "PIPELINE_CANCELLED"


def test_list_reports(client) -> None:
    mock_cache = AsyncMock(spec=FileCache)
    mock_cache.get_report_user_id = AsyncMock(return_value="test-user-id")
    mock_cache.get_status = AsyncMock(return_value=None)
    mock_cache.list_reports = AsyncMock(
        return_value=(
            [
                ReportIndex(
                    report_id="abc",
                    query="test idea",
                    cache_key="k",
                    created_at=datetime.now(timezone.utc),
                    competitor_count=3,
                )
            ],
            1,
        )
    )

    with patch("ideago.api.routes.reports.get_cache", return_value=mock_cache):
        response = client.get("/api/v1/reports")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["query"] == "test idea"
    mock_cache.list_reports.assert_awaited_once_with(
        limit=20,
        offset=0,
        user_id="test-user-id",
    )


def test_list_reports_with_pagination_query_params(client) -> None:
    mock_cache = AsyncMock(spec=FileCache)
    mock_cache.get_report_user_id = AsyncMock(return_value="test-user-id")
    mock_cache.get_status = AsyncMock(return_value=None)
    mock_cache.list_reports = AsyncMock(
        return_value=(
            [
                ReportIndex(
                    report_id="paginated-id",
                    query="paged idea",
                    cache_key="k",
                    created_at=datetime.now(timezone.utc),
                    competitor_count=1,
                )
            ],
            50,
        )
    )

    with patch("ideago.api.routes.reports.get_cache", return_value=mock_cache):
        response = client.get("/api/v1/reports?limit=1&offset=20")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 50
    assert len(payload["items"]) == 1
    assert payload["items"][0]["id"] == "paginated-id"
    mock_cache.list_reports.assert_awaited_once_with(
        limit=1,
        offset=20,
        user_id="test-user-id",
    )


def test_delete_report(client) -> None:
    mock_cache = AsyncMock(spec=FileCache)
    mock_cache.get_report_user_id = AsyncMock(return_value="test-user-id")
    mock_cache.get_status = AsyncMock(return_value=None)
    mock_cache.delete = AsyncMock(return_value=True)

    with patch("ideago.api.routes.reports.get_cache", return_value=mock_cache):
        response = client.delete("/api/v1/reports/some-id")
    assert response.status_code == 200


def test_delete_report_not_found(client) -> None:
    mock_cache = AsyncMock(spec=FileCache)
    mock_cache.get_report_user_id = AsyncMock(return_value="test-user-id")
    mock_cache.get_status = AsyncMock(return_value=None)
    mock_cache.delete = AsyncMock(return_value=False)

    with patch("ideago.api.routes.reports.get_cache", return_value=mock_cache):
        response = client.delete("/api/v1/reports/nonexistent")
    assert response.status_code == 404


def test_export_report(client, tmp_path) -> None:
    report = _make_test_report()
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=24)

    import asyncio

    asyncio.run(cache.put(report, user_id="test-user-id"))

    with patch("ideago.api.routes.reports.get_cache", return_value=cache):
        response = client.get(f"/api/v1/reports/{report.id}/export")
    assert response.status_code == 200
    assert "text/markdown" in response.headers["content-type"]
    assert "Competitor Research Report" in response.text
    assert "TestProduct" in response.text


def test_linuxdo_start_redirects_to_authorize_url(client) -> None:
    fake_settings = type(
        "Settings",
        (),
        {
            "linuxdo_client_id": "ld-client",
            "linuxdo_authorize_url": "https://connect.linux.do/oauth2/authorize",
            "linuxdo_scope": "openid profile email",
            "auth_session_secret": "state-secret",
            "frontend_app_url": "https://ideago.simonsun.cc",
        },
    )()
    with patch("ideago.api.routes.auth.get_settings", return_value=fake_settings):
        response = client.get(
            "/api/v1/auth/linuxdo/start?redirect_to=https://ideago.simonsun.cc/auth/callback",
            follow_redirects=False,
        )

    assert response.status_code == 302
    location = response.headers["location"]
    assert location.startswith("https://connect.linux.do/oauth2/authorize?")
    assert "client_id=ld-client" in location
    assert "redirect_uri=" in location
    assert "state=" in location


def test_linuxdo_callback_redirects_with_internal_token_fragment(client) -> None:
    fake_settings = type(
        "Settings",
        (),
        {
            "frontend_app_url": "https://ideago.simonsun.cc",
            "auth_session_secret": "state-secret",
        },
    )()
    with (
        patch("ideago.api.routes.auth.get_settings", return_value=fake_settings),
        patch(
            "ideago.api.routes.auth._parse_state_token",
            return_value={"redirect_to": "https://ideago.simonsun.cc/auth/callback"},
        ),
        patch(
            "ideago.api.routes.auth._exchange_linuxdo_code",
            new=AsyncMock(return_value="linuxdo-token"),
        ),
        patch(
            "ideago.api.routes.auth._fetch_linuxdo_userinfo",
            new=AsyncMock(
                return_value={
                    "id": 123,
                    "email": "user@example.com",
                    "username": "user",
                }
            ),
        ),
        patch(
            "ideago.api.routes.auth.ensure_profile_exists",
            new=AsyncMock(return_value=True),
        ),
        patch("ideago.api.routes.auth._issue_auth_token", return_value="ideago-token"),
    ):
        response = client.get(
            "/api/v1/auth/linuxdo/callback?code=ok&state=good",
            follow_redirects=False,
        )

    assert response.status_code == 302
    location = response.headers["location"]
    assert location.startswith("https://ideago.simonsun.cc/auth/callback#")
    assert "access_token=ideago-token" in location
    assert "provider=linuxdo" in location


def test_auth_me_accepts_backend_session_jwt() -> None:
    token = jwt.encode(
        {
            "sub": "f0f581f8-f6e4-47a9-9162-d53eabc8dd9a",
            "email": "linuxdo@example.com",
            "aud": "ideago-auth",
        },
        "session-secret",
        algorithm="HS256",
    )
    fake_settings = type(
        "Settings",
        (),
        {
            "auth_session_secret": "session-secret",
            "supabase_jwt_secret": "",
            "supabase_url": "",
            "supabase_anon_key": "",
        },
    )()
    with patch("ideago.auth.dependencies.get_settings", return_value=fake_settings):
        app = create_app()
        with TestClient(app, headers={"X-Requested-With": "IdeaGo"}) as test_client:
            response = test_client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == "f0f581f8-f6e4-47a9-9162-d53eabc8dd9a"
    assert payload["email"] == "linuxdo@example.com"


@pytest.mark.asyncio
async def test_stream_reconnect_replays_history_and_terminal_event() -> None:
    report_id = "report-reconnect"
    run_state = deps.get_or_create_report_run(report_id)
    await run_state.publish(
        PipelineEvent(
            type=EventType.INTENT_PARSED,
            stage="intent_parsing",
            message="Analyzing idea",
        )
    )

    first_stream = analyze_route._stream_events(report_id)
    first_event = await anext(first_stream)
    assert first_event["event"] == EventType.INTENT_PARSED.value
    await first_stream.aclose()

    await run_state.publish(
        PipelineEvent(
            type=EventType.SOURCE_COMPLETED,
            stage="github_search",
            message="Found 2 results from github",
            data={"platform": "github", "count": 2},
        )
    )
    await run_state.publish(
        PipelineEvent(
            type=EventType.REPORT_READY,
            stage="complete",
            message="Report ready",
        )
    )

    reconnect_stream = analyze_route._stream_events(report_id)
    replayed_events = [
        (await anext(reconnect_stream))["event"],
        (await anext(reconnect_stream))["event"],
        (await anext(reconnect_stream))["event"],
    ]
    assert replayed_events[-1] == EventType.REPORT_READY.value
    assert EventType.SOURCE_COMPLETED.value in replayed_events
    await reconnect_stream.aclose()


@pytest.mark.asyncio
async def test_stream_status_only_processing_keeps_ping_until_complete() -> None:
    report_id = "report-status-only-processing"
    mock_cache = AsyncMock(spec=FileCache)
    mock_cache.get_status = AsyncMock(
        side_effect=[
            {"status": "processing"},
            {"status": "processing"},
            {"status": "complete"},
            {"status": "complete"},
        ]
    )
    sleep_mock = AsyncMock(return_value=None)

    with (
        patch("ideago.api.routes.analyze.get_cache", return_value=mock_cache),
        patch("ideago.api.routes.analyze.asyncio.sleep", new=sleep_mock),
    ):
        stream = analyze_route._stream_events(report_id)
        first = await anext(stream)
        second = await anext(stream)
        terminal = await anext(stream)
        await stream.aclose()

    assert first["event"] == "ping"
    assert second["event"] == "ping"
    assert terminal["event"] == EventType.REPORT_READY.value
    assert sleep_mock.await_count == 2


@pytest.mark.asyncio
async def test_stream_status_only_processing_emits_failed_terminal_event() -> None:
    report_id = "report-status-only-failed"
    mock_cache = AsyncMock(spec=FileCache)
    mock_cache.get_status = AsyncMock(
        side_effect=[
            {"status": "processing"},
            {
                "status": "failed",
                "error_code": "PIPELINE_FAILURE",
                "message": "Pipeline failed. Please retry.",
            },
            {
                "status": "failed",
                "error_code": "PIPELINE_FAILURE",
                "message": "Pipeline failed. Please retry.",
            },
        ]
    )
    sleep_mock = AsyncMock(return_value=None)

    with (
        patch("ideago.api.routes.analyze.get_cache", return_value=mock_cache),
        patch("ideago.api.routes.analyze.asyncio.sleep", new=sleep_mock),
    ):
        stream = analyze_route._stream_events(report_id)
        first = await anext(stream)
        terminal = await anext(stream)
        await stream.aclose()

    assert first["event"] == "ping"
    assert terminal["event"] == EventType.ERROR.value
    assert sleep_mock.await_count == 1


@pytest.mark.asyncio
async def test_stream_status_only_processing_times_out_with_terminal_error() -> None:
    report_id = "report-status-only-stale-processing"
    ping_iterations = 90
    mock_cache = AsyncMock(spec=FileCache)
    mock_cache.get_status = AsyncMock(
        side_effect=[{"status": "processing"}] * (ping_iterations + 5)
    )
    sleep_mock = AsyncMock(return_value=None)

    with (
        patch("ideago.api.routes.analyze.get_cache", return_value=mock_cache),
        patch("ideago.api.routes.analyze.asyncio.sleep", new=sleep_mock),
    ):
        stream = analyze_route._stream_events(report_id)
        pings = [await anext(stream) for _ in range(ping_iterations)]
        terminal = await anext(stream)
        await stream.aclose()

    assert all(item["event"] == "ping" for item in pings)
    assert terminal["event"] == EventType.ERROR.value
    payload = json.loads(terminal["data"])
    assert payload["data"]["error_code"] == "PIPELINE_PROCESSING_STALE"
    assert sleep_mock.await_count == ping_iterations


@pytest.mark.asyncio
async def test_status_terminal_event_for_failed_status_includes_error_code(
    tmp_path,
) -> None:
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=24)
    report_id = "report-failed-status"
    await cache.put_status(report_id, "failed", "bad query")

    with patch("ideago.api.routes.analyze.get_cache", return_value=cache):
        event = await analyze_route._status_terminal_event(report_id)

    assert event is not None
    assert event.type == EventType.ERROR
    assert event.data.get("error_code") == "PIPELINE_FAILURE"


@pytest.mark.asyncio
async def test_cancel_analysis_cancels_task_and_marks_status(tmp_path) -> None:
    from ideago.auth.models import AuthUser

    query = "A cancellable startup research query"
    report_id = "report-cancel"
    user_id = "test-cancel-user"
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=24)
    query_hash = hashlib.sha256(query.encode()).hexdigest()[:16]
    deps._processing_reports[f"{user_id}:{query_hash}"] = report_id
    await cache.put_status(report_id, "processing", query, user_id=user_id)

    class SlowOrchestrator:
        async def run(self, *_args, **_kwargs) -> None:
            await asyncio.sleep(10)

    mock_user = AuthUser(id=user_id, email="cancel@test.com")

    with (
        patch("ideago.api.routes.analyze.get_cache", return_value=cache),
        patch(
            "ideago.api.routes.analyze.get_orchestrator",
            return_value=SlowOrchestrator(),
        ),
    ):
        task = asyncio.create_task(
            analyze_route._run_pipeline(query, report_id, user_id)
        )
        deps.set_pipeline_task(report_id, task)

        result = await analyze_route.cancel_analysis(report_id, user=mock_user)
        assert result["status"] == "cancelled"

        with contextlib.suppress(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=2)
        assert task.cancelled() or task.done()
        status = await cache.get_status(report_id)
        assert status is not None
        assert status["status"] == "cancelled"
        assert status["error_code"] == "PIPELINE_CANCELLED"
        assert status["message"] == "Analysis cancelled by user"

        run_state = deps.get_report_run(report_id)
        assert run_state is not None
        assert any(e.type == EventType.CANCELLED for e in run_state.history)


@pytest.mark.asyncio
async def test_run_pipeline_redacts_internal_error_details(tmp_path) -> None:
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=24)
    report_id = "report-internal-error"

    class FailingOrchestrator:
        async def run(self, *_args, **_kwargs):
            raise RuntimeError("internal failure: token=abc123")

    with (
        patch("ideago.api.routes.analyze.get_cache", return_value=cache),
        patch(
            "ideago.api.routes.analyze.get_orchestrator",
            return_value=FailingOrchestrator(),
        ),
    ):
        await analyze_route._run_pipeline("A failing startup query", report_id)

    status = await cache.get_status(report_id)
    assert status is not None
    assert status["status"] == "failed"
    assert status["error_code"] == "PIPELINE_FAILURE"
    assert status["message"] == "Pipeline failed. Please retry."

    run_state = deps.get_report_run(report_id)
    assert run_state is not None
    error_events = [e for e in run_state.history if e.type == EventType.ERROR]
    assert error_events
    assert "token=abc123" not in error_events[-1].message
    assert error_events[-1].data["error_code"] == "PIPELINE_FAILURE"


def test_spa_fallback_serves_index_for_frontend_routes(tmp_path) -> None:
    """Direct deep links like /reports/:id should return index.html."""
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    index_path = dist_dir / "index.html"
    index_path.write_text("<html><body>SPA</body></html>", encoding="utf-8")

    with (
        patch.object(app_module, "_FRONTEND_DIST", dist_dir),
        patch.object(app_module, "_FRONTEND_INDEX", index_path),
    ):
        app = create_app()
        with TestClient(app) as local_client:
            response = local_client.get("/reports/136574fd-94c2-47f3-9b70-765b16104709")
            assert response.status_code == 200
            assert "SPA" in response.text


def test_spa_fallback_serves_existing_static_file(tmp_path) -> None:
    """Files that exist in dist should be served directly."""
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    index_path = dist_dir / "index.html"
    index_path.write_text("<html><body>SPA</body></html>", encoding="utf-8")
    robots_path = dist_dir / "robots.txt"
    robots_path.write_text("User-agent: *\nDisallow:", encoding="utf-8")

    with (
        patch.object(app_module, "_FRONTEND_DIST", dist_dir),
        patch.object(app_module, "_FRONTEND_INDEX", index_path),
    ):
        app = create_app()
        with TestClient(app) as local_client:
            response = local_client.get("/robots.txt")
            assert response.status_code == 200
            assert "User-agent: *" in response.text


class _AdminFakeResponse:
    def __init__(self, status_code: int, *, payload=None, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        return self._payload


def test_extract_token_subject_with_ideago_jwt() -> None:
    token = jwt.encode(
        {"sub": "user-123", "aud": "ideago-auth"},
        "test-secret",
        algorithm="HS256",
    )
    fake_settings = type(
        "Settings",
        (),
        {"auth_session_secret": "test-secret", "supabase_jwt_secret": ""},
    )()

    with patch("ideago.auth.dependencies.get_settings", return_value=fake_settings):
        assert auth_deps.extract_token_subject(token) == "user-123"


def test_extract_token_subject_with_supabase_jwt() -> None:
    token = jwt.encode(
        {"sub": "supa-user", "aud": "authenticated"},
        "supa-secret",
        algorithm="HS256",
    )
    fake_settings = type(
        "Settings",
        (),
        {"auth_session_secret": "", "supabase_jwt_secret": "supa-secret"},
    )()

    with patch("ideago.auth.dependencies.get_settings", return_value=fake_settings):
        assert auth_deps.extract_token_subject(token) == "supa-user"


@pytest.mark.asyncio
async def test_get_optional_user_via_remote_verification() -> None:
    request = type(
        "Req",
        (),
        {"headers": {"Authorization": "Bearer remote-token"}},
    )()
    fake_settings = type(
        "Settings",
        (),
        {
            "auth_session_secret": "",
            "supabase_jwt_secret": "",
            "supabase_url": "https://example.supabase.co",
            "supabase_anon_key": "anon",
        },
    )()
    with (
        patch("ideago.auth.dependencies.get_settings", return_value=fake_settings),
        patch(
            "ideago.auth.dependencies._verify_supabase_token_remote",
            new=AsyncMock(return_value={"id": "uid-1", "email": "u@example.com"}),
        ),
    ):
        user = await auth_deps.get_optional_user(request)
    assert user is not None
    assert user.id == "uid-1"


@pytest.mark.asyncio
async def test_get_optional_user_missing_or_empty_token_returns_none() -> None:
    fake_settings = type(
        "Settings",
        (),
        {
            "auth_session_secret": "",
            "supabase_jwt_secret": "",
            "supabase_url": "",
            "supabase_anon_key": "",
        },
    )()
    request_no_header = type("Req", (), {"headers": {}})()
    request_empty_token = type("Req", (), {"headers": {"Authorization": "Bearer "}})()

    with patch("ideago.auth.dependencies.get_settings", return_value=fake_settings):
        assert await auth_deps.get_optional_user(request_no_header) is None
        assert await auth_deps.get_optional_user(request_empty_token) is None


@pytest.mark.asyncio
async def test_get_optional_user_supabase_jwt_invalid_returns_none() -> None:
    fake_settings = type(
        "Settings",
        (),
        {
            "auth_session_secret": "",
            "supabase_jwt_secret": "supa-secret",
            "supabase_url": "",
            "supabase_anon_key": "",
        },
    )()
    request = type(
        "Req",
        (),
        {"headers": {"Authorization": "Bearer invalid"}},
    )()

    with patch("ideago.auth.dependencies.get_settings", return_value=fake_settings):
        assert await auth_deps.get_optional_user(request) is None


@pytest.mark.asyncio
async def test_get_current_user_raises_when_missing() -> None:
    with pytest.raises(HTTPException) as exc:
        await auth_deps.get_current_user(None)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_supabase_admin_quota_and_profile_fallback_paths() -> None:
    with patch("ideago.auth.supabase_admin._is_configured", return_value=False):
        quota = await supabase_admin.check_and_increment_quota("uid")
        info = await supabase_admin.get_quota_info("uid")
        profile = await supabase_admin.get_profile("uid")
        updated = await supabase_admin.update_profile("uid", display_name="n", bio="b")

    assert quota.allowed is True
    assert info["plan"] == "dev"
    assert profile["display_name"] == ""
    assert updated["display_name"] == "n"


@pytest.mark.asyncio
async def test_supabase_admin_quota_success_and_errors() -> None:
    fake_settings = type(
        "Settings",
        (),
        {
            "supabase_url": "https://example.supabase.co",
            "supabase_service_role_key": "srk",
        },
    )()
    fake_client = AsyncMock()
    fake_client.post = AsyncMock(
        side_effect=[
            _AdminFakeResponse(
                200,
                payload={
                    "allowed": True,
                    "usage_count": 1,
                    "plan_limit": 10,
                    "plan": "free",
                },
            ),
            _AdminFakeResponse(500, text="boom"),
            RuntimeError("network"),
        ]
    )

    with (
        patch("ideago.auth.supabase_admin._is_configured", return_value=True),
        patch("ideago.auth.supabase_admin.get_settings", return_value=fake_settings),
        patch("ideago.auth.supabase_admin._get_client", return_value=fake_client),
    ):
        ok = await supabase_admin.check_and_increment_quota("uid")
        rpc_fail = await supabase_admin.check_and_increment_quota("uid")
        network_fail = await supabase_admin.check_and_increment_quota("uid")

    assert ok.allowed is True and ok.plan_limit == 10
    assert rpc_fail.error == "quota_check_failed"
    assert network_fail.error == "quota_check_error"


@pytest.mark.asyncio
async def test_supabase_admin_profile_and_quota_info_paths() -> None:
    fake_settings = type(
        "Settings",
        (),
        {
            "supabase_url": "https://example.supabase.co",
            "supabase_service_role_key": "srk",
        },
    )()
    fake_client = AsyncMock()
    fake_client.post = AsyncMock(
        side_effect=[
            _AdminFakeResponse(
                200, payload={"usage_count": 3, "plan_limit": 10, "plan": "free"}
            ),
            _AdminFakeResponse(204),
            _AdminFakeResponse(500, text="fail"),
        ]
    )
    fake_client.get = AsyncMock(
        side_effect=[
            _AdminFakeResponse(
                200,
                payload=[
                    {
                        "display_name": "Alice",
                        "avatar_url": "",
                        "bio": "",
                        "created_at": "2026-01-01",
                    }
                ],
            ),
            _AdminFakeResponse(500, text="fail"),
        ]
    )
    fake_client.patch = AsyncMock(
        side_effect=[
            _AdminFakeResponse(
                200,
                payload=[
                    {
                        "display_name": "Bob",
                        "avatar_url": "",
                        "bio": "Hi",
                        "created_at": "2026-01-01",
                    }
                ],
            ),
            _AdminFakeResponse(500, text="fail"),
        ]
    )

    with (
        patch("ideago.auth.supabase_admin._is_configured", return_value=True),
        patch("ideago.auth.supabase_admin.get_settings", return_value=fake_settings),
        patch("ideago.auth.supabase_admin._get_client", return_value=fake_client),
    ):
        quota = await supabase_admin.get_quota_info("uid")
        upsert_ok = await supabase_admin.ensure_profile_exists(
            "uid", display_name="Alice"
        )
        upsert_fail = await supabase_admin.ensure_profile_exists(
            "uid", display_name="Alice"
        )
        profile_ok = await supabase_admin.get_profile("uid")
        profile_fail = await supabase_admin.get_profile("uid")
        updated_ok = await supabase_admin.update_profile(
            "uid", display_name="Bob", bio="Hi"
        )
        updated_fail = await supabase_admin.update_profile(
            "uid", display_name="Bob", bio="Hi"
        )

    assert quota["usage_count"] == 3
    assert upsert_ok is True and upsert_fail is False
    assert profile_ok["display_name"] == "Alice"
    assert profile_fail["error"] == "profile_fetch_failed"
    assert updated_ok["display_name"] == "Bob"
    assert updated_fail["error"] == "profile_update_failed"


# ── Multi-user isolation tests ────────────────────────────────────────


def test_user_b_cannot_view_user_a_report(tmp_path) -> None:
    """User B gets 403 when accessing user A's report."""
    report = _make_test_report()
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=24)
    asyncio.run(cache.put(report, user_id="user-a-id"))

    auth_secret = "test-session-secret-0123456789abcdef"
    fake_auth = type(
        "Settings",
        (),
        {
            "auth_session_secret": auth_secret,
            "supabase_jwt_secret": "",
            "supabase_url": "",
            "supabase_anon_key": "",
        },
    )()
    token_b = jwt.encode(
        {"sub": "user-b-id", "email": "b@test.com", "aud": "ideago-auth"},
        auth_secret,
        algorithm="HS256",
    )
    app = create_app()

    with (
        patch("ideago.auth.dependencies.get_settings", return_value=fake_auth),
        patch("ideago.api.dependencies._cache", cache),
        patch("ideago.api.dependencies.get_cache", return_value=cache),
        TestClient(
            app,
            headers={
                "X-Requested-With": "IdeaGo",
                "Authorization": f"Bearer {token_b}",
            },
        ) as client_b,
    ):
        response = client_b.get(f"/api/v1/reports/{report.id}")
    assert response.status_code == 403


def test_user_b_cannot_delete_user_a_report(tmp_path) -> None:
    """User B gets 403 when deleting user A's report."""
    report = _make_test_report()
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=24)
    asyncio.run(cache.put(report, user_id="user-a-id"))

    auth_secret = "test-session-secret-0123456789abcdef"
    fake_auth = type(
        "Settings",
        (),
        {
            "auth_session_secret": auth_secret,
            "supabase_jwt_secret": "",
            "supabase_url": "",
            "supabase_anon_key": "",
        },
    )()
    token_b = jwt.encode(
        {"sub": "user-b-id", "email": "b@test.com", "aud": "ideago-auth"},
        auth_secret,
        algorithm="HS256",
    )
    app = create_app()

    with (
        patch("ideago.auth.dependencies.get_settings", return_value=fake_auth),
        patch("ideago.api.dependencies._cache", cache),
        patch("ideago.api.dependencies.get_cache", return_value=cache),
        TestClient(
            app,
            headers={
                "X-Requested-With": "IdeaGo",
                "Authorization": f"Bearer {token_b}",
            },
        ) as client_b,
    ):
        response = client_b.delete(f"/api/v1/reports/{report.id}")
    assert response.status_code == 403


def test_user_b_cannot_export_user_a_report(tmp_path) -> None:
    """User B gets 403 when exporting user A's report."""
    report = _make_test_report()
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=24)
    asyncio.run(cache.put(report, user_id="user-a-id"))

    auth_secret = "test-session-secret-0123456789abcdef"
    fake_auth = type(
        "Settings",
        (),
        {
            "auth_session_secret": auth_secret,
            "supabase_jwt_secret": "",
            "supabase_url": "",
            "supabase_anon_key": "",
        },
    )()
    token_b = jwt.encode(
        {"sub": "user-b-id", "email": "b@test.com", "aud": "ideago-auth"},
        auth_secret,
        algorithm="HS256",
    )
    app = create_app()

    with (
        patch("ideago.auth.dependencies.get_settings", return_value=fake_auth),
        patch("ideago.api.dependencies._cache", cache),
        patch("ideago.api.dependencies.get_cache", return_value=cache),
        TestClient(
            app,
            headers={
                "X-Requested-With": "IdeaGo",
                "Authorization": f"Bearer {token_b}",
            },
        ) as client_b,
    ):
        response = client_b.get(f"/api/v1/reports/{report.id}/export")
    assert response.status_code == 403


def test_owner_check_falls_back_to_status_user_id(tmp_path) -> None:
    """When report.user_id is empty, owner check uses status.user_id."""
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=24)
    report_id = "processing-report-x"
    asyncio.run(
        cache.put_status(
            report_id,
            "processing",
            "test query",
            user_id="user-a-id",
        )
    )

    auth_secret = "test-session-secret-0123456789abcdef"
    fake_auth = type(
        "Settings",
        (),
        {
            "auth_session_secret": auth_secret,
            "supabase_jwt_secret": "",
            "supabase_url": "",
            "supabase_anon_key": "",
        },
    )()
    token_b = jwt.encode(
        {"sub": "user-b-id", "email": "b@test.com", "aud": "ideago-auth"},
        auth_secret,
        algorithm="HS256",
    )
    app = create_app()

    with (
        patch("ideago.auth.dependencies.get_settings", return_value=fake_auth),
        patch("ideago.api.routes.reports.get_cache", return_value=cache),
        patch(
            "ideago.api.routes.reports.is_report_id_processing",
            return_value=False,
        ),
        TestClient(
            app,
            headers={
                "X-Requested-With": "IdeaGo",
                "Authorization": f"Bearer {token_b}",
            },
        ) as client_b,
    ):
        response = client_b.get(f"/api/v1/reports/{report_id}/status")
    assert response.status_code == 403


def test_same_query_different_users_separate_pipelines(tmp_path) -> None:
    """Two users with the same query get separate report IDs (dedup is per-user)."""
    auth_secret = "test-session-secret-0123456789abcdef"
    fake_auth = type(
        "Settings",
        (),
        {
            "auth_session_secret": auth_secret,
            "supabase_jwt_secret": "",
            "supabase_url": "",
            "supabase_anon_key": "",
        },
    )()

    async def fake_run(_q: str, _r: str, _u: str = "", **_kw: object) -> None:
        await asyncio.sleep(1)

    query = "I want to build a todo app"
    report_ids = []

    for uid, email in [("user-a", "a@test.com"), ("user-b", "b@test.com")]:
        token = jwt.encode(
            {"sub": uid, "email": email, "aud": "ideago-auth"},
            auth_secret,
            algorithm="HS256",
        )
        app = create_app()
        with (
            patch("ideago.auth.dependencies.get_settings", return_value=fake_auth),
            patch("ideago.api.routes.analyze._run_pipeline", new=fake_run),
            TestClient(
                app,
                headers={
                    "X-Requested-With": "IdeaGo",
                    "Authorization": f"Bearer {token}",
                },
            ) as c,
        ):
            resp = c.post("/api/v1/analyze", json={"query": query})
            assert resp.status_code == 200
            report_ids.append(resp.json()["report_id"])

    assert len(set(report_ids)) == 2, "Different users should get different report IDs"


def test_cache_isolation_between_users(tmp_path) -> None:
    """Cache get() with user_id only returns reports owned by that user."""
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=24)
    report_a = _make_test_report()
    asyncio.run(cache.put(report_a, user_id="user-a"))

    result_a = asyncio.run(cache.get("test_cache_key", user_id="user-a"))
    assert result_a is not None
    assert result_a.id == report_a.id

    result_b = asyncio.run(cache.get("test_cache_key", user_id="user-b"))
    assert result_b is None, "User B should not see user A's cached report"


def test_file_cache_put_status_stores_user_id(tmp_path) -> None:
    """FileCache.put_status must persist user_id in the status JSON file."""
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=24)
    asyncio.run(
        cache.put_status(
            "report-xyz",
            "processing",
            "test query",
            user_id="uid-123",
        )
    )
    status = asyncio.run(cache.get_status("report-xyz"))
    assert status is not None
    assert status["user_id"] == "uid-123"


def test_open_redirect_blocked_when_frontend_url_empty() -> None:
    """_is_safe_redirect must reject any URL when frontend_app_url is empty."""
    from ideago.api.routes.auth import _is_safe_redirect

    fake_settings = type("Settings", (), {"frontend_app_url": ""})()
    with patch("ideago.api.routes.auth.get_settings", return_value=fake_settings):
        assert not _is_safe_redirect("https://evil.com/steal")
        assert not _is_safe_redirect("https://ideago.simonsun.cc/callback")


def test_quota_fails_closed_on_rpc_error() -> None:
    """Quota check must deny when the RPC endpoint returns an error."""
    fake_settings = type(
        "Settings",
        (),
        {
            "supabase_url": "https://test.supabase.co",
            "supabase_service_role_key": "key",
        },
    )()

    class _FakeResponse:
        status_code = 500
        text = "Internal Server Error"

    class _FakeClient:
        async def post(self, *_a, **_kw):
            return _FakeResponse()

    with (
        patch("ideago.auth.supabase_admin._is_configured", return_value=True),
        patch("ideago.auth.supabase_admin.get_settings", return_value=fake_settings),
        patch("ideago.auth.supabase_admin._get_client", return_value=_FakeClient()),
    ):
        result = asyncio.run(supabase_admin.check_and_increment_quota("uid"))
    assert result.allowed is False
    assert result.error == "quota_check_failed"
