"""Tavily data source — web search via Tavily API.

通过 Tavily API 进行网页搜索。
"""

from __future__ import annotations

import asyncio

from tavily import AsyncTavilyClient

from ideago.models.research import Platform, RawResult
from ideago.observability.log_config import get_logger
from ideago.sources.errors import SourceSearchError

logger = get_logger(__name__)


class TavilySource:
    """Searches the web using Tavily's search API."""

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "",
        timeout: int = 30,
        max_concurrent_queries: int = 2,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._timeout = timeout
        self._max_concurrent_queries = max(1, max_concurrent_queries)
        self._runtime_max_concurrent_queries: int | None = None
        self._last_search_diagnostics: dict[str, object] = {
            "partial_failure": False,
            "failed_queries": [],
            "timed_out_queries": [],
        }
        if api_key:
            if base_url:
                self._client = AsyncTavilyClient(api_key=api_key, api_base_url=base_url)
            else:
                self._client = AsyncTavilyClient(api_key=api_key)
        else:
            self._client = None

    @property
    def platform(self) -> Platform:
        return Platform.TAVILY

    def is_available(self) -> bool:
        return bool(self._api_key)

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
        if not self._client:
            return []
        try:
            response = await asyncio.wait_for(
                self._client.search(
                    query=query,
                    max_results=limit,
                    search_depth="basic",
                ),
                timeout=self._timeout,
            )
            return [
                RawResult(
                    title=item.get("title", ""),
                    description=item.get("content", ""),
                    url=item.get("url", ""),
                    platform=Platform.TAVILY,
                    raw_data={
                        "score": item.get("score"),
                        "raw_content": item.get("raw_content"),
                    },
                )
                for item in response.get("results", [])
                if item.get("url")
            ]
        except asyncio.TimeoutError:
            logger.warning("Tavily search timed out for '{query}'", query=query)
            raise
        except Exception as exc:
            logger.warning(
                "Tavily search failed for '{query}': {exc}", query=query, exc=exc
            )
            raise SourceSearchError(self.platform.value, str(exc)) from exc

    async def search(self, queries: list[str], limit: int = 10) -> list[RawResult]:
        """Search web for each query and return combined results."""
        if not self._client or not queries:
            return []

        self._last_search_diagnostics = {
            "partial_failure": False,
            "failed_queries": [],
            "timed_out_queries": [],
        }
        seen_urls: set[str] = set()
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
                if isinstance(query_result, asyncio.TimeoutError):
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
                if result.url in seen_urls:
                    continue
                seen_urls.add(result.url)
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
