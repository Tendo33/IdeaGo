"""Tests for the personal file cache."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from ideago.cache.file_cache import FileCache, _is_stale_status_file
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
async def test_cache_put_and_get_round_trip(tmp_path) -> None:
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=24)
    report = _make_report()

    await cache.put(report)

    result = await cache.get("test_key")
    assert result is not None
    assert result.id == report.id
    assert result.query == "test idea"


@pytest.mark.asyncio
async def test_cache_get_by_id_and_status_round_trip(tmp_path) -> None:
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=24)
    report = _make_report()

    await cache.put(report)
    await cache.put_status(
        report.id,
        "failed",
        report.query,
        error_code="PIPELINE_FAILURE",
        message="Pipeline failed. Please retry.",
    )

    cached_report = await cache.get_by_id(report.id)
    status = await cache.get_status(report.id)

    assert cached_report is not None
    assert cached_report.id == report.id
    assert status is not None
    assert status["status"] == "failed"
    assert status["error_code"] == "PIPELINE_FAILURE"


@pytest.mark.asyncio
async def test_cache_enforces_anonymous_ttl(tmp_path) -> None:
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=1)
    report = _make_report()
    report.created_at = datetime.now(timezone.utc) - timedelta(hours=2)

    await cache.put(report)

    assert await cache.get("test_key") is None
    assert await cache.get_by_id(report.id) is None


@pytest.mark.asyncio
async def test_cache_keeps_owned_reports_past_ttl(tmp_path) -> None:
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=1)
    report = _make_report("owned-key", "owned idea")
    report.created_at = datetime.now(timezone.utc) - timedelta(hours=5)

    await cache.put(report, user_id="owner-1")

    result = await cache.get("owned-key", user_id="owner-1")
    assert result is not None
    assert result.query == "owned idea"


@pytest.mark.asyncio
async def test_cache_list_reports_supports_pagination(tmp_path) -> None:
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=24)
    await cache.put(_make_report("key1", "idea 1"))
    await cache.put(_make_report("key2", "idea 2"))
    await cache.put(_make_report("key3", "idea 3"))

    reports, total = await cache.list_reports(limit=2, offset=1)

    assert total == 3
    assert len(reports) == 2


@pytest.mark.asyncio
async def test_cache_update_report_user_id_and_lookup(tmp_path) -> None:
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=24)
    report = _make_report()

    await cache.put(report)
    assert await cache.get_report_user_id(report.id) == ""

    await cache.update_report_user_id(report.id, "user-1")

    assert await cache.get_report_user_id(report.id) == "user-1"
    assert await cache.get_by_id(report.id, user_id="user-2") is None
    assert await cache.get_by_id(report.id, user_id="user-1") is not None


@pytest.mark.asyncio
async def test_cache_delete_removes_report_and_status(tmp_path) -> None:
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=24)
    report = _make_report()

    await cache.put(report)
    await cache.put_status(report.id, "processing", report.query)

    deleted = await cache.delete(report.id)

    assert deleted is True
    assert await cache.get_by_id(report.id) is None
    assert await cache.get_status(report.id) is None


@pytest.mark.asyncio
async def test_cache_cleanup_expired_removes_stale_anonymous_entries(tmp_path) -> None:
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=1)
    fresh = _make_report("fresh-key", "fresh")
    stale = _make_report("stale-key", "stale")
    stale.created_at = datetime.now(timezone.utc) - timedelta(hours=2)

    await cache.put(fresh)
    await cache.put(stale)

    removed = await cache.cleanup_expired()
    reports, total = await cache.list_reports()

    assert removed == 1
    assert total == 1
    assert reports[0].query == "fresh"


@pytest.mark.asyncio
async def test_cache_eviction_keeps_owned_entries_when_max_entries_reached(
    tmp_path,
) -> None:
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=24, max_entries=2)
    await cache.put(_make_report("anon-1", "anon 1"))
    await cache.put(_make_report("anon-2", "anon 2"))
    await cache.put(_make_report("owned-1", "owned 1"), user_id="owner-1")

    reports, total = await cache.list_reports()
    queries = {report.query for report in reports}

    assert total == 2
    assert "owned 1" in queries
    assert len(queries) == 2


def test_internal_helpers_handle_corrupt_or_stale_files(tmp_path) -> None:
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=24)
    cache._index_path.write_text("not-json", encoding="utf-8")
    assert cache._read_index() == []

    stale_status = tmp_path / "cache" / "bad.status.json"
    stale_status.write_text("{", encoding="utf-8")
    assert _is_stale_status_file(stale_status, 24) is True

    valid_status = tmp_path / "cache" / "good.status.json"
    valid_status.write_text(
        json.dumps(
            {
                "report_id": "good",
                "status": "processing",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        ),
        encoding="utf-8",
    )
    assert _is_stale_status_file(valid_status, 24) is False
