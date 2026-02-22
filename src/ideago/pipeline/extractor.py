"""Extractor — uses LLM to extract competitors from raw search results.

使用 LLM 从原始搜索结果中提取竞品信息。
"""

from __future__ import annotations

import json

from loguru import logger

from ideago.llm.client import LLMClient
from ideago.llm.prompt_loader import load_prompt
from ideago.models.research import Competitor, RawResult
from ideago.pipeline.exceptions import ExtractionError


class Extractor:
    """Extracts structured Competitor objects from raw search results using LLM."""

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    async def extract(
        self,
        raw_results: list[RawResult],
        query_context: str,
    ) -> list[Competitor]:
        """Extract competitors from raw results of a single platform.

        Args:
            raw_results: Raw search results from one data source.
            query_context: The user's original query for context.

        Returns:
            List of extracted Competitor objects. Invalid entries are skipped.
        """
        if not raw_results:
            return []

        try:
            platform = raw_results[0].platform
            raw_json = json.dumps(
                [
                    r.model_dump(mode="json", exclude={"raw_data", "fetched_at"})
                    for r in raw_results
                ],
                ensure_ascii=False,
            )
            prompt = load_prompt(
                "extractor",
                platform=platform.value,
                raw_results_json=raw_json,
                query_context=query_context,
            )
            data = await self._llm.complete_json(
                prompt,
                system="You are a competitor analysis expert. Return only valid JSON.",
            )
            logger.debug(
                "Extractor LLM response for {}: {} items",
                platform.value,
                len(data.get("competitors", [])),
            )

            result: list[Competitor] = []
            for entry in data.get("competitors", []):
                try:
                    comp = Competitor.model_validate(entry)
                    if comp.links:
                        result.append(comp)
                except Exception:
                    logger.warning("Skipping invalid competitor entry: {}", entry)
            return result
        except ExtractionError:
            raise
        except Exception as exc:
            raise ExtractionError(f"Failed to extract competitors: {exc}") from exc
