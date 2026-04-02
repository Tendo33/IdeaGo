"""FastAPI application factory.

FastAPI 应用工厂。
"""

from __future__ import annotations

import asyncio
import contextlib
import time as time_module
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError as FastAPIRequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ideago import __version__
from ideago.api.errors import ErrorCode as ApiErrorCode
from ideago.api.exception_handlers import register_exception_handlers
from ideago.api.http_middleware import (
    register_csrf_protection_middleware,
    register_security_headers_middleware,
    register_trace_id_middleware,
)
from ideago.api.rate_limit import (
    cleanup_pg_rate_limit_hits,
    clear_rate_limit_state,
    close_rate_limit_http_client,
    evict_stale_rate_limit_keys,
    get_rate_limit_store,
    register_rate_limit_middleware,
)
from ideago.api.routes import admin, analyze, auth, health, reports

# from ideago.api.routes import billing
from ideago.config.settings import get_settings
from ideago.observability.error_catalog import log_error_event
from ideago.observability.log_config import get_logger

logger = get_logger(__name__)
time = time_module
RequestValidationError = FastAPIRequestValidationError
ErrorCode = ApiErrorCode

_FRONTEND_DIST = (
    Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "dist"
)
_FRONTEND_INDEX = _FRONTEND_DIST / "index.html"
_CLEANUP_INTERVAL_SECONDS = 3600
_cleanup_task: asyncio.Task[None] | None = None

# Backward-compatible aliases used by tests.
_rate_limit_store = get_rate_limit_store()


async def _cleanup_pg_rate_limit_hits() -> int:
    return await cleanup_pg_rate_limit_hits(
        get_settings(),
        logger,
        cleanup_interval_seconds=_CLEANUP_INTERVAL_SECONDS,
    )


def _evict_stale_rate_limit_keys() -> int:
    return evict_stale_rate_limit_keys(get_settings())


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
    global _cleanup_task
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
    await close_rate_limit_http_client()
    clear_rate_limit_state()

    if _orchestrator is None:
        return
    for source in _orchestrator.get_all_sources():
        if hasattr(source, "close"):
            try:
                await source.close()
            except Exception:
                logger.warning("Failed to close source {}", source.platform.value)


def _init_sentry(settings) -> None:  # type: ignore[no-untyped-def]
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


def _configure_cors(app: FastAPI, settings) -> None:  # type: ignore[no-untyped-def]
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


def _register_routes(app: FastAPI) -> None:
    app.include_router(health.router, prefix="/api/v1")
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(analyze.router, prefix="/api/v1")
    app.include_router(reports.router, prefix="/api/v1")
    # app.include_router(billing.router, prefix="/api/v1")
    app.include_router(admin.router, prefix="/api/v1")


def _register_spa_fallback(app: FastAPI) -> None:
    if not _FRONTEND_DIST.is_dir():
        return

    assets_dir = _FRONTEND_DIST / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)))

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str) -> FileResponse:
        """Serve built frontend assets and fall back to index.html."""
        requested_path = (_FRONTEND_DIST / full_path).resolve()
        dist_root = _FRONTEND_DIST.resolve()
        if requested_path.is_file() and requested_path.is_relative_to(dist_root):
            return FileResponse(path=requested_path)
        if full_path.startswith("api/"):
            from ideago.api.errors import AppError, ErrorCode

            raise AppError(404, ErrorCode.NOT_FOUND, "Not Found")
        if Path(full_path).suffix:
            from ideago.api.errors import AppError, ErrorCode

            raise AppError(404, ErrorCode.NOT_FOUND, "Not Found")
        return FileResponse(path=_FRONTEND_INDEX)


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

    _configure_cors(app, settings)
    register_csrf_protection_middleware(app)
    register_rate_limit_middleware(app, settings=settings, logger=logger)
    register_security_headers_middleware(app, environment=settings.environment)
    register_trace_id_middleware(app)
    register_exception_handlers(app, logger, log_error_event_fn=log_error_event)
    _register_routes(app)
    _register_spa_fallback(app)
    return app
