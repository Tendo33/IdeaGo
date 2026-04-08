"""Personal-mode API tests."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from ideago.api import app as app_module
from ideago.api import dependencies as deps
from ideago.api.app import create_app
from ideago.cache.file_cache import FileCache
from ideago.config.settings import get_settings, reload_settings
from ideago.models.research import Intent, Platform, ResearchReport, SearchQuery


def _make_report(
    cache_key: str = "test_key", query: str = "test idea"
) -> ResearchReport:
    intent = Intent(
        keywords_en=["test"],
        app_type="web",
        target_scenario="test",
        search_queries=[SearchQuery(platform=Platform.GITHUB, queries=["test"])],
        cache_key=cache_key,
    )
    return ResearchReport(query=query, intent=intent)


@pytest.fixture
def personal_runtime(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Iterator[FileCache]:
    cache_dir = tmp_path / "cache"
    checkpoint_path = tmp_path / "langgraph-checkpoints.db"
    monkeypatch.setenv("CACHE_DIR", str(cache_dir))
    monkeypatch.setenv("LANGGRAPH_CHECKPOINT_DB_PATH", str(checkpoint_path))
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")

    reload_settings()
    deps._cache = None
    deps._orchestrator = None

    cache = FileCache(
        str(cache_dir), ttl_hours=get_settings().anonymous_cache_ttl_hours
    )
    deps._cache = cache

    yield cache

    deps._cache = None
    deps._orchestrator = None
    get_settings.cache_clear()


def test_health_endpoint_returns_ok(personal_runtime: FileCache) -> None:
    app = create_app()

    with TestClient(app) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_reports_endpoints_are_anonymous(personal_runtime: FileCache) -> None:
    report = _make_report("report-key", "personal deployment idea")

    app = create_app()
    with TestClient(app) as client:
        personal_runtime._put_sync(report)

        list_response = client.get("/api/v1/reports")
        detail_response = client.get(f"/api/v1/reports/{report.id}")
        status_response = client.get(f"/api/v1/reports/{report.id}/status")
        export_response = client.get(f"/api/v1/reports/{report.id}/export")
        delete_response = client.delete(
            f"/api/v1/reports/{report.id}",
            headers={"X-Requested-With": "IdeaGo"},
        )

    assert list_response.status_code == 200
    assert list_response.json()["items"][0]["id"] == report.id
    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == report.id
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "complete"
    assert export_response.status_code == 200
    assert export_response.text.startswith("# Source Intelligence Report")
    assert delete_response.status_code == 200
    assert delete_response.json() == {"status": "deleted"}


def test_report_runtime_status_uses_status_file_when_report_not_ready(
    personal_runtime: FileCache,
) -> None:
    app = create_app()
    report = _make_report("pending-key", "pending idea")

    with TestClient(app) as client:
        personal_runtime._put_status_sync(
            report.id,
            "processing",
            report.query,
            None,
            "Analysis is in progress",
        )
        detail_response = client.get(f"/api/v1/reports/{report.id}")
        status_response = client.get(f"/api/v1/reports/{report.id}/status")

    assert detail_response.status_code == 202
    assert detail_response.json()["status"] == "processing"
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "processing"


def test_cancel_analysis_returns_not_found_without_active_task(
    personal_runtime: FileCache,
) -> None:
    app = create_app()

    with TestClient(app) as client:
        response = client.delete(
            "/api/v1/reports/missing-report/cancel",
            headers={"X-Requested-With": "IdeaGo"},
        )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ANALYSIS_NOT_FOUND"


def test_mutating_routes_require_csrf_header(personal_runtime: FileCache) -> None:
    app = create_app()

    with TestClient(app) as client:
        response = client.post("/api/v1/analyze", json={"query": "test idea"})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_MISSING_HEADER"


def test_health_endpoint_includes_content_security_policy(
    personal_runtime: FileCache,
) -> None:
    app = create_app()

    with TestClient(app) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert "Content-Security-Policy" in response.headers
    assert "default-src 'self'" in response.headers["Content-Security-Policy"]


def test_report_rate_limits_use_separate_buckets(
    personal_runtime: FileCache, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RATE_LIMIT_REPORTS_MAX", "1")
    monkeypatch.setenv("RATE_LIMIT_REPORTS_WINDOW_SECONDS", "60")
    reload_settings()
    app_module._rate_limit_store.clear()

    report = _make_report("bucket-key", "bucket idea")
    personal_runtime._put_sync(report)
    app = create_app()

    with TestClient(app) as client:
        list_response = client.get("/api/v1/reports")
        status_response = client.get(f"/api/v1/reports/{report.id}/status")
        delete_response = client.delete(
            f"/api/v1/reports/{report.id}",
            headers={"X-Requested-With": "IdeaGo"},
        )

    assert list_response.status_code == 200
    assert status_response.status_code == 200
    assert delete_response.status_code == 200


def test_report_rate_limits_are_isolated_by_session_id(
    personal_runtime: FileCache, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RATE_LIMIT_REPORTS_MAX", "1")
    monkeypatch.setenv("RATE_LIMIT_REPORTS_WINDOW_SECONDS", "60")
    reload_settings()
    app_module._rate_limit_store.clear()

    report = _make_report("session-key", "session idea")
    personal_runtime._put_sync(report)
    app = create_app()

    with TestClient(app) as client:
        first = client.get("/api/v1/reports", headers={"X-Session-Id": "session-a"})
        second = client.get("/api/v1/reports", headers={"X-Session-Id": "session-b"})

    assert first.status_code == 200
    assert second.status_code == 200
