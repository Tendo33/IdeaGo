"""GitHub data source — searches repositories via GitHub Search API.

通过 GitHub Search API 搜索仓库。
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from typing import NamedTuple

import httpx

from ideago.models.research import Platform, RawResult
from ideago.observability.log_config import get_logger
from ideago.pipeline.query_builder import infer_query_family
from ideago.sources.errors import SourceSearchError

logger = get_logger(__name__)
_DEFAULT_MIN_STARS = 50


class _ResolvedQuery(NamedTuple):
    text: str
    family: str


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

    async def _search_single_query(
        self,
        resolved_query: _ResolvedQuery,
        limit: int,
    ) -> list[RawResult]:
        query = resolved_query.text
        normalized_query = _normalize_github_query(query)
        try:
            resp = await self._client.get(
                "/search/repositories",
                params={"q": normalized_query, "per_page": limit},
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
            candidates = [
                item
                for item in data.get("items", [])
                if item.get("html_url")
                and int(item.get("stargazers_count", 0) or 0)
                >= _min_stars_for_query(
                    self._min_stars,
                    resolved_query.family,
                    query,
                )
                and _is_non_empty_repository(item)
            ]
            ranked_candidates = sorted(
                candidates,
                key=lambda item: _repository_rank(item, query=query),
                reverse=True,
            )
            return [
                RawResult(
                    title=item.get("full_name", ""),
                    description=item.get("description") or "",
                    url=item.get("html_url", ""),
                    platform=Platform.GITHUB,
                    raw_data={
                        "matched_query": query,
                        "query_family": resolved_query.family,
                        "source_native_score": item.get("stargazers_count", 0),
                        "engagement_proxy": int(item.get("stargazers_count", 0) or 0)
                        + int(item.get("forks_count", 0) or 0),
                        "freshness_timestamp": _normalize_iso8601(
                            item.get("pushed_at") or item.get("updated_at")
                        ),
                        "stargazers_count": item.get("stargazers_count", 0),
                        "language": item.get("language"),
                        "topics": item.get("topics", []),
                        "forks_count": item.get("forks_count", 0),
                        "size": item.get("size", 0),
                        "pushed_at": item.get("pushed_at"),
                        "updated_at": item.get("updated_at"),
                    },
                )
                for item in ranked_candidates
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
        resolved_queries = [
            resolved_query
            for query in queries
            if (resolved_query := _resolve_query(query)).text
        ]
        if not resolved_queries:
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

        async def run_query(
            resolved_query: _ResolvedQuery,
        ) -> tuple[str, list[RawResult] | Exception]:
            async with semaphore:
                try:
                    return resolved_query.text, await self._search_single_query(
                        resolved_query,
                        limit,
                    )
                except Exception as exc:  # noqa: BLE001
                    return resolved_query.text, exc

        grouped_results = await asyncio.gather(
            *(run_query(query) for query in resolved_queries),
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


def _repository_rank(item: dict[str, object], *, query: str) -> tuple[int, int, int]:
    raw_topics = item.get("topics", [])
    topics = raw_topics if isinstance(raw_topics, list) else []
    text_blob = " ".join(
        str(value).lower()
        for value in (
            item.get("full_name"),
            item.get("description"),
            " ".join(str(topic) for topic in topics),
        )
        if value
    )
    normalized_query = query.strip().lower()
    exact_hit = 1 if normalized_query and normalized_query in text_blob else 0
    query_tokens = [
        token for token in normalized_query.replace('"', "").split() if token
    ]
    anchor_hits = sum(
        1 for anchor in _extract_anchor_phrases(query) if anchor and anchor in text_blob
    )
    token_hits = sum(1 for token in query_tokens if token in text_blob)
    freshness_bonus = _freshness_score(item.get("pushed_at") or item.get("updated_at"))
    popularity = _safe_int(item.get("stargazers_count")) + _safe_int(
        item.get("forks_count")
    )
    return (exact_hit * 10 + anchor_hits * 6 + token_hits, freshness_bonus, popularity)


def _extract_anchor_phrases(query: str) -> list[str]:
    quoted = [match.strip().lower() for match in re.findall(r'"([^"]+)"', query)]
    if quoted:
        return [phrase for phrase in quoted if phrase]
    tokens = [token for token in re.findall(r"[A-Za-z0-9]+", query) if token]
    if len(tokens) >= 2:
        return [" ".join(tokens[:2]).lower()]
    return []


def _min_stars_for_query(default_min_stars: int, family: str, query: str) -> int:
    normalized_family = family.strip().lower()
    if normalized_family in {"direct_competitor", "workflow_interface"}:
        return min(default_min_stars, 10)
    if normalized_family in {"competitor_discovery", "workflow_discovery"} and (
        '"' in query or _has_direct_anchor_phrase(query)
    ):
        return min(default_min_stars, 10)
    return default_min_stars


def _has_direct_anchor_phrase(query: str) -> bool:
    lowered = query.lower()
    return any(
        token in lowered
        for token in (" gui", " cli", " desktop", " interface", " workflow")
    )


def _freshness_score(value: object) -> int:
    normalized = _normalize_iso8601(value)
    if not normalized:
        return 0
    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError:
        return 0
    delta_days = max((datetime.now(timezone.utc) - parsed).days, 0)
    if delta_days <= 30:
        return 3
    if delta_days <= 180:
        return 2
    if delta_days <= 365:
        return 1
    return 0


def _safe_int(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip() or "0")
        except ValueError:
            return 0
    return 0


def _is_non_empty_repository(item: dict[str, object]) -> bool:
    """Filter obvious placeholder repos with no actual repository contents."""
    raw_size = item.get("size", 0)
    if isinstance(raw_size, bool):
        size = int(raw_size)
    elif isinstance(raw_size, int):
        size = raw_size
    elif isinstance(raw_size, float):
        size = int(raw_size)
    elif isinstance(raw_size, str):
        try:
            size = int(raw_size.strip() or "0")
        except ValueError:
            size = 0
    else:
        size = 0
    if size > 0:
        return True
    return bool(item.get("pushed_at"))


def _resolve_query(query: object) -> _ResolvedQuery:
    text = _extract_query_text(query)
    if not text:
        return _ResolvedQuery("", "competitor_discovery")
    family = _extract_query_family(query)
    return _ResolvedQuery(text, family or infer_query_family(text))


def _extract_query_text(query: object) -> str:
    if isinstance(query, str):
        return query.strip()
    if isinstance(query, dict):
        for key in ("query", "text", "value"):
            value = query.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""
    for attr in ("query", "text", "value"):
        value = getattr(query, attr, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _extract_query_family(query: object) -> str:
    if isinstance(query, dict):
        value = query.get("query_family") or query.get("family")
        return value.strip() if isinstance(value, str) and value.strip() else ""
    value = getattr(query, "query_family", None) or getattr(query, "family", None)
    return value.strip() if isinstance(value, str) and value.strip() else ""


def _normalize_iso8601(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    else:
        parsed = parsed.astimezone(timezone.utc)
    return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")
