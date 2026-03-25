"""Shared LLM invocation helpers used by pipeline components."""

from __future__ import annotations

from typing import Any

from ideago.llm.chat_model import ChatModelClient


async def invoke_json_with_optional_meta(
    *,
    llm: ChatModelClient,
    prompt: str,
    system: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Invoke LLM for JSON output, extracting call metadata.

    Returns:
        Tuple of (parsed_json_data, llm_call_metadata).
    """
    return await llm.invoke_json_with_meta(prompt=prompt, system=system)
