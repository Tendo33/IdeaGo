"""Context management for storing runtime values.

This module provides an async-safe context system using contextvars for storing
and managing runtime values. Supports scoped contexts and hierarchical context
management with proper isolation between async tasks.

用于存储运行时值的上下文管理模块，使用 contextvars 实现异步安全。
"""

from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager, contextmanager
from contextvars import Context as ContextRunner
from contextvars import ContextVar
from typing import Any, TypeVar

T = TypeVar("T")

# 全局上下文存储
_context_data: ContextVar[dict[str, Any] | None] = ContextVar(
    "context_data", default=None
)
_named_contexts: ContextVar[dict[str, "Context"] | None] = ContextVar(
    "named_contexts", default=None
)


class Context:
    """Async-safe context for storing runtime values.

    异步安全的运行时值存储上下文。

    This class uses contextvars internally, providing proper isolation between
    different async tasks while maintaining a simple dictionary-like interface.

    该类内部使用 contextvars，在不同异步任务之间提供适当的隔离，
    同时保持简单的类似字典的接口。

    Example:
        >>> ctx = Context()
        >>> ctx.set("user_id", 123)
        >>> ctx.get("user_id")
        123
        >>> ctx.get("missing", "default")
        'default'
    """

    def __init__(self, name: str = "default") -> None:
        """Initialize context.

        初始化上下文。

        Args:
            name: Context name for identification
        """
        self.name = name
        self._data: ContextVar[dict[str, Any] | None] = ContextVar(
            f"context_{name}", default=None
        )

    def _get_data(self) -> dict[str, Any]:
        """获取当前上下文数据。"""
        data = self._data.get()
        if data is None:
            data = {}
            self._data.set(data)
        return data

    def set(self, key: str, value: Any) -> None:
        """Set a value in the context.

        在上下文中设置值。

        Args:
            key: Key to store value under
            value: Value to store
        """
        data = self._get_data().copy()
        data[key] = value
        self._data.set(data)

    def get(self, key: str, default: T | None = None) -> T | None:
        """Get a value from the context.

        从上下文中获取值。

        Args:
            key: Key to retrieve
            default: Default value if key not found

        Returns:
            Value associated with key, or default if not found
        """
        return self._get_data().get(key, default)

    def delete(self, key: str) -> bool:
        """Delete a value from the context.

        从上下文中删除值。

        Args:
            key: Key to delete

        Returns:
            True if key was deleted, False if key didn't exist
        """
        data = self._get_data()
        if key in data:
            new_data = data.copy()
            del new_data[key]
            self._data.set(new_data)
            return True
        return False

    def has(self, key: str) -> bool:
        """Check if a key exists in the context.

        检查键是否存在于上下文中。

        Args:
            key: Key to check

        Returns:
            True if key exists, False otherwise
        """
        return key in self._get_data()

    def clear(self) -> None:
        """Clear all values from the context.

        清除上下文中的所有值。
        """
        self._data.set({})

    def keys(self) -> list[str]:
        """Get all keys in the context.

        获取上下文中的所有键。

        Returns:
            List of all keys
        """
        return list(self._get_data().keys())

    def values(self) -> list[Any]:
        """Get all values in the context.

        获取上下文中的所有值。

        Returns:
            List of all values
        """
        return list(self._get_data().values())

    def items(self) -> list[tuple[str, Any]]:
        """Get all key-value pairs in the context.

        获取上下文中的所有键值对。

        Returns:
            List of (key, value) tuples
        """
        return list(self._get_data().items())

    def update(self, data: dict[str, Any]) -> None:
        """Update context with multiple key-value pairs.

        使用多个键值对更新上下文。

        Args:
            data: Dictionary of key-value pairs to add
        """
        new_data = self._get_data().copy()
        new_data.update(data)
        self._data.set(new_data)

    def to_dict(self) -> dict[str, Any]:
        """Convert context to dictionary.

        将上下文转换为字典。

        Returns:
            Copy of internal data dictionary
        """
        return self._get_data().copy()

    def __len__(self) -> int:
        """Get number of items in context.

        获取上下文中的项目数量。
        """
        return len(self._get_data())

    def __repr__(self) -> str:
        """String representation of context.

        上下文的字符串表示。
        """
        return f"Context(name='{self.name}', items={len(self)})"

    def __contains__(self, key: str) -> bool:
        """Support 'in' operator."""
        return self.has(key)

    def __getitem__(self, key: str) -> Any:
        """Support bracket notation for getting values."""
        value = self.get(key)
        if value is None and key not in self._get_data():
            raise KeyError(key)
        return value

    def __setitem__(self, key: str, value: Any) -> None:
        """Support bracket notation for setting values."""
        self.set(key, value)

    def __delitem__(self, key: str) -> None:
        """Support bracket notation for deleting values."""
        if not self.delete(key):
            raise KeyError(key)


class ContextManager:
    """Manager for multiple context scopes.

    多上下文作用域管理器。

    This class manages multiple named contexts and provides utilities for
    working with scoped contexts.

    该类管理多个命名上下文并提供用于处理作用域上下文的工具。

    Example:
        >>> manager = ContextManager()
        >>> ctx = manager.get_or_create_context("request")
        >>> ctx.set("user", "alice")
        >>> ctx.get("user")
        'alice'
    """

    def __init__(self) -> None:
        """Initialize context manager.

        初始化上下文管理器。
        """
        self._contexts: dict[str, Context] = {}

    def create_context(self, name: str) -> Context:
        """Create a new named context.

        创建新的命名上下文。

        Args:
            name: Name for the new context

        Returns:
            Newly created context

        Raises:
            ValueError: If context with this name already exists
        """
        if name in self._contexts:
            raise ValueError(f"Context '{name}' already exists")
        ctx = Context(name=name)
        self._contexts[name] = ctx
        return ctx

    def get_context(self, name: str) -> Context | None:
        """Get a context by name.

        通过名称获取上下文。

        Args:
            name: Name of context to retrieve

        Returns:
            Context if found, None otherwise
        """
        return self._contexts.get(name)

    def get_or_create_context(self, name: str) -> Context:
        """Get existing context or create new one.

        获取现有上下文或创建新上下文。

        Args:
            name: Name of context

        Returns:
            Existing or newly created context
        """
        if name not in self._contexts:
            self._contexts[name] = Context(name=name)
        return self._contexts[name]

    def delete_context(self, name: str) -> bool:
        """Delete a context by name.

        通过名称删除上下文。

        Args:
            name: Name of context to delete

        Returns:
            True if context was deleted, False if it didn't exist
        """
        if name in self._contexts:
            del self._contexts[name]
            return True
        return False

    def clear_all(self) -> None:
        """Clear all contexts.

        清除所有上下文。
        """
        self._contexts.clear()

    def list_contexts(self) -> list[str]:
        """List all context names.

        列出所有上下文名称。

        Returns:
            List of context names
        """
        return list(self._contexts.keys())


# Global instances / 全局实例
_global_context: Context | None = None
_context_manager: ContextManager | None = None


def get_context(name: str = "global") -> Context:
    """Get or create a global context.

    获取或创建全局上下文。

    Args:
        name: Context name (default: "global")

    Returns:
        Context instance

    Example:
        >>> ctx = get_context()
        >>> ctx.set("app_start_time", time.time())
    """
    global _context_manager
    if _context_manager is None:
        _context_manager = ContextManager()
    return _context_manager.get_or_create_context(name)


def get_global_context() -> Context:
    """Get the global application context.

    获取全局应用上下文。

    Returns:
        Global context instance
    """
    global _global_context
    if _global_context is None:
        _global_context = Context(name="global")
    return _global_context


@contextmanager
def context_scope(
    name: str, initial_data: dict[str, Any] | None = None
) -> Generator[Context, None, None]:
    """Context manager for scoped context operations.

    作用域上下文操作的上下文管理器。

    Creates a temporary context that is automatically cleaned up when exiting
    the scope. Useful for request/session-scoped data.

    创建临时上下文，在退出作用域时自动清理。适用于请求/会话作用域的数据。

    Args:
        name: Name for the scoped context
        initial_data: Optional initial data to populate context

    Yields:
        Context instance for the scope

    Example:
        >>> with context_scope("request", {"user_id": 123}) as ctx:
        ...     ctx.set("action", "login")
        ...     print(ctx.get("user_id"))
        123
        # Context is automatically cleaned up after exiting
    """
    ctx = get_context(name)
    if initial_data:
        ctx.update(initial_data)
    try:
        yield ctx
    finally:
        global _context_manager
        if _context_manager:
            _context_manager.delete_context(name)


@asynccontextmanager
async def async_context_scope(
    name: str, initial_data: dict[str, Any] | None = None
) -> AsyncGenerator[Context, None]:
    """Async context manager for scoped context operations.

    异步作用域上下文操作的上下文管理器。

    Args:
        name: Name for the scoped context
        initial_data: Optional initial data to populate context

    Yields:
        Context instance for the scope

    Example:
        >>> async with async_context_scope("request", {"user_id": 123}) as ctx:
        ...     ctx.set("action", "login")
        ...     print(ctx.get("user_id"))
        123
    """
    ctx = get_context(name)
    if initial_data:
        ctx.update(initial_data)
    try:
        yield ctx
    finally:
        global _context_manager
        if _context_manager:
            _context_manager.delete_context(name)


def run_in_context(ctx: Context, func: Any, *args: Any, **kwargs: Any) -> Any:
    """Run a function with a specific context.

    使用特定上下文运行函数。

    Args:
        ctx: Context to use
        func: Function to run
        *args: Positional arguments
        **kwargs: Keyword arguments

    Returns:
        Function result
    """
    data_snapshot = ctx.to_dict()
    execution_context = ContextRunner()
    execution_context.run(ctx._data.set, data_snapshot)
    return execution_context.run(func, *args, **kwargs)


# Convenience functions / 便捷函数
def set_global(key: str, value: Any) -> None:
    """Set a value in the global context.

    在全局上下文中设置值。

    Args:
        key: Key to store value under
        value: Value to store
    """
    get_global_context().set(key, value)


def get_global(key: str, default: T | None = None) -> T | None:
    """Get a value from the global context.

    从全局上下文中获取值。

    Args:
        key: Key to retrieve
        default: Default value if key not found

    Returns:
        Value associated with key, or default if not found
    """
    return get_global_context().get(key, default)


def clear_global() -> None:
    """Clear the global context.

    清除全局上下文。
    """
    get_global_context().clear()


__all__ = [
    "Context",
    "ContextManager",
    "get_context",
    "get_global_context",
    "context_scope",
    "async_context_scope",
    "run_in_context",
    "set_global",
    "get_global",
    "clear_global",
]
