"""Tests for file_utils module.

文件操作工具测试。
"""

from pathlib import Path

from python_template.utils import decorator_utils
from python_template.utils.file_utils import (
    calculate_file_hash,
    copy_file,
    delete_file,
    ensure_directory,
    format_file_size,
    get_file_size,
    list_files,
    move_file,
    read_text_file,
    sanitize_filename,
    write_text_file,
)

# =============================================================================
# ensure_directory 测试
# =============================================================================


class TestEnsureDirectory:
    """Tests for ensure_directory function."""

    def test_create_new_directory(self, temp_dir: Path) -> None:
        """Test creating new directory."""
        new_dir = temp_dir / "new_directory"
        result = ensure_directory(new_dir)
        assert result is not None
        assert new_dir.exists()
        assert new_dir.is_dir()

    def test_existing_directory(self, temp_dir: Path) -> None:
        """Test with existing directory."""
        result = ensure_directory(temp_dir)
        assert result is not None
        assert temp_dir.exists()

    def test_nested_directory(self, temp_dir: Path) -> None:
        """Test creating nested directories."""
        nested = temp_dir / "level1" / "level2" / "level3"
        result = ensure_directory(nested)
        assert result is not None
        assert nested.exists()


# =============================================================================
# get_file_size / format_file_size 测试
# =============================================================================


class TestFileSize:
    """Tests for file size functions."""

    def test_get_file_size(self, temp_file: Path) -> None:
        """Test getting file size."""
        size = get_file_size(temp_file)
        assert size is not None
        assert size > 0

    def test_get_file_size_nonexistent(self, temp_dir: Path) -> None:
        """Test getting size of nonexistent file."""
        result = get_file_size(temp_dir / "nonexistent.txt")
        assert result is None

    def test_format_file_size_bytes(self) -> None:
        """Test formatting file size in bytes."""
        result = format_file_size(100)
        assert "B" in result
        assert "100" in result

    def test_format_file_size_kb(self) -> None:
        """Test formatting file size in KB."""
        result = format_file_size(1024)
        assert "KB" in result

    def test_format_file_size_mb(self) -> None:
        """Test formatting file size in MB."""
        result = format_file_size(1024 * 1024)
        assert "MB" in result

    def test_format_file_size_gb(self) -> None:
        """Test formatting file size in GB."""
        result = format_file_size(1024 * 1024 * 1024)
        assert "GB" in result


# =============================================================================
# calculate_file_hash 测试
# =============================================================================


class TestCalculateFileHash:
    """Tests for calculate_file_hash function."""

    def test_hash_sha256(self, temp_file: Path) -> None:
        """Test SHA256 hash calculation."""
        hash1 = calculate_file_hash(temp_file)
        hash2 = calculate_file_hash(temp_file)
        assert hash1 is not None
        assert hash1 == hash2  # Same file, same hash

    def test_hash_md5(self, temp_file: Path) -> None:
        """Test MD5 hash calculation."""
        result = calculate_file_hash(temp_file, algorithm="md5")
        assert result is not None
        assert len(result) == 32  # MD5 produces 32 hex chars

    def test_hash_sha1(self, temp_file: Path) -> None:
        """Test SHA1 hash calculation."""
        result = calculate_file_hash(temp_file, algorithm="sha1")
        assert result is not None
        assert len(result) == 40  # SHA1 produces 40 hex chars

    def test_hash_nonexistent_file(self, temp_dir: Path) -> None:
        """Test hash of nonexistent file."""
        result = calculate_file_hash(temp_dir / "nonexistent.txt")
        assert result is None

    def test_hash_logs_timing(self, temp_file: Path, monkeypatch) -> None:
        """Test hash calculation emits timing log."""
        debug_messages: list[str] = []

        monkeypatch.setattr(decorator_utils.logger, "debug", debug_messages.append)

        result = calculate_file_hash(temp_file)

        assert result is not None
        assert any("calculate_file_hash took" in message for message in debug_messages)


# =============================================================================
# copy_file / move_file 测试
# =============================================================================


class TestCopyMoveFile:
    """Tests for copy_file and move_file functions."""

    def test_copy_file(self, temp_file: Path, temp_dir: Path) -> None:
        """Test copying file."""
        dest = temp_dir / "copy.txt"
        result = copy_file(temp_file, dest)
        assert result is not None
        assert dest.exists()
        assert temp_file.exists()  # Original still exists
        assert temp_file.read_text() == dest.read_text()

    def test_copy_file_create_dirs(self, temp_file: Path, temp_dir: Path) -> None:
        """Test copying file with directory creation."""
        dest = temp_dir / "subdir" / "copy.txt"
        result = copy_file(temp_file, dest, create_dirs=True)
        assert result is not None
        assert dest.exists()

    def test_copy_file_logs_timing(
        self, temp_file: Path, temp_dir: Path, monkeypatch
    ) -> None:
        """Test copy emits timing log."""
        debug_messages: list[str] = []
        monkeypatch.setattr(decorator_utils.logger, "debug", debug_messages.append)

        dest = temp_dir / "copy_with_timing.txt"
        result = copy_file(temp_file, dest)

        assert result is not None
        assert any("copy_file took" in message for message in debug_messages)

    def test_move_file(self, temp_file: Path, temp_dir: Path) -> None:
        """Test moving file."""
        content = temp_file.read_text()
        dest = temp_dir / "moved.txt"
        result = move_file(temp_file, dest)
        assert result is not None
        assert dest.exists()
        assert not temp_file.exists()  # Original no longer exists
        assert dest.read_text() == content

    def test_move_file_logs_timing(
        self, temp_file: Path, temp_dir: Path, monkeypatch
    ) -> None:
        """Test move emits timing log."""
        debug_messages: list[str] = []
        monkeypatch.setattr(decorator_utils.logger, "debug", debug_messages.append)

        dest = temp_dir / "move_with_timing.txt"
        result = move_file(temp_file, dest)

        assert result is not None
        assert any("move_file took" in message for message in debug_messages)


# =============================================================================
# delete_file 测试
# =============================================================================


class TestDeleteFile:
    """Tests for delete_file function."""

    def test_delete_existing_file(self, temp_file: Path) -> None:
        """Test deleting existing file."""
        assert temp_file.exists()
        result = delete_file(temp_file)
        assert result is True
        assert not temp_file.exists()

    def test_delete_nonexistent_missing_ok(self, temp_dir: Path) -> None:
        """Test deleting nonexistent file with missing_ok=True."""
        result = delete_file(temp_dir / "nonexistent.txt", missing_ok=True)
        assert result is True

    def test_delete_nonexistent_not_ok(self, temp_dir: Path) -> None:
        """Test deleting nonexistent file with missing_ok=False."""
        result = delete_file(temp_dir / "nonexistent.txt", missing_ok=False)
        assert result is False


# =============================================================================
# list_files 测试
# =============================================================================


class TestListFiles:
    """Tests for list_files function."""

    def test_list_all_files(self, temp_dir: Path) -> None:
        """Test listing all files in directory."""
        # Create test files
        (temp_dir / "file1.txt").write_text("content1")
        (temp_dir / "file2.txt").write_text("content2")
        (temp_dir / "file3.py").write_text("content3")

        result = list_files(temp_dir)
        assert result is not None
        assert len(result) == 3

    def test_list_files_with_pattern(self, temp_dir: Path) -> None:
        """Test listing files with pattern."""
        (temp_dir / "file1.txt").write_text("content1")
        (temp_dir / "file2.txt").write_text("content2")
        (temp_dir / "file3.py").write_text("content3")

        result = list_files(temp_dir, pattern="*.txt")
        assert result is not None
        assert len(result) == 2

    def test_list_files_recursive(self, temp_dir: Path) -> None:
        """Test listing files recursively."""
        subdir = temp_dir / "subdir"
        subdir.mkdir()
        (temp_dir / "file1.txt").write_text("content1")
        (subdir / "file2.txt").write_text("content2")

        result = list_files(temp_dir, recursive=True)
        assert result is not None
        assert len(result) == 2

    def test_list_empty_directory(self, temp_dir: Path) -> None:
        """Test listing empty directory."""
        result = list_files(temp_dir)
        assert result is not None
        assert result == []

    def test_list_files_logs_timing(self, temp_dir: Path, monkeypatch) -> None:
        """Test list_files emits timing log."""
        debug_messages: list[str] = []
        monkeypatch.setattr(decorator_utils.logger, "debug", debug_messages.append)

        (temp_dir / "file1.txt").write_text("content1")
        result = list_files(temp_dir)

        assert result is not None
        assert any("list_files took" in message for message in debug_messages)


# =============================================================================
# read_text_file / write_text_file 测试
# =============================================================================


class TestReadWriteTextFile:
    """Tests for read_text_file and write_text_file functions."""

    def test_write_and_read(self, temp_dir: Path) -> None:
        """Test writing and reading text file."""
        file_path = temp_dir / "test.txt"
        content = "Hello, World!\nLine 2"

        write_result = write_text_file(content, file_path)
        assert write_result is not None
        assert write_result == len(content)

        read_result = read_text_file(file_path)
        assert read_result == content

    def test_write_creates_dirs(self, temp_dir: Path) -> None:
        """Test writing creates parent directories."""
        file_path = temp_dir / "subdir" / "deep" / "test.txt"
        result = write_text_file("content", file_path, create_dirs=True)
        assert result is not None
        assert file_path.exists()

    def test_read_nonexistent_returns_none(self, temp_dir: Path) -> None:
        """Test reading nonexistent file returns None."""
        result = read_text_file(temp_dir / "nonexistent.txt")
        assert result is None

    def test_write_unicode(self, temp_dir: Path) -> None:
        """Test writing and reading unicode content."""
        file_path = temp_dir / "unicode.txt"
        content = "你好世界 🌍 日本語"

        write_text_file(content, file_path)
        result = read_text_file(file_path)
        assert result == content


# =============================================================================
# sanitize_filename 测试
# =============================================================================


class TestSanitizeFilename:
    """Tests for sanitize_filename function."""

    def test_sanitize_special_chars(self) -> None:
        """Test sanitizing special characters."""
        result = sanitize_filename("file<>:name.txt")
        assert "<" not in result
        assert ">" not in result
        assert ":" not in result

    def test_sanitize_normal_name(self) -> None:
        """Test sanitizing normal filename."""
        result = sanitize_filename("normal_file.txt")
        assert result == "normal_file.txt"

    def test_sanitize_with_custom_replacement(self) -> None:
        """Test sanitizing with custom replacement character."""
        result = sanitize_filename("file:name.txt", replacement="-")
        assert ":" not in result
        assert "-" in result

    def test_sanitize_empty_string(self) -> None:
        """Test sanitizing empty string."""
        result = sanitize_filename("")
        assert result == ""
