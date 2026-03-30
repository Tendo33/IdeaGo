"""Supabase admin client for backend-only DB operations.

Uses service_role key to bypass RLS. Only used server-side for:
- Quota enforcement (check_and_increment_quota)
- Quota reads (get_quota_info)
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from ideago.config.settings import get_settings
from ideago.observability.log_config import get_logger

logger = get_logger(__name__)
_DAILY_ANALYSIS_LIMIT = 5
_DAILY_PLAN_NAME = "daily"

_http_client: httpx.AsyncClient | None = None


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
