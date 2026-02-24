"""Extractor — uses LLM to extract competitors from raw search results.

使用 LLM 从原始搜索结果中提取竞品信息。
"""

from __future__ import annotations

import json
from urllib.parse import urlsplit, urlunsplit

from loguru import logger

from ideago.llm.chat_model import ChatModelClient
from ideago.llm.prompt_loader import load_prompt
from ideago.models.research import Competitor, RawResult
from ideago.pipeline.exceptions import ExtractionError


class Extractor:
    """Extracts structured Competitor objects from raw search results using LLM."""

    def __init__(self, llm: ChatModelClient) -> None:
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
            allowed_urls = {
                _normalize_url(r.url) for r in raw_results if _normalize_url(r.url)
            }
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
            data = await self._llm.invoke_json(
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
                    filtered_links = [
                        link
                        for link in comp.links
                        if _normalize_url(link) in allowed_urls
                    ]
                    filtered_source_urls = [
                        url
                        for url in comp.source_urls
                        if _normalize_url(url) in allowed_urls
                    ]
                    if not filtered_links:
                        logger.warning(
                            "Dropping competitor '{}' due to unverifiable links",
                            comp.name,
                        )
                        continue
                    if len(filtered_links) < len(comp.links):
                        logger.info(
                            "Filtered {} fabricated links for competitor '{}'",
                            len(comp.links) - len(filtered_links),
                            comp.name,
                        )
                    result.append(
                        comp.model_copy(
                            update={
                                "links": filtered_links,
                                "source_urls": filtered_source_urls or filtered_links,
                            }
                        )
                    )
                except Exception:
                    logger.warning("Skipping invalid competitor entry: {}", entry)
            return result
        except ExtractionError:
            raise
        except Exception as exc:
            raise ExtractionError(f"Failed to extract competitors: {exc}") from exc


def _normalize_url(url: str) -> str:
    """Normalize URL for strict source-link verification."""
    if not url:
        return ""
    try:
        parsed = urlsplit(url.strip())
    except ValueError:
        return ""
    if not parsed.scheme or not parsed.netloc:
        return ""
    path = parsed.path.rstrip("/")
    return urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            "",
            "",
        )
    )
