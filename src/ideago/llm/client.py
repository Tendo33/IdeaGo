"""Async OpenAI client wrapper with JSON mode support.

异步 OpenAI 客户端封装，支持 JSON 格式输出。
"""

from __future__ import annotations

import json
from typing import Any

from loguru import logger
from openai import AsyncOpenAI


class LLMClient:
    """Thin async wrapper around the OpenAI ChatCompletion API."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        timeout: int = 60,
    ) -> None:
        self._client = AsyncOpenAI(api_key=api_key, timeout=timeout)
        self._model = model

    async def complete(self, prompt: str, system: str = "") -> str:
        """Send a chat completion request and return the text response."""
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
            )
            return response.choices[0].message.content or ""
        except Exception:
            logger.exception("LLM completion request failed")
            raise

    async def complete_json(self, prompt: str, system: str = "") -> dict[str, Any]:
        """Send a chat completion request with JSON mode and return parsed dict."""
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content or "{}"
            return json.loads(content)
        except json.JSONDecodeError:
            logger.exception("LLM returned invalid JSON")
            raise
        except Exception:
            logger.exception("LLM JSON completion request failed")
            raise
