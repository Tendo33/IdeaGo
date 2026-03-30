"""Supabase admin client for backend-only DB operations.

Uses service_role key to bypass RLS. Only used server-side for:
- Quota enforcement (check_and_increment_quota)
- Quota reads (get_quota_info)
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from ideago.billing.stripe_service import delete_customer_data
from ideago.config.settings import get_settings
from ideago.observability.log_config import get_logger

logger = get_logger(__name__)
_DAILY_ANALYSIS_LIMIT = 5
_DAILY_PLAN_NAME = "daily"

_http_client: httpx.AsyncClient | None = None


class BillingProfileLookupError(RuntimeError):
    """Raised when billing identifiers cannot be safely loaded from profile."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


def _get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            timeout=10.0,
            limits=httpx.Limits(
                max_connections=50,
                max_keepalive_connections=20,
            ),
        )
    return _http_client


async def close_supabase_admin_client() -> None:
    global _http_client
    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None


def _headers() -> dict[str, str]:
    settings = get_settings()
    return {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Content-Type": "application/json",
    }


def _is_configured() -> bool:
    settings = get_settings()
    return bool(settings.supabase_url and settings.supabase_service_role_key)


@dataclass
class QuotaResult:
    allowed: bool
    usage_count: int
    plan_limit: int
    plan: str
    error: str = ""


async def check_and_increment_quota(user_id: str) -> QuotaResult:
    """Call the DB function to atomically check + increment quota.

    Returns a QuotaResult. If Supabase is not configured, allows by default
    (graceful degradation for local dev without Supabase).
    When configured but the RPC fails, denies by default to prevent abuse.
    """
    if not _is_configured():
        logger.debug("Supabase not configured; skipping quota check")
        return QuotaResult(
            allowed=True,
            usage_count=0,
            plan_limit=_DAILY_ANALYSIS_LIMIT,
            plan=_DAILY_PLAN_NAME,
        )

    settings = get_settings()
    client = _get_client()
    try:
        resp = await client.post(
            f"{settings.supabase_url}/rest/v1/rpc/check_and_increment_quota",
            headers=_headers(),
            json={"p_user_id": user_id},
        )
        if resp.status_code != 200:
            logger.warning("Quota RPC failed: {} {}", resp.status_code, resp.text)
            return QuotaResult(
                allowed=False,
                usage_count=0,
                plan_limit=0,
                plan="unknown",
                error="quota_check_failed",
            )
        data = resp.json()
        return QuotaResult(
            allowed=data.get("allowed", True),
            usage_count=data.get("usage_count", 0),
            plan_limit=data.get("plan_limit", 0),
            plan=data.get("plan", "free"),
            error=data.get("error", ""),
        )
    except Exception:
        logger.opt(exception=True).warning("Quota check error")
        return QuotaResult(
            allowed=False,
            usage_count=0,
            plan_limit=0,
            plan="unknown",
            error="quota_check_error",
        )


async def get_quota_info(user_id: str) -> dict:
    """Read-only quota info for display purposes."""
    if not _is_configured():
        return {
            "usage_count": 0,
            "plan_limit": _DAILY_ANALYSIS_LIMIT,
            "plan": _DAILY_PLAN_NAME,
            "reset_at": "",
        }

    settings = get_settings()
    client = _get_client()
    try:
        resp = await client.post(
            f"{settings.supabase_url}/rest/v1/rpc/get_quota_info",
            headers=_headers(),
            json={"p_user_id": user_id},
        )
        if resp.status_code != 200:
            logger.warning("Quota info RPC failed: {} {}", resp.status_code, resp.text)
            return {"error": "rpc_failed"}
        return resp.json()
    except Exception:
        logger.opt(exception=True).warning("Quota info error")
        return {"error": "network_error"}


async def ensure_profile_exists(
    user_id: str,
    *,
    display_name: str = "",
    avatar_url: str = "",
    bio: str = "",
    auth_provider: str = "supabase",
) -> bool:
    """Create a profile row when missing (idempotent upsert)."""
    if not _is_configured():
        return False

    settings = get_settings()
    client = _get_client()
    payload: dict[str, str] = {
        "id": user_id,
        "display_name": display_name,
        "avatar_url": avatar_url,
        "bio": bio,
        "auth_provider": auth_provider,
    }
    try:
        resp = await client.post(
            f"{settings.supabase_url}/rest/v1/profiles",
            headers={
                **_headers(),
                "Prefer": "resolution=ignore-duplicates,return=minimal",
            },
            json=payload,
        )
        if resp.status_code in (200, 201, 204):
            return True
        logger.warning("Profile upsert failed: {} {}", resp.status_code, resp.text)
    except Exception:
        logger.opt(exception=True).warning("Profile upsert error")
    return False


async def get_profile(user_id: str) -> dict:
    """Return one profile row for the given user id."""
    if not _is_configured():
        return {
            "display_name": "",
            "avatar_url": "",
            "bio": "",
            "created_at": "",
        }

    settings = get_settings()
    client = _get_client()
    try:
        resp = await client.get(
            f"{settings.supabase_url}/rest/v1/profiles",
            headers={**_headers(), "Accept": "application/json"},
            params={
                "id": f"eq.{user_id}",
                "select": "display_name,avatar_url,bio,created_at,role",
                "limit": "1",
            },
        )
        if resp.status_code != 200:
            logger.warning("Get profile failed: {} {}", resp.status_code, resp.text)
            return {"error": "profile_fetch_failed"}
        rows = resp.json()
        if isinstance(rows, list) and rows:
            row = rows[0]
            if isinstance(row, dict):
                return row
        return {"error": "profile_not_found"}
    except Exception:
        logger.opt(exception=True).warning("Get profile error")
        return {"error": "network_error"}


async def update_profile(user_id: str, *, display_name: str, bio: str) -> dict:
    """Update profile fields and return latest values."""
    if not _is_configured():
        return {
            "display_name": display_name,
            "avatar_url": "",
            "bio": bio,
            "created_at": "",
        }

    settings = get_settings()
    client = _get_client()
    try:
        resp = await client.patch(
            f"{settings.supabase_url}/rest/v1/profiles",
            headers={**_headers(), "Prefer": "return=representation"},
            params={
                "id": f"eq.{user_id}",
                "select": "display_name,avatar_url,bio,created_at",
            },
            json={"display_name": display_name, "bio": bio},
        )
        if resp.status_code != 200:
            logger.warning("Update profile failed: {} {}", resp.status_code, resp.text)
            return {"error": "profile_update_failed"}
        rows = resp.json()
        if isinstance(rows, list) and rows:
            row = rows[0]
            if isinstance(row, dict):
                return row
        return {"error": "profile_not_found"}
    except Exception:
        logger.opt(exception=True).warning("Update profile error")
        return {"error": "network_error"}


async def list_profiles(*, limit: int = 50, offset: int = 0) -> list[dict]:
    """List all user profiles (admin only). Returns a list of profile dicts."""
    if not _is_configured():
        return []

    settings = get_settings()
    client = _get_client()
    try:
        resp = await client.get(
            f"{settings.supabase_url}/rest/v1/profiles",
            headers={
                **_headers(),
                "Accept": "application/json",
                "Prefer": "count=exact",
            },
            params={
                "select": "id,display_name,avatar_url,bio,created_at,plan,usage_count,plan_limit,role,auth_provider",
                "order": "created_at.desc",
                "limit": str(limit),
                "offset": str(offset),
            },
        )
        if resp.status_code != 200:
            logger.warning("list_profiles failed: {} {}", resp.status_code, resp.text)
            return []
        rows = resp.json()
        return rows if isinstance(rows, list) else []
    except Exception:
        logger.opt(exception=True).warning("list_profiles error")
        return []


async def set_user_quota(
    user_id: str, *, plan_limit: int | None = None, usage_count: int | None = None
) -> dict:
    """Admin adjustment of a user's quota fields."""
    if not _is_configured():
        return {"error": "supabase_not_configured"}

    settings = get_settings()
    client = _get_client()
    payload: dict[str, int] = {}
    if plan_limit is not None:
        payload["plan_limit"] = plan_limit
    if usage_count is not None:
        payload["usage_count"] = usage_count
    if not payload:
        return {"error": "nothing_to_update"}

    try:
        resp = await client.patch(
            f"{settings.supabase_url}/rest/v1/profiles",
            headers={**_headers(), "Prefer": "return=representation"},
            params={
                "id": f"eq.{user_id}",
                "select": "id,display_name,plan,usage_count,plan_limit,role",
            },
            json=payload,
        )
        if resp.status_code != 200:
            logger.warning("set_user_quota failed: {} {}", resp.status_code, resp.text)
            return {"error": "update_failed"}
        rows = resp.json()
        if isinstance(rows, list) and rows:
            return rows[0]
        return {"error": "user_not_found"}
    except Exception:
        logger.opt(exception=True).warning("set_user_quota error")
        return {"error": "network_error"}


async def delete_user_data(user_id: str) -> dict:
    """Cascade-delete all data for a user (GDPR / account deletion).

    Deletes: reports, report_status, processing_reports, profile.
    Returns {"deleted": True} on success, {"error": ...} on failure.
    """
    if not _is_configured():
        return {"error": "supabase_not_configured"}

    settings = get_settings()
    client = _get_client()
    headers = _headers()
    base = settings.supabase_url
    errors: list[str] = []

    for table, filter_col in [
        ("reports", "user_id"),
        ("report_status", "user_id"),
        ("processing_reports", "user_id"),
    ]:
        try:
            resp = await client.delete(
                f"{base}/rest/v1/{table}",
                headers=headers,
                params={filter_col: f"eq.{user_id}"},
            )
            if resp.status_code not in (200, 204):
                errors.append(f"{table}: {resp.status_code}")
        except Exception:
            logger.opt(exception=True).warning("delete_user_data: {} failed", table)
            errors.append(f"{table}: exception")

    try:
        resp = await client.delete(
            f"{base}/rest/v1/profiles",
            headers=headers,
            params={"id": f"eq.{user_id}"},
        )
        if resp.status_code not in (200, 204):
            errors.append(f"profiles: {resp.status_code}")
    except Exception:
        logger.opt(exception=True).warning("delete_user_data: profiles failed")
        errors.append("profiles: exception")

    if errors:
        logger.warning("delete_user_data partial failure for {}: {}", user_id, errors)
        return {"error": "partial_failure", "details": errors}

    logger.info("All data deleted for user {}", user_id)
    return {"deleted": True}


async def _get_profile_billing_ids(user_id: str) -> tuple[str, str]:
    """Return Stripe customer/subscription ids for a profile when present."""
    if not _is_configured():
        return "", ""

    settings = get_settings()
    client = _get_client()
    try:
        resp = await client.get(
            f"{settings.supabase_url}/rest/v1/profiles",
            headers={**_headers(), "Accept": "application/json"},
            params={
                "id": f"eq.{user_id}",
                "select": "stripe_customer_id,stripe_subscription_id",
                "limit": "1",
            },
        )
        if resp.status_code != 200:
            logger.warning(
                "Failed to load billing ids for {}: {} {}",
                user_id,
                resp.status_code,
                resp.text,
            )
            raise BillingProfileLookupError(
                f"billing_profile_lookup: {resp.status_code}"
            )
        rows = resp.json()
        if isinstance(rows, list) and rows:
            row = rows[0]
            if isinstance(row, dict):
                return (
                    str(row.get("stripe_customer_id") or "").strip(),
                    str(row.get("stripe_subscription_id") or "").strip(),
                )
        return "", ""
    except BillingProfileLookupError:
        raise
    except Exception as err:
        logger.opt(exception=True).warning("Failed to load billing ids for {}", user_id)
        raise BillingProfileLookupError("billing_profile_lookup: exception") from err


async def delete_billing_customer_data(user_id: str) -> dict:
    """Delete Stripe-side billing artifacts for a user when configured."""
    try:
        customer_id, subscription_id = await _get_profile_billing_ids(user_id)
    except BillingProfileLookupError as exc:
        return {"error": "billing_lookup_failed", "details": [exc.detail]}
    return await delete_customer_data(
        customer_id=customer_id or None,
        subscription_id=subscription_id or None,
    )


async def delete_auth_identity(user_id: str) -> dict:
    """Delete the upstream Supabase auth identity for a user when configured."""
    if not _is_configured():
        return {"status": "skipped"}

    settings = get_settings()
    client = _get_client()
    try:
        resp = await client.delete(
            f"{settings.supabase_url}/auth/v1/admin/users/{user_id}",
            headers=_headers(),
        )
        if resp.status_code in (200, 204, 404):
            return {"status": "deleted"}
        logger.warning(
            "delete_auth_identity failed for {}: {} {}",
            user_id,
            resp.status_code,
            resp.text,
        )
        return {
            "error": "auth_identity_delete_failed",
            "details": [f"auth_identity: {resp.status_code}"],
        }
    except Exception:
        logger.opt(exception=True).warning("delete_auth_identity error for {}", user_id)
        return {
            "error": "auth_identity_delete_failed",
            "details": ["auth_identity: exception"],
        }


def _account_cleanup_error(
    *,
    phase: str,
    details: list[str],
    cleanup: dict[str, str],
) -> dict:
    return {
        "error": "partial_failure",
        "phase": phase,
        "details": details,
        "cleanup": cleanup,
    }


async def delete_user_account(user_id: str) -> dict:
    """Delete app data, billing artifacts, and auth identity in explicit phases."""
    cleanup = {
        "domain_data": "pending",
        "billing": "pending",
        "auth_identity": "pending",
    }

    billing_result = await delete_billing_customer_data(user_id)
    if billing_result.get("error"):
        cleanup["billing"] = "failed"
        return _account_cleanup_error(
            phase="billing_cleanup",
            details=list(billing_result.get("details") or [billing_result["error"]]),
            cleanup=cleanup,
        )
    cleanup["billing"] = str(billing_result.get("status") or "skipped")

    domain_result = await delete_user_data(user_id)
    if domain_result.get("error"):
        cleanup["domain_data"] = "failed"
        return _account_cleanup_error(
            phase="domain_data_cleanup",
            details=list(domain_result.get("details") or [domain_result["error"]]),
            cleanup=cleanup,
        )
    cleanup["domain_data"] = "deleted"

    auth_result = await delete_auth_identity(user_id)
    if auth_result.get("error"):
        cleanup["auth_identity"] = "failed"
        return _account_cleanup_error(
            phase="auth_identity_cleanup",
            details=list(auth_result.get("details") or [auth_result["error"]]),
            cleanup=cleanup,
        )
    cleanup["auth_identity"] = str(auth_result.get("status") or "skipped")

    return {"status": "deleted", "cleanup": cleanup}
