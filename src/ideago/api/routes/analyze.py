"""Analyze endpoint — starts pipeline and streams progress via SSE.

分析端点：启动管道并通过 SSE 实时推送进度。
"""

from __future__ import annotations

import asyncio
import hashlib
import uuid
from collections.abc import AsyncGenerator

from fastapi import APIRouter, BackgroundTasks, HTTPException
from loguru import logger
from sse_starlette.sse import EventSourceResponse

from ideago.api.dependencies import (
    get_cache,
    get_orchestrator,
    get_processing_reports,
    get_report_queue,
    remove_report_queue,
)
from ideago.api.schemas import AnalyzeRequest, AnalyzeResponse
from ideago.pipeline.events import EventType, PipelineEvent

router = APIRouter(tags=["analyze"])


class _QueueCallback:
    """Push pipeline events to an asyncio queue for SSE consumption."""

    def __init__(self, queue: asyncio.Queue) -> None:
        self._queue = queue

    async def on_event(self, event: PipelineEvent) -> None:
        await self._queue.put(event)


async def _run_pipeline(query: str, report_id: str) -> None:
    """Background task: run the pipeline and push events to the queue."""
    cache = get_cache()
    queue = get_report_queue(report_id)
    callback = _QueueCallback(queue)
    await cache.put_status(report_id, "processing", query)
    try:
        orchestrator = get_orchestrator()
        report = await orchestrator.run(query, callback=callback, report_id=report_id)
        logger.info("Pipeline completed for report {}", report.id)
        await cache.put_status(report_id, "complete", query)
    except Exception as exc:
        logger.exception("Pipeline failed for report {}", report_id)
        await cache.put_status(report_id, "failed", query)
        await queue.put(
            PipelineEvent(
                type=EventType.ERROR,
                stage="pipeline",
                message=f"Pipeline failed: {exc}",
            )
        )
    finally:
        processing = get_processing_reports()
        keys_to_remove = [k for k, v in processing.items() if v == report_id]
        for k in keys_to_remove:
            processing.pop(k, None)


@router.post("/analyze", response_model=AnalyzeResponse)
async def start_analysis(
    request: AnalyzeRequest,
    background_tasks: BackgroundTasks,
) -> AnalyzeResponse:
    """Start a competitor research pipeline for the given idea."""
    query = request.query.strip()

    processing = get_processing_reports()
    query_hash = hashlib.sha256(query.encode()).hexdigest()[:16]
    if query_hash in processing:
        return AnalyzeResponse(report_id=processing[query_hash])

    report_id = str(uuid.uuid4())
    get_report_queue(report_id)
    processing[query_hash] = report_id

    background_tasks.add_task(_run_pipeline, query, report_id)
    return AnalyzeResponse(report_id=report_id)


@router.get("/reports/{report_id}/stream")
async def stream_progress(report_id: str) -> EventSourceResponse:
    """SSE endpoint — stream pipeline progress events for a report."""

    async def event_generator() -> AsyncGenerator[dict, None]:
        queue = get_report_queue(report_id)
        try:
            while True:
                try:
                    event: PipelineEvent = await asyncio.wait_for(
                        queue.get(), timeout=120
                    )
                    yield {"event": event.type.value, "data": event.to_sse()}
                    if event.type in (EventType.REPORT_READY, EventType.ERROR):
                        break
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": "{}"}
        finally:
            remove_report_queue(report_id)

    return EventSourceResponse(event_generator())


@router.delete("/reports/{report_id}/cancel")
async def cancel_analysis(report_id: str) -> dict:
    """Cancel an in-progress analysis by pushing an error event to the SSE queue."""
    processing = get_processing_reports()
    if report_id not in processing.values():
        raise HTTPException(
            status_code=404, detail="No active analysis found for this report"
        )

    queue = get_report_queue(report_id)
    await queue.put(
        PipelineEvent(
            type=EventType.ERROR,
            stage="pipeline",
            message="Analysis cancelled by user",
        )
    )

    keys_to_remove = [k for k, v in processing.items() if v == report_id]
    for k in keys_to_remove:
        processing.pop(k, None)

    logger.info("Analysis cancelled for report {}", report_id)
    return {"status": "cancelled"}
