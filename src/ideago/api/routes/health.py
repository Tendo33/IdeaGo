"""Health check endpoints.

Public ``/health`` returns process liveness only. Detailed dependency and source
information is served from ``/admin/health`` (see admin routes).
"""

from __future__ import annotations

import time

from fastapi import APIRouter

from ideago.api.dependencies import get_orchestrator
from ideago.config.settings import get_settings
from ideago.http.clients import get_probe_client
from ideago.observability.log_config import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["health"])

# The public endpoint is unauthenticated and outside the rate limiter. Probing
# Supabase on every hit turned it into a free amplifier: one cheap anonymous
# request became one outbound Supabase call plus a TLS handshake. The Docker
# HEALTHCHECK alone fired it ~2880 times a day. Results are cached, and the
# public endpoint no longer waits on the probe at all.
_DEPENDENCY_PROBE_TTL_SECONDS = 15.0
_probe_cache: tuple[float, str] | None = None


def _clear_probe_cache() -> None:
    global _probe_cache
    _probe_cache = None


async def _check_supabase(*, use_cache: bool = True) -> str:
    """Ping Supabase REST API. Returns 'ok' or an error detail."""
    global _probe_cache
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        return "not_configured"

    if use_cache and _probe_cache is not None:
        expires_at, cached = _probe_cache
        if time.monotonic() < expires_at:
            return cached

    try:
        resp = await get_probe_client().get(
            f"{settings.supabase_url}/rest/v1/",
            headers={
                "apikey": settings.supabase_service_role_key,
                "Authorization": f"Bearer {settings.supabase_service_role_key}",
            },
        )
        result = "ok" if 200 <= resp.status_code < 300 else f"error:{resp.status_code}"
    except Exception as exc:
        result = f"unreachable:{type(exc).__name__}"

    _probe_cache = (time.monotonic() + _DEPENDENCY_PROBE_TTL_SECONDS, result)
    return result


async def _check_stripe() -> str:
    """Verify Stripe key is configured."""
    settings = get_settings()
    if not settings.stripe_secret_key:
        return "not_configured"
    return "ok"


@router.get("/health")
async def health_check() -> dict:
    """Return process liveness (public, unauthenticated, no outbound calls).

    Deliberately does not probe dependencies: this endpoint answers "is the
    process up", which is what container orchestrators and uptime monitors need.
    Dependency status lives behind ``/admin/health``.
    """
    return {"status": "ok"}


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
