"""GitHub data source — searches repositories via GitHub Search API.

通过 GitHub Search API 搜索仓库。
"""

from __future__ import annotations

import httpx

from ideago.models.research import Platform, RawResult
from ideago.observability.log_config import get_logger

logger = get_logger(__name__)


class GitHubSource:
    """Searches GitHub repositories using the official Search API."""

    _BASE_URL = "https://api.github.com"

    def __init__(self, token: str = "", timeout: int = 30) -> None:
        headers: dict[str, str] = {"Accept": "application/vnd.github+json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.AsyncClient(
            base_url=self._BASE_URL,
            headers=headers,
            timeout=timeout,
        )

    @property
    def platform(self) -> Platform:
        return Platform.GITHUB

    def is_available(self) -> bool:
        return True

    async def search(self, queries: list[str], limit: int = 10) -> list[RawResult]:
        """Search GitHub repos for each query and return combined results."""
        results: list[RawResult] = []
        seen_urls: set[str] = set()

        for query in queries:
            try:
                resp = await self._client.get(
                    "/search/repositories",
                    params={"q": query, "sort": "stars", "per_page": limit},
                )
                if resp.status_code != 200:
                    logger.warning(
                        "GitHub API returned {status} for query '{query}'",
                        status=resp.status_code,
                        query=query,
                    )
                    continue

                data = resp.json()
                for item in data.get("items", []):
                    url = item.get("html_url", "")
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)
                    results.append(
                        RawResult(
                            title=item.get("full_name", ""),
                            description=item.get("description") or "",
                            url=url,
                            platform=Platform.GITHUB,
                            raw_data={
                                "stargazers_count": item.get("stargazers_count", 0),
                                "language": item.get("language"),
                                "topics": item.get("topics", []),
                                "forks_count": item.get("forks_count", 0),
                                "updated_at": item.get("updated_at"),
                            },
                        )
                    )
            except httpx.HTTPError as exc:
                logger.warning(
                    "GitHub search failed for '{query}': {exc}", query=query, exc=exc
                )

        return results

    async def close(self) -> None:
        await self._client.aclose()
