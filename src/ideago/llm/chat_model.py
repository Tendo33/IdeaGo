"""LangChain-based chat model client with JSON response + retry support.

基于 LangChain 的聊天模型客户端，支持 JSON 输出与重试。
"""

from __future__ import annotations

import asyncio
import json
import random
from dataclasses import dataclass
from typing import Any

from json_repair import repair_json
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.utils.json import parse_json_markdown
from langchain_openai import ChatOpenAI
from openai import APIStatusError, APITimeoutError, RateLimitError
from pydantic import SecretStr

from ideago.observability.log_config import get_logger

logger = get_logger(__name__)

_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
_FAILOVER_STATUS_CODES = {401, 403, 404, 408, 409, 429, 500, 502, 503, 504}


@dataclass(frozen=True)
class LlmEndpointConfig:
    """Runtime config for one OpenAI-compatible endpoint."""

    name: str
    api_key: str
    model: str
    base_url: str | None
    timeout: int


def _empty_call_metadata() -> dict[str, Any]:
    return {
        "llm_calls": 0,
        "llm_retries": 0,
        "endpoint_failovers": 0,
        "tokens_prompt": 0,
        "tokens_completion": 0,
        "fallback_used": False,
        "endpoints_tried": [],
        "endpoint_used": "",
        "last_error_class": "",
        "json_parse_strategy": "",
    }


class ChatModelClient:
    """Thin async wrapper around LangChain ChatOpenAI for JSON responses."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str | None = None,
        timeout: int = 60,
        max_retries: int = 2,
        json_parse_max_retries: int = 1,
        base_delay: float = 1.0,
        fallback_endpoints: list[dict[str, Any]] | None = None,
    ) -> None:
        self._max_retries = max_retries
        self._json_parse_max_retries = max(0, int(json_parse_max_retries))
        self._base_delay = base_delay
        normalized_base_url = base_url.strip() if isinstance(base_url, str) else None
        if not normalized_base_url:
            normalized_base_url = None
        primary_endpoint = LlmEndpointConfig(
            name="primary",
            api_key=api_key,
            model=model,
            base_url=normalized_base_url,
            timeout=timeout,
        )
        self._endpoint_configs = [
            primary_endpoint,
            *_parse_fallback_endpoints(fallback_endpoints),
        ]
        self._clients = [
            self._build_chat_client(endpoint) for endpoint in self._endpoint_configs
        ]
        self._json_models = [
            client.bind(response_format={"type": "json_object"})
            for client in self._clients
        ]
        self._json_model = self._json_models[0]
        self._fallback_json_models = self._json_models[1:]

    def _build_chat_client(self, endpoint: LlmEndpointConfig) -> ChatOpenAI:
        return ChatOpenAI(
            api_key=SecretStr(endpoint.api_key),
            model=endpoint.model,
            base_url=endpoint.base_url,
            timeout=endpoint.timeout,
            max_retries=0,
        )

    async def _invoke_with_retry_meta(
        self,
        messages: list[Any],
        *,
        start_endpoint_index: int = 0,
    ) -> tuple[Any, dict[str, Any]]:
        """Invoke bound JSON model with exponential-backoff retry."""
        last_exc: Exception | None = None
        last_error_class = ""
        endpoint_failovers = 0
        attempts_total = 0
        endpoints_tried: list[str] = []
        models = [self._json_model, *self._fallback_json_models]
        if not models:
            raise RuntimeError("No LLM endpoint configured")
        ordered_endpoint_indexes = _build_ordered_endpoint_indexes(
            endpoint_count=len(models),
            start_index=start_endpoint_index,
        )
        used_fallback_endpoint = False

        for ordered_index, endpoint_index in enumerate(ordered_endpoint_indexes):
            json_model = models[endpoint_index]
            endpoint = self._endpoint_configs[
                min(endpoint_index, len(self._endpoint_configs) - 1)
            ]
            endpoints_tried.append(endpoint.name)
            used_fallback_endpoint = used_fallback_endpoint or endpoint_index > 0
            endpoint_exc: Exception | None = None
            retry_count_on_endpoint = 0
            max_attempts = self._max_retries + 1

            for attempt in range(max_attempts):
                attempts_total += 1
                try:
                    response = await json_model.ainvoke(messages)
                    prompt_tokens, completion_tokens = _extract_token_usage(response)
                    metadata = {
                        "llm_calls": attempts_total,
                        "llm_retries": max(0, attempts_total - 1),
                        "endpoint_failovers": endpoint_failovers,
                        "tokens_prompt": prompt_tokens,
                        "tokens_completion": completion_tokens,
                        "fallback_used": used_fallback_endpoint
                        or endpoint_failovers > 0,
                        "endpoints_tried": endpoints_tried,
                        "endpoint_used": endpoint.name,
                        "last_error_class": last_error_class,
                    }
                    return response, metadata
                except Exception as exc:
                    last_exc = exc
                    endpoint_exc = exc
                    error_class = _classify_exception(exc)
                    last_error_class = error_class
                    can_retry_same_endpoint = _is_retryable_exception(exc)
                    if can_retry_same_endpoint and attempt < self._max_retries:
                        retry_count_on_endpoint += 1
                        delay = _backoff_delay_seconds(self._base_delay, attempt)
                        logger.warning(
                            "Retryable LLM error [{}] on endpoint '{}' (attempt {}/{}), retrying in {:.2f}s",
                            error_class,
                            endpoint.name,
                            attempt + 1,
                            max_attempts,
                            delay,
                        )
                        await asyncio.sleep(delay)
                        continue
                    break

            if endpoint_exc is None:
                continue
            if ordered_index < len(
                ordered_endpoint_indexes
            ) - 1 and _is_failover_eligible(endpoint_exc):
                endpoint_failovers += 1
                logger.warning(
                    "Switching LLM endpoint '{}' after {} retries due to [{}]",
                    endpoint.name,
                    retry_count_on_endpoint,
                    last_error_class,
                )
                continue

            break

        logger.exception("LLM request failed")
        raise last_exc or RuntimeError("LLM request failed")

    async def _invoke_with_retry(self, messages: list[Any]) -> Any:
        response, _ = await self._invoke_with_retry_meta(messages)
        return response

    async def invoke_json(self, prompt: str, system: str = "") -> dict[str, Any]:
        """Invoke the chat model and parse JSON output."""
        payload, _ = await self.invoke_json_with_meta(prompt=prompt, system=system)
        return payload

    async def invoke_json_with_meta(
        self, prompt: str, system: str = ""
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Invoke the chat model and parse JSON output with call metadata."""
        messages: list[Any] = []
        if system:
            messages.append(SystemMessage(content=system))
        messages.append(HumanMessage(content=prompt))

        aggregated_metadata = _empty_call_metadata()
        model_count = max(1, len([self._json_model, *self._fallback_json_models]))
        next_start_index = 0
        last_decode_error: json.JSONDecodeError | None = None

        for parse_attempt in range(self._json_parse_max_retries + 1):
            response, metadata = await self._invoke_with_retry_meta(
                messages,
                start_endpoint_index=next_start_index,
            )
            aggregated_metadata = _merge_call_metadata(aggregated_metadata, metadata)
            content = _extract_content_text(response.content)
            try:
                payload, parse_strategy = _parse_json_response_content(content)
                aggregated_metadata["json_parse_strategy"] = parse_strategy
                return payload, aggregated_metadata
            except json.JSONDecodeError as exc:
                last_decode_error = exc
                logger.exception("LLM returned invalid JSON: {}", content[:200])
                aggregated_metadata["last_error_class"] = "json_parse_error"
                if parse_attempt >= self._json_parse_max_retries:
                    raise
                next_start_index = _next_start_endpoint_index(
                    current_endpoint_name=str(metadata.get("endpoint_used", "") or ""),
                    endpoint_configs=self._endpoint_configs,
                    model_count=model_count,
                )

        raise last_decode_error or RuntimeError("LLM JSON parsing failed")


def _is_retryable_exception(exc: Exception) -> bool:
    """Return whether exception is safe to retry."""
    return _classify_exception(exc) in {
        "rate_limit",
        "retryable_http",
        "network_error",
        "timeout_error",
    }


def _is_failover_eligible(exc: Exception) -> bool:
    error_class = _classify_exception(exc)
    return error_class in {
        "rate_limit",
        "retryable_http",
        "auth_error",
        "model_unavailable",
        "network_error",
        "timeout_error",
    }


def _merge_call_metadata(
    current: dict[str, Any], incoming: dict[str, Any]
) -> dict[str, Any]:
    merged = _empty_call_metadata()
    merged["llm_calls"] = _safe_non_negative_int(
        current.get("llm_calls")
    ) + _safe_non_negative_int(incoming.get("llm_calls"))
    merged["llm_retries"] = max(0, merged["llm_calls"] - 1)
    merged["endpoint_failovers"] = _safe_non_negative_int(
        current.get("endpoint_failovers")
    ) + _safe_non_negative_int(incoming.get("endpoint_failovers"))
    merged["tokens_prompt"] = _safe_non_negative_int(
        current.get("tokens_prompt")
    ) + _safe_non_negative_int(incoming.get("tokens_prompt"))
    merged["tokens_completion"] = _safe_non_negative_int(
        current.get("tokens_completion")
    ) + _safe_non_negative_int(incoming.get("tokens_completion"))
    merged["fallback_used"] = bool(current.get("fallback_used", False)) or bool(
        incoming.get("fallback_used", False)
    )
    merged["endpoints_tried"] = list(
        dict.fromkeys(
            [
                *[
                    str(item)
                    for item in current.get("endpoints_tried", [])
                    if str(item).strip()
                ],
                *[
                    str(item)
                    for item in incoming.get("endpoints_tried", [])
                    if str(item).strip()
                ],
            ]
        )
    )
    incoming_endpoint = str(incoming.get("endpoint_used", "") or "").strip()
    current_endpoint = str(current.get("endpoint_used", "") or "").strip()
    merged["endpoint_used"] = incoming_endpoint or current_endpoint
    incoming_error = str(incoming.get("last_error_class", "") or "").strip()
    current_error = str(current.get("last_error_class", "") or "").strip()
    merged["last_error_class"] = incoming_error or current_error
    incoming_parse_strategy = str(incoming.get("json_parse_strategy", "") or "").strip()
    current_parse_strategy = str(current.get("json_parse_strategy", "") or "").strip()
    merged["json_parse_strategy"] = incoming_parse_strategy or current_parse_strategy
    return merged


def _safe_non_negative_int(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, float):
        if value != value:  # NaN
            return 0
        return max(0, int(value))
    if isinstance(value, str):
        try:
            return max(0, int(value.strip() or "0"))
        except ValueError:
            return 0
    return 0


def _build_ordered_endpoint_indexes(endpoint_count: int, start_index: int) -> list[int]:
    if endpoint_count <= 0:
        return []
    normalized_start = start_index % endpoint_count
    return [
        (normalized_start + offset) % endpoint_count for offset in range(endpoint_count)
    ]


def _next_start_endpoint_index(
    *,
    current_endpoint_name: str,
    endpoint_configs: list[LlmEndpointConfig],
    model_count: int,
) -> int:
    if model_count <= 1:
        return 0
    normalized_name = current_endpoint_name.strip()
    current_index = 0
    for idx, endpoint in enumerate(endpoint_configs[:model_count]):
        if endpoint.name == normalized_name:
            current_index = idx
            break
    return (current_index + 1) % model_count


def _classify_exception(exc: Exception) -> str:
    if isinstance(exc, RateLimitError):
        return "rate_limit"
    if isinstance(exc, APITimeoutError):
        return "timeout_error"
    if isinstance(exc, APIStatusError):
        status = exc.status_code
        if status in {401, 403}:
            return "auth_error"
        if status == 404:
            return "model_unavailable"
        if status in _RETRYABLE_STATUS_CODES or status == 408:
            return "retryable_http"
        return "non_retryable_http"

    status_code = _extract_status_code(exc)
    if status_code in {401, 403}:
        return "auth_error"
    if status_code == 404:
        return "model_unavailable"
    if status_code in _RETRYABLE_STATUS_CODES or status_code == 408:
        return "retryable_http"

    name = exc.__class__.__name__.lower()
    message = str(exc).lower()
    if "ratelimit" in name or "rate_limit" in name or "too many requests" in message:
        return "rate_limit"
    if "timeout" in name or "timeout" in message or "timed out" in message:
        return "timeout_error"
    if any(token in message for token in ("connection", "network", "connect", "fetch")):
        return "network_error"
    return "unknown_error"


def _extract_status_code(exc: Exception) -> int | None:
    raw = getattr(exc, "status_code", None)
    if isinstance(raw, int):
        return raw
    response = getattr(exc, "response", None)
    if response is not None:
        status_code = getattr(response, "status_code", None)
        if isinstance(status_code, int):
            return status_code
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


def _parse_json_response_content(content: str) -> tuple[dict[str, Any], str]:
    """Parse model response into JSON object using layered, regex-free fallbacks."""
    normalized = content.strip()
    payload_text = normalized or "{}"

    strict_decode_error: json.JSONDecodeError | None = None
    try:
        parsed = json.loads(payload_text)
        if isinstance(parsed, dict):
            return parsed, "strict"
    except json.JSONDecodeError as exc:
        strict_decode_error = exc

    try:
        parsed_markdown = parse_json_markdown(payload_text)
        if isinstance(parsed_markdown, dict):
            return parsed_markdown, "markdown"
    except Exception:
        pass

    try:
        repaired = repair_json(payload_text, return_objects=True)
        if isinstance(repaired, dict):
            return repaired, "repair"
        if isinstance(repaired, str):
            parsed_repaired = json.loads(repaired)
            if isinstance(parsed_repaired, dict):
                return parsed_repaired, "repair"
    except Exception:
        pass

    if strict_decode_error is not None:
        raise strict_decode_error
    raise json.JSONDecodeError("Invalid JSON object", payload_text, 0)


def _extract_token_usage(response: Any) -> tuple[int, int]:
    prompt_tokens = 0
    completion_tokens = 0
    usage_candidates = []
    usage_metadata = getattr(response, "usage_metadata", None)
    if isinstance(usage_metadata, dict):
        usage_candidates.append(usage_metadata)
    response_metadata = getattr(response, "response_metadata", None)
    if isinstance(response_metadata, dict):
        token_usage = response_metadata.get("token_usage")
        if isinstance(token_usage, dict):
            usage_candidates.append(token_usage)
    additional_kwargs = getattr(response, "additional_kwargs", None)
    if isinstance(additional_kwargs, dict):
        usage = additional_kwargs.get("usage")
        if isinstance(usage, dict):
            usage_candidates.append(usage)

    for usage in usage_candidates:
        if not isinstance(usage, dict):
            continue
        prompt_tokens = int(
            usage.get("prompt_tokens")
            or usage.get("input_tokens")
            or prompt_tokens
            or 0
        )
        completion_tokens = int(
            usage.get("completion_tokens")
            or usage.get("output_tokens")
            or completion_tokens
            or 0
        )
    return max(prompt_tokens, 0), max(completion_tokens, 0)


def _parse_fallback_endpoints(
    fallback_endpoints: list[dict[str, Any]] | None,
) -> list[LlmEndpointConfig]:
    if not fallback_endpoints:
        return []

    endpoints: list[LlmEndpointConfig] = []
    for index, endpoint in enumerate(fallback_endpoints):
        if not isinstance(endpoint, dict):
            continue
        api_key_raw = endpoint.get("api_key")
        model_raw = endpoint.get("model")
        if not isinstance(api_key_raw, str) or not api_key_raw.strip():
            continue
        if not isinstance(model_raw, str) or not model_raw.strip():
            continue
        base_url_raw = endpoint.get("base_url")
        normalized_base_url = (
            base_url_raw.strip()
            if isinstance(base_url_raw, str) and base_url_raw.strip()
            else None
        )
        timeout_raw = endpoint.get("timeout")
        timeout = (
            int(timeout_raw) if isinstance(timeout_raw, int) and timeout_raw > 0 else 60
        )
        name_raw = endpoint.get("name")
        name = (
            name_raw.strip()
            if isinstance(name_raw, str) and name_raw.strip()
            else f"fallback-{index + 1}"
        )
        endpoints.append(
            LlmEndpointConfig(
                name=name,
                api_key=api_key_raw.strip(),
                model=model_raw.strip(),
                base_url=normalized_base_url,
                timeout=timeout,
            )
        )
    return endpoints


def _backoff_delay_seconds(base_delay: float, attempt: int) -> float:
    jitter = random.uniform(0.0, 0.25)
    return base_delay * (2**attempt) + jitter
