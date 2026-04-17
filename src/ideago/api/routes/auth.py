"""Auth endpoints: current user info, quota, LinuxDo OAuth, and profile."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from ideago.api.errors import AppError, ErrorCode
from ideago.auth.dependencies import get_current_user
from ideago.auth.models import AuthUser
from ideago.auth.session import (
    AUTH_SESSION_COOKIE_NAME,
    clear_auth_session_cookie,
    set_auth_session_cookie,
)
from ideago.auth.session_store import (
    create_auth_session,
    is_auth_session_active,
    revoke_auth_session,
)
from ideago.auth.supabase_admin import (
    delete_user_account,
    ensure_profile_exists,
    get_profile,
    get_quota_info,
    update_profile,
)
from ideago.config.settings import get_settings
from ideago.observability.audit import log_audit_event
from ideago.observability.metrics import metrics as app_metrics

router = APIRouter(tags=["auth"])


class ProfileUpdatePayload(BaseModel):
    display_name: str = Field(default="", max_length=100)
    bio: str = Field(default="", max_length=300)


class LinuxDoStartPayload(BaseModel):
    url: str


class LinuxDoStartRequest(BaseModel):
    redirect_to: str | None = None
    captcha_token: str | None = None
    prefetch: bool = False


def _frontend_callback_url(request: Request) -> str:
    settings = get_settings()
    base = settings.frontend_app_url.strip().rstrip("/")
    if base:
        return f"{base}/auth/callback"
    host = str(request.base_url).rstrip("/")
    return f"{host}/auth/callback"


def _backend_linuxdo_callback_url(request: Request) -> str:
    return str(request.url_for("linuxdo_callback"))


def _is_safe_redirect(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    if not parsed.netloc:
        return False
    settings = get_settings()
    configured = settings.frontend_app_url.strip()
    if not configured:
        return False
    try:
        configured_parsed = urlparse(configured)
        return (
            parsed.scheme == configured_parsed.scheme
            and parsed.netloc == configured_parsed.netloc
        )
    except ValueError:
        return False


def _build_state_token(*, redirect_to: str) -> str:
    settings = get_settings()
    if not settings.auth_session_secret:
        raise HTTPException(
            status_code=503, detail="AUTH_SESSION_SECRET is not configured"
        )
    now = datetime.now(timezone.utc)
    payload = {
        "redirect_to": redirect_to,
        "nonce": secrets.token_urlsafe(16),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=10)).timestamp()),
        "aud": "ideago-linuxdo-state",
    }
    return jwt.encode(payload, settings.auth_session_secret, algorithm="HS256")


def _parse_state_token(state: str) -> dict:
    settings = get_settings()
    if not settings.auth_session_secret:
        raise HTTPException(
            status_code=503, detail="AUTH_SESSION_SECRET is not configured"
        )
    try:
        return jwt.decode(
            state,
            settings.auth_session_secret,
            algorithms=["HS256"],
            audience="ideago-linuxdo-state",
        )
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=400, detail=f"Invalid OAuth state: {exc}"
        ) from exc


async def _exchange_linuxdo_code(*, code: str, redirect_uri: str) -> str:
    settings = get_settings()
    if not settings.linuxdo_client_id or not settings.linuxdo_client_secret:
        raise HTTPException(status_code=503, detail="LinuxDo OAuth is not configured")

    form_data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": settings.linuxdo_client_id,
        "client_secret": settings.linuxdo_client_secret,
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(settings.linuxdo_token_url, data=form_data)
        if resp.status_code != 200:
            raise HTTPException(
                status_code=400, detail="Failed to exchange LinuxDo authorization code"
            )
        data = resp.json()
        token = data.get("access_token")
        if not isinstance(token, str) or not token:
            raise HTTPException(
                status_code=400, detail="LinuxDo token response missing access_token"
            )
        return token


async def _fetch_linuxdo_userinfo(access_token: str) -> dict:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            settings.linuxdo_userinfo_url,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if resp.status_code != 200:
            raise HTTPException(
                status_code=400, detail="Failed to fetch LinuxDo user info"
            )
        data = resp.json()
        if not isinstance(data, dict):
            raise HTTPException(
                status_code=400, detail="Invalid LinuxDo user info payload"
            )
        return data


def _extract_linuxdo_identity(userinfo: dict) -> tuple[str, str, str]:
    raw_id = userinfo.get("id") or userinfo.get("sub")
    if raw_id is None:
        raise HTTPException(status_code=400, detail="LinuxDo user info missing id")
    linuxdo_id = str(raw_id)
    email = str(userinfo.get("email") or "").strip()
    username = str(userinfo.get("username") or userinfo.get("name") or "").strip()
    if not email:
        fallback = username or linuxdo_id
        email = f"{fallback}@linux.do"
    display_name = username or email.split("@", 1)[0]
    return linuxdo_id, email, display_name


def _build_internal_user_id(linuxdo_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"linuxdo:{linuxdo_id}"))


def _issue_auth_token(
    *, user_id: str, email: str, provider: str, session_id: str = ""
) -> str:
    settings = get_settings()
    if not settings.auth_session_secret:
        raise HTTPException(
            status_code=503, detail="AUTH_SESSION_SECRET is not configured"
        )
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "email": email,
        "provider": provider,
        "sid": session_id,
        "aud": "ideago-auth",
        "iat": int(now.timestamp()),
        "exp": int(
            (now + timedelta(hours=settings.auth_session_expire_hours)).timestamp()
        ),
    }
    return jwt.encode(payload, settings.auth_session_secret, algorithm="HS256")


def _hash_email(email: str) -> str:
    normalized = email.strip().lower()
    if not normalized:
        return ""
    return hashlib.sha256(normalized.encode()).hexdigest()[:12]


def _redirect_error(redirect_to: str, message: str) -> RedirectResponse:
    safe_message = message or "Authentication failed"
    parsed = urlparse(redirect_to)
    query_items = parse_qsl(parsed.query, keep_blank_values=True)
    query_items.extend(
        [
            ("error", "linuxdo_auth"),
            ("error_description", safe_message),
        ]
    )
    return RedirectResponse(
        url=urlunparse(parsed._replace(query=urlencode(query_items))),
        status_code=302,
    )


def _custom_session_token_from_request(request: Request) -> str:
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.removeprefix("Bearer ").strip()
    if token:
        return token
    cookie_jar = getattr(request, "cookies", {}) or {}
    return str(cookie_jar.get(AUTH_SESSION_COOKIE_NAME, "")).strip()


def _decode_custom_session_token(
    token: str, *, verify_exp: bool = True
) -> dict[str, object]:
    settings = get_settings()
    if not settings.auth_session_secret:
        raise HTTPException(
            status_code=503, detail="AUTH_SESSION_SECRET is not configured"
        )
    try:
        return jwt.decode(
            token,
            settings.auth_session_secret,
            algorithms=["HS256"],
            audience="ideago-auth",
            options={"verify_exp": verify_exp},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token") from None


def _profile_is_deleted_or_pending(profile: dict[str, object]) -> bool:
    return bool(profile.get("deletion_pending") or profile.get("deleted_at"))


def _raise_profile_error(error_code: str) -> None:
    if error_code == "profile_not_found":
        raise HTTPException(status_code=404, detail="profile_not_found")
    raise AppError(
        503,
        ErrorCode.DEPENDENCY_UNAVAILABLE,
        "Profile service temporarily unavailable",
        extra={"dependency": "supabase_profiles", "reason": error_code},
    )


async def _ensure_active_profile_for_user(user_id: str) -> dict[str, object]:
    profile = await get_profile(user_id)
    if isinstance(profile, dict) and _profile_is_deleted_or_pending(profile):
        raise AppError(410, ErrorCode.ACCOUNT_DELETED, "Account deletion in progress")
    if isinstance(profile, dict) and not profile.get("error"):
        return profile
    initial_error = str(profile.get("error") or "") if isinstance(profile, dict) else ""
    if initial_error and initial_error != "profile_not_found":
        _raise_profile_error(initial_error)
    created = await ensure_profile_exists(user_id)
    if not created:
        profile = await get_profile(user_id)
        if isinstance(profile, dict) and _profile_is_deleted_or_pending(profile):
            raise AppError(
                410, ErrorCode.ACCOUNT_DELETED, "Account deletion in progress"
            )
        if isinstance(profile, dict) and profile.get("error"):
            _raise_profile_error(str(profile.get("error") or "profile_not_found"))
    if isinstance(profile, dict) and not profile.get("error"):
        return profile
    profile = await get_profile(user_id)
    if isinstance(profile, dict) and not profile.get("error"):
        return profile
    if isinstance(profile, dict) and profile.get("error"):
        _raise_profile_error(str(profile.get("error") or "profile_not_found"))
    raise HTTPException(status_code=404, detail="profile_not_found")


async def _verify_turnstile_token(*, token: str, remote_ip: str | None = None) -> bool:
    settings = get_settings()
    secret = settings.turnstile_secret_key.strip()
    if not secret:
        raise HTTPException(
            status_code=503, detail="TURNSTILE_SECRET_KEY is not configured"
        )

    form_data: dict[str, str] = {
        "secret": secret,
        "response": token,
    }
    if remote_ip:
        form_data["remoteip"] = remote_ip

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://challenges.cloudflare.com/turnstile/v0/siteverify",
                data=form_data,
            )
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail="Captcha verification failed"
        ) from exc

    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Captcha verification failed")

    data = resp.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=502, detail="Captcha verification failed")
    return bool(data.get("success") is True)


@router.post("/auth/linuxdo/start", response_model=None)
async def linuxdo_start(
    request: Request,
    payload: LinuxDoStartRequest,
) -> RedirectResponse | LinuxDoStartPayload:
    settings = get_settings()
    if not settings.linuxdo_client_id:
        raise HTTPException(status_code=503, detail="LinuxDo OAuth is not configured")
    redirect_to = payload.redirect_to
    captcha_token = payload.captcha_token
    prefetch = payload.prefetch
    if not captcha_token:
        raise HTTPException(status_code=400, detail="Missing captcha token")

    target = redirect_to or _frontend_callback_url(request)
    if not _is_safe_redirect(target):
        raise HTTPException(status_code=400, detail="Invalid redirect_to")
    is_valid_captcha = await _verify_turnstile_token(
        token=captcha_token,
        remote_ip=request.client.host if request.client else None,
    )
    if not is_valid_captcha:
        raise HTTPException(status_code=401, detail="Invalid captcha token")

    state = _build_state_token(redirect_to=target)
    callback_url = _backend_linuxdo_callback_url(request)
    query = urlencode(
        {
            "client_id": settings.linuxdo_client_id,
            "response_type": "code",
            "redirect_uri": callback_url,
            "scope": settings.linuxdo_scope,
            "state": state,
        }
    )
    authorize_url = f"{settings.linuxdo_authorize_url}?{query}"
    if prefetch:
        return LinuxDoStartPayload(url=authorize_url)
    return RedirectResponse(url=authorize_url, status_code=302)


@router.get("/auth/linuxdo/callback", name="linuxdo_callback")
async def linuxdo_callback(
    request: Request,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
) -> RedirectResponse:
    fallback = _frontend_callback_url(request)

    if not state:
        return _redirect_error(fallback, "Missing OAuth state")

    try:
        parsed_state = _parse_state_token(state)
        redirect_to = str(parsed_state.get("redirect_to") or fallback)
    except HTTPException as exc:
        return _redirect_error(
            fallback,
            exc.detail if isinstance(exc.detail, str) else "Invalid OAuth state",
        )

    if not _is_safe_redirect(redirect_to):
        redirect_to = fallback

    if error:
        return _redirect_error(redirect_to, error_description or error)
    if not code:
        return _redirect_error(redirect_to, "Missing authorization code")

    try:
        callback_url = _backend_linuxdo_callback_url(request)
        linuxdo_access_token = await _exchange_linuxdo_code(
            code=code, redirect_uri=callback_url
        )
        userinfo = await _fetch_linuxdo_userinfo(linuxdo_access_token)
        linuxdo_id, email, display_name = _extract_linuxdo_identity(userinfo)
        user_id = _build_internal_user_id(linuxdo_id)
        avatar_url = str(
            userinfo.get("avatar_url") or userinfo.get("avatar") or ""
        ).strip()
        created = await ensure_profile_exists(
            user_id,
            display_name=display_name,
            avatar_url=avatar_url,
            auth_provider="linuxdo",
        )
        if not created:
            existing_profile = await get_profile(user_id)
            if isinstance(existing_profile, dict) and _profile_is_deleted_or_pending(
                existing_profile
            ):
                return _redirect_error(redirect_to, "Account deletion in progress")
            return _redirect_error(redirect_to, "Authentication failed")
        session_id = await create_auth_session(user_id, provider="linuxdo")
        app_access_token = _issue_auth_token(
            user_id=user_id,
            email=email,
            provider="linuxdo",
            session_id=session_id,
        )
    except HTTPException as exc:
        return _redirect_error(
            redirect_to,
            exc.detail if isinstance(exc.detail, str) else "Authentication failed",
        )
    except Exception:
        return _redirect_error(redirect_to, "Authentication failed")

    await log_audit_event(
        actor_id=user_id,
        action="auth.login",
        metadata={"provider": "linuxdo", "email_hash": _hash_email(email)},
        ip_address=request.client.host if request.client else None,
    )
    response = RedirectResponse(url=redirect_to, status_code=302)
    set_auth_session_cookie(response, request, app_access_token)
    return response


@router.get("/auth/me")
async def get_me(user: AuthUser = Depends(get_current_user)) -> dict:
    """Return the currently authenticated user."""
    return {"id": user.id, "email": user.email}


_REFRESH_GRACE_HOURS = 24 * 7


@router.post("/auth/refresh")
async def refresh_token(request: Request, response: Response) -> dict:
    """Issue a fresh JWT for custom OAuth sessions (LinuxDo).

    Accepts tokens that are expired within a grace period so that
    clients can renew without forcing a full re-login.
    Supabase-native sessions should use the Supabase SDK refresh flow.
    """
    settings = get_settings()
    if not settings.auth_session_secret:
        raise HTTPException(
            status_code=503, detail="AUTH_SESSION_SECRET is not configured"
        )

    auth_header = request.headers.get("Authorization", "")
    token = auth_header.removeprefix("Bearer ").strip()
    if not token:
        cookie_jar = getattr(request, "cookies", {}) or {}
        token = str(cookie_jar.get(AUTH_SESSION_COOKIE_NAME, "")).strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")

    try:
        payload = _decode_custom_session_token(token, verify_exp=False)
    except HTTPException:
        raise

    user_id = str(payload.get("sub") or "")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    session_id = str(payload.get("sid") or "")
    if not session_id:
        raise AppError(401, ErrorCode.SESSION_REVOKED, "Session revoked")
    profile = await get_profile(user_id)
    if not isinstance(profile, dict):
        raise AppError(401, ErrorCode.SESSION_REVOKED, "Session revoked")
    if profile.get("error"):
        error_code = str(profile.get("error") or "")
        if error_code == "profile_not_found":
            raise AppError(401, ErrorCode.SESSION_REVOKED, "Session revoked")
        _raise_profile_error(error_code or "profile_fetch_failed")
    if _profile_is_deleted_or_pending(profile):
        raise AppError(410, ErrorCode.ACCOUNT_DELETED, "Account deletion in progress")
    if not await is_auth_session_active(session_id, user_id=user_id):
        raise AppError(401, ErrorCode.SESSION_REVOKED, "Session revoked")

    exp_raw = payload.get("exp", 0)
    exp_ts = exp_raw if isinstance(exp_raw, int) else 0
    now_ts = int(datetime.now(timezone.utc).timestamp())
    if exp_ts > 0 and now_ts - exp_ts > _REFRESH_GRACE_HOURS * 3600:
        raise HTTPException(status_code=401, detail="Token expired beyond grace period")

    new_token = _issue_auth_token(
        user_id=user_id,
        email=str(payload.get("email") or ""),
        provider=str(payload.get("provider") or ""),
        session_id=session_id,
    )
    set_auth_session_cookie(response, request, new_token)
    return {"access_token": new_token}


@router.post("/auth/logout")
async def logout(
    request: Request,
    response: Response,
    user: AuthUser = Depends(get_current_user),
) -> dict:
    """Clear backend-managed auth session cookie."""
    token = _custom_session_token_from_request(request)
    if token:
        try:
            payload = _decode_custom_session_token(token)
        except HTTPException:
            payload = {}
        session_id = str(payload.get("sid") or "")
        if session_id:
            await revoke_auth_session(session_id)
    clear_auth_session_cookie(response, request)
    await log_audit_event(
        actor_id=user.id,
        action="auth.logout",
        metadata={"provider": "custom_session"},
        ip_address=request.client.host if request.client else None,
    )
    return {"status": "logged_out"}


@router.get("/auth/quota")
async def get_user_quota(user: AuthUser = Depends(get_current_user)) -> dict:
    """Return the user's current usage quota information."""
    await _ensure_active_profile_for_user(user.id)
    return await get_quota_info(user.id)


@router.get("/auth/profile")
async def get_my_profile(user: AuthUser = Depends(get_current_user)) -> dict:
    """Return profile for current user."""
    return await _ensure_active_profile_for_user(user.id)


@router.put("/auth/profile")
async def update_my_profile(
    payload: ProfileUpdatePayload,
    user: AuthUser = Depends(get_current_user),
) -> dict:
    """Update profile for current user."""
    await _ensure_active_profile_for_user(user.id)
    data = await update_profile(
        user.id,
        display_name=payload.display_name.strip(),
        bio=payload.bio.strip(),
    )
    if data.get("error"):
        raise HTTPException(status_code=400, detail=data["error"])
    return data


@router.delete("/auth/account")
async def delete_account(
    request: Request,
    response: Response,
    user: AuthUser = Depends(get_current_user),
) -> dict:
    """Permanently delete the authenticated user's account and all data."""
    session_id = ""
    token = _custom_session_token_from_request(request)
    if token:
        try:
            payload = _decode_custom_session_token(token)
        except HTTPException:
            payload = {}
        session_id = str(payload.get("sid") or "")
    result = await delete_user_account(user.id)
    if result.get("error"):
        phase = str(result.get("phase") or "unknown_phase")
        details = list(result.get("details") or [])
        cleanup = result.get("cleanup", {})
        await log_audit_event(
            actor_id=user.id,
            action="auth.delete_account",
            metadata={
                "outcome": "failed",
                "phase": phase,
                "details": details,
                "cleanup": cleanup,
            },
            ip_address=request.client.host if request.client else None,
        )
        app_metrics.increment_event("account_delete_failed", reason=phase)
        raise AppError(
            500,
            ErrorCode.INTERNAL_ERROR,
            f"Failed to delete account during {phase}",
            extra={
                "phase": phase,
                "details": details,
                "cleanup": cleanup,
            },
        )
    if session_id:
        await revoke_auth_session(session_id)
    await log_audit_event(
        actor_id=user.id,
        action="auth.delete_account",
        metadata={"cleanup": result.get("cleanup", {})},
        ip_address=request.client.host if request.client else None,
    )
    clear_auth_session_cookie(response, request)
    return result
