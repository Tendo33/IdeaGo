"""Scheduled maintenance for Supabase-side retention.

Migrations shipped cleanup functions for webhook events, rate-limit hits, audit
log and stale processing slots — but nothing ever called them, and
``auth_sessions`` had no cleanup function at all. Four tables grew without
bound for the life of a deployment.

Every ``cleanup_*`` function in ``supabase/migrations/`` is invoked from here.
A test asserts that correspondence so a future migration cannot quietly add a
fifth orphan.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from ideago.config.settings import get_settings
from ideago.http.clients import get_supabase_client
from ideago.observability.error_catalog import log_error_event
from ideago.observability.log_config import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class RetentionJob:
    """One Supabase cleanup RPC and the arguments it takes."""

    rpc: str
    params: dict[str, object]
    description: str


def build_retention_jobs(*, cleanup_interval_seconds: int) -> list[RetentionJob]:
    """Return every retention job the backend is responsible for running."""
    return [
        RetentionJob(
            rpc="cleanup_stale_processing_slots",
            params={},
            description="dedup reservations orphaned by a crash or restart",
        ),
        RetentionJob(
            rpc="cleanup_old_webhook_events",
            params={},
            description="processed Stripe webhook idempotency records",
        ),
        RetentionJob(
            rpc="cleanup_audit_log",
            params={},
            description="audit records past their retention window",
        ),
        RetentionJob(
            rpc="cleanup_auth_sessions",
            params={},
            description="revoked and expired custom auth sessions",
        ),
    ]


async def run_retention_jobs(*, cleanup_interval_seconds: int) -> dict[str, int]:
    """Run every retention job. Never raises; a failure must not kill the loop.

    Returns rpc name -> rows removed (0 when the RPC does not report a count).
    """
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        return {}

    headers = {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Content-Type": "application/json",
    }
    client = get_supabase_client()
    removed: dict[str, int] = {}

    for job in build_retention_jobs(cleanup_interval_seconds=cleanup_interval_seconds):
        try:
            response = await client.post(
                f"{settings.supabase_url}/rest/v1/rpc/{job.rpc}",
                headers=headers,
                json=job.params,
            )
            if response.status_code == 200:
                payload = response.json()
                removed[job.rpc] = payload if isinstance(payload, int) else 0
                continue
            # A missing function means the migration has not been applied yet;
            # that is an operator problem, not a reason to stop the loop.
            log_error_event(
                logger,
                error_code="RETENTION_RPC_FAILED",
                subsystem="maintenance",
                message=f"retention RPC {job.rpc} returned non-200",
                details={"rpc": job.rpc, "status_code": response.status_code},
            )
        except httpx.HTTPError:
            log_error_event(
                logger,
                error_code="RETENTION_RPC_HTTP_ERROR",
                subsystem="maintenance",
                message=f"retention RPC {job.rpc} HTTP error",
                details={"rpc": job.rpc},
            )
        except Exception:
            log_error_event(
                logger,
                error_code="RETENTION_RPC_UNEXPECTED",
                subsystem="maintenance",
                message=f"retention RPC {job.rpc} unexpected error",
                details={"rpc": job.rpc},
                include_exception=True,
            )
    return removed
