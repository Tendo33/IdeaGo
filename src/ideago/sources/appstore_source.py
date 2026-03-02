"""App Store data source — searches iOS apps via iTunes Search API.

通过 iTunes Search API 搜索 iOS App。
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from ideago.models.research import Platform, RawResult
from ideago.observability.log_config import get_logger
from ideago.sources.errors import SourceSearchError

logger = get_logger(__name__)


class AppStoreSource:
    """Searches iOS apps using the public iTunes Search API."""

    _BASE_URL = "https://itunes.apple.com"

    def __init__(
        self,
        country: str = "us",
        timeout: int = 30,
        max_concurrent_queries: int = 2,
    ) -> None:
        self._country = (country or "us").lower()
        self._client = httpx.AsyncClient(
            base_url=self._BASE_URL,
            timeout=timeout,
        )
        self._max_concurrent_queries = max(1, max_concurrent_queries)

    @property
    def platform(self) -> Platform:
        return Platform.APPSTORE

    def is_available(self) -> bool:
        return True

    async def _search_single_query(self, query: str, limit: int) -> list[RawResult]:
        try:
            resp = await self._client.get(
                "/search",
                params={
                    "term": query,
                    "entity": "software",
                    "country": self._country,
                    "limit": limit,
                },
            )
            if resp.status_code != 200:
                error_message = _extract_error_message(resp)
                logger.warning(
                    "App Store API returned {status} for query '{query}'",
                    status=resp.status_code,
                    query=query,
                )
                raise SourceSearchError(
                    self.platform.value,
                    error_message,
                    status_code=resp.status_code,
                )

            payload = resp.json()
            results: list[RawResult] = []
            for item in payload.get("results", []):
                track_url = item.get("trackViewUrl")
                if not track_url:
                    continue
                results.append(
                    RawResult(
                        title=item.get("trackName", ""),
                        description=item.get("description") or "",
                        url=track_url,
                        platform=Platform.APPSTORE,
                        raw_data={
                            "track_id": item.get("trackId"),
                            "bundle_id": item.get("bundleId"),
                            "seller_name": item.get("sellerName"),
                            "primary_genre_name": item.get("primaryGenreName"),
                            "average_user_rating": item.get("averageUserRating"),
                            "user_rating_count": item.get("userRatingCount"),
                            "price": item.get("price"),
                            "formatted_price": item.get("formattedPrice"),
                            "currency": item.get("currency"),
                            "version": item.get("version"),
                            "release_date": item.get("releaseDate"),
                        },
                    )
                )
            return results
        except httpx.HTTPError as exc:
            logger.warning(
                "App Store search failed for '{query}': {exc}", query=query, exc=exc
            )
            raise SourceSearchError(self.platform.value, str(exc)) from exc

    async def search(self, queries: list[str], limit: int = 10) -> list[RawResult]:
        """Search iOS apps for each query and return deduplicated results."""
        if not queries:
            return []

        seen_track_ids: set[int] = set()
        seen_urls: set[str] = set()
        semaphore = asyncio.Semaphore(self._max_concurrent_queries)

        async def run_query(query: str) -> list[RawResult]:
            async with semaphore:
                return await self._search_single_query(query, limit)

        grouped_results = await asyncio.gather(*(run_query(query) for query in queries))
        deduped_results: list[RawResult] = []
        for query_results in grouped_results:
            for result in query_results:
                track_id = result.raw_data.get("track_id")
                if isinstance(track_id, int):
                    if track_id in seen_track_ids:
                        continue
                    seen_track_ids.add(track_id)
                elif result.url in seen_urls:
                    continue
                seen_urls.add(result.url)
                deduped_results.append(result)
        return deduped_results

    async def close(self) -> None:
        await self._client.aclose()


def _extract_error_message(resp: httpx.Response) -> str:
    try:
        payload: Any = resp.json()
    except ValueError:
        return "App Store API non-200 response"
    if isinstance(payload, dict):
        error_message = payload.get("errorMessage")
        if isinstance(error_message, str) and error_message.strip():
            return error_message
    return "App Store API non-200 response"
