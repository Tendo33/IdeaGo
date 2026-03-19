"""Hacker News data source — searches via Algolia HN API.

通过 Algolia HN API 搜索 Hacker News 讨论帖。
"""

from __future__ import annotations

import asyncio

import httpx

from ideago.models.research import Platform, RawResult
from ideago.observability.log_config import get_logger
from ideago.sources.errors import SourceSearchError
from ideago.utils.text_utils import decode_entities_and_strip_html

logger = get_logger(__name__)


class HackerNewsSource:
    """Searches Hacker News stories using the free Algolia HN API."""

    _BASE_URL = "https://hn.algolia.com/api/v1"

    def __init__(self, timeout: int = 30, max_concurrent_queries: int = 2) -> None:
        self._client = httpx.AsyncClient(
            base_url=self._BASE_URL,
            timeout=timeout,
        )
        self._max_concurrent_queries = max(1, max_concurrent_queries)
        self._runtime_max_concurrent_queries: int | None = None
        self._last_search_diagnostics: dict[str, object] = {
            "partial_failure": False,
            "failed_queries": [],
            "timed_out_queries": [],
        }

    @property
    def platform(self) -> Platform:
        return Platform.HACKERNEWS

    def is_available(self) -> bool:
        return True

    def set_runtime_max_concurrent_queries(self, value: int | None) -> None:
        self._runtime_max_concurrent_queries = max(1, int(value)) if value else None

    def consume_last_search_diagnostics(self) -> dict[str, object]:
        payload = self._last_search_diagnostics
        self._last_search_diagnostics = {
            "partial_failure": False,
            "failed_queries": [],
            "timed_out_queries": [],
        }
        return payload

    async def _search_single_query(self, query: str, limit: int) -> list[RawResult]:
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
                raise SourceSearchError(
                    self.platform.value,
                    "HN API non-200 response",
                    status_code=resp.status_code,
                )

            data = resp.json()
            result: list[RawResult] = []
            for hit in data.get("hits", []):
                object_id = hit.get("objectID", "")
                if not object_id:
                    continue
                url = (
                    hit.get("url")
                    or f"https://news.ycombinator.com/item?id={object_id}"
                )
                result.append(
                    RawResult(
                        title=hit.get("title", ""),
                        description=decode_entities_and_strip_html(
                            hit.get("story_text") or ""
                        ),
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
            return result
        except httpx.HTTPError as exc:
            logger.warning(
                "HN search failed for '{query}': {exc}", query=query, exc=exc
            )
            raise SourceSearchError(self.platform.value, str(exc)) from exc

    async def search(self, queries: list[str], limit: int = 10) -> list[RawResult]:
        """Search HN stories for each query and return combined results."""
        if not queries:
            return []

        self._last_search_diagnostics = {
            "partial_failure": False,
            "failed_queries": [],
            "timed_out_queries": [],
        }
        seen_ids: set[str] = set()
        max_concurrency = (
            self._runtime_max_concurrent_queries or self._max_concurrent_queries
        )
        semaphore = asyncio.Semaphore(max_concurrency)

        async def run_query(query: str) -> tuple[str, list[RawResult] | Exception]:
            async with semaphore:
                try:
                    return query, await self._search_single_query(query, limit)
                except Exception as exc:  # noqa: BLE001
                    return query, exc

        grouped_results = await asyncio.gather(
            *(run_query(query) for query in queries),
            return_exceptions=False,
        )
        results: list[RawResult] = []
        failed_queries: list[str] = []
        timed_out_queries: list[str] = []
        first_error: Exception | None = None
        for query, query_result in grouped_results:
            if isinstance(query_result, Exception):
                failed_queries.append(query)
                if first_error is None:
                    first_error = query_result
                error_cause = query_result.__cause__
                if isinstance(error_cause, httpx.TimeoutException):
                    timed_out_queries.append(query)
                logger.warning(
                    "Source query failure: platform={}, query={}, error_type={}",
                    self.platform.value,
                    query,
                    type(query_result).__name__,
                )
                continue
            query_results = query_result
            for result in query_results:
                object_id = str(result.raw_data.get("object_id", ""))
                if not object_id or object_id in seen_ids:
                    continue
                seen_ids.add(object_id)
                results.append(result)
        if failed_queries and results:
            self._last_search_diagnostics = {
                "partial_failure": True,
                "failed_queries": failed_queries,
                "timed_out_queries": timed_out_queries,
            }
            return results
        if failed_queries and first_error is not None:
            raise first_error
        return results

    async def close(self) -> None:
        await self._client.aclose()
