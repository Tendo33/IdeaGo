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

import pytest
from fastapi.testclient import TestClient

from ideago.api import app as app_module
from ideago.api import dependencies as deps
from ideago.api.app import create_app
from ideago.api.routes import analyze as analyze_route
from ideago.cache.file_cache import FileCache, ReportIndex
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
    deps.get_processing_reports().clear()
    deps._report_runs.clear()
    for task in list(deps._pipeline_tasks.values()):
        task.cancel()
    deps._pipeline_tasks.clear()
    yield
    app_module._rate_limit_store.clear()
    deps.get_processing_reports().clear()
    deps._report_runs.clear()
    for task in list(deps._pipeline_tasks.values()):
        task.cancel()
    deps._pipeline_tasks.clear()


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
    assert data["sources"]["appstore"] is True


def test_health_endpoint_returns_degraded_when_orchestrator_unavailable(client) -> None:
    with patch(
        "ideago.api.routes.health.get_orchestrator",
        side_effect=RuntimeError("dependency init failed"),
    ):
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["sources"] == {}


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

    async def fake_run_pipeline(_query: str, _report_id: str) -> None:
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
    mock_cache.get_status = AsyncMock(return_value=None)

    with patch("ideago.api.routes.reports.get_cache", return_value=mock_cache):
        response = client.get("/api/v1/reports/nonexistent-id")
    assert response.status_code == 404


def test_get_report_status_complete(client, tmp_path) -> None:
    report = _make_test_report()
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=24)
    asyncio.run(cache.put(report))

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

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "not_found"
    assert payload["report_id"] == "nonexistent-id"


def test_get_report_status_processing_from_runtime_map(client, tmp_path) -> None:
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=24)
    report_id = "processing-report"
    deps.get_processing_reports()["query-hash"] = report_id

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
    mock_cache.list_reports.assert_awaited_once_with(limit=None, offset=0)


def test_list_reports_with_pagination_query_params(client) -> None:
    mock_cache = AsyncMock(spec=FileCache)
    mock_cache.list_reports = AsyncMock(
        return_value=[
            ReportIndex(
                report_id="paginated-id",
                query="paged idea",
                cache_key="k",
                created_at=datetime.now(timezone.utc),
                competitor_count=1,
            )
        ]
    )

    with patch("ideago.api.routes.reports.get_cache", return_value=mock_cache):
        response = client.get("/api/v1/reports?limit=1&offset=20")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["id"] == "paginated-id"
    mock_cache.list_reports.assert_awaited_once_with(limit=1, offset=20)


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
    query = "A cancellable startup research query"
    report_id = "report-cancel"
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=24)
    query_hash = hashlib.sha256(query.encode()).hexdigest()[:16]
    deps.get_processing_reports()[query_hash] = report_id

    class SlowOrchestrator:
        async def run(self, *_args, **_kwargs) -> None:
            await asyncio.sleep(10)

    with (
        patch("ideago.api.routes.analyze.get_cache", return_value=cache),
        patch(
            "ideago.api.routes.analyze.get_orchestrator",
            return_value=SlowOrchestrator(),
        ),
    ):
        task = asyncio.create_task(analyze_route._run_pipeline(query, report_id))
        deps.set_pipeline_task(report_id, task)

        result = await analyze_route.cancel_analysis(report_id)
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
