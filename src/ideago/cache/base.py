"""Abstract report repository interface.

所有报告存储后端都实现此协议；`main` 当前使用本地文件缓存。
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from pydantic import Field

from ideago.models.base import BaseModel
from ideago.models.research import ResearchReport


class ReportIndex(BaseModel):
    """Summary entry used for report listing."""

    report_id: str
    query: str
    cache_key: str
    created_at: datetime
    competitor_count: int = Field(default=0)
    user_id: str = Field(default="")


class ReportRepository(Protocol):
    """Storage backend for research reports and pipeline status."""

    # ── Report CRUD ──────────────────────────────────────────────

    async def get(self, cache_key: str, *, user_id: str = "") -> ResearchReport | None:
        """Retrieve a cached report by its content-hash cache key.

        When *user_id* is provided, repositories may use it to scope results
        to an owning identity. ``main`` usually leaves this empty.
        """
        ...

    async def get_by_id(
        self, report_id: str, *, user_id: str = ""
    ) -> ResearchReport | None:
        """Retrieve a report by its unique ID.

        When *user_id* is provided, repositories may use it to scope results
        to an owning identity. ``main`` usually leaves this empty.
        """
        ...

    async def put(self, report: ResearchReport, *, user_id: str = "") -> None:
        """Store (upsert) a report, optionally associating it with a user."""
        ...

    async def delete(self, report_id: str, *, user_id: str = "") -> bool:
        """Delete a report. Returns True if it existed.

        When *user_id* is provided, repositories may use it to scope deletion
        to an owning identity. ``main`` usually leaves this empty.
        """
        ...

    async def list_reports(
        self,
        *,
        limit: int | None = None,
        offset: int = 0,
        user_id: str = "",
    ) -> tuple[list[ReportIndex], int]:
        """List reports, optionally filtered by user, sorted newest-first.

        Returns:
            Tuple of (entries, total_count) where total_count is the full
            count before limit/offset pagination.
        """
        ...

    # ── User ownership ───────────────────────────────────────────

    async def update_report_user_id(self, report_id: str, user_id: str) -> None:
        """Associate a report with a user."""
        ...

    async def get_report_user_id(self, report_id: str) -> str:
        """Return the owning user_id for a report, or empty string."""
        ...

    # ── Pipeline status ──────────────────────────────────────────

    async def put_status(
        self,
        report_id: str,
        status: str,
        query: str = "",
        *,
        error_code: str | None = None,
        message: str | None = None,
        user_id: str = "",
    ) -> None:
        """Write a pipeline run status record."""
        ...

    async def get_status(self, report_id: str) -> dict | None:
        """Read a pipeline run status. Returns None if not found."""
        ...

    async def remove_status(self, report_id: str) -> None:
        """Remove a pipeline run status record."""
        ...

    # ── Maintenance ──────────────────────────────────────────────

    async def cleanup_expired(self) -> int:
        """Remove expired entries. Returns count of removed reports."""
        ...
