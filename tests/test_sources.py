"""Tests for data source plugins and registry."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from ideago.models.research import Platform, RawResult
from ideago.sources.github_source import GitHubSource
from ideago.sources.hackernews_source import HackerNewsSource
from ideago.sources.registry import SourceRegistry
from ideago.sources.tavily_source import TavilySource

# ---------- SourceRegistry ----------

MOCK_GITHUB_RESPONSE = {
    "total_count": 2,
    "items": [
        {
            "full_name": "user/markdown-clipper",
            "description": "Clip web pages as Markdown",
            "html_url": "https://github.com/user/markdown-clipper",
            "stargazers_count": 1200,
            "language": "TypeScript",
            "topics": ["markdown", "browser-extension"],
            "forks_count": 50,
            "updated_at": "2026-01-01T00:00:00Z",
        },
        {
            "full_name": "user2/web-to-md",
            "description": "Convert web to markdown",
            "html_url": "https://github.com/user2/web-to-md",
            "stargazers_count": 300,
            "language": "JavaScript",
            "topics": [],
            "forks_count": 10,
            "updated_at": "2025-12-01T00:00:00Z",
        },
    ],
}

MOCK_HN_RESPONSE = {
    "hits": [
        {
            "title": "Show HN: I built a Markdown web clipper",
            "url": "https://example.com/clipper",
            "objectID": "12345",
            "points": 150,
            "num_comments": 42,
            "story_text": "",
            "author": "user1",
        },
        {
            "title": "Ask HN: Best tools for web clipping?",
            "url": "",
            "objectID": "67890",
            "points": 80,
            "num_comments": 65,
            "story_text": "Looking for recommendations...",
            "author": "user2",
        },
    ]
}


class FakeSource:
    platform = Platform.GITHUB

    def is_available(self) -> bool:
        return True

    async def search(self, queries: list[str], limit: int = 10) -> list[RawResult]:
        return []


class UnavailableSource:
    platform = Platform.TAVILY

    def is_available(self) -> bool:
        return False

    async def search(self, queries: list[str], limit: int = 10) -> list[RawResult]:
        return []


def test_register_and_get_source() -> None:
    reg = SourceRegistry()
    src = FakeSource()
    reg.register(src)
    assert reg.get(Platform.GITHUB) is src


def test_get_available_sources_filters_unavailable() -> None:
    reg = SourceRegistry()
    reg.register(FakeSource())
    reg.register(UnavailableSource())
    available = reg.get_available()
    assert len(available) == 1
    assert available[0].platform == Platform.GITHUB


def test_register_duplicate_raises() -> None:
    reg = SourceRegistry()
    reg.register(FakeSource())
    with pytest.raises(ValueError, match="already registered"):
        reg.register(FakeSource())


def test_get_nonexistent_returns_none() -> None:
    reg = SourceRegistry()
    assert reg.get(Platform.HACKERNEWS) is None


def test_get_all_returns_everything() -> None:
    reg = SourceRegistry()
    reg.register(FakeSource())
    reg.register(UnavailableSource())
    assert len(reg.get_all()) == 2


# ---------- GitHubSource ----------


def test_github_source_platform() -> None:
    src = GitHubSource(token="")
    assert src.platform == Platform.GITHUB


def test_github_is_always_available() -> None:
    src = GitHubSource(token="")
    assert src.is_available() is True


@pytest.mark.asyncio
async def test_github_search_returns_raw_results() -> None:
    src = GitHubSource(token="test-token")
    mock_response = httpx.Response(200, json=MOCK_GITHUB_RESPONSE)
    with patch.object(
        src._client, "get", new_callable=AsyncMock, return_value=mock_response
    ):
        results = await src.search(["markdown notes extension"], limit=10)
    assert len(results) == 2
    assert results[0].platform == Platform.GITHUB
    assert "github.com" in results[0].url
    assert results[0].raw_data["stargazers_count"] == 1200


@pytest.mark.asyncio
async def test_github_search_handles_api_error() -> None:
    src = GitHubSource(token="")
    mock_response = httpx.Response(403, json={"message": "rate limit"})
    with patch.object(
        src._client, "get", new_callable=AsyncMock, return_value=mock_response
    ):
        results = await src.search(["test"], limit=5)
    assert results == []


@pytest.mark.asyncio
async def test_github_search_deduplicates_across_queries() -> None:
    src = GitHubSource(token="")
    mock_response = httpx.Response(200, json=MOCK_GITHUB_RESPONSE)
    with patch.object(
        src._client, "get", new_callable=AsyncMock, return_value=mock_response
    ):
        results = await src.search(["query1", "query2"], limit=10)
    assert len(results) == 2


# ---------- TavilySource ----------


def test_tavily_not_available_without_key() -> None:
    src = TavilySource(api_key="")
    assert src.is_available() is False


def test_tavily_available_with_key() -> None:
    src = TavilySource(api_key="tvly-test")
    assert src.is_available() is True


def test_tavily_platform() -> None:
    src = TavilySource(api_key="test")
    assert src.platform == Platform.TAVILY


@pytest.mark.asyncio
async def test_tavily_search_without_key_returns_empty() -> None:
    src = TavilySource(api_key="")
    results = await src.search(["test"])
    assert results == []


@pytest.mark.asyncio
async def test_tavily_search_returns_raw_results() -> None:
    src = TavilySource(api_key="tvly-test")
    mock_tavily_response = {
        "results": [
            {
                "title": "Markdownify - Chrome Extension",
                "url": "https://chromewebstore.google.com/detail/markdownify",
                "content": "Convert any webpage to markdown with one click...",
                "score": 0.95,
            },
            {
                "title": "Web Clipper for Notion",
                "url": "https://notion.so/web-clipper",
                "content": "Save web pages directly to Notion...",
                "score": 0.82,
            },
        ]
    }
    with patch.object(
        src._client, "search", new_callable=AsyncMock, return_value=mock_tavily_response
    ):
        results = await src.search(["markdown browser extension"], limit=10)
    assert len(results) == 2
    assert results[0].platform == Platform.TAVILY
    assert "chromewebstore" in results[0].url


@pytest.mark.asyncio
async def test_tavily_search_times_out_slow_queries() -> None:
    src = TavilySource(api_key="tvly-test", timeout=0.05)

    async def slow_search(**_kwargs):
        await asyncio.sleep(1)
        return {"results": []}

    with patch.object(src._client, "search", new_callable=AsyncMock) as mock_search:
        mock_search.side_effect = slow_search
        results = await asyncio.wait_for(
            src.search(["slow tavily query"], limit=5),
            timeout=0.2,
        )

    assert results == []


# ---------- HackerNewsSource ----------


def test_hn_platform() -> None:
    src = HackerNewsSource()
    assert src.platform == Platform.HACKERNEWS


def test_hn_always_available() -> None:
    src = HackerNewsSource()
    assert src.is_available() is True


@pytest.mark.asyncio
async def test_hn_search_returns_raw_results() -> None:
    src = HackerNewsSource()
    mock_response = httpx.Response(200, json=MOCK_HN_RESPONSE)
    with patch.object(
        src._client, "get", new_callable=AsyncMock, return_value=mock_response
    ):
        results = await src.search(["markdown web clipper"], limit=10)
    assert len(results) == 2
    assert results[0].platform == Platform.HACKERNEWS
    assert "example.com" in results[0].url
    # HN posts without URL get the HN discussion URL
    assert "ycombinator" in results[1].url


@pytest.mark.asyncio
async def test_hn_search_handles_api_error() -> None:
    src = HackerNewsSource()
    mock_response = httpx.Response(500, json={})
    with patch.object(
        src._client, "get", new_callable=AsyncMock, return_value=mock_response
    ):
        results = await src.search(["test"], limit=5)
    assert results == []
