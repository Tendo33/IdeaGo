"""Admin-only API routes."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from ideago.api.errors import AppError, DependencyUnavailableError, ErrorCode
from ideago.auth.dependencies import require_admin
from ideago.auth.models import AuthUser
from ideago.auth.supabase_admin import list_profiles, set_user_quota
from ideago.config.settings import get_settings
from ideago.http.clients import get_probe_client
from ideago.observability.audit import log_audit_event
from ideago.observability.log_config import get_logger
from ideago.observability.metrics import metrics as app_metrics

logger = get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])
_ADMIN_STATS_CACHE_TTL_SECONDS = 30.0
_admin_stats_cache: tuple[float, AdminStatsResponse] | None = None


class AdminStatsResponse(BaseModel):
    total_users: int | None
    total_reports: int | None
    active_processing: int | None
    plan_breakdown: dict[str, int]


def _clear_admin_stats_cache() -> None:
    global _admin_stats_cache
    _admin_stats_cache = None


def _empty_admin_stats() -> AdminStatsResponse:
    return AdminStatsResponse(
        total_users=None,
        total_reports=None,
        active_processing=None,
        plan_breakdown={},
    )


def _coerce_nullable_int(value: object) -> int | None:
    return value if isinstance(value, int) and value >= 0 else None


def _normalize_plan_breakdown(value: object) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    plan_breakdown: dict[str, int] = {}
    for plan, count in value.items():
        if isinstance(plan, str) and isinstance(count, int) and count >= 0:
            plan_breakdown[plan] = count
    return plan_breakdown


def _parse_admin_stats_summary(payload: object) -> AdminStatsResponse:
    if not isinstance(payload, dict):
        raise ValueError("Admin stats summary payload must be an object")
    return AdminStatsResponse(
        total_users=_coerce_nullable_int(payload.get("total_users")),
        total_reports=_coerce_nullable_int(payload.get("total_reports")),
        active_processing=_coerce_nullable_int(payload.get("active_processing")),
        plan_breakdown=_normalize_plan_breakdown(payload.get("plan_breakdown")),
    )


def _get_cached_admin_stats() -> AdminStatsResponse | None:
    if _admin_stats_cache is None:
        return None
    expires_at, payload = _admin_stats_cache
    if time.monotonic() >= expires_at:
        _clear_admin_stats_cache()
        return None
    return payload.model_copy(deep=True)


def _store_admin_stats_cache(payload: AdminStatsResponse) -> None:
    global _admin_stats_cache
    _admin_stats_cache = (
        time.monotonic() + _ADMIN_STATS_CACHE_TTL_SECONDS,
        payload.model_copy(deep=True),
    )


@router.get("/users")
async def admin_list_users(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    q: str = Query(default="", max_length=100),
    _admin: AuthUser = Depends(require_admin),
) -> dict:
    """Paginated user list with quota/plan info."""
    try:
        listed = await list_profiles(limit=limit, offset=offset, q=q)
        if isinstance(listed, tuple):
            items, total = listed
        else:
            items = listed
            total = len(items)
        return {
            "items": items,
            "total": total,
            "has_next": offset + len(items) < total,
            "limit": limit,
            "offset": offset,
        }
    except DependencyUnavailableError:
        raise AppError(
            503,
            ErrorCode.DEPENDENCY_UNAVAILABLE,
            "Admin data unavailable",
        ) from None


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
    try:
        result = await set_user_quota(
            user_id,
            plan_limit=body.plan_limit,
            usage_count=body.usage_count,
        )
    except DependencyUnavailableError:
        raise AppError(
            503,
            ErrorCode.DEPENDENCY_UNAVAILABLE,
            "Admin data unavailable",
        ) from None
    if result.get("error"):
        raise AppError(400, ErrorCode.VALIDATION_ERROR, result["error"])
    await log_audit_event(
        actor_id=_admin.id,
        action="admin.quota_update",
        target_type="user",
        target_id=user_id,
        metadata={"plan_limit": body.plan_limit, "usage_count": body.usage_count},
    )
    return result


async def _fetch_admin_stats_summary() -> AdminStatsResponse:
    """Fetch aggregated admin stats from a single Supabase RPC."""
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        return _empty_admin_stats()
    headers = {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    try:
        resp = await get_probe_client().post(
            f"{settings.supabase_url}/rest/v1/rpc/get_admin_stats_summary",
            headers=headers,
            json={},
        )
        if resp.status_code != 200:
            # Do not log the upstream body: PostgREST errors leak schema details.
            logger.warning(
                "Admin stats summary RPC failed with status {}",
                resp.status_code,
            )
            app_metrics.increment_event(
                "admin_stats_summary_degraded", reason="rpc_failed"
            )
            return _empty_admin_stats()

        summary = _parse_admin_stats_summary(resp.json())
        _store_admin_stats_cache(summary)
        return summary
    except ValueError as exc:
        logger.warning("Admin stats summary payload invalid: {}", exc)
        app_metrics.increment_event(
            "admin_stats_summary_degraded", reason="invalid_payload"
        )
    except Exception:
        logger.debug("Failed to fetch aggregated admin stats")
        app_metrics.increment_event("admin_stats_summary_degraded", reason="exception")
    return _empty_admin_stats()


@router.get("/stats", response_model=AdminStatsResponse)
async def admin_system_stats(
    _admin: AuthUser = Depends(require_admin),
) -> AdminStatsResponse:
    """Aggregate system statistics for the admin dashboard."""
    cached = _get_cached_admin_stats()
    if cached is not None:
        return cached
    return await _fetch_admin_stats_summary()


@router.get("/metrics")
async def admin_metrics(
    _admin: AuthUser = Depends(require_admin),
) -> dict:
    """In-process request metrics snapshot."""
    return app_metrics.snapshot()


@router.get("/health")
async def admin_health(
    _admin: AuthUser = Depends(require_admin),
) -> dict:
    """Detailed dependency and source health (admin-only)."""
    from ideago.api.routes.health import detailed_health_check

    return await detailed_health_check()
