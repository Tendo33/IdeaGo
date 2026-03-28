"""Report assembly helpers for pipeline nodes."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from ideago.models.research import (
    Competitor,
    ConfidenceMetrics,
    CostBreakdown,
    EvidenceItem,
    EvidenceSummary,
    LlmFaultToleranceMeta,
    RecommendationType,
    ReportMeta,
    SourceResult,
    SourceStatus,
)
from ideago.pipeline.nodes_confidence import score_freshness_hint, sorted_platforms


def build_evidence_summary(
    *,
    competitors: list[Competitor] | None = None,
    evidence_items: list[EvidenceItem] | None = None,
    source_results: list[SourceResult] | None = None,
    uncertainty_notes: list[str] | None = None,
) -> EvidenceSummary:
    normalized_evidence_items = _dedupe_evidence_items(evidence_items or [])
    top_evidence = [
        _truncate_text(
            f"{item.title}: {item.snippet}"
            if item.snippet
            else f"{item.title}: {item.url}",
            140,
        )
        for item in normalized_evidence_items[:4]
        if item.title or item.snippet or item.url
    ]
    if not top_evidence:
        ranked = sorted(
            competitors or [],
            key=lambda item: item.relevance_score,
            reverse=True,
        )
        top_evidence = [
            _truncate_text(f"{competitor.name}: {competitor.one_liner}", 140)
            for competitor in ranked[:4]
            if competitor.name or competitor.one_liner
        ]
    category_counts = _build_evidence_category_counts(normalized_evidence_items)
    freshness_distribution = _build_freshness_distribution(normalized_evidence_items)
    return EvidenceSummary(
        top_evidence=top_evidence,
        evidence_items=normalized_evidence_items,
        category_counts=category_counts,
        source_platforms=sorted_platforms(
            {
                item.platform
                for item in normalized_evidence_items
                if item.platform is not None
            }
        ),
        freshness_distribution=freshness_distribution,
        degraded_sources=sorted_platforms(
            {
                source_result.platform
                for source_result in (source_results or [])
                if source_result.status
                in {SourceStatus.DEGRADED, SourceStatus.FAILED, SourceStatus.TIMEOUT}
            }
        ),
        uncertainty_notes=list(uncertainty_notes or []),
    )


def build_cost_breakdown(
    *,
    llm_usage: dict[str, Any],
    source_results: list[SourceResult],
    pipeline_latency_ms: int,
) -> CostBreakdown:
    return CostBreakdown(
        llm_calls=max(0, int(llm_usage.get("llm_calls", 0) or 0)),
        llm_retries=max(0, int(llm_usage.get("llm_retries", 0) or 0)),
        endpoint_failovers=max(0, int(llm_usage.get("endpoint_failovers", 0) or 0)),
        source_calls=len(source_results),
        pipeline_latency_ms=max(0, int(pipeline_latency_ms)),
        tokens_prompt=max(0, int(llm_usage.get("tokens_prompt", 0) or 0)),
        tokens_completion=max(0, int(llm_usage.get("tokens_completion", 0) or 0)),
    )


def build_report_meta(
    llm_usage: dict[str, Any], *, quality_warnings: list[str]
) -> ReportMeta:
    endpoints = llm_usage.get("endpoints_tried", [])
    endpoint_names = (
        [str(item) for item in endpoints if str(item).strip()]
        if isinstance(endpoints, list)
        else []
    )
    return ReportMeta(
        llm_fault_tolerance=LlmFaultToleranceMeta(
            fallback_used=bool(llm_usage.get("fallback_used", False)),
            endpoints_tried=endpoint_names,
            last_error_class=str(llm_usage.get("last_error_class", "") or ""),
        ),
        quality_warnings=quality_warnings,
    )


def apply_recommendation_quality_guard(
    *,
    recommendation_type: RecommendationType,
    go_no_go: str,
    confidence: ConfidenceMetrics,
    output_language: str = "en",
) -> tuple[RecommendationType, str, list[str]]:
    warnings: list[str] = []
    adjusted_type = recommendation_type
    adjusted_text = (
        go_no_go.strip()
        if go_no_go.strip()
        else _localized_text(
            output_language,
            "建议待补充。",
            "Recommendation pending.",
        )
    )

    low_evidence = (
        confidence.sample_size == 0
        or confidence.source_success_rate < 0.4
        or confidence.score < 40
    )
    if low_evidence:
        warnings.append(
            _localized_text(
                output_language,
                "当前证据置信度较低，建议保守解读本次结论。",
                "Low evidence confidence: recommendation is calibrated conservatively.",
            )
        )

    if low_evidence and recommendation_type == RecommendationType.GO:
        adjusted_type = RecommendationType.CAUTION
        adjusted_text = _rewrite_low_evidence_recommendation_text(
            adjusted_text,
            output_language=output_language,
        )
        warnings.append(
            _localized_text(
                output_language,
                "由于证据不足，建议已从 GO 下调为 CAUTION。",
                "Recommendation downgraded from GO to CAUTION due to insufficient evidence.",
            )
        )
    elif low_evidence and recommendation_type == RecommendationType.NO_GO:
        adjusted_type = RecommendationType.CAUTION
        adjusted_text = _rewrite_low_evidence_recommendation_text(
            adjusted_text,
            output_language=output_language,
        )
        warnings.append(
            _localized_text(
                output_language,
                "由于证据不足，建议已从 NO_GO 放宽为 CAUTION。",
                "Recommendation softened from NO_GO to CAUTION due to insufficient evidence.",
            )
        )

    if adjusted_type != recommendation_type:
        guardrail_note = _localized_text(
            output_language,
            "由于当前证据不足，这条建议已做保守调整；在做最终判断前，建议先补充更多已验证竞品。",
            "This recommendation is adjusted due to insufficient evidence; collect more validated competitors before making a final decision.",
        )
        if guardrail_note not in adjusted_text:
            adjusted_text = f"{adjusted_text} {guardrail_note}".strip()

    return adjusted_type, adjusted_text, warnings


def _rewrite_low_evidence_recommendation_text(
    text: str,
    *,
    output_language: str,
) -> str:
    rationale = _strip_recommendation_prefix(text)
    if output_language == "zh":
        if rationale:
            return f"CAUTION：{rationale} 当前证据不足。"
        return "CAUTION：当前证据不足。"
    if rationale:
        return f"Caution: {rationale} Current evidence is insufficient."
    return "Caution: current evidence is insufficient."


def _strip_recommendation_prefix(text: str) -> str:
    normalized = text.strip()
    if not normalized:
        return ""
    stripped = re.sub(
        r"^(go|no[\s-]?go|caution)\s*[:\-]\s*",
        "",
        normalized,
        flags=re.IGNORECASE,
    ).strip()
    if stripped == normalized:
        return normalized
    return stripped


def _truncate_text(value: str, limit: int) -> str:
    text = value.strip()
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3].rstrip()}..."


def _dedupe_evidence_items(evidence_items: list[EvidenceItem]) -> list[EvidenceItem]:
    deduped: list[EvidenceItem] = []
    seen: set[tuple[str, str, str, str, str]] = set()
    for item in evidence_items:
        key = (
            item.url.strip().lower(),
            item.category.value,
            item.platform.value if item.platform is not None else "",
            item.title.strip().lower(),
            item.snippet.strip().lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _build_freshness_distribution(
    evidence_items: list[EvidenceItem],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    now = datetime.now(timezone.utc)
    for item in evidence_items:
        _, bucket = score_freshness_hint(item.freshness_hint, now=now)
        counts[bucket] = counts.get(bucket, 0) + 1
    return counts


def _build_evidence_category_counts(
    evidence_items: list[EvidenceItem],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in evidence_items:
        category_key = item.category.value
        counts[category_key] = counts.get(category_key, 0) + 1
    return counts


def _localized_text(output_language: str, zh: str, en: str) -> str:
    return zh if output_language == "zh" else en
