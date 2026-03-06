"""Product Hunt data source — searches posts via Product Hunt GraphQL API."""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from ideago.models.research import Platform, RawResult
from ideago.observability.log_config import get_logger
from ideago.sources.errors import SourceSearchError

logger = get_logger(__name__)

_TOPICS_QUERY = """
query Topics($q: String!, $first: Int!) {
  topics(query: $q, first: $first) {
    nodes { name slug postsCount url }
  }
}
"""

_POSTS_QUERY = """
query Posts($topic: String!, $first: Int!, $after: String, $postedAfter: DateTime) {
  posts(topic: $topic, first: $first, after: $after, postedAfter: $postedAfter) {
    nodes {
      id
      name
      tagline
      votesCount
      createdAt
      url
      website
    }
    pageInfo { hasNextPage endCursor }
  }
}
"""


class ProductHuntSource:
    """Searches Product Hunt posts with a developer token."""

    _BASE_URL = "https://api.producthunt.com"
    _GRAPHQL_PATH = "/v2/api/graphql"

    def __init__(
        self,
        dev_token: str = "",
        posted_after_days: int = 730,
        timeout: int = 30,
        max_concurrent_queries: int = 2,
    ) -> None:
        self._dev_token = dev_token.strip()
        self._posted_after_days = max(1, posted_after_days)
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self._dev_token:
            headers["Authorization"] = f"Bearer {self._dev_token}"
        self._client = httpx.AsyncClient(
            base_url=self._BASE_URL,
            headers=headers,
            timeout=timeout,
        )
        self._max_concurrent_queries = max(1, max_concurrent_queries)

    @property
    def platform(self) -> Platform:
        return Platform.PRODUCT_HUNT

    def is_available(self) -> bool:
        return bool(self._dev_token)

    async def _graphql(
        self,
        query: str,
        variables: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            resp = await self._client.post(
                self._GRAPHQL_PATH,
                json={"query": query, "variables": variables},
            )
            if resp.status_code != 200:
                logger.warning(
                    "Product Hunt API returned {status}",
                    status=resp.status_code,
                )
                raise SourceSearchError(
                    self.platform.value,
                    "Product Hunt API non-200 response",
                    status_code=resp.status_code,
                )
            payload = resp.json()
            errors = payload.get("errors")
            if errors:
                raise SourceSearchError(
                    self.platform.value,
                    f"GraphQL errors: {errors}",
                )
            data = payload.get("data")
            if isinstance(data, dict):
                return data
            return {}
        except SourceSearchError:
            raise
        except httpx.HTTPError as exc:
            logger.warning("Product Hunt request failed: {exc}", exc=exc)
            raise SourceSearchError(self.platform.value, str(exc)) from exc
        except ValueError as exc:
            raise SourceSearchError(
                self.platform.value,
                "Invalid JSON payload from Product Hunt",
            ) from exc

    async def _find_topic_slugs(self, query: str, first: int = 5) -> list[str]:
        payload = await self._graphql(_TOPICS_QUERY, {"q": query, "first": first})
        topics = payload.get("topics", {})
        if not isinstance(topics, dict):
            return []
        nodes = topics.get("nodes", [])
        if not isinstance(nodes, list):
            return []
        slugs: list[str] = []
        seen: set[str] = set()
        for node in nodes:
            if not isinstance(node, dict):
                continue
            slug = node.get("slug", "")
            if not isinstance(slug, str) or not slug:
                continue
            if slug in seen:
                continue
            seen.add(slug)
            slugs.append(slug)
        return slugs

    async def _fetch_posts_by_topic(
        self,
        topic_slug: str,
        posted_after_iso: str,
        page_size: int,
        max_pages: int,
    ) -> list[dict[str, Any]]:
        collected: list[dict[str, Any]] = []
        after: str | None = None
        for _ in range(max_pages):
            payload = await self._graphql(
                _POSTS_QUERY,
                {
                    "topic": topic_slug,
                    "first": page_size,
                    "after": after,
                    "postedAfter": posted_after_iso,
                },
            )
            posts = payload.get("posts", {})
            if not isinstance(posts, dict):
                break
            nodes = posts.get("nodes", [])
            if isinstance(nodes, list):
                for node in nodes:
                    if isinstance(node, dict):
                        enriched = dict(node)
                        enriched["topic_slug"] = topic_slug
                        collected.append(enriched)
            page_info = posts.get("pageInfo", {})
            if not isinstance(page_info, dict):
                break
            has_next_page = bool(page_info.get("hasNextPage"))
            after_value = page_info.get("endCursor")
            if not has_next_page or not isinstance(after_value, str) or not after_value:
                break
            after = after_value
        return collected

    async def search(self, queries: list[str], limit: int = 10) -> list[RawResult]:
        """Search Product Hunt and return deduplicated raw posts."""
        if not self.is_available() or not queries:
            return []

        normalized_queries = [query.strip() for query in queries if query.strip()]
        if not normalized_queries:
            return []

        unique_slugs: list[str] = []
        seen_slugs: set[str] = set()
        for query in normalized_queries:
            slugs = await self._find_topic_slugs(query=query, first=5)
            for slug in slugs:
                if slug in seen_slugs:
                    continue
                seen_slugs.add(slug)
                unique_slugs.append(slug)

        if not unique_slugs:
            return []

        posted_after = (
            datetime.now(timezone.utc) - timedelta(days=self._posted_after_days)
        ).isoformat()
        page_size = max(1, min(limit, 20))
        max_pages = 3
        semaphore = asyncio.Semaphore(self._max_concurrent_queries)

        async def fetch_slug(slug: str) -> list[dict[str, Any]]:
            async with semaphore:
                return await self._fetch_posts_by_topic(
                    topic_slug=slug,
                    posted_after_iso=posted_after,
                    page_size=page_size,
                    max_pages=max_pages,
                )

        grouped_posts = await asyncio.gather(
            *(fetch_slug(slug) for slug in unique_slugs)
        )
        query_tokens = _extract_query_tokens(normalized_queries)
        if not query_tokens:
            query_tokens = set(normalized_queries)

        candidates: dict[str, tuple[RawResult, int, int, str]] = {}
        for posts in grouped_posts:
            for post in posts:
                post_url = _safe_str(post.get("url"))
                if not post_url:
                    continue

                name = _safe_str(post.get("name"))
                tagline = _safe_str(post.get("tagline"))
                text_blob = f"{name} {tagline}".lower()
                score = sum(1 for token in query_tokens if token in text_blob)
                if score < 1:
                    continue

                votes_count = _safe_int(post.get("votesCount"))
                created_at = _safe_str(post.get("createdAt"))
                raw_result = RawResult(
                    title=name,
                    description=tagline,
                    url=post_url,
                    platform=Platform.PRODUCT_HUNT,
                    raw_data={
                        "post_id": post.get("id"),
                        "votes_count": votes_count,
                        "created_at": created_at,
                        "website": post.get("website"),
                        "topic_slug": post.get("topic_slug"),
                    },
                )
                existing = candidates.get(post_url)
                rank_tuple = (score, votes_count, created_at)
                if existing is None or rank_tuple > (
                    existing[1],
                    existing[2],
                    existing[3],
                ):
                    candidates[post_url] = (raw_result, score, votes_count, created_at)

        sorted_candidates = sorted(
            candidates.values(),
            key=lambda item: (item[1], item[2], item[3]),
            reverse=True,
        )
        upper_bound = max(1, limit) * max(1, len(normalized_queries))
        return [item[0] for item in sorted_candidates[:upper_bound]]

    async def close(self) -> None:
        await self._client.aclose()


def _extract_query_tokens(queries: list[str]) -> set[str]:
    tokens: set[str] = set()
    for query in queries:
        for token in re.findall(r"[A-Za-z0-9_+-]{2,}", query.lower()):
            tokens.add(token)
    return tokens


def _safe_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return 0
    return 0


def _safe_str(value: Any) -> str:
    if isinstance(value, str):
        return value
    return ""
