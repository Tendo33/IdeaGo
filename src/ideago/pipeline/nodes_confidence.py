"""Confidence and trust-scoring helpers for pipeline nodes."""

from __future__ import annotations

from datetime import datetime, timezone

from ideago.models.research import (
    CommercialSignal,
    Competitor,
    ConfidenceMetrics,
    EvidenceItem,
    PainSignal,
    Platform,
    SourceResult,
    SourceStatus,
)


def build_confidence_metrics(
    all_competitors: list[Competitor],
    source_results: list[SourceResult],
    *,
    evidence_items: list[EvidenceItem] | None = None,
    pain_signals: list[PainSignal] | None = None,
    commercial_signals: list[CommercialSignal] | None = None,
    uncertainty_notes: list[str] | None = None,
    generated_at: datetime | None = None,
    output_language: str = "en",
) -> ConfidenceMetrics:
    normalized_evidence_items = _dedupe_evidence_items(evidence_items or [])
    normalized_pain_signals = list(pain_signals or [])
    normalized_commercial_signals = list(commercial_signals or [])
    normalized_uncertainty_notes = [
        note.strip() for note in (uncertainty_notes or []) if note.strip()
    ]

    sample_size = max(
        len(all_competitors),
        len(normalized_evidence_items),
        len(normalized_pain_signals) + len(normalized_commercial_signals),
    )
    total_sources = len(source_results)
    source_coverage = sum(
        1
        for source_result in source_results
        if source_result.status
        in {SourceStatus.OK, SourceStatus.CACHED, SourceStatus.DEGRADED}
    )
    effective_success = sum(
        1.0
        if source_result.status in {SourceStatus.OK, SourceStatus.CACHED}
        else 0.7
        if source_result.status == SourceStatus.DEGRADED
        else 0.0
        for source_result in source_results
    )
    source_success_rate = (
        (effective_success / total_sources) if total_sources > 0 else 0.0
    )
    source_diversity = _count_supporting_platforms(
        source_results=source_results,
        evidence_items=normalized_evidence_items,
        pain_signals=normalized_pain_signals,
        commercial_signals=normalized_commercial_signals,
    )
    evidence_density = _build_evidence_density_score(
        evidence_items=normalized_evidence_items,
        pain_signals=normalized_pain_signals,
        commercial_signals=normalized_commercial_signals,
    )
    now = datetime.now(timezone.utc)
    reference_time = generated_at or now
    recency_score = _build_recency_score(
        normalized_evidence_items,
        source_results=source_results,
        now=reference_time,
    )
    degradation_penalty = _build_degradation_penalty(source_results)
    contradiction_penalty = _build_contradiction_penalty(
        pain_signals=normalized_pain_signals,
        commercial_signals=normalized_commercial_signals,
        uncertainty_notes=normalized_uncertainty_notes,
    )
    sample_size_score = min(1.0, sample_size / 6.0) if sample_size > 0 else 0.0
    diversity_score = min(1.0, source_diversity / 4.0) if source_diversity > 0 else 0.0
    base_score = (
        diversity_score * 0.22
        + evidence_density * 0.18
        + recency_score * 0.12
        + source_success_rate * 0.28
        + sample_size_score * 0.20
    ) * 100
    penalty_points = degradation_penalty * 24 + contradiction_penalty * 26
    score = int(round(max(0.0, min(100.0, base_score - penalty_points))))
    return ConfidenceMetrics(
        sample_size=sample_size,
        source_coverage=source_coverage,
        source_success_rate=round(source_success_rate, 3),
        source_diversity=source_diversity,
        evidence_density=round(evidence_density, 3),
        recency_score=round(recency_score, 3),
        degradation_penalty=round(degradation_penalty, 3),
        contradiction_penalty=round(contradiction_penalty, 3),
        reasons=_build_confidence_reasons(
            source_diversity=source_diversity,
            evidence_density=evidence_density,
            recency_score=recency_score,
            degradation_penalty=degradation_penalty,
            contradiction_penalty=contradiction_penalty,
            source_results=source_results,
            uncertainty_notes=normalized_uncertainty_notes,
            output_language=output_language,
        ),
        freshness_hint=build_relative_freshness_hint(
            reference_time,
            now,
            output_language=output_language,
        ),
        score=max(0, min(100, score)),
    )


def build_confidence_penalty_reasons(
    *,
    confidence: ConfidenceMetrics,
    source_results: list[SourceResult],
    uncertainty_notes: list[str] | None,
    output_language: str,
) -> list[str]:
    reasons: list[str] = []
    degraded_count = sum(
        1
        for source_result in source_results
        if source_result.status
        in {SourceStatus.DEGRADED, SourceStatus.FAILED, SourceStatus.TIMEOUT}
    )
    if degraded_count > 0 and confidence.degradation_penalty > 0:
        reasons.append(
            _localized_text(
                output_language,
                f"{degraded_count} 个来源出现降级或失败，已下调置信度。",
                f"{degraded_count} sources were degraded or failed, reducing confidence.",
            )
        )

    normalized_uncertainty_notes = [
        note.strip() for note in (uncertainty_notes or []) if note.strip()
    ]
    if confidence.contradiction_penalty > 0 and normalized_uncertainty_notes:
        reasons.append(
            _localized_text(
                output_language,
                "存在冲突或不确定证据，已下调置信度。",
                "Conflicting or uncertain evidence reduced confidence.",
            )
        )
    return reasons


def build_relative_freshness_hint(
    created_at: datetime,
    now: datetime,
    output_language: str = "en",
) -> str:
    created_ts = (
        created_at.replace(tzinfo=timezone.utc)
        if created_at.tzinfo is None
        else created_at.astimezone(timezone.utc)
    )
    now_ts = (
        now.replace(tzinfo=timezone.utc)
        if now.tzinfo is None
        else now.astimezone(timezone.utc)
    )
    delta_seconds = max(0, int((now_ts - created_ts).total_seconds()))
    if delta_seconds < 60:
        return _localized_text(output_language, "刚刚生成", "Generated just now")
    if delta_seconds < 3600:
        minutes = max(1, delta_seconds // 60)
        return _localized_text(
            output_language,
            f"{minutes} 分钟前生成",
            f"Generated {minutes}m ago",
        )
    if delta_seconds < 86400:
        hours = max(1, delta_seconds // 3600)
        return _localized_text(
            output_language,
            f"{hours} 小时前生成",
            f"Generated {hours}h ago",
        )
    if delta_seconds < 7 * 86400:
        days = max(1, delta_seconds // 86400)
        return _localized_text(
            output_language,
            f"{days} 天前生成",
            f"Generated {days}d ago",
        )
    return _localized_text(
        output_language,
        f"生成于 {created_ts.date().isoformat()}",
        f"Generated on {created_ts.date().isoformat()}",
    )


def score_freshness_hint(
    freshness_hint: str,
    *,
    now: datetime,
) -> tuple[float, str]:
    normalized_hint = freshness_hint.strip()
    if not normalized_hint:
        return 0.0, "unknown"

    parsed_timestamp = _parse_iso_datetime(normalized_hint)
    if parsed_timestamp is not None:
        age_days = max(0.0, (now - parsed_timestamp).total_seconds() / 86400.0)
        if age_days <= 30:
            return 1.0, "recent"
        if age_days <= 365:
            return 0.55, "aging"
        if age_days <= 730:
            return 0.3, "stale"
        return 0.15, "stale"

    lower_hint = normalized_hint.lower()
    if any(
        token in lower_hint for token in ("just now", "moments ago", "recent", "new")
    ):
        return 0.8, "recent"
    if any(token in lower_hint for token in ("week", "month", "day")):
        return 0.5, "aging"
    return 0.35, "unknown"


def sorted_platforms(platforms: set[Platform]) -> list[Platform]:
    return sorted(platforms, key=lambda platform: platform.value)


def _count_supporting_platforms(
    *,
    source_results: list[SourceResult],
    evidence_items: list[EvidenceItem],
    pain_signals: list[PainSignal],
    commercial_signals: list[CommercialSignal],
) -> int:
    supporting_platforms = {
        item.platform for item in evidence_items if item.platform is not None
    }
    for signal in pain_signals:
        supporting_platforms.update(signal.source_platforms)
    for commercial_signal in commercial_signals:
        supporting_platforms.update(commercial_signal.source_platforms)
    supporting_platforms.update(
        source_result.platform
        for source_result in source_results
        if source_result.status in {SourceStatus.OK, SourceStatus.CACHED}
        and source_result.raw_count > 0
    )
    return len(supporting_platforms)


def _build_evidence_density_score(
    *,
    evidence_items: list[EvidenceItem],
    pain_signals: list[PainSignal],
    commercial_signals: list[CommercialSignal],
) -> float:
    unique_urls = {item.url.strip() for item in evidence_items if item.url.strip()}
    density_points = (
        len(evidence_items) * 1.0
        + len(unique_urls) * 0.5
        + len(pain_signals) * 0.5
        + len(commercial_signals) * 0.5
    )
    return max(0.0, min(1.0, density_points / 10.0))


def _build_recency_score(
    evidence_items: list[EvidenceItem],
    *,
    source_results: list[SourceResult],
    now: datetime,
) -> float:
    freshness_scores = [
        score_freshness_hint(item.freshness_hint, now=now)[0]
        for item in evidence_items
        if item.freshness_hint.strip()
    ]
    if not freshness_scores:
        if evidence_items:
            return 0.35
        has_recent_observation = any(
            source_result.status in {SourceStatus.OK, SourceStatus.CACHED}
            and source_result.raw_count > 0
            for source_result in source_results
        )
        return 0.4 if has_recent_observation else 0.0
    return max(0.0, min(1.0, sum(freshness_scores) / len(freshness_scores)))


def _build_degradation_penalty(source_results: list[SourceResult]) -> float:
    if not source_results:
        return 0.0
    penalty_points = 0.0
    for source_result in source_results:
        if source_result.status == SourceStatus.DEGRADED:
            penalty_points += 0.18
        elif source_result.status in {SourceStatus.FAILED, SourceStatus.TIMEOUT}:
            penalty_points += 0.35
    return max(0.0, min(1.0, penalty_points / len(source_results)))


def _build_contradiction_penalty(
    *,
    pain_signals: list[PainSignal],
    commercial_signals: list[CommercialSignal],
    uncertainty_notes: list[str],
) -> float:
    penalty = 0.0
    for note in uncertainty_notes:
        lower_note = note.lower()
        penalty += (
            0.2
            if any(
                token in lower_note
                for token in ("conflict", "contradict", "mixed", "inconsistent")
            )
            else 0.1
        )
        if any(token in lower_note for token in ("weak", "sparse", "limited")):
            penalty += 0.05
    return max(0.0, min(1.0, penalty))


def _build_confidence_reasons(
    *,
    source_diversity: int,
    evidence_density: float,
    recency_score: float,
    degradation_penalty: float,
    contradiction_penalty: float,
    source_results: list[SourceResult],
    uncertainty_notes: list[str],
    output_language: str,
) -> list[str]:
    reasons: list[str] = []
    if source_diversity >= 3:
        reasons.append(
            _localized_text(
                output_language,
                f"证据覆盖 {source_diversity} 个独立来源平台。",
                f"Evidence spans {source_diversity} distinct source platforms.",
            )
        )
    if evidence_density >= 0.6:
        reasons.append(
            _localized_text(
                output_language,
                "证据密度较高，痛点与商业信号互相印证。",
                "Evidence density is strong with corroborating pain and commercial signals.",
            )
        )
    if recency_score >= 0.75:
        reasons.append(
            _localized_text(
                output_language,
                "关键证据较新，时效性较好。",
                "Key evidence is recent enough to support current-market interpretation.",
            )
        )

    degraded_count = sum(
        1
        for source_result in source_results
        if source_result.status
        in {SourceStatus.DEGRADED, SourceStatus.FAILED, SourceStatus.TIMEOUT}
    )
    if degraded_count > 0 and degradation_penalty > 0:
        reasons.append(
            _localized_text(
                output_language,
                f"{degraded_count} 个来源出现降级或失败，已下调置信度。",
                f"{degraded_count} sources were degraded or failed, reducing confidence.",
            )
        )
    if contradiction_penalty > 0 and uncertainty_notes:
        reasons.append(
            _localized_text(
                output_language,
                "存在冲突或不确定证据，已下调置信度。",
                "Conflicting or uncertain evidence reduced confidence.",
            )
        )
    return reasons


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


def _parse_iso_datetime(value: str) -> datetime | None:
    normalized = value.strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _localized_text(output_language: str, zh: str, en: str) -> str:
    return zh if output_language == "zh" else en
