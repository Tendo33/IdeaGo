"""Helpers for backend-managed auth session cookies."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import Request, Response

from ideago.config.settings import get_settings

AUTH_SESSION_COOKIE_NAME = "ideago_session"


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
