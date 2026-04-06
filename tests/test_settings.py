"""Tests for personal-deployment settings."""

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
        "OPENAI_API_KEY=test-openai-key\n"
        "OPENAI_BASE_URL=https://openrouter.ai/api/v1\n"
        "CACHE_DIR=.cache/ideago-personal\n",
        encoding="utf-8",
    )

    monkeypatch.delenv("ENVIRONMENT", raising=False)
    settings = reload_settings(env_file=env_file)
    assert settings.log_level == "DEBUG"
    assert settings.environment == "production"
    assert settings.openai_api_key == "test-openai-key"
    assert settings.openai_base_url == "https://openrouter.ai/api/v1"
    assert settings.cache_dir == ".cache/ideago-personal"

    get_settings.cache_clear()


def test_settings_no_longer_include_saas_fields() -> None:
    """main branch settings should not expose SaaS runtime knobs."""
    settings = Settings()
    assert not hasattr(settings, "supabase_url")
    assert not hasattr(settings, "stripe_secret_key")
    assert not hasattr(settings, "linuxdo_client_id")
    assert not hasattr(settings, "auth_session_secret")


def test_settings_environment_validation() -> None:
    """Settings should reject invalid environment values."""
    with pytest.raises(ValidationError):
        Settings(environment="invalid")


def test_langgraph_json_parse_max_retries_default() -> None:
    settings = Settings()
    assert settings.langgraph_json_parse_max_retries == 1


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


def test_extractor_max_results_per_source_default_and_bounds() -> None:
    settings = Settings()
    assert settings.extractor_max_results_per_source == 10

    with pytest.raises(ValidationError):
        Settings(extractor_max_results_per_source=0)
    with pytest.raises(ValidationError):
        Settings(extractor_max_results_per_source=51)


def test_aggregation_timeout_seconds_default_and_bounds() -> None:
    settings = Settings()
    assert settings.aggregation_timeout_seconds == 180

    with pytest.raises(ValidationError):
        Settings(aggregation_timeout_seconds=0)
    with pytest.raises(ValidationError):
        Settings(aggregation_timeout_seconds=301)


def test_personal_mode_cache_defaults() -> None:
    settings = Settings()
    assert settings.cache_dir == ".cache/ideago"
    assert settings.anonymous_cache_ttl_hours == 24
    assert settings.file_cache_max_entries == 500
    assert settings.langgraph_checkpoint_db_path.endswith("langgraph-checkpoints.db")


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


def test_settings_path_and_origin_helpers(tmp_path: Path) -> None:
    relative = Settings(
        log_file="logs/test.log", cors_allow_origins=" https://a.com, https://b.com "
    )
    absolute = Settings(log_file=str(tmp_path / "app.log"), cors_allow_origins="")
    project_root = relative.get_project_root()

    assert (project_root / "pyproject.toml").exists()
    assert (project_root / "src").exists()
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


def test_production_settings_require_openai_api_key() -> None:
    with pytest.raises(ValidationError):
        Settings(environment="production", openai_api_key="")

    settings = Settings(environment="production", openai_api_key="test-openai-key")
    assert settings.environment == "production"


def test_runtime_dependencies_pin_requests_to_patched_version() -> None:
    """Runtime deps should require a non-vulnerable requests release."""
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    pyproject_text = pyproject_path.read_text(encoding="utf-8")

    assert '"requests>=2.33.0",' in pyproject_text
