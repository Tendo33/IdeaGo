"""Rate-limit helpers and middleware wiring."""

from __future__ import annotations

import time
from collections import defaultdict

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from ideago.api.errors import ErrorCode
from ideago.observability.error_catalog import log_error_event

_rate_limit_store: dict[str, list[float]] = defaultdict(list)
_rate_limit_http_client: httpx.AsyncClient | None = None


def get_rate_limit_store() -> dict[str, list[float]]:
    return _rate_limit_store


def get_rate_limit_http_client() -> httpx.AsyncClient:
    global _rate_limit_http_client
    if _rate_limit_http_client is None:
        _rate_limit_http_client = httpx.AsyncClient(
            timeout=3.0,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
    return _rate_limit_http_client


async def close_rate_limit_http_client() -> None:
    global _rate_limit_http_client
    if _rate_limit_http_client is not None:
        await _rate_limit_http_client.aclose()
        _rate_limit_http_client = None


def clear_rate_limit_state() -> None:
    _rate_limit_store.clear()


async def cleanup_pg_rate_limit_hits(
    settings,
    logger,  # type: ignore[no-untyped-def]
    *,
    cleanup_interval_seconds: int,
) -> int:
    """Cleanup stale PG-backed rate-limit rows. Returns removed row count."""
    supabase_url = getattr(settings, "supabase_url", "")
    service_role_key = getattr(settings, "supabase_service_role_key", "")
    if not supabase_url or not service_role_key:
        return 0
    try:
        response = await get_rate_limit_http_client().post(
            f"{supabase_url}/rest/v1/rpc/cleanup_rate_limit_hits",
            headers={
                "apikey": service_role_key,
                "Authorization": f"Bearer {service_role_key}",
                "Content-Type": "application/json",
            },
            json={"p_max_age_seconds": max(cleanup_interval_seconds * 2, 7200)},
        )
        if response.status_code == 200:
            payload = response.json()
            return payload if isinstance(payload, int) and payload > 0 else 0
        log_error_event(
            logger,
            error_code="RATE_LIMIT_PG_CLEANUP_FAILED",
            subsystem="rate_limit",
            details={"status_code": response.status_code},
            message="cleanup_rate_limit_hits RPC returned non-200",
        )
    except httpx.TimeoutException:
        log_error_event(
            logger,
            error_code="RATE_LIMIT_PG_CLEANUP_TIMEOUT",
            subsystem="rate_limit",
            message="cleanup_rate_limit_hits RPC timeout",
        )
    except httpx.HTTPError:
        log_error_event(
            logger,
            error_code="RATE_LIMIT_PG_CLEANUP_HTTP_ERROR",
            subsystem="rate_limit",
            message="cleanup_rate_limit_hits HTTP error",
            include_exception=True,
        )
    except Exception:
        log_error_event(
            logger,
            error_code="RATE_LIMIT_PG_CLEANUP_UNEXPECTED",
            subsystem="rate_limit",
            message="cleanup_rate_limit_hits unexpected error",
            include_exception=True,
        )
    return 0


def evict_stale_rate_limit_keys(settings) -> int:
    """Remove rate-limit keys whose timestamps have all expired."""
    max_window = max(
        settings.rate_limit_analyze_window_seconds,
        settings.rate_limit_reports_window_seconds,
    )
    now = time.monotonic()
    stale_keys = [
        key
        for key, timestamps in _rate_limit_store.items()
        if not timestamps
        or all(now - timestamp >= max_window for timestamp in timestamps)
    ]
    for key in stale_keys:
        _rate_limit_store.pop(key, None)
    return len(stale_keys)


def _resolve_rate_key(request: Request, user_id: str) -> str:
    if user_id:
        return f"user:{user_id}"
    client_ip = request.client.host if request.client else "unknown"
    return client_ip


def _check_rate_limit_memory(
    key: str, *, max_requests: int, window_seconds: int
) -> bool:
    now = time.monotonic()
    timestamps = _rate_limit_store[key]
    timestamps[:] = [
        timestamp for timestamp in timestamps if now - timestamp < window_seconds
    ]
    if not timestamps:
        _rate_limit_store.pop(key, None)
        timestamps = _rate_limit_store[key]
    if len(timestamps) >= max_requests:
        return True
    timestamps.append(now)
    return False


async def _check_rate_limit_pg(
    settings,
    logger,  # type: ignore[no-untyped-def]
    key: str,
    *,
    max_requests: int,
    window_seconds: int,
) -> bool:
    url = f"{settings.supabase_url}/rest/v1/rpc/check_rate_limit"
    headers = {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "p_key": key,
        "p_max_requests": max_requests,
        "p_window_seconds": window_seconds,
    }
    try:
        response = await get_rate_limit_http_client().post(
            url,
            json=payload,
            headers=headers,
        )
        if response.status_code == 200:
            return response.json() is True
        log_error_event(
            logger,
            error_code="RATE_LIMIT_PG_RPC_FAILED",
            subsystem="rate_limit",
            details={"status_code": response.status_code},
            message="check_rate_limit RPC returned non-200",
        )
    except httpx.TimeoutException:
        log_error_event(
            logger,
            error_code="RATE_LIMIT_PG_RPC_TIMEOUT",
            subsystem="rate_limit",
            message="check_rate_limit RPC timeout",
        )
    except httpx.HTTPError:
        log_error_event(
            logger,
            error_code="RATE_LIMIT_PG_RPC_HTTP_ERROR",
            subsystem="rate_limit",
            message="check_rate_limit RPC HTTP error",
            include_exception=True,
        )
    except Exception:
        log_error_event(
            logger,
            error_code="RATE_LIMIT_PG_RPC_UNEXPECTED",
            subsystem="rate_limit",
            message="check_rate_limit RPC unexpected error",
            include_exception=True,
        )
    return _check_rate_limit_memory(
        key, max_requests=max_requests, window_seconds=window_seconds
    )


def register_rate_limit_middleware(
    app: FastAPI,
    *,
    settings,
    logger,  # type: ignore[no-untyped-def]
) -> None:
    """Wire the API rate-limiter middleware onto the app."""
    use_pg_rate_limit = bool(
        settings.supabase_url and settings.supabase_service_role_key
    )

    async def _check_rate_limit(
        key: str, *, max_requests: int, window_seconds: int
    ) -> bool:
        if use_pg_rate_limit:
            return await _check_rate_limit_pg(
                settings,
                logger,
                key,
                max_requests=max_requests,
                window_seconds=window_seconds,
            )
        return _check_rate_limit_memory(
            key, max_requests=max_requests, window_seconds=window_seconds
        )

    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        path = request.url.path
        limit_max: int | None = None
        limit_window: int | None = None
        prefix = ""

        if request.method == "POST" and path.endswith("/analyze"):
            limit_max = settings.rate_limit_analyze_max
            limit_window = settings.rate_limit_analyze_window_seconds
            prefix = "analyze:"
        elif (
            request.method == "GET"
            and path.startswith("/api/v1/reports")
            and not path.endswith("/status")
            and not path.endswith("/stream")
        ):
            limit_max = settings.rate_limit_reports_max
            limit_window = settings.rate_limit_reports_window_seconds
            prefix = "reports:"

        if limit_max is not None and limit_window is not None:
            from ideago.auth.dependencies import get_optional_user

            user_id = ""
            try:
                user = await get_optional_user(request)
                if user is not None:
                    user_id = user.id
            except Exception:
                log_error_event(
                    logger,
                    error_code="RATE_LIMIT_USER_RESOLVE_FAILED",
                    subsystem="rate_limit",
                    trace_id=getattr(request.state, "trace_id", ""),
                    message="resolve user in rate-limit middleware failed",
                    include_exception=True,
                )

            rate_key = prefix + _resolve_rate_key(request, user_id)
            if await _check_rate_limit(
                rate_key, max_requests=limit_max, window_seconds=limit_window
            ):
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": {
                            "code": ErrorCode.RATE_LIMIT_EXCEEDED.value,
                            "message": "Rate limit exceeded. Please try again later.",
                        }
                    },
                )
        return await call_next(request)
