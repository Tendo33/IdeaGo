"""Reports endpoints — list, get, delete, export.

报告端点：列表、详情、删除、导出。
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, PlainTextResponse

from ideago.api.dependencies import get_cache, get_processing_reports
from ideago.api.schemas import ReportListItem, ReportRuntimeStatus
from ideago.auth.dependencies import get_current_user
from ideago.auth.models import AuthUser
from ideago.cache.base import ReportRepository
from ideago.models.research import ResearchReport

router = APIRouter(tags=["reports"])


async def _assert_report_owner(
    cache: ReportRepository, report_id: str, user_id: str
) -> None:
    """Raise 403 if the report/status belongs to another user.

    Checks report.user_id first, then falls back to report_status.user_id
    for reports still in processing (owner set before pipeline starts).
    """
    owner_id = await cache.get_report_user_id(report_id)
    if not owner_id:
        status = await cache.get_status(report_id)
        if status:
            owner_id = status.get("user_id", "") or ""
    if owner_id and owner_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")


def _parse_status_updated_at(raw_value: object) -> datetime | None:
    """Parse status payload timestamp into datetime if possible."""
    if not isinstance(raw_value, str):
        return None
    try:
        return datetime.fromisoformat(raw_value)
    except ValueError:
        return None


@router.get("/reports", response_model=list[ReportListItem])
async def list_reports(
    limit: int | None = Query(default=None, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: AuthUser = Depends(get_current_user),
) -> list[ReportListItem]:
    """List research reports belonging to the authenticated user."""
    cache = get_cache()
    entries = await cache.list_reports(limit=limit, offset=offset, user_id=user.id)
    return [
        ReportListItem(
            id=e.report_id,
            query=e.query,
            created_at=e.created_at,
            competitor_count=e.competitor_count,
        )
        for e in entries
    ]


@router.get("/reports/{report_id}", response_model=None)
async def get_report(
    report_id: str,
    user: AuthUser = Depends(get_current_user),
) -> dict | JSONResponse:
    """Get a completed report by ID. Returns 202 if still processing, 404 if not found."""
    cache = get_cache()
    await _assert_report_owner(cache, report_id, user.id)

    report = await cache.get_by_id(report_id)
    if report is not None:
        return report.model_dump(mode="json")

    processing = get_processing_reports()
    if report_id in processing.values():
        return JSONResponse(
            status_code=202,
            content={"status": "processing", "report_id": report_id},
        )

    status = await cache.get_status(report_id)
    if status and status.get("status") == "processing":
        return JSONResponse(
            status_code=202,
            content={"status": "processing", "report_id": report_id},
        )

    raise HTTPException(status_code=404, detail="Report not found")


@router.get("/reports/{report_id}/status", response_model=ReportRuntimeStatus)
async def get_report_status(
    report_id: str,
    user: AuthUser = Depends(get_current_user),
) -> ReportRuntimeStatus:
    """Get report runtime status for processing/failed/cancelled/complete/not_found."""
    cache = get_cache()
    await _assert_report_owner(cache, report_id, user.id)

    report = await cache.get_by_id(report_id)
    if report is not None:
        return ReportRuntimeStatus(
            status="complete",
            report_id=report_id,
            updated_at=report.updated_at,
            query=report.query,
        )

    processing = get_processing_reports()
    if report_id in processing.values():
        return ReportRuntimeStatus(status="processing", report_id=report_id)

    status_payload = await cache.get_status(report_id)
    if status_payload:
        status_value = status_payload.get("status")
        if isinstance(status_value, str) and status_value in {
            "processing",
            "failed",
            "cancelled",
            "complete",
        }:
            runtime_status = cast(
                Literal["processing", "failed", "cancelled", "complete"],
                status_value,
            )
            return ReportRuntimeStatus(
                status=runtime_status,
                report_id=report_id,
                error_code=status_payload.get("error_code"),
                message=status_payload.get("message"),
                updated_at=_parse_status_updated_at(status_payload.get("updated_at")),
                query=status_payload.get("query"),
            )

    return ReportRuntimeStatus(status="not_found", report_id=report_id)


@router.delete("/reports/{report_id}")
async def delete_report(
    report_id: str,
    user: AuthUser = Depends(get_current_user),
) -> dict:
    """Delete a cached report owned by the authenticated user."""
    cache = get_cache()
    await _assert_report_owner(cache, report_id, user.id)
    deleted = await cache.delete(report_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Report not found")
    return {"status": "deleted"}


@router.get("/reports/{report_id}/export")
async def export_report(
    report_id: str,
    user: AuthUser = Depends(get_current_user),
) -> PlainTextResponse:
    """Export a report as Markdown."""
    cache = get_cache()
    await _assert_report_owner(cache, report_id, user.id)
    report = await cache.get_by_id(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")

    md = _report_to_markdown(report)
    return PlainTextResponse(
        content=md,
        media_type="text/markdown",
        headers={
            "Content-Disposition": f'attachment; filename="report-{report_id[:8]}.md"'
        },
    )


def _report_to_markdown(report: ResearchReport) -> str:
    """Convert a ResearchReport to a Markdown string."""
    lines: list[str] = []
    lines.append("# Competitor Research Report")
    lines.append(f"\n**Query:** {report.query}")
    lines.append(f"\n**Generated:** {report.created_at.strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append(f"\n**App Type:** {report.intent.app_type}")
    lines.append(f"\n**Keywords:** {', '.join(report.intent.keywords_en)}")

    if report.go_no_go:
        lines.append(f"\n## Recommendation\n\n{report.go_no_go}")

    if report.market_summary:
        lines.append(f"\n## Market Summary\n\n{report.market_summary}")

    if report.competitors:
        lines.append(f"\n## Competitors ({len(report.competitors)})\n")
        for i, c in enumerate(report.competitors, 1):
            lines.append(f"### {i}. {c.name}")
            lines.append(f"\n> {c.one_liner}")
            if c.features:
                lines.append(f"\n**Features:** {', '.join(c.features)}")
            if c.pricing:
                lines.append(f"\n**Pricing:** {c.pricing}")
            if c.strengths:
                lines.append(f"\n**Strengths:** {'; '.join(c.strengths)}")
            if c.weaknesses:
                lines.append(f"\n**Weaknesses:** {'; '.join(c.weaknesses)}")
            lines.append(f"\n**Links:** {', '.join(c.links)}")
            lines.append(f"\n**Relevance:** {c.relevance_score:.1f}/1.0")
            lines.append("")

    if report.differentiation_angles:
        lines.append("\n## Differentiation Opportunities\n")
        for angle in report.differentiation_angles:
            lines.append(f"- {angle}")

    lines.append("\n## Data Sources\n")
    for sr in report.source_results:
        status_icon = {
            "ok": "✓",
            "failed": "✗",
            "timeout": "⏱",
            "degraded": "⚠",
            "cached": "📦",
        }.get(sr.status.value, "?")
        lines.append(
            f"- {status_icon} **{sr.platform.value}**: {sr.status.value} ({sr.raw_count} results, {sr.duration_ms}ms)"
        )

    return "\n".join(lines)
