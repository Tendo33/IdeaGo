"""Tests for file cache."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from ideago.cache.file_cache import FileCache
from ideago.models.research import Intent, Platform, ResearchReport, SearchQuery


def _make_report(
    cache_key: str = "test_key", query: str = "test idea"
) -> ResearchReport:
    intent = Intent(
        keywords_en=["test"],
        app_type="web",
        target_scenario="test",
        search_queries=[SearchQuery(platform=Platform.GITHUB, queries=["test"])],
        cache_key=cache_key,
    )
    return ResearchReport(query=query, intent=intent)


@pytest.mark.asyncio
async def test_cache_put_and_get(tmp_path) -> None:
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=24)
    report = _make_report()
    await cache.put(report)

    result = await cache.get("test_key")
    assert result is not None
    assert result.id == report.id
    assert result.query == "test idea"


@pytest.mark.asyncio
async def test_cache_get_missing_returns_none(tmp_path) -> None:
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=24)
    result = await cache.get("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_cache_get_by_id(tmp_path) -> None:
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=24)
    report = _make_report()
    await cache.put(report)

    result = await cache.get_by_id(report.id)
    assert result is not None
    assert result.query == "test idea"


@pytest.mark.asyncio
async def test_cache_expired_returns_none(tmp_path) -> None:
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=1)
    report = _make_report()
    report.created_at = datetime.now(timezone.utc) - timedelta(hours=2)
    await cache.put(report)

    result = await cache.get("test_key")
    assert result is None


@pytest.mark.asyncio
async def test_cache_list_reports(tmp_path) -> None:
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=24)
    await cache.put(_make_report("key1", "idea 1"))
    await cache.put(_make_report("key2", "idea 2"))

    reports = await cache.list_reports()
    assert len(reports) == 2


@pytest.mark.asyncio
async def test_cache_delete(tmp_path) -> None:
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=24)
    report = _make_report()
    await cache.put(report)

    deleted = await cache.delete(report.id)
    assert deleted is True

    result = await cache.get_by_id(report.id)
    assert result is None

    reports = await cache.list_reports()
    assert len(reports) == 0


@pytest.mark.asyncio
async def test_cache_delete_nonexistent(tmp_path) -> None:
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=24)
    deleted = await cache.delete("nonexistent")
    assert deleted is False


@pytest.mark.asyncio
async def test_cache_cleanup_expired(tmp_path) -> None:
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=1)

    fresh = _make_report("fresh_key", "fresh")
    await cache.put(fresh)

    old = _make_report("old_key", "old")
    old.created_at = datetime.now(timezone.utc) - timedelta(hours=2)
    await cache.put(old)

    removed = await cache.cleanup_expired()
    assert removed == 1

    reports = await cache.list_reports()
    assert len(reports) == 1
    assert reports[0].query == "fresh"


@pytest.mark.asyncio
async def test_cache_overwrites_same_cache_key(tmp_path) -> None:
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=24)
    r1 = _make_report("same_key", "first query")
    await cache.put(r1)
    r2 = _make_report("same_key", "second query")
    await cache.put(r2)

    reports = await cache.list_reports()
    assert len(reports) == 1
    assert reports[0].query == "second query"
