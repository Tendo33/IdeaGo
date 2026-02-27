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
        timeout: int = 30,
        max_concurrent_queries: int = 2,
    ) -> None:
        self._api_key = api_key
        self._timeout = timeout
        self._max_concurrent_queries = max(1, max_concurrent_queries)
        if api_key:
            self._client = AsyncTavilyClient(api_key=api_key)
        else:
            self._client = None

    @property
    def platform(self) -> Platform:
        return Platform.TAVILY

    def is_available(self) -> bool:
        return bool(self._api_key)

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

        seen_urls: set[str] = set()
        semaphore = asyncio.Semaphore(self._max_concurrent_queries)

        async def run_query(query: str) -> list[RawResult]:
            async with semaphore:
                return await self._search_single_query(query, limit)

        grouped_results = await asyncio.gather(*(run_query(query) for query in queries))
        results: list[RawResult] = []
        for query_results in grouped_results:
            for result in query_results:
                if result.url in seen_urls:
                    continue
                seen_urls.add(result.url)
                results.append(result)
        return results
