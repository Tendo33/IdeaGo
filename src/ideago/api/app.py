"""FastAPI application factory.

FastAPI 应用工厂。
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from ideago.api.routes import analyze, health, reports

_FRONTEND_DIST = (
    Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "dist"
)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="IdeaGo",
        version="0.3.0",
        description="AI-powered competitor research engine for startup ideas",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router, prefix="/api/v1")
    app.include_router(analyze.router, prefix="/api/v1")
    app.include_router(reports.router, prefix="/api/v1")

    if _FRONTEND_DIST.is_dir():
        app.mount(
            "/", StaticFiles(directory=str(_FRONTEND_DIST), html=True), name="frontend"
        )

    return app
