"""Intent parser — extracts structured search intent from natural language.

从自然语言中提取结构化搜索意图。
"""

from __future__ import annotations

from loguru import logger

from ideago.llm.chat_model import ChatModelClient
from ideago.llm.prompt_loader import load_prompt
from ideago.models.research import Intent
from ideago.pipeline.exceptions import IntentParsingError


class IntentParser:
    """Parses a user's natural language query into a structured Intent."""

    def __init__(self, llm: ChatModelClient) -> None:
        self._llm = llm

    async def parse(self, query: str) -> Intent:
        """Parse user query into Intent with per-platform search queries.

        Args:
            query: User's natural language startup idea description.

        Returns:
            Structured Intent with keywords, app_type, and search queries.
        """
        try:
            prompt = load_prompt("intent_parser", query=query)
            data = await self._llm.invoke_json(
                prompt,
                system="You are a startup research assistant. Return only valid JSON.",
            )
            logger.debug("Intent parser LLM response: {}", data)
            intent = Intent.model_validate(data)
            intent.cache_key = intent.compute_cache_key()
            return intent
        except IntentParsingError:
            raise
        except Exception as exc:
            raise IntentParsingError(f"Failed to parse intent: {exc}") from exc
