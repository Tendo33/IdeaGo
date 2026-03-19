"""Abstract report repository interface.

所有报告存储后端（文件系统、Supabase PostgreSQL）都实现此协议。
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from pydantic import Field

from ideago.models.base import BaseModel
from ideago.models.research import ResearchReport


class ReportIndex(BaseModel):
    """Summary entry used for report listing across all backends."""

    report_id: str
    query: str
    cache_key: str
    created_at: datetime
    competitor_count: int = Field(default=0)
    user_id: str = Field(default="")


class ReportRepository(Protocol):
    """Storage backend for research reports and pipeline status."""

    # ── Report CRUD ──────────────────────────────────────────────

    async def get(self, cache_key: str) -> ResearchReport | None:
        """Retrieve a cached report by its content-hash cache key."""
        ...

    async def get_by_id(self, report_id: str) -> ResearchReport | None:
        """Retrieve a report by its unique ID."""
        ...

    async def put(self, report: ResearchReport) -> None:
        """Store (upsert) a report."""
        ...

    async def delete(self, report_id: str) -> bool:
        """Delete a report. Returns True if it existed."""
        ...

    async def list_reports(
        self,
        *,
        limit: int | None = None,
        offset: int = 0,
        user_id: str = "",
    ) -> list[ReportIndex]:
        """List reports, optionally filtered by user, sorted newest-first."""
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
