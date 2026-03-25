"""Structured audit logging via Supabase.

Records security-relevant events (admin actions, login, account deletion)
into the ``audit_log`` table. Falls back to application logging when
Supabase is not configured.
"""

from __future__ import annotations

from typing import Any

import httpx

from ideago.config.settings import get_settings
from ideago.observability.log_config import get_logger

logger = get_logger(__name__)

_audit_http_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _audit_http_client
    if _audit_http_client is None:
        _audit_http_client = httpx.AsyncClient(
            timeout=5.0,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )
    return _audit_http_client


async def close_audit_client() -> None:
    """Shut down the shared HTTP client (called during app lifespan teardown)."""
    global _audit_http_client
    if _audit_http_client is not None:
        await _audit_http_client.aclose()
        _audit_http_client = None


async def log_audit_event(
    *,
    actor_id: str,
    action: str,
    target_type: str | None = None,
    target_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> None:
    """Persist an audit event to the ``audit_log`` table.

    Falls back to structured logging when Supabase is unavailable.
    """
    settings = get_settings()
    log_payload = {
        "actor_id": actor_id,
        "action": action,
        "target_type": target_type,
        "target_id": target_id,
        "metadata": metadata or {},
        "ip_address": ip_address,
    }

    if not settings.supabase_url or not settings.supabase_service_role_key:
        logger.info("audit_event (log-only): {}", log_payload)
        return

    row = {
        "actor_id": actor_id,
        "action": action,
        "target_type": target_type or "",
        "target_id": target_id or "",
        "metadata": metadata or {},
        "ip_address": ip_address or "",
    }
    try:
        resp = await _get_client().post(
            f"{settings.supabase_url}/rest/v1/audit_log",
            headers={
                "apikey": settings.supabase_service_role_key,
                "Authorization": f"Bearer {settings.supabase_service_role_key}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            },
            json=row,
        )
        if resp.status_code not in {200, 201}:
            logger.warning(
                "Failed to insert audit log ({}): {}",
                resp.status_code,
                resp.text[:200],
            )
    except Exception:
        logger.opt(exception=True).warning("Audit log insert failed")
        logger.info("audit_event (fallback): {}", log_payload)
