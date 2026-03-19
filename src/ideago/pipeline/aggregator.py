"""Aggregator — LLM-only market analysis on pre-merged competitors.

Dedup/scoring is now handled by ``merger.py``. This module focuses the LLM
exclusively on market analysis, go/no-go recommendation, and differentiation.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any

from ideago.llm.chat_model import ChatModelClient
from ideago.llm.invoke_helpers import invoke_json_with_optional_meta
from ideago.llm.prompt_loader import load_prompt
from ideago.models.research import Competitor, RecommendationType
from ideago.observability.log_config import get_logger
from ideago.pipeline.exceptions import AggregationError

logger = get_logger(__name__)


@dataclass
class AggregationResult:
    """Result of the analysis phase (no competitor modifications)."""

    competitors: list[Competitor] = field(default_factory=list)
    market_summary: str = ""
    go_no_go: str = ""
    recommendation_type: RecommendationType = RecommendationType.GO
    differentiation_angles: list[str] = field(default_factory=list)


class Aggregator:
    """Market analysis using LLM on already-deduplicated competitors."""

    def __init__(self, llm: ChatModelClient) -> None:
        self._llm = llm
        self._llm_metrics_by_task: dict[int, dict[str, Any]] = {}

    async def analyze(
        self,
        competitors: list[Competitor],
        original_query: str,
    ) -> AggregationResult:
        """Generate market analysis on pre-merged competitors.

        Args:
            competitors: Deduplicated competitor list (from merger.py).
            original_query: The user's original query text.

        Returns:
            AggregationResult with analysis fields populated.
        """
        if not competitors:
            return AggregationResult(
                market_summary="No competitors were found across any data source.",
                go_no_go="Go — This appears to be an unexplored space based on available data.",
            )

        try:
            competitors_json = json.dumps(
                [c.model_dump(mode="json") for c in competitors],
                ensure_ascii=False,
            )
            prompt = load_prompt(
                "aggregator",
                competitors_json=competitors_json,
                original_query=original_query,
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

            return AggregationResult(
                competitors=competitors,
                market_summary=data.get("market_summary", ""),
                go_no_go=data.get("go_no_go", ""),
                recommendation_type=rec_type,
                differentiation_angles=data.get("differentiation_angles", []),
            )
        except AggregationError:
            raise
        except Exception as exc:
            raise AggregationError(f"Failed to analyze: {exc}") from exc

    async def aggregate(
        self,
        competitors: list[Competitor],
        original_query: str,
    ) -> AggregationResult:
        """Backward-compatible alias for ``analyze``."""
        return await self.analyze(competitors, original_query)

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
