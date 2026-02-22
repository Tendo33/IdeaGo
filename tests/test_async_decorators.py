"""Tests for async decorators and utilities.

测试异步装饰器的功能。
"""

import asyncio

import pytest

from python_template.utils.decorator_utils import (
    AsyncContextTimer,
    catch_exceptions,
    log_calls,
    retry,
    timing,
)


class TestAsyncTiming:
    """Tests for async timing decorator."""

    async def test_async_timing_returns_result(self) -> None:
        """Test that async decorated function returns correct result."""

        @timing
        async def async_add(a: int, b: int) -> int:
            await asyncio.sleep(0.01)
            return a + b

        result = await async_add(2, 3)
        assert result == 5

    async def test_async_timing_preserves_name(self) -> None:
        """Test that async function name is preserved."""

        @timing
        async def my_async_function() -> None:
            pass

        assert my_async_function.__name__ == "my_async_function"

    async def test_async_timing_with_exception(self) -> None:
        """Test that exceptions are reraised in async timing."""

        @timing
        async def failing_async() -> None:
            raise ValueError("Async error")

        with pytest.raises(ValueError, match="Async error"):
            await failing_async()


class TestAsyncRetry:
    """Tests for async retry decorator."""

    async def test_async_retry_success_first_try(self) -> None:
        """Test async successful execution on first try."""
        call_count = 0

        @retry(max_retries=3)
        async def async_success() -> str:
            nonlocal call_count
            call_count += 1
            return "success"

        result = await async_success()
        assert result == "success"
        assert call_count == 1

    async def test_async_retry_success_after_failures(self) -> None:
        """Test async success after some failures."""
        call_count = 0

        @retry(max_retries=3, delay=0.01)
        async def async_flaky() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Fail")
            return "success"

        result = await async_flaky()
        assert result == "success"
        assert call_count == 3

    async def test_async_retry_all_failures(self) -> None:
        """Test async exception raised after all retries fail."""

        @retry(max_retries=2, delay=0.01)
        async def async_always_fails() -> None:
            raise ValueError("Always fails")

        with pytest.raises(ValueError, match="Always fails"):
            await async_always_fails()


class TestAsyncCatchExceptions:
    """Tests for async catch_exceptions decorator."""

    async def test_async_catch_returns_default(self) -> None:
        """Test that async exceptions return default value."""

        @catch_exceptions(default_return="error")
        async def async_failing() -> str:
            raise ValueError("Test error")

        result = await async_failing()
        assert result == "error"

    async def test_async_catch_success(self) -> None:
        """Test that async successful execution returns normally."""

        @catch_exceptions(default_return="error")
        async def async_success() -> str:
            return "success"

        result = await async_success()
        assert result == "success"


class TestAsyncLogCalls:
    """Tests for async log_calls decorator."""

    async def test_async_log_calls_returns_result(self) -> None:
        """Test that async decorated function returns correct result."""

        @log_calls()
        async def async_multiply(a: int, b: int) -> int:
            return a * b

        result = await async_multiply(3, 4)
        assert result == 12

    async def test_async_log_calls_preserves_name(self) -> None:
        """Test that async function name is preserved."""

        @log_calls()
        async def my_async_func() -> None:
            pass

        assert my_async_func.__name__ == "my_async_func"


class TestAsyncContextTimer:
    """Tests for AsyncContextTimer class."""

    async def test_async_context_timer_basic(self) -> None:
        """Test basic async context timer usage."""
        async with AsyncContextTimer("async operation") as timer:
            await asyncio.sleep(0.01)

        assert timer.elapsed_time is not None
        assert timer.elapsed_time >= 0.01

    async def test_async_context_timer_name(self) -> None:
        """Test async context timer stores name."""
        async with AsyncContextTimer("my_async_operation") as timer:
            pass

        assert timer.name == "my_async_operation"

    async def test_async_context_timer_with_exception(self) -> None:
        """Test async context timer handles exceptions."""
        with pytest.raises(ValueError):
            async with AsyncContextTimer("failing") as timer:
                raise ValueError("Test error")

        assert timer.elapsed_time is not None
