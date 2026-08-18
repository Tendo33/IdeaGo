"""Helpers for backend-managed auth session cookies."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import Request, Response

from ideago.config.settings import get_settings

AUTH_SESSION_COOKIE_NAME = "ideago_session"
OAUTH_STATE_COOKIE_NAME = "ideago_oauth_state"
# The OAuth round trip is a few seconds; 10 minutes is generous and matches the
# `exp` baked into the signed state token.
OAUTH_STATE_COOKIE_MAX_AGE_SECONDS = 600


def _should_use_secure_cookie(request: Request) -> bool:
    settings = get_settings()
    if settings.environment == "production":
        return True
    headers = getattr(request, "headers", {}) or {}
    forwarded_proto = str(headers.get("x-forwarded-proto", "")).lower().strip()
    if forwarded_proto:
        return forwarded_proto == "https"
    request_url = getattr(request, "url", None)
    scheme = getattr(request_url, "scheme", "")
    return str(scheme).lower() == "https"


def set_auth_session_cookie(response: Response, request: Request, token: str) -> None:
    """Set an HTTP-only auth cookie for custom OAuth sessions."""
    settings = get_settings()
    max_age_seconds = int(settings.auth_session_expire_hours * 3600)
    response.set_cookie(
        key=AUTH_SESSION_COOKIE_NAME,
        value=token,
        max_age=max_age_seconds,
        expires=max_age_seconds,
        httponly=True,
        secure=_should_use_secure_cookie(request),
        samesite="lax",
        path="/",
    )


def clear_auth_session_cookie(response: Response, request: Request) -> None:
    """Expire the auth session cookie."""
    response.set_cookie(
        key=AUTH_SESSION_COOKIE_NAME,
        value="",
        expires=datetime.now(timezone.utc) - timedelta(days=1),
        max_age=0,
        httponly=True,
        secure=_should_use_secure_cookie(request),
        samesite="lax",
        path="/",
    )


def set_oauth_state_cookie(response: Response, request: Request, binding: str) -> None:
    """Bind an in-flight OAuth handshake to this specific browser.

    The signed ``state`` token alone proves only that *we* minted it — not that
    the browser completing the callback is the one that started the flow. An
    attacker could mint a valid state, complete authorization as themselves, and
    then trick a victim's browser into the callback, planting the attacker's
    session cookie in the victim's browser (login CSRF / session fixation).

    Pairing state with a one-time secret held in an HttpOnly cookie closes that:
    the callback only proceeds when the browser presents the matching secret.
    """
    response.set_cookie(
        key=OAUTH_STATE_COOKIE_NAME,
        value=binding,
        max_age=OAUTH_STATE_COOKIE_MAX_AGE_SECONDS,
        expires=OAUTH_STATE_COOKIE_MAX_AGE_SECONDS,
        httponly=True,
        secure=_should_use_secure_cookie(request),
        # Lax, not Strict: the callback is a cross-site top-level GET redirect
        # from the OAuth provider, and Strict would withhold the cookie there.
        samesite="lax",
        path="/",
    )


def clear_oauth_state_cookie(response: Response, request: Request) -> None:
    """Expire the OAuth state cookie so each binding is single-use."""
    response.set_cookie(
        key=OAUTH_STATE_COOKIE_NAME,
        value="",
        expires=datetime.now(timezone.utc) - timedelta(days=1),
        max_age=0,
        httponly=True,
        secure=_should_use_secure_cookie(request),
        samesite="lax",
        path="/",
    )
