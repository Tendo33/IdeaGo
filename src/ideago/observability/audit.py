"""Structured audit logging via Supabase.

Records security-relevant events (admin actions, login, account deletion)
into the ``audit_log`` table. Falls back to application logging when
Supabase is not configured.
"""

from __future__ import annotations

from typing import Any

import httpx

from ideago.config.settings import get_settings
from ideago.http.clients import get_probe_client
from ideago.observability.log_config import get_logger

logger = get_logger(__name__)


def _get_client() -> httpx.AsyncClient:
    """Audit writes share the fast-failing probe client."""
    return get_probe_client()


async def close_audit_client() -> None:
    """Kept for backwards compatibility; shared clients close via close_all_clients."""
    return None


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
