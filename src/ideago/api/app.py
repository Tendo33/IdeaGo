"""FastAPI application factory.

FastAPI 应用工厂。
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from collections import defaultdict
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from ideago import __version__
from ideago.api.routes import analyze, auth, health, reports
from ideago.config.settings import get_settings
from ideago.observability.log_config import get_logger

logger = get_logger(__name__)


_FRONTEND_DIST = (
    Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "dist"
)
_FRONTEND_INDEX = _FRONTEND_DIST / "index.html"

_rate_limit_store: dict[str, list[float]] = defaultdict(list)
_RATE_LIMIT_MAX = 10
_RATE_LIMIT_WINDOW = 60


_cleanup_task: asyncio.Task[None] | None = None
_CLEANUP_INTERVAL_SECONDS = 3600


async def _periodic_cleanup() -> None:
    """Background task: clean up expired reports every hour."""
    from ideago.api.dependencies import get_cache

    while True:
        await asyncio.sleep(_CLEANUP_INTERVAL_SECONDS)
        try:
            removed = await get_cache().cleanup_expired()
            if removed > 0:
                logger.info("Cleaned up {} expired reports", removed)
        except Exception:
            logger.opt(exception=True).warning("Cleanup task error")


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

    await shutdown_runtime_state()
    await close_auth_http_client()
    await close_supabase_admin_client()
    if _cache is not None and hasattr(_cache, "close"):
        await _cache.close()
    _rate_limit_store.clear()

    if _orchestrator is None:
        return
    for source in _orchestrator.get_all_sources():
        if hasattr(source, "close"):
            try:
                await source.close()
            except Exception:
                logger.warning("Failed to close source {}", source.platform.value)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()
    app = FastAPI(
        title="IdeaGo",
        version=__version__,
        description="AI-powered competitor research engine for startup ideas",
        lifespan=_lifespan,
    )
    origins = settings.get_cors_allow_origins()
    if origins == ["*"]:
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

    _CSRF_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

    @app.middleware("http")
    async def csrf_protection(request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        """Reject cross-origin state-changing requests without a custom header.

        Browsers block cross-origin JS from setting custom headers, so
        requiring `X-Requested-With` on mutating API calls prevents CSRF
        while remaining transparent to our own SPA (which always sends it).
        """
        if (
            request.method in _CSRF_METHODS
            and request.url.path.startswith("/api/")
            and not request.headers.get("X-Requested-With")
        ):
            return JSONResponse(
                status_code=403,
                content={"detail": "Missing required header: X-Requested-With"},
            )
        return await call_next(request)

    @app.middleware("http")
    async def rate_limit_analyze(request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        """In-memory rate limiter for /analyze.

        Keys by authenticated user ID when available (survives proxy/LB
        changes), falls back to IP + session for unauthenticated requests.
        The Supabase quota system (check_and_increment_quota) provides the
        durable monthly cap; this layer only throttles burst frequency.
        """
        if request.method == "POST" and request.url.path.endswith("/analyze"):
            auth_header = request.headers.get("Authorization", "")
            user_id = ""
            if auth_header.startswith("Bearer "):
                import jwt as _jwt

                token = auth_header.removeprefix("Bearer ").strip()
                jwt_secret = settings.supabase_jwt_secret
                if jwt_secret:
                    try:
                        payload = _jwt.decode(
                            token,
                            jwt_secret,
                            algorithms=["HS256"],
                            audience="authenticated",
                        )
                        user_id = payload.get("sub", "")
                    except _jwt.InvalidTokenError:
                        pass

            if user_id:
                rate_key = f"user:{user_id}"
            else:
                client_ip = request.client.host if request.client else "unknown"
                session_id = request.headers.get("X-Session-Id", "")
                rate_key = f"{client_ip}:{session_id}" if session_id else client_ip

            now = time.monotonic()
            timestamps = _rate_limit_store[rate_key]
            timestamps[:] = [t for t in timestamps if now - t < _RATE_LIMIT_WINDOW]
            if len(timestamps) >= _RATE_LIMIT_MAX:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded. Please try again later."},
                )
            timestamps.append(now)
        return await call_next(request)

    app.include_router(health.router, prefix="/api/v1")
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(analyze.router, prefix="/api/v1")
    app.include_router(reports.router, prefix="/api/v1")

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
                raise HTTPException(status_code=404, detail="Not Found")
            if Path(full_path).suffix:
                raise HTTPException(status_code=404, detail="Not Found")
            return FileResponse(path=_FRONTEND_INDEX)

    return app
