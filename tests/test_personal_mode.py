from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.routing import APIRoute, iter_route_contexts
from fastapi.testclient import TestClient

from ideago.api import dependencies as deps
from ideago.api.app import create_app
from ideago.config.settings import get_settings, reload_settings


@pytest.fixture
def personal_defaults(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("ENVIRONMENT", "development")
    reload_settings()
    deps._cache = None
    deps._orchestrator = None
    yield
    deps._cache = None
    deps._orchestrator = None
    get_settings.cache_clear()


def test_personal_mode_exposes_only_public_core_routes(
    personal_defaults: None,
) -> None:
    app = create_app()
    # `include_router` results stay nested under a single node in `app.routes`,
    # so the effective prefixed paths only show up through their contexts.
    paths = {
        ctx.path
        for ctx in iter_route_contexts(app.routes)
        if isinstance(ctx.route, APIRoute) and ctx.path.startswith("/api/v1/")
    }

    assert "/api/v1/health" in paths
    assert "/api/v1/analyze" in paths
    assert "/api/v1/reports" in paths
    assert "/api/v1/auth/me" not in paths
    assert "/api/v1/billing/status" not in paths
    assert "/api/v1/admin/stats" not in paths


def test_personal_mode_allows_anonymous_analyze_requests(
    personal_defaults: None,
) -> None:
    app = create_app()

    with TestClient(app, headers={"X-Requested-With": "IdeaGo"}) as client:
        response = client.post(
            "/api/v1/analyze",
            json={"query": "I want to build a markdown notes extension"},
        )

    assert response.status_code == 200
    assert "report_id" in response.json()
