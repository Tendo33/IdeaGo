"""Intent parser — extracts structured search intent from natural language.

从自然语言中提取结构化搜索意图。
"""

from __future__ import annotations

import asyncio
from typing import Any

from ideago.llm.chat_model import ChatModelClient
from ideago.llm.prompt_loader import load_prompt
from ideago.models.research import Intent
from ideago.observability.log_config import get_logger
from ideago.pipeline.exceptions import IntentParsingError

logger = get_logger(__name__)


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
            data, llm_metrics = await _invoke_json_with_optional_meta(
                llm=self._llm,
                prompt=prompt,
                system="You are a startup research assistant. Return only valid JSON.",
            )
            self._store_metrics_for_current_task(llm_metrics)
            logger.debug("Intent parser LLM response: {}", data)
            intent = Intent.model_validate(data)
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
