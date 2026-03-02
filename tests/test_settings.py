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


def test_reload_settings_supports_custom_env_file(tmp_path: Path) -> None:
    """reload_settings should rebuild settings from the provided env file."""
    env_file = tmp_path / ".env.test"
    env_file.write_text(
        "LOG_LEVEL=debug\n"
        "ENVIRONMENT=production\n"
        "OPENAI_BASE_URL=https://openrouter.ai/api/v1\n",
        encoding="utf-8",
    )

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


def test_langgraph_json_parse_max_retries_bounds() -> None:
    with pytest.raises(ValidationError):
        Settings(langgraph_json_parse_max_retries=-1)
    with pytest.raises(ValidationError):
        Settings(langgraph_json_parse_max_retries=4)
