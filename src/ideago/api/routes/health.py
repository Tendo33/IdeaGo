"""Health check endpoints.

Public ``/health`` returns a minimal status. Detailed dependency and source
information is served from ``/admin/health`` (see admin routes).
"""

from __future__ import annotations

import httpx
from fastapi import APIRouter

from ideago.api.dependencies import get_orchestrator
from ideago.config.settings import get_settings
from ideago.observability.log_config import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["health"])


async def _check_supabase() -> str:
    """Ping Supabase REST API. Returns 'ok' or error detail."""
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        return "not_configured"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{settings.supabase_url}/rest/v1/",
                headers={
                    "apikey": settings.supabase_service_role_key,
                    "Authorization": f"Bearer {settings.supabase_service_role_key}",
                },
            )
        return "ok" if resp.status_code < 500 else f"error:{resp.status_code}"
    except Exception as exc:
        return f"unreachable:{type(exc).__name__}"


async def _check_stripe() -> str:
    """Verify Stripe key is configured."""
    settings = get_settings()
    if not settings.stripe_secret_key:
        return "not_configured"
    return "ok"


@router.get("/health")
async def health_check() -> dict:
    """Return minimal service health status (public)."""
    status = "ok"
    supabase_status = await _check_supabase()
    if supabase_status not in ("ok", "not_configured"):
        status = "degraded"
    return {"status": status}


async def detailed_health_check() -> dict:
    """Return full dependency and source health (called by admin route)."""
    status = "ok"
    try:
        orchestrator = get_orchestrator()
        sources_status = orchestrator.get_source_availability()
    except Exception:
        logger.warning("Could not initialize orchestrator for health check")
        status = "degraded"
        sources_status = {}

    supabase_status = await _check_supabase()
    stripe_status = await _check_stripe()

    deps = {
        "supabase": supabase_status,
        "stripe": stripe_status,
    }

    if supabase_status not in ("ok", "not_configured"):
        status = "degraded"

    return {
        "status": status,
        "sources": sources_status,
        "dependencies": deps,
    }
