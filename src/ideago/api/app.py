"""FastAPI application factory.

FastAPI 应用工厂。
"""

from __future__ import annotations

import secrets
import time
from collections import defaultdict
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from ideago.api.routes import analyze, health, reports
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


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup / shutdown logic."""
    yield
    from ideago.api.dependencies import _orchestrator

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
        version="0.3.0",
        description="AI-powered competitor research engine for startup ideas",
        lifespan=_lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.get_cors_allow_origins(),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def api_key_auth(request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        """Validate X-API-Key header when APP_API_KEY is configured."""
        configured_key = settings.app_api_key
        if configured_key:
            path = request.url.path
            is_api_path = path.startswith("/api/")
            is_health = path == "/api/v1/health"
            if is_api_path and not is_health:
                incoming_key = request.headers.get("X-API-Key", "")
                if not secrets.compare_digest(incoming_key, configured_key):
                    return JSONResponse(
                        status_code=401,
                        content={"detail": "Invalid or missing API key"},
                    )
        return await call_next(request)

    @app.middleware("http")
    async def rate_limit_analyze(request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        """In-memory rate limiter for /analyze, keyed by (IP, session)."""
        if request.method == "POST" and request.url.path.endswith("/analyze"):
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
