"""Aggregator — deduplicates competitors and generates market summary.

全局聚合：竞品去重 + 市场分析 + Go/No-Go 建议。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from loguru import logger

from ideago.llm.client import LLMClient
from ideago.llm.prompt_loader import load_prompt
from ideago.models.research import Competitor


@dataclass
class AggregationResult:
    """Result of the aggregation phase."""

    competitors: list[Competitor] = field(default_factory=list)
    market_summary: str = ""
    go_no_go: str = ""
    differentiation_angles: list[str] = field(default_factory=list)


class Aggregator:
    """Deduplicates competitors across platforms and generates market insights."""

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    async def aggregate(
        self,
        competitors: list[Competitor],
        original_query: str,
    ) -> AggregationResult:
        """Deduplicate competitors and generate market analysis.

        Args:
            competitors: All competitors from all platforms (may contain duplicates).
            original_query: The user's original query text.

        Returns:
            AggregationResult with deduplicated list and analysis.
        """
        if not competitors:
            return AggregationResult(
                market_summary="No competitors were found across any data source.",
                go_no_go="Go — This appears to be an unexplored space based on available data.",
            )

        competitors_json = json.dumps(
            [c.model_dump(mode="json") for c in competitors],
            ensure_ascii=False,
        )
        prompt = load_prompt(
            "aggregator",
            competitors_json=competitors_json,
            original_query=original_query,
        )
        data = await self._llm.complete_json(
            prompt,
            system="You are a market research analyst. Return only valid JSON.",
        )
        logger.debug(
            "Aggregator LLM response: {} competitors", len(data.get("competitors", []))
        )

        deduped: list[Competitor] = []
        for entry in data.get("competitors", []):
            try:
                comp = Competitor.model_validate(entry)
                deduped.append(comp)
            except Exception:
                logger.warning("Skipping invalid competitor in aggregation: {}", entry)

        deduped.sort(key=lambda c: c.relevance_score, reverse=True)

        return AggregationResult(
            competitors=deduped,
            market_summary=data.get("market_summary", ""),
            go_no_go=data.get("go_no_go", ""),
            differentiation_angles=data.get("differentiation_angles", []),
        )
