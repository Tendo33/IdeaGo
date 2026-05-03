from __future__ import annotations

from unittest.mock import patch

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from ideago.api.app import create_app
from ideago.api.http_middleware import _CSRF_EXEMPT_PATHS
from ideago.config.settings import Settings


def _dev_settings() -> Settings:
    return Settings(
        _env_file=None,
        environment="development",
        auth_session_secret="test-session-secret-0123456789abcdef",
        frontend_app_url="https://app.example.com",
        cors_allow_origins="*",
        supabase_url="https://example.supabase.co",
        supabase_service_role_key="srk",
    )


def test_create_app_registers_hosted_route_families_and_billing_webhook() -> None:
    settings = _dev_settings()
    with (
        patch("ideago.api.app.get_settings", return_value=settings),
        patch("ideago.api.app._init_sentry"),
    ):
        app = create_app()

    routes = {route.path for route in app.routes if isinstance(route, APIRoute)}

    assert "/api/v1/auth/me" in routes
    assert "/api/v1/analyze" in routes
    assert "/api/v1/reports/{report_id}" in routes
    assert "/api/v1/admin/stats" in routes
    assert "/api/v1/billing/webhook" in routes
    assert "/api/v1/billing/checkout" in routes
    assert "/api/v1/billing/webhook" in _CSRF_EXEMPT_PATHS
    assert "decision-first" in app.description.lower()

    route_map = {
        route.path: route for route in app.routes if isinstance(route, APIRoute)
    }
    assert route_map["/api/v1/billing/checkout"].include_in_schema is False
    assert route_map["/api/v1/billing/portal"].include_in_schema is False
    assert route_map["/api/v1/billing/status"].include_in_schema is False


def test_billing_webhook_is_reachable_and_exempt_from_csrf() -> None:
    settings = _dev_settings()
    with (
        patch("ideago.auth.dependencies.get_settings", return_value=settings),
        patch("ideago.api.dependencies.get_settings", return_value=settings),
        patch("ideago.api.app.get_settings", return_value=settings),
        patch("ideago.api.app._init_sentry"),
        patch("ideago.api.routes.billing.is_configured", return_value=True),
        patch(
            "ideago.api.routes.billing.construct_webhook_event",
            side_effect=ValueError("bad signature"),
        ),
    ):
        app = create_app()
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/billing/webhook",
                content=b"{}",
                headers={"stripe-signature": "invalid"},
            )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "BILLING_INVALID_SIGNATURE"


def test_hidden_billing_routes_return_not_found_before_auth() -> None:
    settings = _dev_settings()
    with (
        patch("ideago.auth.dependencies.get_settings", return_value=settings),
        patch("ideago.api.dependencies.get_settings", return_value=settings),
        patch("ideago.api.app.get_settings", return_value=settings),
        patch("ideago.api.app._init_sentry"),
    ):
        app = create_app()
        with TestClient(app) as client:
            response = client.get("/api/v1/billing/status")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
