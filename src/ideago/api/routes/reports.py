"""Reports endpoints — list, get, delete, export.

报告端点：列表、详情、删除、导出。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse

from ideago.api.dependencies import get_cache, get_processing_reports
from ideago.api.schemas import ReportListItem
from ideago.models.research import ResearchReport

router = APIRouter(tags=["reports"])


@router.get("/reports", response_model=list[ReportListItem])
async def list_reports() -> list[ReportListItem]:
    """List all cached research reports."""
    cache = get_cache()
    entries = await cache.list_reports()
    return [
        ReportListItem(
            id=e.report_id,
            query=e.query,
            created_at=e.created_at,
            competitor_count=e.competitor_count,
        )
        for e in sorted(entries, key=lambda x: x.created_at, reverse=True)
    ]


@router.get("/reports/{report_id}", response_model=None)
async def get_report(report_id: str) -> dict | JSONResponse:
    """Get a completed report by ID. Returns 202 if still processing, 404 if not found."""
    cache = get_cache()
    report = await cache.get_by_id(report_id)
    if report is not None:
        return report.model_dump(mode="json")

    processing = get_processing_reports()
    if report_id in processing.values():
        return JSONResponse(
            status_code=202,
            content={"status": "processing", "report_id": report_id},
        )

    raise HTTPException(status_code=404, detail="Report not found")


@router.delete("/reports/{report_id}")
async def delete_report(report_id: str) -> dict:
    """Delete a cached report."""
    cache = get_cache()
    deleted = await cache.delete(report_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Report not found")
    return {"status": "deleted"}


@router.get("/reports/{report_id}/export")
async def export_report(report_id: str) -> PlainTextResponse:
    """Export a report as Markdown."""
    cache = get_cache()
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
