"""App Store data source — searches iOS apps via iTunes Search API.

通过 iTunes Search API 搜索 iOS App。
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any
from urllib.parse import urlsplit, urlunsplit

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
                            "canonical_track_url": _canonicalize_track_url(track_url),
                            "rating": _to_float(item.get("averageUserRating")),
                            "rating_count": _to_int(item.get("userRatingCount")),
                            "price_numeric": _to_float(item.get("price")),
                            "price_label": _to_price_label(
                                item.get("formattedPrice"),
                                item.get("price"),
                            ),
                            "release_date_iso": _to_iso_date(item.get("releaseDate")),
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


def _canonicalize_track_url(url: str) -> str:
    if not isinstance(url, str) or not url.strip():
        return ""
    try:
        parsed = urlsplit(url.strip())
    except ValueError:
        return ""
    if not parsed.scheme or not parsed.netloc:
        return ""
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def _to_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _to_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _to_price_label(formatted_price: object, price: object) -> str | None:
    if isinstance(formatted_price, str) and formatted_price.strip():
        return formatted_price
    numeric_price = _to_float(price)
    if numeric_price is None:
        return None
    return str(numeric_price)


def _to_iso_date(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.date().isoformat()
