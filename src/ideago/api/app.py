"""FastAPI application factory.

FastAPI 应用工厂。
"""

from __future__ import annotations

import asyncio
import contextlib
import time
import uuid
from collections import defaultdict
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from ideago import __version__
from ideago.api.errors import AppError, ErrorCode
from ideago.api.routes import admin, analyze, auth, billing, health, reports
from ideago.config.settings import get_settings
from ideago.observability.error_catalog import AlertLevel, log_error_event
from ideago.observability.log_config import get_logger

logger = get_logger(__name__)


_FRONTEND_DIST = (
    Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "dist"
)
_FRONTEND_INDEX = _FRONTEND_DIST / "index.html"

_rate_limit_store: dict[str, list[float]] = defaultdict(list)

_TURNSTILE_ORIGIN = "https://challenges.cloudflare.com"
_GOOGLE_FONTS_STYLES_ORIGIN = "https://fonts.googleapis.com"
_GOOGLE_FONTS_ASSETS_ORIGIN = "https://fonts.gstatic.com"


_cleanup_task: asyncio.Task[None] | None = None
_CLEANUP_INTERVAL_SECONDS = 3600
_rate_limit_http_client: httpx.AsyncClient | None = None


def _get_rate_limit_http_client() -> httpx.AsyncClient:
    global _rate_limit_http_client
    if _rate_limit_http_client is None:
        _rate_limit_http_client = httpx.AsyncClient(
            timeout=3.0,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
    return _rate_limit_http_client


async def _cleanup_pg_rate_limit_hits() -> int:
    """Cleanup stale PG-backed rate-limit rows. Returns removed row count."""
    settings = get_settings()
    supabase_url = getattr(settings, "supabase_url", "")
    service_role_key = getattr(settings, "supabase_service_role_key", "")
    if not supabase_url or not service_role_key:
        return 0
    try:
        response = await _get_rate_limit_http_client().post(
            f"{supabase_url}/rest/v1/rpc/cleanup_rate_limit_hits",
            headers={
                "apikey": service_role_key,
                "Authorization": f"Bearer {service_role_key}",
                "Content-Type": "application/json",
            },
            json={"p_max_age_seconds": max(_CLEANUP_INTERVAL_SECONDS * 2, 7200)},
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


def _evict_stale_rate_limit_keys() -> int:
    """Remove rate-limit keys whose timestamps have all expired."""
    settings = get_settings()
    max_window = max(
        settings.rate_limit_analyze_window_seconds,
        settings.rate_limit_reports_window_seconds,
    )
    now = time.monotonic()
    stale_keys = [
        k
        for k, ts in _rate_limit_store.items()
        if not ts or all(now - t >= max_window for t in ts)
    ]
    for k in stale_keys:
        _rate_limit_store.pop(k, None)
    return len(stale_keys)


async def _periodic_cleanup() -> None:
    """Background task: clean up expired reports and stale rate-limit keys."""
    from ideago.api.dependencies import get_cache

    while True:
        await asyncio.sleep(_CLEANUP_INTERVAL_SECONDS)
        try:
            removed = await get_cache().cleanup_expired()
            if removed > 0:
                logger.info("Cleaned up {} expired reports", removed)
        except Exception:
            log_error_event(
                logger,
                error_code="CACHE_CLEANUP_FAILED",
                subsystem="maintenance",
                message="periodic cache cleanup failed",
                include_exception=True,
            )
        pg_removed = await _cleanup_pg_rate_limit_hits()
        if pg_removed > 0:
            logger.debug("Cleaned up {} stale PG rate-limit rows", pg_removed)
        evicted = _evict_stale_rate_limit_keys()
        if evicted > 0:
            logger.debug("Evicted {} stale rate-limit keys", evicted)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup / shutdown logic."""
    global _cleanup_task, _rate_limit_http_client
    _cleanup_task = asyncio.create_task(_periodic_cleanup())
    yield
    if _cleanup_task is not None:
        _cleanup_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _cleanup_task
    from ideago.api.dependencies import _cache, _orchestrator, shutdown_runtime_state
    from ideago.auth.dependencies import close_auth_http_client
    from ideago.auth.supabase_admin import close_supabase_admin_client
    from ideago.observability.audit import close_audit_client

    await shutdown_runtime_state()
    await close_auth_http_client()
    await close_supabase_admin_client()
    await close_audit_client()
    if _cache is not None and hasattr(_cache, "close"):
        await _cache.close()
    if _rate_limit_http_client is not None:
        await _rate_limit_http_client.aclose()
        _rate_limit_http_client = None
    _rate_limit_store.clear()

    if _orchestrator is None:
        return
    for source in _orchestrator.get_all_sources():
        if hasattr(source, "close"):
            try:
                await source.close()
            except Exception:
                logger.warning("Failed to close source {}", source.platform.value)


def _init_sentry(settings) -> None:
    """Initialize Sentry SDK if a DSN is configured."""
    if not settings.sentry_dsn:
        return
    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        environment=settings.environment,
        release=__version__,
        send_default_pii=False,
    )
    logger.info("Sentry initialized (env={})", settings.environment)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()
    _init_sentry(settings)
    app = FastAPI(
        title="IdeaGo",
        version=__version__,
        description="AI-powered competitor research engine for startup ideas",
        lifespan=_lifespan,
    )
    origins = settings.get_cors_allow_origins()
    if origins == ["*"]:
        if settings.environment == "production":
            raise RuntimeError(
                "CORS_ALLOW_ORIGINS must be explicitly configured in production. "
                "Set the CORS_ALLOW_ORIGINS environment variable to a comma-separated "
                "list of allowed origins (e.g. 'https://ideago.example.com')."
            )
        origins = [
            "http://localhost:5173",
            "http://localhost:3000",
            "http://127.0.0.1:5173",
        ]
        logger.info("CORS: using default dev origins {}", origins)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from ideago.observability.metrics import metrics as _app_metrics

    @app.middleware("http")
    async def trace_id_middleware(request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        """Attach a unique trace ID and record metrics for every request."""
        trace_id = request.headers.get("X-Trace-Id") or uuid.uuid4().hex
        request.state.trace_id = trace_id
        start = time.monotonic()
        response: Response = await call_next(request)
        latency_ms = (time.monotonic() - start) * 1000
        _app_metrics.record(request.url.path, response.status_code, latency_ms)
        response.headers["X-Trace-Id"] = trace_id
        return response

    _CSRF_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
    _CSRF_EXEMPT_PATHS = {"/api/v1/billing/webhook"}
    _STRICT_CSP = (
        "default-src 'self'; "
        f"script-src 'self' {_TURNSTILE_ORIGIN}; "
        f"style-src 'self' 'unsafe-inline' {_GOOGLE_FONTS_STYLES_ORIGIN}; "
        "img-src 'self' data: https:; "
        "connect-src 'self' https:; "
        f"frame-src 'self' {_TURNSTILE_ORIGIN}; "
        f"font-src 'self' data: {_GOOGLE_FONTS_ASSETS_ORIGIN}; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )
    _DOCS_CSP = (
        "default-src 'self' https:; "
        "script-src 'self' 'unsafe-inline' https:; "
        "style-src 'self' 'unsafe-inline' https:; "
        "img-src 'self' data: https:; "
        "connect-src 'self' https:; "
        "font-src 'self' data: https:; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )
    _DOCS_PATHS = {path for path in (app.docs_url, app.redoc_url) if path}

    @app.middleware("http")
    async def csrf_protection(request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        """Reject cross-origin state-changing requests without a custom header.

        Browsers block cross-origin JS from setting custom headers, so
        requiring `X-Requested-With` on mutating API calls prevents CSRF
        while remaining transparent to our own SPA (which always sends it).

        Webhook endpoints are exempt because they use signature verification
        instead of CSRF tokens.
        """
        if (
            request.method in _CSRF_METHODS
            and request.url.path.startswith("/api/")
            and request.url.path not in _CSRF_EXEMPT_PATHS
            and not request.headers.get("X-Requested-With")
        ):
            return JSONResponse(
                status_code=403,
                content={
                    "error": {
                        "code": ErrorCode.CSRF_MISSING_HEADER.value,
                        "message": "Missing required header: X-Requested-With",
                    }
                },
            )
        return await call_next(request)

    def _resolve_rate_key(request: Request, user_id: str) -> str:
        if user_id:
            return f"user:{user_id}"
        client_ip = request.client.host if request.client else "unknown"
        session_id = request.headers.get("X-Session-Id", "")
        return f"{client_ip}:{session_id}" if session_id else client_ip

    def _check_rate_limit_memory(
        key: str, *, max_requests: int, window_seconds: int
    ) -> bool:
        """In-memory sliding-window check. Returns True when over limit."""
        now = time.monotonic()
        timestamps = _rate_limit_store[key]
        timestamps[:] = [t for t in timestamps if now - t < window_seconds]
        if not timestamps:
            _rate_limit_store.pop(key, None)
            timestamps = _rate_limit_store[key]
        if len(timestamps) >= max_requests:
            return True
        timestamps.append(now)
        return False

    _use_pg_rate_limit = bool(
        settings.supabase_url and settings.supabase_service_role_key
    )

    async def _check_rate_limit_pg(
        key: str, *, max_requests: int, window_seconds: int
    ) -> bool:
        """PG-backed sliding-window check via Supabase RPC."""
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
            resp = await _get_rate_limit_http_client().post(
                url,
                json=payload,
                headers=headers,
            )
            if resp.status_code == 200:
                return resp.json() is True
            log_error_event(
                logger,
                error_code="RATE_LIMIT_PG_RPC_FAILED",
                subsystem="rate_limit",
                details={"status_code": resp.status_code},
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

    async def _check_rate_limit(
        key: str, *, max_requests: int, window_seconds: int
    ) -> bool:
        if _use_pg_rate_limit:
            return await _check_rate_limit_pg(
                key, max_requests=max_requests, window_seconds=window_seconds
            )
        return _check_rate_limit_memory(
            key, max_requests=max_requests, window_seconds=window_seconds
        )

    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        """Sliding-window rate limiter for /analyze and /reports.

        Uses PG-backed rate limiting when Supabase is configured (works across
        multiple workers/nodes). Falls back to in-memory for dev mode.

        Keys by authenticated user ID. Falls back to IP + session for
        unauthenticated requests.
        """
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

    @app.middleware("http")
    async def security_headers_middleware(request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        """Add standard security headers to all responses."""
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )
        response.headers["Content-Security-Policy"] = (
            _DOCS_CSP if request.url.path in _DOCS_PATHS else _STRICT_CSP
        )
        if settings.environment == "production":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        return response

    @app.exception_handler(AppError)
    async def _app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        log_error_event(
            logger,
            error_code=exc.code.value,
            subsystem="api",
            trace_id=getattr(request.state, "trace_id", ""),
            message="application error",
            details={"status_code": exc.status_code},
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.detail},
        )

    _STATUS_TO_ERROR_CODE = {
        400: ErrorCode.VALIDATION_ERROR,
        401: ErrorCode.NOT_AUTHORIZED,
        403: ErrorCode.NOT_AUTHORIZED,
        404: ErrorCode.NOT_FOUND,
        503: ErrorCode.AUTH_NOT_CONFIGURED,
    }

    @app.exception_handler(HTTPException)
    async def _http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
        """Normalise plain HTTPException into the unified error envelope."""
        if isinstance(exc, AppError):
            return await _app_error_handler(request, exc)
        code = _STATUS_TO_ERROR_CODE.get(exc.status_code, ErrorCode.INTERNAL_ERROR)
        message = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        alert_level = AlertLevel.WARNING if exc.status_code in {401, 403} else None
        log_error_event(
            logger,
            error_code=code.value,
            subsystem="api",
            trace_id=getattr(request.state, "trace_id", ""),
            message="http exception",
            details={"status_code": exc.status_code},
            alert_level=alert_level,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": code.value, "message": message}},
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Return 422 validation errors in the unified error envelope."""
        errors = exc.errors()
        if errors:
            first = errors[0]
            loc = " → ".join(str(p) for p in first.get("loc", []))
            message = f"{loc}: {first.get('msg', 'Validation error')}"
        else:
            message = "Request validation failed"
        log_error_event(
            logger,
            error_code=ErrorCode.VALIDATION_ERROR.value,
            subsystem="api",
            trace_id=getattr(request.state, "trace_id", ""),
            message="request validation failed",
            details={"errors_count": len(errors)},
        )
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": ErrorCode.VALIDATION_ERROR.value,
                    "message": message,
                }
            },
        )

    app.include_router(health.router, prefix="/api/v1")
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(analyze.router, prefix="/api/v1")
    app.include_router(reports.router, prefix="/api/v1")
    app.include_router(billing.router, prefix="/api/v1")
    app.include_router(admin.router, prefix="/api/v1")

    if _FRONTEND_DIST.is_dir():
        assets_dir = _FRONTEND_DIST / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)))

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa_fallback(full_path: str) -> FileResponse:
            """
            SPA fallback for direct URL access.

            - API routes are handled by routers above.
            - Existing files in dist are served directly.
            - Other frontend routes fall back to index.html.
            """
            requested_path = (_FRONTEND_DIST / full_path).resolve()
            dist_root = _FRONTEND_DIST.resolve()
            if requested_path.is_file() and requested_path.is_relative_to(dist_root):
                return FileResponse(path=requested_path)
            if full_path.startswith("api/"):
                raise AppError(404, ErrorCode.NOT_FOUND, "Not Found")
            if Path(full_path).suffix:
                raise AppError(404, ErrorCode.NOT_FOUND, "Not Found")
            return FileResponse(path=_FRONTEND_INDEX)

    return app
