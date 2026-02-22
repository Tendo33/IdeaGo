"""Tests for FastAPI application and routes."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from ideago.api.app import create_app
from ideago.cache.file_cache import FileCache, ReportIndex
from ideago.models.research import (
    Competitor,
    Intent,
    Platform,
    ResearchReport,
    SearchQuery,
)


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


def test_health_endpoint(client) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "sources" in data
    assert data["sources"]["hackernews"] is True


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

    asyncio.run(cache.put(report))

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
    mock_cache.get_by_id = AsyncMock(return_value=None)

    with patch("ideago.api.routes.reports.get_cache", return_value=mock_cache):
        response = client.get("/api/v1/reports/nonexistent-id")
    assert response.status_code == 404


def test_list_reports(client) -> None:
    mock_cache = AsyncMock(spec=FileCache)
    mock_cache.list_reports = AsyncMock(
        return_value=[
            ReportIndex(
                report_id="abc",
                query="test idea",
                cache_key="k",
                created_at=datetime.now(timezone.utc),
                competitor_count=3,
            )
        ]
    )

    with patch("ideago.api.routes.reports.get_cache", return_value=mock_cache):
        response = client.get("/api/v1/reports")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["query"] == "test idea"


def test_delete_report(client) -> None:
    mock_cache = AsyncMock(spec=FileCache)
    mock_cache.delete = AsyncMock(return_value=True)

    with patch("ideago.api.routes.reports.get_cache", return_value=mock_cache):
        response = client.delete("/api/v1/reports/some-id")
    assert response.status_code == 200


def test_delete_report_not_found(client) -> None:
    mock_cache = AsyncMock(spec=FileCache)
    mock_cache.delete = AsyncMock(return_value=False)

    with patch("ideago.api.routes.reports.get_cache", return_value=mock_cache):
        response = client.delete("/api/v1/reports/nonexistent")
    assert response.status_code == 404


def test_export_report(client, tmp_path) -> None:
    report = _make_test_report()
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=24)

    import asyncio

    asyncio.run(cache.put(report))

    with patch("ideago.api.routes.reports.get_cache", return_value=cache):
        response = client.get(f"/api/v1/reports/{report.id}/export")
    assert response.status_code == 200
    assert "text/markdown" in response.headers["content-type"]
    assert "Competitor Research Report" in response.text
    assert "TestProduct" in response.text
