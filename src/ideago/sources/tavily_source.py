"""Tavily data source — web search via Tavily API.

通过 Tavily API 进行网页搜索。
"""

from __future__ import annotations

import asyncio
from typing import NamedTuple
from urllib.parse import urlsplit

from tavily import AsyncTavilyClient

from ideago.models.research import Platform, RawResult
from ideago.observability.log_config import get_logger
from ideago.pipeline.query_builder import infer_query_family
from ideago.sources.errors import SourceSearchError

logger = get_logger(__name__)


class _ResolvedQuery(NamedTuple):
    text: str
    family: str


class TavilySource:
    """Searches the web using Tavily's search API."""

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "",
        timeout: int = 30,
        max_concurrent_queries: int = 2,
        max_age_days: int = 0,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._timeout = timeout
        self._max_concurrent_queries = max(1, max_concurrent_queries)
        self._max_age_days = max(0, max_age_days)
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

    async def _search_single_query(
        self,
        resolved_query: _ResolvedQuery,
        limit: int,
    ) -> list[RawResult]:
        if not self._client:
            return []
        query = resolved_query.text
        try:
            search_kwargs: dict[str, object] = {
                "query": query,
                "max_results": limit,
                "search_depth": "basic",
            }
            if self._max_age_days > 0:
                search_kwargs["days"] = self._max_age_days
            response = await asyncio.wait_for(
                self._client.search(**search_kwargs),  # type: ignore[arg-type]
                timeout=self._timeout,
            )
            ranked_items = sorted(
                response.get("results", []),
                key=_tavily_result_rank,
                reverse=True,
            )
            return [
                RawResult(
                    title=item.get("title", ""),
                    description=item.get("content", ""),
                    url=item.get("url", ""),
                    platform=Platform.TAVILY,
                    raw_data={
                        "matched_query": query,
                        "query_family": resolved_query.family,
                        "source_native_score": item.get("score"),
                        "engagement_proxy": item.get("score"),
                        "freshness_timestamp": None,
                        "score": item.get("score"),
                        "raw_content": item.get("raw_content"),
                    },
                )
                for item in ranked_items
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


def _tavily_result_rank(item: dict[str, object]) -> tuple[int, float]:
    url = str(item.get("url", "") or "")
    title = str(item.get("title", "") or "")
    content = str(item.get("content", "") or "")
    product_bias = _product_page_bias(url=url, title=title, content=content)
    raw_score = item.get("score")
    native_score = float(raw_score) if isinstance(raw_score, int | float) else 0.0
    return (product_bias, native_score)


def _product_page_bias(*, url: str, title: str, content: str) -> int:
    parsed = urlsplit(url)
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    combined = f"{title} {content}".lower()

    score = 0
    if (
        host.startswith("github.com")
        or "producthunt.com" in host
        or "apps.apple.com" in host
    ):
        score += 6
    if any(
        token in path
        for token in (
            "/product",
            "/products",
            "/app",
            "/apps",
            "/download",
            "/pricing",
            "/docs",
        )
    ):
        score += 4
    if any(
        token in combined
        for token in ("official", "pricing", "product", "download", "docs")
    ):
        score += 2
    if any(
        token in host for token in ("blog.", "medium.com", "substack.com", "dev.to")
    ):
        score -= 6
    if any(
        token in path
        for token in ("/blog", "/news", "/article", "/tutorial", "/review")
    ):
        score -= 5
    if any(
        token in combined
        for token in ("review", "tutorial", "changed my mind", "case study")
    ):
        score -= 3
    return score
