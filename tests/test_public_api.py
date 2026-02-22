"""Regression tests for public package APIs."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from python_template import utils


def test_models_module_can_be_imported() -> None:
    """`python_template.models` should always be importable."""
    models_module = importlib.import_module("python_template.models")
    assert hasattr(models_module, "BaseModel")
    assert hasattr(models_module, "User")


def test_utils_exposes_logging_setup() -> None:
    """`setup_logging` is documented and must be exported from utils."""
    assert callable(utils.setup_logging)


def test_utils_get_settings_returns_settings_instance() -> None:
    """`get_settings` should return a configured settings object."""
    settings = utils.get_settings()
    assert settings is not None
    assert settings.environment in {"development", "staging", "production"}


def test_read_text_file_supports_default_value(tmp_path: Path) -> None:
    """Missing text files should return provided default."""
    fallback = "fallback-text"
    result = utils.read_text_file(tmp_path / "missing.txt", default=fallback)
    assert result == fallback


def test_read_json_supports_default_value(tmp_path: Path) -> None:
    """Missing JSON files should return provided default."""
    fallback = {"status": "missing"}
    result = utils.read_json(tmp_path / "missing.json", default=fallback)
    assert result == fallback


def test_utils_removed_symbol_raises_import_error() -> None:
    """Removed top-level symbols should no longer be importable from utils."""
    with pytest.raises(ImportError):
        exec("from python_template.utils import retry_decorator")


def test_removed_symbol_remains_available_from_submodule() -> None:
    """Removed top-level symbols are still available via submodules."""
    from python_template.utils.decorator_utils import retry_decorator

    assert callable(retry_decorator)


@pytest.mark.parametrize(
    "module_name",
    [
        "python_template.utils.setting",
        "python_template.utils.context",
        "python_template.utils.protocols",
        "python_template.utils.logger_util",
    ],
)
def test_removed_legacy_utils_modules_raise_import_error(module_name: str) -> None:
    """Legacy utils module paths should be removed in the template."""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module_name)


def test_utils_wildcard_exports_only_core_symbols() -> None:
    """`python_template.utils.__all__` should be the constrained core surface."""
    expected = {
        "get_logger",
        "setup_logging",
        "configure_json_logging",
        "Settings",
        "get_settings",
        "reload_settings",
        "ensure_directory",
        "read_text_file",
        "write_text_file",
        "read_json",
        "write_json",
        "safe_json_loads",
        "safe_json_dumps",
        "get_timestamp",
        "parse_timestamp",
        "format_datetime",
        "parse_datetime",
        "get_current_date",
        "get_current_time",
    }
    assert set(utils.__all__) == expected
