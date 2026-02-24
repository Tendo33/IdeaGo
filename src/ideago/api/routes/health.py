"""Health check endpoint."""

from __future__ import annotations

from fastapi import APIRouter
from loguru import logger

from ideago.api.dependencies import get_orchestrator

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict:
    """Return service health and source availability."""
    status = "ok"
    try:
        orchestrator = get_orchestrator()
        sources_status = orchestrator.get_source_availability()
    except Exception:
        logger.warning("Could not initialize orchestrator for health check")
        status = "degraded"
        sources_status = {}
    return {
        "status": status,
        "sources": sources_status,
    }
