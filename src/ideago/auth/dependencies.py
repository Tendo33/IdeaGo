"""FastAPI dependencies for authentication.

FastAPI 认证依赖注入：从请求头提取并验证 Supabase JWT。
"""

from __future__ import annotations

import httpx
from fastapi import Depends, HTTPException, Request

from ideago.auth.models import AuthUser
from ideago.config.settings import get_settings
from ideago.observability.log_config import get_logger

logger = get_logger(__name__)

_http_client: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:
    """Lazily create a shared async HTTP client for auth verification."""
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=5.0)
    return _http_client


async def close_auth_http_client() -> None:
    """Shut down the shared HTTP client (called during app lifespan teardown)."""
    global _http_client
    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None


async def _verify_supabase_token(token: str) -> dict | None:
    """Verify a Supabase access token by calling the auth endpoint.

    Returns the user payload dict on success, None on failure.
    """
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
        logger.warning("Unexpected error verifying Supabase token")
    return None


async def get_optional_user(request: Request) -> AuthUser | None:
    """Extract and verify the user from the Authorization header.

    Returns None when no valid token is present (non-blocking).
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    token = auth_header.removeprefix("Bearer ").strip()
    if not token:
        return None

    user_data = await _verify_supabase_token(token)
    if user_data is None:
        return None
    user_id = user_data.get("id", "")
    if not user_id:
        return None
    return AuthUser(
        id=user_id,
        email=user_data.get("email", ""),
    )


async def get_current_user(
    user: AuthUser | None = Depends(get_optional_user),
) -> AuthUser:
    """Require an authenticated user. Raises 401 when unauthenticated."""
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user
