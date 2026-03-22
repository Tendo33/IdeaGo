"""Admin-only API routes."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from ideago.api.errors import AppError, ErrorCode
from ideago.auth.dependencies import require_admin
from ideago.auth.models import AuthUser
from ideago.auth.supabase_admin import list_profiles, set_user_quota
from ideago.config.settings import get_settings
from ideago.observability.log_config import get_logger
from ideago.observability.metrics import metrics as app_metrics

logger = get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users")
async def admin_list_users(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _admin: AuthUser = Depends(require_admin),
) -> list[dict]:
    """Paginated user list with quota/plan info."""
    return await list_profiles(limit=limit, offset=offset)


class QuotaAdjustment(BaseModel):
    plan_limit: int | None = Field(default=None, ge=0, le=10000)
    usage_count: int | None = Field(default=None, ge=0)


@router.patch("/users/{user_id}/quota")
async def admin_set_quota(
    user_id: str,
    body: QuotaAdjustment,
    _admin: AuthUser = Depends(require_admin),
) -> dict:
    """Adjust a user's quota limit or usage count."""
    result = await set_user_quota(
        user_id,
        plan_limit=body.plan_limit,
        usage_count=body.usage_count,
    )
    if result.get("error"):
        raise AppError(400, ErrorCode.VALIDATION_ERROR, result["error"])
    return result


async def _count_table(table: str) -> int:
    """Count rows in a Supabase table using HEAD + Prefer: count=exact."""
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        return -1
    headers = {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Prefer": "count=exact",
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.head(
                f"{settings.supabase_url}/rest/v1/{table}",
                headers=headers,
                params={"select": "*"},
            )
        content_range = resp.headers.get("content-range", "")
        if "/" in content_range:
            total = content_range.split("/")[-1]
            return int(total) if total != "*" else -1
    except Exception:
        logger.debug("Failed to count table {}", table)
    return -1


@router.get("/stats")
async def admin_system_stats(
    _admin: AuthUser = Depends(require_admin),
) -> dict:
    """Aggregate system statistics for the admin dashboard."""
    total_users = await _count_table("profiles")
    total_reports = await _count_table("reports")
    active_processing = await _count_table("processing_reports")

    plan_breakdown: dict[str, int] = {}
    settings = get_settings()
    if settings.supabase_url and settings.supabase_service_role_key:
        headers = {
            "apikey": settings.supabase_service_role_key,
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
        }
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{settings.supabase_url}/rest/v1/profiles",
                    headers={**headers, "Accept": "application/json"},
                    params={"select": "plan"},
                )
            if resp.status_code == 200:
                for row in resp.json():
                    plan = row.get("plan", "free")
                    plan_breakdown[plan] = plan_breakdown.get(plan, 0) + 1
        except Exception:
            logger.debug("Failed to fetch plan breakdown")

    return {
        "total_users": total_users,
        "total_reports": total_reports,
        "active_processing": active_processing,
        "plan_breakdown": plan_breakdown,
    }


@router.get("/metrics")
async def admin_metrics(
    _admin: AuthUser = Depends(require_admin),
) -> dict:
    """In-process request metrics snapshot."""
    return app_metrics.snapshot()
