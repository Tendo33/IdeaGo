"""Tests for file cache."""

from __future__ import annotations

import asyncio
import contextlib
import json
import threading
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from ideago.api.errors import DependencyUnavailableError
from ideago.cache.file_cache import FileCache
from ideago.cache.supabase_cache import SupabaseReportRepository
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


def test_file_cache_internal_helpers_handle_corrupt_files(tmp_path) -> None:
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=24)
    cache._index_path.write_text("not-json", encoding="utf-8")
    assert cache._read_index() == []

    report = _make_report()
    assert cache._is_expired(report.created_at, has_owner=True) is False

    stale_status = tmp_path / "cache" / "bad.status.json"
    stale_status.write_text("{", encoding="utf-8")
    from ideago.cache.file_cache import _is_stale_status_file

    assert _is_stale_status_file(stale_status, 24) is True


@pytest.mark.asyncio
async def test_cache_get_by_id(tmp_path) -> None:
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=24)
    report = _make_report()
    await cache.put(report)

    result = await cache.get_by_id(report.id)
    assert result is not None
    assert result.query == "test idea"


@pytest.mark.asyncio
async def test_cache_get_and_get_by_id_tenant_and_corrupt_paths(tmp_path) -> None:
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=24)
    report = _make_report("tenant-key", "tenant query")
    await cache.put(report, user_id="user-a")

    assert await cache.get("tenant-key", user_id="user-b") is None
    assert await cache.get_by_id(report.id, user_id="user-b") is None

    report_path = tmp_path / "cache" / f"{report.id}.json"
    report_path.unlink()
    assert await cache.get("tenant-key", user_id="user-a") is None
    assert await cache.get_by_id(report.id, user_id="user-a") is None

    await cache.put(report, user_id="user-a")
    report_path.write_text("{", encoding="utf-8")
    assert await cache.get("tenant-key", user_id="user-a") is None
    assert await cache.get_by_id(report.id, user_id="user-a") is None


@pytest.mark.asyncio
async def test_cache_expired_returns_none(tmp_path) -> None:
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=1)
    report = _make_report()
    report.created_at = datetime.now(timezone.utc) - timedelta(hours=2)
    await cache.put(report)

    result = await cache.get("test_key")
    assert result is None


@pytest.mark.asyncio
async def test_cache_get_by_id_ignores_expired_report(tmp_path) -> None:
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=1)
    report = _make_report()
    report.created_at = datetime.now(timezone.utc) - timedelta(hours=2)
    await cache.put(report)

    result = await cache.get_by_id(report.id)
    assert result is None


@pytest.mark.asyncio
async def test_cache_list_reports(tmp_path) -> None:
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=24)
    await cache.put(_make_report("key1", "idea 1"))
    await cache.put(_make_report("key2", "idea 2"))

    reports, has_next, total = await cache.list_reports()
    assert len(reports) == 2
    assert has_next is False
    assert total == 2


@pytest.mark.asyncio
async def test_cache_list_reports_pagination_and_user_filter(tmp_path) -> None:
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=24)
    await cache.put(_make_report("key1", "idea 1"), user_id="user-a")
    await cache.put(_make_report("key2", "idea 2"), user_id="user-b")
    await cache.put(_make_report("key3", "idea 3"), user_id="user-a")

    reports, has_next, total = await cache.list_reports(
        limit=1, offset=1, user_id="user-a"
    )
    assert total == 2
    assert has_next is False
    assert len(reports) == 1
    assert reports[0].user_id == "user-a"


@pytest.mark.asyncio
async def test_cache_delete(tmp_path) -> None:
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=24)
    report = _make_report()
    await cache.put(report)

    deleted = await cache.delete(report.id)
    assert deleted is True

    result = await cache.get_by_id(report.id)
    assert result is None

    reports, _, _ = await cache.list_reports()
    assert len(reports) == 0


@pytest.mark.asyncio
async def test_cache_delete_removes_status_file(tmp_path) -> None:
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=24)
    report = _make_report()
    await cache.put(report)
    await cache.put_status(
        report.id, "failed", report.query, error_code="PIPELINE_FAILURE"
    )

    deleted = await cache.delete(report.id)
    assert deleted is True
    assert await cache.get_status(report.id) is None


@pytest.mark.asyncio
async def test_cache_delete_nonexistent(tmp_path) -> None:
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=24)
    deleted = await cache.delete("nonexistent")
    assert deleted is False


@pytest.mark.asyncio
async def test_cache_delete_respects_user_and_missing_entry(tmp_path) -> None:
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=24)
    report = _make_report("delete-key", "delete query")
    await cache.put(report, user_id="user-a")

    assert await cache.delete(report.id, user_id="user-b") is False
    assert await cache.delete("missing", user_id="user-a") is False
    assert await cache.delete(report.id, user_id="user-a") is True


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

    reports, _, _ = await cache.list_reports()
    assert len(reports) == 1
    assert reports[0].query == "fresh"


@pytest.mark.asyncio
async def test_cache_cleanup_expired_removes_stale_orphan_status_files(
    tmp_path,
) -> None:
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=1)
    stale_status_path = tmp_path / "cache" / "orphan-report.status.json"
    stale_status_path.parent.mkdir(parents=True, exist_ok=True)
    stale_status_path.write_text(
        json.dumps(
            {
                "report_id": "orphan-report",
                "status": "failed",
                "updated_at": (
                    datetime.now(timezone.utc) - timedelta(hours=2)
                ).isoformat(),
            },
        ),
        encoding="utf-8",
    )

    removed_count = await cache.cleanup_expired()

    assert removed_count == 0
    assert not stale_status_path.exists()


@pytest.mark.asyncio
async def test_cache_cleanup_keeps_recent_or_invalid_owner_reports(tmp_path) -> None:
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=1)
    owned = _make_report("owned-key", "owned")
    owned.created_at = datetime.now(timezone.utc) - timedelta(hours=5)
    await cache.put(owned, user_id="owner")

    status_path = tmp_path / "cache" / f"{owned.id}.status.json"
    status_path.write_text(
        json.dumps(
            {
                "report_id": owned.id,
                "status": "processing",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        ),
        encoding="utf-8",
    )

    removed = await cache.cleanup_expired()
    assert removed == 0
    assert status_path.exists()


@pytest.mark.asyncio
async def test_cache_overwrites_same_cache_key(tmp_path) -> None:
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=24)
    r1 = _make_report("same_key", "first query")
    await cache.put(r1)
    r2 = _make_report("same_key", "second query")
    await cache.put(r2)

    reports, _, _ = await cache.list_reports()
    assert len(reports) == 1
    assert reports[0].query == "second query"


@pytest.mark.asyncio
async def test_cache_eviction_update_owner_and_status_edge_cases(tmp_path) -> None:
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=24, max_entries=2)
    first = _make_report("k1", "first")
    second = _make_report("k2", "second")
    third = _make_report("k3", "third")
    first.created_at = datetime.now(timezone.utc) - timedelta(hours=3)
    second.created_at = datetime.now(timezone.utc) - timedelta(hours=2)
    third.created_at = datetime.now(timezone.utc) - timedelta(hours=1)

    await cache.put(first)
    await cache.put(second, user_id="owner")
    await cache.put(third)

    reports, has_next, total = await cache.list_reports()
    assert total == 2
    assert has_next is False
    assert all(entry.report_id != first.id for entry in reports)

    await cache.update_report_user_id(third.id, "new-owner")
    assert await cache.get_report_user_id(third.id) == "new-owner"
    assert await cache.get_report_user_id("missing") == ""

    bad_status = tmp_path / "cache" / "bad-report.status.json"
    bad_status.write_text("{", encoding="utf-8")
    assert await cache.get_status("bad-report") is None
    await cache.remove_status("missing")


# --- Pipeline status ---


@pytest.mark.asyncio
async def test_cache_put_and_get_status(tmp_path) -> None:
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=24)
    await cache.put_status("report-1", "processing", "my test query")

    status = await cache.get_status("report-1")
    assert status is not None
    assert status["status"] == "processing"
    assert status["query"] == "my test query"
    assert status["report_id"] == "report-1"


@pytest.mark.asyncio
async def test_cache_get_status_missing(tmp_path) -> None:
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=24)
    status = await cache.get_status("nonexistent")
    assert status is None


@pytest.mark.asyncio
async def test_cache_remove_status(tmp_path) -> None:
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=24)
    await cache.put_status("report-1", "processing")
    await cache.remove_status("report-1")

    status = await cache.get_status("report-1")
    assert status is None


@pytest.mark.asyncio
async def test_cache_concurrent_put_preserves_all_entries(tmp_path) -> None:
    cache = FileCache(str(tmp_path / "cache"), ttl_hours=24)
    reports = [_make_report(f"key-{i}", f"idea-{i}") for i in range(5)]

    original_read_index = cache._read_index
    barrier = threading.Barrier(parties=len(reports))
    guarded_calls = 0
    guarded_lock = threading.Lock()

    def synchronized_read_index():
        nonlocal guarded_calls
        with guarded_lock:
            guarded_calls += 1
            should_guard = guarded_calls <= len(reports)
        if should_guard:
            with contextlib.suppress(threading.BrokenBarrierError):
                barrier.wait(timeout=0.2)
        return original_read_index()

    with patch.object(cache, "_read_index", side_effect=synchronized_read_index):
        await asyncio.gather(*(cache.put(report) for report in reports))

    entries, _, _ = await cache.list_reports()
    assert len(entries) == len(reports)


class _FakeResponse:
    def __init__(
        self,
        status_code: int,
        *,
        payload=None,
        text: str = "",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text
        self.headers = headers or {}

    def json(self):
        return self._payload


@pytest.mark.asyncio
async def test_supabase_repo_get_and_get_by_id(tmp_path) -> None:
    report = _make_report("cache-key", "query-1")
    fake_client = AsyncMock()
    fake_client.get = AsyncMock(
        side_effect=[
            _FakeResponse(
                200, payload=[{"report_data": report.model_dump(mode="json")}]
            ),
            _FakeResponse(
                200, payload=[{"report_data": report.model_dump(mode="json")}]
            ),
            _FakeResponse(200, payload=[]),
        ]
    )
    fake_settings = type(
        "Settings",
        (),
        {
            "supabase_url": "https://example.supabase.co",
            "supabase_service_role_key": "srk",
        },
    )()
    repo = SupabaseReportRepository(ttl_hours=24)
    repo._client = fake_client

    with patch("ideago.cache.supabase_cache.get_settings", return_value=fake_settings):
        assert await repo.get("cache-key") is not None
        assert await repo.get_by_id(report.id) is not None
        assert await repo.get("missing-key") is None


@pytest.mark.asyncio
async def test_supabase_repo_get_error_and_parse_failures() -> None:
    report = _make_report("cache-key", "query-1")
    fake_client = AsyncMock()
    fake_client.get = AsyncMock(
        side_effect=[
            _FakeResponse(500, payload=[]),
            _FakeResponse(200, payload=[{"report_data": {"bad": "payload"}}]),
            _FakeResponse(500, payload=[]),
            _FakeResponse(200, payload=[{"report_data": {"bad": "payload"}}]),
        ]
    )
    fake_settings = type(
        "Settings",
        (),
        {
            "environment": "production",
            "supabase_url": "https://example.supabase.co",
            "supabase_service_role_key": "srk",
        },
    )()
    with patch("ideago.cache.supabase_cache.get_settings", return_value=fake_settings):
        repo = SupabaseReportRepository(ttl_hours=24)
        repo._client = fake_client
        with pytest.raises(DependencyUnavailableError):
            await repo.get(report.intent.cache_key)
        assert await repo.get(report.intent.cache_key) is None
        with pytest.raises(DependencyUnavailableError):
            await repo.get_by_id(report.id)
        assert await repo.get_by_id(report.id) is None


@pytest.mark.asyncio
async def test_supabase_repo_put_list_and_delete() -> None:
    report = _make_report("cache-key-2", "query-2")
    fake_client = AsyncMock()
    fake_client.post = AsyncMock(return_value=_FakeResponse(201))
    fake_client.get = AsyncMock(
        return_value=_FakeResponse(
            200,
            payload=[
                {
                    "id": report.id,
                    "query": report.query,
                    "cache_key": report.intent.cache_key,
                    "created_at": report.created_at.isoformat(),
                    "competitor_count": 0,
                    "user_id": "user-1",
                }
            ],
            headers={"content-range": "0-0/1"},
        )
    )
    fake_client.delete = AsyncMock(
        return_value=_FakeResponse(200, payload=[{"id": report.id}])
    )
    fake_settings = type(
        "Settings",
        (),
        {
            "supabase_url": "https://example.supabase.co",
            "supabase_service_role_key": "srk",
        },
    )()
    repo = SupabaseReportRepository(ttl_hours=24)
    repo._client = fake_client

    with patch("ideago.cache.supabase_cache.get_settings", return_value=fake_settings):
        await repo.put(report)
        rows, has_next, total = await repo.list_reports(
            limit=10, offset=0, user_id="user-1"
        )
        assert len(rows) == 1
        assert has_next is False
        assert total == 1
        deleted = await repo.delete(report.id)
        assert deleted is True


@pytest.mark.asyncio
async def test_supabase_repo_list_reports_accepts_partial_content() -> None:
    report = _make_report("cache-key-206", "query-206")
    fake_client = AsyncMock()
    fake_client.get = AsyncMock(
        return_value=_FakeResponse(
            206,
            payload=[
                {
                    "id": report.id,
                    "query": report.query,
                    "cache_key": report.intent.cache_key,
                    "created_at": report.created_at.isoformat(),
                    "competitor_count": 0,
                    "user_id": "user-1",
                }
            ],
            headers={"content-range": "0-0/6"},
        )
    )
    fake_settings = type(
        "Settings",
        (),
        {
            "supabase_url": "https://example.supabase.co",
            "supabase_service_role_key": "srk",
        },
    )()
    repo = SupabaseReportRepository(ttl_hours=24)
    repo._client = fake_client

    with patch("ideago.cache.supabase_cache.get_settings", return_value=fake_settings):
        rows, has_next, total = await repo.list_reports(
            limit=5, offset=0, user_id="user-1"
        )
        assert len(rows) == 1
        assert has_next is False
        assert total == 6


@pytest.mark.asyncio
async def test_supabase_repo_put_list_and_delete_error_paths() -> None:
    report = _make_report("cache-key-3", "query-3")
    fake_client = AsyncMock()
    fake_client.post = AsyncMock(return_value=_FakeResponse(500, text="fail"))
    fake_client.get = AsyncMock(
        side_effect=[
            _FakeResponse(500, payload=[]),
            _FakeResponse(
                200,
                payload=[
                    {
                        "id": report.id,
                        "created_at": "bad-date",
                    }
                ],
                headers={},
            ),
        ]
    )
    fake_client.delete = AsyncMock(
        side_effect=[
            _FakeResponse(204),
            _FakeResponse(200, payload=[]),
            _FakeResponse(204),
            _FakeResponse(200, payload=[]),
            _FakeResponse(200, payload=[]),
            _FakeResponse(204),
        ]
    )
    fake_settings = type(
        "Settings",
        (),
        {
            "environment": "development",
            "supabase_url": "https://example.supabase.co",
            "supabase_service_role_key": "srk",
        },
    )()
    with patch("ideago.cache.supabase_cache.get_settings", return_value=fake_settings):
        repo = SupabaseReportRepository(ttl_hours=24)
        repo._client = fake_client
        with pytest.raises(DependencyUnavailableError):
            await repo.put(report, user_id="user-1")
        with pytest.raises(DependencyUnavailableError):
            await repo.list_reports(limit=10, offset=0)
        rows, has_next, total = await repo.list_reports(limit=10, offset=0)
        assert rows == []
        assert has_next is False
        assert total == 0
        assert await repo.delete(report.id) is True
        assert await repo.delete(report.id) is False


@pytest.mark.asyncio
async def test_supabase_repo_user_and_status_and_cleanup() -> None:
    fake_client = AsyncMock()
    fake_client.patch = AsyncMock(return_value=_FakeResponse(204))
    fake_client.post = AsyncMock(
        side_effect=[
            _FakeResponse(201),
            _FakeResponse(200, payload=3),
        ]
    )
    fake_client.get = AsyncMock(
        side_effect=[
            _FakeResponse(200, payload=[{"user_id": "user-42"}]),
            _FakeResponse(
                200,
                payload=[
                    {
                        "report_id": "r-1",
                        "status": "failed",
                        "query": "query",
                        "error_code": "PIPELINE_FAILURE",
                        "message": "Pipeline failed",
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }
                ],
            ),
        ]
    )
    fake_client.delete = AsyncMock(return_value=_FakeResponse(204))
    fake_settings = type(
        "Settings",
        (),
        {
            "supabase_url": "https://example.supabase.co",
            "supabase_service_role_key": "srk",
        },
    )()
    repo = SupabaseReportRepository(ttl_hours=24)
    repo._client = fake_client

    with patch("ideago.cache.supabase_cache.get_settings", return_value=fake_settings):
        await repo.update_report_user_id("r-1", "user-42")
        owner = await repo.get_report_user_id("r-1")
        assert owner == "user-42"

        await repo.put_status("r-1", "failed", "query", error_code="PIPELINE_FAILURE")
        status = await repo.get_status("r-1")
        assert status is not None
        assert status["status"] == "failed"

        await repo.remove_status("r-1")
        removed = await repo.cleanup_expired()
        assert removed == 3


@pytest.mark.asyncio
async def test_supabase_repo_user_status_cleanup_and_close_edge_paths() -> None:
    fake_client = AsyncMock()
    fake_client.patch = AsyncMock(return_value=_FakeResponse(500))
    fake_client.post = AsyncMock(
        side_effect=[
            _FakeResponse(500, text="fail"),
            _FakeResponse(500, payload={}),
        ]
    )
    fake_client.get = AsyncMock(
        side_effect=[
            _FakeResponse(500, payload=[]),
            _FakeResponse(200, payload=[]),
            _FakeResponse(500, payload=[]),
            _FakeResponse(200, payload=[]),
        ]
    )
    fake_client.delete = AsyncMock(return_value=_FakeResponse(204))
    fake_settings = type(
        "Settings",
        (),
        {
            "environment": "production",
            "supabase_url": "https://example.supabase.co",
            "supabase_service_role_key": "srk",
        },
    )()
    with patch("ideago.cache.supabase_cache.get_settings", return_value=fake_settings):
        repo = SupabaseReportRepository(ttl_hours=24)
        repo._client = fake_client
        await repo.update_report_user_id("r-2", "user-9")
        with pytest.raises(DependencyUnavailableError):
            await repo.get_report_user_id("r-2")
        assert await repo.get_report_user_id("r-2") == ""
        await repo.put_status("r-2", "processing", "query")
        with pytest.raises(DependencyUnavailableError):
            await repo.get_status("r-2")
        assert await repo.get_status("r-2") is None
        await repo.remove_status("r-2")
        assert await repo.cleanup_expired() == 0
        repo._client = None
        await repo.close()


@pytest.mark.asyncio
async def test_supabase_repo_close_releases_client() -> None:
    fake_client = AsyncMock()
    fake_settings = type(
        "Settings",
        (),
        {
            "supabase_url": "https://example.supabase.co",
            "supabase_service_role_key": "srk",
        },
    )()
    repo = SupabaseReportRepository(ttl_hours=24)
    repo._client = fake_client

    with patch("ideago.cache.supabase_cache.get_settings", return_value=fake_settings):
        await repo.close()
    fake_client.aclose.assert_awaited_once()
