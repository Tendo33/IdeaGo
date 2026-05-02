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
from ideago.billing.stripe_service import delete_customer_data
from ideago.config.settings import get_settings
from ideago.observability.error_catalog import log_error_event
from ideago.observability.log_config import get_logger
from ideago.observability.metrics import metrics as app_metrics

logger = get_logger(__name__)
_DAILY_ANALYSIS_LIMIT = 5
_DAILY_PLAN_NAME = "daily"

_http_client: httpx.AsyncClient | None = None


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
    return _DAILY_ANALYSIS_LIMIT


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
    """Best-effort refund for a previously charged analysis slot."""
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
            "quota refund RPC failed, falling back to profile patch: {} {}",
            rpc_resp.status_code,
            rpc_resp.text,
        )
    except Exception:
        logger.opt(exception=True).warning(
            "quota refund RPC error for {}, falling back to profile patch", user_id
        )

    profile = await get_profile(user_id)
    if profile.get("error"):
        logger.warning("quota refund skipped; profile missing for {}", user_id)
        return False

    current_usage = profile.get("usage_count", 0)
    if not isinstance(current_usage, int):
        logger.warning("quota refund skipped; invalid usage_count for {}", user_id)
        return False

    next_usage = max(0, current_usage - 1)
    try:
        patch_resp = await client.patch(
            f"{settings.supabase_url}/rest/v1/profiles",
            headers={**_headers(), "Prefer": "return=minimal"},
            params={"id": f"eq.{user_id}"},
            json={"usage_count": next_usage},
        )
        if patch_resp.status_code not in (200, 204):
            logger.warning(
                "quota refund failed: {} {}", patch_resp.status_code, patch_resp.text
            )
            return False
        return True
    except Exception:
        logger.opt(exception=True).warning("quota refund error for {}", user_id)
        return False


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
            logger.warning("Get profile failed: {} {}", resp.status_code, resp.text)
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
                resp.text,
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
                resp.text,
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
                resp.text,
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
            logger.warning("list_profiles failed: {} {}", resp.status_code, resp.text)
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
            logger.warning("set_user_quota failed: {} {}", resp.status_code, resp.text)
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


async def delete_user_data(user_id: str) -> dict:
    """Cascade-delete domain data for a user while leaving tombstone profile in place."""
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


def _record_stuck_pending_deletion(
    user_id: str,
    *,
    phase: str,
    details: list[str],
) -> None:
    app_metrics.increment_event("account_delete_stuck_pending", reason=phase)
    log_error_event(
        logger,
        error_code="ACCOUNT_DELETE_STUCK_PENDING",
        subsystem="account_delete",
        message="Account deletion remains in deletion_pending after partial failure",
        details={
            "user_id": user_id,
            "phase": phase,
            "details": details,
        },
    )


async def _rollback_failed_account_deletion(
    user_id: str,
    *,
    phase: str,
    details: list[str],
    cleanup: dict[str, str],
) -> dict:
    app_metrics.increment_event("account_delete_rollback_triggered", reason=phase)
    log_error_event(
        logger,
        error_code="ACCOUNT_DELETE_ROLLBACK_TRIGGERED",
        subsystem="account_delete",
        message="Rolling back deletion_pending after partial account deletion failure",
        details={"user_id": user_id, "phase": phase},
    )
    rollback_profile_state = "rolled_back"
    if phase in {"domain_data_cleanup", "auth_identity_cleanup"}:
        rollback_profile_state = "restored_access_only"
    rollback = await restore_profile_after_failed_deletion(user_id)
    if rollback.get("error"):
        cleanup["profile"] = "rollback_failed"
        rollback_details = details + list(
            rollback.get("details") or [str(rollback.get("error"))]
        )
        _record_stuck_pending_deletion(
            user_id,
            phase=phase,
            details=rollback_details,
        )
        return _account_cleanup_error(
            phase=phase,
            details=rollback_details,
            cleanup=cleanup,
        )
    cleanup["profile"] = rollback_profile_state
    return _account_cleanup_error(phase=phase, details=details, cleanup=cleanup)


async def delete_user_account(user_id: str) -> dict:
    """Delete app data, billing artifacts, and auth identity in explicit phases."""
    cleanup = {
        "domain_data": "pending",
        "billing": "pending",
        "auth_identity": "pending",
        "profile": "pending",
    }

    profile_mark_result = await mark_profile_deletion_pending(user_id)
    if profile_mark_result.get("error"):
        cleanup["profile"] = "failed"
        return _account_cleanup_error(
            phase="profile_delete_mark",
            details=list(
                profile_mark_result.get("details")
                or [str(profile_mark_result["error"])]
            ),
            cleanup=cleanup,
        )
    cleanup["profile"] = "deletion_pending"

    billing_result = await delete_billing_customer_data(user_id)
    if billing_result.get("error"):
        cleanup["billing"] = "failed"
        return await _rollback_failed_account_deletion(
            user_id,
            phase="billing_cleanup",
            details=list(billing_result.get("details") or [billing_result["error"]]),
            cleanup=cleanup,
        )
    cleanup["billing"] = str(billing_result.get("status") or "skipped")

    domain_result = await delete_user_data(user_id)
    if domain_result.get("error"):
        cleanup["domain_data"] = "failed"
        return await _rollback_failed_account_deletion(
            user_id,
            phase="domain_data_cleanup",
            details=list(domain_result.get("details") or [domain_result["error"]]),
            cleanup=cleanup,
        )
    cleanup["domain_data"] = "deleted"

    auth_result = await delete_auth_identity(user_id)
    if auth_result.get("error"):
        cleanup["auth_identity"] = "failed"
        return await _rollback_failed_account_deletion(
            user_id,
            phase="auth_identity_cleanup",
            details=list(auth_result.get("details") or [auth_result["error"]]),
            cleanup=cleanup,
        )
    cleanup["auth_identity"] = str(auth_result.get("status") or "skipped")

    profile_delete_result = await delete_profile_record(user_id)
    if profile_delete_result.get("error"):
        cleanup["profile"] = "deletion_pending"
        details = list(
            profile_delete_result.get("details")
            or [str(profile_delete_result["error"])]
        )
        _record_stuck_pending_deletion(
            user_id,
            phase="profile_delete_finalize",
            details=details,
        )
        return _account_cleanup_error(
            phase="profile_delete_finalize",
            details=details,
            cleanup=cleanup,
        )
    cleanup["profile"] = "deleted"

    return {"status": "deleted", "cleanup": cleanup}
