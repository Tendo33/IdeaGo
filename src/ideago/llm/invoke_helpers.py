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
    """Invoke LLM for JSON output, extracting call metadata when available.

    Tries ``invoke_json_with_meta`` first (returns data + metrics in one call).
    Falls back to ``invoke_json`` + ``pop_last_call_metadata``.

    Returns:
        Tuple of (parsed_json_data, llm_call_metadata).
    """
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
