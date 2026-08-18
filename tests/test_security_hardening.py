"""Security regression tests for hardening applied on 2026-08-18.

Covers the OAuth login-CSRF fix, production docs exposure, and log sanitization.
"""

from __future__ import annotations

import httpx
import jwt
import pytest
from fastapi.testclient import TestClient

from ideago.api import app as app_module
from ideago.api.routes import auth as auth_route
from ideago.auth.session import OAUTH_STATE_COOKIE_NAME
from ideago.auth.supabase_admin import _safe_upstream_detail
from ideago.config import settings as settings_module
from ideago.config.settings import Settings, reload_settings

AUTH_SECRET = "state-binding-test-secret-0123456789"


def _install_settings(monkeypatch, **overrides):
    settings = Settings(
        _env_file=None,
        environment=overrides.pop("environment", "development"),
        auth_session_secret=AUTH_SECRET,
        **overrides,
    )
    monkeypatch.setattr(settings_module, "_settings_override", settings)
    settings_module.get_settings.cache_clear()
    monkeypatch.setattr(app_module, "_init_sentry", lambda _s: None)
    return settings


@pytest.fixture(autouse=True)
def _restore_settings():
    yield
    settings_module.get_settings.cache_clear()
    reload_settings()


class TestOAuthStateBinding:
    """A signed state proves *we* minted it, not that this browser started it.

    Without a browser binding an attacker can mint a state, authorize as
    themselves, then drive a victim's browser through the callback — planting
    the attacker's session cookie in the victim's browser (login CSRF /
    session fixation).
    """

    def test_state_token_carries_only_a_hash_of_the_binding(self, monkeypatch) -> None:
        _install_settings(monkeypatch)
        state, binding = auth_route._build_state_token(
            redirect_to="https://app.test/cb"
        )

        payload = jwt.decode(
            state, AUTH_SECRET, algorithms=["HS256"], audience="ideago-linuxdo-state"
        )

        assert binding not in state, "raw binding must never travel inside the state"
        assert payload["bh"] == auth_route._hash_state_binding(binding)

    def test_binding_matches_only_for_the_issuing_browser(self, monkeypatch) -> None:
        _install_settings(monkeypatch)
        _, binding = auth_route._build_state_token(redirect_to="https://app.test/cb")
        payload = {"bh": auth_route._hash_state_binding(binding)}

        assert auth_route._state_binding_matches(payload, binding) is True
        assert auth_route._state_binding_matches(payload, "attacker-value") is False

    @pytest.mark.parametrize("presented", ["", "   "])
    def test_missing_binding_is_rejected(self, monkeypatch, presented: str) -> None:
        _install_settings(monkeypatch)
        _, binding = auth_route._build_state_token(redirect_to="https://app.test/cb")
        payload = {"bh": auth_route._hash_state_binding(binding)}

        assert auth_route._state_binding_matches(payload, presented) is False

    def test_state_without_binding_hash_is_rejected(self, monkeypatch) -> None:
        """Legacy states minted before this fix must not be accepted."""
        _install_settings(monkeypatch)
        assert (
            auth_route._state_binding_matches({"nonce": "legacy"}, "anything") is False
        )
        assert auth_route._state_binding_matches({}, "anything") is False

    def test_each_start_issues_a_distinct_binding(self, monkeypatch) -> None:
        _install_settings(monkeypatch)
        _, first = auth_route._build_state_token(redirect_to="https://app.test/cb")
        _, second = auth_route._build_state_token(redirect_to="https://app.test/cb")
        assert first != second

    def test_callback_rejects_state_without_matching_cookie(self, monkeypatch) -> None:
        """The end-to-end attack: valid state, wrong browser."""
        _install_settings(
            monkeypatch,
            frontend_app_url="https://app.test",
            linuxdo_client_id="client-id",
            linuxdo_client_secret="client-secret",
        )
        state, _binding = auth_route._build_state_token(
            redirect_to="https://app.test/cb"
        )

        exchanged = False

        async def _must_not_run(**_kwargs):
            nonlocal exchanged
            exchanged = True
            return "token"

        monkeypatch.setattr(auth_route, "_exchange_linuxdo_code", _must_not_run)

        with TestClient(app_module.create_app()) as client:
            # Victim's browser holds no binding cookie for this handshake.
            response = client.get(
                "/api/v1/auth/linuxdo/callback",
                params={"code": "attacker-code", "state": state},
                follow_redirects=False,
            )

        assert response.status_code == 302
        assert "error=linuxdo_auth" in response.headers["location"]
        assert not exchanged, "code exchange must not happen on an unbound state"
        assert OAUTH_STATE_COOKIE_NAME not in response.cookies

    def test_callback_accepts_state_with_matching_cookie(self, monkeypatch) -> None:
        _install_settings(
            monkeypatch,
            frontend_app_url="https://app.test",
            linuxdo_client_id="client-id",
            linuxdo_client_secret="client-secret",
        )
        state, binding = auth_route._build_state_token(
            redirect_to="https://app.test/cb"
        )

        reached_exchange = False

        async def _fake_exchange(**_kwargs):
            nonlocal reached_exchange
            reached_exchange = True
            raise auth_route.HTTPException(status_code=400, detail="stop here")

        monkeypatch.setattr(auth_route, "_exchange_linuxdo_code", _fake_exchange)

        with TestClient(app_module.create_app()) as client:
            client.cookies.set(OAUTH_STATE_COOKIE_NAME, binding)
            client.get(
                "/api/v1/auth/linuxdo/callback",
                params={"code": "code", "state": state},
                follow_redirects=False,
            )

        assert reached_exchange, "a correctly bound state must proceed to exchange"


class TestInteractiveDocsExposure:
    """Docs enumerate every admin/auth/billing route — free recon in production."""

    def test_schema_and_docs_ui_are_absent_in_production(self, monkeypatch) -> None:
        _install_settings(
            monkeypatch,
            environment="production",
            supabase_url="https://p.supabase.co",
            supabase_service_role_key="service-role",
            frontend_app_url="https://app.test",
            cors_allow_origins="https://app.test",
        )
        app = app_module.create_app()

        # No docs routes are registered at all.
        assert app.docs_url is None
        assert app.redoc_url is None
        assert app.openapi_url is None

        with TestClient(app) as client:
            # The schema itself must not be reachable.
            assert client.get("/openapi.json").status_code == 404
            # /docs and /redoc may still return 200 because the SPA catch-all
            # serves index.html for extension-less paths — but the response must
            # be the app shell, never a docs UI that enumerates the API.
            for path in ("/docs", "/redoc"):
                body = client.get(path).text.lower()
                assert "swagger" not in body
                assert "redoc" not in body
                assert "openapi" not in body

    @pytest.mark.parametrize("path", ["/docs", "/openapi.json"])
    def test_available_outside_production(self, monkeypatch, path: str) -> None:
        _install_settings(monkeypatch, environment="development")
        with TestClient(app_module.create_app()) as client:
            assert client.get(path).status_code == 200


class TestUpstreamLogSanitization:
    """PostgREST error bodies echo table names, columns and whole profile rows."""

    def test_extracts_only_the_error_code(self) -> None:
        response = httpx.Response(
            400,
            json={
                "code": "42703",
                "message": "column profiles.deletion_pending does not exist",
                "details": "user@example.com",
                "hint": "Perhaps you meant...",
            },
        )
        assert _safe_upstream_detail(response) == "42703"

    def test_never_returns_row_data(self) -> None:
        response = httpx.Response(
            400, json={"message": "duplicate key", "details": "secret@example.com"}
        )
        detail = _safe_upstream_detail(response)
        assert "secret@example.com" not in detail
        assert "duplicate key" not in detail

    def test_handles_non_json_body(self) -> None:
        assert _safe_upstream_detail(httpx.Response(502, text="<html>gateway")) == (
            "unparseable_body"
        )

    def test_handles_non_object_body(self) -> None:
        assert (
            _safe_upstream_detail(httpx.Response(400, json=["a"])) == "non_object_body"
        )

    def test_truncates_long_codes(self) -> None:
        response = httpx.Response(400, json={"code": "x" * 500})
        assert len(_safe_upstream_detail(response)) <= 64
