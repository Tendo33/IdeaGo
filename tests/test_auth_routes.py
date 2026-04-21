from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import Response

from ideago.api.routes import auth as auth_route
from tests.test_api import reset_runtime_state  # noqa: F401


def _fake_auth_settings():
    return type(
        "Settings",
        (),
        {
            "auth_session_secret": "session-secret-session-secret-012345",
            "auth_session_expire_hours": 24,
        },
    )()


def _cookie_backed_request():
    return type(
        "Req",
        (),
        {
            "client": type("Client", (), {"host": "127.0.0.1"})(),
            "headers": {},
            "cookies": {},
        },
    )()


@pytest.mark.asyncio
async def test_delete_account_keeps_session_when_deletion_fails() -> None:
    user = auth_route.AuthUser(id="uid", email="u@example.com")
    fake_settings = _fake_auth_settings()
    request = _cookie_backed_request()
    with patch("ideago.api.routes.auth.get_settings", return_value=fake_settings):
        request.cookies[auth_route.AUTH_SESSION_COOKIE_NAME] = (
            auth_route._issue_auth_token(
                user_id=user.id,
                email=user.email,
                provider="linuxdo",
                session_id="session-1",
            )
        )

    with (
        patch(
            "ideago.api.routes.auth.delete_user_account",
            new=AsyncMock(
                return_value={
                    "error": "partial_failure",
                    "phase": "billing_cleanup",
                    "details": [],
                    "cleanup": {},
                }
            ),
        ),
        patch("ideago.api.routes.auth.get_settings", return_value=fake_settings),
        patch("ideago.api.routes.auth.revoke_auth_session", new=AsyncMock()) as revoke,
        patch("ideago.api.routes.auth.log_audit_event", new=AsyncMock()),
        pytest.raises(auth_route.AppError),
    ):
        await auth_route.delete_account(request, Response(), user)

    revoke.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_account_revokes_session_when_failure_leaves_account_stuck_pending() -> (
    None
):
    user = auth_route.AuthUser(id="uid", email="u@example.com")
    fake_settings = _fake_auth_settings()
    request = _cookie_backed_request()
    with patch("ideago.api.routes.auth.get_settings", return_value=fake_settings):
        request.cookies[auth_route.AUTH_SESSION_COOKIE_NAME] = (
            auth_route._issue_auth_token(
                user_id=user.id,
                email=user.email,
                provider="linuxdo",
                session_id="session-1",
            )
        )

    with (
        patch(
            "ideago.api.routes.auth.delete_user_account",
            new=AsyncMock(
                return_value={
                    "error": "partial_failure",
                    "phase": "profile_delete_finalize",
                    "details": ["profiles: 500"],
                    "cleanup": {
                        "domain_data": "deleted",
                        "billing": "deleted",
                        "auth_identity": "deleted",
                        "profile": "deletion_pending",
                    },
                }
            ),
        ),
        patch("ideago.api.routes.auth.get_settings", return_value=fake_settings),
        patch("ideago.api.routes.auth.revoke_auth_session", new=AsyncMock()) as revoke,
        patch("ideago.api.routes.auth.log_audit_event", new=AsyncMock()),
        pytest.raises(auth_route.AppError),
    ):
        await auth_route.delete_account(request, Response(), user)

    revoke.assert_awaited_once_with("session-1")


@pytest.mark.asyncio
async def test_delete_account_revokes_session_when_failure_only_restores_access() -> (
    None
):
    user = auth_route.AuthUser(id="uid", email="u@example.com")
    fake_settings = _fake_auth_settings()
    request = _cookie_backed_request()
    with patch("ideago.api.routes.auth.get_settings", return_value=fake_settings):
        request.cookies[auth_route.AUTH_SESSION_COOKIE_NAME] = (
            auth_route._issue_auth_token(
                user_id=user.id,
                email=user.email,
                provider="linuxdo",
                session_id="session-1",
            )
        )

    with (
        patch(
            "ideago.api.routes.auth.delete_user_account",
            new=AsyncMock(
                return_value={
                    "error": "partial_failure",
                    "phase": "auth_identity_cleanup",
                    "details": ["auth_identity: exception"],
                    "cleanup": {
                        "domain_data": "deleted",
                        "billing": "deleted",
                        "auth_identity": "failed",
                        "profile": "restored_access_only",
                    },
                }
            ),
        ),
        patch("ideago.api.routes.auth.get_settings", return_value=fake_settings),
        patch("ideago.api.routes.auth.revoke_auth_session", new=AsyncMock()) as revoke,
        patch("ideago.api.routes.auth.log_audit_event", new=AsyncMock()),
        pytest.raises(auth_route.AppError),
    ):
        await auth_route.delete_account(request, Response(), user)

    revoke.assert_awaited_once_with("session-1")
