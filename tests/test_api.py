"""Tests for FastAPI application and routes."""

from __future__ import annotations

import asyncio
import concurrent.futures
import contextlib
import hashlib
import json
import runpy
import threading
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from ideago.api import app as app_module
from ideago.api import dependencies as deps
from ideago.api.app import create_app
from ideago.api.errors import AppError
from ideago.api.routes import admin as admin_route
from ideago.api.routes import analyze as analyze_route
from ideago.api.routes import auth as auth_route
from ideago.api.routes import billing as billing_route
from ideago.api.routes import health as health_route
from ideago.auth import dependencies as auth_deps
from ideago.auth import supabase_admin
from ideago.billing import stripe_service
from ideago.cache.base import ReportIndex
from ideago.cache.file_cache import FileCache
from ideago.config.settings import Settings
from ideago.models.research import (
    Competitor,
    Intent,
    Platform,
    ResearchReport,
    SearchQuery,
)
from ideago.notifications import service as notification_service
from ideago.pipeline.events import EventType, PipelineEvent


@pytest.fixture(autouse=True)
def reset_runtime_state() -> None:
    app_module._rate_limit_store.clear()
    auth_deps._clear_jwks_cache()
    with contextlib.suppress(RuntimeError):
        asyncio.run(deps.shutdown_runtime_state())
    with contextlib.suppress(RuntimeError):
        asyncio.run(supabase_admin.close_supabase_admin_client())
    deps._cache = None
    yield
    app_module._rate_limit_store.clear()
    auth_deps._clear_jwks_cache()
    with contextlib.suppress(RuntimeError):
        asyncio.run(deps.shutdown_runtime_state())
    with contextlib.suppress(RuntimeError):
        asyncio.run(supabase_admin.close_supabase_admin_client())
    deps._cache = None


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
    fake_settings = Settings(
        _env_file=None,
        environment="development",
        auth_session_secret=auth_secret,
        supabase_url="",
        supabase_anon_key="",
        supabase_service_role_key="",
    )
    with (
        patch("ideago.auth.dependencies.get_settings", return_value=fake_settings),
        patch("ideago.api.dependencies.get_settings", return_value=fake_settings),
        patch("ideago.api.app.get_settings", return_value=fake_settings),
        patch("ideago.auth.supabase_admin._is_configured", return_value=False),
    ):
        app = create_app()
        with TestClient(
            app,
            headers={
                "X-Requested-With": "IdeaGo",
                "Authorization": f"Bearer {token}",
            },
        ) as test_client:
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


def test_frontend_callback_url_prefers_configured_frontend_url() -> None:
    request = type("Req", (), {"base_url": "https://api.example.com/"})()
    fake_settings = type(
        "Settings", (), {"frontend_app_url": "https://app.example.com"}
    )()

    with patch("ideago.api.routes.auth.get_settings", return_value=fake_settings):
        assert (
            auth_route._frontend_callback_url(request)
            == "https://app.example.com/auth/callback"
        )


def test_frontend_callback_url_falls_back_to_request_base_url() -> None:
    request = type("Req", (), {"base_url": "https://api.example.com/"})()
    fake_settings = type("Settings", (), {"frontend_app_url": ""})()

    with patch("ideago.api.routes.auth.get_settings", return_value=fake_settings):
        assert (
            auth_route._frontend_callback_url(request)
            == "https://api.example.com/auth/callback"
        )


def test_is_safe_redirect_accepts_same_frontend_host() -> None:
    fake_settings = type(
        "Settings", (), {"frontend_app_url": "https://app.example.com"}
    )()

    with patch("ideago.api.routes.auth.get_settings", return_value=fake_settings):
        assert auth_route._is_safe_redirect("https://app.example.com/auth/callback")
        assert not auth_route._is_safe_redirect("javascript:alert(1)")
        assert not auth_route._is_safe_redirect("https://evil.example.com/callback")


def test_build_and_parse_state_token_round_trip() -> None:
    fake_settings = type("Settings", (), {"auth_session_secret": "x" * 32})()

    with patch("ideago.api.routes.auth.get_settings", return_value=fake_settings):
        token = auth_route._build_state_token(
            redirect_to="https://app.example.com/auth/callback"
        )
        payload = auth_route._parse_state_token(token)

    assert payload["redirect_to"] == "https://app.example.com/auth/callback"
    assert payload["aud"] == "ideago-linuxdo-state"


def test_build_state_token_requires_auth_session_secret() -> None:
    fake_settings = type("Settings", (), {"auth_session_secret": ""})()

    with (
        patch("ideago.api.routes.auth.get_settings", return_value=fake_settings),
        pytest.raises(HTTPException) as exc,
    ):
        auth_route._build_state_token(
            redirect_to="https://app.example.com/auth/callback"
        )

    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_exchange_linuxdo_code_success_failure_and_missing_token() -> None:
    fake_settings = type(
        "Settings",
        (),
        {
            "linuxdo_client_id": "client",
            "linuxdo_client_secret": "secret",
            "linuxdo_token_url": "https://connect.linux.do/token",
        },
    )()
    fake_client = AsyncMock()
    fake_client.post = AsyncMock(
        side_effect=[
            _AdminFakeResponse(200, payload={"access_token": "linuxdo-token"}),
            _AdminFakeResponse(400, payload={"error": "bad"}),
            _AdminFakeResponse(200, payload={"token_type": "bearer"}),
        ]
    )

    with (
        patch("ideago.api.routes.auth.get_settings", return_value=fake_settings),
        patch(
            "ideago.api.routes.auth.httpx.AsyncClient",
            return_value=_AsyncClientContext(fake_client),
        ),
    ):
        assert (
            await auth_route._exchange_linuxdo_code(
                code="ok",
                redirect_uri="https://api.example.com/callback",
            )
            == "linuxdo-token"
        )
        with pytest.raises(HTTPException) as bad_status:
            await auth_route._exchange_linuxdo_code(
                code="bad",
                redirect_uri="https://api.example.com/callback",
            )
        with pytest.raises(HTTPException) as missing_token:
            await auth_route._exchange_linuxdo_code(
                code="missing",
                redirect_uri="https://api.example.com/callback",
            )

    assert bad_status.value.status_code == 400
    assert missing_token.value.status_code == 400


@pytest.mark.asyncio
async def test_fetch_linuxdo_userinfo_success_and_errors() -> None:
    fake_settings = type(
        "Settings",
        (),
        {"linuxdo_userinfo_url": "https://connect.linux.do/api/user"},
    )()
    fake_client = AsyncMock()
    fake_client.get = AsyncMock(
        side_effect=[
            _AdminFakeResponse(200, payload={"id": 1, "email": "u@example.com"}),
            _AdminFakeResponse(400, payload={"error": "bad"}),
            _AdminFakeResponse(200, payload=["bad"]),
        ]
    )

    with (
        patch("ideago.api.routes.auth.get_settings", return_value=fake_settings),
        patch(
            "ideago.api.routes.auth.httpx.AsyncClient",
            return_value=_AsyncClientContext(fake_client),
        ),
    ):
        data = await auth_route._fetch_linuxdo_userinfo("ok")
        with pytest.raises(HTTPException) as bad_status:
            await auth_route._fetch_linuxdo_userinfo("bad")
        with pytest.raises(HTTPException) as bad_payload:
            await auth_route._fetch_linuxdo_userinfo("weird")

    assert data["id"] == 1
    assert bad_status.value.status_code == 400
    assert bad_payload.value.status_code == 400


def test_extract_linuxdo_identity_handles_missing_email_and_missing_id() -> None:
    linuxdo_id, email, display_name = auth_route._extract_linuxdo_identity(
        {"id": 123, "username": "alice"}
    )

    assert linuxdo_id == "123"
    assert email == "alice@linux.do"
    assert display_name == "alice"

    with pytest.raises(HTTPException) as exc:
        auth_route._extract_linuxdo_identity({"email": "x@example.com"})

    assert exc.value.status_code == 400


def test_build_internal_user_id_is_deterministic() -> None:
    assert auth_route._build_internal_user_id(
        "abc"
    ) == auth_route._build_internal_user_id("abc")


def test_issue_auth_token_success_and_missing_secret() -> None:
    good_settings = type(
        "Settings",
        (),
        {"auth_session_secret": "y" * 32, "auth_session_expire_hours": 24},
    )()
    bad_settings = type("Settings", (), {"auth_session_secret": ""})()

    with patch("ideago.api.routes.auth.get_settings", return_value=good_settings):
        token = auth_route._issue_auth_token(
            user_id="uid",
            email="u@example.com",
            provider="linuxdo",
        )
        decoded = jwt.decode(
            token,
            good_settings.auth_session_secret,
            algorithms=["HS256"],
            audience="ideago-auth",
        )

    assert decoded["sub"] == "uid"

    with (
        patch("ideago.api.routes.auth.get_settings", return_value=bad_settings),
        pytest.raises(HTTPException) as exc,
    ):
        auth_route._issue_auth_token(
            user_id="uid", email="u@example.com", provider="linuxdo"
        )

    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_refresh_token_success_and_error_paths() -> None:
    fake_settings = type(
        "Settings",
        (),
        {"auth_session_secret": "z" * 32, "auth_session_expire_hours": 24},
    )()
    valid_token = jwt.encode(
        {
            "sub": "uid",
            "email": "u@example.com",
            "provider": "linuxdo",
            "aud": "ideago-auth",
            "exp": int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp()),
        },
        fake_settings.auth_session_secret,
        algorithm="HS256",
    )
    stale_token = jwt.encode(
        {
            "sub": "uid",
            "email": "u@example.com",
            "provider": "linuxdo",
            "aud": "ideago-auth",
            "exp": int((datetime.now(timezone.utc) - timedelta(days=10)).timestamp()),
        },
        fake_settings.auth_session_secret,
        algorithm="HS256",
    )
    good_request = type(
        "Req", (), {"headers": {"Authorization": f"Bearer {valid_token}"}}
    )()
    empty_request = type("Req", (), {"headers": {}})()
    stale_request = type(
        "Req", (), {"headers": {"Authorization": f"Bearer {stale_token}"}}
    )()
    invalid_request = type(
        "Req", (), {"headers": {"Authorization": "Bearer invalid"}}
    )()

    with patch("ideago.api.routes.auth.get_settings", return_value=fake_settings):
        refreshed = await auth_route.refresh_token(good_request)
        with pytest.raises(HTTPException) as missing:
            await auth_route.refresh_token(empty_request)
        with pytest.raises(HTTPException) as invalid:
            await auth_route.refresh_token(invalid_request)
        with pytest.raises(HTTPException) as stale:
            await auth_route.refresh_token(stale_request)

    assert "access_token" in refreshed
    assert missing.value.status_code == 401
    assert invalid.value.status_code == 401
    assert stale.value.status_code == 401


@pytest.mark.asyncio
async def test_auth_profile_and_delete_account_error_paths() -> None:
    user = auth_route.AuthUser(id="uid", email="u@example.com")
    request = type("Req", (), {"client": type("Client", (), {"host": "127.0.0.1"})()})()

    with (
        patch(
            "ideago.api.routes.auth.ensure_profile_exists",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "ideago.api.routes.auth.get_profile",
            new=AsyncMock(return_value={"error": "profile_fetch_failed"}),
        ),
        pytest.raises(HTTPException) as profile_exc,
    ):
        await auth_route.get_my_profile(user)

    with (
        patch(
            "ideago.api.routes.auth.delete_user_data",
            new=AsyncMock(return_value={"error": "partial_failure"}),
        ),
        patch("ideago.api.routes.auth.log_audit_event", new=AsyncMock()),
        pytest.raises(AppError) as delete_exc,
    ):
        await auth_route.delete_account(request, user)

    assert profile_exc.value.status_code == 404
    assert delete_exc.value.status_code == 500


@pytest.mark.asyncio
async def test_auth_callback_quota_and_profile_success_paths() -> None:
    request = type(
        "Req",
        (),
        {
            "base_url": "https://api.example.com/",
            "client": type("Client", (), {"host": "127.0.0.1"})(),
            "url_for": lambda self, name: (
                "https://api.example.com/api/v1/auth/linuxdo/callback"
            ),
        },
    )()
    fake_settings = type(
        "Settings",
        (),
        {
            "frontend_app_url": "https://app.example.com",
            "auth_session_secret": "state-secret-state-secret-state-secret",
        },
    )()

    with patch("ideago.api.routes.auth.get_settings", return_value=fake_settings):
        bad_state = await auth_route.linuxdo_callback(request, code="ok", state=None)
        bad_code = await auth_route.linuxdo_callback(
            request,
            code=None,
            state=auth_route._build_state_token(
                redirect_to="https://app.example.com/auth/callback"
            ),
            error=None,
            error_description=None,
        )

    assert "Missing+OAuth+state" in bad_state.headers["location"]
    assert "Missing+authorization+code" in bad_code.headers["location"]

    user = auth_route.AuthUser(id="uid", email="u@example.com")
    with (
        patch(
            "ideago.api.routes.auth.ensure_profile_exists",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "ideago.api.routes.auth.get_quota_info",
            new=AsyncMock(return_value={"plan": "pro", "usage_count": 1}),
        ),
        patch(
            "ideago.api.routes.auth.get_profile",
            new=AsyncMock(return_value={"display_name": "Alice"}),
        ),
        patch(
            "ideago.api.routes.auth.update_profile",
            new=AsyncMock(return_value={"display_name": "Bob", "bio": "Hi"}),
        ),
        patch(
            "ideago.api.routes.auth.delete_user_data",
            new=AsyncMock(return_value={"deleted": True}),
        ),
        patch("ideago.api.routes.auth.log_audit_event", new=AsyncMock()),
    ):
        quota = await auth_route.get_user_quota(user)
        profile = await auth_route.get_my_profile(user)
        updated = await auth_route.update_my_profile(
            auth_route.ProfileUpdatePayload(display_name=" Bob ", bio=" Hi "),
            user,
        )
        deleted = await auth_route.delete_account(request, user)

    assert quota["plan"] == "pro"
    assert profile["display_name"] == "Alice"
    assert updated["display_name"] == "Bob"
    assert updated["bio"] == "Hi"
    assert deleted == {"status": "deleted"}


def test_notification_sender_singleton_default() -> None:
    notification_service._sender = None
    first = notification_service.get_notification_sender()
    second = notification_service.get_notification_sender()
    assert isinstance(first, notification_service.LogNotificationSender)
    assert first is second


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
        patch("ideago.api.dependencies._supabase_dedup_configured", return_value=False),
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


@pytest.mark.asyncio
async def test_run_pipeline_completion_cancel_skip_and_notification_failure(
    tmp_path,
) -> None:
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=24)
    report_id = "report-complete"
    report = _make_test_report()

    class SuccessfulOrchestrator:
        async def run(self, *_args, **_kwargs):
            return report

    with (
        patch("ideago.api.routes.analyze.get_cache", return_value=cache),
        patch(
            "ideago.api.routes.analyze.get_orchestrator",
            return_value=SuccessfulOrchestrator(),
        ),
        patch(
            "ideago.api.routes.analyze.notify_report_ready",
            new=AsyncMock(side_effect=RuntimeError("mail failed")),
        ) as notify_ready,
        patch(
            "ideago.api.routes.analyze.release_processing_report",
            new=AsyncMock(return_value=None),
        ) as release_processing,
        patch(
            "ideago.api.routes.analyze.remove_pipeline_task",
            new=AsyncMock(return_value=None),
        ) as remove_task,
        patch("ideago.api.routes.analyze.cleanup_report_runs"),
    ):
        await analyze_route._run_pipeline(
            "good query",
            report_id,
            "user-1",
            user_email="user@example.com",
        )

    status = await cache.get_status(report_id)
    assert status is not None
    assert status["status"] == "complete"
    notify_ready.assert_awaited_once()
    release_processing.assert_awaited_once_with(report_id)
    remove_task.assert_awaited_once_with(report_id)

    cancelled_report_id = "report-cancelled-before-complete"
    cancelled_state = deps.get_or_create_report_run(cancelled_report_id)
    await cancelled_state.publish(
        PipelineEvent(
            type=EventType.CANCELLED,
            stage="pipeline",
            message="cancelled",
            data={"report_id": cancelled_report_id},
        )
    )
    with (
        patch("ideago.api.routes.analyze.get_cache", return_value=cache),
        patch(
            "ideago.api.routes.analyze.get_orchestrator",
            return_value=SuccessfulOrchestrator(),
        ),
        patch(
            "ideago.api.routes.analyze.release_processing_report",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "ideago.api.routes.analyze.remove_pipeline_task",
            new=AsyncMock(return_value=None),
        ),
        patch("ideago.api.routes.analyze.cleanup_report_runs"),
    ):
        await analyze_route._run_pipeline(
            "good query",
            cancelled_report_id,
            "user-1",
        )

    cancelled_status = await cache.get_status(cancelled_report_id)
    assert cancelled_status is None


@pytest.mark.asyncio
async def test_mark_cancelled_status_terminal_event_and_owner_checks(tmp_path) -> None:
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=24)
    report_id = "report-owner-check"
    await cache.put_status(report_id, "processing", "query", user_id="owner-1")

    with patch("ideago.api.routes.analyze.get_cache", return_value=cache):
        await analyze_route._mark_cancelled(report_id)
        cancelled = await cache.get_status(report_id)
        assert cancelled is not None
        assert cancelled["status"] == "cancelled"
        event = await analyze_route._status_terminal_event(report_id)
        assert event is not None
        assert event.type == EventType.CANCELLED

        await cache.put_status(
            "complete-report", "complete", "query", user_id="owner-1"
        )
        complete_event = await analyze_route._status_terminal_event("complete-report")
        assert complete_event is not None
        assert complete_event.type == EventType.REPORT_READY
        assert await analyze_route._status_terminal_event("missing-report") is None

        assert await analyze_route._get_effective_owner(report_id) == "owner-1"
        await analyze_route._assert_owner_or_deny(report_id, "owner-1")

        with pytest.raises(AppError) as wrong_owner:
            await analyze_route._assert_owner_or_deny(report_id, "owner-2")
        assert wrong_owner.value.status_code == 403

        with pytest.raises(AppError) as missing_owner:
            await analyze_route._assert_owner_or_deny("missing-report", "owner-1")
        assert missing_owner.value.status_code == 404


@pytest.mark.asyncio
async def test_start_analysis_quota_and_existing_report_paths(tmp_path) -> None:
    user = analyze_route.AuthUser(id="user-1", email="user@example.com")
    request = analyze_route.AnalyzeRequest(query="  build a useful app  ")
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=24)
    quota_denied = type(
        "Quota",
        (),
        {"allowed": False, "plan_limit": 10, "plan": "free", "usage_count": 10},
    )()
    quota_warn = type(
        "Quota",
        (),
        {"allowed": True, "plan_limit": 10, "plan": "free", "usage_count": 8},
    )()
    quota_low = type(
        "Quota",
        (),
        {"allowed": True, "plan_limit": 10, "plan": "free", "usage_count": 1},
    )()

    with (
        patch(
            "ideago.api.routes.analyze.check_and_increment_quota",
            new=AsyncMock(return_value=quota_denied),
        ),
        pytest.raises(AppError) as quota_exc,
    ):
        await analyze_route.start_analysis(request, user)
    assert quota_exc.value.status_code == 429

    with (
        patch(
            "ideago.api.routes.analyze.check_and_increment_quota",
            new=AsyncMock(return_value=quota_low),
        ),
        patch(
            "ideago.api.routes.analyze.reserve_processing_report",
            new=AsyncMock(return_value="existing-report"),
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
async def test_cancel_analysis_else_branch_and_stream_progress_owner_check(
    tmp_path,
) -> None:
    user = analyze_route.AuthUser(id="owner-1", email="owner@example.com")
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=24)
    report_id = "cancel-without-task"
    await cache.put_status(report_id, "processing", "query", user_id="owner-1")

    with (
        patch("ideago.api.routes.analyze.get_cache", return_value=cache),
        patch(
            "ideago.api.routes.analyze.get_pipeline_task_for_report",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "ideago.api.routes.analyze.is_processing_report",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "ideago.api.routes.analyze.release_processing_report",
            new=AsyncMock(return_value=None),
        ) as release_processing,
    ):
        result = await analyze_route.cancel_analysis(report_id, user=user)

    assert result == {"status": "cancelled"}
    release_processing.assert_awaited_once_with(report_id)

    with patch("ideago.api.routes.analyze._assert_owner_or_deny", new=AsyncMock()):
        response = await analyze_route.stream_progress(report_id, user=user)
    assert isinstance(response, analyze_route.EventSourceResponse)


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


def test_app_middlewares_rate_limit_headers_and_spa_fallback_branches(tmp_path) -> None:
    auth_secret = "test-session-secret-0123456789abcdef"
    token = jwt.encode(
        {
            "sub": "rate-user",
            "email": "rate@example.com",
            "aud": "ideago-auth",
        },
        auth_secret,
        algorithm="HS256",
    )
    dist_dir = tmp_path / "dist"
    assets_dir = dist_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    index_path = dist_dir / "index.html"
    index_path.write_text("<html><body>SPA</body></html>", encoding="utf-8")
    asset_path = dist_dir / "logo.svg"
    asset_path.write_text("<svg></svg>", encoding="utf-8")

    prod_settings = type(
        "Settings",
        (),
        {
            "environment": "production",
            "auth_session_secret": auth_secret,
            "frontend_app_url": "https://app.example.com",
            "rate_limit_analyze_max": 1,
            "rate_limit_analyze_window_seconds": 60,
            "rate_limit_reports_max": 1,
            "rate_limit_reports_window_seconds": 60,
            "supabase_url": "",
            "supabase_anon_key": "",
            "supabase_service_role_key": "",
            "sentry_dsn": "",
            "get_cors_allow_origins": lambda self: ["https://app.example.com"],
        },
    )()
    local_cache = FileCache(str(tmp_path / "cache"), ttl_hours=24)

    with (
        patch.object(app_module, "_FRONTEND_DIST", dist_dir),
        patch.object(app_module, "_FRONTEND_INDEX", index_path),
        patch("ideago.auth.dependencies.get_settings", return_value=prod_settings),
        patch("ideago.api.dependencies.get_settings", return_value=prod_settings),
        patch("ideago.api.dependencies._cache", local_cache),
        patch("ideago.api.dependencies.get_cache", return_value=local_cache),
        patch("ideago.api.app.get_settings", return_value=prod_settings),
        patch("ideago.auth.supabase_admin._is_configured", return_value=False),
    ):
        app = create_app()
        with TestClient(app) as local_client:
            csrf = local_client.post(
                "/api/v1/analyze",
                json={"query": "A product idea worth testing"},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert csrf.status_code == 403
            assert csrf.json()["error"]["code"] == "CSRF_MISSING_HEADER"
            app_module._rate_limit_store.clear()

            first = local_client.post(
                "/api/v1/analyze",
                json={"query": "A product idea worth testing"},
                headers={
                    "X-Requested-With": "IdeaGo",
                    "Authorization": f"Bearer {token}",
                    "X-Trace-Id": "trace-123",
                },
            )
            second = local_client.post(
                "/api/v1/analyze",
                json={"query": "Another product idea worth testing"},
                headers={
                    "X-Requested-With": "IdeaGo",
                    "Authorization": f"Bearer {token}",
                },
            )
            reports_first = local_client.get(
                "/api/v1/reports",
                headers={
                    "X-Requested-With": "IdeaGo",
                    "Authorization": f"Bearer {token}",
                },
            )
            reports_second = local_client.get(
                "/api/v1/reports",
                headers={
                    "X-Requested-With": "IdeaGo",
                    "Authorization": f"Bearer {token}",
                },
            )
            static_file = local_client.get("/logo.svg")
            api_not_found = local_client.get("/api/unknown")
            suffix_not_found = local_client.get("/missing.js")

    assert first.status_code == 200
    assert first.headers["X-Trace-Id"] == "trace-123"
    assert first.headers["X-Content-Type-Options"] == "nosniff"
    assert first.headers["X-Frame-Options"] == "DENY"
    assert "Strict-Transport-Security" in first.headers
    assert second.status_code == 429
    assert second.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    assert reports_first.status_code == 200
    assert reports_second.status_code == 429
    assert static_file.status_code == 200
    assert "<svg" in static_file.text
    assert api_not_found.status_code == 404
    assert suffix_not_found.status_code == 404


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
        self.headers: dict[str, str] = {}

    def json(self):
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "boom",
                request=httpx.Request("GET", "https://example.com"),
                response=httpx.Response(self.status_code),
            )


class _AsyncClientContext:
    def __init__(self, client: object) -> None:
        self._client = client

    async def __aenter__(self) -> object:
        return self._client

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


def _build_supabase_jwks_token(
    *,
    subject: str = "supa-user",
    email: str = "supa@example.com",
    audience: str = "authenticated",
    issuer: str = "https://example.supabase.co/auth/v1",
    expires_at: datetime | None = None,
    kid: str = "kid-1",
) -> tuple[str, dict]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_jwk = json.loads(
        jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key())
    )
    public_jwk["kid"] = kid
    expires = expires_at or (datetime.now(timezone.utc) + timedelta(minutes=5))
    token = jwt.encode(
        {
            "sub": subject,
            "email": email,
            "aud": audience,
            "iss": issuer,
            "exp": expires,
        },
        private_key,
        algorithm="RS256",
        headers={"kid": kid},
    )
    return token, public_jwk


def _make_supabase_auth_settings(**overrides: object) -> object:
    values = {
        "auth_session_secret": "",
        "supabase_url": "https://example.supabase.co",
        "supabase_anon_key": "anon",
        "supabase_jwt_audience": "authenticated",
        "supabase_jwks_cache_ttl_seconds": 300,
        "get_supabase_jwks_url": lambda self: (
            "https://example.supabase.co/auth/v1/.well-known/jwks.json"
        ),
        "get_supabase_jwt_issuer": lambda self: "https://example.supabase.co/auth/v1",
    }
    values.update(overrides)
    return type("Settings", (), values)()


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


def test_verify_ideago_jwt_invalid_and_extract_helpers() -> None:
    expired = jwt.encode(
        {
            "sub": "user-123",
            "aud": "ideago-auth",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        },
        "test-secret",
        algorithm="HS256",
    )

    assert auth_deps._verify_ideago_jwt("not-a-jwt", "test-secret") is None
    assert auth_deps._verify_ideago_jwt(expired, "test-secret") is None
    assert auth_deps._extract_user_from_jwt_payload({}) is None
    assert auth_deps._extract_user_from_api_response({}) is None
    assert auth_deps._extract_user_from_ideago_payload({}) is None


def test_extract_token_subject_with_supabase_jwks_jwt() -> None:
    token, public_jwk = _build_supabase_jwks_token()
    fake_settings = type(
        "Settings",
        (),
        {
            "auth_session_secret": "",
            "supabase_url": "https://example.supabase.co",
            "supabase_anon_key": "anon-key",
            "supabase_jwt_audience": "authenticated",
            "supabase_jwks_cache_ttl_seconds": 300,
            "get_supabase_jwks_url": lambda self: (
                "https://example.supabase.co/auth/v1/.well-known/jwks.json"
            ),
            "get_supabase_jwt_issuer": lambda self: (
                "https://example.supabase.co/auth/v1"
            ),
        },
    )()

    with (
        patch("ideago.auth.dependencies.get_settings", return_value=fake_settings),
        patch(
            "ideago.auth.dependencies._fetch_jwks",
            new=AsyncMock(return_value={"keys": [public_jwk]}),
        ),
    ):
        assert auth_deps.extract_token_subject(token) == "supa-user"


@pytest.mark.asyncio
async def test_get_optional_user_via_remote_verification() -> None:
    token, _public_jwk = _build_supabase_jwks_token()
    request = type(
        "Req",
        (),
        {"headers": {"Authorization": f"Bearer {token}"}},
    )()
    fake_settings = _make_supabase_auth_settings()
    with (
        patch("ideago.auth.dependencies.get_settings", return_value=fake_settings),
        patch(
            "ideago.auth.dependencies._fetch_jwks",
            new=AsyncMock(side_effect=httpx.TimeoutException("timeout")),
        ),
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
    fake_settings = _make_supabase_auth_settings(
        supabase_url="",
        supabase_anon_key="",
        get_supabase_jwks_url=lambda self: "",
        get_supabase_jwt_issuer=lambda self: "",
    )
    request_no_header = type("Req", (), {"headers": {}})()
    request_empty_token = type("Req", (), {"headers": {"Authorization": "Bearer "}})()

    with patch("ideago.auth.dependencies.get_settings", return_value=fake_settings):
        assert await auth_deps.get_optional_user(request_no_header) is None
        assert await auth_deps.get_optional_user(request_empty_token) is None


@pytest.mark.asyncio
async def test_get_optional_user_supabase_jwt_invalid_returns_none() -> None:
    fake_settings = _make_supabase_auth_settings()
    request = type(
        "Req",
        (),
        {"headers": {"Authorization": "Bearer invalid"}},
    )()

    with (
        patch("ideago.auth.dependencies.get_settings", return_value=fake_settings),
        patch(
            "ideago.auth.dependencies._fetch_jwks",
            new=AsyncMock(return_value={"keys": []}),
        ),
    ):
        assert await auth_deps.get_optional_user(request) is None


@pytest.mark.asyncio
async def test_get_optional_user_via_supabase_jwks() -> None:
    token, public_jwk = _build_supabase_jwks_token()
    request = type("Req", (), {"headers": {"Authorization": f"Bearer {token}"}})()
    fake_settings = _make_supabase_auth_settings()
    with (
        patch("ideago.auth.dependencies.get_settings", return_value=fake_settings),
        patch(
            "ideago.auth.dependencies._fetch_jwks",
            new=AsyncMock(return_value={"keys": [public_jwk]}),
        ),
    ):
        user = await auth_deps.get_optional_user(request)

    assert user is not None
    assert user.id == "supa-user"
    assert user.email == "supa@example.com"


@pytest.mark.asyncio
async def test_get_optional_user_supabase_jwt_expired_returns_none() -> None:
    token, public_jwk = _build_supabase_jwks_token(
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1)
    )
    request = type("Req", (), {"headers": {"Authorization": f"Bearer {token}"}})()
    fake_settings = _make_supabase_auth_settings()
    with (
        patch("ideago.auth.dependencies.get_settings", return_value=fake_settings),
        patch(
            "ideago.auth.dependencies._fetch_jwks",
            new=AsyncMock(return_value={"keys": [public_jwk]}),
        ),
    ):
        assert await auth_deps.get_optional_user(request) is None


@pytest.mark.asyncio
async def test_get_optional_user_supabase_jwt_invalid_audience_returns_none() -> None:
    token, public_jwk = _build_supabase_jwks_token(audience="other-audience")
    request = type("Req", (), {"headers": {"Authorization": f"Bearer {token}"}})()
    fake_settings = _make_supabase_auth_settings()
    with (
        patch("ideago.auth.dependencies.get_settings", return_value=fake_settings),
        patch(
            "ideago.auth.dependencies._fetch_jwks",
            new=AsyncMock(return_value={"keys": [public_jwk]}),
        ),
    ):
        assert await auth_deps.get_optional_user(request) is None


@pytest.mark.asyncio
async def test_get_optional_user_supabase_jwt_invalid_issuer_returns_none() -> None:
    token, public_jwk = _build_supabase_jwks_token(
        issuer="https://evil.example.com/auth/v1"
    )
    request = type("Req", (), {"headers": {"Authorization": f"Bearer {token}"}})()
    fake_settings = _make_supabase_auth_settings()
    with (
        patch("ideago.auth.dependencies.get_settings", return_value=fake_settings),
        patch(
            "ideago.auth.dependencies._fetch_jwks",
            new=AsyncMock(return_value={"keys": [public_jwk]}),
        ),
    ):
        assert await auth_deps.get_optional_user(request) is None


@pytest.mark.asyncio
async def test_get_optional_user_refreshes_jwks_on_missing_kid() -> None:
    token, public_jwk = _build_supabase_jwks_token(kid="new-kid")
    request = type("Req", (), {"headers": {"Authorization": f"Bearer {token}"}})()
    fake_settings = _make_supabase_auth_settings()
    with (
        patch("ideago.auth.dependencies.get_settings", return_value=fake_settings),
        patch(
            "ideago.auth.dependencies._fetch_jwks",
            new=AsyncMock(side_effect=[{"keys": []}, {"keys": [public_jwk]}]),
        ) as fetch_jwks,
    ):
        user = await auth_deps.get_optional_user(request)

    assert user is not None
    assert user.id == "supa-user"
    assert fetch_jwks.await_count == 2


@pytest.mark.asyncio
async def test_get_optional_user_remote_fallback_fails_when_jwks_unavailable() -> None:
    token, _public_jwk = _build_supabase_jwks_token()
    request = type("Req", (), {"headers": {"Authorization": f"Bearer {token}"}})()
    fake_settings = _make_supabase_auth_settings()
    with (
        patch("ideago.auth.dependencies.get_settings", return_value=fake_settings),
        patch(
            "ideago.auth.dependencies._fetch_jwks",
            new=AsyncMock(side_effect=httpx.TimeoutException("timeout")),
        ),
        patch(
            "ideago.auth.dependencies._verify_supabase_token_remote",
            new=AsyncMock(return_value=None),
        ),
    ):
        assert await auth_deps.get_optional_user(request) is None


@pytest.mark.asyncio
async def test_get_current_user_raises_when_missing() -> None:
    with pytest.raises(HTTPException) as exc:
        await auth_deps.get_current_user(None)
    assert exc.value.status_code == 401


def test_auth_http_client_and_jwk_lookup_helpers() -> None:
    auth_deps._clear_jwks_cache()
    first = auth_deps._get_http_client()
    second = auth_deps._get_http_client()

    assert first is second
    assert auth_deps._get_jwk_for_kid({"keys": "nope"}, "kid") is None
    assert auth_deps._get_jwk_for_kid({"keys": [{"kid": "match"}]}, "match") == {
        "kid": "match"
    }


@pytest.mark.asyncio
async def test_close_auth_http_client_and_fetch_jwks_error_paths() -> None:
    fake_settings = _make_supabase_auth_settings()
    fake_client = AsyncMock()
    fake_client.get = AsyncMock(
        side_effect=[
            _AdminFakeResponse(200, payload={"keys": []}),
            _AdminFakeResponse(200, payload=[]),
        ]
    )
    auth_deps._http_client = fake_client
    auth_deps._jwks_cache = {"keys": [{"kid": "old"}]}
    auth_deps._jwks_cache_expires_at = 999.0

    with patch("ideago.auth.dependencies.get_settings", return_value=fake_settings):
        jwks = await auth_deps._fetch_jwks()
        with pytest.raises(RuntimeError):
            await auth_deps._fetch_jwks()

    assert jwks == {"keys": []}

    await auth_deps.close_auth_http_client()

    assert auth_deps._http_client is None
    assert auth_deps._jwks_cache is None

    no_url_settings = _make_supabase_auth_settings(
        get_supabase_jwks_url=lambda self: ""
    )
    with (
        patch("ideago.auth.dependencies.get_settings", return_value=no_url_settings),
        pytest.raises(RuntimeError),
    ):
        await auth_deps._fetch_jwks()


@pytest.mark.asyncio
async def test_get_jwks_cache_and_signing_key_error_paths() -> None:
    fake_settings = _make_supabase_auth_settings(supabase_jwks_cache_ttl_seconds=0)
    token, public_jwk = _build_supabase_jwks_token()
    mismatch_jwk = dict(public_jwk, alg="RS512")

    with (
        patch("ideago.auth.dependencies.get_settings", return_value=fake_settings),
        patch(
            "ideago.auth.dependencies._fetch_jwks",
            new=AsyncMock(return_value={"keys": [public_jwk]}),
        ) as fetch_jwks,
    ):
        first = await auth_deps._get_jwks()
        second = await auth_deps._get_jwks()

    assert first == {"keys": [public_jwk]}
    assert second == {"keys": [public_jwk]}
    assert fetch_jwks.await_count == 2

    with pytest.raises(ValueError):
        await auth_deps._get_supabase_signing_key("not-a-jwt")

    bad_alg_token = jwt.encode(
        {
            "sub": "user",
            "aud": "authenticated",
            "iss": "https://example.supabase.co/auth/v1",
        },
        "secret",
        algorithm="HS256",
        headers={"kid": "kid-1"},
    )
    with pytest.raises(ValueError):
        await auth_deps._get_supabase_signing_key(bad_alg_token)

    missing_kid_token = jwt.encode(
        {
            "sub": "user",
            "aud": "authenticated",
            "iss": "https://example.supabase.co/auth/v1",
        },
        rsa.generate_private_key(public_exponent=65537, key_size=2048),
        algorithm="RS256",
    )
    with pytest.raises(ValueError):
        await auth_deps._get_supabase_signing_key(missing_kid_token)

    with (
        patch(
            "ideago.auth.dependencies._get_jwks",
            new=AsyncMock(return_value={"keys": [mismatch_jwk]}),
        ),
        pytest.raises(ValueError),
    ):
        await auth_deps._get_supabase_signing_key(token)


@pytest.mark.asyncio
async def test_verify_supabase_jwt_and_remote_error_paths() -> None:
    token, _public_jwk = _build_supabase_jwks_token()
    no_config_settings = _make_supabase_auth_settings(
        supabase_url="",
        get_supabase_jwt_issuer=lambda self: "",
    )

    with patch(
        "ideago.auth.dependencies.get_settings", return_value=no_config_settings
    ):
        result = await auth_deps._verify_supabase_jwt(token)
    assert result.payload is None
    assert result.should_fallback_remote is False

    configured_settings = _make_supabase_auth_settings()
    with (
        patch(
            "ideago.auth.dependencies.get_settings", return_value=configured_settings
        ),
        patch(
            "ideago.auth.dependencies._get_supabase_signing_key",
            new=AsyncMock(side_effect=httpx.ConnectError("boom")),
        ),
    ):
        result = await auth_deps._verify_supabase_jwt(token)
    assert result.should_fallback_remote is True

    fake_client = AsyncMock()
    fake_client.get = AsyncMock(
        side_effect=[
            _AdminFakeResponse(401, payload={"error": "bad"}),
            httpx.TimeoutException("timeout"),
            RuntimeError("boom"),
            _AdminFakeResponse(200, payload={"id": "uid-2", "email": "u2@example.com"}),
        ]
    )
    auth_deps._http_client = fake_client

    with patch(
        "ideago.auth.dependencies.get_settings", return_value=configured_settings
    ):
        assert await auth_deps._verify_supabase_token_remote(token) is None
        assert await auth_deps._verify_supabase_token_remote(token) is None
        assert await auth_deps._verify_supabase_token_remote(token) is None
        assert await auth_deps._verify_supabase_token_remote(token) == {
            "id": "uid-2",
            "email": "u2@example.com",
        }


def test_extract_token_subject_returns_empty_when_no_valid_sub() -> None:
    fake_settings = _make_supabase_auth_settings()
    with (
        patch("ideago.auth.dependencies.get_settings", return_value=fake_settings),
        patch(
            "ideago.auth.dependencies._verify_supabase_jwt",
            new=AsyncMock(
                return_value=auth_deps._SupabaseJwtVerificationResult(
                    payload={"email": "x@example.com"},
                    should_fallback_remote=False,
                )
            ),
        ),
    ):
        assert auth_deps.extract_token_subject("token") == ""


@pytest.mark.asyncio
async def test_run_async_bridge_admin_resolution_and_require_admin() -> None:
    async def compute() -> str:
        return "ok"

    results: list[str] = []

    async def runner() -> None:
        results.append(auth_deps._run_async_for_sync_context(compute()))

    await runner()
    assert results == ["ok"]

    user = auth_deps.AuthUser(id="user-1", email="u@example.com", role="user")
    admin_user = auth_deps.AuthUser(id="admin-1", email="a@example.com", role="admin")

    resolved_admin = await auth_deps._resolve_admin_role(admin_user)
    assert resolved_admin.role == "admin"

    with patch(
        "ideago.auth.supabase_admin.get_profile",
        new=AsyncMock(return_value={"role": "admin"}),
    ):
        elevated = await auth_deps._resolve_admin_role(user)
    assert elevated.role == "admin"

    with patch(
        "ideago.auth.supabase_admin.get_profile",
        new=AsyncMock(side_effect=RuntimeError("boom")),
    ):
        unchanged = await auth_deps._resolve_admin_role(user)
    assert unchanged.role == "user"

    with pytest.raises(HTTPException) as exc:
        await auth_deps.require_admin(user)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_health_route_internal_checks_and_main_entrypoint(tmp_path) -> None:
    health_settings = type(
        "Settings",
        (),
        {
            "supabase_url": "https://example.supabase.co",
            "supabase_service_role_key": "srk",
            "stripe_secret_key": "sk_test",
        },
    )()
    no_supabase = type(
        "Settings",
        (),
        {
            "supabase_url": "",
            "supabase_service_role_key": "",
            "stripe_secret_key": "",
        },
    )()
    ok_client = AsyncMock()
    ok_client.get = AsyncMock(return_value=_AdminFakeResponse(200))
    bad_client = AsyncMock()
    bad_client.get = AsyncMock(return_value=_AdminFakeResponse(503))

    with patch("ideago.api.routes.health.get_settings", return_value=no_supabase):
        assert await health_route._check_supabase() == "not_configured"
        assert await health_route._check_stripe() == "not_configured"

    with (
        patch("ideago.api.routes.health.get_settings", return_value=health_settings),
        patch(
            "ideago.api.routes.health.httpx.AsyncClient",
            return_value=_AsyncClientContext(ok_client),
        ),
    ):
        assert await health_route._check_supabase() == "ok"
        assert await health_route._check_stripe() == "ok"

    with (
        patch("ideago.api.routes.health.get_settings", return_value=health_settings),
        patch(
            "ideago.api.routes.health.httpx.AsyncClient",
            return_value=_AsyncClientContext(bad_client),
        ),
    ):
        assert await health_route._check_supabase() == "error:503"

    with (
        patch("ideago.api.routes.health.get_settings", return_value=health_settings),
        patch(
            "ideago.api.routes.health.httpx.AsyncClient",
            side_effect=RuntimeError("boom"),
        ),
    ):
        assert await health_route._check_supabase() == "unreachable:RuntimeError"

    with patch(
        "ideago.api.routes.health._check_supabase",
        new=AsyncMock(return_value="error:503"),
    ):
        assert await health_route.health_check() == {"status": "degraded"}

    fake_orchestrator = type(
        "Orchestrator",
        (),
        {"get_source_availability": lambda self: {"github": True}},
    )()
    with (
        patch(
            "ideago.api.routes.health.get_orchestrator", return_value=fake_orchestrator
        ),
        patch(
            "ideago.api.routes.health._check_supabase", new=AsyncMock(return_value="ok")
        ),
        patch(
            "ideago.api.routes.health._check_stripe", new=AsyncMock(return_value="ok")
        ),
    ):
        assert await health_route.detailed_health_check() == {
            "status": "ok",
            "sources": {"github": True},
            "dependencies": {"supabase": "ok", "stripe": "ok"},
        }

    with (
        patch(
            "ideago.api.routes.health.get_orchestrator",
            side_effect=RuntimeError("boom"),
        ),
        patch(
            "ideago.api.routes.health._check_supabase",
            new=AsyncMock(return_value="error:500"),
        ),
        patch(
            "ideago.api.routes.health._check_stripe",
            new=AsyncMock(return_value="not_configured"),
        ),
    ):
        degraded = await health_route.detailed_health_check()
    assert degraded["status"] == "degraded"
    assert degraded["sources"] == {}

    main_settings = type("Settings", (), {"host": "127.0.0.1", "port": 9000})()
    with (
        patch("ideago.config.settings.get_settings", return_value=main_settings),
        patch("ideago.api.app.create_app", return_value="app"),
        patch("uvicorn.run") as uvicorn_run,
    ):
        runpy.run_module("ideago.__main__", run_name="__main__")
    uvicorn_run.assert_called_once_with("app", host="127.0.0.1", port=9000)


@pytest.mark.asyncio
async def test_api_dependencies_runtime_state_and_dedup_helpers(tmp_path) -> None:
    run = deps.ReportRunState(max_history=1)
    queue = run.subscribe()
    first_event = PipelineEvent(
        type=EventType.INTENT_STARTED,
        stage="intent",
        message="started",
        data={"step": 1},
    )
    ready_event = PipelineEvent(
        type=EventType.REPORT_READY,
        stage="done",
        message="ready",
        data={"id": "r1"},
    )
    await run.publish(first_event)
    assert await queue.get() == first_event
    await run.publish(ready_event)
    assert run.is_terminal is True
    assert len(run.history_snapshot()) == 1
    run.unsubscribe(queue)

    deps._report_runs.clear()
    stale = deps.ReportRunState()
    stale.is_terminal = True
    stale.updated_at = time.monotonic() - 1000
    deps._report_runs["stale"] = stale
    deps.cleanup_report_runs()
    assert "stale" not in deps._report_runs

    created = deps.get_or_create_report_run("fresh")
    assert deps.get_or_create_report_run("fresh") is created
    assert deps.get_report_run("fresh") is created

    file_settings = Settings(
        _env_file=None,
        environment="development",
        cache_dir=str(tmp_path / "cache"),
        supabase_url="",
        supabase_service_role_key="",
    )
    deps._cache = None
    with patch("ideago.api.dependencies.get_settings", return_value=file_settings):
        cache = deps.get_cache()
    assert isinstance(cache, FileCache)

    deps._cache = None
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            environment="production",
            supabase_url="",
            supabase_service_role_key="",
        )
    prod_like_settings = type(
        "Settings",
        (),
        {
            "environment": "production",
            "supabase_url": "",
            "supabase_service_role_key": "",
            "anonymous_cache_ttl_hours": 24,
            "cache_dir": str(tmp_path / "unused"),
            "file_cache_max_entries": 100,
        },
    )()
    with (
        patch("ideago.api.dependencies.get_settings", return_value=prod_like_settings),
        pytest.raises(RuntimeError),
    ):
        deps.get_cache()

    fake_repo = object()
    deps._cache = None
    sb_settings = Settings(
        _env_file=None,
        environment="production",
        auth_session_secret="test-session-secret-0123456789abcdef",
        frontend_app_url="https://app.example.com",
        supabase_url="https://example.supabase.co",
        supabase_service_role_key="srk",
    )
    with (
        patch("ideago.api.dependencies.get_settings", return_value=sb_settings),
        patch(
            "ideago.cache.supabase_cache.SupabaseReportRepository",
            return_value=fake_repo,
        ),
    ):
        assert deps.get_cache() is fake_repo

    deps._dedup_http_client = None
    dedup_settings = type(
        "Settings",
        (),
        {
            "supabase_url": "https://example.supabase.co",
            "supabase_service_role_key": "srk",
        },
    )()
    with patch("ideago.api.dependencies.get_settings", return_value=dedup_settings):
        assert deps._supabase_dedup_configured() is True
        headers = deps._dedup_headers()
        client = deps._get_dedup_client()
        assert headers["Authorization"] == "Bearer srk"
        assert deps._get_dedup_client() is client

    fake_client = AsyncMock()
    fake_client.post = AsyncMock(
        side_effect=[
            _AdminFakeResponse(200, payload="existing-report"),
            _AdminFakeResponse(500, payload={}),
            RuntimeError("boom"),
            _AdminFakeResponse(200, payload=True),
            _AdminFakeResponse(200, payload=False),
            RuntimeError("boom"),
            _AdminFakeResponse(204, payload={}),
            RuntimeError("boom"),
        ]
    )
    with (
        patch("ideago.api.dependencies.get_settings", return_value=dedup_settings),
        patch("ideago.api.dependencies._get_dedup_client", return_value=fake_client),
    ):
        assert await deps._pg_reserve("k", "r1", "u1") == "existing-report"
        assert await deps._pg_reserve("k", "r1", "u1") is None
        assert await deps._pg_reserve("k", "r1", "u1") is None
        assert await deps._pg_is_processing("r1") is True
        assert await deps._pg_is_processing("r1") is False
        assert await deps._pg_is_processing("r1") is False
        await deps._pg_release("r1")
        await deps._pg_release("r1")

    deps._processing_reports.clear()
    with patch(
        "ideago.api.dependencies._supabase_dedup_configured", return_value=False
    ):
        assert (
            await deps.reserve_processing_report("hash", "report-1", user_id="u1")
            is None
        )
        assert (
            await deps.reserve_processing_report("hash", "report-2", user_id="u1")
            == "report-1"
        )
        assert await deps.is_processing_report("report-1") is True
        await deps.release_processing_report("report-1")
        assert await deps.is_processing_report("report-1") is False

    deps._processing_reports.clear()
    with (
        patch("ideago.api.dependencies._supabase_dedup_configured", return_value=True),
        patch("ideago.api.dependencies._pg_reserve", new=AsyncMock(return_value=None)),
        patch("ideago.api.dependencies._pg_release", new=AsyncMock(return_value=None)),
        patch(
            "ideago.api.dependencies._pg_is_processing",
            new=AsyncMock(return_value=True),
        ),
    ):
        assert (
            await deps.reserve_processing_report("hash", "report-3", user_id="u2")
            is None
        )
        assert deps.get_processing_reports() == {"u2:hash": "report-3"}
        assert await deps.is_processing_report("report-x") is True
        await deps.release_processing_report("report-3")
        assert deps.get_processing_reports() == {}

    task = asyncio.create_task(asyncio.sleep(0))
    await deps.register_pipeline_task("report-task", task)
    assert await deps.get_pipeline_task_for_report("report-task") is task
    assert await deps.remove_pipeline_task("report-task") is task
    deps.set_pipeline_task("report-task-2", task)
    assert deps.is_report_id_processing("missing") is False
    await task
    deps._cache = None


def test_api_app_rate_limit_and_sentry_helpers() -> None:
    app_module._rate_limit_store.clear()
    app_module._rate_limit_store["stale"] = [time.monotonic() - 1000]
    app_module._rate_limit_store["fresh"] = [time.monotonic()]
    rate_settings = type(
        "Settings",
        (),
        {
            "rate_limit_analyze_window_seconds": 10,
            "rate_limit_reports_window_seconds": 20,
        },
    )()

    with patch("ideago.api.app.get_settings", return_value=rate_settings):
        evicted = app_module._evict_stale_rate_limit_keys()
    assert evicted == 1
    assert "stale" not in app_module._rate_limit_store

    sentry_settings = type(
        "Settings",
        (),
        {
            "sentry_dsn": "https://example@sentry.io/1",
            "sentry_traces_sample_rate": 0.5,
            "environment": "production",
        },
    )()
    with patch("sentry_sdk.init") as sentry_init:
        app_module._init_sentry(sentry_settings)
    sentry_init.assert_called_once()

    no_sentry = type("Settings", (), {"sentry_dsn": ""})()
    with patch("sentry_sdk.init") as sentry_init:
        app_module._init_sentry(no_sentry)
    sentry_init.assert_not_called()

    create_settings = Settings(
        _env_file=None,
        environment="development",
        auth_session_secret="test-session-secret-0123456789abcdef",
        frontend_app_url="https://app.example.com",
        cors_allow_origins="*",
        supabase_url="",
        supabase_anon_key="",
        supabase_service_role_key="",
    )
    with (
        patch("ideago.api.app.get_settings", return_value=create_settings),
        patch("ideago.api.app._init_sentry"),
    ):
        app = create_app()
    assert app is not None

    prod_bad_cors = Settings(
        _env_file=None,
        environment="production",
        auth_session_secret="test-session-secret-0123456789abcdef",
        frontend_app_url="https://app.example.com",
        cors_allow_origins="*",
        supabase_url="https://example.supabase.co",
        supabase_service_role_key="srk",
    )
    with (
        patch("ideago.api.app.get_settings", return_value=prod_bad_cors),
        patch("ideago.api.app._init_sentry"),
        pytest.raises(RuntimeError),
    ):
        create_app()


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


def test_supabase_admin_headers_and_client_lifecycle() -> None:
    fake_settings = type(
        "Settings",
        (),
        {"supabase_service_role_key": "srk"},
    )()

    with patch("ideago.auth.supabase_admin.get_settings", return_value=fake_settings):
        headers = supabase_admin._headers()

    assert headers["apikey"] == "srk"
    assert headers["Authorization"] == "Bearer srk"


@pytest.mark.asyncio
async def test_supabase_admin_list_profiles_quota_update_and_delete_user_data() -> None:
    fake_settings = type(
        "Settings",
        (),
        {
            "supabase_url": "https://example.supabase.co",
            "supabase_service_role_key": "srk",
        },
    )()
    fake_client = AsyncMock()
    fake_client.get = AsyncMock(
        side_effect=[
            _AdminFakeResponse(200, payload=[{"id": "u1", "plan": "free"}]),
            _AdminFakeResponse(500, text="fail"),
            RuntimeError("network"),
        ]
    )
    fake_client.patch = AsyncMock(
        side_effect=[
            _AdminFakeResponse(200, payload=[{"id": "u1", "plan_limit": 20}]),
            _AdminFakeResponse(500, text="fail"),
            RuntimeError("network"),
        ]
    )
    fake_client.delete = AsyncMock(
        side_effect=[
            _AdminFakeResponse(204),
            _AdminFakeResponse(204),
            _AdminFakeResponse(204),
            _AdminFakeResponse(204),
            _AdminFakeResponse(500, text="fail"),
            _AdminFakeResponse(204),
            _AdminFakeResponse(204),
            _AdminFakeResponse(204),
        ]
    )

    with (
        patch("ideago.auth.supabase_admin._is_configured", return_value=True),
        patch("ideago.auth.supabase_admin.get_settings", return_value=fake_settings),
        patch("ideago.auth.supabase_admin._get_client", return_value=fake_client),
    ):
        listed = await supabase_admin.list_profiles(limit=10, offset=5)
        listed_fail = await supabase_admin.list_profiles()
        listed_error = await supabase_admin.list_profiles()
        updated = await supabase_admin.set_user_quota("u1", plan_limit=20)
        updated_fail = await supabase_admin.set_user_quota("u1", plan_limit=10)
        updated_error = await supabase_admin.set_user_quota("u1", plan_limit=5)
        no_payload = await supabase_admin.set_user_quota("u1")
        deleted = await supabase_admin.delete_user_data("u1")
        partial = await supabase_admin.delete_user_data("u2")

    assert listed == [{"id": "u1", "plan": "free"}]
    assert listed_fail == []
    assert listed_error == []
    assert updated["id"] == "u1"
    assert updated_fail["error"] == "update_failed"
    assert updated_error["error"] == "network_error"
    assert no_payload["error"] == "nothing_to_update"
    assert deleted == {"deleted": True}
    assert partial["error"] == "partial_failure"


@pytest.mark.asyncio
async def test_supabase_admin_delete_user_data_not_configured() -> None:
    with patch("ideago.auth.supabase_admin._is_configured", return_value=False):
        result = await supabase_admin.delete_user_data("uid")
    assert result["error"] == "supabase_not_configured"


@pytest.mark.asyncio
async def test_billing_validate_redirect_and_service_paths() -> None:
    good_settings = type(
        "Settings",
        (),
        {
            "frontend_app_url": "https://app.example.com",
            "stripe_secret_key": "sk_test_x",
            "supabase_url": "https://example.supabase.co",
            "supabase_service_role_key": "srk",
            "stripe_webhook_secret": "whsec",
        },
    )()
    bad_settings = type(
        "Settings",
        (),
        {
            "frontend_app_url": "",
            "stripe_secret_key": "",
            "supabase_url": "",
            "supabase_service_role_key": "",
            "stripe_webhook_secret": "whsec",
        },
    )()
    fake_http_client = AsyncMock()
    fake_http_client.get = AsyncMock(
        side_effect=[
            _AdminFakeResponse(200, payload=[{"stripe_customer_id": "cus_existing"}]),
            _AdminFakeResponse(200, payload=[{}]),
        ]
    )
    fake_http_client.patch = AsyncMock(
        side_effect=[_AdminFakeResponse(204), _AdminFakeResponse(500, text="fail")]
    )

    class _Customer:
        id = "cus_new"

    class _Session:
        def __init__(self, url: str | None) -> None:
            self.url = url

    fake_event = type(
        "Event",
        (),
        {
            "id": "evt_1",
            "type": "checkout.session.completed",
            "data": type(
                "Data",
                (),
                {"object": {"customer": "cus_1", "subscription": "sub_1"}},
            )(),
        },
    )()

    with (
        patch("ideago.api.routes.billing.get_settings", return_value=bad_settings),
        pytest.raises(AppError),
    ):
        billing_route._validate_redirect_url("https://app.example.com/ok", "return_url")

    with patch("ideago.api.routes.billing.get_settings", return_value=good_settings):
        billing_route._validate_redirect_url("https://app.example.com/ok", "return_url")
        with pytest.raises(AppError):
            billing_route._validate_redirect_url(
                "ftp://app.example.com/ok", "return_url"
            )
        with pytest.raises(AppError):
            billing_route._validate_redirect_url(
                "https://evil.example.com/ok", "return_url"
            )

    with (
        patch("ideago.billing.stripe_service.get_settings", return_value=good_settings),
        patch(
            "httpx.AsyncClient",
            return_value=_AsyncClientContext(fake_http_client),
        ),
        patch(
            "ideago.billing.stripe_service.stripe.Customer.create",
            return_value=_Customer(),
        ),
        patch(
            "ideago.billing.stripe_service.stripe.checkout.Session.create",
            return_value=_Session("https://checkout.example.com"),
        ),
        patch(
            "ideago.billing.stripe_service.stripe.billing_portal.Session.create",
            return_value=_Session("https://portal.example.com"),
        ),
        patch(
            "ideago.billing.stripe_service.stripe.Webhook.construct_event",
            return_value=fake_event,
        ),
    ):
        assert stripe_service._configure() is True
        assert stripe_service.is_configured() is True
        assert (
            await stripe_service.get_or_create_customer("uid", "u@example.com")
            == "cus_existing"
        )
        assert (
            await stripe_service.get_or_create_customer("uid", "u@example.com")
            == "cus_new"
        )
        assert (
            await stripe_service.create_checkout_session(
                customer_id="cus_new",
                price_id="price_1",
                success_url="https://app.example.com/success",
                cancel_url="https://app.example.com/cancel",
            )
            == "https://checkout.example.com"
        )
        assert (
            await stripe_service.create_portal_session(
                customer_id="cus_new",
                return_url="https://app.example.com/profile",
            )
            == "https://portal.example.com"
        )
        assert stripe_service.construct_webhook_event(b"{}", "sig").id == "evt_1"

    with patch("ideago.billing.stripe_service.get_settings", return_value=bad_settings):
        assert stripe_service._configure() is False
        assert stripe_service.is_configured() is False
        with pytest.raises(RuntimeError):
            await stripe_service.get_or_create_customer("uid", "u@example.com")


@pytest.mark.asyncio
async def test_billing_claim_event_handle_webhook_and_routes() -> None:
    fake_settings = type(
        "Settings",
        (),
        {
            "frontend_app_url": "https://app.example.com",
            "stripe_pro_price_id": "price_1",
            "supabase_url": "https://example.supabase.co",
            "supabase_service_role_key": "srk",
            "stripe_webhook_secret": "whsec",
            "stripe_secret_key": "sk_test_x",
        },
    )()
    claim_client = AsyncMock()
    claim_client.post = AsyncMock(
        side_effect=[
            _AdminFakeResponse(201, payload=[{"event_id": "evt_1"}]),
            _AdminFakeResponse(409, payload=[]),
            RuntimeError("network"),
        ]
    )
    webhook_client = AsyncMock()
    webhook_client.patch = AsyncMock(return_value=_AdminFakeResponse(204))
    request = type(
        "Req",
        (),
        {
            "headers": {"stripe-signature": "sig"},
            "body": AsyncMock(return_value=b"{}"),
        },
    )()
    user = billing_route.AuthUser(id="uid", email="u@example.com")
    completed_event = type(
        "Event",
        (),
        {
            "id": "evt_1",
            "type": "checkout.session.completed",
            "data": type(
                "Data",
                (),
                {"object": {"customer": "cus_1", "subscription": "sub_1"}},
            )(),
        },
    )()
    deleted_event = type(
        "Event",
        (),
        {
            "id": "evt_2",
            "type": "customer.subscription.deleted",
            "data": type(
                "Data",
                (),
                {"object": {"customer": "cus_1", "status": "canceled"}},
            )(),
        },
    )()
    unknown_event = type(
        "Event",
        (),
        {
            "id": "evt_3",
            "type": "other.event",
            "data": type("Data", (), {"object": {}})(),
        },
    )()

    with (
        patch("ideago.billing.stripe_service.get_settings", return_value=fake_settings),
        patch(
            "httpx.AsyncClient",
            side_effect=[
                _AsyncClientContext(claim_client),
                _AsyncClientContext(claim_client),
                _AsyncClientContext(claim_client),
                _AsyncClientContext(claim_client),
                _AsyncClientContext(webhook_client),
                _AsyncClientContext(claim_client),
                _AsyncClientContext(webhook_client),
                _AsyncClientContext(claim_client),
                _AsyncClientContext(webhook_client),
            ],
        ),
    ):
        assert (
            await stripe_service._try_claim_event("evt_1", "checkout.session.completed")
            is True
        )
        assert (
            await stripe_service._try_claim_event("evt_1", "checkout.session.completed")
            is False
        )
        assert await stripe_service._try_claim_event("evt_2", "other.event") is True
        await stripe_service.handle_webhook_event(completed_event)
        await stripe_service.handle_webhook_event(deleted_event)
        await stripe_service.handle_webhook_event(unknown_event)

    with (
        patch("ideago.api.routes.billing.is_configured", return_value=False),
        pytest.raises(AppError) as not_configured,
    ):
        await billing_route.create_checkout(
            billing_route.CheckoutRequest(
                success_url="https://app.example.com/success",
                cancel_url="https://app.example.com/cancel",
            ),
            user,
        )

    with (
        patch("ideago.api.routes.billing.is_configured", return_value=True),
        patch(
            "ideago.api.routes.billing.get_settings",
            return_value=type("Settings", (), {"stripe_pro_price_id": ""})(),
        ),
        pytest.raises(AppError) as no_price,
    ):
        await billing_route.create_checkout(
            billing_route.CheckoutRequest(
                success_url="https://app.example.com/success",
                cancel_url="https://app.example.com/cancel",
            ),
            user,
        )

    with (
        patch("ideago.api.routes.billing.is_configured", return_value=True),
        patch("ideago.api.routes.billing.get_settings", return_value=fake_settings),
        patch(
            "ideago.api.routes.billing.get_or_create_customer",
            new=AsyncMock(return_value="cus_1"),
        ),
        patch(
            "ideago.api.routes.billing.create_checkout_session",
            new=AsyncMock(return_value=""),
        ),
        pytest.raises(AppError) as checkout_failed,
    ):
        await billing_route.create_checkout(
            billing_route.CheckoutRequest(
                success_url="https://app.example.com/success",
                cancel_url="https://app.example.com/cancel",
            ),
            user,
        )

    with (
        patch("ideago.api.routes.billing.is_configured", return_value=True),
        patch("ideago.api.routes.billing.get_settings", return_value=fake_settings),
        patch(
            "ideago.api.routes.billing.get_or_create_customer",
            new=AsyncMock(return_value="cus_1"),
        ),
        patch(
            "ideago.api.routes.billing.create_checkout_session",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ),
        pytest.raises(AppError) as checkout_error,
    ):
        await billing_route.create_checkout(
            billing_route.CheckoutRequest(
                success_url="https://app.example.com/success",
                cancel_url="https://app.example.com/cancel",
            ),
            user,
        )

    with (
        patch("ideago.api.routes.billing.is_configured", return_value=True),
        patch(
            "ideago.auth.supabase_admin.get_quota_info",
            new=AsyncMock(return_value={"plan": "pro"}),
        ),
    ):
        status = await billing_route.get_subscription_status(user)

    with (
        patch("ideago.api.routes.billing.is_configured", return_value=True),
        patch(
            "ideago.api.routes.billing.get_or_create_customer",
            new=AsyncMock(return_value="cus_1"),
        ),
        patch(
            "ideago.api.routes.billing.create_portal_session",
            new=AsyncMock(return_value="https://portal.example.com"),
        ),
        patch("ideago.api.routes.billing.get_settings", return_value=fake_settings),
    ):
        portal = await billing_route.create_portal(
            billing_route.PortalRequest(return_url="https://app.example.com/profile"),
            user,
        )

    with (
        patch("ideago.api.routes.billing.is_configured", return_value=True),
        patch(
            "ideago.api.routes.billing.construct_webhook_event",
            side_effect=RuntimeError("bad sig"),
        ),
        pytest.raises(AppError) as invalid_sig,
    ):
        await billing_route.stripe_webhook(request)

    with (
        patch("ideago.api.routes.billing.is_configured", return_value=True),
        patch(
            "ideago.api.routes.billing.construct_webhook_event",
            return_value=completed_event,
        ),
        patch(
            "ideago.api.routes.billing.handle_webhook_event",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ),
        pytest.raises(AppError) as webhook_error,
    ):
        await billing_route.stripe_webhook(request)

    with (
        patch("ideago.api.routes.billing.is_configured", return_value=True),
        patch(
            "ideago.api.routes.billing.construct_webhook_event",
            return_value=completed_event,
        ),
        patch(
            "ideago.api.routes.billing.handle_webhook_event",
            new=AsyncMock(return_value=None),
        ),
    ):
        ok = await billing_route.stripe_webhook(request)

    assert not_configured.value.status_code == 503
    assert no_price.value.status_code == 503
    assert checkout_failed.value.status_code == 502
    assert checkout_error.value.status_code == 500
    assert status.plan == "pro"
    assert portal.url == "https://portal.example.com"
    assert invalid_sig.value.status_code == 400
    assert webhook_error.value.status_code == 500
    assert ok == {"received": True}


@pytest.mark.asyncio
async def test_admin_routes_and_notifications() -> None:
    admin_user = admin_route.AuthUser(
        id="admin-id", email="admin@example.com", role="admin"
    )
    fake_settings = type(
        "Settings",
        (),
        {
            "supabase_url": "https://example.supabase.co",
            "supabase_service_role_key": "srk",
        },
    )()
    count_response = _AdminFakeResponse(200)
    count_response.headers["content-range"] = "0-9/10"
    plan_client = AsyncMock()
    plan_client.head = AsyncMock(return_value=count_response)
    plan_client.get = AsyncMock(
        return_value=_AdminFakeResponse(
            200, payload=[{"plan": "free"}, {"plan": "pro"}]
        )
    )

    with (
        patch(
            "ideago.api.routes.admin.list_profiles",
            new=AsyncMock(return_value=[{"id": "u1"}]),
        ),
        patch(
            "ideago.api.routes.admin.set_user_quota",
            new=AsyncMock(return_value={"id": "u1", "plan_limit": 20}),
        ),
        patch("ideago.api.routes.admin.log_audit_event", new=AsyncMock()),
        patch("ideago.api.routes.admin.get_settings", return_value=fake_settings),
        patch(
            "ideago.api.routes.admin.httpx.AsyncClient",
            return_value=_AsyncClientContext(plan_client),
        ),
        patch(
            "ideago.api.routes.admin.app_metrics.snapshot", return_value={"requests": 1}
        ),
        patch(
            "ideago.api.routes.health.detailed_health_check",
            new=AsyncMock(return_value={"status": "ok"}),
        ),
    ):
        users = await admin_route.admin_list_users(
            limit=10, offset=5, _admin=admin_user
        )
        updated = await admin_route.admin_set_quota(
            "u1",
            admin_route.QuotaAdjustment(plan_limit=20),
            _admin=admin_user,
        )
        stats = await admin_route.admin_system_stats(_admin=admin_user)
        metrics = await admin_route.admin_metrics(_admin=admin_user)
        health = await admin_route.admin_health(_admin=admin_user)

    with (
        patch(
            "ideago.api.routes.admin.set_user_quota",
            new=AsyncMock(return_value={"error": "update_failed"}),
        ),
        pytest.raises(AppError) as quota_exc,
    ):
        await admin_route.admin_set_quota(
            "u1",
            admin_route.QuotaAdjustment(plan_limit=10),
            _admin=admin_user,
        )

    class _Sender:
        async def send(self, **kwargs: str) -> bool:
            return kwargs["to"] == "u@example.com"

    with patch(
        "ideago.notifications.service.get_notification_sender", return_value=_Sender()
    ):
        assert (
            await notification_service.notify_welcome("u@example.com", "Alice") is True
        )
        assert (
            await notification_service.notify_quota_warning("u@example.com", 4, 5)
            is True
        )
        assert (
            await notification_service.notify_report_ready(
                "u@example.com", "report-1", "A very long query"
            )
            is True
        )

    sender = notification_service.LogNotificationSender()
    assert (
        await sender.send(
            to="u@example.com",
            subject="hello",
            body_text="body",
        )
        is True
    )
    assert users == [{"id": "u1"}]
    assert updated["plan_limit"] == 20
    assert stats["total_users"] == 10
    assert stats["plan_breakdown"] == {"free": 1, "pro": 1}
    assert metrics == {"requests": 1}
    assert health == {"status": "ok"}
    assert quota_exc.value.status_code == 400


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
    fake_auth = Settings(
        _env_file=None,
        environment="development",
        auth_session_secret=auth_secret,
        supabase_url="",
        supabase_anon_key="",
        supabase_service_role_key="",
    )

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
        with (
            patch("ideago.auth.dependencies.get_settings", return_value=fake_auth),
            patch("ideago.api.dependencies.get_settings", return_value=fake_auth),
            patch("ideago.api.app.get_settings", return_value=fake_auth),
            patch("ideago.auth.supabase_admin._is_configured", return_value=False),
            patch("ideago.api.routes.analyze._run_pipeline", new=fake_run),
        ):
            app = create_app()
            with TestClient(
                app,
                headers={
                    "X-Requested-With": "IdeaGo",
                    "Authorization": f"Bearer {token}",
                },
            ) as c:
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
