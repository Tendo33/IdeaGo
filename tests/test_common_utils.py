"""Tests for common_utils module.

通用工具函数测试。
"""

from typing import Any

import pytest

from python_template.utils.common_utils import (
    batch_process,
    chunk_list,
    clamp,
    deep_merge_dict,
    ensure_list,
    filter_dict,
    first_non_none,
    flatten_dict,
    generate_uuid,
    merge_dicts,
    remove_empty_values,
    remove_none_values,
    retry_on_exception,
    safe_get,
    safe_set,
    unflatten_dict,
    validate_email,
)

# =============================================================================
# chunk_list 测试
# =============================================================================


class TestChunkList:
    """Tests for chunk_list function."""

    def test_normal_chunks(self, sample_list: list) -> None:
        """Test normal chunking of list."""
        chunks = list(chunk_list(sample_list, 3))
        assert len(chunks) == 4
        assert chunks[0] == [1, 2, 3]
        assert chunks[1] == [4, 5, 6]
        assert chunks[2] == [7, 8, 9]
        assert chunks[3] == [10]

    def test_chunk_size_larger_than_list(self) -> None:
        """Test when chunk size is larger than list."""
        data = [1, 2, 3]
        chunks = list(chunk_list(data, 10))
        assert len(chunks) == 1
        assert chunks[0] == [1, 2, 3]

    def test_chunk_size_equals_list(self) -> None:
        """Test when chunk size equals list length."""
        data = [1, 2, 3]
        chunks = list(chunk_list(data, 3))
        assert len(chunks) == 1
        assert chunks[0] == [1, 2, 3]

    def test_empty_list(self) -> None:
        """Test chunking empty list."""
        chunks = list(chunk_list([], 5))
        assert chunks == []

    def test_chunk_size_must_be_positive(self) -> None:
        """Test chunk size validation."""
        for invalid_size in (0, -1):
            with pytest.raises(ValueError, match="chunk_size must be greater than 0"):
                list(chunk_list([1, 2, 3], invalid_size))


# =============================================================================
# ensure_list 测试
# =============================================================================


class TestEnsureList:
    """Tests for ensure_list function."""

    def test_none_returns_empty_list(self) -> None:
        """Test None returns empty list."""
        assert ensure_list(None) == []

    def test_single_value_returns_list(self) -> None:
        """Test single value returns list."""
        assert ensure_list(1) == [1]
        assert ensure_list("test") == ["test"]

    def test_list_returns_same(self) -> None:
        """Test list returns same list."""
        original = [1, 2, 3]
        assert ensure_list(original) == original


# =============================================================================
# first_non_none 测试
# =============================================================================


class TestFirstNonNone:
    """Tests for first_non_none function."""

    def test_first_value_non_none(self) -> None:
        """Test returns first non-None value."""
        assert first_non_none(1, 2, 3) == 1
        assert first_non_none(None, 2, 3) == 2
        assert first_non_none(None, None, 3) == 3

    def test_all_none(self) -> None:
        """Test all None values."""
        assert first_non_none(None, None, None) is None

    def test_empty_args(self) -> None:
        """Test with no arguments."""
        assert first_non_none() is None


# =============================================================================
# flatten_dict / unflatten_dict 测试
# =============================================================================


class TestFlattenUnflattenDict:
    """Tests for flatten_dict and unflatten_dict functions."""

    def test_flatten_nested_dict(self, sample_nested_dict: dict[str, Any]) -> None:
        """Test flattening nested dictionary."""
        result = flatten_dict(sample_nested_dict)
        assert result == {"a.b.c": 1, "a.d": 2, "e": 3}

    def test_flatten_empty_dict(self) -> None:
        """Test flattening empty dictionary."""
        assert flatten_dict({}) == {}

    def test_flatten_flat_dict(self) -> None:
        """Test flattening already flat dictionary."""
        data = {"a": 1, "b": 2}
        assert flatten_dict(data) == data

    def test_flatten_with_custom_sep(self) -> None:
        """Test flattening with custom separator."""
        data = {"a": {"b": 1}}
        result = flatten_dict(data, sep="/")
        assert result == {"a/b": 1}

    def test_unflatten_dict(self) -> None:
        """Test unflattening dictionary."""
        data = {"a.b.c": 1, "a.d": 2, "e": 3}
        result = unflatten_dict(data)
        assert result == {"a": {"b": {"c": 1}, "d": 2}, "e": 3}

    def test_unflatten_with_custom_sep(self) -> None:
        """Test unflattening with custom separator."""
        data = {"a/b": 1}
        result = unflatten_dict(data, sep="/")
        assert result == {"a": {"b": 1}}

    def test_round_trip(self, sample_nested_dict: dict[str, Any]) -> None:
        """Test flattening and unflattening returns original."""
        flattened = flatten_dict(sample_nested_dict)
        result = unflatten_dict(flattened)
        assert result == sample_nested_dict


# =============================================================================
# merge_dicts / deep_merge_dict 测试
# =============================================================================


class TestMergeDicts:
    """Tests for merge_dicts and deep_merge_dict functions."""

    def test_merge_simple_dicts(self) -> None:
        """Test merging simple dictionaries."""
        d1 = {"a": 1, "b": 2}
        d2 = {"c": 3, "d": 4}
        result = merge_dicts(d1, d2)
        assert result == {"a": 1, "b": 2, "c": 3, "d": 4}

    def test_merge_with_overlap(self) -> None:
        """Test merging with overlapping keys."""
        d1 = {"a": 1, "b": 2}
        d2 = {"b": 3, "c": 4}
        result = merge_dicts(d1, d2)
        assert result["b"] == 3  # d2 value takes precedence

    def test_deep_merge(self) -> None:
        """Test deep merging nested dictionaries."""
        d1 = {"a": {"b": 1, "c": 2}}
        d2 = {"a": {"d": 3}}
        result = deep_merge_dict(d1, d2)
        assert result == {"a": {"b": 1, "c": 2, "d": 3}}

    def test_merge_empty_dict(self) -> None:
        """Test merging with empty dictionary."""
        d1 = {"a": 1}
        assert merge_dicts(d1, {}) == d1
        assert merge_dicts({}, d1) == d1


# =============================================================================
# filter_dict 测试
# =============================================================================


class TestFilterDict:
    """Tests for filter_dict function."""

    def test_filter_keys(self) -> None:
        """Test filtering dictionary by keys."""
        data = {"a": 1, "b": 2, "c": 3}
        result = filter_dict(data, ["a", "c"])
        assert result == {"a": 1, "c": 3}

    def test_filter_nonexistent_keys(self) -> None:
        """Test filtering with nonexistent keys."""
        data = {"a": 1, "b": 2}
        result = filter_dict(data, ["a", "x"])
        assert result == {"a": 1}

    def test_filter_empty_keys(self) -> None:
        """Test filtering with empty keys list."""
        data = {"a": 1, "b": 2}
        result = filter_dict(data, [])
        assert result == {}


# =============================================================================
# safe_get / safe_set 测试
# =============================================================================


class TestSafeGetSet:
    """Tests for safe_get and safe_set functions."""

    def test_safe_get_nested(self, sample_dict: dict[str, Any]) -> None:
        """Test safe_get with nested path."""
        result = safe_get(sample_dict, "nested.level1.level2")
        assert result == "deep_value"

    def test_safe_get_missing(self, sample_dict: dict[str, Any]) -> None:
        """Test safe_get with missing path."""
        result = safe_get(sample_dict, "nested.missing", default="default")
        assert result == "default"

    def test_safe_get_simple(self, sample_dict: dict[str, Any]) -> None:
        """Test safe_get with simple key."""
        result = safe_get(sample_dict, "name")
        assert result == "test"

    def test_safe_set_new_path(self) -> None:
        """Test safe_set creating new path."""
        data: dict[str, Any] = {}
        safe_set(data, "a.b.c", "value")
        assert data == {"a": {"b": {"c": "value"}}}

    def test_safe_set_existing_path(self) -> None:
        """Test safe_set updating existing path."""
        data: dict[str, Any] = {"a": {"b": 1}}
        safe_set(data, "a.b", 2)
        assert data["a"]["b"] == 2


# =============================================================================
# remove_none_values / remove_empty_values 测试
# =============================================================================


class TestRemoveValues:
    """Tests for remove_none_values and remove_empty_values functions."""

    def test_remove_none_values(self) -> None:
        """Test removing None values."""
        data = {"a": 1, "b": None, "c": 3}
        result = remove_none_values(data)
        assert result == {"a": 1, "c": 3}

    def test_remove_none_values_recursive(self) -> None:
        """Test removing None values recursively."""
        data = {"a": {"b": None, "c": 1}, "d": None}
        result = remove_none_values(data, recursive=True)
        assert result == {"a": {"c": 1}}

    def test_remove_empty_values(self) -> None:
        """Test removing empty values."""
        data = {"a": 1, "b": "", "c": [], "d": {}, "e": None, "f": "text"}
        result = remove_empty_values(data)
        assert result == {"a": 1, "f": "text"}

    def test_remove_empty_values_recursive(self) -> None:
        """Test removing empty values recursively."""
        data = {"a": {"b": "", "c": 1}, "d": []}
        result = remove_empty_values(data, recursive=True)
        assert result == {"a": {"c": 1}}


# =============================================================================
# batch_process 测试
# =============================================================================


class TestBatchProcess:
    """Tests for batch_process function."""

    def test_batch_process(self) -> None:
        """Test batch processing."""
        items = [1, 2, 3, 4, 5]
        results = batch_process(items, 2, sum)
        assert results == [3, 7, 5]  # sum([1,2]), sum([3,4]), sum([5])

    def test_batch_process_empty(self) -> None:
        """Test batch processing empty list."""
        results = batch_process([], 2, sum)
        assert results == []


# =============================================================================
# generate_uuid 测试
# =============================================================================


class TestGenerateUuid:
    """Tests for generate_uuid function."""

    def test_uuid_format(self) -> None:
        """Test UUID format."""
        uuid = generate_uuid()
        assert len(uuid) == 36
        assert uuid.count("-") == 4

    def test_uuid_uniqueness(self) -> None:
        """Test UUID uniqueness."""
        uuids = {generate_uuid() for _ in range(100)}
        assert len(uuids) == 100  # All UUIDs should be unique


# =============================================================================
# clamp 测试
# =============================================================================


class TestClamp:
    """Tests for clamp function."""

    def test_clamp_within_range(self) -> None:
        """Test clamping value within range."""
        assert clamp(5, 0, 10) == 5

    def test_clamp_below_min(self) -> None:
        """Test clamping value below min."""
        assert clamp(-5, 0, 10) == 0

    def test_clamp_above_max(self) -> None:
        """Test clamping value above max."""
        assert clamp(15, 0, 10) == 10

    def test_clamp_at_boundaries(self) -> None:
        """Test clamping at boundaries."""
        assert clamp(0, 0, 10) == 0
        assert clamp(10, 0, 10) == 10


# =============================================================================
# validate_email 测试
# =============================================================================


class TestValidateEmail:
    """Tests for validate_email function."""

    def test_valid_emails(self) -> None:
        """Test valid email addresses."""
        assert validate_email("test@example.com") is True
        assert validate_email("user.name@domain.co.uk") is True
        assert validate_email("user+tag@example.org") is True

    def test_invalid_emails(self) -> None:
        """Test invalid email addresses."""
        assert validate_email("invalid") is False
        assert validate_email("@example.com") is False
        assert validate_email("test@") is False
        assert validate_email("") is False


class TestRetryOnException:
    """Tests for retry_on_exception function."""

    def test_retry_eventual_success(self) -> None:
        """Retry should return result when a later attempt succeeds."""
        attempts = 0

        def flaky() -> str:
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise ValueError("not yet")
            return "ok"

        result = retry_on_exception(flaky, max_retries=3, delay=0)
        assert result == "ok"
        assert attempts == 3

    def test_retry_raises_after_all_failures(self) -> None:
        """Retry should raise when all attempts fail."""

        def always_fail() -> str:
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"):
            retry_on_exception(always_fail, max_retries=2, delay=0)


def test_common_utils_does_not_reexport_settings_api() -> None:
    """common_utils should not re-export Settings accessors."""
    with pytest.raises(ImportError):
        exec("from python_template.utils.common_utils import get_settings")
