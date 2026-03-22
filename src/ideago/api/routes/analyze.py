"""Analyze endpoint — starts pipeline and streams progress via SSE.

分析端点：启动管道并通过 SSE 实时推送进度。
"""

from __future__ import annotations

import asyncio
import hashlib
import uuid
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from ideago.api.dependencies import (
    cleanup_report_runs,
    get_cache,
    get_or_create_report_run,
    get_orchestrator,
    get_pipeline_task_for_report,
    get_report_run,
    is_processing_report,
    register_pipeline_task,
    release_processing_report,
    remove_pipeline_task,
    reserve_processing_report,
)
from ideago.api.errors import AppError, ErrorCode
from ideago.api.schemas import AnalyzeRequest, AnalyzeResponse
from ideago.auth.dependencies import get_current_user
from ideago.auth.models import AuthUser
from ideago.auth.supabase_admin import check_and_increment_quota
from ideago.notifications.service import notify_quota_warning, notify_report_ready
from ideago.observability.log_config import get_logger
from ideago.pipeline.events import EventType, PipelineEvent

logger = get_logger(__name__)

router = APIRouter(tags=["analyze"])
_TERMINAL_EVENTS = {EventType.REPORT_READY, EventType.ERROR, EventType.CANCELLED}
_STATUS_ONLY_PING_INTERVAL_SECONDS = 2
_STATUS_ONLY_MAX_WAIT_SECONDS = 180
_STATUS_ONLY_MAX_PINGS = (
    _STATUS_ONLY_MAX_WAIT_SECONDS // _STATUS_ONLY_PING_INTERVAL_SECONDS
)
_ACTIVE_STREAM_PING_INTERVAL_SECONDS = 15


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
    cache = get_cache()
    existing_user_id = ""
    existing_status = await cache.get_status(report_id)
    if existing_status:
        existing_user_id = existing_status.get("user_id", "") or ""
    await cache.put_status(
        report_id,
        "cancelled",
        error_code="PIPELINE_CANCELLED",
        message="Analysis cancelled by user",
        user_id=existing_user_id,
    )


class _RunStateCallback:
    """Push pipeline events into report runtime state for SSE consumption."""

    def __init__(self, report_id: str) -> None:
        self._report_id = report_id

    async def on_event(self, event: PipelineEvent) -> None:
        run_state = get_or_create_report_run(self._report_id)
        await run_state.publish(event)


async def _run_pipeline(
    query: str, report_id: str, user_id: str = "", user_email: str = ""
) -> None:
    """Background task: run the pipeline and push events to the queue."""
    cache = get_cache()
    run_state = get_or_create_report_run(report_id)
    callback = _RunStateCallback(report_id)
    try:
        orchestrator = get_orchestrator()
        report = await orchestrator.run(
            query, callback=callback, report_id=report_id, user_id=user_id
        )
        if run_state.history and run_state.history[-1].type == EventType.CANCELLED:
            logger.info("Skipping completion for cancelled report {}", report_id)
            return
        logger.info("Pipeline completed for report {}", report.id)
        await cache.put_status(
            report_id,
            "complete",
            query,
            message="Report ready",
            user_id=user_id,
        )
        if user_email:
            try:
                await notify_report_ready(user_email, report_id, query)
            except Exception:
                logger.debug("Failed to send report-ready notification")
    except asyncio.CancelledError:
        logger.info("Pipeline cancelled for report {}", report_id)
        await _mark_cancelled(report_id)
    except Exception:
        logger.exception("Pipeline failed for report {}", report_id)
        await cache.put_status(
            report_id,
            "failed",
            query,
            error_code="PIPELINE_FAILURE",
            message="Pipeline failed. Please retry.",
            user_id=user_id,
        )
        await run_state.publish(
            PipelineEvent(
                type=EventType.ERROR,
                stage="pipeline",
                message="Pipeline failed. Please retry.",
                data={
                    "report_id": report_id,
                    "error_code": "PIPELINE_FAILURE",
                },
            )
        )
    finally:
        await release_processing_report(report_id)
        await remove_pipeline_task(report_id)
        cleanup_report_runs()


@router.post("/analyze", response_model=AnalyzeResponse)
async def start_analysis(
    request: AnalyzeRequest,
    user: AuthUser = Depends(get_current_user),
) -> AnalyzeResponse:
    """Start a competitor research pipeline for the given idea."""
    quota = await check_and_increment_quota(user.id)
    if not quota.allowed:
        raise AppError(
            429,
            ErrorCode.QUOTA_EXCEEDED,
            f"Monthly limit reached ({quota.plan_limit} analyses on {quota.plan} plan)",
        )

    query = request.query.strip()

    query_hash = hashlib.sha256(query.encode()).hexdigest()[:16]
    report_id = str(uuid.uuid4())
    existing_report_id = await reserve_processing_report(
        query_hash, report_id, user_id=user.id
    )
    if existing_report_id is not None:
        return AnalyzeResponse(report_id=existing_report_id)

    cache = get_cache()
    await cache.put_status(
        report_id,
        "processing",
        query,
        message="Analysis is in progress",
        user_id=user.id,
    )

    get_or_create_report_run(report_id)

    if quota.usage_count >= int(quota.plan_limit * 0.8) and user.email:
        try:
            await notify_quota_warning(user.email, quota.usage_count, quota.plan_limit)
        except Exception:
            logger.debug("Failed to send quota warning notification")

    task = asyncio.create_task(
        _run_pipeline(query, report_id, user.id, user_email=user.email)
    )
    await register_pipeline_task(report_id, task)
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
            message=status.get("message", "Analysis cancelled by user"),
            data={"report_id": report_id},
        )
    if state == "failed":
        return PipelineEvent(
            type=EventType.ERROR,
            stage="pipeline",
            message=status.get("message", "Pipeline failed"),
            data={
                "report_id": report_id,
                "error_code": status.get("error_code", "PIPELINE_FAILURE"),
            },
        )
    return None


async def _stream_events(report_id: str) -> AsyncGenerator[dict, None]:
    """Yield replay + live SSE events for a report run."""
    run_state = get_report_run(report_id)
    if run_state is None:
        processing_ping_count = 0
        while True:
            status = await get_cache().get_status(report_id)
            if status and status.get("status") == "processing":
                if processing_ping_count >= _STATUS_ONLY_MAX_PINGS:
                    stale_terminal = PipelineEvent(
                        type=EventType.ERROR,
                        stage="pipeline",
                        message=(
                            "Analysis is still marked processing but no active "
                            "runtime was found. Please retry."
                        ),
                        data={
                            "report_id": report_id,
                            "error_code": "PIPELINE_PROCESSING_STALE",
                        },
                    )
                    yield {
                        "event": stale_terminal.type.value,
                        "data": stale_terminal.to_sse(),
                    }
                    return
                processing_ping_count += 1
                yield {"event": "ping", "data": "{}"}
                await asyncio.sleep(_STATUS_ONLY_PING_INTERVAL_SECONDS)
                continue

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
                    queue.get(), timeout=_ACTIVE_STREAM_PING_INTERVAL_SECONDS
                )
                yield {"event": queued_event.type.value, "data": queued_event.to_sse()}
                if queued_event.type in _TERMINAL_EVENTS:
                    break
            except asyncio.TimeoutError:
                yield {"event": "ping", "data": "{}"}
    finally:
        run_state.unsubscribe(queue)
        cleanup_report_runs()


async def _get_effective_owner(report_id: str) -> str:
    """Return the effective owner of a report, checking both report and status."""
    cache = get_cache()
    owner_id = await cache.get_report_user_id(report_id)
    if owner_id:
        return owner_id
    status = await cache.get_status(report_id)
    if status:
        return status.get("user_id", "") or ""
    return ""


async def _assert_owner_or_deny(report_id: str, user_id: str) -> None:
    """Raise 403/404 if the report/status belongs to another user or has no owner.

    Fail-close: when no owner can be resolved, treat the report as not found.
    """
    owner_id = await _get_effective_owner(report_id)
    if not owner_id:
        raise AppError(404, ErrorCode.REPORT_NOT_FOUND, "Report not found")
    if owner_id != user_id:
        raise AppError(403, ErrorCode.NOT_AUTHORIZED, "Not authorized")


@router.get("/reports/{report_id}/stream")
async def stream_progress(
    report_id: str,
    user: AuthUser = Depends(get_current_user),
) -> EventSourceResponse:
    """SSE endpoint — stream pipeline progress events for a report."""
    await _assert_owner_or_deny(report_id, user.id)
    return EventSourceResponse(_stream_events(report_id))


@router.delete("/reports/{report_id}/cancel")
async def cancel_analysis(
    report_id: str,
    user: AuthUser = Depends(get_current_user),
) -> dict:
    """Cancel an in-progress analysis task."""
    await _assert_owner_or_deny(report_id, user.id)
    task = await get_pipeline_task_for_report(report_id)
    report_is_processing = await is_processing_report(report_id)
    if (task is None or task.done()) and not report_is_processing:
        raise AppError(
            404,
            ErrorCode.ANALYSIS_NOT_FOUND,
            "No active analysis found for this report",
        )

    if task is not None and not task.done():
        task.cancel()
        await _mark_cancelled(report_id)
        await release_processing_report(report_id)
    else:
        await _mark_cancelled(report_id)
        await release_processing_report(report_id)

    logger.info("Analysis cancelled for report {}", report_id)
    return {"status": "cancelled"}
