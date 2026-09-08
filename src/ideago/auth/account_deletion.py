"""Account deletion saga.

Deleting an account touches three systems that cannot share a transaction:
PostgREST domain tables, Stripe, and Supabase auth. The work is therefore an
explicit multi-phase saga with compensations, and the phase names and cleanup
states are part of the API contract — the frontend picks its wording from them
(see `getDeleteAccountErrorMessage` in ProfilePage.tsx) and

Split out of `supabase_admin.py`, which had grown to mix plain PostgREST data
access with this orchestration.
"""

from __future__ import annotations

# Imported as a module, not by name. These helpers are owned by
# supabase_admin; binding them here would shadow the originals and silently
# break every monkeypatch that targets `supabase_admin.<helper>`.
from ideago.auth import session_cache, supabase_admin
from ideago.auth.supabase_admin import BillingProfileLookupError
from ideago.billing.stripe_service import delete_customer_data
from ideago.config.settings import get_settings
from ideago.observability.error_catalog import log_error_event
from ideago.observability.log_config import get_logger
from ideago.observability.metrics import metrics as app_metrics

logger = get_logger(__name__)


async def delete_user_data(user_id: str) -> dict:
    """Cascade-delete domain data for a user while leaving tombstone profile in place."""
    if not supabase_admin._is_configured():
        return {"error": "supabase_not_configured"}

    settings = get_settings()
    client = supabase_admin._get_client()
    headers = supabase_admin._headers()
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
    if not supabase_admin._is_configured():
        return "", ""

    settings = get_settings()
    client = supabase_admin._get_client()
    try:
        resp = await client.get(
            f"{settings.supabase_url}/rest/v1/profiles",
            headers={**supabase_admin._headers(), "Accept": "application/json"},
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
                supabase_admin._safe_upstream_detail(resp),
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
    if not supabase_admin._is_configured():
        return {"status": "skipped"}

    settings = get_settings()
    client = supabase_admin._get_client()
    try:
        resp = await client.delete(
            f"{settings.supabase_url}/auth/v1/admin/users/{user_id}",
            headers=supabase_admin._headers(),
        )
        if resp.status_code in (200, 204, 404):
            return {"status": "deleted"}
        logger.warning(
            "delete_auth_identity failed for {}: {} {}",
            user_id,
            resp.status_code,
            supabase_admin._safe_upstream_detail(resp),
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
    rollback = await supabase_admin.restore_profile_after_failed_deletion(user_id)
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
    session_cache.invalidate_user(user_id)
    cleanup = {
        "domain_data": "pending",
        "billing": "pending",
        "auth_identity": "pending",
        "profile": "pending",
    }

    profile_mark_result = await supabase_admin.mark_profile_deletion_pending(user_id)
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

    profile_delete_result = await supabase_admin.delete_profile_record(user_id)
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
