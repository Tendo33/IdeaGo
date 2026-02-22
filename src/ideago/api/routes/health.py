"""Health check endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from ideago.config.settings import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict:
    """Return service health and source availability."""
    settings = get_settings()
    return {
        "status": "ok",
        "sources": {
            "github": True,
            "tavily": bool(settings.tavily_api_key),
            "hackernews": True,
        },
    }
