"""Health check endpoint."""

from __future__ import annotations

from fastapi import APIRouter
from loguru import logger

from ideago.api.dependencies import get_orchestrator

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict:
    """Return service health and source availability."""
    try:
        orchestrator = get_orchestrator()
        sources_status = {
            s.platform.value: s.is_available() for s in orchestrator._registry.get_all()
        }
    except Exception:
        logger.warning("Could not initialize orchestrator for health check")
        sources_status = {}
    return {
        "status": "ok",
        "sources": sources_status,
    }
