"""Decorator utilities module.

Provides unified decorator functions that automatically handle synchronous and asynchronous functions.
"""

import asyncio
import functools
import time
import traceback
from collections.abc import Callable, Coroutine
from typing import Any, ParamSpec, TypeVar, cast

from python_template.observability.log_config import get_logger

P = ParamSpec("P")
R = TypeVar("R")
T = TypeVar("T")

logger = get_logger(__name__)


# =============================================================================
# Unified Decorators - Auto-detect Sync/Async
# =============================================================================


def timing(
    func: Callable[P, R] | Callable[P, Coroutine[Any, Any, R]],
) -> Callable[P, R] | Callable[P, Coroutine[Any, Any, R]]:
    """Decorator to measure execution time (auto-detects sync/async).

    Args:
        func: The function to decorate
    """
    if asyncio.iscoroutinefunction(func):
        async_func = cast(Callable[P, Coroutine[Any, Any, R]], func)
        return _async_timing_impl(async_func)
    sync_func = cast(Callable[P, R], func)
    return _sync_timing_impl(sync_func)


def retry(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> Callable[
    [Callable[P, R] | Callable[P, Coroutine[Any, Any, R]]],
    Callable[P, R] | Callable[P, Coroutine[Any, Any, R]],
]:
    """Decorator to retry function execution on failure (auto-detects sync/async).

    Args:
        max_retries: Maximum number of retries
        delay: Initial delay between retries in seconds
        backoff: Multiplier for delay after each retry
        exceptions: Tuple of exceptions to catch
    """

    def decorator(
        func: Callable[P, R] | Callable[P, Coroutine[Any, Any, R]],
    ) -> Callable[P, R] | Callable[P, Coroutine[Any, Any, R]]:
        if asyncio.iscoroutinefunction(func):
            async_func = cast(Callable[P, Coroutine[Any, Any, R]], func)
            return _async_retry_impl(
                async_func, max_retries, delay, backoff, exceptions
            )
        sync_func = cast(Callable[P, R], func)
        return _sync_retry_impl(sync_func, max_retries, delay, backoff, exceptions)

    return decorator


def catch_exceptions(
    default_return: Any = None,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
    reraise: bool = False,
) -> Callable[
    [Callable[P, R] | Callable[P, Coroutine[Any, Any, R]]],
    Callable[P, R] | Callable[P, Coroutine[Any, Any, R]],
]:
    """Decorator to catch exceptions and return default value (auto-detects sync/async).

    Args:
        default_return: Value to return if exception occurs
        exceptions: Tuple of exceptions to catch
        reraise: Whether to re-raise the exception after logging
    """

    def decorator(
        func: Callable[P, R] | Callable[P, Coroutine[Any, Any, R]],
    ) -> Callable[P, R] | Callable[P, Coroutine[Any, Any, R]]:
        if asyncio.iscoroutinefunction(func):
            async_func = cast(Callable[P, Coroutine[Any, Any, R]], func)
            return _async_catch_impl(async_func, default_return, exceptions, reraise)
        sync_func = cast(Callable[P, R], func)
        return _sync_catch_impl(sync_func, default_return, exceptions, reraise)

    return decorator


def log_calls(
    level: str = "DEBUG",
    log_args: bool = True,
    log_result: bool = True,
) -> Callable[
    [Callable[P, R] | Callable[P, Coroutine[Any, Any, R]]],
    Callable[P, R] | Callable[P, Coroutine[Any, Any, R]],
]:
    """Decorator to log function calls (auto-detects sync/async).

    Args:
        level: Log level (DEBUG, INFO, etc.)
        log_args: Whether to log arguments
        log_result: Whether to log result
    """

    def decorator(
        func: Callable[P, R] | Callable[P, Coroutine[Any, Any, R]],
    ) -> Callable[P, R] | Callable[P, Coroutine[Any, Any, R]]:
        if asyncio.iscoroutinefunction(func):
            async_func = cast(Callable[P, Coroutine[Any, Any, R]], func)
            return _async_log_calls_impl(async_func, level, log_args, log_result)
        sync_func = cast(Callable[P, R], func)
        return _sync_log_calls_impl(sync_func, level, log_args, log_result)

    return decorator


# =============================================================================
# Helper Implementations - Sync
# =============================================================================


def _sync_timing_impl(func: Callable[P, R]) -> Callable[P, R]:
    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        logger.debug(f"{func.__name__} took {end_time - start_time:.4f}s")
        return result

    return wrapper


def _sync_retry_impl(
    func: Callable[P, R],
    max_retries: int,
    delay: float,
    backoff: float,
    exceptions: tuple[type[BaseException], ...],
) -> Callable[P, R]:
    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        current_delay = delay
        last_exception: BaseException | None = None

        for attempt in range(max_retries + 1):
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                last_exception = e
                if attempt < max_retries:
                    logger.warning(
                        f"Attempt {attempt + 1}/{max_retries + 1} failed: {e}. Retrying in {current_delay}s"
                    )
                    time.sleep(current_delay)
                    current_delay *= backoff
                else:
                    logger.error(f"All {max_retries + 1} attempts failed")

        if last_exception:
            raise last_exception
        raise RuntimeError("Unexpected state")

    return wrapper


def _sync_catch_impl(
    func: Callable[P, R],
    default_return: Any,
    exceptions: tuple[type[BaseException], ...],
    reraise: bool,
) -> Callable[P, R]:
    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return func(*args, **kwargs)
        except exceptions as e:
            logger.error(f"Error in {func.__name__}: {e}\n{traceback.format_exc()}")
            if reraise:
                raise
            return default_return

    return wrapper


def _sync_log_calls_impl(
    func: Callable[P, R], level: str, log_args: bool, log_result: bool
) -> Callable[P, R]:
    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        if log_args:
            logger.log(
                level, f"Calling {func.__name__} with args={args} kwargs={kwargs}"
            )
        else:
            logger.log(level, f"Calling {func.__name__}")

        result = func(*args, **kwargs)

        if log_result:
            logger.log(level, f"{func.__name__} returned: {result}")
        else:
            logger.log(level, f"{func.__name__} completed")

        return result

    return wrapper


# =============================================================================
# Helper Implementations - Async
# =============================================================================


def _async_timing_impl(
    func: Callable[P, Coroutine[Any, Any, R]],
) -> Callable[P, Coroutine[Any, Any, R]]:
    @functools.wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        start_time = time.perf_counter()
        result = await func(*args, **kwargs)
        end_time = time.perf_counter()
        logger.debug(f"{func.__name__} took {end_time - start_time:.4f}s")
        return result

    return wrapper


def _async_retry_impl(
    func: Callable[P, Coroutine[Any, Any, R]],
    max_retries: int,
    delay: float,
    backoff: float,
    exceptions: tuple[type[BaseException], ...],
) -> Callable[P, Coroutine[Any, Any, R]]:
    @functools.wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        current_delay = delay
        last_exception: BaseException | None = None

        for attempt in range(max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except exceptions as e:
                last_exception = e
                if attempt < max_retries:
                    logger.warning(
                        f"Attempt {attempt + 1}/{max_retries + 1} failed: {e}. Retrying in {current_delay}s"
                    )
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff
                else:
                    logger.error(f"All {max_retries + 1} attempts failed")

        if last_exception:
            raise last_exception
        raise RuntimeError("Unexpected state")

    return wrapper


def _async_catch_impl(
    func: Callable[P, Coroutine[Any, Any, R]],
    default_return: Any,
    exceptions: tuple[type[BaseException], ...],
    reraise: bool,
) -> Callable[P, Coroutine[Any, Any, R]]:
    @functools.wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return await func(*args, **kwargs)
        except exceptions as e:
            logger.error(f"Error in {func.__name__}: {e}\n{traceback.format_exc()}")
            if reraise:
                raise
            return default_return

    return wrapper


def _async_log_calls_impl(
    func: Callable[P, Coroutine[Any, Any, R]],
    level: str,
    log_args: bool,
    log_result: bool,
) -> Callable[P, Coroutine[Any, Any, R]]:
    @functools.wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        if log_args:
            logger.log(
                level, f"Calling {func.__name__} with args={args} kwargs={kwargs}"
            )
        else:
            logger.log(level, f"Calling {func.__name__}")

        result = await func(*args, **kwargs)

        if log_result:
            logger.log(level, f"{func.__name__} returned: {result}")
        else:
            logger.log(level, f"{func.__name__} completed")

        return result

    return wrapper


# =============================================================================
# Other Decorators
# =============================================================================


def deprecated(reason: str = "") -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator to mark a function as deprecated.

    Args:
        reason: Reason for deprecation
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            logger.warning(
                f"DeprecationWarning: {func.__name__} is deprecated. {reason}"
            )
            return func(*args, **kwargs)

        return wrapper

    return decorator


def singleton(cls: type[T]) -> type[T]:
    """Decorator to make a class a singleton.

    Args:
        cls: Class to decorate
    """
    instances: dict[type[T], T] = {}

    @functools.wraps(cls)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]

    return wrapper  # type: ignore


# =============================================================================
# Context Managers as Decorators
# =============================================================================


class ContextTimer:
    """Context manager to measure execution time."""

    def __init__(self, name: str = "Operation"):
        self.name = name
        self.start_time: float = 0
        self._elapsed_time: float | None = None

    @property
    def elapsed_time(self) -> float | None:
        """Get elapsed time in seconds.

        If the timer is still running, returns time since start.
        If the timer has stopped, returns total duration.
        If the timer hasn't started, returns None.
        """
        if self._elapsed_time is not None:
            return self._elapsed_time
        if self.start_time > 0:
            return time.perf_counter() - self.start_time
        return None

    def __enter__(self) -> "ContextTimer":
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, _exc_type: Any, _exc_val: Any, _exc_tb: Any) -> None:
        end_time = time.perf_counter()
        self._elapsed_time = end_time - self.start_time
        logger.debug(f"{self.name} took {self._elapsed_time:.4f}s")


class AsyncContextTimer:
    """Async context manager to measure execution time."""

    def __init__(self, name: str = "Operation"):
        self.name = name
        self.start_time: float = 0
        self._elapsed_time: float | None = None

    @property
    def elapsed_time(self) -> float | None:
        """Get elapsed time in seconds.

        If the timer is still running, returns time since start.
        If the timer has stopped, returns total duration.
        If the timer hasn't started, returns None.
        """
        if self._elapsed_time is not None:
            return self._elapsed_time
        if self.start_time > 0:
            return time.perf_counter() - self.start_time
        return None

    async def __aenter__(self) -> "AsyncContextTimer":
        self.start_time = time.perf_counter()
        return self

    async def __aexit__(self, _exc_type: Any, _exc_val: Any, _exc_tb: Any) -> None:
        end_time = time.perf_counter()
        self._elapsed_time = end_time - self.start_time
        logger.debug(f"{self.name} took {self._elapsed_time:.4f}s")


# Aliases for compatibility
timing_decorator = timing
retry_decorator = retry
async_timing_decorator = timing
async_retry_decorator = retry
async_catch_exceptions = catch_exceptions
async_log_calls = log_calls

__all__ = [
    "timing",
    "retry",
    "catch_exceptions",
    "log_calls",
    "deprecated",
    "singleton",
    "ContextTimer",
    "AsyncContextTimer",
    "timing_decorator",
    "retry_decorator",
    "async_timing_decorator",
    "async_retry_decorator",
    "async_catch_exceptions",
    "async_log_calls",
]
