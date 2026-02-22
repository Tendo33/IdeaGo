"""Tests for decorator_utils module.

测试装饰器工具函数模块。
"""

import time

import pytest

from python_template.utils.decorator_utils import (
    ContextTimer,
    catch_exceptions,
    deprecated,
    log_calls,
    retry_decorator,
    singleton,
    timing_decorator,
)


class TestTimingDecorator:
    """Tests for timing_decorator function."""

    def test_timing_decorator_returns_result(self) -> None:
        """Test that decorated function returns correct result."""

        @timing_decorator
        def add(a: int, b: int) -> int:
            return a + b

        result = add(2, 3)
        assert result == 5

    def test_timing_decorator_preserves_function_name(self) -> None:
        """Test that function name is preserved."""

        @timing_decorator
        def my_function() -> None:
            pass

        assert my_function.__name__ == "my_function"

    def test_timing_decorator_with_exception(self) -> None:
        """Test that exceptions are reraised."""

        @timing_decorator
        def failing_function() -> None:
            raise ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            failing_function()


class TestRetryDecorator:
    """Tests for retry_decorator function."""

    def test_retry_decorator_success_first_try(self) -> None:
        """Test successful execution on first try."""
        call_count = 0

        @retry_decorator(max_retries=3)
        def success_function() -> str:
            nonlocal call_count
            call_count += 1
            return "success"

        result = success_function()
        assert result == "success"
        assert call_count == 1

    def test_retry_decorator_success_after_failures(self) -> None:
        """Test success after some failures."""
        call_count = 0

        @retry_decorator(max_retries=3, delay=0.01)
        def flaky_function() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Fail")
            return "success"

        result = flaky_function()
        assert result == "success"
        assert call_count == 3

    def test_retry_decorator_all_failures(self) -> None:
        """Test exception raised after all retries fail."""

        @retry_decorator(max_retries=2, delay=0.01)
        def always_fails() -> None:
            raise ValueError("Always fails")

        with pytest.raises(ValueError, match="Always fails"):
            always_fails()

    def test_retry_decorator_specific_exceptions(self) -> None:
        """Test that only specified exceptions are retried."""
        call_count = 0

        @retry_decorator(max_retries=3, delay=0.01, exceptions=(ValueError,))
        def specific_error() -> None:
            nonlocal call_count
            call_count += 1
            raise TypeError("Wrong type")

        with pytest.raises(TypeError):
            specific_error()
        assert call_count == 1  # No retry for TypeError


class TestCatchExceptions:
    """Tests for catch_exceptions decorator."""

    def test_catch_exceptions_returns_default(self) -> None:
        """Test that exceptions return default value."""

        @catch_exceptions(default_return="error")
        def failing_function() -> str:
            raise ValueError("Test error")

        result = failing_function()
        assert result == "error"

    def test_catch_exceptions_success(self) -> None:
        """Test that successful execution returns normally."""

        @catch_exceptions(default_return="error")
        def success_function() -> str:
            return "success"

        result = success_function()
        assert result == "success"

    def test_catch_exceptions_reraise(self) -> None:
        """Test that exceptions can be reraised."""

        @catch_exceptions(default_return="error", reraise=True)
        def failing_function() -> str:
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            failing_function()


class TestLogCalls:
    """Tests for log_calls decorator."""

    def test_log_calls_returns_result(self) -> None:
        """Test that decorated function returns correct result."""

        @log_calls()
        def multiply(a: int, b: int) -> int:
            return a * b

        result = multiply(3, 4)
        assert result == 12

    def test_log_calls_preserves_name(self) -> None:
        """Test that function name is preserved."""

        @log_calls()
        def my_func() -> None:
            pass

        assert my_func.__name__ == "my_func"


class TestDeprecated:
    """Tests for deprecated decorator."""

    def test_deprecated_returns_result(self) -> None:
        """Test that deprecated function still works."""

        @deprecated(reason="Use new_function instead")
        def old_function() -> str:
            return "old result"

        result = old_function()
        assert result == "old result"

    def test_deprecated_preserves_name(self) -> None:
        """Test that function name is preserved."""

        @deprecated()
        def legacy_func() -> None:
            pass

        assert legacy_func.__name__ == "legacy_func"


class TestSingleton:
    """Tests for singleton decorator."""

    def test_singleton_same_instance(self) -> None:
        """Test that singleton returns same instance."""

        @singleton
        class MyClass:
            def __init__(self, value: int = 0):
                self.value = value

        instance1 = MyClass(10)
        instance2 = MyClass(20)

        assert instance1 is instance2
        assert instance1.value == 10  # First call's value

    def test_singleton_different_classes(self) -> None:
        """Test that different classes have different singletons."""

        @singleton
        class ClassA:
            pass

        @singleton
        class ClassB:
            pass

        a = ClassA()
        b = ClassB()

        assert a is not b


class TestContextTimer:
    """Tests for ContextTimer class."""

    def test_context_timer_basic(self) -> None:
        """Test basic context timer usage."""
        with ContextTimer("test operation") as timer:
            time.sleep(0.01)

        assert timer.elapsed_time is not None
        assert timer.elapsed_time >= 0.01

    def test_context_timer_name(self) -> None:
        """Test context timer stores name."""
        with ContextTimer("my_operation") as timer:
            pass

        assert timer.name == "my_operation"

    def test_context_timer_elapsed_during_execution(self) -> None:
        """Test elapsed_time during execution."""
        with ContextTimer("running") as timer:
            time.sleep(0.01)
            elapsed = timer.elapsed_time
            assert elapsed is not None
            assert elapsed >= 0.01

    def test_context_timer_with_exception(self) -> None:
        """Test context timer handles exceptions."""
        with pytest.raises(ValueError), ContextTimer("failing") as timer:
            raise ValueError("Test error")

        # Timer should still record elapsed time
        assert timer.elapsed_time is not None
