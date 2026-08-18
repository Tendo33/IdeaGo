"""Supabase admin client for backend-only DB operations.

Uses service_role key to bypass RLS. Only used server-side for:
- Quota enforcement (check_and_increment_quota)
- Quota reads (get_quota_info)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

from ideago.api.errors import DependencyUnavailableError
from ideago.auth import session_cache
from ideago.config.settings import get_settings
from ideago.observability.error_catalog import log_error_event
from ideago.observability.log_config import get_logger
from ideago.observability.metrics import metrics as app_metrics

logger = get_logger(__name__)
_DAILY_PLAN_NAME = "daily"


def _daily_analysis_limit() -> int:
    """Default daily quota.

    Read from settings rather than hard-coded so the free tier can be changed
    without a deploy. Must stay in step with public.get_plan_limit() in the
    database, which is the authority for the RPC path.
    """
    return int(getattr(get_settings(), "daily_analysis_limit", 5))


_http_client: httpx.AsyncClient | None = None

# PostgREST error bodies routinely echo table names, column names, constraint
# names and — with `Prefer: return=representation` — whole profile rows. Logging
# them verbatim puts PII and schema details into logs and Sentry breadcrumbs.
# Keep only the machine-readable error code.
_SAFE_ERROR_KEYS = ("code", "error", "error_code")


def _safe_upstream_detail(response: httpx.Response) -> str:
    """Summarize a failed PostgREST response without echoing its body.

    Returns the upstream error code when the payload exposes one, otherwise a
    content-free marker. Never returns caller data.
    """
    try:
        payload = response.json()
    except Exception:
        return "unparseable_body"
    if not isinstance(payload, dict):
        return "non_object_body"
    for key in _SAFE_ERROR_KEYS:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            # PostgREST codes are short SQLSTATE-ish tokens, safe to log.
            return value.strip()[:64]
    return "no_error_code"


def _escape_ilike_term(value: str) -> str:
    """Escape PostgREST ilike wildcards so admin search stays literal."""
    return (
        value.replace("\\", r"\\")
        .replace("%", r"\%")
        .replace("_", r"\_")
        .replace("*", r"\*")
        .replace(",", r"\,")
        .replace("(", r"\(")
        .replace(")", r"\)")
    )


class BillingProfileLookupError(RuntimeError):
    """Raised when billing identifiers cannot be safely loaded from profile."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


def _coerce_plan_limit(override: object) -> int:
    if isinstance(override, int) and override >= 0:
        return override
    return _daily_analysis_limit()


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
            plan_limit=_daily_analysis_limit(),
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
            logger.warning(
                "Quota RPC failed: {} {}", resp.status_code, _safe_upstream_detail(resp)
            )
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


async def check_quota_available(user_id: str) -> QuotaResult:
    """Read quota without consuming usage and evaluate whether work is allowed."""
    info = await get_quota_info(user_id)
    if info.get("error"):
        error = str(info["error"])
        return QuotaResult(
            allowed=False,
            usage_count=0,
            plan_limit=0,
            plan="unknown",
            error=error,
        )

    usage_count = int(info.get("usage_count", 0) or 0)
    plan_limit = int(info.get("plan_limit", 0) or 0)
    plan = str(info.get("plan", _DAILY_PLAN_NAME) or _DAILY_PLAN_NAME)
    allowed = plan_limit <= 0 or usage_count < plan_limit
    return QuotaResult(
        allowed=allowed,
        usage_count=usage_count,
        plan_limit=plan_limit,
        plan=plan,
        error="" if allowed else "quota_exceeded",
    )


async def refund_quota_charge(user_id: str) -> bool:
    """Refund a previously charged analysis slot.

    Only the atomic RPC is used. The previous fallback read ``usage_count`` and
    wrote back ``value - 1``, which loses updates: two concurrent refunds both
    read 5 and both write 4, so one refund silently vanishes. A missed refund is
    recorded for reconciliation instead of being papered over with a racy write.
    """
    if not _is_configured():
        return True

    settings = get_settings()
    client = _get_client()
    try:
        rpc_resp = await client.post(
            f"{settings.supabase_url}/rest/v1/rpc/refund_quota_charge",
            headers=_headers(),
            json={"p_user_id": user_id},
        )
        if rpc_resp.status_code in (200, 204):
            return True
        logger.warning(
            "quota refund RPC failed: {} {}",
            rpc_resp.status_code,
            _safe_upstream_detail(rpc_resp),
        )
        reason = f"rpc_{rpc_resp.status_code}"
    except Exception:
        logger.opt(exception=True).warning("quota refund RPC error for {}", user_id)
        reason = "rpc_exception"

    app_metrics.increment_event("quota_refund_failed", reason=reason)
    log_error_event(
        logger,
        error_code="QUOTA_REFUND_FAILED",
        subsystem="quota",
        message="Quota refund could not be applied; user was charged for work "
        "that did not complete",
        details={"user_id": user_id, "reason": reason},
    )
    return False


async def get_quota_info(user_id: str) -> dict:
    """Read-only quota info for display purposes."""
    if not _is_configured():
        return {
            "usage_count": 0,
            "plan_limit": _daily_analysis_limit(),
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
            logger.warning(
                "Quota info RPC failed: {} {}",
                resp.status_code,
                _safe_upstream_detail(resp),
            )
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
    existing = await get_profile(user_id)
    if isinstance(existing, dict):
        if not existing.get("error"):
            return not bool(
                existing.get("deletion_pending") or existing.get("deleted_at")
            )
        if existing.get("error") != "profile_not_found":
            return False
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
        logger.warning(
            "Profile upsert failed: {} {}",
            resp.status_code,
            _safe_upstream_detail(resp),
        )
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
            "usage_count": 0,
        }

    settings = get_settings()
    client = _get_client()
    params = {
        "id": f"eq.{user_id}",
        "select": "display_name,avatar_url,bio,created_at,role,usage_count,deletion_pending,deleted_at",
        "limit": "1",
    }
    try:
        resp = await client.get(
            f"{settings.supabase_url}/rest/v1/profiles",
            headers={**_headers(), "Accept": "application/json"},
            params=params,
        )
        # Control flow, not logging: older schemas lack the column and PostgREST
        # names it in the 400 body. Inspect the raw text here, never log it.
        if resp.status_code == 400 and "deletion_pending" in resp.text:
            resp = await client.get(
                f"{settings.supabase_url}/rest/v1/profiles",
                headers={**_headers(), "Accept": "application/json"},
                params={
                    **params,
                    "select": "display_name,avatar_url,bio,created_at,role,usage_count",
                },
            )
        if resp.status_code != 200:
            logger.warning(
                "Get profile failed: {} {}",
                resp.status_code,
                _safe_upstream_detail(resp),
            )
            return {"error": "profile_fetch_failed"}
        rows = resp.json()
        if isinstance(rows, list) and rows:
            row = rows[0]
            if isinstance(row, dict):
                row.setdefault("deletion_pending", False)
                row.setdefault("deleted_at", None)
                return row
        return {"error": "profile_not_found"}
    except Exception:
        logger.opt(exception=True).warning("Get profile error")
        return {"error": "network_error"}


async def mark_profile_deletion_pending(user_id: str) -> dict:
    """Mark a profile as deleting to block recreation and session refresh."""
    # Cached liveness would otherwise keep the account usable for up to the
    # cache TTL after it has been marked for deletion.
    session_cache.invalidate_user(user_id)
    if not _is_configured():
        return {"error": "supabase_not_configured"}

    settings = get_settings()
    client = _get_client()
    try:
        resp = await client.patch(
            f"{settings.supabase_url}/rest/v1/profiles",
            headers={**_headers(), "Prefer": "return=representation"},
            params={
                "id": f"eq.{user_id}",
                "select": "id,deletion_pending,deleted_at",
            },
            json={
                "deletion_pending": True,
                "deleted_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        if resp.status_code != 200:
            logger.warning(
                "mark_profile_deletion_pending failed: {} {}",
                resp.status_code,
                _safe_upstream_detail(resp),
            )
            return {"error": "profile_delete_mark_failed"}
        rows = resp.json()
        if isinstance(rows, list) and rows:
            row = rows[0]
            if isinstance(row, dict):
                return row
        return {"error": "profile_not_found"}
    except Exception:
        logger.opt(exception=True).warning("mark_profile_deletion_pending error")
        return {"error": "network_error"}


async def delete_profile_record(user_id: str) -> dict:
    """Delete the profile row after the rest of account cleanup succeeds."""
    if not _is_configured():
        return {"error": "supabase_not_configured"}

    settings = get_settings()
    client = _get_client()
    try:
        resp = await client.delete(
            f"{settings.supabase_url}/rest/v1/profiles",
            headers={**_headers(), "Prefer": "return=minimal"},
            params={"id": f"eq.{user_id}"},
        )
        if resp.status_code not in (200, 204):
            logger.warning(
                "delete_profile_record failed: {} {}",
                resp.status_code,
                _safe_upstream_detail(resp),
            )
            return {
                "error": "profile_delete_failed",
                "details": [f"profiles: {resp.status_code}"],
            }
        return {"status": "deleted"}
    except Exception:
        logger.opt(exception=True).warning("delete_profile_record error")
        return {"error": "profile_delete_failed", "details": ["profiles: exception"]}


async def restore_profile_after_failed_deletion(user_id: str) -> dict:
    """Clear deletion markers so a partially failed deletion can be retried safely."""
    if not _is_configured():
        return {"error": "supabase_not_configured"}

    settings = get_settings()
    client = _get_client()
    try:
        resp = await client.patch(
            f"{settings.supabase_url}/rest/v1/profiles",
            headers={**_headers(), "Prefer": "return=representation"},
            params={
                "id": f"eq.{user_id}",
                "select": "id,deletion_pending,deleted_at",
            },
            json={
                "deletion_pending": False,
                "deleted_at": None,
            },
        )
        if resp.status_code != 200:
            logger.warning(
                "restore_profile_after_failed_deletion failed: {} {}",
                resp.status_code,
                _safe_upstream_detail(resp),
            )
            return {
                "error": "profile_delete_restore_failed",
                "details": [f"profiles: {resp.status_code}"],
            }
        rows = resp.json()
        if isinstance(rows, list) and rows:
            row = rows[0]
            if isinstance(row, dict):
                return row
        return {"error": "profile_not_found"}
    except Exception:
        logger.opt(exception=True).warning(
            "restore_profile_after_failed_deletion error"
        )
        return {
            "error": "profile_delete_restore_failed",
            "details": ["profiles: exception"],
        }


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
            logger.warning(
                "Update profile failed: {} {}",
                resp.status_code,
                _safe_upstream_detail(resp),
            )
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


async def list_profiles(
    *, limit: int = 50, offset: int = 0, q: str = ""
) -> tuple[list[dict], int]:
    """List all user profiles (admin only). Returns rows plus total count."""
    if not _is_configured():
        return [], 0

    settings = get_settings()
    client = _get_client()
    try:
        params = {
            "select": "id,display_name,avatar_url,bio,created_at,plan,usage_count,plan_limit_override,role,auth_provider,deletion_pending,deleted_at",
            "order": "created_at.desc",
            "limit": str(limit),
            "offset": str(offset),
            "deletion_pending": "eq.false",
        }
        normalized_q = q.strip()
        if normalized_q:
            escaped = _escape_ilike_term(normalized_q)
            params["or"] = f"(display_name.ilike.*{escaped}*,id.ilike.*{escaped}*)"
        resp = await client.get(
            f"{settings.supabase_url}/rest/v1/profiles",
            headers={
                **_headers(),
                "Accept": "application/json",
                "Prefer": "count=exact",
            },
            params=params,
        )
        # Control flow, not logging: older schemas lack the column and PostgREST
        # names it in the 400 body. Inspect the raw text here, never log it.
        if resp.status_code == 400 and "deletion_pending" in resp.text:
            fallback_params = dict(params)
            fallback_params.pop("deletion_pending", None)
            fallback_params["select"] = (
                "id,display_name,avatar_url,bio,created_at,plan,usage_count,plan_limit_override,role,auth_provider"
            )
            resp = await client.get(
                f"{settings.supabase_url}/rest/v1/profiles",
                headers={
                    **_headers(),
                    "Accept": "application/json",
                    "Prefer": "count=exact",
                },
                params=fallback_params,
            )
        if resp.status_code != 200:
            logger.warning(
                "list_profiles failed: {} {}",
                resp.status_code,
                _safe_upstream_detail(resp),
            )
            raise DependencyUnavailableError(
                "profiles_list_failed", dependency="supabase_profiles"
            )
        rows = resp.json()
        if not isinstance(rows, list):
            raise DependencyUnavailableError(
                "profiles_list_invalid_payload", dependency="supabase_profiles"
            )
        normalized: list[dict] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            payload = dict(row)
            payload.setdefault("deletion_pending", False)
            payload.setdefault("deleted_at", None)
            payload["plan_limit"] = _coerce_plan_limit(
                payload.pop("plan_limit_override", None)
            )
            normalized.append(payload)
        content_range = resp.headers.get("content-range", "")
        total = 0
        if "/" in content_range:
            total_raw = content_range.split("/")[-1]
            if total_raw.isdigit():
                total = int(total_raw)
        return normalized, total
    except DependencyUnavailableError:
        raise
    except Exception as err:
        logger.opt(exception=True).warning("list_profiles error")
        raise DependencyUnavailableError(
            "profiles_list_network_error", dependency="supabase_profiles"
        ) from err


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
        payload["plan_limit_override"] = plan_limit
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
                "select": "id,display_name,plan,usage_count,plan_limit_override,role",
            },
            json=payload,
        )
        if resp.status_code != 200:
            logger.warning(
                "set_user_quota failed: {} {}",
                resp.status_code,
                _safe_upstream_detail(resp),
            )
            raise DependencyUnavailableError(
                "quota_update_failed", dependency="supabase_profiles"
            )
        rows = resp.json()
        if isinstance(rows, list) and rows:
            updated = dict(rows[0])
            updated["plan_limit"] = _coerce_plan_limit(
                updated.pop("plan_limit_override", None)
            )
            return updated
        return {"error": "user_not_found"}
    except DependencyUnavailableError:
        raise
    except Exception as err:
        logger.opt(exception=True).warning("set_user_quota error")
        raise DependencyUnavailableError(
            "quota_update_network_error", dependency="supabase_profiles"
        ) from err


# The account-deletion saga lives in `account_deletion.py`. Re-exported here so
# existing imports (and their patch targets in tests) keep working.
from ideago.auth.account_deletion import (  # noqa: E402
    delete_auth_identity,
    delete_billing_customer_data,
    delete_user_account,
    delete_user_data,
)

__all__ = [
    "delete_auth_identity",
    "delete_billing_customer_data",
    "delete_user_account",
    "delete_user_data",
]
