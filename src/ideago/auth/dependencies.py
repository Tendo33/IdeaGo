"""FastAPI dependencies for authentication.

FastAPI 认证依赖注入：优先使用 PyJWT 本地验证 Supabase JWT，
如未配置 JWT Secret 则回退到 HTTP 远程验证。
"""

from __future__ import annotations

import httpx
import jwt
from fastapi import Depends, HTTPException, Request

from ideago.auth.models import AuthUser
from ideago.config.settings import get_settings
from ideago.observability.log_config import get_logger

logger = get_logger(__name__)

_http_client: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:
    """Lazily create a shared async HTTP client for remote auth verification."""
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            timeout=5.0,
            limits=httpx.Limits(max_connections=30, max_keepalive_connections=10),
        )
    return _http_client


async def close_auth_http_client() -> None:
    """Shut down the shared HTTP client (called during app lifespan teardown)."""
    global _http_client
    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None


def _verify_jwt_locally(token: str, jwt_secret: str) -> dict | None:
    """Verify and decode a Supabase JWT using the project's JWT secret.

    Returns the decoded payload on success, None on failure.
    Supabase uses HS256 by default.
    """
    try:
        payload = jwt.decode(
            token,
            jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
        return payload
    except jwt.ExpiredSignatureError:
        logger.debug("JWT expired")
    except jwt.InvalidTokenError as exc:
        logger.debug("JWT validation failed: {}", exc)
    return None


def _verify_ideago_jwt(token: str, jwt_secret: str) -> dict | None:
    """Verify and decode a backend-issued JWT for custom OAuth sessions."""
    try:
        return jwt.decode(
            token,
            jwt_secret,
            algorithms=["HS256"],
            audience="ideago-auth",
        )
    except jwt.ExpiredSignatureError:
        logger.debug("IdeaGo JWT expired")
    except jwt.InvalidTokenError as exc:
        logger.debug("IdeaGo JWT validation failed: {}", exc)
    return None


async def _verify_supabase_token_remote(token: str) -> dict | None:
    """Fallback: verify token via Supabase HTTP endpoint (~100-200ms)."""
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_anon_key:
        logger.warning("Supabase URL or anon key not configured; skipping auth")
        return None
    try:
        client = _get_http_client()
        resp = await client.get(
            f"{settings.supabase_url}/auth/v1/user",
            headers={
                "Authorization": f"Bearer {token}",
                "apikey": settings.supabase_anon_key,
            },
        )
        if resp.status_code == 200:
            return resp.json()
        logger.debug("Supabase token verification failed: {}", resp.status_code)
    except httpx.TimeoutException:
        logger.warning("Supabase auth endpoint timed out")
    except Exception:
        logger.opt(exception=True).warning("Unexpected error verifying Supabase token")
    return None


def _extract_user_from_jwt_payload(payload: dict) -> AuthUser | None:
    """Extract AuthUser from a locally-decoded JWT payload."""
    user_id = payload.get("sub", "")
    if not user_id:
        return None
    email = payload.get("email", "")
    return AuthUser(id=user_id, email=email)


def _extract_user_from_api_response(data: dict) -> AuthUser | None:
    """Extract AuthUser from the Supabase /auth/v1/user response."""
    user_id = data.get("id", "")
    if not user_id:
        return None
    return AuthUser(id=user_id, email=data.get("email", ""))


def _extract_user_from_ideago_payload(payload: dict) -> AuthUser | None:
    """Extract AuthUser from a backend-issued JWT payload."""
    user_id = payload.get("sub", "")
    if not user_id:
        return None
    return AuthUser(id=user_id, email=payload.get("email", ""))


def extract_token_subject(token: str) -> str:
    """Best-effort extraction of user id from a bearer token for rate limiting."""
    settings = get_settings()

    if settings.auth_session_secret:
        payload = _verify_ideago_jwt(token, settings.auth_session_secret)
        if payload is not None:
            sub = payload.get("sub", "")
            if isinstance(sub, str) and sub:
                return sub

    if settings.supabase_jwt_secret:
        payload = _verify_jwt_locally(token, settings.supabase_jwt_secret)
        if payload is not None:
            sub = payload.get("sub", "")
            if isinstance(sub, str) and sub:
                return sub

    return ""


async def get_optional_user(request: Request) -> AuthUser | None:
    """Extract and verify the user from the Authorization header.

    Uses local JWT verification when SUPABASE_JWT_SECRET is configured,
    falls back to HTTP remote verification otherwise.
    Returns None when no valid token is present (non-blocking).
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    token = auth_header.removeprefix("Bearer ").strip()
    if not token:
        return None

    settings = get_settings()

    if settings.auth_session_secret:
        payload = _verify_ideago_jwt(token, settings.auth_session_secret)
        if payload is not None:
            return _extract_user_from_ideago_payload(payload)

    if settings.supabase_jwt_secret:
        payload = _verify_jwt_locally(token, settings.supabase_jwt_secret)
        if payload is not None:
            return _extract_user_from_jwt_payload(payload)
        return None

    user_data = await _verify_supabase_token_remote(token)
    if user_data is None:
        return None
    return _extract_user_from_api_response(user_data)


async def get_current_user(
    user: AuthUser | None = Depends(get_optional_user),
) -> AuthUser:
    """Require an authenticated user. Raises 401 when unauthenticated."""
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user
