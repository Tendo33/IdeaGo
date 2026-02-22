"""Pytest configuration and fixtures for python-template tests.

提供测试所需的通用 fixtures 和配置。
"""

import json
import tempfile
from collections.abc import Generator
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test files.

    创建用于测试的临时目录。
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_file(temp_dir: Path) -> Path:
    """Create a temporary text file.

    创建临时文本文件。
    """
    file_path = temp_dir / "test_file.txt"
    file_path.write_text("Hello, World!\nThis is a test file.", encoding="utf-8")
    return file_path


@pytest.fixture
def temp_json_file(temp_dir: Path) -> Path:
    """Create a temporary JSON file.

    创建临时 JSON 文件。
    """
    file_path = temp_dir / "test_data.json"
    data = {"name": "test", "value": 123, "nested": {"key": "value"}}
    file_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return file_path


@pytest.fixture
def sample_dict() -> dict[str, Any]:
    """Sample dictionary for testing.

    用于测试的示例字典。
    """
    return {
        "name": "test",
        "value": 42,
        "nested": {"level1": {"level2": "deep_value"}},
        "list": [1, 2, 3],
        "empty": None,
    }


@pytest.fixture
def sample_nested_dict() -> dict[str, Any]:
    """Sample nested dictionary for flatten/unflatten tests.

    用于展平/还原测试的嵌套字典。
    """
    return {"a": {"b": {"c": 1}, "d": 2}, "e": 3}


@pytest.fixture
def sample_datetime() -> datetime:
    """Sample datetime for testing.

    用于测试的示例日期时间。
    """
    return datetime(2024, 6, 15, 14, 30, 45)


@pytest.fixture
def sample_list() -> list:
    """Sample list for chunk testing.

    用于分块测试的示例列表。
    """
    return [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
