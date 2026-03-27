"""FastAPI dependencies for authentication.

FastAPI 认证依赖注入：优先使用后端自签 JWT，
随后使用 Supabase JWKS 做本地验签，
最后在基础设施异常时回退到 Supabase HTTP 远程验证。
"""

from __future__ import annotations

import asyncio
import threading
import time
from typing import Any, NamedTuple

import httpx
import jwt
from fastapi import Depends, HTTPException, Request

from ideago.auth.models import AuthUser
from ideago.auth.session import AUTH_SESSION_COOKIE_NAME
from ideago.config.settings import get_settings
from ideago.observability.log_config import get_logger

logger = get_logger(__name__)

_http_client: httpx.AsyncClient | None = None
_jwks_cache: dict[str, Any] | None = None
_jwks_cache_expires_at = 0.0
_TRUSTED_SUPABASE_ALGORITHMS = frozenset(
    {"RS256", "RS384", "RS512", "ES256", "ES384", "ES512"}
)


class _SupabaseJwtVerificationResult(NamedTuple):
    payload: dict[str, Any] | None
    should_fallback_remote: bool


def _get_http_client() -> httpx.AsyncClient:
    """Lazily create a shared async HTTP client for auth verification."""
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            timeout=5.0,
            limits=httpx.Limits(max_connections=30, max_keepalive_connections=10),
        )
    return _http_client


def _clear_jwks_cache() -> None:
    """Clear the in-memory JWKS cache."""
    global _jwks_cache, _jwks_cache_expires_at
    _jwks_cache = None
    _jwks_cache_expires_at = 0.0


async def close_auth_http_client() -> None:
    """Shut down the shared HTTP client (called during app lifespan teardown)."""
    global _http_client
    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None
    _clear_jwks_cache()


def _verify_ideago_jwt(token: str, jwt_secret: str) -> dict[str, Any] | None:
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


def _should_try_ideago_jwt(token: str) -> bool:
    """Quickly identify whether a token looks like an IdeaGo-issued HS256 JWT."""
    try:
        header = jwt.get_unverified_header(token)
    except jwt.InvalidTokenError:
        return True

    alg = header.get("alg")
    return isinstance(alg, str) and alg == "HS256"


async def _fetch_jwks() -> dict[str, Any]:
    """Fetch the current Supabase JWKS document."""
    settings = get_settings()
    jwks_url = settings.get_supabase_jwks_url()
    if not jwks_url:
        raise RuntimeError("Supabase JWKS URL is not configured")

    client = _get_http_client()
    resp = await client.get(jwks_url)
    resp.raise_for_status()
    payload = resp.json()
    if not isinstance(payload, dict):
        raise RuntimeError("Invalid JWKS response")
    keys = payload.get("keys")
    if not isinstance(keys, list):
        raise RuntimeError("Invalid JWKS response")
    return payload


async def _get_jwks(*, force_refresh: bool = False) -> dict[str, Any]:
    """Return cached JWKS, refreshing it when expired or explicitly requested."""
    global _jwks_cache, _jwks_cache_expires_at

    now = time.monotonic()
    if not force_refresh and _jwks_cache is not None and now < _jwks_cache_expires_at:
        return _jwks_cache

    payload = await _fetch_jwks()
    ttl = get_settings().supabase_jwks_cache_ttl_seconds
    _jwks_cache = payload
    _jwks_cache_expires_at = now + max(ttl, 0)
    return payload


def _get_jwk_for_kid(jwks: dict[str, Any], kid: str) -> dict[str, Any] | None:
    """Find the JWK matching the given kid."""
    keys = jwks.get("keys", [])
    if not isinstance(keys, list):
        return None
    for key in keys:
        if isinstance(key, dict) and key.get("kid") == kid:
            return key
    return None


async def _get_supabase_signing_key(
    token: str,
) -> tuple[Any, str]:
    """Resolve the signing key for a Supabase JWT."""
    try:
        header = jwt.get_unverified_header(token)
    except jwt.DecodeError as exc:
        raise ValueError("Invalid JWT header") from exc

    alg = header.get("alg")
    kid = header.get("kid")
    if not isinstance(alg, str) or alg not in _TRUSTED_SUPABASE_ALGORITHMS:
        raise ValueError("Unsupported JWT signing algorithm")
    if not isinstance(kid, str) or not kid:
        raise ValueError("JWT kid is missing")

    jwks = await _get_jwks(force_refresh=False)
    jwk = _get_jwk_for_kid(jwks, kid)
    if jwk is None:
        jwks = await _get_jwks(force_refresh=True)
        jwk = _get_jwk_for_kid(jwks, kid)
    if jwk is None:
        raise ValueError("Signing key not found for JWT kid")

    jwk_alg = jwk.get("alg")
    if isinstance(jwk_alg, str) and jwk_alg != alg:
        raise ValueError("JWT algorithm does not match JWK")

    pyjwk = jwt.PyJWK.from_dict(jwk)
    return pyjwk.key, alg


async def _verify_supabase_jwt(token: str) -> _SupabaseJwtVerificationResult:
    """Verify and decode a Supabase JWT using the project's JWKS."""
    settings = get_settings()
    issuer = settings.get_supabase_jwt_issuer()
    if not settings.supabase_url or not issuer:
        return _SupabaseJwtVerificationResult(None, False)

    try:
        signing_key, algorithm = await _get_supabase_signing_key(token)
        payload = jwt.decode(
            token,
            signing_key,
            algorithms=[algorithm],
            audience=settings.supabase_jwt_audience,
            issuer=issuer,
        )
        return _SupabaseJwtVerificationResult(payload, False)
    except (httpx.HTTPError, RuntimeError) as exc:
        logger.warning("Supabase JWKS fetch failed: {}", exc)
        return _SupabaseJwtVerificationResult(None, True)
    except jwt.ExpiredSignatureError:
        logger.debug("Supabase JWT expired")
    except jwt.InvalidTokenError as exc:
        logger.debug("Supabase JWT validation failed: {}", exc)
    except ValueError as exc:
        logger.debug("Supabase JWT validation failed: {}", exc)
    return _SupabaseJwtVerificationResult(None, False)


async def _verify_supabase_token_remote(token: str) -> dict[str, Any] | None:
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


def _extract_user_from_jwt_payload(payload: dict[str, Any]) -> AuthUser | None:
    """Extract AuthUser from a locally-decoded JWT payload."""
    user_id = payload.get("sub", "")
    if not user_id:
        return None
    email = payload.get("email", "")
    role = payload.get("role", "user")
    return AuthUser(id=user_id, email=email, role=role)


def _extract_user_from_api_response(data: dict[str, Any]) -> AuthUser | None:
    """Extract AuthUser from the Supabase /auth/v1/user response."""
    user_id = data.get("id", "")
    if not user_id:
        return None
    return AuthUser(id=user_id, email=data.get("email", ""))


def _extract_user_from_ideago_payload(payload: dict[str, Any]) -> AuthUser | None:
    """Extract AuthUser from a backend-issued JWT payload."""
    user_id = payload.get("sub", "")
    if not user_id:
        return None
    role = payload.get("role", "user")
    return AuthUser(id=user_id, email=payload.get("email", ""), role=role)


def _run_async_for_sync_context(coro: Any) -> Any:
    """Run an async coroutine from sync code, even if a loop is already running."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result: dict[str, Any] = {}
    error: dict[str, BaseException] = {}

    def _runner() -> None:
        try:
            result["value"] = asyncio.run(coro)
        except BaseException as exc:  # pragma: no cover - defensive bridge
            error["value"] = exc

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()
    thread.join()
    if "value" in error:
        raise error["value"]
    return result.get("value")


def extract_token_subject(token: str) -> str:
    """Best-effort extraction of user id from a bearer token for rate limiting."""
    settings = get_settings()

    if settings.auth_session_secret and _should_try_ideago_jwt(token):
        payload = _verify_ideago_jwt(token, settings.auth_session_secret)
        if payload is not None:
            sub = payload.get("sub", "")
            if isinstance(sub, str) and sub:
                return sub

    result = _run_async_for_sync_context(_verify_supabase_jwt(token))
    if (
        isinstance(result, _SupabaseJwtVerificationResult)
        and result.payload is not None
    ):
        sub = result.payload.get("sub", "")
        if isinstance(sub, str) and sub:
            return sub

    return ""


async def get_optional_user(request: Request) -> AuthUser | None:
    """Extract and verify the user from bearer token or auth cookie."""
    auth_header = request.headers.get("Authorization", "")
    bearer_token = auth_header.removeprefix("Bearer ").strip()
    cookie_jar = getattr(request, "cookies", {}) or {}
    cookie_token = str(cookie_jar.get(AUTH_SESSION_COOKIE_NAME, "")).strip()
    candidate_tokens = [token for token in (bearer_token, cookie_token) if token]
    if not candidate_tokens:
        return None

    for token in candidate_tokens:
        user = await _authenticate_token(token)
        if user is not None:
            return user
    return None


async def _authenticate_token(token: str) -> AuthUser | None:
    """Best-effort token authentication for one candidate token."""
    settings = get_settings()

    if settings.auth_session_secret and _should_try_ideago_jwt(token):
        payload = _verify_ideago_jwt(token, settings.auth_session_secret)
        if payload is not None:
            return _extract_user_from_ideago_payload(payload)

    jwks_result = await _verify_supabase_jwt(token)
    if jwks_result.payload is not None:
        return _extract_user_from_jwt_payload(jwks_result.payload)
    if not jwks_result.should_fallback_remote:
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


async def _resolve_admin_role(user: AuthUser) -> AuthUser:
    """Fetch role from profiles if not already embedded in the JWT."""
    if user.role == "admin":
        return user
    try:
        from ideago.auth.supabase_admin import get_profile

        profile = await get_profile(user.id)
        if profile and profile.get("role") == "admin":
            return user.model_copy(update={"role": "admin"})
    except Exception:
        logger.debug("Could not fetch profile role for admin check")
    return user


async def require_admin(
    user: AuthUser = Depends(get_current_user),
) -> AuthUser:
    """Require an admin user. Raises 403 when the user lacks the admin role."""
    user = await _resolve_admin_role(user)
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
