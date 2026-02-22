"""Tests for async utility functions.

测试异步工具函数。
"""

import json
import tempfile
from pathlib import Path

import pytest

from python_template.utils.common_utils import (
    async_batch_process,
    async_batch_process_concurrent,
    async_retry_on_exception,
)
from python_template.utils.file_utils import (
    async_calculate_file_hash,
    async_copy_file,
    async_delete_file,
    async_list_files,
    async_move_file,
    async_read_text_file,
    async_write_text_file,
)
from python_template.utils.json_utils import (
    async_load_json_batch,
    async_merge_json_files,
    async_read_json,
    async_write_json,
)


@pytest.fixture
def async_temp_dir():
    """Create a temporary directory for async tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


class TestAsyncFileUtils:
    """Tests for async file utilities."""

    async def test_async_read_write_text_file(self, async_temp_dir: Path) -> None:
        """Test async read and write text file."""
        test_file = async_temp_dir / "test.txt"
        content = "Hello, async world!"

        # Write
        write_result = await async_write_text_file(content, test_file)
        assert write_result == len(content)

        # Read
        read_result = await async_read_text_file(test_file)
        assert read_result == content

    async def test_async_read_nonexistent_file(self) -> None:
        """Test async reading non-existent file returns None."""
        result = await async_read_text_file("/nonexistent/path/file.txt")
        assert result is None

    async def test_async_copy_file(self, async_temp_dir: Path) -> None:
        """Test async file copy."""
        src = async_temp_dir / "source.txt"
        dst = async_temp_dir / "dest.txt"

        # Create source
        src.write_text("copy me")

        # Copy
        result = await async_copy_file(src, dst)
        assert result is not None
        assert dst.exists()
        assert dst.read_text() == "copy me"

    async def test_async_move_file(self, async_temp_dir: Path) -> None:
        """Test async file move."""
        src = async_temp_dir / "to_move.txt"
        dst = async_temp_dir / "moved.txt"

        # Create source
        src.write_text("move me")

        # Move
        result = await async_move_file(src, dst)
        assert result is not None
        assert not src.exists()
        assert dst.exists()
        assert dst.read_text() == "move me"

    async def test_async_delete_file(self, async_temp_dir: Path) -> None:
        """Test async file delete."""
        test_file = async_temp_dir / "to_delete.txt"
        test_file.write_text("delete me")

        result = await async_delete_file(test_file)
        assert result is True
        assert not test_file.exists()

    async def test_async_delete_nonexistent_missing_ok(self) -> None:
        """Test async delete non-existent file with missing_ok."""
        result = await async_delete_file("/nonexistent/file.txt", missing_ok=True)
        assert result is True

    async def test_async_calculate_file_hash(self, async_temp_dir: Path) -> None:
        """Test async file hash calculation."""
        test_file = async_temp_dir / "hash_test.txt"
        test_file.write_text("test content")

        result = await async_calculate_file_hash(test_file, "sha256")
        assert result is not None
        assert len(result) == 64  # SHA256 hex is 64 chars

    async def test_async_list_files(self, async_temp_dir: Path) -> None:
        """Test async listing files."""
        # Create test files
        (async_temp_dir / "file1.txt").write_text("1")
        (async_temp_dir / "file2.txt").write_text("2")
        (async_temp_dir / "file3.py").write_text("3")

        result = await async_list_files(async_temp_dir, "*.txt")
        assert result is not None
        assert len(result) == 2


class TestAsyncJsonUtils:
    """Tests for async JSON utilities."""

    async def test_async_read_write_json(self, async_temp_dir: Path) -> None:
        """Test async read and write JSON."""
        test_file = async_temp_dir / "test.json"
        data = {"name": "test", "value": 123}

        # Write
        write_result = await async_write_json(data, test_file)
        assert write_result is True

        # Read
        read_result = await async_read_json(test_file)
        assert read_result == data

    async def test_async_write_json_returns_false_on_serialize_error(
        self, async_temp_dir: Path
    ) -> None:
        """Test async write JSON returns False when serialization fails."""
        test_file = async_temp_dir / "bad.json"

        class Unserializable:
            pass

        result = await async_write_json(Unserializable(), test_file)
        assert result is False

    async def test_async_merge_json_files(self, async_temp_dir: Path) -> None:
        """Test async merging JSON files."""
        file1 = async_temp_dir / "data1.json"
        file2 = async_temp_dir / "data2.json"
        output = async_temp_dir / "merged.json"

        file1.write_text(json.dumps({"a": 1, "b": 2}))
        file2.write_text(json.dumps({"c": 3, "d": 4}))

        result = await async_merge_json_files([file1, file2], output)
        assert result == {"a": 1, "b": 2, "c": 3, "d": 4}
        assert output.exists()

    async def test_async_load_json_batch(self, async_temp_dir: Path) -> None:
        """Test async batch loading JSON files."""
        files = []
        for i in range(5):
            f = async_temp_dir / f"data{i}.json"
            f.write_text(json.dumps({"index": i}))
            files.append(f)

        results = await async_load_json_batch(files, max_concurrency=3)
        assert len(results) == 5
        for i, result in enumerate(results):
            assert result is not None
            assert result["index"] == i


class TestAsyncBatchProcess:
    """Tests for async batch processing."""

    async def test_async_batch_process(self) -> None:
        """Test async batch processing."""
        items = list(range(10))

        async def process_batch(batch: list[int]) -> int:
            return sum(batch)

        results = await async_batch_process(
            items, batch_size=3, process_func=process_batch
        )
        assert len(results) == 4  # 10 items / 3 per batch = 4 batches
        assert sum(results) == sum(items)

    async def test_async_batch_process_concurrent(self) -> None:
        """Test concurrent async batch processing."""
        items = list(range(20))

        async def process_batch(batch: list[int]) -> int:
            return sum(batch)

        results = await async_batch_process_concurrent(
            items, batch_size=5, process_func=process_batch, max_concurrency=3
        )
        assert len(results) == 4  # 20 items / 5 per batch = 4 batches
        assert sum(results) == sum(items)


class TestAsyncRetryOnException:
    """Tests for async retry on exception."""

    async def test_async_retry_success(self) -> None:
        """Test async retry succeeds on first try."""
        call_count = 0

        async def always_success() -> str:
            nonlocal call_count
            call_count += 1
            return "success"

        result = await async_retry_on_exception(always_success, max_retries=3)
        assert result == "success"
        assert call_count == 1

    async def test_async_retry_eventual_success(self) -> None:
        """Test async retry eventually succeeds."""
        call_count = 0

        async def eventually_success() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Not yet")
            return "success"

        result = await async_retry_on_exception(
            eventually_success, max_retries=3, delay=0.01
        )
        assert result == "success"
        assert call_count == 3

    async def test_async_retry_all_failures(self) -> None:
        """Test async retry gives up after max retries."""

        async def always_fail() -> str:
            raise ValueError("Always fails")

        with pytest.raises(ValueError, match="Always fails"):
            await async_retry_on_exception(always_fail, max_retries=2, delay=0.01)
