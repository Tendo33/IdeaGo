"""Aggregator - LLM-only market analysis on pre-merged competitors.

Dedup/scoring is handled by ``merger.py``. This module focuses the LLM on
market analysis, recommendation, and differentiation only.
"""

from __future__ import annotations

import asyncio
import json
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from ideago.llm.chat_model import ChatModelClient
from ideago.llm.invoke_helpers import invoke_json_with_optional_meta
from ideago.llm.prompt_loader import load_prompt
from ideago.models.research import (
    CommercialSignal,
    Competitor,
    EvidenceItem,
    OpportunityScoreBreakdown,
    PainSignal,
    RecommendationType,
    WhitespaceOpportunity,
)
from ideago.observability.log_config import emit_observability_event, get_logger
from ideago.pipeline.exceptions import AggregationError

logger = get_logger(__name__)


def _fallback_market_summary(output_language: str) -> str:
    if output_language == "zh":
        return (
            "\u5f53\u524d\u53ef\u7528\u6570\u636e\u6e90\u4e2d"
            "\u672a\u53d1\u73b0\u660e\u786e\u7ade\u54c1\u3002"
        )
    return "No competitors were found across any data source."


def _fallback_go_no_go(output_language: str) -> str:
    if output_language == "zh":
        return (
            "CAUTION\uff1a\u5f53\u524d\u672a\u83b7\u5f97\u8db3\u591f\u8bc1\u636e\uff0c"
            "\u6682\u65f6\u4e0d\u5efa\u8bae\u6839\u636e\u201c\u672a\u627e\u5230\u7ade\u54c1\u201d"
            "\u76f4\u63a5\u5f97\u51fa\u4e50\u89c2\u7ed3\u8bba\u3002"
        )
    return (
        "Caution: there is not enough evidence to treat an empty retrieval pass "
        "as proof of whitespace."
    )


def _fallback_uncertainty_note(output_language: str) -> str:
    if output_language == "zh":
        return (
            "\u5f53\u524d\u6ca1\u6709\u68c0\u7d22\u5230\u8db3\u591f\u8bc1\u636e\uff0c"
            "\u7a7a\u7ed3\u679c\u4e0d\u5e94\u88ab\u76f4\u63a5\u89e3\u8bfb\u4e3a"
            "\u5b58\u5728\u660e\u786e\u5e02\u573a\u7a7a\u767d\u3002"
        )
    return (
        "No validated evidence was retrieved, so an empty result set should not be "
        "treated as confirmed whitespace."
    )


@dataclass
class AggregationResult:
    """Result of the analysis phase (no competitor modifications)."""

    competitors: list[Competitor] = field(default_factory=list)
    market_summary: str = ""
    go_no_go: str = ""
    recommendation_type: RecommendationType = RecommendationType.GO
    differentiation_angles: list[str] = field(default_factory=list)
    pain_signals: list[PainSignal] = field(default_factory=list)
    commercial_signals: list[CommercialSignal] = field(default_factory=list)
    whitespace_opportunities: list[WhitespaceOpportunity] = field(default_factory=list)
    opportunity_score: OpportunityScoreBreakdown = field(
        default_factory=OpportunityScoreBreakdown
    )
    evidence_items: list[EvidenceItem] = field(default_factory=list)
    uncertainty_notes: list[str] = field(default_factory=list)


class Aggregator:
    """Market analysis using LLM on already-deduplicated competitors."""

    def __init__(self, llm: ChatModelClient) -> None:
        self._llm = llm
        self._llm_metrics_by_task: dict[int, dict[str, Any]] = {}

    async def analyze(
        self,
        competitors: list[Competitor],
        original_query: str,
        output_language: str = "en",
        *,
        pain_signals: list[PainSignal] | None = None,
        commercial_signals: list[CommercialSignal] | None = None,
        evidence_items: list[EvidenceItem] | None = None,
    ) -> AggregationResult:
        """Generate market analysis on pre-merged competitors."""
        normalized_pain_signals = list(pain_signals or [])
        normalized_commercial_signals = list(commercial_signals or [])
        normalized_evidence_items = list(evidence_items or [])

        if (
            not competitors
            and not normalized_pain_signals
            and not normalized_commercial_signals
            and not normalized_evidence_items
        ):
            emit_observability_event(
                logger,
                "aggregation_synthesis_summary",
                {
                    "input_competitor_count": 0,
                    "input_signal_count": 0,
                    "evidence_category_counts": {},
                    "whitespace_opportunity_count": 0,
                    "whitespace_generation_rate": 0.0,
                    "whitespace_fallback_used": False,
                },
            )
            return AggregationResult(
                market_summary=_fallback_market_summary(output_language),
                go_no_go=_fallback_go_no_go(output_language),
                recommendation_type=RecommendationType.CAUTION,
                uncertainty_notes=[_fallback_uncertainty_note(output_language)],
            )

        try:
            competitors_json = json.dumps(
                [c.model_dump(mode="json") for c in competitors],
                ensure_ascii=False,
            )
            pain_signals_json = json.dumps(
                [signal.model_dump(mode="json") for signal in normalized_pain_signals],
                ensure_ascii=False,
            )
            commercial_signals_json = json.dumps(
                [
                    signal.model_dump(mode="json")
                    for signal in normalized_commercial_signals
                ],
                ensure_ascii=False,
            )
            evidence_items_json = json.dumps(
                [item.model_dump(mode="json") for item in normalized_evidence_items],
                ensure_ascii=False,
            )
            prompt = load_prompt(
                "aggregator",
                competitors_json=competitors_json,
                pain_signals_json=pain_signals_json,
                commercial_signals_json=commercial_signals_json,
                evidence_items_json=evidence_items_json,
                original_query=original_query,
                output_language=output_language,
            )
            data, llm_metrics = await invoke_json_with_optional_meta(
                llm=self._llm,
                prompt=prompt,
                system="You are a market research analyst. Return only valid JSON.",
            )
            self._store_metrics_for_current_task(llm_metrics)

            raw_rec_type = data.get("recommendation_type", "go")
            try:
                rec_type = RecommendationType(raw_rec_type)
            except ValueError:
                rec_type = _infer_recommendation_type(data.get("go_no_go", ""))

            differentiation_angles = _parse_string_list(
                data.get("differentiation_angles")
            )
            whitespace_opportunities = _parse_whitespace_opportunities(
                data.get("whitespace_opportunities")
            )
            used_whitespace_fallback = False
            if not whitespace_opportunities and (
                normalized_pain_signals
                or normalized_commercial_signals
                or normalized_evidence_items
            ):
                whitespace_opportunities = _build_fallback_whitespace_opportunities(
                    differentiation_angles=differentiation_angles,
                    pain_signals=normalized_pain_signals,
                    commercial_signals=normalized_commercial_signals,
                    evidence_items=normalized_evidence_items,
                    output_language=output_language,
                )
                used_whitespace_fallback = bool(whitespace_opportunities)
            opportunity_score = _parse_opportunity_score(data.get("opportunity_score"))
            if opportunity_score == OpportunityScoreBreakdown():
                opportunity_score = _build_fallback_opportunity_score(
                    pain_signals=normalized_pain_signals,
                    commercial_signals=normalized_commercial_signals,
                    whitespace_opportunities=whitespace_opportunities,
                )
            evidence_category_counts = _build_evidence_category_counts(
                normalized_evidence_items
            )
            whitespace_generation_rate = 1.0 if whitespace_opportunities else 0.0
            emit_observability_event(
                logger,
                "aggregation_synthesis_summary",
                {
                    "input_competitor_count": len(competitors),
                    "input_signal_count": len(normalized_pain_signals)
                    + len(normalized_commercial_signals),
                    "evidence_category_counts": evidence_category_counts,
                    "whitespace_opportunity_count": len(whitespace_opportunities),
                    "whitespace_generation_rate": whitespace_generation_rate,
                    "whitespace_fallback_used": used_whitespace_fallback,
                },
            )

            return AggregationResult(
                competitors=competitors,
                market_summary=data.get("market_summary", ""),
                go_no_go=data.get("go_no_go", ""),
                recommendation_type=rec_type,
                differentiation_angles=differentiation_angles,
                pain_signals=normalized_pain_signals,
                commercial_signals=normalized_commercial_signals,
                whitespace_opportunities=whitespace_opportunities,
                opportunity_score=opportunity_score,
                evidence_items=normalized_evidence_items,
                uncertainty_notes=_parse_string_list(data.get("uncertainty_notes")),
            )
        except AggregationError:
            raise
        except Exception as exc:
            raise AggregationError(f"Failed to analyze: {exc}") from exc

    async def aggregate(
        self,
        competitors: list[Competitor],
        original_query: str,
        output_language: str = "en",
        *,
        pain_signals: list[PainSignal] | None = None,
        commercial_signals: list[CommercialSignal] | None = None,
        evidence_items: list[EvidenceItem] | None = None,
    ) -> AggregationResult:
        """Backward-compatible alias for ``analyze``."""
        return await self.analyze(
            competitors,
            original_query,
            output_language,
            pain_signals=pain_signals,
            commercial_signals=commercial_signals,
            evidence_items=evidence_items,
        )

    def pop_llm_metrics_for_current_task(self) -> dict[str, Any]:
        task = asyncio.current_task()
        if task is None:
            return {}
        return self._llm_metrics_by_task.pop(id(task), {})

    def _store_metrics_for_current_task(self, metrics: dict[str, Any]) -> None:
        task = asyncio.current_task()
        if task is None:
            return
        self._llm_metrics_by_task[id(task)] = metrics

    def build_failure_result(
        self,
        *,
        competitors: list[Competitor],
        output_language: str,
        pain_signals: list[PainSignal] | None = None,
        commercial_signals: list[CommercialSignal] | None = None,
        evidence_items: list[EvidenceItem] | None = None,
    ) -> AggregationResult:
        return build_failed_aggregation_result(
            competitors=competitors,
            output_language=output_language,
            pain_signals=pain_signals,
            commercial_signals=commercial_signals,
            evidence_items=evidence_items,
        )


def build_failed_aggregation_result(
    *,
    competitors: list[Competitor],
    output_language: str,
    pain_signals: list[PainSignal] | None = None,
    commercial_signals: list[CommercialSignal] | None = None,
    evidence_items: list[EvidenceItem] | None = None,
) -> AggregationResult:
    normalized_pain_signals = list(pain_signals or [])
    normalized_commercial_signals = list(commercial_signals or [])
    normalized_evidence_items = list(evidence_items or [])
    whitespace_opportunities = _build_fallback_whitespace_opportunities(
        differentiation_angles=[],
        pain_signals=normalized_pain_signals,
        commercial_signals=normalized_commercial_signals,
        evidence_items=normalized_evidence_items,
        output_language=output_language,
    )
    opportunity_score = _build_fallback_opportunity_score(
        pain_signals=normalized_pain_signals,
        commercial_signals=normalized_commercial_signals,
        whitespace_opportunities=whitespace_opportunities,
    )
    return AggregationResult(
        competitors=list(competitors),
        pain_signals=normalized_pain_signals,
        commercial_signals=normalized_commercial_signals,
        evidence_items=normalized_evidence_items,
        whitespace_opportunities=whitespace_opportunities,
        opportunity_score=opportunity_score,
        market_summary=_localized_failure_market_summary(output_language),
        go_no_go=_localized_failure_recommendation(output_language),
        recommendation_type=RecommendationType.CAUTION,
        uncertainty_notes=[_localized_failure_uncertainty_note(output_language)],
    )


def _infer_recommendation_type(go_no_go: str) -> RecommendationType:
    """Fallback: infer recommendation type from free-form text."""
    lower = go_no_go.lower()
    if (
        "no-go" in lower
        or "no go" in lower
        or "don't" in lower
        or "advise against" in lower
    ):
        return RecommendationType.NO_GO
    if "caution" in lower or "careful" in lower or "risk" in lower:
        return RecommendationType.CAUTION
    return RecommendationType.GO


def _localized_failure_market_summary(output_language: str) -> str:
    if output_language == "zh":
        return (
            "\u805a\u5408\u5206\u6790\u5931\u8d25\uff0c\u4ee5\u4e0b\u7ed3\u8bba"
            "\u57fa\u4e8e\u5df2\u63d0\u53d6\u7684\u7ed3\u6784\u5316\u8bc1\u636e"
            "\u8fdb\u884c\u4fdd\u5b88\u964d\u7ea7\u751f\u6210\u3002"
        )
    return (
        "Aggregation failed, so the report falls back to a conservative synthesis "
        "from the validated extracted evidence."
    )


def _localized_failure_recommendation(output_language: str) -> str:
    if output_language == "zh":
        return (
            "CAUTION\uff1a\u5f53\u524d\u7ed3\u8bba\u57fa\u4e8e\u964d\u7ea7"
            "\u5206\u6790\u751f\u6210\uff0c\u5efa\u8bae\u8865\u5145\u66f4\u591a"
            "\u5df2\u9a8c\u8bc1\u8bc1\u636e\u540e\u518d\u505a\u6700\u7ec8"
            "\u5224\u65ad\u3002"
        )
    return (
        "Caution: this recommendation is generated from degraded analysis, so "
        "collect more validated evidence before making a final decision."
    )


def _localized_failure_uncertainty_note(output_language: str) -> str:
    if output_language == "zh":
        return (
            "\u805a\u5408\u9636\u6bb5\u5931\u8d25\uff0c\u6700\u7ec8\u5efa\u8bae"
            "\u57fa\u4e8e\u964d\u7ea7\u8bc1\u636e\u5408\u6210\u3002"
        )
    return (
        "Aggregation stage failed; recommendation is based on degraded evidence "
        "synthesis."
    )


def _parse_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _parse_whitespace_opportunities(value: object) -> list[WhitespaceOpportunity]:
    if not isinstance(value, list):
        return []
    opportunities: list[WhitespaceOpportunity] = []
    for item in value:
        try:
            opportunities.append(WhitespaceOpportunity.model_validate(item))
        except Exception:
            logger.warning("Skipping invalid whitespace opportunity: {}", item)
    return opportunities


def _parse_opportunity_score(value: object) -> OpportunityScoreBreakdown:
    if not isinstance(value, dict):
        return OpportunityScoreBreakdown()
    try:
        return OpportunityScoreBreakdown.model_validate(value)
    except Exception:
        logger.warning("Skipping invalid opportunity score payload: {}", value)
        return OpportunityScoreBreakdown()


def _build_evidence_category_counts(
    evidence_items: list[EvidenceItem],
) -> dict[str, int]:
    counts = Counter(item.category.value for item in evidence_items)
    return dict(counts)


def _build_fallback_whitespace_opportunities(
    *,
    differentiation_angles: list[str],
    pain_signals: list[PainSignal],
    commercial_signals: list[CommercialSignal],
    evidence_items: list[EvidenceItem],
    output_language: str,
) -> list[WhitespaceOpportunity]:
    if not differentiation_angles and not pain_signals and not commercial_signals:
        return []

    top_pain = pain_signals[0] if pain_signals else None
    top_commercial = commercial_signals[0] if commercial_signals else None
    lead_angle = differentiation_angles[0] if differentiation_angles else ""
    title = (
        "SMB whitespace wedge"
        if output_language == "en"
        else "\u4e2d\u5c0f\u56e2\u961f\u5207\u5165\u7a7a\u767d"
    )
    description_parts = [
        signal.summary
        for signal in (top_pain, top_commercial)
        if signal is not None and signal.summary
    ]
    description = " ".join(description_parts).strip()
    target_segment = _infer_target_segment(top_pain, top_commercial, output_language)
    wedge = lead_angle or (
        top_commercial.monetization_hint
        if top_commercial is not None and top_commercial.monetization_hint
        else (
            top_pain.theme
            if top_pain is not None
            else (
                "Focused workflow specialization"
                if output_language == "en"
                else "\u805a\u7126\u5de5\u4f5c\u6d41\u5207\u5165"
            )
        )
    )
    supporting_evidence = [
        item.url for item in evidence_items if isinstance(item.url, str) and item.url
    ][:3]
    return [
        WhitespaceOpportunity(
            title=title,
            description=description,
            target_segment=target_segment,
            wedge=wedge,
            potential_score=min(
                0.85,
                0.45
                + (top_pain.intensity * 0.2 if top_pain is not None else 0.0)
                + (
                    top_commercial.intent_strength * 0.2
                    if top_commercial is not None
                    else 0.0
                ),
            ),
            confidence=min(
                0.8,
                0.4 + 0.1 * len(differentiation_angles) + 0.1 * bool(evidence_items),
            ),
            supporting_evidence=supporting_evidence,
        )
    ]


def _build_fallback_opportunity_score(
    *,
    pain_signals: list[PainSignal],
    commercial_signals: list[CommercialSignal],
    whitespace_opportunities: list[WhitespaceOpportunity],
) -> OpportunityScoreBreakdown:
    pain_intensity = max((signal.intensity for signal in pain_signals), default=0.0)
    commercial_intent = max(
        (signal.intent_strength for signal in commercial_signals),
        default=0.0,
    )
    solution_gap = max(
        (opportunity.potential_score for opportunity in whitespace_opportunities),
        default=0.0,
    )
    score = min(
        1.0,
        pain_intensity * 0.35 + commercial_intent * 0.3 + solution_gap * 0.35,
    )
    return OpportunityScoreBreakdown(
        pain_intensity=round(pain_intensity, 2),
        solution_gap=round(solution_gap, 2),
        commercial_intent=round(commercial_intent, 2),
        freshness=0.0,
        competition_density=0.0,
        score=round(score, 2),
    )


def _infer_target_segment(
    pain_signal: PainSignal | None,
    commercial_signal: CommercialSignal | None,
    output_language: str,
) -> str:
    combined = " ".join(
        part
        for part in (
            pain_signal.theme if pain_signal is not None else "",
            commercial_signal.theme if commercial_signal is not None else "",
            commercial_signal.summary if commercial_signal is not None else "",
        )
        if part
    ).lower()
    if "smb" in combined or "small" in combined:
        return "SMB teams" if output_language == "en" else "\u4e2d\u5c0f\u56e2\u961f"
    if "team" in combined:
        return (
            "Operations teams"
            if output_language == "en"
            else "\u8fd0\u8425\u56e2\u961f"
        )
    return (
        "Focused niche teams"
        if output_language == "en"
        else "\u805a\u7126\u5782\u76f4\u56e2\u961f"
    )
