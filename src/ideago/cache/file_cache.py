"""Local JSON file cache for research reports.

本地 JSON 文件缓存，用于存储和检索调研报告。
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from ideago.models.base import BaseModel
from ideago.models.research import ResearchReport
from ideago.observability.log_config import get_logger

logger = get_logger(__name__)


class ReportIndex(BaseModel):
    """Summary entry in the cache index."""

    report_id: str
    query: str
    cache_key: str
    created_at: datetime
    competitor_count: int = 0


class FileCache:
    """File-based cache that stores reports as JSON files with a central index."""

    def __init__(self, cache_dir: str, ttl_hours: int = 24) -> None:
        self._dir = Path(cache_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._ttl_hours = ttl_hours
        self._index_path = self._dir / "_index.json"
        self._index_lock = threading.Lock()

    def _is_expired(self, created_at: datetime) -> bool:
        age = datetime.now(timezone.utc) - created_at
        return age.total_seconds() > self._ttl_hours * 3600

    def _read_index(self) -> list[ReportIndex]:
        if not self._index_path.exists():
            return []
        try:
            data = json.loads(self._index_path.read_text(encoding="utf-8"))
            return [ReportIndex.model_validate(entry) for entry in data]
        except Exception:
            logger.warning("Failed to read cache index, starting fresh")
            return []

    def _write_index(self, entries: list[ReportIndex]) -> None:
        data = [e.model_dump(mode="json") for e in entries]
        temp_path = self._dir / f".{self._index_path.name}.{uuid4().hex}.tmp"
        temp_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temp_path.replace(self._index_path)

    async def get(self, cache_key: str) -> ResearchReport | None:
        """Retrieve a cached report by cache key. Returns None if missing or expired."""
        return await asyncio.to_thread(self._get_sync, cache_key)

    def _get_sync(self, cache_key: str) -> ResearchReport | None:
        with self._index_lock:
            index = self._read_index()
        for entry in index:
            if entry.cache_key == cache_key:
                if self._is_expired(entry.created_at):
                    return None
                report_path = self._dir / f"{entry.report_id}.json"
                if not report_path.exists():
                    return None
                try:
                    data = json.loads(report_path.read_text(encoding="utf-8"))
                    return ResearchReport.model_validate(data)
                except Exception:
                    logger.warning("Failed to read cached report {}", entry.report_id)
                    return None
        return None

    async def get_by_id(self, report_id: str) -> ResearchReport | None:
        """Retrieve a cached report by its ID."""
        return await asyncio.to_thread(self._get_by_id_sync, report_id)

    def _get_by_id_sync(self, report_id: str) -> ResearchReport | None:
        report_path = self._dir / f"{report_id}.json"
        if not report_path.exists():
            return None
        try:
            data = json.loads(report_path.read_text(encoding="utf-8"))
            report = ResearchReport.model_validate(data)
            if self._is_expired(report.created_at):
                return None
            return report
        except Exception:
            logger.warning("Failed to read cached report {}", report_id)
            return None

    async def put(self, report: ResearchReport) -> None:
        """Store a report in the cache."""
        await asyncio.to_thread(self._put_sync, report)

    def _put_sync(self, report: ResearchReport) -> None:
        report_path = self._dir / f"{report.id}.json"
        report_path.write_text(
            report.model_dump_json(indent=2),
            encoding="utf-8",
        )

        with self._index_lock:
            index = self._read_index()
            index = [e for e in index if e.cache_key != report.intent.cache_key]
            index.append(
                ReportIndex(
                    report_id=report.id,
                    query=report.query,
                    cache_key=report.intent.cache_key,
                    created_at=report.created_at,
                    competitor_count=len(report.competitors),
                )
            )
            self._write_index(index)

    async def list_reports(
        self,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[ReportIndex]:
        """List cached reports, excluding expired entries."""
        return await asyncio.to_thread(self._list_reports_sync, limit, offset)

    def _list_reports_sync(
        self,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[ReportIndex]:
        with self._index_lock:
            index = self._read_index()
        reports = [e for e in index if not self._is_expired(e.created_at)]
        reports.sort(key=lambda entry: entry.created_at, reverse=True)
        if offset > 0:
            reports = reports[offset:]
        if limit is not None:
            reports = reports[:limit]
        return reports

    async def delete(self, report_id: str) -> bool:
        """Delete a cached report by ID."""
        return await asyncio.to_thread(self._delete_sync, report_id)

    def _delete_sync(self, report_id: str) -> bool:
        report_path = self._dir / f"{report_id}.json"
        if report_path.exists():
            report_path.unlink()
        status_path = self._dir / f"{report_id}.status.json"
        if status_path.exists():
            status_path.unlink()

        with self._index_lock:
            index = self._read_index()
            new_index = [e for e in index if e.report_id != report_id]
            if len(new_index) < len(index):
                self._write_index(new_index)
                return True
            return False

    async def put_status(
        self,
        report_id: str,
        status: str,
        query: str = "",
        *,
        error_code: str | None = None,
        message: str | None = None,
    ) -> None:
        """Write a lightweight status file for a pipeline run."""
        await asyncio.to_thread(
            self._put_status_sync,
            report_id,
            status,
            query,
            error_code,
            message,
        )

    def _put_status_sync(
        self,
        report_id: str,
        status: str,
        query: str,
        error_code: str | None,
        message: str | None,
    ) -> None:
        status_path = self._dir / f"{report_id}.status.json"
        data = {
            "report_id": report_id,
            "status": status,
            "query": query,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if error_code:
            data["error_code"] = error_code
        if message:
            data["message"] = message
        status_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    async def get_status(self, report_id: str) -> dict | None:
        """Read a pipeline status file. Returns None if not found."""
        return await asyncio.to_thread(self._get_status_sync, report_id)

    def _get_status_sync(self, report_id: str) -> dict | None:
        status_path = self._dir / f"{report_id}.status.json"
        if not status_path.exists():
            return None
        try:
            return json.loads(status_path.read_text(encoding="utf-8"))
        except Exception:
            return None

    async def remove_status(self, report_id: str) -> None:
        """Remove a pipeline status file."""
        await asyncio.to_thread(self._remove_status_sync, report_id)

    def _remove_status_sync(self, report_id: str) -> None:
        status_path = self._dir / f"{report_id}.status.json"
        if status_path.exists():
            status_path.unlink()

    async def cleanup_expired(self) -> int:
        """Remove all expired cache entries. Returns count of removed entries."""
        return await asyncio.to_thread(self._cleanup_expired_sync)

    def _cleanup_expired_sync(self) -> int:
        with self._index_lock:
            index = self._read_index()
            kept: list[ReportIndex] = []
            removed = 0
            for entry in index:
                if self._is_expired(entry.created_at):
                    report_path = self._dir / f"{entry.report_id}.json"
                    if report_path.exists():
                        report_path.unlink()
                    removed += 1
                else:
                    kept.append(entry)
            self._write_index(kept)

        kept_report_ids = {entry.report_id for entry in kept}
        for status_path in self._dir.glob("*.status.json"):
            report_id = status_path.name.removesuffix(".status.json")
            if report_id in kept_report_ids:
                continue
            report_path = self._dir / f"{report_id}.json"
            if report_path.exists():
                continue
            if _is_stale_status_file(status_path, self._ttl_hours):
                with contextlib.suppress(OSError):
                    status_path.unlink()

        return removed


def _is_stale_status_file(status_path: Path, ttl_hours: int) -> bool:
    """Return whether a status file is stale enough to be cleaned up."""
    try:
        payload = json.loads(status_path.read_text(encoding="utf-8"))
    except Exception:
        return True

    raw_updated_at = payload.get("updated_at")
    if not isinstance(raw_updated_at, str):
        return True
    try:
        updated_at = datetime.fromisoformat(raw_updated_at)
    except ValueError:
        return True

    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    age_seconds = (datetime.now(timezone.utc) - updated_at).total_seconds()
    return age_seconds > ttl_hours * 3600
