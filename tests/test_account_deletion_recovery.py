from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from ideago.auth import supabase_admin
from ideago.observability.metrics import metrics as app_metrics


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("phase_patch", "phase_name", "expected_profile_state", "restore_expected"),
    [
        ("delete_billing_customer_data", "billing_cleanup", "rolled_back", True),
        ("delete_user_data", "domain_data_cleanup", "restored_access_only", True),
        ("delete_auth_identity", "auth_identity_cleanup", "restored_access_only", True),
        ("delete_profile_record", "profile_delete_finalize", "deletion_pending", False),
    ],
)
async def test_delete_user_account_rolls_back_profile_when_phase_fails(
    phase_patch: str,
    phase_name: str,
    expected_profile_state: str,
    restore_expected: bool,
) -> None:
    failing_result = {
        "error": f"{phase_name}_failed",
        "details": [f"{phase_name}: failed"],
    }
    app_metrics.reset()

    patches = {
        "delete_billing_customer_data": AsyncMock(return_value={"status": "deleted"}),
        "delete_user_data": AsyncMock(return_value={"deleted": True}),
        "delete_auth_identity": AsyncMock(return_value={"status": "deleted"}),
        "delete_profile_record": AsyncMock(return_value={"status": "deleted"}),
    }
    patches[phase_patch] = AsyncMock(return_value=failing_result)

    with (
        patch(
            "ideago.auth.supabase_admin.mark_profile_deletion_pending",
            new=AsyncMock(return_value={"status": "marked"}),
        ),
        patch(
            "ideago.auth.supabase_admin.restore_profile_after_failed_deletion",
            new=AsyncMock(return_value={"status": "restored"}),
        ) as restore_profile,
        patch(
            "ideago.auth.supabase_admin.delete_billing_customer_data",
            new=patches["delete_billing_customer_data"],
        ),
        patch(
            "ideago.auth.supabase_admin.delete_user_data",
            new=patches["delete_user_data"],
        ),
        patch(
            "ideago.auth.supabase_admin.delete_auth_identity",
            new=patches["delete_auth_identity"],
        ),
        patch(
            "ideago.auth.supabase_admin.delete_profile_record",
            new=patches["delete_profile_record"],
        ),
    ):
        result = await supabase_admin.delete_user_account("uid")

    assert result["error"] == "partial_failure"
    assert result["phase"] == phase_name
    assert result["cleanup"]["profile"] == expected_profile_state
    if restore_expected:
        restore_profile.assert_awaited_once_with("uid")
    else:
        restore_profile.assert_not_awaited()
    metrics = app_metrics.snapshot()
    if restore_expected:
        assert metrics["event_counts"]["account_delete_rollback_triggered"] == 1
        assert metrics["event_reasons"]["account_delete_rollback_triggered"] == {
            phase_name: 1
        }
    else:
        assert metrics["event_counts"]["account_delete_stuck_pending"] == 1
        assert metrics["event_reasons"]["account_delete_stuck_pending"] == {
            phase_name: 1
        }


@pytest.mark.asyncio
async def test_delete_user_account_marks_profile_as_stuck_when_rollback_fails() -> None:
    app_metrics.reset()
    with (
        patch(
            "ideago.auth.supabase_admin.mark_profile_deletion_pending",
            new=AsyncMock(return_value={"status": "marked"}),
        ),
        patch(
            "ideago.auth.supabase_admin.delete_billing_customer_data",
            new=AsyncMock(
                return_value={
                    "error": "billing_cleanup_failed",
                    "details": ["subscription_cancel_failed"],
                }
            ),
        ),
        patch(
            "ideago.auth.supabase_admin.restore_profile_after_failed_deletion",
            new=AsyncMock(
                return_value={
                    "error": "profile_delete_restore_failed",
                    "details": ["profiles: 500"],
                }
            ),
        ),
    ):
        result = await supabase_admin.delete_user_account("uid")

    assert result == {
        "error": "partial_failure",
        "phase": "billing_cleanup",
        "details": ["subscription_cancel_failed", "profiles: 500"],
        "cleanup": {
            "domain_data": "pending",
            "billing": "failed",
            "auth_identity": "pending",
            "profile": "rollback_failed",
        },
    }
    metrics = app_metrics.snapshot()
    assert metrics["event_counts"]["account_delete_rollback_triggered"] == 1
    assert metrics["event_counts"]["account_delete_stuck_pending"] == 1
    assert metrics["event_reasons"]["account_delete_stuck_pending"] == {
        "billing_cleanup": 1
    }
