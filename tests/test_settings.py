"""Tests for settings module."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from ideago.config.settings import Settings, get_settings, reload_settings


def test_get_settings_uses_singleton_cache() -> None:
    """get_settings should return the same cached instance."""
    get_settings.cache_clear()
    first = get_settings()
    second = get_settings()
    assert first is second


def test_reload_settings_supports_custom_env_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """reload_settings should rebuild settings from the provided env file."""
    env_file = tmp_path / ".env.test"
    env_file.write_text(
        "LOG_LEVEL=debug\n"
        "ENVIRONMENT=production\n"
        "OPENAI_BASE_URL=https://openrouter.ai/api/v1\n"
        "AUTH_SESSION_SECRET=test-secret-long-enough\n"
        "SUPABASE_URL=https://test.supabase.co\n"
        "SUPABASE_SERVICE_ROLE_KEY=test-service-role-key\n"
        "FRONTEND_APP_URL=https://example.com\n",
        encoding="utf-8",
    )

    monkeypatch.delenv("ENVIRONMENT", raising=False)
    settings = reload_settings(env_file=env_file)
    assert settings.log_level == "DEBUG"
    assert settings.environment == "production"
    assert settings.openai_base_url == "https://openrouter.ai/api/v1"

    get_settings.cache_clear()


def test_settings_no_longer_include_app_name_or_version_or_debug() -> None:
    """Template settings should only keep environment among runtime mode fields."""
    settings = Settings()
    assert not hasattr(settings, "app_name")
    assert not hasattr(settings, "app_version")
    assert not hasattr(settings, "debug")


def test_settings_environment_validation() -> None:
    """Settings should reject invalid environment values."""
    with pytest.raises(ValidationError):
        Settings(environment="invalid")


def test_langgraph_json_parse_max_retries_default() -> None:
    settings = Settings()
    assert settings.langgraph_json_parse_max_retries == 1


def test_reddit_public_fallback_disabled_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("REDDIT_ENABLE_PUBLIC_FALLBACK", raising=False)
    settings = Settings(_env_file=None)
    assert settings.reddit_enable_public_fallback is False


def test_langgraph_json_parse_max_retries_bounds() -> None:
    with pytest.raises(ValidationError):
        Settings(langgraph_json_parse_max_retries=-1)
    with pytest.raises(ValidationError):
        Settings(langgraph_json_parse_max_retries=4)


def test_source_global_concurrency_default_and_bounds() -> None:
    settings = Settings()
    assert settings.source_global_concurrency == 3

    with pytest.raises(ValidationError):
        Settings(source_global_concurrency=0)
    with pytest.raises(ValidationError):
        Settings(source_global_concurrency=9)


def test_aggregation_timeout_default_and_bounds() -> None:
    settings = Settings()
    assert settings.aggregation_timeout_seconds == 180

    with pytest.raises(ValidationError):
        Settings(aggregation_timeout_seconds=0)
    with pytest.raises(ValidationError):
        Settings(aggregation_timeout_seconds=301)


def test_source_and_extractor_result_caps_defaults_and_bounds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MAX_RESULTS_PER_SOURCE", raising=False)
    monkeypatch.delenv("EXTRACTOR_MAX_RESULTS_PER_SOURCE", raising=False)
    settings = Settings(_env_file=None)
    assert settings.max_results_per_source == 20
    assert settings.extractor_max_results_per_source == 15

    with pytest.raises(ValidationError):
        Settings(max_results_per_source=0)
    with pytest.raises(ValidationError):
        Settings(extractor_max_results_per_source=0)


def test_source_query_caps_defaults_and_overrides() -> None:
    defaults = Settings().get_source_query_caps()
    assert defaults["github"] >= 1
    assert defaults["tavily"] >= 1

    overridden = Settings(
        source_query_caps='{"github": 2, "tavily": "4", "reddit": 0, "unknown": 9}'
    ).get_source_query_caps()
    assert overridden["github"] == 2
    assert overridden["tavily"] == 4
    assert overridden["reddit"] == defaults["reddit"]
    assert "unknown" not in overridden


def test_query_family_weights_defaults_and_overrides() -> None:
    defaults = Settings().get_query_family_default_weights()
    assert defaults["competitor_discovery"] > 0
    assert defaults["pain_discovery"] > 0

    overridden = Settings(
        query_family_default_weights=(
            '{"pain_discovery": 1.6, "commercial_discovery": "0.5", "bad": "x"}'
        )
    ).get_query_family_default_weights()
    assert overridden["pain_discovery"] == pytest.approx(1.6)
    assert overridden["commercial_discovery"] == pytest.approx(0.5)
    assert "bad" not in overridden


def test_orchestration_profiles_defaults_and_overrides() -> None:
    defaults = Settings().get_orchestration_profiles()
    assert "default" in defaults
    assert defaults["default"]["role_query_budgets"]

    overridden = Settings(
        app_type_orchestration_profiles=(
            '{"mobile":{"role_query_budgets":{"user_feedback":6},'
            '"family_weight_overrides":{"pain_discovery":1.5},'
            '"family_trim_threshold":0.75}}'
        )
    ).get_orchestration_profiles()
    mobile_profile = overridden["mobile"]
    assert mobile_profile["role_query_budgets"]["user_feedback"] == 6
    assert mobile_profile["family_weight_overrides"]["pain_discovery"] == pytest.approx(
        1.5
    )
    assert mobile_profile["family_trim_threshold"] == pytest.approx(0.75)


def test_supabase_jwks_settings_defaults() -> None:
    settings = Settings()
    assert settings.supabase_jwt_audience == "authenticated"
    assert settings.supabase_jwks_cache_ttl_seconds == 300


def test_supabase_jwks_urls_are_derived_from_supabase_url() -> None:
    settings = Settings(supabase_url="https://demo-project.supabase.co")
    assert (
        settings.get_supabase_jwks_url()
        == "https://demo-project.supabase.co/auth/v1/.well-known/jwks.json"
    )
    assert (
        settings.get_supabase_jwt_issuer() == "https://demo-project.supabase.co/auth/v1"
    )


def test_settings_path_and_origin_helpers(tmp_path: Path) -> None:
    relative = Settings(
        log_file="logs/test.log", cors_allow_origins=" https://a.com, https://b.com "
    )
    absolute = Settings(log_file=str(tmp_path / "app.log"), cors_allow_origins="")

    assert relative.get_project_root().name == "IdeaGo"
    assert relative.get_log_file_path().name == "test.log"
    assert absolute.get_log_file_path() == tmp_path / "app.log"
    assert relative.get_cors_allow_origins() == ["https://a.com", "https://b.com"]
    assert absolute.get_cors_allow_origins() == ["*"]
    assert Settings(cors_allow_origins="*").get_cors_allow_origins() == ["*"]


def test_openai_fallback_endpoints_parser() -> None:
    settings = Settings(
        openai_fallback_endpoints=(
            '[{"name":"a","base_url":"https://x","api_key":"k","model":"m","timeout":30},'
            '"skip",{"name":"b"}]'
        )
    )

    assert settings.get_openai_fallback_endpoints() == [
        {
            "name": "a",
            "base_url": "https://x",
            "api_key": "k",
            "model": "m",
            "timeout": 30,
        },
        {
            "name": "b",
            "base_url": None,
            "api_key": None,
            "model": None,
            "timeout": None,
        },
    ]
    assert (
        Settings(openai_fallback_endpoints="not-json").get_openai_fallback_endpoints()
        == []
    )
    assert (
        Settings(openai_fallback_endpoints='{"x":1}').get_openai_fallback_endpoints()
        == []
    )


def test_production_settings_require_critical_fields() -> None:
    with pytest.raises(ValidationError):
        Settings(
            environment="production",
            auth_session_secret="",
            supabase_url="",
            supabase_service_role_key="",
            frontend_app_url="",
        )

    settings = Settings(
        environment="production",
        auth_session_secret="test-session-secret-0123456789abcdef",
        supabase_url="https://example.supabase.co",
        supabase_service_role_key="srk",
        frontend_app_url="https://app.example.com",
    )
    assert settings.environment == "production"
