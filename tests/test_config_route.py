"""Tests for the public runtime-config endpoint.

Guards the fix for published Docker images shipping an unusable login: public
frontend config must be served at runtime, and must never leak secrets.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from ideago.api import app as app_module
from ideago.api.app import create_app
from ideago.api.routes.config import PublicConfig, build_public_config
from ideago.config import settings as settings_module
from ideago.config.settings import Settings, reload_settings

SECRET_VALUES = {
    "supabase_service_role_key": "service-role-must-not-leak",
    "auth_session_secret": "session-secret-must-not-leak",
    "turnstile_secret_key": "turnstile-secret-must-not-leak",
    "stripe_secret_key": "stripe-secret-must-not-leak",
    "stripe_webhook_secret": "webhook-secret-must-not-leak",
    "openai_api_key": "openai-key-must-not-leak",
    "tavily_api_key": "tavily-key-must-not-leak",
    "github_token": "github-token-must-not-leak",
    "reddit_client_secret": "reddit-secret-must-not-leak",
    "linuxdo_client_secret": "linuxdo-secret-must-not-leak",
    "supabase_db_url": "postgresql://must-not-leak",
    "sentry_dsn": "https://backend-dsn-must-not-leak@sentry.io/1",
}

PUBLIC_VALUES = {
    "supabase_url": "https://project.supabase.co",
    "supabase_anon_key": "anon-key-is-public",
    "turnstile_site_key": "turnstile-site-key-is-public",
    "frontend_sentry_dsn": "https://frontend@sentry.io/2",
    "pricing_enabled": True,
    "environment": "staging",
}


@pytest.fixture
def configured_client(monkeypatch):
    settings = Settings(_env_file=None, **SECRET_VALUES, **PUBLIC_VALUES)
    monkeypatch.setattr(settings_module, "_settings_override", settings)
    settings_module.get_settings.cache_clear()
    # SECRET_VALUES carries a DSN-shaped sentry_dsn so the leak test has something
    # to look for; stub the initializer so the suite never opens a real transport.
    monkeypatch.setattr(app_module, "_init_sentry", lambda _settings: None)
    with TestClient(create_app()) as client:
        yield client
    settings_module.get_settings.cache_clear()
    reload_settings()


def test_returns_public_values(configured_client) -> None:
    response = configured_client.get("/api/v1/config")

    assert response.status_code == 200
    assert response.json() == {
        "supabase_url": "https://project.supabase.co",
        "supabase_anon_key": "anon-key-is-public",
        "turnstile_site_key": "turnstile-site-key-is-public",
        "sentry_dsn": "https://frontend@sentry.io/2",
        "pricing_enabled": True,
        "environment": "staging",
    }


def test_never_leaks_secrets(configured_client) -> None:
    """The allowlist must hold even as new settings fields are added."""
    body = configured_client.get("/api/v1/config").text

    for field, secret in SECRET_VALUES.items():
        assert secret not in body, f"{field} leaked through /api/v1/config"


def test_response_field_set_is_locked_down() -> None:
    """A new field here is world-readable — make adding one a deliberate act."""
    assert set(PublicConfig.model_fields) == {
        "supabase_url",
        "supabase_anon_key",
        "turnstile_site_key",
        "sentry_dsn",
        "pricing_enabled",
        "environment",
    }


def test_is_cacheable(configured_client) -> None:
    response = configured_client.get("/api/v1/config")
    assert response.headers["cache-control"] == "public, max-age=60"


def test_requires_no_authentication(configured_client) -> None:
    """Every value is already public; requiring auth would deadlock bootstrap."""
    response = configured_client.get("/api/v1/config", headers={})
    assert response.status_code == 200


def test_unconfigured_deployment_returns_empty_strings(monkeypatch) -> None:
    """Frontend degrades explicitly rather than seeing nulls or a 500."""
    settings = Settings(_env_file=None, environment="development")
    monkeypatch.setattr(settings_module, "_settings_override", settings)
    settings_module.get_settings.cache_clear()

    config = build_public_config()

    assert config.supabase_url == ""
    assert config.supabase_anon_key == ""
    assert config.turnstile_site_key == ""
    assert config.sentry_dsn == ""
    assert config.pricing_enabled is False

    settings_module.get_settings.cache_clear()
    reload_settings()


def test_values_are_trimmed(monkeypatch) -> None:
    settings = Settings(
        _env_file=None,
        environment="development",
        supabase_url="  https://padded.supabase.co  ",
        turnstile_site_key="  padded-site-key  ",
    )
    monkeypatch.setattr(settings_module, "_settings_override", settings)
    settings_module.get_settings.cache_clear()

    config = build_public_config()

    assert config.supabase_url == "https://padded.supabase.co"
    assert config.turnstile_site_key == "padded-site-key"

    settings_module.get_settings.cache_clear()
    reload_settings()
