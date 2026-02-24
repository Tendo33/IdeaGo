"""Tavily data source — web search via Tavily API.

通过 Tavily API 进行网页搜索。
"""

from __future__ import annotations

import asyncio

from tavily import AsyncTavilyClient

from ideago.models.research import Platform, RawResult
from ideago.observability.log_config import get_logger

logger = get_logger(__name__)


class TavilySource:
    """Searches the web using Tavily's search API."""

    def __init__(self, api_key: str = "", timeout: int = 30) -> None:
        self._api_key = api_key
        self._timeout = timeout
        if api_key:
            self._client = AsyncTavilyClient(api_key=api_key)
        else:
            self._client = None

    @property
    def platform(self) -> Platform:
        return Platform.TAVILY

    def is_available(self) -> bool:
        return bool(self._api_key)

    async def search(self, queries: list[str], limit: int = 10) -> list[RawResult]:
        """Search web for each query and return combined results."""
        if not self._client:
            return []

        results: list[RawResult] = []
        seen_urls: set[str] = set()

        for query in queries:
            try:
                response = await asyncio.wait_for(
                    self._client.search(
                        query=query,
                        max_results=limit,
                        search_depth="basic",
                    ),
                    timeout=self._timeout,
                )
                for item in response.get("results", []):
                    url = item.get("url", "")
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)
                    results.append(
                        RawResult(
                            title=item.get("title", ""),
                            description=item.get("content", ""),
                            url=url,
                            platform=Platform.TAVILY,
                            raw_data={
                                "score": item.get("score"),
                                "raw_content": item.get("raw_content"),
                            },
                        )
                    )
            except asyncio.TimeoutError:
                logger.warning("Tavily search timed out for '{query}'", query=query)
            except Exception as exc:
                logger.warning(
                    "Tavily search failed for '{query}': {exc}", query=query, exc=exc
                )

        return results
