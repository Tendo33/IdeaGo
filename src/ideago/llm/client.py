"""Async OpenAI client wrapper with JSON mode support and retry logic.

异步 OpenAI 客户端封装，支持 JSON 格式输出及自动重试。
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from loguru import logger
from openai import APIStatusError, AsyncOpenAI, RateLimitError

_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
_MAX_RETRIES = 2
_BASE_DELAY = 1.0


class LLMClient:
    """Thin async wrapper around the OpenAI ChatCompletion API with retry."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        timeout: int = 60,
    ) -> None:
        self._client = AsyncOpenAI(api_key=api_key, timeout=timeout)
        self._model = model

    async def _call_with_retry(
        self,
        messages: list[dict[str, str]],
        response_format: dict[str, str] | None = None,
    ) -> str:
        """Execute a chat completion with exponential-backoff retry for transient errors."""
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                kwargs: dict[str, Any] = dict(model=self._model, messages=messages)
                if response_format:
                    kwargs["response_format"] = response_format
                response = await self._client.chat.completions.create(**kwargs)
                return response.choices[0].message.content or ""
            except RateLimitError as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES:
                    delay = _BASE_DELAY * (2**attempt)
                    logger.warning(
                        "Rate limited (attempt {}/{}), retrying in {:.1f}s",
                        attempt + 1,
                        _MAX_RETRIES + 1,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                raise
            except APIStatusError as exc:
                last_exc = exc
                if (
                    exc.status_code in _RETRYABLE_STATUS_CODES
                    and attempt < _MAX_RETRIES
                ):
                    delay = _BASE_DELAY * (2**attempt)
                    logger.warning(
                        "Transient API error {} (attempt {}/{}), retrying in {:.1f}s",
                        exc.status_code,
                        attempt + 1,
                        _MAX_RETRIES + 1,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                raise
            except Exception:
                logger.exception("LLM request failed")
                raise
        raise last_exc  # type: ignore[misc]

    async def complete(self, prompt: str, system: str = "") -> str:
        """Send a chat completion request and return the text response."""
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return await self._call_with_retry(messages)

    async def complete_json(self, prompt: str, system: str = "") -> dict[str, Any]:
        """Send a chat completion request with JSON mode and return parsed dict."""
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        content = await self._call_with_retry(
            messages, response_format={"type": "json_object"}
        )
        try:
            return json.loads(content or "{}")
        except json.JSONDecodeError:
            logger.exception("LLM returned invalid JSON: {}", content[:200])
            raise
