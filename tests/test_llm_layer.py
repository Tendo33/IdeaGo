"""Tests for LLM client, prompt loader, intent parser, extractor, aggregator."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from ideago.llm.chat_model import ChatModelClient
from ideago.llm.prompt_loader import load_prompt
from ideago.models.research import Competitor, Intent, Platform, RawResult
from ideago.pipeline.aggregator import AggregationResult, Aggregator
from ideago.pipeline.extractor import Extractor
from ideago.pipeline.intent_parser import IntentParser
from ideago.pipeline.merger import merge_competitors

_TEST_INTENT = Intent(
    keywords_en=["markdown", "notes"],
    app_type="browser-extension",
    target_scenario="Take markdown notes",
    cache_key="test-key",
)

# ---------- prompt_loader ----------


def test_load_prompt_intent_parser() -> None:
    prompt = load_prompt("intent_parser", query="I want to build a markdown clipper")
    assert "markdown clipper" in prompt
    assert "keywords_en" in prompt
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
    )
    assert "github" in prompt
    assert "markdown, notes" in prompt
    assert "{platform}" not in prompt


def test_load_prompt_extractor_appstore() -> None:
    prompt = load_prompt(
        "extractor_appstore",
        platform="appstore",
        raw_results_json="[]",
        query_context="test",
    )
    assert "App Store products" in prompt
    assert "{platform}" not in prompt


def test_load_prompt_aggregator() -> None:
    prompt = load_prompt(
        "aggregator",
        competitors_json="[]",
        original_query="test idea",
    )
    assert "test idea" in prompt


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

    metadata = client.pop_last_call_metadata()
    assert metadata["llm_calls"] == 2
    assert metadata["llm_retries"] == 1
    assert metadata["fallback_used"] is True
    assert metadata["endpoints_tried"] == ["primary", "fallback-1"]
    assert metadata["last_error_class"] == "auth_error"


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
async def test_chat_model_client_json_parse_retry_exhausted_keeps_metadata() -> None:
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

    metadata = client.pop_last_call_metadata()
    assert metadata["llm_calls"] == 2
    assert metadata["llm_retries"] == 1
    assert metadata["fallback_used"] is False
    assert metadata["endpoints_tried"] == ["primary"]
    assert metadata["last_error_class"] == "json_parse_error"


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


# ---------- IntentParser ----------

MOCK_INTENT_LLM_RESPONSE = {
    "keywords_en": ["markdown", "notes", "browser extension"],
    "keywords_zh": ["Markdown 笔记", "浏览器插件"],
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
    llm.invoke_json = AsyncMock(return_value=MOCK_INTENT_LLM_RESPONSE)

    parser = IntentParser(llm)
    intent = await parser.parse("我想做一个给网页内容做Markdown笔记的浏览器插件")

    assert "markdown" in intent.keywords_en
    assert intent.app_type == "browser-extension"
    assert len(intent.search_queries) == 5
    assert len(intent.cache_key) == 16


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
    llm.invoke_json = AsyncMock(return_value=MOCK_EXTRACTOR_LLM_RESPONSE)

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
    llm.invoke_json = AsyncMock(
        return_value={
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
        }
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
        cache_key="focus-key",
    )
    await extractor.extract(raw, focus_intent)

    call_kwargs = llm.invoke_json_with_meta.await_args.kwargs
    prompt = call_kwargs["prompt"]
    assert "focused on App Store products" in prompt
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
    assert "appstore_meta" not in prompt
    assert "stargazers_count" not in prompt


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
    llm.invoke_json = AsyncMock(return_value=MOCK_AGGREGATOR_LLM_RESPONSE)

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
    result = await agg.analyze(competitors, "markdown notes extension")
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
    result = await agg.aggregate([], "test")
    assert result.competitors == []
    assert (
        "no competitors" in result.market_summary.lower()
        or "unexplored" in result.go_no_go.lower()
    )
    llm.invoke_json.assert_not_called()


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
