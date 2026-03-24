"""GitHub data source — searches repositories via GitHub Search API.

通过 GitHub Search API 搜索仓库。
"""

from __future__ import annotations

import asyncio
import re

import httpx

from ideago.models.research import Platform, RawResult
from ideago.observability.log_config import get_logger
from ideago.sources.errors import SourceSearchError

logger = get_logger(__name__)
_DEFAULT_MIN_STARS = 50


class GitHubSource:
    """Searches GitHub repositories using the official Search API."""

    _BASE_URL = "https://api.github.com"

    def __init__(
        self,
        token: str = "",
        timeout: int = 30,
        max_concurrent_queries: int = 2,
        min_stars: int = _DEFAULT_MIN_STARS,
    ) -> None:
        headers: dict[str, str] = {"Accept": "application/vnd.github+json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.AsyncClient(
            base_url=self._BASE_URL,
            headers=headers,
            timeout=timeout,
        )
        self._max_concurrent_queries = max(1, max_concurrent_queries)
        self._min_stars = max(0, min_stars)
        self._runtime_max_concurrent_queries: int | None = None
        self._last_search_diagnostics: dict[str, object] = {
            "partial_failure": False,
            "failed_queries": [],
            "timed_out_queries": [],
        }

    @property
    def platform(self) -> Platform:
        return Platform.GITHUB

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
        normalized_query = _normalize_github_query(query)
        try:
            resp = await self._client.get(
                "/search/repositories",
                params={"q": normalized_query, "sort": "stars", "per_page": limit},
            )
            if resp.status_code != 200:
                logger.warning(
                    "GitHub API returned {status} for query '{query}'",
                    status=resp.status_code,
                    query=query,
                )
                raise SourceSearchError(
                    self.platform.value,
                    "GitHub API non-200 response",
                    status_code=resp.status_code,
                )

            data = resp.json()
            return [
                RawResult(
                    title=item.get("full_name", ""),
                    description=item.get("description") or "",
                    url=item.get("html_url", ""),
                    platform=Platform.GITHUB,
                    raw_data={
                        "stargazers_count": item.get("stargazers_count", 0),
                        "language": item.get("language"),
                        "topics": item.get("topics", []),
                        "forks_count": item.get("forks_count", 0),
                        "size": item.get("size", 0),
                        "pushed_at": item.get("pushed_at"),
                        "updated_at": item.get("updated_at"),
                    },
                )
                for item in data.get("items", [])
                if item.get("html_url")
                and int(item.get("stargazers_count", 0) or 0) >= self._min_stars
                and _is_non_empty_repository(item)
            ]
        except httpx.HTTPError as exc:
            logger.warning(
                "GitHub search failed for '{query}': {exc}", query=query, exc=exc
            )
            raise SourceSearchError(self.platform.value, str(exc)) from exc

    async def search(self, queries: list[str], limit: int = 10) -> list[RawResult]:
        """Search GitHub repos for each query and return combined results."""
        if not queries:
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

    async def close(self) -> None:
        await self._client.aclose()


_STRIP_QUALIFIER_PATTERN = re.compile(
    r"\b(?:stars|forks|size|language|created|pushed|updated|sort|order):\S+",
    flags=re.IGNORECASE,
)


def _normalize_github_query(query: str) -> str:
    """Normalize GitHub queries: preserve topic: qualifiers, strip ranking qualifiers."""
    stripped = query.strip()
    if not stripped:
        return ""
    without_ranking = _STRIP_QUALIFIER_PATTERN.sub(" ", stripped)
    tokens = [token for token in re.split(r"\s+", without_ranking) if token]
    if not tokens:
        return stripped
    return " ".join(tokens[:8])


def _is_non_empty_repository(item: dict[str, object]) -> bool:
    """Filter obvious placeholder repos with no actual repository contents."""
    size = int(item.get("size", 0) or 0)
    if size > 0:
        return True
    return bool(item.get("pushed_at"))
