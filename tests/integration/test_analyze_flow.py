"""End-to-end coverage for the analyze lifecycle.

Every existing test mocks one layer at a time. The chain that actually breaks in
production — ``POST /analyze`` → SSE terminal event → ``GET /reports/{id}``
returning a readable report — had no test at all, which is why the frontend grew
three layers of reconciliation polling to paper over an ordering bug.

These tests drive the real FastAPI app with a real ``FileCache`` and a fake
orchestrator, so routing, middleware, ownership checks, SSE framing and status
transitions are all exercised together.
"""

from __future__ import annotations

import asyncio
import json

import jwt
import pytest
from fastapi.testclient import TestClient

from ideago.api import app as app_module
from ideago.api import dependencies as deps
from ideago.api.routes import analyze as analyze_route
from ideago.cache.file_cache import FileCache
from ideago.config import settings as settings_module
from ideago.config.settings import Settings, reload_settings
from ideago.models.research import Intent, Platform, ResearchReport, SearchQuery
from ideago.pipeline.events import EventType, PipelineEvent

AUTH_SECRET = "e2e-analyze-secret-0123456789abcdef"
USER_ID = "6f1c9d70-1111-4222-8333-444455556666"
OTHER_USER_ID = "aaaa1111-2222-4333-8444-555566667777"


def _token(user_id: str = USER_ID) -> str:
    return jwt.encode(
        {"sub": user_id, "email": f"{user_id}@example.com", "aud": "ideago-auth"},
        AUTH_SECRET,
        algorithm="HS256",
    )


def _headers(user_id: str = USER_ID) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_token(user_id)}",
        "X-Requested-With": "IdeaGo",
    }


def _build_report(report_id: str, query: str) -> ResearchReport:
    """A minimally valid report — the pipeline's real output shape."""
    return ResearchReport(
        id=report_id,
        query=query,
        intent=Intent(
            keywords_en=["notes"],
            app_type="web",
            target_scenario="researchers capturing notes",
            search_queries=[SearchQuery(platform=Platform.GITHUB, queries=["notes"])],
            cache_key=f"cache::{query}",
        ),
    )


class _FakeOrchestrator:
    """Emits a realistic event sequence, then persists like the real pipeline."""

    def __init__(self, cache: FileCache, *, fail: bool = False) -> None:
        self._cache = cache
        self._fail = fail
        self.started = asyncio.Event()

    def get_all_sources(self):
        return []

    async def run(
        self, query, callback=None, report_id=None, user_id="", force_refresh=False
    ):
        self.started.set()
        self.force_refresh_seen = force_refresh
        for stage, event_type in (
            ("intent", EventType.INTENT_STARTED),
            ("intent", EventType.INTENT_PARSED),
            ("aggregation", EventType.AGGREGATION_COMPLETED),
        ):
            if callback is not None:
                await callback.on_event(
                    PipelineEvent(type=event_type, stage=stage, message=stage)
                )
            await asyncio.sleep(0)

        if self._fail:
            raise RuntimeError("pipeline exploded")

        report = _build_report(report_id or "r-1", query)
        # Mirrors persist_report_node: report and terminal status are both
        # durable *before* REPORT_READY is emitted.
        await self._cache.put(report, user_id=user_id)
        await self._cache.put_status(
            report.id, "complete", query, message="Report ready", user_id=user_id
        )
        if callback is not None:
            await callback.on_event(
                PipelineEvent(
                    type=EventType.REPORT_READY,
                    stage="complete",
                    message="Report ready",
                    data={"report_id": report.id},
                )
            )
        return report


@pytest.fixture
def e2e(tmp_path, monkeypatch):
    settings = Settings(
        _env_file=None,
        environment="development",
        auth_session_secret=AUTH_SECRET,
        cache_dir=str(tmp_path / "cache"),
    )
    monkeypatch.setattr(settings_module, "_settings_override", settings)
    settings_module.get_settings.cache_clear()
    monkeypatch.setattr(app_module, "_init_sentry", lambda _s: None)

    cache = FileCache(str(tmp_path / "cache"), ttl_hours=24)
    monkeypatch.setattr(deps, "_cache", cache)
    monkeypatch.setattr(analyze_route, "get_cache", lambda: cache)
    monkeypatch.setattr("ideago.api.routes.reports.get_cache", lambda: cache)

    orchestrator = _FakeOrchestrator(cache)
    monkeypatch.setattr(analyze_route, "get_orchestrator", lambda: orchestrator)

    with TestClient(app_module.create_app()) as client:
        yield client, cache, orchestrator

    settings_module.get_settings.cache_clear()
    reload_settings()


def _wait_for_report(client, report_id: str, *, attempts: int = 200):
    """Poll the public status endpoint until the run leaves `processing`."""
    for _ in range(attempts):
        res = client.get(f"/api/v1/reports/{report_id}/status", headers=_headers())
        if res.status_code == 200 and res.json()["status"] != "processing":
            return res.json()
    raise AssertionError("report never reached a terminal state")


def test_analyze_to_readable_report(e2e) -> None:
    """The chain the frontend depends on, end to end."""
    client, _cache, _orchestrator = e2e

    started = client.post(
        "/api/v1/analyze",
        json={"query": "a note taking app for researchers"},
        headers=_headers(),
    )
    assert started.status_code == 200
    report_id = started.json()["report_id"]

    status = _wait_for_report(client, report_id)
    assert status["status"] == "complete"

    # The contract that matters: once status says complete, the report reads.
    detail = client.get(f"/api/v1/reports/{report_id}", headers=_headers())
    assert detail.status_code == 200, (
        "a completed report must be readable immediately — this is exactly the "
        "race the frontend reconciliation loop was built to survive"
    )
    assert detail.json()["id"] == report_id

    listing = client.get("/api/v1/reports", headers=_headers())
    assert listing.status_code == 200
    assert any(item["id"] == report_id for item in listing.json()["items"])


def test_force_refresh_reaches_the_orchestrator(e2e) -> None:
    """The flag has to survive request body -> route -> engine -> graph state."""
    client, _cache, orchestrator = e2e

    started = client.post(
        "/api/v1/analyze",
        json={"query": "an idea worth re-checking", "force_refresh": True},
        headers=_headers(),
    )
    assert started.status_code == 200
    _wait_for_report(client, started.json()["report_id"])

    assert orchestrator.force_refresh_seen is True


def test_analysis_uses_the_cache_by_default(e2e) -> None:
    client, _cache, orchestrator = e2e

    started = client.post(
        "/api/v1/analyze",
        json={"query": "an idea that may reuse evidence"},
        headers=_headers(),
    )
    _wait_for_report(client, started.json()["report_id"])

    assert orchestrator.force_refresh_seen is False


def test_sse_stream_replays_history_and_ends_on_terminal_event(e2e) -> None:
    client, _cache, _orchestrator = e2e

    started = client.post(
        "/api/v1/analyze",
        json={"query": "a habit tracker for teams"},
        headers=_headers(),
    )
    report_id = started.json()["report_id"]
    _wait_for_report(client, report_id)

    with client.stream(
        "GET", f"/api/v1/reports/{report_id}/stream", headers=_headers()
    ) as stream:
        assert stream.status_code == 200
        event_names = []
        for raw in stream.iter_lines():
            if raw.startswith("event:"):
                event_names.append(raw.split(":", 1)[1].strip())
            if event_names and event_names[-1] in {
                EventType.REPORT_READY.value,
                EventType.ERROR.value,
                EventType.CANCELLED.value,
            }:
                break

    assert event_names[-1] == EventType.REPORT_READY.value
    assert EventType.INTENT_STARTED.value in event_names, "history must be replayed"


def test_failed_run_surfaces_as_failed_status_not_a_hang(e2e, monkeypatch) -> None:
    client, cache, _orchestrator = e2e
    monkeypatch.setattr(
        analyze_route, "get_orchestrator", lambda: _FakeOrchestrator(cache, fail=True)
    )

    started = client.post(
        "/api/v1/analyze",
        json={"query": "an idea that will fail to process"},
        headers=_headers(),
    )
    report_id = started.json()["report_id"]

    status = _wait_for_report(client, report_id)
    assert status["status"] == "failed"
    assert status["error_code"] == "PIPELINE_FAILURE"

    detail = client.get(f"/api/v1/reports/{report_id}", headers=_headers())
    assert detail.status_code == 404


def test_another_user_cannot_reach_the_report(e2e) -> None:
    """Ownership is enforced on every read path, not just the list."""
    client, _cache, _orchestrator = e2e

    started = client.post(
        "/api/v1/analyze",
        json={"query": "a private business idea"},
        headers=_headers(),
    )
    report_id = started.json()["report_id"]
    _wait_for_report(client, report_id)

    intruder = _headers(OTHER_USER_ID)
    assert (
        client.get(f"/api/v1/reports/{report_id}", headers=intruder).status_code == 404
    )
    assert (
        client.get(f"/api/v1/reports/{report_id}/export", headers=intruder).status_code
        == 404
    )
    assert (
        client.delete(f"/api/v1/reports/{report_id}", headers=intruder).status_code
        == 404
    )
    assert (
        client.get(f"/api/v1/reports/{report_id}/stream", headers=intruder).status_code
        == 404
    )
    # And the owner is unaffected by the failed attempts.
    assert (
        client.get(f"/api/v1/reports/{report_id}", headers=_headers()).status_code
        == 200
    )


def test_export_returns_markdown_for_the_owner(e2e) -> None:
    client, _cache, _orchestrator = e2e

    started = client.post(
        "/api/v1/analyze",
        json={"query": "a markdown export worth having"},
        headers=_headers(),
    )
    report_id = started.json()["report_id"]
    _wait_for_report(client, report_id)

    exported = client.get(f"/api/v1/reports/{report_id}/export", headers=_headers())
    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("text/markdown")
    assert "# Source Intelligence Report" in exported.text


def test_status_endpoint_reports_not_found_for_unknown_report(e2e) -> None:
    client, _cache, _orchestrator = e2e
    res = client.get("/api/v1/reports/does-not-exist/status", headers=_headers())
    assert res.status_code == 200
    assert res.json()["status"] == "not_found"


class TestMiddlewareContract:
    """Cross-cutting behaviour that only shows up through the real app."""

    def test_mutating_request_without_csrf_header_is_rejected(self, e2e) -> None:
        client, _cache, _orchestrator = e2e
        res = client.post(
            "/api/v1/analyze",
            json={"query": "an idea submitted without the SPA header"},
            headers={"Authorization": f"Bearer {_token()}"},
        )
        assert res.status_code == 403
        assert res.json()["error"]["code"] == "CSRF_MISSING_HEADER"

    def test_short_circuit_responses_still_carry_cors_and_trace_headers(
        self, e2e
    ) -> None:
        client, _cache, _orchestrator = e2e
        origin = "http://localhost:5173"
        res = client.post(
            "/api/v1/analyze",
            json={"query": "an idea submitted cross origin"},
            headers={"Authorization": f"Bearer {_token()}", "Origin": origin},
        )
        assert res.status_code == 403
        assert res.headers["access-control-allow-origin"] == origin
        assert res.headers["x-trace-id"]

    def test_unauthenticated_requests_are_rejected(self, e2e) -> None:
        client, _cache, _orchestrator = e2e
        res = client.post(
            "/api/v1/analyze",
            json={"query": "an idea from nobody"},
            headers={"X-Requested-With": "IdeaGo"},
        )
        assert res.status_code == 401

    def test_security_headers_are_present_on_api_responses(self, e2e) -> None:
        client, _cache, _orchestrator = e2e
        res = client.get("/api/v1/health")
        assert res.headers["X-Content-Type-Options"] == "nosniff"
        assert res.headers["X-Frame-Options"] == "DENY"
        assert "Content-Security-Policy" in res.headers

    def test_caller_supplied_trace_id_is_echoed(self, e2e) -> None:
        client, _cache, _orchestrator = e2e
        res = client.get("/api/v1/health", headers={"X-Trace-Id": "trace-e2e-1"})
        assert res.headers["X-Trace-Id"] == "trace-e2e-1"


def test_report_detail_payload_matches_the_frontend_contract(e2e) -> None:
    """Field set is a cross-layer contract; drift breaks the SPA silently."""
    client, _cache, _orchestrator = e2e

    started = client.post(
        "/api/v1/analyze",
        json={"query": "a contract worth pinning"},
        headers=_headers(),
    )
    report_id = started.json()["report_id"]
    _wait_for_report(client, report_id)

    payload = client.get(f"/api/v1/reports/{report_id}", headers=_headers()).json()

    for field in (
        "id",
        "query",
        "created_at",
        "recommendation_type",
        "pain_signals",
        "commercial_signals",
        "whitespace_opportunities",
        "competitors",
        "evidence_summary",
        "confidence",
        "source_results",
    ):
        assert field in payload, f"report detail lost the `{field}` field"

    assert json.dumps(payload), "detail payload must be JSON serialisable"
