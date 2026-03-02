"""Extractor — uses LLM to extract competitors from raw search results.

使用 LLM 从原始搜索结果中提取竞品信息。
"""

from __future__ import annotations

import asyncio
import json
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from ideago.llm.chat_model import ChatModelClient
from ideago.llm.prompt_loader import load_prompt
from ideago.models.research import Competitor, RawResult
from ideago.observability.log_config import get_logger
from ideago.pipeline.exceptions import ExtractionError

logger = get_logger(__name__)


class Extractor:
    """Extracts structured Competitor objects from raw search results using LLM."""

    def __init__(self, llm: ChatModelClient) -> None:
        self._llm = llm
        self._llm_metrics_by_task: dict[int, dict[str, Any]] = {}

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
            data, llm_metrics = await _invoke_json_with_optional_meta(
                llm=self._llm,
                prompt=prompt,
                system="You are a competitor analysis expert. Return only valid JSON.",
            )
            self._store_metrics_for_current_task(llm_metrics)
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


async def _invoke_json_with_optional_meta(
    *,
    llm: ChatModelClient,
    prompt: str,
    system: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    invoke_with_meta = getattr(llm, "invoke_json_with_meta", None)
    if callable(invoke_with_meta):
        payload = await invoke_with_meta(prompt=prompt, system=system)
        if (
            isinstance(payload, tuple)
            and len(payload) == 2
            and isinstance(payload[0], dict)
            and isinstance(payload[1], dict)
        ):
            return payload[0], payload[1]

    data = await llm.invoke_json(prompt=prompt, system=system)
    pop_meta = getattr(llm, "pop_last_call_metadata", None)
    if callable(pop_meta):
        payload = pop_meta()
        if isinstance(payload, dict):
            return data, payload
    return data, {}
