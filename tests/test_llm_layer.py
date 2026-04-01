"""Tests for LLM client, prompt loader, intent parser, extractor, aggregator."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from openai import APIStatusError

from ideago.llm.chat_model import (
    ChatModelClient,
    LlmEndpointConfig,
    _backoff_delay_seconds,
    _build_ordered_endpoint_indexes,
    _classify_exception,
    _empty_call_metadata,
    _extract_content_text,
    _extract_status_code,
    _extract_token_usage,
    _merge_call_metadata,
    _next_start_endpoint_index,
    _parse_fallback_endpoints,
    _parse_json_response_content,
    _safe_non_negative_int,
)
from ideago.llm.prompt_loader import load_prompt
from ideago.models.research import (
    Competitor,
    Intent,
    Platform,
    QueryFamily,
    QueryPlan,
    RawResult,
)
from ideago.pipeline.aggregator import AggregationResult, Aggregator
from ideago.pipeline.exceptions import AggregationError, IntentParsingError
from ideago.pipeline.extractor import Extractor
from ideago.pipeline.intent_parser import IntentParser
from ideago.pipeline.merger import merge_competitors
from ideago.pipeline.query_planning import QueryPlanner

_TEST_INTENT = Intent(
    keywords_en=["markdown", "notes"],
    app_type="browser-extension",
    target_scenario="Take markdown notes",
    output_language="en",
    cache_key="test-key",
)

# ---------- prompt_loader ----------


def test_load_prompt_intent_parser() -> None:
    prompt = load_prompt("intent_parser", query="I want to build a markdown clipper")
    assert "markdown clipper" in prompt
    assert "keywords_en" in prompt
    assert "exact_entities" in prompt
    assert "comparison_anchors" in prompt
    assert "output_language" in prompt
    assert "app_type" in prompt
    assert "target_scenario" in prompt
    assert "Do not invent product or company names" in prompt
    assert "{query}" not in prompt


def test_load_prompt_extractor() -> None:
    prompt = load_prompt(
        "extractor",
        platform="github",
        raw_results_json="[]",
        keywords="markdown, notes",
        app_type="web",
        target_scenario="Take notes",
        output_language="en",
    )
    assert "github" in prompt
    assert "markdown, notes" in prompt
    assert "Output language: en" in prompt
    assert "{platform}" not in prompt


def test_load_prompt_extractor_appstore() -> None:
    prompt = load_prompt(
        "extractor_appstore",
        platform="appstore",
        raw_results_json="[]",
        keywords="notes",
        app_type="mobile",
        target_scenario="Capture notes",
        output_language="zh",
    )
    assert "App Store products" in prompt
    assert "Output language: zh" in prompt
    assert "{platform}" not in prompt


def test_load_prompt_aggregator() -> None:
    prompt = load_prompt(
        "aggregator",
        competitors_json="[]",
        original_query="test idea",
        output_language="zh",
    )
    assert "test idea" in prompt
    assert "Output Language" in prompt


def test_load_prompt_missing_raises() -> None:
    with pytest.raises(FileNotFoundError):
        load_prompt("nonexistent_template_xyz")


# ---------- ChatModelClient ----------


def _make_mock_chat_response(content: str) -> MagicMock:
    response = MagicMock()
    response.content = content
    return response


@pytest.mark.asyncio
async def test_chat_model_client_invoke_json_parses() -> None:
    client = ChatModelClient(api_key="sk-test", model="gpt-4o-mini")
    mock_resp = _make_mock_chat_response('{"name": "test", "score": 0.8}')
    client._invoke_with_retry_meta = AsyncMock(
        return_value=(mock_resp, {"llm_calls": 1})
    )

    result = await client.invoke_json("test prompt")
    assert result["name"] == "test"
    assert result["score"] == 0.8


@pytest.mark.asyncio
async def test_chat_model_client_invoke_json_invalid_raises() -> None:
    client = ChatModelClient(api_key="sk-test", model="gpt-4o-mini")
    mock_resp = _make_mock_chat_response("not valid json {{{")
    client._invoke_with_retry_meta = AsyncMock(
        return_value=(mock_resp, {"llm_calls": 1})
    )

    with pytest.raises(json.JSONDecodeError):
        await client.invoke_json("test")


def test_parse_json_response_content_accepts_markdown_block() -> None:
    payload, strategy = _parse_json_response_content(
        '```json\n{"name":"test","score":0.8}\n```'
    )
    assert payload["name"] == "test"
    assert payload["score"] == 0.8
    assert strategy == "markdown"


def test_parse_json_response_content_accepts_prefixed_chatter() -> None:
    payload, strategy = _parse_json_response_content(
        '好的，这是你的结果：\n{"name":"test","score":0.8}'
    )
    assert payload["name"] == "test"
    assert payload["score"] == 0.8
    assert strategy in {"markdown", "repair"}


def test_parse_json_response_content_repairs_trailing_comma() -> None:
    payload, strategy = _parse_json_response_content('{"name":"test","score":0.8,}')
    assert payload["name"] == "test"
    assert payload["score"] == 0.8
    assert strategy == "repair"


@pytest.mark.asyncio
async def test_chat_model_client_retries_retryable_errors() -> None:
    class RetryableError(Exception):
        status_code = 429

    client = ChatModelClient(
        api_key="sk-test",
        model="gpt-4o-mini",
        max_retries=2,
        base_delay=0.0,
    )
    mock_resp = _make_mock_chat_response('{"ok": true}')
    client._json_model = MagicMock()
    client._json_model.ainvoke = AsyncMock(
        side_effect=[
            RetryableError("rate limit"),
            RetryableError("rate limit"),
            mock_resp,
        ]
    )

    result, metadata = await client.invoke_json_with_meta("test")
    assert result["ok"] is True
    assert client._json_model.ainvoke.call_count == 3
    assert metadata["llm_calls"] == 3
    assert metadata["llm_retries"] == 2
    assert metadata["endpoint_used"] == "primary"


@pytest.mark.asyncio
async def test_chat_model_client_failovers_on_auth_error() -> None:
    class AuthError(Exception):
        status_code = 401

    client = ChatModelClient(
        api_key="sk-primary",
        model="gpt-4o-mini",
        max_retries=0,
        fallback_endpoints=[
            {"api_key": "sk-fallback", "model": "gpt-4o-mini"},
        ],
    )
    primary_model = MagicMock()
    fallback_model = MagicMock()
    primary_model.ainvoke = AsyncMock(side_effect=AuthError("forbidden"))
    fallback_model.ainvoke = AsyncMock(
        return_value=_make_mock_chat_response('{"ok": true}')
    )
    client._json_model = primary_model
    client._fallback_json_models = [fallback_model]

    payload, metadata = await client.invoke_json_with_meta("test prompt")

    assert payload["ok"] is True
    assert metadata["llm_calls"] == 2
    assert metadata["llm_retries"] == 1
    assert metadata["fallback_used"] is True
    assert metadata["endpoint_failovers"] == 1
    assert metadata["endpoints_tried"] == ["primary", "fallback-1"]
    assert metadata["endpoint_used"] == "fallback-1"


@pytest.mark.asyncio
async def test_chat_model_client_all_endpoints_fail_exposes_error_class() -> None:
    class AuthError(Exception):
        status_code = 403

    client = ChatModelClient(
        api_key="sk-primary",
        model="gpt-4o-mini",
        max_retries=0,
        fallback_endpoints=[
            {"api_key": "sk-fallback", "model": "gpt-4o-mini"},
        ],
    )
    primary_model = MagicMock()
    fallback_model = MagicMock()
    primary_model.ainvoke = AsyncMock(side_effect=AuthError("forbidden"))
    fallback_model.ainvoke = AsyncMock(side_effect=AuthError("forbidden"))
    client._json_model = primary_model
    client._fallback_json_models = [fallback_model]

    with pytest.raises(AuthError):
        await client.invoke_json("test prompt")

    assert primary_model.ainvoke.call_count == 1
    assert fallback_model.ainvoke.call_count == 1


@pytest.mark.asyncio
async def test_chat_model_client_json_parse_retry_with_endpoint_failover_succeeds() -> (
    None
):
    client = ChatModelClient(
        api_key="sk-primary",
        model="gpt-4o-mini",
        max_retries=0,
        json_parse_max_retries=1,
        fallback_endpoints=[{"api_key": "sk-fallback", "model": "gpt-4o-mini"}],
    )
    primary_model = MagicMock()
    fallback_model = MagicMock()
    primary_model.ainvoke = AsyncMock(
        return_value=_make_mock_chat_response("not valid json {{{")
    )
    fallback_model.ainvoke = AsyncMock(
        return_value=_make_mock_chat_response('{"ok": true}')
    )
    client._json_model = primary_model
    client._fallback_json_models = [fallback_model]

    payload, metadata = await client.invoke_json_with_meta("test prompt")

    assert payload["ok"] is True
    assert primary_model.ainvoke.call_count == 1
    assert fallback_model.ainvoke.call_count == 1
    assert metadata["llm_calls"] == 2
    assert metadata["llm_retries"] == 1
    assert metadata["fallback_used"] is True
    assert metadata["endpoints_tried"] == ["primary", "fallback-1"]
    assert metadata["endpoint_used"] == "fallback-1"


@pytest.mark.asyncio
async def test_chat_model_client_json_parse_retry_exhausted_raises() -> None:
    client = ChatModelClient(
        api_key="sk-primary",
        model="gpt-4o-mini",
        max_retries=0,
        json_parse_max_retries=1,
    )
    primary_model = MagicMock()
    primary_model.ainvoke = AsyncMock(
        return_value=_make_mock_chat_response("not valid json {{{")
    )
    client._json_model = primary_model
    client._fallback_json_models = []

    with pytest.raises(json.JSONDecodeError):
        await client.invoke_json("test prompt")

    assert primary_model.ainvoke.call_count == 2


def test_chat_model_client_passes_custom_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

        def bind(self, **_: object) -> MagicMock:
            return MagicMock()

    monkeypatch.setattr("ideago.llm.chat_model.ChatOpenAI", FakeChatOpenAI)

    ChatModelClient(
        api_key="sk-test",
        model="gpt-4o-mini",
        base_url="https://openrouter.ai/api/v1",
    )

    assert captured["base_url"] == "https://openrouter.ai/api/v1"


def test_chat_model_client_treats_blank_base_url_as_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

        def bind(self, **_: object) -> MagicMock:
            return MagicMock()

    monkeypatch.setattr("ideago.llm.chat_model.ChatOpenAI", FakeChatOpenAI)

    ChatModelClient(api_key="sk-test", model="gpt-4o-mini", base_url="   ")

    assert captured["base_url"] is None


def test_chat_model_helpers_cover_metadata_and_parsing_paths() -> None:
    metadata = _empty_call_metadata()
    assert metadata["llm_calls"] == 0

    merged = _merge_call_metadata(
        {
            "llm_calls": "2",
            "endpoint_failovers": 1,
            "tokens_prompt": 3.0,
            "tokens_completion": True,
            "fallback_used": False,
            "endpoints_tried": ["primary", ""],
            "endpoint_used": "",
            "last_error_class": "old",
        },
        {
            "llm_calls": 1,
            "endpoint_failovers": "2",
            "tokens_prompt": "4",
            "tokens_completion": 5,
            "fallback_used": True,
            "endpoints_tried": ["fallback-1", "primary"],
            "endpoint_used": "fallback-1",
            "last_error_class": "timeout_error",
        },
    )
    assert merged["llm_calls"] == 3
    assert merged["llm_retries"] == 2
    assert merged["endpoint_failovers"] == 3
    assert merged["tokens_prompt"] == 7
    assert merged["tokens_completion"] == 6
    assert merged["fallback_used"] is True
    assert merged["endpoints_tried"] == ["primary", "fallback-1"]
    assert merged["endpoint_used"] == "fallback-1"
    assert merged["last_error_class"] == "timeout_error"

    assert _safe_non_negative_int(True) == 1
    assert _safe_non_negative_int(-4) == 0
    assert _safe_non_negative_int(3.7) == 3
    assert _safe_non_negative_int(" 5 ") == 5
    assert _safe_non_negative_int("bad") == 0

    assert _build_ordered_endpoint_indexes(3, 1) == [1, 2, 0]
    assert _build_ordered_endpoint_indexes(0, 1) == []
    assert (
        _next_start_endpoint_index(
            current_endpoint_name="fallback-1",
            endpoint_configs=[
                LlmEndpointConfig("primary", "k", "m", None, 60),
                LlmEndpointConfig("fallback-1", "k2", "m2", None, 60),
            ],
            model_count=2,
        )
        == 0
    )

    endpoints = _parse_fallback_endpoints(
        [
            {"api_key": " ", "model": "m"},
            {
                "api_key": "k1",
                "model": "m1",
                "name": " fb ",
                "base_url": " https://x ",
                "timeout": 30,
            },
            {"api_key": "k2", "model": "m2"},
            "bad",
        ]
    )
    assert [endpoint.name for endpoint in endpoints] == ["fb", "fallback-3"]
    assert endpoints[0].base_url == "https://x"
    assert endpoints[1].timeout == 60

    assert _extract_content_text("hello") == "hello"
    assert _extract_content_text(["a", {"text": "b"}, {"bad": "x"}]) == "ab"
    assert _extract_content_text(123) == "123"

    response = MagicMock()
    response.content = "{}"
    response.usage_metadata = {"input_tokens": 3, "output_tokens": 4}
    response.response_metadata = {"token_usage": {"prompt_tokens": 5}}
    response.additional_kwargs = {"usage": {"completion_tokens": 6}}
    assert _extract_token_usage(response) == (5, 6)


def test_chat_model_exception_classification_helpers() -> None:
    response = MagicMock()
    response.status_code = 404
    api_error = APIStatusError.__new__(APIStatusError)
    api_error.response = response
    api_error.status_code = 404
    assert _classify_exception(api_error) == "model_unavailable"

    class StatusExc(Exception):
        def __init__(self, status_code: int, message: str) -> None:
            super().__init__(message)
            self.status_code = status_code

    assert _classify_exception(StatusExc(401, "forbidden")) == "auth_error"
    assert _classify_exception(StatusExc(429, "too many requests")) == "retryable_http"
    assert (
        _classify_exception(RuntimeError("network connection dropped"))
        == "network_error"
    )
    assert _classify_exception(RuntimeError("request timed out")) == "timeout_error"
    assert _classify_exception(RuntimeError("other")) == "unknown_error"
    assert _extract_status_code(StatusExc(500, "boom")) == 500
    assert _extract_status_code(RuntimeError("boom")) is None


def test_backoff_delay_is_non_negative() -> None:
    delay = _backoff_delay_seconds(0.5, 2)
    assert delay >= 2.0


# ---------- IntentParser ----------

MOCK_INTENT_LLM_RESPONSE = {
    "keywords_en": ["markdown", "notes", "browser extension"],
    "exact_entities": ["Browser Extension"],
    "comparison_anchors": ["Notion Web Clipper"],
    "search_goal": "find_direct_competitors",
    "keywords_zh": ["Markdown 笔记", "浏览器插件"],
    "output_language": "zh",
    "app_type": "browser-extension",
    "target_scenario": "Take markdown notes while browsing web pages",
    "search_queries": [
        {
            "platform": "github",
            "queries": ["markdown notes browser extension stars:>50"],
        },
        {
            "platform": "tavily",
            "queries": ["markdown notes chrome extension competitor"],
        },
        {"platform": "hackernews", "queries": ["Show HN markdown notes extension"]},
        {
            "platform": "appstore",
            "queries": ["ios markdown notes app competitor"],
        },
        {
            "platform": "producthunt",
            "queries": ["product hunt markdown notes new launch"],
        },
    ],
}


@pytest.mark.asyncio
async def test_intent_parser_returns_intent() -> None:
    llm = MagicMock(spec=ChatModelClient)
    llm.invoke_json_with_meta = AsyncMock(return_value=(MOCK_INTENT_LLM_RESPONSE, {}))

    parser = IntentParser(llm)
    intent = await parser.parse("我想做一个给网页内容做Markdown笔记的浏览器插件")

    assert "markdown" in intent.keywords_en
    assert intent.app_type == "browser-extension"
    assert intent.output_language == "zh"
    assert intent.exact_entities == ["Browser Extension"]
    assert intent.comparison_anchors == ["Notion Web Clipper"]
    assert intent.search_goal == "find_direct_competitors"
    assert len(intent.search_queries) == 5
    assert len(intent.cache_key) == 16


@pytest.mark.asyncio
async def test_intent_parser_error_and_metrics_paths() -> None:
    llm = MagicMock(spec=ChatModelClient)
    llm.invoke_json_with_meta = AsyncMock(side_effect=IntentParsingError("bad prompt"))
    parser = IntentParser(llm)

    with pytest.raises(IntentParsingError):
        await parser.parse("bad query")

    parser._store_metrics_for_current_task({"llm_calls": 1})
    assert parser.pop_llm_metrics_for_current_task() == {"llm_calls": 1}
    assert parser.pop_llm_metrics_for_current_task() == {}


@pytest.mark.asyncio
async def test_intent_parser_normalizes_search_goal_and_backfills_anchor_keywords() -> (
    None
):
    llm = MagicMock(spec=ChatModelClient)
    llm.invoke_json_with_meta = AsyncMock(
        return_value=(
            {
                "keywords_en": ["visual editor", "AI coding assistant"],
                "keywords_zh": ["可视化编辑器"],
                "exact_entities": [" Claude Code ", "claude code"],
                "comparison_anchors": [" Cursor ", "cursor"],
                "search_goal": "something_unknown",
                "app_type": "web",
                "target_scenario": "为 Claude Code 提供可视化界面",
                "output_language": "zh",
            },
            {},
        )
    )

    parser = IntentParser(llm)
    intent = await parser.parse("我想开发一个 Claude Code 的可视化编辑器")

    assert intent.search_goal == "find_direct_competitors"
    assert intent.exact_entities == ["Claude Code"]
    assert intent.comparison_anchors == ["Cursor"]
    assert any(keyword.lower() == "claude code" for keyword in intent.keywords_en)


@pytest.mark.asyncio
async def test_query_planner_prefers_llm_output_and_returns_typed_plan() -> None:
    llm = MagicMock(spec=ChatModelClient)
    llm.invoke_json_with_meta = AsyncMock(
        return_value=(
            {
                "query_groups": [
                    {
                        "family": "direct_competitor",
                        "anchor_terms": ["Claude Code"],
                        "comparison_anchors": ["Cursor"],
                        "rewritten_queries": [
                            {
                                "query": '"Claude Code" gui',
                                "family": "direct_competitor",
                                "purpose": "Find direct GUI wrappers.",
                            }
                        ],
                    }
                ]
            },
            {"llm_calls": 1},
        )
    )
    planner = QueryPlanner(llm)
    intent = Intent(
        keywords_en=["visual editor"],
        app_type="web",
        target_scenario="为 Claude Code 提供可视化界面",
        output_language="zh",
        exact_entities=["Claude Code"],
        comparison_anchors=["Cursor"],
        cache_key="plan-intent",
    )

    plan = await planner.plan(intent)

    assert isinstance(plan, QueryPlan)
    assert plan.query_groups[0].family == QueryFamily.DIRECT_COMPETITOR
    assert plan.query_groups[0].anchor_terms == ["Claude Code"]
    assert plan.query_groups[0].rewritten_queries[0].query == '"Claude Code" gui'


@pytest.mark.asyncio
async def test_query_planner_falls_back_to_rule_planner_on_invalid_payload() -> None:
    llm = MagicMock(spec=ChatModelClient)
    llm.invoke_json_with_meta = AsyncMock(return_value=({"bad": "payload"}, {}))
    planner = QueryPlanner(llm)
    intent = Intent(
        keywords_en=["visual editor", "agent IDE"],
        app_type="web",
        target_scenario="为 Claude Code 提供可视化界面",
        output_language="zh",
        exact_entities=["Claude Code"],
        comparison_anchors=["Cursor"],
        cache_key="plan-intent",
    )

    plan = await planner.plan(intent)

    assert plan.query_groups
    assert any(
        group.family == QueryFamily.DIRECT_COMPETITOR for group in plan.query_groups
    )


# ---------- Extractor ----------

MOCK_EXTRACTOR_LLM_RESPONSE = {
    "competitors": [
        {
            "name": "markdown-clipper",
            "links": ["https://github.com/user/markdown-clipper"],
            "one_liner": "Clip web pages as Markdown",
            "features": ["one-click clip", "custom templates"],
            "pricing": "Open Source",
            "strengths": ["large community", "well documented"],
            "weaknesses": ["no mobile support"],
            "relevance_score": 0.85,
            "source_platforms": ["github"],
            "source_urls": ["https://github.com/user/markdown-clipper"],
        },
        {
            "name": "invalid-no-links",
            "links": [],
            "one_liner": "should be filtered out",
            "source_platforms": ["github"],
            "source_urls": [],
        },
    ]
}


@pytest.mark.asyncio
async def test_extractor_extracts_valid_competitors() -> None:
    llm = MagicMock(spec=ChatModelClient)
    llm.invoke_json_with_meta = AsyncMock(
        return_value=(MOCK_EXTRACTOR_LLM_RESPONSE, {})
    )

    extractor = Extractor(llm)
    raw = [
        RawResult(
            title="markdown-clipper",
            url="https://github.com/user/markdown-clipper",
            platform=Platform.GITHUB,
        )
    ]
    result = await extractor.extract(raw, _TEST_INTENT)
    # Only the valid one passes (the invalid one with empty links is filtered)
    assert len(result) == 1
    assert result[0].name == "markdown-clipper"


@pytest.mark.asyncio
async def test_extractor_filters_unverifiable_links() -> None:
    llm = MagicMock(spec=ChatModelClient)
    llm.invoke_json_with_meta = AsyncMock(
        return_value=(
            {
                "competitors": [
                    {
                        "name": "MixedLinks",
                        "links": [
                            "https://github.com/user/markdown-clipper",
                            "https://fake-site.example/fabricated",
                        ],
                        "one_liner": "Contains one valid and one fabricated link",
                        "source_platforms": ["github"],
                        "source_urls": [
                            "https://github.com/user/markdown-clipper",
                            "https://fake-site.example/fabricated",
                        ],
                    },
                    {
                        "name": "AllFake",
                        "links": ["https://fake-site.example/only-fake"],
                        "one_liner": "Should be removed",
                        "source_platforms": ["github"],
                        "source_urls": ["https://fake-site.example/only-fake"],
                    },
                ]
            },
            {},
        )
    )

    extractor = Extractor(llm)
    raw = [
        RawResult(
            title="markdown-clipper",
            url="https://github.com/user/markdown-clipper/",
            platform=Platform.GITHUB,
        )
    ]
    result = await extractor.extract(raw, _TEST_INTENT)

    assert len(result) == 1
    assert result[0].name == "MixedLinks"
    assert result[0].links == ["https://github.com/user/markdown-clipper"]
    assert result[0].source_urls == ["https://github.com/user/markdown-clipper"]


@pytest.mark.asyncio
async def test_extractor_backfills_strengths_and_weaknesses_when_missing() -> None:
    llm = MagicMock(spec=ChatModelClient)
    llm.invoke_json_with_meta = AsyncMock(
        return_value=(
            {
                "competitors": [
                    {
                        "name": "ops-monitor",
                        "links": ["https://example.com/ops-monitor"],
                        "one_liner": "Monitor line throughput and alert on bottlenecks.",
                        "features": ["throughput dashboard", "alerting", "line status"],
                        "pricing": "Contact sales",
                        "relevance_score": 0.84,
                        "source_platforms": ["tavily"],
                        "source_urls": ["https://example.com/ops-monitor"],
                    }
                ]
            },
            {},
        )
    )

    extractor = Extractor(llm)
    raw = [
        RawResult(
            title="ops-monitor",
            url="https://example.com/ops-monitor",
            platform=Platform.TAVILY,
        )
    ]

    result = await extractor.extract(raw, _TEST_INTENT)

    assert len(result) == 1
    assert result[0].strengths
    assert result[0].weaknesses
    assert any(
        "throughput" in item.lower() or "dashboard" in item.lower()
        for item in result[0].strengths
    )
    assert any(
        "single source" in item.lower() or "pricing" in item.lower()
        for item in result[0].weaknesses
    )


@pytest.mark.asyncio
async def test_extractor_empty_input_returns_empty() -> None:
    llm = MagicMock(spec=ChatModelClient)
    extractor = Extractor(llm)
    result = await extractor.extract([], _TEST_INTENT)
    assert result == []
    llm.invoke_json.assert_not_called()


@pytest.mark.asyncio
async def test_extractor_uses_appstore_prompt_and_meta_payload() -> None:
    llm = MagicMock(spec=ChatModelClient)
    llm.invoke_json_with_meta = AsyncMock(return_value=({"competitors": []}, {}))
    llm.invoke_json = AsyncMock(return_value={"competitors": []})

    extractor = Extractor(llm)
    raw = [
        RawResult(
            title="Focus Notes",
            description="Capture quick notes and tasks with AI assistance.",
            url="https://apps.apple.com/us/app/focus-notes/id1001?uo=4",
            platform=Platform.APPSTORE,
            raw_data={
                "track_id": 1001,
                "bundle_id": "com.example.focusnotes",
                "seller_name": "Example Inc",
                "primary_genre_name": "Productivity",
                "rating": 4.8,
                "rating_count": 9021,
                "price_numeric": 0.0,
                "price_label": "Free",
                "currency": "USD",
                "version": "2.3.1",
                "release_date_iso": "2025-12-01",
                "canonical_track_url": "https://apps.apple.com/us/app/focus-notes/id1001",
            },
        )
    ]
    focus_intent = Intent(
        keywords_en=["focus", "notes"],
        app_type="mobile",
        target_scenario="Focus notes app",
        output_language="en",
        cache_key="focus-key",
    )
    await extractor.extract(raw, focus_intent)

    call_kwargs = llm.invoke_json_with_meta.await_args.kwargs
    prompt = call_kwargs["prompt"]
    assert "focused on App Store products" in prompt
    assert "Output language: en" in prompt
    assert "appstore_meta" in prompt
    assert "Capture quick notes and tasks with AI assistance." in prompt
    assert '"price_label": "Free"' in prompt
    assert (
        '"canonical_track_url": "https://apps.apple.com/us/app/focus-notes/id1001"'
        in prompt
    )


@pytest.mark.asyncio
async def test_extractor_non_appstore_payload_unchanged() -> None:
    llm = MagicMock(spec=ChatModelClient)
    llm.invoke_json_with_meta = AsyncMock(return_value=({"competitors": []}, {}))
    llm.invoke_json = AsyncMock(return_value={"competitors": []})

    extractor = Extractor(llm)
    raw = [
        RawResult(
            title="markdown-clipper",
            description="Clip web pages as Markdown",
            url="https://github.com/user/markdown-clipper",
            platform=Platform.GITHUB,
            raw_data={"stargazers_count": 1200},
        )
    ]
    await extractor.extract(raw, _TEST_INTENT)

    call_kwargs = llm.invoke_json_with_meta.await_args.kwargs
    prompt = call_kwargs["prompt"]
    assert "Source platform: github" in prompt
    assert "Output language: en" in prompt
    assert "appstore_meta" not in prompt
    assert "stargazers_count" not in prompt


@pytest.mark.asyncio
async def test_extractor_normalizes_nullable_evidence_fields() -> None:
    llm = MagicMock(spec=ChatModelClient)
    llm.invoke_json_with_meta = AsyncMock(
        return_value=(
            {
                "competitors": [],
                "evidence_items": [
                    {
                        "title": "Claude Code article",
                        "url": "https://example.com/claude-code",
                        "platform": "tavily",
                        "snippet": "Mentions integrated editor workflows.",
                        "category": "market",
                        "freshness_hint": None,
                        "matched_query": "Claude Code 编辑器体验",
                        "query_family": "competitor_discovery",
                    }
                ],
            },
            {},
        )
    )

    extractor = Extractor(llm)
    raw = [
        RawResult(
            title="Claude Code article",
            url="https://example.com/claude-code",
            platform=Platform.TAVILY,
        )
    ]

    structured = await extractor.extract_structured(raw, _TEST_INTENT)

    assert len(structured.evidence_items) == 1
    assert structured.evidence_items[0].freshness_hint == ""


# ---------- Aggregator ----------

MOCK_AGGREGATOR_LLM_RESPONSE = {
    "competitors": [
        {
            "name": "Markdownify",
            "links": ["https://markdownify.app", "https://github.com/user/markdownify"],
            "one_liner": "Best markdown clipper",
            "features": ["one-click", "templates"],
            "pricing": "Free",
            "strengths": ["popular"],
            "weaknesses": ["slow"],
            "relevance_score": 0.9,
            "source_platforms": ["github", "tavily"],
            "source_urls": [
                "https://github.com/user/markdownify",
                "https://markdownify.app",
            ],
        }
    ],
    "market_summary": "The markdown clipper space has several players...",
    "recommendation_type": "caution",
    "go_no_go": "Go with caution — the space is moderately crowded.",
    "differentiation_angles": ["Mobile support", "AI summarization", "Offline mode"],
}


@pytest.mark.asyncio
async def test_aggregator_analyzes_without_modifying_competitors() -> None:
    llm = MagicMock(spec=ChatModelClient)
    llm.invoke_json_with_meta = AsyncMock(
        return_value=(MOCK_AGGREGATOR_LLM_RESPONSE, {})
    )

    agg = Aggregator(llm)
    competitors = [
        Competitor(
            name="Markdownify",
            links=["https://markdownify.app"],
            one_liner="markdown clipper",
            source_platforms=[Platform.TAVILY],
            source_urls=["https://markdownify.app"],
        ),
        Competitor(
            name="markdownify",
            links=["https://github.com/user/markdownify"],
            one_liner="markdown clipper open source",
            source_platforms=[Platform.GITHUB],
            source_urls=["https://github.com/user/markdownify"],
        ),
    ]
    result = await agg.analyze(
        competitors,
        "markdown notes extension",
        output_language="en",
    )
    assert isinstance(result, AggregationResult)
    assert len(result.competitors) == 2
    assert "crowded" in result.go_no_go.lower() or "caution" in result.go_no_go.lower()
    assert len(result.differentiation_angles) == 3
    from ideago.models.research import RecommendationType

    assert result.recommendation_type == RecommendationType.CAUTION


@pytest.mark.asyncio
async def test_aggregator_empty_competitors() -> None:
    llm = MagicMock(spec=ChatModelClient)
    agg = Aggregator(llm)
    result = await agg.aggregate([], "test", output_language="zh")
    assert result.competitors == []
    assert "竞品" in result.market_summary
    assert "探索" in result.go_no_go
    llm.invoke_json.assert_not_called()


@pytest.mark.asyncio
async def test_aggregator_error_and_metrics_paths() -> None:
    llm = MagicMock(spec=ChatModelClient)
    llm.invoke_json_with_meta = AsyncMock(side_effect=RuntimeError("boom"))
    agg = Aggregator(llm)

    competitor = Competitor(
        name="One",
        links=["https://example.com"],
        one_liner="one",
        source_platforms=[Platform.TAVILY],
        source_urls=["https://example.com"],
    )

    with pytest.raises(AggregationError):
        await agg.analyze([competitor], "query", output_language="en")

    agg._store_metrics_for_current_task({"llm_calls": 2})
    assert agg.pop_llm_metrics_for_current_task() == {"llm_calls": 2}
    assert agg.pop_llm_metrics_for_current_task() == {}


def test_aggregator_infers_recommendation_type_fallback() -> None:
    from ideago.models.research import RecommendationType
    from ideago.pipeline.aggregator import _infer_recommendation_type

    assert _infer_recommendation_type("No-go for now") == RecommendationType.NO_GO
    assert (
        _infer_recommendation_type("Proceed with caution") == RecommendationType.CAUTION
    )
    assert _infer_recommendation_type("Go build it") == RecommendationType.GO


def test_fuse_competitors_merges_cross_source_duplicates() -> None:
    fused = merge_competitors(
        [
            Competitor(
                name="Markdownify",
                links=["https://markdownify.app"],
                one_liner="Web markdown clipper",
                source_platforms=[Platform.TAVILY],
                source_urls=["https://markdownify.app"],
                features=["templates"],
                strengths=["fast"],
                relevance_score=0.7,
            ),
            Competitor(
                name="markdownify",
                links=["https://www.markdownify.app/"],
                one_liner="Clip pages to markdown quickly",
                source_platforms=[Platform.GITHUB],
                source_urls=["https://github.com/user/markdownify"],
                features=["sync"],
                weaknesses=["limited mobile"],
                relevance_score=0.85,
            ),
        ]
    )

    assert len(fused) == 1
    merged = fused[0]
    assert merged.relevance_score == 0.9
    assert set(merged.source_platforms) == {Platform.TAVILY, Platform.GITHUB}
    assert "templates" in merged.features
    assert "sync" in merged.features
