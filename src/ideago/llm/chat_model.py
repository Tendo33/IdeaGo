"""LangChain-based chat model client with JSON response + retry support.

基于 LangChain 的聊天模型客户端，支持 JSON 输出与重试。
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from openai import APIStatusError, RateLimitError
from pydantic import SecretStr

from ideago.observability.log_config import get_logger

logger = get_logger(__name__)

_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class ChatModelClient:
    """Thin async wrapper around LangChain ChatOpenAI for JSON responses."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        timeout: int = 60,
        max_retries: int = 2,
        base_delay: float = 1.0,
    ) -> None:
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._client = ChatOpenAI(
            api_key=SecretStr(api_key),
            model=model,
            timeout=timeout,
            max_retries=0,
        )
        self._json_model = self._client.bind(response_format={"type": "json_object"})

    async def _invoke_with_retry(self, messages: list[Any]) -> Any:
        """Invoke bound JSON model with exponential-backoff retry."""
        last_exc: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                return await self._json_model.ainvoke(messages)
            except Exception as exc:
                last_exc = exc
                if _is_retryable_exception(exc) and attempt < self._max_retries:
                    delay = self._base_delay * (2**attempt)
                    logger.warning(
                        "Retryable LLM error (attempt {}/{}), retrying in {:.1f}s",
                        attempt + 1,
                        self._max_retries + 1,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                logger.exception("LLM request failed")
                raise
        raise last_exc  # type: ignore[misc]

    async def invoke_json(self, prompt: str, system: str = "") -> dict[str, Any]:
        """Invoke the chat model and parse JSON output."""
        messages: list[Any] = []
        if system:
            messages.append(SystemMessage(content=system))
        messages.append(HumanMessage(content=prompt))

        response = await self._invoke_with_retry(messages)
        content = _extract_content_text(response.content)
        try:
            return json.loads(content or "{}")
        except json.JSONDecodeError:
            logger.exception("LLM returned invalid JSON: {}", content[:200])
            raise


def _is_retryable_exception(exc: Exception) -> bool:
    """Return whether exception is safe to retry."""
    if isinstance(exc, RateLimitError):
        return True
    if isinstance(exc, APIStatusError):
        return exc.status_code in _RETRYABLE_STATUS_CODES

    status_code = _extract_status_code(exc)
    if status_code in _RETRYABLE_STATUS_CODES:
        return True

    name = exc.__class__.__name__.lower()
    if "ratelimit" in name or "rate_limit" in name:
        return True

    cause = exc.__cause__ or exc.__context__
    if isinstance(cause, Exception):
        return _is_retryable_exception(cause)
    return False


def _extract_status_code(exc: Exception) -> int | None:
    raw = getattr(exc, "status_code", None)
    if isinstance(raw, int):
        return raw
    return None


def _extract_content_text(content: Any) -> str:
    """Normalize model response content to plain text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    return str(content)
