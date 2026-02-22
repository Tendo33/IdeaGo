"""Tests for context module.

上下文管理工具测试。
"""

import pytest

from python_template.core.context import (
    Context,
    ContextManager,
    async_context_scope,
    clear_global,
    context_scope,
    get_global,
    get_global_context,
    run_in_context,
    set_global,
)

# =============================================================================
# Context 类测试
# =============================================================================


class TestContext:
    """Tests for Context class."""

    def test_context_creation(self) -> None:
        """Test context creation."""
        ctx = Context("test_context")
        assert ctx.name == "test_context"
        assert len(ctx) == 0

    def test_set_and_get(self) -> None:
        """Test setting and getting values."""
        ctx = Context("test_set_get")
        ctx.set("key", "value")
        assert ctx.get("key") == "value"
        ctx.clear()

    def test_get_default(self) -> None:
        """Test getting with default value."""
        ctx = Context("test_default")
        assert ctx.get("missing", default="default") == "default"

    def test_delete(self) -> None:
        """Test deleting values."""
        ctx = Context("test_delete")
        ctx.set("key", "value")
        assert ctx.delete("key") is True
        assert ctx.get("key") is None

    def test_delete_missing(self) -> None:
        """Test deleting missing key."""
        ctx = Context("test_delete_missing")
        assert ctx.delete("missing") is False

    def test_has(self) -> None:
        """Test checking key existence."""
        ctx = Context("test_has")
        ctx.set("key", "value")
        assert ctx.has("key") is True
        assert ctx.has("missing") is False
        ctx.clear()

    def test_clear(self) -> None:
        """Test clearing context."""
        ctx = Context("test_clear")
        ctx.set("key1", "value1")
        ctx.set("key2", "value2")
        ctx.clear()
        assert len(ctx) == 0

    def test_keys_values_items(self) -> None:
        """Test keys, values, items methods."""
        ctx = Context("test_kvi")
        ctx.set("a", 1)
        ctx.set("b", 2)

        assert set(ctx.keys()) == {"a", "b"}
        assert set(ctx.values()) == {1, 2}
        assert set(ctx.items()) == {("a", 1), ("b", 2)}
        ctx.clear()

    def test_update(self) -> None:
        """Test updating context."""
        ctx = Context("test_update")
        ctx.update({"a": 1, "b": 2})
        assert ctx.get("a") == 1
        assert ctx.get("b") == 2
        ctx.clear()

    def test_to_dict(self) -> None:
        """Test converting context to dict."""
        ctx = Context("test_to_dict")
        ctx.set("key", "value")
        result = ctx.to_dict()
        assert result == {"key": "value"}
        ctx.clear()

    def test_contains_operator(self) -> None:
        """Test 'in' operator."""
        ctx = Context("test_contains")
        ctx.set("key", "value")
        assert "key" in ctx
        assert "missing" not in ctx
        ctx.clear()

    def test_bracket_notation(self) -> None:
        """Test bracket notation."""
        ctx = Context("test_bracket")
        ctx["key"] = "value"
        assert ctx["key"] == "value"
        ctx.clear()

    def test_bracket_notation_missing(self) -> None:
        """Test bracket notation with missing key."""
        ctx = Context("test_bracket_missing")
        with pytest.raises(KeyError):
            _ = ctx["missing"]

    def test_del_bracket(self) -> None:
        """Test deleting with bracket notation."""
        ctx = Context("test_del_bracket")
        ctx["key"] = "value"
        del ctx["key"]
        assert "key" not in ctx


# =============================================================================
# ContextManager 类测试
# =============================================================================


class TestContextManager:
    """Tests for ContextManager class."""

    def test_create_context(self) -> None:
        """Test creating context."""
        manager = ContextManager()
        ctx = manager.create_context("test")
        assert ctx.name == "test"

    def test_create_duplicate_context(self) -> None:
        """Test creating duplicate context raises error."""
        manager = ContextManager()
        manager.create_context("test")
        with pytest.raises(ValueError):
            manager.create_context("test")

    def test_get_context(self) -> None:
        """Test getting context."""
        manager = ContextManager()
        manager.create_context("test")
        ctx = manager.get_context("test")
        assert ctx is not None
        assert ctx.name == "test"

    def test_get_or_create_context(self) -> None:
        """Test get_or_create_context."""
        manager = ContextManager()

        # Create new
        ctx1 = manager.get_or_create_context("test")
        assert ctx1.name == "test"

        # Get existing
        ctx2 = manager.get_or_create_context("test")
        assert ctx1 is ctx2

    def test_list_contexts(self) -> None:
        """Test listing contexts."""
        manager = ContextManager()
        manager.create_context("ctx1")
        manager.create_context("ctx2")
        names = manager.list_contexts()
        assert "ctx1" in names
        assert "ctx2" in names


# =============================================================================
# context_scope 测试
# =============================================================================


class TestContextScope:
    """Tests for context_scope function."""

    def test_context_scope_basic(self) -> None:
        """Test basic context scope usage."""
        with context_scope("test_scope", {"key": "value"}) as ctx:
            assert ctx.get("key") == "value"

    def test_context_scope_set_values(self) -> None:
        """Test setting values in context scope."""
        with context_scope("test_scope_set") as ctx:
            ctx.set("key", "value")
            assert ctx.get("key") == "value"


# =============================================================================
# Global context 测试
# =============================================================================


class TestGlobalContext:
    """Tests for global context functions."""

    def test_set_get_global(self) -> None:
        """Test setting and getting global values."""
        set_global("test_key", "test_value")
        assert get_global("test_key") == "test_value"

    def test_get_global_default(self) -> None:
        """Test getting global with default."""
        assert get_global("missing_key", "default") == "default"

    def test_clear_global(self) -> None:
        """Test clearing global values."""
        set_global("test_key_clear", "value")
        clear_global()
        # After clear, all keys should be gone
        assert get_global("test_key_clear") is None

    def test_get_global_context(self) -> None:
        """Test getting global context."""
        ctx = get_global_context()
        assert ctx is not None


# =============================================================================
# run_in_context 测试
# =============================================================================


class TestRunInContext:
    """Tests for run_in_context function."""

    def test_run_in_context(self) -> None:
        """Test running function in context."""

        def func(x: int) -> int:
            return x * 2

        ctx = Context("run_test")
        result = run_in_context(ctx, func, 21)
        assert result == 42

    def test_run_in_context_uses_isolated_target_context(self) -> None:
        """Test run_in_context uses the provided context without ambient globals."""
        clear_global()
        set_global("ambient_key", "ambient-value")

        ctx = Context("isolated_run")
        ctx.set("scoped_key", "scoped-value")

        def func() -> tuple[str | None, str | None]:
            return ctx.get("scoped_key"), get_global("ambient_key")

        scoped_value, ambient_value = run_in_context(ctx, func)
        assert scoped_value == "scoped-value"
        assert ambient_value is None
        assert get_global("ambient_key") == "ambient-value"

        clear_global()


# =============================================================================
# async_context_scope 测试
# =============================================================================


class TestAsyncContextScope:
    """Tests for async_context_scope function."""

    @pytest.mark.asyncio
    async def test_async_context_scope_basic(self) -> None:
        """Test basic async context scope usage."""
        async with async_context_scope("async_test", {"key": "value"}) as ctx:
            assert ctx.get("key") == "value"

    @pytest.mark.asyncio
    async def test_async_context_scope_set_values(self) -> None:
        """Test setting values in async context scope."""
        async with async_context_scope("async_test_set") as ctx:
            ctx.set("key", "value")
            assert ctx.get("key") == "value"
