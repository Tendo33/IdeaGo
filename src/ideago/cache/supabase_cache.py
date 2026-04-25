"""Supabase PostgreSQL implementation of ReportRepository.

通过 Supabase REST API（service_role key）存取报告和管道状态。
"""

from __future__ import annotations

import httpx

from ideago.api.errors import DependencyUnavailableError
from ideago.cache.base import ReportIndex
from ideago.config.settings import get_settings
from ideago.models.research import ResearchReport
from ideago.observability.log_config import get_logger

logger = get_logger(__name__)


class SupabaseReportRepository:
    """Stores reports and status in Supabase PostgreSQL via REST API."""

    def __init__(self, ttl_hours: int = 24) -> None:
        self._ttl_hours = ttl_hours
        self._client: httpx.AsyncClient | None = None
        self._is_production = get_settings().environment == "production"

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=15.0,
                limits=httpx.Limits(
                    max_connections=100,
                    max_keepalive_connections=30,
                ),
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _headers(self) -> dict[str, str]:
        settings = get_settings()
        return {
            "apikey": settings.supabase_service_role_key,
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    def _url(self, path: str) -> str:
        return f"{get_settings().supabase_url}/rest/v1/{path}"

    # ── Tenant enforcement ─────────────────────────────────────

    def _warn_missing_user_id(self, operation: str) -> None:
        """Log a warning when user_id is empty in production."""
        if self._is_production:
            logger.warning(
                "Tenant isolation: {} called without user_id in production",
                operation,
            )

    # ── Report CRUD ──────────────────────────────────────────────

    async def get(self, cache_key: str, *, user_id: str = "") -> ResearchReport | None:
        if not user_id:
            self._warn_missing_user_id("get")
        client = self._get_client()
        params: dict[str, str] = {
            "cache_key": f"eq.{cache_key}",
            "select": "report_data",
            "order": "created_at.desc",
            "limit": "1",
        }
        if user_id:
            params["user_id"] = f"eq.{user_id}"
        resp = await client.get(
            self._url("reports"),
            headers={**self._headers(), "Accept": "application/json"},
            params=params,
        )
        if resp.status_code != 200:
            logger.warning("Supabase get by cache_key failed: {}", resp.status_code)
            raise DependencyUnavailableError(
                "report_cache_lookup_failed", dependency="supabase_reports"
            )
        rows = resp.json()
        if not rows:
            return None
        try:
            return ResearchReport.model_validate(rows[0]["report_data"])
        except Exception:
            logger.opt(exception=True).warning("Failed to parse report from DB")
            return None

    async def get_by_id(
        self, report_id: str, *, user_id: str = ""
    ) -> ResearchReport | None:
        if not user_id:
            self._warn_missing_user_id("get_by_id")
        client = self._get_client()
        params: dict[str, str] = {
            "id": f"eq.{report_id}",
            "select": "report_data",
            "limit": "1",
        }
        if user_id:
            params["user_id"] = f"eq.{user_id}"
        resp = await client.get(
            self._url("reports"),
            headers={**self._headers(), "Accept": "application/json"},
            params=params,
        )
        if resp.status_code != 200:
            raise DependencyUnavailableError(
                "report_lookup_failed", dependency="supabase_reports"
            )
        rows = resp.json()
        if not rows:
            return None
        try:
            return ResearchReport.model_validate(rows[0]["report_data"])
        except Exception:
            logger.opt(exception=True).warning("Failed to parse report {}", report_id)
            return None

    async def put(self, report: ResearchReport, *, user_id: str = "") -> None:
        if not user_id:
            self._warn_missing_user_id("put")
        client = self._get_client()
        body: dict[str, object] = {
            "id": report.id,
            "query": report.query,
            "cache_key": report.intent.cache_key,
            "competitor_count": len(report.competitors),
            "report_data": report.model_dump(mode="json"),
            "created_at": report.created_at.isoformat(),
        }
        if user_id:
            body["user_id"] = user_id
            body["expires_at"] = None
        else:
            from datetime import datetime, timedelta, timezone

            body["expires_at"] = (
                datetime.now(timezone.utc) + timedelta(hours=self._ttl_hours)
            ).isoformat()
        resp = await client.post(
            self._url("reports"),
            headers={
                **self._headers(),
                "Prefer": "resolution=merge-duplicates,return=minimal",
            },
            json=body,
        )
        if resp.status_code not in (200, 201):
            logger.warning(
                "Supabase put report failed: {} {}", resp.status_code, resp.text
            )
            raise DependencyUnavailableError(
                "report_persist_failed",
                dependency="supabase_reports",
            )

    async def delete(self, report_id: str, *, user_id: str = "") -> bool:
        if not user_id:
            self._warn_missing_user_id("delete")
        client = self._get_client()
        params: dict[str, str] = {"id": f"eq.{report_id}"}
        if user_id:
            params["user_id"] = f"eq.{user_id}"
        resp = await client.delete(
            self._url("reports"),
            headers=self._headers(),
            params=params,
        )
        if resp.status_code not in (200, 204):
            return False
        cleanup_params: dict[str, str] = {"report_id": f"eq.{report_id}"}
        if user_id:
            cleanup_params["user_id"] = f"eq.{user_id}"
        await client.delete(
            self._url("report_status"),
            headers=self._headers(),
            params=cleanup_params,
        )
        await client.delete(
            self._url("processing_reports"),
            headers=self._headers(),
            params=cleanup_params,
        )
        if resp.status_code == 200:
            rows = resp.json()
            return len(rows) > 0 if isinstance(rows, list) else True
        return True

    async def list_reports(
        self,
        *,
        limit: int | None = None,
        offset: int = 0,
        user_id: str = "",
        q: str = "",
    ) -> tuple[list[ReportIndex], bool, int]:
        client = self._get_client()
        requested_limit = limit
        params: dict[str, str] = {
            "select": "id,query,cache_key,created_at,competitor_count,user_id",
            "order": "created_at.desc",
        }
        if user_id:
            params["user_id"] = f"eq.{user_id}"
        normalized_q = q.strip().replace("*", "")
        if normalized_q:
            params["query"] = f"ilike.*{normalized_q}*"
        if limit is not None:
            params["limit"] = str(limit + 1)
        if offset > 0:
            params["offset"] = str(offset)

        resp = await client.get(
            self._url("reports"),
            headers={
                **self._headers(),
                "Accept": "application/json",
                "Prefer": "count=exact",
            },
            params=params,
        )
        if resp.status_code not in (200, 206):
            logger.warning("Supabase list_reports failed: {}", resp.status_code)
            raise DependencyUnavailableError(
                "report_list_failed", dependency="supabase_reports"
            )

        rows = resp.json()
        has_next = False
        if requested_limit is not None and len(rows) > requested_limit:
            rows = rows[:requested_limit]
            has_next = True
        result: list[ReportIndex] = []
        for row in rows:
            try:
                result.append(
                    ReportIndex(
                        report_id=row["id"],
                        query=row.get("query", ""),
                        cache_key=row.get("cache_key", ""),
                        created_at=row["created_at"],
                        competitor_count=row.get("competitor_count", 0),
                        user_id=row.get("user_id") or "",
                    )
                )
            except Exception:
                continue
        content_range = resp.headers.get("content-range", "")
        total = 0
        if "/" in content_range:
            total_raw = content_range.split("/")[-1]
            if total_raw.isdigit():
                total = int(total_raw)
        return result, has_next, total

    # ── User ownership ───────────────────────────────────────────

    async def update_report_user_id(self, report_id: str, user_id: str) -> None:
        client = self._get_client()
        resp = await client.patch(
            self._url("reports"),
            headers={**self._headers(), "Prefer": "return=minimal"},
            params={"id": f"eq.{report_id}"},
            json={"user_id": user_id, "expires_at": None},
        )
        if resp.status_code not in (200, 204):
            logger.warning("update_report_user_id failed: {}", resp.status_code)

    async def get_report_user_id(self, report_id: str) -> str:
        client = self._get_client()
        resp = await client.get(
            self._url("reports"),
            headers={**self._headers(), "Accept": "application/json"},
            params={
                "id": f"eq.{report_id}",
                "select": "user_id",
                "limit": "1",
            },
        )
        if resp.status_code != 200:
            raise DependencyUnavailableError(
                "report_owner_lookup_failed", dependency="supabase_reports"
            )
        rows = resp.json()
        if not rows:
            return ""
        return rows[0].get("user_id") or ""

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
        client = self._get_client()
        body: dict[str, str | None] = {
            "report_id": report_id,
            "status": status,
            "query": query,
            "error_code": error_code,
            "message": message,
        }
        if user_id:
            body["user_id"] = user_id
        resp = await client.post(
            self._url("report_status"),
            headers={
                **self._headers(),
                "Prefer": "resolution=merge-duplicates,return=minimal",
            },
            json=body,
        )
        if resp.status_code not in (200, 201):
            logger.warning("put_status failed: {} {}", resp.status_code, resp.text)
            raise DependencyUnavailableError(
                "report_status_persist_failed",
                dependency="supabase_report_status",
            )

    async def get_status(self, report_id: str) -> dict | None:
        client = self._get_client()
        resp = await client.get(
            self._url("report_status"),
            headers={**self._headers(), "Accept": "application/json"},
            params={
                "report_id": f"eq.{report_id}",
                "select": "report_id,status,query,error_code,message,updated_at,user_id",
                "limit": "1",
            },
        )
        if resp.status_code != 200:
            raise DependencyUnavailableError(
                "report_status_lookup_failed", dependency="supabase_report_status"
            )
        rows = resp.json()
        if not rows:
            return None
        return rows[0]

    async def remove_status(self, report_id: str) -> None:
        client = self._get_client()
        await client.delete(
            self._url("report_status"),
            headers=self._headers(),
            params={"report_id": f"eq.{report_id}"},
        )

    # ── Maintenance ──────────────────────────────────────────────

    async def cleanup_expired(self) -> int:
        """Call the DB function to clean up expired reports."""
        client = self._get_client()
        settings = get_settings()
        resp = await client.post(
            f"{settings.supabase_url}/rest/v1/rpc/cleanup_expired_reports",
            headers=self._headers(),
            json={"p_ttl_hours": self._ttl_hours},
        )
        if resp.status_code != 200:
            logger.warning("cleanup_expired failed: {}", resp.status_code)
            return 0
        result = resp.json()
        return result if isinstance(result, int) else 0
