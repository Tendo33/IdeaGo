"""Intent parser — extracts structured search intent from natural language.

从自然语言中提取结构化搜索意图。
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

from ideago.llm.chat_model import ChatModelClient
from ideago.llm.invoke_helpers import invoke_json_with_optional_meta
from ideago.llm.prompt_loader import load_prompt
from ideago.models.research import Intent
from ideago.observability.log_config import get_logger
from ideago.pipeline.exceptions import IntentParsingError

logger = get_logger(__name__)
_VALID_SEARCH_GOALS = {
    "find_direct_competitors",
    "find_adjacent_products",
    "find_workflow_interfaces",
    "find_market_evidence",
}


class IntentParser:
    """Parses a user's natural language query into a structured Intent."""

    def __init__(self, llm: ChatModelClient) -> None:
        self._llm = llm
        self._llm_metrics_by_task: dict[int, dict[str, Any]] = {}

    async def parse(self, query: str) -> Intent:
        """Parse user query into Intent with per-platform search queries.

        Args:
            query: User's natural language startup idea description.

        Returns:
            Structured Intent with keywords, app_type, and search queries.
        """
        try:
            prompt = load_prompt("intent_parser", query=query)
            data, llm_metrics = await invoke_json_with_optional_meta(
                llm=self._llm,
                prompt=prompt,
                system="You are a startup research assistant. Return only valid JSON.",
            )
            self._store_metrics_for_current_task(llm_metrics)
            logger.debug("Intent parser LLM response: {}", data)
            intent = Intent.model_validate(data)
            intent = _normalize_intent(intent, query=query)
            intent.cache_key = intent.compute_cache_key()
            return intent
        except IntentParsingError:
            raise
        except Exception as exc:
            raise IntentParsingError(f"Failed to parse intent: {exc}") from exc

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


def _normalize_intent(intent: Intent, *, query: str) -> Intent:
    output_language = (
        intent.output_language if intent.output_language in {"zh", "en"} else "en"
    )
    exact_entities = _dedupe_terms(intent.exact_entities)
    comparison_anchors = _dedupe_terms(intent.comparison_anchors)
    if not exact_entities:
        exact_entities = _infer_exact_entities_from_query(query)
        if exact_entities:
            logger.warning(
                "Intent parser missed exact anchors; recovered from query: {}",
                exact_entities,
            )
    keywords_en = _normalize_keywords(intent.keywords_en, exact_entities=exact_entities)
    normalized_search_goal = intent.search_goal.strip().lower()
    if normalized_search_goal not in _VALID_SEARCH_GOALS:
        normalized_search_goal = "find_direct_competitors"

    return intent.model_copy(
        update={
            "keywords_en": keywords_en,
            "exact_entities": exact_entities,
            "comparison_anchors": comparison_anchors,
            "search_goal": normalized_search_goal,
            "output_language": output_language,
        }
    )


def _dedupe_terms(values: list[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for value in values:
        cleaned = value.strip()
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(cleaned)
    return normalized


def _normalize_keywords(
    keywords: list[str],
    *,
    exact_entities: list[str],
) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for keyword in keywords:
        cleaned = keyword.strip()
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(cleaned)
    for entity in exact_entities:
        key = entity.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.insert(0, entity)
    return normalized or exact_entities[:]


def _infer_exact_entities_from_query(query: str) -> list[str]:
    candidates: list[str] = []
    for phrase in re.findall(
        r"\b(?:[A-Z][a-z]+|[A-Z]{2,})(?:\s+(?:[A-Z][a-z]+|[A-Z]{2,}))*\b", query
    ):
        cleaned = phrase.strip()
        if len(cleaned.split()) < 2:
            continue
        candidates.append(cleaned)
    return _dedupe_terms(candidates)
