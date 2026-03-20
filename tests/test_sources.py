"""Tests for data source plugins and registry."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from ideago.models.research import Platform, RawResult
from ideago.sources.appstore_source import AppStoreSource
from ideago.sources.errors import SourceSearchError
from ideago.sources.github_source import GitHubSource
from ideago.sources.hackernews_source import HackerNewsSource
from ideago.sources.producthunt_source import ProductHuntSource
from ideago.sources.reddit_source import RedditSource
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

MOCK_APPSTORE_RESPONSE = {
    "resultCount": 2,
    "results": [
        {
            "trackId": 1001,
            "trackName": "Focus Notes",
            "description": "Capture quick notes",
            "trackViewUrl": "https://apps.apple.com/us/app/focus-notes/id1001?uo=4",
            "bundleId": "com.example.focusnotes",
            "sellerName": "Example Inc",
            "primaryGenreName": "Productivity",
            "averageUserRating": 4.8,
            "userRatingCount": 9021,
            "price": 0.0,
            "formattedPrice": "Free",
            "currency": "USD",
            "version": "2.3.1",
            "releaseDate": "2025-12-01T00:00:00Z",
        },
        {
            "trackId": 1002,
            "trackName": "Idea Scanner",
            "description": "",
            "trackViewUrl": "https://apps.apple.com/us/app/idea-scanner/id1002",
            "bundleId": "com.example.ideascanner",
            "sellerName": "Example Labs",
            "primaryGenreName": "Business",
            "averageUserRating": 4.4,
            "userRatingCount": 1200,
            "price": 2.99,
            "formattedPrice": "$2.99",
            "currency": "USD",
            "version": "1.8.0",
            "releaseDate": "2025-10-15T00:00:00Z",
        },
    ],
}

MOCK_PRODUCTHUNT_TOPICS_RESPONSE = {
    "data": {
        "topics": {
            "nodes": [
                {
                    "name": "Developer Tools",
                    "slug": "developer-tools",
                    "postsCount": 100,
                    "url": "https://www.producthunt.com/topics/developer-tools",
                },
                {
                    "name": "Productivity",
                    "slug": "productivity",
                    "postsCount": 100,
                    "url": "https://www.producthunt.com/topics/productivity",
                },
            ]
        }
    }
}

MOCK_PRODUCTHUNT_POSTS_RESPONSE = {
    "data": {
        "posts": {
            "nodes": [
                {
                    "id": "post-1",
                    "name": "Markdown Rocket",
                    "tagline": "Convert html to markdown in seconds",
                    "votesCount": 320,
                    "createdAt": "2026-01-10T00:00:00Z",
                    "url": "https://www.producthunt.com/posts/markdown-rocket",
                    "website": "https://markdown-rocket.example.com",
                },
                {
                    "id": "post-2",
                    "name": "Writer Helper",
                    "tagline": "AI writing helper for docs",
                    "votesCount": 120,
                    "createdAt": "2025-10-10T00:00:00Z",
                    "url": "https://www.producthunt.com/posts/writer-helper",
                    "website": "https://writer-helper.example.com",
                },
            ],
            "pageInfo": {"hasNextPage": False, "endCursor": None},
        }
    }
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
    with (
        patch.object(
            src._client, "get", new_callable=AsyncMock, return_value=mock_response
        ),
        pytest.raises(SourceSearchError),
    ):
        await src.search(["test"], limit=5)


@pytest.mark.asyncio
async def test_github_search_deduplicates_across_queries() -> None:
    src = GitHubSource(token="")
    mock_response = httpx.Response(200, json=MOCK_GITHUB_RESPONSE)
    with patch.object(
        src._client, "get", new_callable=AsyncMock, return_value=mock_response
    ):
        results = await src.search(["query1", "query2"], limit=10)
    assert len(results) == 2


@pytest.mark.asyncio
async def test_github_search_strips_ranking_qualifiers_but_keeps_topic() -> None:
    src = GitHubSource(token="")
    mock_response = httpx.Response(200, json={"items": []})
    with patch.object(src._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        await src.search(
            ["real-time api monitoring stars:>50 language:python"], limit=5
        )

    called_params = mock_get.await_args.kwargs["params"]
    assert called_params["q"] == "real-time api monitoring"


@pytest.mark.asyncio
async def test_github_search_preserves_topic_qualifier() -> None:
    src = GitHubSource(token="")
    mock_response = httpx.Response(200, json={"items": []})
    with patch.object(src._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        await src.search(["topic:markdown topic:notes"], limit=5)

    called_params = mock_get.await_args.kwargs["params"]
    assert "topic:markdown" in called_params["q"]
    assert "topic:notes" in called_params["q"]


@pytest.mark.asyncio
async def test_github_search_respects_query_concurrency_limit() -> None:
    src = GitHubSource(token="", max_concurrent_queries=2)
    in_flight = 0
    max_in_flight = 0
    lock = asyncio.Lock()

    async def fake_get(*_args, **_kwargs):
        nonlocal in_flight, max_in_flight
        async with lock:
            in_flight += 1
            max_in_flight = max(max_in_flight, in_flight)
        await asyncio.sleep(0.02)
        async with lock:
            in_flight -= 1
        return httpx.Response(200, json={"items": []})

    with patch.object(src._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = fake_get
        await src.search(["q1", "q2", "q3", "q4"], limit=5)

    assert max_in_flight == 2


@pytest.mark.asyncio
async def test_github_search_partial_failure_returns_partial_results() -> None:
    src = GitHubSource(token="")

    async def fake_get(*_args, **kwargs):
        query = kwargs["params"]["q"]
        if query == "bad":
            raise httpx.ReadTimeout("timeout")
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "full_name": f"user/{query}",
                        "description": "ok",
                        "html_url": f"https://github.com/user/{query}",
                        "stargazers_count": 1,
                        "language": "Python",
                        "topics": [],
                        "forks_count": 0,
                        "updated_at": "2026-01-01T00:00:00Z",
                    }
                ]
            },
        )

    with patch.object(src._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = fake_get
        results = await src.search(["good", "bad"], limit=5)

    assert len(results) == 1
    diagnostics = src.consume_last_search_diagnostics()
    assert diagnostics["partial_failure"] is True
    assert diagnostics["failed_queries"] == ["bad"]


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


def test_tavily_client_receives_base_url() -> None:
    with patch("ideago.sources.tavily_source.AsyncTavilyClient") as mock_client:
        TavilySource(api_key="tvly-test", base_url="https://tavily.local")
    mock_client.assert_called_once_with(
        api_key="tvly-test", api_base_url="https://tavily.local"
    )


def test_tavily_client_uses_default_when_base_url_empty() -> None:
    with patch("ideago.sources.tavily_source.AsyncTavilyClient") as mock_client:
        TavilySource(api_key="tvly-test", base_url="")
    mock_client.assert_called_once_with(api_key="tvly-test")


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
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(
                src.search(["slow tavily query"], limit=5),
                timeout=0.2,
            )


@pytest.mark.asyncio
async def test_tavily_search_respects_query_concurrency_limit() -> None:
    src = TavilySource(api_key="tvly-test", max_concurrent_queries=2)
    in_flight = 0
    max_in_flight = 0
    lock = asyncio.Lock()

    async def fake_search(**_kwargs):
        nonlocal in_flight, max_in_flight
        async with lock:
            in_flight += 1
            max_in_flight = max(max_in_flight, in_flight)
        await asyncio.sleep(0.02)
        async with lock:
            in_flight -= 1
        return {"results": []}

    with patch.object(src._client, "search", new_callable=AsyncMock) as mock_search:
        mock_search.side_effect = fake_search
        await src.search(["q1", "q2", "q3", "q4"], limit=5)

    assert max_in_flight == 2


@pytest.mark.asyncio
async def test_tavily_search_partial_failure_returns_partial_results() -> None:
    src = TavilySource(api_key="tvly-test")

    async def fake_search(**kwargs):
        query = kwargs["query"]
        if query == "bad":
            raise RuntimeError("query failed")
        return {
            "results": [
                {
                    "title": f"title-{query}",
                    "url": f"https://example.com/{query}",
                    "content": "ok",
                    "score": 0.9,
                }
            ]
        }

    with patch.object(src._client, "search", new_callable=AsyncMock) as mock_search:
        mock_search.side_effect = fake_search
        results = await src.search(["good", "bad"], limit=5)

    assert len(results) == 1
    diagnostics = src.consume_last_search_diagnostics()
    assert diagnostics["partial_failure"] is True
    assert diagnostics["failed_queries"] == ["bad"]


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
async def test_hn_search_sanitizes_story_text_html_and_entities() -> None:
    src = HackerNewsSource()
    mock_response = httpx.Response(
        200,
        json={
            "hits": [
                {
                    "title": "Show HN: API monitor",
                    "url": "https://apitally.io",
                    "objectID": "abc123",
                    "points": 88,
                    "num_comments": 12,
                    "story_text": (
                        "Hi HN, I&#x27;m Simon. <p>I built "
                        '<a href="https://apitally.io">Apitally</a></p>'
                    ),
                    "author": "simon",
                }
            ]
        },
    )
    with patch.object(
        src._client, "get", new_callable=AsyncMock, return_value=mock_response
    ):
        results = await src.search(["api monitor"], limit=10)

    assert len(results) == 1
    assert results[0].description == "Hi HN, I'm Simon. I built Apitally"
    assert "<" not in results[0].description
    assert "&#x27;" not in results[0].description


@pytest.mark.asyncio
async def test_hn_search_handles_api_error() -> None:
    src = HackerNewsSource()
    mock_response = httpx.Response(500, json={})
    with (
        patch.object(
            src._client, "get", new_callable=AsyncMock, return_value=mock_response
        ),
        pytest.raises(SourceSearchError),
    ):
        await src.search(["test"], limit=5)


@pytest.mark.asyncio
async def test_hn_search_respects_query_concurrency_limit() -> None:
    src = HackerNewsSource(max_concurrent_queries=2)
    in_flight = 0
    max_in_flight = 0
    lock = asyncio.Lock()

    async def fake_get(*_args, **_kwargs):
        nonlocal in_flight, max_in_flight
        async with lock:
            in_flight += 1
            max_in_flight = max(max_in_flight, in_flight)
        await asyncio.sleep(0.02)
        async with lock:
            in_flight -= 1
        return httpx.Response(200, json={"hits": []})

    with patch.object(src._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = fake_get
        await src.search(["q1", "q2", "q3", "q4"], limit=5)

    assert max_in_flight == 2


# ---------- AppStoreSource ----------


def test_appstore_source_platform() -> None:
    src = AppStoreSource()
    assert src.platform == Platform.APPSTORE


def test_appstore_source_is_available_without_api_key() -> None:
    src = AppStoreSource()
    assert src.is_available() is True


@pytest.mark.asyncio
async def test_appstore_search_returns_raw_results() -> None:
    src = AppStoreSource(country="us")
    mock_response = httpx.Response(200, json=MOCK_APPSTORE_RESPONSE)
    with patch.object(
        src._client, "get", new_callable=AsyncMock, return_value=mock_response
    ):
        results = await src.search(["focus notes"], limit=10)

    assert len(results) == 2
    assert results[0].platform == Platform.APPSTORE
    assert "apps.apple.com" in results[0].url
    assert results[0].raw_data["track_id"] == 1001
    assert results[0].description == "Capture quick notes"


@pytest.mark.asyncio
async def test_appstore_search_populates_structured_meta_fields() -> None:
    src = AppStoreSource(country="us")
    mock_response = httpx.Response(200, json=MOCK_APPSTORE_RESPONSE)
    with patch.object(
        src._client, "get", new_callable=AsyncMock, return_value=mock_response
    ):
        results = await src.search(["focus notes"], limit=10)

    assert len(results) == 2
    first = results[0]
    assert (
        first.raw_data["canonical_track_url"]
        == "https://apps.apple.com/us/app/focus-notes/id1001"
    )
    assert first.raw_data["rating"] == pytest.approx(4.8)
    assert first.raw_data["rating_count"] == 9021
    assert first.raw_data["price_numeric"] == pytest.approx(0.0)
    assert first.raw_data["price_label"] == "Free"
    assert first.raw_data["release_date_iso"] == "2025-12-01"


@pytest.mark.asyncio
async def test_appstore_search_deduplicates_by_track_id() -> None:
    src = AppStoreSource(country="us")
    mock_response = httpx.Response(200, json=MOCK_APPSTORE_RESPONSE)
    with patch.object(
        src._client, "get", new_callable=AsyncMock, return_value=mock_response
    ):
        results = await src.search(["query1", "query2"], limit=10)

    assert len(results) == 2


@pytest.mark.asyncio
async def test_appstore_search_handles_non_200() -> None:
    src = AppStoreSource(country="us")
    mock_response = httpx.Response(503, json={"errorMessage": "service unavailable"})
    with (
        patch.object(
            src._client, "get", new_callable=AsyncMock, return_value=mock_response
        ),
        pytest.raises(SourceSearchError),
    ):
        await src.search(["test"], limit=5)


@pytest.mark.asyncio
async def test_appstore_search_respects_query_concurrency_limit() -> None:
    src = AppStoreSource(country="us", max_concurrent_queries=2)
    in_flight = 0
    max_in_flight = 0
    lock = asyncio.Lock()

    async def fake_get(*_args, **_kwargs):
        nonlocal in_flight, max_in_flight
        async with lock:
            in_flight += 1
            max_in_flight = max(max_in_flight, in_flight)
        await asyncio.sleep(0.02)
        async with lock:
            in_flight -= 1
        return httpx.Response(200, json={"resultCount": 0, "results": []})

    with patch.object(src._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = fake_get
        await src.search(["q1", "q2", "q3", "q4"], limit=5)

    assert max_in_flight == 2


# ---------- ProductHuntSource ----------


def test_producthunt_source_platform() -> None:
    src = ProductHuntSource(dev_token="ph-token")
    assert src.platform == Platform.PRODUCT_HUNT


def test_producthunt_not_available_without_token() -> None:
    src = ProductHuntSource(dev_token="")
    assert src.is_available() is False


def test_producthunt_available_with_token() -> None:
    src = ProductHuntSource(dev_token="ph-token")
    assert src.is_available() is True


@pytest.mark.asyncio
async def test_producthunt_search_returns_raw_results() -> None:
    src = ProductHuntSource(dev_token="ph-token")
    with patch.object(src._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [
            httpx.Response(200, json=MOCK_PRODUCTHUNT_TOPICS_RESPONSE),
            httpx.Response(200, json=MOCK_PRODUCTHUNT_POSTS_RESPONSE),
            httpx.Response(200, json=MOCK_PRODUCTHUNT_POSTS_RESPONSE),
        ]
        results = await src.search(["html to markdown"], limit=10)

    assert len(results) == 1
    first = results[0]
    assert first.title == "Markdown Rocket"
    assert first.description == "Convert html to markdown in seconds"
    assert first.url == "https://www.producthunt.com/posts/markdown-rocket"
    assert first.platform == Platform.PRODUCT_HUNT
    assert first.raw_data["post_id"] == "post-1"
    assert first.raw_data["votes_count"] == 320
    assert first.raw_data["created_at"] == "2026-01-10T00:00:00Z"
    assert first.raw_data["website"] == "https://markdown-rocket.example.com"
    assert first.raw_data["topic_slug"] in {"developer-tools", "productivity"}


@pytest.mark.asyncio
async def test_producthunt_search_without_token_returns_empty() -> None:
    src = ProductHuntSource(dev_token="")
    results = await src.search(["markdown"], limit=10)
    assert results == []


@pytest.mark.asyncio
async def test_producthunt_search_handles_non_200() -> None:
    src = ProductHuntSource(dev_token="ph-token")
    with (
        patch.object(
            src._client,
            "post",
            new_callable=AsyncMock,
            return_value=httpx.Response(503, json={}),
        ),
        pytest.raises(SourceSearchError),
    ):
        await src.search(["markdown"], limit=10)


@pytest.mark.asyncio
async def test_producthunt_search_handles_graphql_errors() -> None:
    src = ProductHuntSource(dev_token="ph-token")
    graphql_error_payload = {
        "errors": [{"message": "topic query denied"}],
        "data": {"topics": {"nodes": []}},
    }
    with (
        patch.object(
            src._client,
            "post",
            new_callable=AsyncMock,
            return_value=httpx.Response(200, json=graphql_error_payload),
        ),
        pytest.raises(SourceSearchError),
    ):
        await src.search(["markdown"], limit=10)


@pytest.mark.asyncio
async def test_producthunt_search_deduplicates_posts_across_topics() -> None:
    src = ProductHuntSource(dev_token="ph-token")
    posts_payload = {
        "data": {
            "posts": {
                "nodes": [
                    {
                        "id": "post-1",
                        "name": "Markdown Rocket",
                        "tagline": "html markdown converter",
                        "votesCount": 200,
                        "createdAt": "2026-01-09T00:00:00Z",
                        "url": "https://www.producthunt.com/posts/markdown-rocket",
                        "website": "https://markdown-rocket.example.com",
                    }
                ],
                "pageInfo": {"hasNextPage": False, "endCursor": None},
            }
        }
    }
    with patch.object(src._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [
            httpx.Response(200, json=MOCK_PRODUCTHUNT_TOPICS_RESPONSE),
            httpx.Response(200, json=posts_payload),
            httpx.Response(200, json=posts_payload),
        ]
        results = await src.search(["markdown"], limit=10)

    assert len(results) == 1
    assert results[0].raw_data["post_id"] == "post-1"


@pytest.mark.asyncio
async def test_producthunt_search_handles_chinese_queries_without_zeroing() -> None:
    src = ProductHuntSource(dev_token="ph-token")
    with patch.object(src._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [
            httpx.Response(200, json=MOCK_PRODUCTHUNT_TOPICS_RESPONSE),
            httpx.Response(200, json=MOCK_PRODUCTHUNT_POSTS_RESPONSE),
            httpx.Response(200, json=MOCK_PRODUCTHUNT_POSTS_RESPONSE),
        ]
        results = await src.search(["实时接口监控告警看板"], limit=10)

    assert len(results) >= 1


@pytest.mark.asyncio
async def test_producthunt_search_falls_back_when_topics_empty() -> None:
    src = ProductHuntSource(dev_token="ph-token")
    empty_topics = {"data": {"topics": {"nodes": []}}}
    with patch.object(src._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [
            httpx.Response(200, json=empty_topics),
            httpx.Response(200, json=MOCK_PRODUCTHUNT_POSTS_RESPONSE),
            httpx.Response(200, json=MOCK_PRODUCTHUNT_POSTS_RESPONSE),
            httpx.Response(200, json=MOCK_PRODUCTHUNT_POSTS_RESPONSE),
            httpx.Response(200, json=MOCK_PRODUCTHUNT_POSTS_RESPONSE),
        ]
        results = await src.search(["markdown"], limit=10)

    assert len(results) >= 1


# ---------- RedditSource ----------

MOCK_REDDIT_RESPONSE = {
    "data": {
        "children": [
            {
                "kind": "t3",
                "data": {
                    "id": "abc123",
                    "title": "Best markdown editor alternatives?",
                    "selftext": "I'm looking for a good markdown editor. Any recommendations?",
                    "url": "https://www.reddit.com/r/software/comments/abc123/best_markdown_editor_alternatives/",
                    "permalink": "/r/software/comments/abc123/best_markdown_editor_alternatives/",
                    "subreddit": "software",
                    "score": 245,
                    "num_comments": 87,
                    "created_utc": 1706745600,
                    "upvote_ratio": 0.95,
                },
            },
            {
                "kind": "t3",
                "data": {
                    "id": "def456",
                    "title": "Recommend me a note-taking app",
                    "selftext": "",
                    "url": "https://www.reddit.com/r/productivity/comments/def456/recommend_me_a_notetaking_app/",
                    "permalink": "/r/productivity/comments/def456/recommend_me_a_notetaking_app/",
                    "subreddit": "productivity",
                    "score": 120,
                    "num_comments": 45,
                    "created_utc": 1706832000,
                    "upvote_ratio": 0.88,
                },
            },
        ]
    }
}

MOCK_TOKEN_RESPONSE = {
    "access_token": "fake-token-abc",
    "token_type": "bearer",
    "expires_in": 86400,
    "scope": "*",
}


def _make_reddit(client_id: str = "test-id", client_secret: str = "test-secret", **kw):
    return RedditSource(client_id=client_id, client_secret=client_secret, **kw)


def _patch_token(src: RedditSource):
    """Patch _ensure_token to skip real OAuth and return a fake token."""
    return patch.object(
        src, "_ensure_token", new_callable=AsyncMock, return_value="fake-token"
    )


def test_reddit_platform() -> None:
    src = _make_reddit()
    assert src.platform == Platform.REDDIT


def test_reddit_available_with_credentials() -> None:
    src = _make_reddit()
    assert src.is_available() is True


def test_reddit_not_available_without_credentials() -> None:
    src = RedditSource()
    assert src.is_available() is False
    src2 = RedditSource(client_id="id-only")
    assert src2.is_available() is False


@pytest.mark.asyncio
async def test_reddit_search_without_credentials_returns_empty() -> None:
    src = RedditSource()
    results = await src.search(["test"])
    assert results == []


@pytest.mark.asyncio
async def test_reddit_search_returns_raw_results() -> None:
    src = _make_reddit()
    mock_response = httpx.Response(200, json=MOCK_REDDIT_RESPONSE)
    with (
        _patch_token(src),
        patch.object(
            src._client, "get", new_callable=AsyncMock, return_value=mock_response
        ),
    ):
        results = await src.search(["markdown editor"], limit=10)
    assert len(results) == 2
    assert results[0].platform == Platform.REDDIT
    assert "reddit.com" in results[0].url
    assert results[0].raw_data["score"] == 245
    assert results[0].raw_data["num_comments"] == 87
    assert results[0].raw_data["subreddit"] == "software"


@pytest.mark.asyncio
async def test_reddit_search_deduplicates_across_queries() -> None:
    src = _make_reddit()
    mock_response = httpx.Response(200, json=MOCK_REDDIT_RESPONSE)
    with (
        _patch_token(src),
        patch.object(
            src._client, "get", new_callable=AsyncMock, return_value=mock_response
        ),
    ):
        results = await src.search(["query1", "query2"], limit=10)
    assert len(results) == 2


@pytest.mark.asyncio
async def test_reddit_search_handles_rate_limit() -> None:
    src = _make_reddit()
    mock_response = httpx.Response(429, json={"message": "Too Many Requests"})
    with (
        _patch_token(src),
        patch.object(
            src._client, "get", new_callable=AsyncMock, return_value=mock_response
        ),
        pytest.raises(SourceSearchError),
    ):
        await src.search(["test"], limit=5)


@pytest.mark.asyncio
async def test_reddit_search_handles_timeout() -> None:
    src = _make_reddit(timeout=1)

    async def slow_get(*_args, **_kwargs):
        raise httpx.ReadTimeout("timeout")

    with (
        _patch_token(src),
        patch.object(src._client, "get", new_callable=AsyncMock) as mock_get,
        pytest.raises(SourceSearchError),
    ):
        mock_get.side_effect = slow_get
        await src.search(["test"], limit=5)


@pytest.mark.asyncio
async def test_reddit_search_partial_failure_returns_partial_results() -> None:
    src = _make_reddit()

    async def fake_get(*_args, **kwargs):
        query = kwargs["params"]["q"]
        if query == "bad":
            raise httpx.ReadTimeout("timeout")
        return httpx.Response(
            200,
            json={
                "data": {
                    "children": [
                        {
                            "kind": "t3",
                            "data": {
                                "id": f"id-{query}",
                                "title": f"Post about {query}",
                                "selftext": "content",
                                "url": f"https://reddit.com/r/test/{query}",
                                "permalink": f"/r/test/{query}",
                                "subreddit": "test",
                                "score": 10,
                                "num_comments": 5,
                                "created_utc": 1706745600,
                                "upvote_ratio": 0.9,
                            },
                        }
                    ]
                }
            },
        )

    with (
        _patch_token(src),
        patch.object(src._client, "get", new_callable=AsyncMock) as mock_get,
    ):
        mock_get.side_effect = fake_get
        results = await src.search(["good", "bad"], limit=5)

    assert len(results) == 1
    diagnostics = src.consume_last_search_diagnostics()
    assert diagnostics["partial_failure"] is True
    assert diagnostics["failed_queries"] == ["bad"]
    assert diagnostics["timed_out_queries"] == ["bad"]


@pytest.mark.asyncio
async def test_reddit_search_sanitizes_selftext_html() -> None:
    src = _make_reddit()
    html_response = {
        "data": {
            "children": [
                {
                    "kind": "t3",
                    "data": {
                        "id": "html1",
                        "title": "Test post",
                        "selftext": 'Check out <a href="https://example.com">this &amp; that</a>',
                        "url": "https://www.reddit.com/r/test/comments/html1/test/",
                        "permalink": "/r/test/comments/html1/test/",
                        "subreddit": "test",
                        "score": 10,
                        "num_comments": 2,
                        "created_utc": 1706745600,
                        "upvote_ratio": 0.9,
                    },
                }
            ]
        }
    }
    mock_response = httpx.Response(200, json=html_response)
    with (
        _patch_token(src),
        patch.object(
            src._client, "get", new_callable=AsyncMock, return_value=mock_response
        ),
    ):
        results = await src.search(["test"], limit=10)

    assert len(results) == 1
    assert "<" not in results[0].description
    assert "&amp;" not in results[0].description
    assert "this & that" in results[0].description


@pytest.mark.asyncio
async def test_reddit_token_acquisition() -> None:
    src = _make_reddit()
    mock_token_resp = httpx.Response(200, json=MOCK_TOKEN_RESPONSE)
    with patch.object(
        src._auth_client, "post", new_callable=AsyncMock, return_value=mock_token_resp
    ):
        token = await src._ensure_token()
    assert token == "fake-token-abc"
    assert src._access_token == "fake-token-abc"


@pytest.mark.asyncio
async def test_reddit_token_reuses_valid_token() -> None:
    src = _make_reddit()
    mock_token_resp = httpx.Response(200, json=MOCK_TOKEN_RESPONSE)
    with patch.object(
        src._auth_client, "post", new_callable=AsyncMock, return_value=mock_token_resp
    ) as mock_post:
        await src._ensure_token()
        await src._ensure_token()
    mock_post.assert_awaited_once()


@pytest.mark.asyncio
async def test_reddit_token_failure_raises() -> None:
    src = _make_reddit()
    mock_token_resp = httpx.Response(401, json={"error": "invalid_grant"})
    with (
        patch.object(
            src._auth_client,
            "post",
            new_callable=AsyncMock,
            return_value=mock_token_resp,
        ),
        pytest.raises(SourceSearchError, match="OAuth token request failed"),
    ):
        await src._ensure_token()
