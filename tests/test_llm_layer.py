"""Tests for LLM client, prompt loader, intent parser, extractor, aggregator."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from ideago.llm.client import LLMClient
from ideago.llm.prompt_loader import load_prompt
from ideago.models.research import Competitor, Platform, RawResult
from ideago.pipeline.aggregator import AggregationResult, Aggregator
from ideago.pipeline.extractor import Extractor
from ideago.pipeline.intent_parser import IntentParser

# ---------- prompt_loader ----------


def test_load_prompt_intent_parser() -> None:
    prompt = load_prompt("intent_parser", query="I want to build a markdown clipper")
    assert "markdown clipper" in prompt
    assert "{query}" not in prompt


def test_load_prompt_extractor() -> None:
    prompt = load_prompt(
        "extractor",
        platform="github",
        raw_results_json="[]",
        query_context="test",
    )
    assert "github" in prompt
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


# ---------- LLMClient ----------


def _make_mock_openai_response(content: str) -> MagicMock:
    choice = MagicMock()
    choice.message.content = content
    response = MagicMock()
    response.choices = [choice]
    return response


@pytest.mark.asyncio
async def test_llm_client_complete_returns_text() -> None:
    client = LLMClient(api_key="sk-test", model="gpt-4o-mini")
    mock_resp = _make_mock_openai_response("Hello world")
    client._client.chat.completions.create = AsyncMock(return_value=mock_resp)

    result = await client.complete("test prompt")
    assert result == "Hello world"


@pytest.mark.asyncio
async def test_llm_client_complete_json_parses() -> None:
    client = LLMClient(api_key="sk-test", model="gpt-4o-mini")
    mock_resp = _make_mock_openai_response('{"name": "test", "score": 0.8}')
    client._client.chat.completions.create = AsyncMock(return_value=mock_resp)

    result = await client.complete_json("test prompt")
    assert result["name"] == "test"
    assert result["score"] == 0.8


@pytest.mark.asyncio
async def test_llm_client_complete_json_invalid_raises() -> None:
    client = LLMClient(api_key="sk-test", model="gpt-4o-mini")
    mock_resp = _make_mock_openai_response("not valid json {{{")
    client._client.chat.completions.create = AsyncMock(return_value=mock_resp)

    with pytest.raises(json.JSONDecodeError):
        await client.complete_json("test")


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
    ],
}


@pytest.mark.asyncio
async def test_intent_parser_returns_intent() -> None:
    llm = MagicMock(spec=LLMClient)
    llm.complete_json = AsyncMock(return_value=MOCK_INTENT_LLM_RESPONSE)

    parser = IntentParser(llm)
    intent = await parser.parse("我想做一个给网页内容做Markdown笔记的浏览器插件")

    assert "markdown" in intent.keywords_en
    assert intent.app_type == "browser-extension"
    assert len(intent.search_queries) == 3
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
    llm = MagicMock(spec=LLMClient)
    llm.complete_json = AsyncMock(return_value=MOCK_EXTRACTOR_LLM_RESPONSE)

    extractor = Extractor(llm)
    raw = [
        RawResult(
            title="markdown-clipper",
            url="https://github.com/user/markdown-clipper",
            platform=Platform.GITHUB,
        )
    ]
    result = await extractor.extract(raw, "markdown notes extension")
    # Only the valid one passes (the invalid one with empty links is filtered)
    assert len(result) == 1
    assert result[0].name == "markdown-clipper"


@pytest.mark.asyncio
async def test_extractor_empty_input_returns_empty() -> None:
    llm = MagicMock(spec=LLMClient)
    extractor = Extractor(llm)
    result = await extractor.extract([], "test")
    assert result == []
    llm.complete_json.assert_not_called()


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
    "go_no_go": "Go with caution — the space is moderately crowded.",
    "differentiation_angles": ["Mobile support", "AI summarization", "Offline mode"],
}


@pytest.mark.asyncio
async def test_aggregator_deduplicates_and_summarizes() -> None:
    llm = MagicMock(spec=LLMClient)
    llm.complete_json = AsyncMock(return_value=MOCK_AGGREGATOR_LLM_RESPONSE)

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
    result = await agg.aggregate(competitors, "markdown notes extension")
    assert isinstance(result, AggregationResult)
    assert len(result.competitors) == 1
    assert "crowded" in result.go_no_go.lower() or "caution" in result.go_no_go.lower()
    assert len(result.differentiation_angles) == 3


@pytest.mark.asyncio
async def test_aggregator_empty_competitors() -> None:
    llm = MagicMock(spec=LLMClient)
    agg = Aggregator(llm)
    result = await agg.aggregate([], "test")
    assert result.competitors == []
    assert (
        "no competitors" in result.market_summary.lower()
        or "unexplored" in result.go_no_go.lower()
    )
    llm.complete_json.assert_not_called()
