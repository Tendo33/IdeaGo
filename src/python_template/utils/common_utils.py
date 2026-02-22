"""Common utility functions module.

Provides shared utilities for list/dict operations, processing, and more.
"""

import asyncio
from collections.abc import Callable, Coroutine, Generator
from typing import Any, TypeVar

from python_template.observability.log_config import get_logger

from .decorator_utils import _async_retry_impl, _sync_retry_impl

logger = get_logger(__name__)

T = TypeVar("T")
R = TypeVar("R")


# =============================================================================
# List Operations
# =============================================================================


def chunk_list(data: list[T], chunk_size: int) -> Generator[list[T], None, None]:
    """Split a list into chunks of specified size.

    Args:
        data: List to chunk
        chunk_size: Size of each chunk

    Yields:
        Chunks of the list
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0")

    for i in range(0, len(data), chunk_size):
        yield data[i : i + chunk_size]


def ensure_list(value: T | list[T] | None) -> list[T]:
    """Ensure value is a list.

    Args:
        value: Value to ensure as list

    Returns:
        List containing value, or value if already list, or empty list if None
    """
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def first_non_none(*args: T | None) -> T | None:
    """Return the first non-None argument.

    Args:
        *args: Arguments to check

    Returns:
        First non-None value or None
    """
    for arg in args:
        if arg is not None:
            return arg
    return None


# =============================================================================
# Dictionary Operations
# =============================================================================


def flatten_dict(
    data: dict[str, Any],
    parent_key: str = "",
    sep: str = ".",
) -> dict[str, Any]:
    """Flatten a nested dictionary.

    Args:
        data: Dictionary to flatten
        parent_key: Key prefix (for recursion)
        sep: Separator for keys

    Returns:
        Flattened dictionary
    """
    items: list[tuple[str, Any]] = []
    for k, v in data.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def unflatten_dict(data: dict[str, Any], sep: str = ".") -> dict[str, Any]:
    """Unflatten a dictionary using separator.

    Args:
        data: Flattened dictionary
        sep: Separator used in keys

    Returns:
        Nested dictionary
    """
    result: dict[str, Any] = {}
    for key, value in data.items():
        parts = key.split(sep)
        d = result
        for part in parts[:-1]:
            d = d.setdefault(part, {})
        d[parts[-1]] = value
    return result


def merge_dicts(dict1: dict[str, Any], dict2: dict[str, Any]) -> dict[str, Any]:
    """Merge two dictionaries deeply.

    Args:
        dict1: First dictionary
        dict2: Second dictionary (overrides first)

    Returns:
        Merged dictionary
    """
    result = dict1.copy()
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_dicts(result[key], value)
        else:
            result[key] = value
    return result


def filter_dict(data: dict[str, Any], keys: list[str]) -> dict[str, Any]:
    """Filter dictionary to keep only specified keys.

    Args:
        data: Dictionary to filter
        keys: Keys to keep

    Returns:
        Filtered dictionary
    """
    return {k: v for k, v in data.items() if k in keys}


def deep_merge_dict(target: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    """Alias for merge_dicts."""
    return merge_dicts(target, source)


def safe_get(data: dict[str, Any], path: str, default: Any = None) -> Any:
    """Safely get nested dictionary value using dot notation."""
    keys = path.split(".")
    current = data
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    return current


def safe_set(data: dict[str, Any], path: str, value: Any, create: bool = True) -> bool:
    """Safely set nested dictionary value using dot notation."""
    keys = path.split(".")
    current = data
    for key in keys[:-1]:
        if key not in current:
            if create:
                current[key] = {}
            else:
                return False
        current = current[key]
        if not isinstance(current, dict):
            return False
    current[keys[-1]] = value
    return True


def remove_none_values(data: dict[str, Any], recursive: bool = True) -> dict[str, Any]:
    """Remove None values from dictionary."""
    result: dict[str, Any] = {}
    for k, v in data.items():
        if v is None:
            continue
        if recursive and isinstance(v, dict):
            result[k] = remove_none_values(v, recursive=True)
        else:
            result[k] = v
    return result


def remove_empty_values(data: dict[str, Any], recursive: bool = True) -> dict[str, Any]:
    """Remove None, empty string, empty list/dict values."""
    result: dict[str, Any] = {}
    for key, value in data.items():
        if value is None or value == "" or value == [] or value == {}:
            continue
        if recursive and isinstance(value, dict):
            processed = remove_empty_values(value, recursive=True)
            if processed:
                result[key] = processed
        else:
            result[key] = value
    return result


# =============================================================================
# Batch Processing
# =============================================================================


def batch_process(
    items: list[T],
    batch_size: int,
    process_func: Callable[[list[T]], R],
    *args: Any,
    **kwargs: Any,
) -> list[R]:
    """Process items in batches."""
    results: list[R] = []
    chunks = chunk_list(items, batch_size)
    for i, chunk in enumerate(chunks):
        logger.debug(f"Processing batch {i + 1} ({len(chunk)} items)")
        result = process_func(chunk, *args, **kwargs)
        results.append(result)
    return results


async def async_batch_process(
    items: list[T],
    batch_size: int,
    process_func: Callable[[list[T]], Coroutine[Any, Any, R]],
    *args: Any,
    **kwargs: Any,
) -> list[R]:
    """Async process items in batches."""
    results: list[R] = []
    chunks = chunk_list(items, batch_size)
    for i, chunk in enumerate(chunks):
        logger.debug(f"Async processing batch {i + 1} ({len(chunk)} items)")
        result = await process_func(chunk, *args, **kwargs)
        results.append(result)
    return results


async def async_batch_process_concurrent(
    items: list[T],
    batch_size: int,
    process_func: Callable[[list[T]], Coroutine[Any, Any, R]],
    max_concurrency: int = 5,
    *args: Any,
    **kwargs: Any,
) -> list[R]:
    """Async process items in batches concurrently."""
    chunks = chunk_list(items, batch_size)
    semaphore = asyncio.Semaphore(max_concurrency)

    async def process_with_semaphore(chunk: list[T], index: int) -> tuple[int, R]:
        async with semaphore:
            logger.debug(f"Concurrent batch {index + 1} start")
            result = await process_func(chunk, *args, **kwargs)
            return index, result

    tasks = [process_with_semaphore(chunk, i) for i, chunk in enumerate(chunks)]
    completed = await asyncio.gather(*tasks)
    sorted_results = sorted(completed, key=lambda x: x[0])
    return [r for _, r in sorted_results]


# =============================================================================
# Retry
# =============================================================================


def retry_on_exception(
    func: Callable[..., R],
    max_retries: int = 3,
    delay: float = 1.0,
    *args: Any,
    **kwargs: Any,
) -> R:
    """Retry function on exception."""
    wrapped = _sync_retry_impl(
        func=func,
        max_retries=max_retries,
        delay=delay,
        backoff=1.0,
        exceptions=(Exception,),
    )
    return wrapped(*args, **kwargs)


async def async_retry_on_exception(
    func: Callable[..., Coroutine[Any, Any, R]],
    max_retries: int = 3,
    delay: float = 1.0,
    *args: Any,
    **kwargs: Any,
) -> R:
    """Async retry function on exception."""
    wrapped = _async_retry_impl(
        func=func,
        max_retries=max_retries,
        delay=delay,
        backoff=1.0,
        exceptions=(Exception,),
    )
    return await wrapped(*args, **kwargs)


# =============================================================================
# Other
# =============================================================================


def generate_uuid() -> str:
    """Generate a UUID4 string."""
    import uuid

    return str(uuid.uuid4())


def clamp(value: float, min_value: float, max_value: float) -> float:
    """Clamp value between min and max."""
    return max(min_value, min(max_value, value))


def validate_email(email: str) -> bool:
    """Validate email format."""
    import re

    EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    return bool(EMAIL_PATTERN.match(email))


__all__ = [
    "chunk_list",
    "flatten_dict",
    "unflatten_dict",
    "merge_dicts",
    "filter_dict",
    "deep_merge_dict",
    "safe_get",
    "safe_set",
    "remove_none_values",
    "remove_empty_values",
    "batch_process",
    "async_batch_process",
    "async_batch_process_concurrent",
    "retry_on_exception",
    "async_retry_on_exception",
    "generate_uuid",
    "clamp",
    "ensure_list",
    "first_non_none",
    "validate_email",
]
