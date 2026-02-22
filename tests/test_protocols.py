"""Tests for protocols module.

协议接口测试。
"""

from typing import Any

import pytest

from python_template.contracts.protocols import (
    AsyncCloseable,
    AsyncFileReader,
    AsyncFileWriter,
    Closeable,
    Configurable,
    FileReader,
    FileWriter,
    Serializable,
)

# =============================================================================
# 测试实现类
# =============================================================================


class MockSerializableImpl:
    """A mock implementation of Serializable protocol."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def to_dict(self) -> dict[str, Any]:
        return self._data.copy()


class MockFileReaderImpl:
    """A mock implementation of FileReader protocol."""

    def __init__(self, content: str) -> None:
        self._content = content

    def read(self, path: str) -> str:
        return self._content


class MockAsyncFileReaderImpl:
    """A mock implementation of AsyncFileReader protocol."""

    def __init__(self, content: str) -> None:
        self._content = content

    async def read(self, path: str) -> str:
        return self._content


class MockFileWriterImpl:
    """A mock implementation of FileWriter protocol."""

    def __init__(self) -> None:
        self.written: dict[str, str] = {}

    def write(self, path: str, content: str) -> bool:
        self.written[path] = content
        return True


class MockAsyncFileWriterImpl:
    """A mock implementation of AsyncFileWriter protocol."""

    def __init__(self) -> None:
        self.written: dict[str, str] = {}

    async def write(self, path: str, content: str) -> bool:
        self.written[path] = content
        return True


class MockCloseableImpl:
    """A mock implementation of Closeable protocol."""

    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class MockAsyncCloseableImpl:
    """A mock implementation of AsyncCloseable protocol."""

    def __init__(self) -> None:
        self.closed = False

    async def close(self) -> None:
        self.closed = True


class MockConfigurableImpl:
    """A mock implementation of Configurable protocol."""

    def __init__(self) -> None:
        self.config: dict[str, Any] = {}

    def configure(self, **kwargs: Any) -> None:
        self.config.update(kwargs)


# =============================================================================
# Serializable 协议测试
# =============================================================================


class TestSerializableProtocol:
    """Tests for Serializable protocol."""

    def test_isinstance_check(self) -> None:
        """Test isinstance check works for Serializable."""
        impl = MockSerializableImpl({"key": "value"})
        assert isinstance(impl, Serializable)

    def test_to_dict(self) -> None:
        """Test to_dict method."""
        data = {"name": "test", "value": 42}
        impl = MockSerializableImpl(data)
        result = impl.to_dict()
        assert result == data

    def test_non_implementation(self) -> None:
        """Test non-implementation is not Serializable."""

        class NotSerializable:
            pass

        assert not isinstance(NotSerializable(), Serializable)


# =============================================================================
# FileReader/FileWriter 协议测试
# =============================================================================


class TestFileReaderProtocol:
    """Tests for FileReader protocol."""

    def test_isinstance_check(self) -> None:
        """Test isinstance check works for FileReader."""
        impl = MockFileReaderImpl("content")
        assert isinstance(impl, FileReader)

    def test_read(self) -> None:
        """Test read method."""
        impl = MockFileReaderImpl("Hello World")
        result = impl.read("/path/to/file")
        assert result == "Hello World"


class TestAsyncFileReaderProtocol:
    """Tests for AsyncFileReader protocol."""

    def test_isinstance_check(self) -> None:
        """Test isinstance check works for AsyncFileReader."""
        impl = MockAsyncFileReaderImpl("content")
        assert isinstance(impl, AsyncFileReader)

    @pytest.mark.asyncio
    async def test_read(self) -> None:
        """Test async read method."""
        impl = MockAsyncFileReaderImpl("Async Content")
        result = await impl.read("/path/to/file")
        assert result == "Async Content"


class TestFileWriterProtocol:
    """Tests for FileWriter protocol."""

    def test_isinstance_check(self) -> None:
        """Test isinstance check works for FileWriter."""
        impl = MockFileWriterImpl()
        assert isinstance(impl, FileWriter)

    def test_write(self) -> None:
        """Test write method."""
        impl = MockFileWriterImpl()
        result = impl.write("/path/to/file", "content")
        assert result is True
        assert impl.written["/path/to/file"] == "content"


class TestAsyncFileWriterProtocol:
    """Tests for AsyncFileWriter protocol."""

    def test_isinstance_check(self) -> None:
        """Test isinstance check works for AsyncFileWriter."""
        impl = MockAsyncFileWriterImpl()
        assert isinstance(impl, AsyncFileWriter)

    @pytest.mark.asyncio
    async def test_write(self) -> None:
        """Test async write method."""
        impl = MockAsyncFileWriterImpl()
        result = await impl.write("/path/to/file", "async content")
        assert result is True
        assert impl.written["/path/to/file"] == "async content"


# =============================================================================
# Closeable 协议测试
# =============================================================================


class TestCloseableProtocol:
    """Tests for Closeable protocol."""

    def test_isinstance_check(self) -> None:
        """Test isinstance check works for Closeable."""
        impl = MockCloseableImpl()
        assert isinstance(impl, Closeable)

    def test_close(self) -> None:
        """Test close method."""
        impl = MockCloseableImpl()
        assert impl.closed is False
        impl.close()
        assert impl.closed is True


class TestAsyncCloseableProtocol:
    """Tests for AsyncCloseable protocol."""

    def test_isinstance_check(self) -> None:
        """Test isinstance check works for AsyncCloseable."""
        impl = MockAsyncCloseableImpl()
        assert isinstance(impl, AsyncCloseable)

    @pytest.mark.asyncio
    async def test_close(self) -> None:
        """Test async close method."""
        impl = MockAsyncCloseableImpl()
        assert impl.closed is False
        await impl.close()
        assert impl.closed is True


# =============================================================================
# Configurable 协议测试
# =============================================================================


class TestConfigurableProtocol:
    """Tests for Configurable protocol."""

    def test_isinstance_check(self) -> None:
        """Test isinstance check works for Configurable."""
        impl = MockConfigurableImpl()
        assert isinstance(impl, Configurable)

    def test_configure(self) -> None:
        """Test configure method."""
        impl = MockConfigurableImpl()
        impl.configure(option1="value1", option2=42)
        assert impl.config == {"option1": "value1", "option2": 42}

    def test_configure_multiple_calls(self) -> None:
        """Test multiple configure calls."""
        impl = MockConfigurableImpl()
        impl.configure(a=1)
        impl.configure(b=2)
        assert impl.config == {"a": 1, "b": 2}
