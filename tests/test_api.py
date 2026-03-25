"""Personal-mode API tests."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

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
