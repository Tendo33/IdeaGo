"""Tests for json_utils module.

测试 JSON 工具函数模块。
"""

import contextlib
import json
from io import StringIO
from pathlib import Path

import pytest

from ideago.utils import decorator_utils
from ideago.utils.json_utils import (
    async_load_json_batch,
    async_merge_json_files,
    async_read_json,
    async_write_json,
    json_path_get,
    merge_json_files,
    pretty_print_json,
    read_json,
    safe_json_dumps,
    safe_json_loads,
    validate_json_schema,
    write_json,
)


class TestReadJson:
    """Tests for read_json function."""

    def test_read_json_valid(self, temp_json_file: Path) -> None:
        """Test reading valid JSON file."""
        data = read_json(temp_json_file)
        assert data is not None
        assert data["name"] == "test"
        assert data["value"] == 123

    def test_read_json_nested(self, temp_json_file: Path) -> None:
        """Test reading nested JSON data."""
        data = read_json(temp_json_file)
        assert data is not None
        assert data["nested"]["key"] == "value"

    def test_read_json_nonexistent(self, temp_dir: Path) -> None:
        """Test reading nonexistent file returns None."""
        result = read_json(temp_dir / "nonexistent.json")
        assert result is None

    def test_read_json_invalid_content(self, temp_dir: Path) -> None:
        """Test reading invalid JSON returns None."""
        invalid_file = temp_dir / "invalid.json"
        invalid_file.write_text("{ invalid json }", encoding="utf-8")
        result = read_json(invalid_file)
        assert result is None

    def test_read_json_logs_timing(self, temp_json_file: Path, monkeypatch) -> None:
        """Test read_json emits timing log."""
        debug_messages: list[str] = []
        monkeypatch.setattr(decorator_utils.logger, "debug", debug_messages.append)

        result = read_json(temp_json_file)
        assert result is not None
        assert any("read_json took" in message for message in debug_messages)


class TestWriteJson:
    """Tests for write_json function."""

    def test_write_json_basic(self, temp_dir: Path) -> None:
        """Test writing JSON file."""
        file_path = temp_dir / "output.json"
        data = {"key": "value", "number": 42}
        result = write_json(data, file_path)
        assert result is True
        assert file_path.exists()

        # Verify content
        content = json.loads(file_path.read_text())
        assert content == data

    def test_write_json_unicode(self, temp_dir: Path) -> None:
        """Test writing JSON with Unicode characters."""
        file_path = temp_dir / "unicode.json"
        data = {"中文": "测试", "emoji": "😀"}
        result = write_json(data, file_path, ensure_ascii=False)
        assert result is True

        content = file_path.read_text(encoding="utf-8")
        assert "中文" in content
        assert "测试" in content

    def test_write_json_creates_dirs(self, temp_dir: Path) -> None:
        """Test write creates parent directories."""
        file_path = temp_dir / "new" / "nested" / "data.json"
        result = write_json({"test": True}, file_path, create_dirs=True)
        assert result is True
        assert file_path.exists()

    def test_write_json_with_indent(self, temp_dir: Path) -> None:
        """Test writing JSON with custom indent."""
        file_path = temp_dir / "indented.json"
        data = {"a": 1, "b": 2}
        write_json(data, file_path, indent=4)

        content = file_path.read_text()
        # Check indentation is present
        assert "    " in content

    def test_write_json_logs_timing(self, temp_dir: Path, monkeypatch) -> None:
        """Test write_json emits timing log."""
        debug_messages: list[str] = []
        monkeypatch.setattr(decorator_utils.logger, "debug", debug_messages.append)

        file_path = temp_dir / "timing.json"
        result = write_json({"key": "value"}, file_path)

        assert result is True
        assert any("write_json took" in message for message in debug_messages)


class TestSafeJsonLoads:
    """Tests for safe_json_loads function."""

    def test_safe_json_loads_valid(self) -> None:
        """Test parsing valid JSON string."""
        json_str = '{"name": "test", "value": 123}'
        result = safe_json_loads(json_str)
        assert result == {"name": "test", "value": 123}

    def test_safe_json_loads_array(self) -> None:
        """Test parsing JSON array."""
        json_str = "[1, 2, 3]"
        result = safe_json_loads(json_str)
        assert result == [1, 2, 3]

    def test_safe_json_loads_invalid(self) -> None:
        """Test parsing invalid JSON returns default."""
        result = safe_json_loads("{ invalid }")
        assert result is None

    def test_safe_json_loads_with_default(self) -> None:
        """Test parsing invalid JSON returns provided default."""
        default = {"status": "error"}
        result = safe_json_loads("{ invalid }", default=default)
        assert result == default

    def test_safe_json_loads_empty_string(self) -> None:
        """Test handling empty string input."""
        result = safe_json_loads("")
        assert result is None

    def test_safe_json_loads_type_error(self) -> None:
        """Test non-string input returns default."""
        assert safe_json_loads(None, default={"bad": True}) == {"bad": True}


class TestSafeJsonDumps:
    """Tests for safe_json_dumps function."""

    def test_safe_json_dumps_dict(self) -> None:
        """Test serializing dictionary."""
        data = {"name": "test", "value": 123}
        json_str = safe_json_dumps(data)
        assert json_str is not None
        assert "test" in json_str
        assert "123" in json_str

    def test_safe_json_dumps_list(self) -> None:
        """Test serializing list."""
        data = [1, 2, 3, "test"]
        # safe_json_dumps defaults to indent=2
        json_str = safe_json_dumps(data, indent=None)
        assert json_str is not None
        assert "[1, 2, 3," in json_str

    def test_safe_json_dumps_unicode(self) -> None:
        """Test serializing with Unicode."""
        data = {"中文": "测试"}
        json_str = safe_json_dumps(data, ensure_ascii=False)
        assert json_str is not None
        assert "中文" in json_str

    def test_safe_json_dumps_with_indent(self) -> None:
        """Test serializing with indentation."""
        data = {"a": 1, "b": 2}
        json_str = safe_json_dumps(data, indent=2)
        assert json_str is not None
        assert "\n" in json_str

    def test_safe_json_dumps_invalid(self) -> None:
        """Test serializing invalid object returns None."""

        class Unserializable:
            pass

        result = safe_json_dumps(Unserializable())
        assert result is None

    def test_safe_json_dumps_with_serializer_default(self) -> None:
        """Test preserving json.dumps default serializer support."""

        class Unserializable:
            def __init__(self, value: str) -> None:
                self.value = value

        result = safe_json_dumps(
            Unserializable("ok"),
            default=lambda obj: {"value": obj.value},
            indent=None,
        )
        assert result == '{"value": "ok"}'

    def test_safe_json_dumps_with_fallback(self) -> None:
        """Test returning fallback value when serialization fails."""

        class Unserializable:
            pass

        result = safe_json_dumps(Unserializable(), fallback="<serialization-failed>")
        assert result == "<serialization-failed>"


class TestMergeJsonFiles:
    """Tests for merge_json_files function."""

    def test_merge_json_files_basic(self, temp_dir: Path) -> None:
        """Test merging multiple JSON files."""
        file1 = temp_dir / "file1.json"
        file2 = temp_dir / "file2.json"

        file1.write_text('{"a": 1, "b": 2}', encoding="utf-8")
        file2.write_text('{"c": 3, "d": 4}', encoding="utf-8")

        result = merge_json_files([file1, file2])
        assert result == {"a": 1, "b": 2, "c": 3, "d": 4}

    def test_merge_json_files_with_output(self, temp_dir: Path) -> None:
        """Test merging with output file."""
        file1 = temp_dir / "file1.json"
        file2 = temp_dir / "file2.json"
        output = temp_dir / "merged.json"

        file1.write_text('{"a": 1}', encoding="utf-8")
        file2.write_text('{"b": 2}', encoding="utf-8")

        result = merge_json_files([file1, file2], output_path=output)
        assert result == {"a": 1, "b": 2}
        assert output.exists()

        merged_content = json.loads(output.read_text())
        assert merged_content == {"a": 1, "b": 2}

    def test_merge_json_files_logs_timing(self, temp_dir: Path, monkeypatch) -> None:
        """Test merge emits timing log."""
        debug_messages: list[str] = []
        monkeypatch.setattr(decorator_utils.logger, "debug", debug_messages.append)

        file1 = temp_dir / "file1.json"
        file2 = temp_dir / "file2.json"
        file1.write_text('{"a": 1}', encoding="utf-8")
        file2.write_text('{"b": 2}', encoding="utf-8")

        result = merge_json_files([file1, file2])
        assert result == {"a": 1, "b": 2}
        assert any("merge_json_files took" in message for message in debug_messages)

    def test_merge_json_files_non_dict_and_write_failure(self, temp_dir: Path) -> None:
        """Test merge skips non-dict payloads and handles output write failures."""
        file1 = temp_dir / "file1.json"
        file2 = temp_dir / "file2.json"
        file1.write_text('{"a": 1}', encoding="utf-8")
        file2.write_text("[1, 2, 3]", encoding="utf-8")

        assert merge_json_files([file1, file2]) == {"a": 1}
        assert merge_json_files([temp_dir / "missing.json"]) is None

        output_dir = temp_dir / "outdir"
        output_dir.mkdir()
        assert merge_json_files([file1], output_path=output_dir) is None


class TestValidateJsonSchema:
    """Tests for validate_json_schema function."""

    def test_validate_json_schema_valid(self) -> None:
        """Test validation with all required keys present."""
        data = {"name": "test", "value": 123, "type": "example"}
        result = validate_json_schema(data, required_keys=["name", "value"])
        assert result is True

    def test_validate_json_schema_missing_keys(self) -> None:
        """Test validation with missing keys."""
        data = {"name": "test"}
        result = validate_json_schema(data, required_keys=["name", "value"])
        assert result is False


class TestJsonPathAndPrettyPrint:
    """Tests for JSON path lookup and pretty printing."""

    def test_json_path_get_success_cases(self) -> None:
        data = {"user": {"items": [{"name": "alpha"}], "age": 10}}
        assert json_path_get(data, "user.items.0.name") == "alpha"
        assert json_path_get(data, "user.age") == 10
        assert json_path_get(data, "user/items/0/name", separator="/") == "alpha"

    def test_json_path_get_failure_cases(self) -> None:
        data = {"user": {"items": [{"name": "alpha"}]}}
        assert json_path_get(data, "user.items.5.name") is None
        assert json_path_get(data, "user.missing") is None
        assert json_path_get(data, "user.items.bad.name") is None

    def test_pretty_print_json_and_fallback(self) -> None:
        stdout = StringIO()
        with contextlib.redirect_stdout(stdout):
            pretty_print_json({"name": "test"})
        assert '"name": "test"' in stdout.getvalue()

        class Unserializable:
            def __str__(self) -> str:
                return "fallback-value"

        stdout = StringIO()
        with contextlib.redirect_stdout(stdout):
            pretty_print_json(Unserializable())
        assert "fallback-value" in stdout.getvalue()


class TestAsyncJsonUtils:
    """Tests for async JSON helpers."""

    @pytest.mark.asyncio
    async def test_async_read_and_write_json(self, temp_dir: Path) -> None:
        file_path = temp_dir / "async.json"
        assert await async_write_json({"a": 1}, file_path) is True
        assert await async_read_json(file_path) == {"a": 1}

    @pytest.mark.asyncio
    async def test_async_read_and_write_json_error_paths(self, temp_dir: Path) -> None:
        missing = temp_dir / "missing.json"
        invalid = temp_dir / "invalid.json"
        invalid.write_text("{ invalid", encoding="utf-8")
        out_dir = temp_dir / "dir"
        out_dir.mkdir()

        class Unserializable:
            pass

        assert await async_read_json(missing) is None
        assert await async_read_json(invalid) is None
        assert await async_write_json(Unserializable(), temp_dir / "bad.json") is False
        assert await async_write_json({"a": 1}, out_dir, create_dirs=False) is False

    @pytest.mark.asyncio
    async def test_async_merge_json_files_and_batch(self, temp_dir: Path) -> None:
        file1 = temp_dir / "file1.json"
        file2 = temp_dir / "file2.json"
        file3 = temp_dir / "file3.json"
        output = temp_dir / "merged.json"

        file1.write_text('{"a": 1}', encoding="utf-8")
        file2.write_text("[1, 2, 3]", encoding="utf-8")
        file3.write_text('{"b": 2}', encoding="utf-8")

        merged = await async_merge_json_files([file1, file2, file3], output_path=output)
        assert merged == {"a": 1, "b": 2}
        assert json.loads(output.read_text(encoding="utf-8")) == {"a": 1, "b": 2}

        assert await async_merge_json_files([temp_dir / "missing.json"]) is None

        batch = await async_load_json_batch(
            [file1, file2, temp_dir / "missing.json"],
            max_concurrency=2,
        )
        assert batch[0] == {"a": 1}
        assert batch[1] == [1, 2, 3]
        assert batch[2] is None
