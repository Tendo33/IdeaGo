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


class GitHubSource:
    """Searches GitHub repositories using the official Search API."""

    _BASE_URL = "https://api.github.com"

    def __init__(
        self,
        token: str = "",
        timeout: int = 30,
        max_concurrent_queries: int = 2,
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

    @property
    def platform(self) -> Platform:
        return Platform.GITHUB

    def is_available(self) -> bool:
        return True

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
                        "updated_at": item.get("updated_at"),
                    },
                )
                for item in data.get("items", [])
                if item.get("html_url")
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

    async def close(self) -> None:
        await self._client.aclose()


_QUALIFIER_PATTERN = re.compile(
    r"\b(?:stars|forks|size|language|topic|created|pushed|updated|sort|order):\S+",
    flags=re.IGNORECASE,
)


def _normalize_github_query(query: str) -> str:
    """Keep GitHub queries keyword-driven and avoid over-constrained search DSL."""
    stripped = query.strip()
    if not stripped:
        return ""
    without_qualifiers = _QUALIFIER_PATTERN.sub(" ", stripped)
    tokens = [token for token in re.split(r"\s+", without_qualifiers) if token]
    if not tokens:
        return stripped
    return " ".join(tokens[:6])
