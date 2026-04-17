"""Reports endpoints — list, get, delete, export.

报告端点：列表、详情、删除、导出。
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, cast

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, PlainTextResponse

from ideago.api.dependencies import (
    get_cache,
    is_report_id_processing,
    release_processing_report,
)
from ideago.api.errors import AppError, DependencyUnavailableError, ErrorCode
from ideago.api.schemas import (
    PaginatedReportList,
    ReportDetailV2,
    ReportListItem,
    ReportRuntimeStatus,
)
from ideago.auth.dependencies import get_current_user
from ideago.auth.models import AuthUser
from ideago.cache.base import ReportRepository
from ideago.models.research import ResearchReport
from ideago.observability.metrics import metrics as app_metrics

router = APIRouter(tags=["reports"])


def _report_to_detail_v2(report: ResearchReport) -> ReportDetailV2:
    return ReportDetailV2(
        id=report.id,
        query=report.query,
        created_at=report.created_at,
        updated_at=report.updated_at,
        intent=report.intent,
        recommendation_type=report.recommendation_type,
        go_no_go=report.go_no_go,
        market_summary=report.market_summary,
        pain_signals=list(report.pain_signals),
        commercial_signals=list(report.commercial_signals),
        whitespace_opportunities=list(report.whitespace_opportunities),
        opportunity_score=report.opportunity_score,
        competitors=list(report.competitors),
        differentiation_angles=list(report.differentiation_angles),
        evidence_summary=report.evidence_summary,
        confidence=report.confidence,
        source_results=list(report.source_results),
        cost_breakdown=report.cost_breakdown,
        report_meta=report.report_meta,
    )


async def _assert_report_owner(
    cache: ReportRepository, report_id: str, user_id: str
) -> None:
    """Raise 403/404 if the report/status belongs to another user or has no owner.

    Fail-close: when no owner can be resolved, treat the report as not found
    to prevent unauthorized access to orphaned data.
    """
    owner_id = await cache.get_report_user_id(report_id)
    if not owner_id:
        status = await cache.get_status(report_id)
        if status:
            owner_id = status.get("user_id", "") or ""
    if not owner_id:
        raise AppError(404, ErrorCode.REPORT_NOT_FOUND, "Report not found")
    if owner_id != user_id:
        raise AppError(404, ErrorCode.REPORT_NOT_FOUND, "Report not found")


def _parse_status_updated_at(raw_value: object) -> datetime | None:
    """Parse status payload timestamp into datetime if possible."""
    if not isinstance(raw_value, str):
        return None
    try:
        return datetime.fromisoformat(raw_value)
    except ValueError:
        return None


_MAX_LIST_LIMIT = 100


@router.get("/reports", response_model=PaginatedReportList)
async def list_reports(
    limit: int = Query(default=20, ge=1, le=_MAX_LIST_LIMIT),
    offset: int = Query(default=0, ge=0),
    q: str = Query(default="", max_length=200),
    user: AuthUser = Depends(get_current_user),
) -> PaginatedReportList:
    """List research reports belonging to the authenticated user."""
    cache = get_cache()
    capped_limit = min(limit, _MAX_LIST_LIMIT)
    try:
        entries, has_next, total = await cache.list_reports(
            limit=capped_limit,
            offset=offset,
            user_id=user.id,
            q=q.strip(),
        )
    except DependencyUnavailableError:
        raise AppError(
            503,
            ErrorCode.DEPENDENCY_UNAVAILABLE,
            "Report store unavailable",
        ) from None
    return PaginatedReportList(
        items=[
            ReportListItem(
                id=e.report_id,
                query=e.query,
                created_at=e.created_at,
                competitor_count=e.competitor_count,
            )
            for e in entries
        ],
        total=total if total is not None else 0,
        has_next=has_next,
        limit=capped_limit,
        offset=offset,
    )


@router.get(
    "/reports/{report_id}",
    response_model=ReportDetailV2,
    responses={202: {"model": ReportRuntimeStatus}},
)
async def get_report(
    report_id: str,
    user: AuthUser = Depends(get_current_user),
) -> ReportDetailV2 | JSONResponse:
    """Get a completed report by ID. Returns 202 if still processing, 404 if not found."""
    cache = get_cache()
    try:
        await _assert_report_owner(cache, report_id, user.id)
        report = await cache.get_by_id(report_id, user_id=user.id)
    except DependencyUnavailableError:
        raise AppError(
            503,
            ErrorCode.DEPENDENCY_UNAVAILABLE,
            "Report store unavailable",
        ) from None
    if report is not None:
        return _report_to_detail_v2(report)

    if is_report_id_processing(report_id):
        return JSONResponse(
            status_code=202,
            content=ReportRuntimeStatus(
                status="processing",
                report_id=report_id,
            ).model_dump(mode="json"),
        )

    status = await cache.get_status(report_id)
    if status and status.get("status") == "processing":
        return JSONResponse(
            status_code=202,
            content=ReportRuntimeStatus(
                status="processing",
                report_id=report_id,
                updated_at=_parse_status_updated_at(status.get("updated_at")),
                query=status.get("query"),
            ).model_dump(mode="json"),
        )

    raise AppError(404, ErrorCode.REPORT_NOT_FOUND, "Report not found")


@router.get("/reports/{report_id}/status", response_model=ReportRuntimeStatus)
async def get_report_status(
    report_id: str,
    user: AuthUser = Depends(get_current_user),
) -> ReportRuntimeStatus:
    """Get report runtime status for processing/failed/cancelled/complete/not_found."""
    cache = get_cache()
    try:
        owner_id = await cache.get_report_user_id(report_id)
        if not owner_id:
            status_payload = await cache.get_status(report_id)
            if status_payload:
                owner_id = status_payload.get("user_id", "") or ""
    except DependencyUnavailableError:
        raise AppError(
            503,
            ErrorCode.DEPENDENCY_UNAVAILABLE,
            "Report store unavailable",
        ) from None
    if not owner_id:
        app_metrics.increment_event("report_status_not_found", reason="missing_owner")
        return ReportRuntimeStatus(status="not_found", report_id=report_id)
    if owner_id != user.id:
        app_metrics.increment_event("report_status_not_found", reason="missing_owner")
        return ReportRuntimeStatus(status="not_found", report_id=report_id)

    report = await cache.get_by_id(report_id, user_id=user.id)
    if report is not None:
        return ReportRuntimeStatus(
            status="complete",
            report_id=report_id,
            updated_at=report.updated_at,
            query=report.query,
        )

    if is_report_id_processing(report_id):
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

    app_metrics.increment_event("report_status_not_found", reason="missing_status")
    return ReportRuntimeStatus(status="not_found", report_id=report_id)


@router.delete("/reports/{report_id}")
async def delete_report(
    report_id: str,
    user: AuthUser = Depends(get_current_user),
) -> dict:
    """Delete a cached report owned by the authenticated user."""
    cache = get_cache()
    try:
        await _assert_report_owner(cache, report_id, user.id)
        deleted = await cache.delete(report_id, user_id=user.id)
    except DependencyUnavailableError:
        raise AppError(
            503,
            ErrorCode.DEPENDENCY_UNAVAILABLE,
            "Report store unavailable",
        ) from None
    if not deleted:
        raise AppError(404, ErrorCode.REPORT_NOT_FOUND, "Report not found")
    await cache.remove_status(report_id)
    await release_processing_report(report_id)
    return {"status": "deleted"}


@router.get("/reports/{report_id}/export")
async def export_report(
    report_id: str,
    user: AuthUser = Depends(get_current_user),
) -> PlainTextResponse:
    """Export a report as Markdown."""
    cache = get_cache()
    try:
        await _assert_report_owner(cache, report_id, user.id)
        report = await cache.get_by_id(report_id, user_id=user.id)
    except DependencyUnavailableError:
        raise AppError(
            503,
            ErrorCode.DEPENDENCY_UNAVAILABLE,
            "Report store unavailable",
        ) from None
    if report is None:
        raise AppError(404, ErrorCode.REPORT_NOT_FOUND, "Report not found")

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
    lines.append("# Source Intelligence Report")
    lines.append(f"\n**Query:** {report.query}")
    lines.append(f"\n**Generated:** {report.created_at.strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append(f"\n**App Type:** {report.intent.app_type}")
    lines.append(f"\n**Keywords:** {', '.join(report.intent.keywords_en)}")

    lines.append("\n## Should We Build This?\n")
    lines.append(
        f"- Recommendation: {report.recommendation_type.value}"
        if report.recommendation_type
        else "- Recommendation: unknown"
    )
    if report.go_no_go:
        lines.append(f"- Summary: {report.go_no_go}")
    if report.opportunity_score.score > 0:
        lines.append(f"- Opportunity Score: {report.opportunity_score.score:.2f}/1.00")

    if report.market_summary:
        lines.append(f"\n## Why Now\n\n{report.market_summary}")

    if report.pain_signals:
        lines.append("\n## Pain Signals\n")
        for signal in report.pain_signals:
            headline = signal.theme or "Pain signal"
            lines.append(f"- **{headline}**")
            if signal.summary:
                lines.append(f"  - {signal.summary}")
            lines.append(
                f"  - Intensity: {signal.intensity:.2f}, Frequency: {signal.frequency:.2f}"
            )

    if report.commercial_signals:
        lines.append("\n## Commercial Signals\n")
        for commercial_signal in report.commercial_signals:
            headline = commercial_signal.theme or "Commercial signal"
            lines.append(f"- **{headline}**")
            if commercial_signal.summary:
                lines.append(f"  - {commercial_signal.summary}")
            lines.append(
                f"  - Intent Strength: {commercial_signal.intent_strength:.2f}"
            )
            if commercial_signal.monetization_hint:
                lines.append(
                    f"  - Monetization Hint: {commercial_signal.monetization_hint}"
                )

    if report.whitespace_opportunities:
        lines.append("\n## Whitespace Opportunities\n")
        for opportunity in report.whitespace_opportunities:
            lines.append(f"### {opportunity.title}")
            if opportunity.description:
                lines.append(f"\n{opportunity.description}")
            if opportunity.target_segment:
                lines.append(f"\n**Target Segment:** {opportunity.target_segment}")
            if opportunity.wedge:
                lines.append(f"\n**Entry Wedge:** {opportunity.wedge}")
            lines.append(
                f"\n**Potential / Confidence:** {opportunity.potential_score:.2f} / {opportunity.confidence:.2f}"
            )
            if opportunity.supporting_evidence:
                lines.append(
                    f"\n**Supporting Evidence:** {', '.join(opportunity.supporting_evidence)}"
                )
            lines.append("")

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
        lines.append("\n## Differentiated Recommendation\n")
        for angle in report.differentiation_angles:
            lines.append(f"- {angle}")

    lines.append("\n## Evidence And Confidence\n")
    lines.append(f"- Confidence Score: {report.confidence.score}/100")
    lines.append(f"- Source Coverage: {report.confidence.source_coverage}")
    lines.append(f"- Source Diversity: {report.confidence.source_diversity}")
    lines.append(f"- Evidence Density: {report.confidence.evidence_density:.2f}")
    lines.append(f"- Recency Score: {report.confidence.recency_score:.2f}")
    lines.append(f"- Freshness: {report.confidence.freshness_hint}")
    if report.confidence.reasons:
        lines.append("- Confidence Reasons:")
        for reason in report.confidence.reasons:
            lines.append(f"  - {reason}")
    if report.evidence_summary.category_counts:
        lines.append("- Evidence Categories:")
        for category, count in sorted(report.evidence_summary.category_counts.items()):
            lines.append(f"  - {category}: {count}")
    if report.evidence_summary.source_platforms:
        lines.append(
            "- Evidence Platforms: "
            + ", ".join(
                platform.value for platform in report.evidence_summary.source_platforms
            )
        )
    if report.evidence_summary.uncertainty_notes:
        lines.append("- Uncertainty Notes:")
        for note in report.evidence_summary.uncertainty_notes:
            lines.append(f"  - {note}")
    if report.evidence_summary.evidence_items:
        lines.append("\n### Evidence Items\n")
        for item in report.evidence_summary.evidence_items:
            category = item.category.value if item.category else "market"
            lines.append(f"- **{item.title or item.url}** [{category}]")
            if item.snippet:
                lines.append(f"  - {item.snippet}")
            if item.url:
                lines.append(f"  - {item.url}")

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
