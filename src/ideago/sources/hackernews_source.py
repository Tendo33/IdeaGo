"""Hacker News data source — searches via Algolia HN API.

通过 Algolia HN API 搜索 Hacker News 讨论帖。
"""

from __future__ import annotations

import httpx
from loguru import logger

from ideago.models.research import Platform, RawResult


class HackerNewsSource:
    """Searches Hacker News stories using the free Algolia HN API."""

    _BASE_URL = "https://hn.algolia.com/api/v1"

    def __init__(self, timeout: int = 30) -> None:
        self._client = httpx.AsyncClient(
            base_url=self._BASE_URL,
            timeout=timeout,
        )

    @property
    def platform(self) -> Platform:
        return Platform.HACKERNEWS

    def is_available(self) -> bool:
        return True

    async def search(self, queries: list[str], limit: int = 10) -> list[RawResult]:
        """Search HN stories for each query and return combined results."""
        results: list[RawResult] = []
        seen_ids: set[str] = set()

        for query in queries:
            try:
                resp = await self._client.get(
                    "/search",
                    params={"query": query, "tags": "story", "hitsPerPage": limit},
                )
                if resp.status_code != 200:
                    logger.warning(
                        "HN API returned {status} for query '{query}'",
                        status=resp.status_code,
                        query=query,
                    )
                    continue

                data = resp.json()
                for hit in data.get("hits", []):
                    object_id = hit.get("objectID", "")
                    if not object_id or object_id in seen_ids:
                        continue
                    seen_ids.add(object_id)

                    url = (
                        hit.get("url")
                        or f"https://news.ycombinator.com/item?id={object_id}"
                    )
                    results.append(
                        RawResult(
                            title=hit.get("title", ""),
                            description=hit.get("story_text") or "",
                            url=url,
                            platform=Platform.HACKERNEWS,
                            raw_data={
                                "object_id": object_id,
                                "points": hit.get("points", 0),
                                "num_comments": hit.get("num_comments", 0),
                                "author": hit.get("author"),
                            },
                        )
                    )
            except httpx.HTTPError as exc:
                logger.warning(
                    "HN search failed for '{query}': {exc}", query=query, exc=exc
                )

        return results

    async def close(self) -> None:
        await self._client.aclose()
