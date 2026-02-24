"""Analyze endpoint — starts pipeline and streams progress via SSE.

分析端点：启动管道并通过 SSE 实时推送进度。
"""

from __future__ import annotations

import asyncio
import hashlib
import uuid
from collections.abc import AsyncGenerator

from fastapi import APIRouter, HTTPException
from loguru import logger
from sse_starlette.sse import EventSourceResponse

from ideago.api.dependencies import (
    cleanup_report_runs,
    clear_processing_report,
    get_cache,
    get_or_create_report_run,
    get_orchestrator,
    get_pipeline_task,
    get_processing_reports,
    get_report_run,
    pop_pipeline_task,
    set_pipeline_task,
)
from ideago.api.schemas import AnalyzeRequest, AnalyzeResponse
from ideago.pipeline.events import EventType, PipelineEvent

router = APIRouter(tags=["analyze"])
_TERMINAL_EVENTS = {EventType.REPORT_READY, EventType.ERROR, EventType.CANCELLED}


async def _mark_cancelled(report_id: str) -> None:
    """Persist cancelled state and broadcast terminal cancellation event."""
    run_state = get_or_create_report_run(report_id)
    if not run_state.is_terminal:
        await run_state.publish(
            PipelineEvent(
                type=EventType.CANCELLED,
                stage="pipeline",
                message="Analysis cancelled by user",
                data={"report_id": report_id},
            )
        )
    await get_cache().put_status(report_id, "cancelled")


class _RunStateCallback:
    """Push pipeline events into report runtime state for SSE consumption."""

    def __init__(self, report_id: str) -> None:
        self._report_id = report_id

    async def on_event(self, event: PipelineEvent) -> None:
        run_state = get_or_create_report_run(self._report_id)
        await run_state.publish(event)


async def _run_pipeline(query: str, report_id: str) -> None:
    """Background task: run the pipeline and push events to the queue."""
    cache = get_cache()
    run_state = get_or_create_report_run(report_id)
    callback = _RunStateCallback(report_id)
    try:
        await cache.put_status(report_id, "processing", query)
        orchestrator = get_orchestrator()
        report = await orchestrator.run(query, callback=callback, report_id=report_id)
        if run_state.history and run_state.history[-1].type == EventType.CANCELLED:
            logger.info("Skipping completion for cancelled report {}", report_id)
            return
        logger.info("Pipeline completed for report {}", report.id)
        await cache.put_status(report_id, "complete", query)
    except asyncio.CancelledError:
        logger.info("Pipeline cancelled for report {}", report_id)
        await _mark_cancelled(report_id)
    except Exception as exc:
        logger.exception("Pipeline failed for report {}", report_id)
        await cache.put_status(report_id, "failed", query)
        await run_state.publish(
            PipelineEvent(
                type=EventType.ERROR,
                stage="pipeline",
                message=f"Pipeline failed: {exc}",
                data={"report_id": report_id},
            )
        )
    finally:
        clear_processing_report(report_id)
        pop_pipeline_task(report_id)
        cleanup_report_runs()


@router.post("/analyze", response_model=AnalyzeResponse)
async def start_analysis(request: AnalyzeRequest) -> AnalyzeResponse:
    """Start a competitor research pipeline for the given idea."""
    query = request.query.strip()

    processing = get_processing_reports()
    query_hash = hashlib.sha256(query.encode()).hexdigest()[:16]
    existing_report_id = processing.get(query_hash)
    if existing_report_id:
        task = get_pipeline_task(existing_report_id)
        if task and not task.done():
            return AnalyzeResponse(report_id=existing_report_id)
        processing.pop(query_hash, None)

    report_id = str(uuid.uuid4())
    get_or_create_report_run(report_id)
    processing[query_hash] = report_id

    task = asyncio.create_task(_run_pipeline(query, report_id))
    set_pipeline_task(report_id, task)
    return AnalyzeResponse(report_id=report_id)


async def _status_terminal_event(report_id: str) -> PipelineEvent | None:
    """Resolve status-file state into a terminal SSE event if available."""
    status = await get_cache().get_status(report_id)
    if not status:
        return None
    state = status.get("status")
    if state == "complete":
        return PipelineEvent(
            type=EventType.REPORT_READY,
            stage="complete",
            message="Report ready",
            data={"report_id": report_id},
        )
    if state == "cancelled":
        return PipelineEvent(
            type=EventType.CANCELLED,
            stage="pipeline",
            message="Analysis cancelled by user",
            data={"report_id": report_id},
        )
    if state == "failed":
        return PipelineEvent(
            type=EventType.ERROR,
            stage="pipeline",
            message="Pipeline failed",
            data={"report_id": report_id},
        )
    return None


async def _stream_events(report_id: str) -> AsyncGenerator[dict, None]:
    """Yield replay + live SSE events for a report run."""
    run_state = get_report_run(report_id)
    if run_state is None:
        terminal = await _status_terminal_event(report_id)
        if terminal is None:
            terminal = PipelineEvent(
                type=EventType.ERROR,
                stage="pipeline",
                message="No active analysis found for this report",
                data={"report_id": report_id},
            )
        yield {"event": terminal.type.value, "data": terminal.to_sse()}
        return

    for event in run_state.history_snapshot():
        yield {"event": event.type.value, "data": event.to_sse()}

    if run_state.is_terminal:
        return

    queue = run_state.subscribe()
    try:
        while True:
            try:
                queued_event: PipelineEvent = await asyncio.wait_for(
                    queue.get(), timeout=120
                )
                yield {"event": queued_event.type.value, "data": queued_event.to_sse()}
                if queued_event.type in _TERMINAL_EVENTS:
                    break
            except asyncio.TimeoutError:
                yield {"event": "ping", "data": "{}"}
    finally:
        run_state.unsubscribe(queue)
        cleanup_report_runs()


@router.get("/reports/{report_id}/stream")
async def stream_progress(report_id: str) -> EventSourceResponse:
    """SSE endpoint — stream pipeline progress events for a report."""
    return EventSourceResponse(_stream_events(report_id))


@router.delete("/reports/{report_id}/cancel")
async def cancel_analysis(report_id: str) -> dict:
    """Cancel an in-progress analysis task."""
    processing = get_processing_reports()
    task = get_pipeline_task(report_id)
    if (task is None or task.done()) and report_id not in processing.values():
        raise HTTPException(
            status_code=404, detail="No active analysis found for this report"
        )

    if task is not None and not task.done():
        task.cancel()
        await _mark_cancelled(report_id)
        clear_processing_report(report_id)
    else:
        await _mark_cancelled(report_id)
        clear_processing_report(report_id)

    logger.info("Analysis cancelled for report {}", report_id)
    return {"status": "cancelled"}
