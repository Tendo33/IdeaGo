"""Product Hunt data source — searches posts via Product Hunt GraphQL API."""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timedelta, timezone
from typing import Any, NamedTuple

import httpx

from ideago.models.research import Platform, RawResult
from ideago.observability.log_config import get_logger
from ideago.pipeline.query_builder import infer_query_family
from ideago.sources.errors import SourceSearchError

logger = get_logger(__name__)
_TOPIC_FALLBACK_SLUGS = [
    "developer-tools",
    "productivity",
    "artificial-intelligence",
    "saas",
]


class _ResolvedQuery(NamedTuple):
    text: str
    family: str


_TOPICS_QUERY = """
query Topics($q: String!, $first: Int!) {
  topics(query: $q, first: $first) {
    nodes { name slug postsCount url }
  }
}
"""

_POSTS_QUERY = """
query Posts($topic: String!, $first: Int!, $after: String, $postedAfter: DateTime) {
  posts(topic: $topic, first: $first, after: $after, postedAfter: $postedAfter) {
    nodes {
      id
      name
      tagline
      votesCount
      createdAt
      url
      website
    }
    pageInfo { hasNextPage endCursor }
  }
}
"""


class ProductHuntSource:
    """Searches Product Hunt posts with a developer token."""

    _BASE_URL = "https://api.producthunt.com"
    _GRAPHQL_PATH = "/v2/api/graphql"

    def __init__(
        self,
        dev_token: str = "",
        posted_after_days: int = 730,
        timeout: int = 30,
        max_concurrent_queries: int = 2,
    ) -> None:
        self._dev_token = dev_token.strip()
        self._posted_after_days = max(1, posted_after_days)
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self._dev_token:
            headers["Authorization"] = f"Bearer {self._dev_token}"
        self._client = httpx.AsyncClient(
            base_url=self._BASE_URL,
            headers=headers,
            timeout=timeout,
        )
        self._max_concurrent_queries = max(1, max_concurrent_queries)
        self._runtime_max_concurrent_queries: int | None = None
        self._last_search_diagnostics: dict[str, object] = {
            "partial_failure": False,
            "failed_queries": [],
            "timed_out_queries": [],
        }

    @property
    def platform(self) -> Platform:
        return Platform.PRODUCT_HUNT

    def is_available(self) -> bool:
        return bool(self._dev_token)

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

    async def _graphql(
        self,
        query: str,
        variables: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            resp = await self._client.post(
                self._GRAPHQL_PATH,
                json={"query": query, "variables": variables},
            )
            if resp.status_code != 200:
                logger.warning(
                    "Product Hunt API returned {status}",
                    status=resp.status_code,
                )
                raise SourceSearchError(
                    self.platform.value,
                    "Product Hunt API non-200 response",
                    status_code=resp.status_code,
                )
            payload = resp.json()
            errors = payload.get("errors")
            if errors:
                raise SourceSearchError(
                    self.platform.value,
                    f"GraphQL errors: {errors}",
                )
            data = payload.get("data")
            if isinstance(data, dict):
                return data
            return {}
        except SourceSearchError:
            raise
        except httpx.HTTPError as exc:
            logger.warning("Product Hunt request failed: {exc}", exc=exc)
            raise SourceSearchError(self.platform.value, str(exc)) from exc
        except ValueError as exc:
            raise SourceSearchError(
                self.platform.value,
                "Invalid JSON payload from Product Hunt",
            ) from exc

    async def _find_topic_slugs(self, query: str, first: int = 5) -> list[str]:
        payload = await self._graphql(_TOPICS_QUERY, {"q": query, "first": first})
        topics = payload.get("topics", {})
        if not isinstance(topics, dict):
            return []
        nodes = topics.get("nodes", [])
        if not isinstance(nodes, list):
            return []
        slugs: list[str] = []
        seen: set[str] = set()
        for node in nodes:
            if not isinstance(node, dict):
                continue
            slug = node.get("slug", "")
            if not isinstance(slug, str) or not slug:
                continue
            if slug in seen:
                continue
            seen.add(slug)
            slugs.append(slug)
        return slugs

    async def _fetch_posts_by_topic(
        self,
        topic_slug: str,
        posted_after_iso: str,
        page_size: int,
        max_pages: int,
    ) -> list[dict[str, Any]]:
        collected: list[dict[str, Any]] = []
        after: str | None = None
        for _ in range(max_pages):
            payload = await self._graphql(
                _POSTS_QUERY,
                {
                    "topic": topic_slug,
                    "first": page_size,
                    "after": after,
                    "postedAfter": posted_after_iso,
                },
            )
            posts = payload.get("posts", {})
            if not isinstance(posts, dict):
                break
            nodes = posts.get("nodes", [])
            if isinstance(nodes, list):
                for node in nodes:
                    if isinstance(node, dict):
                        enriched = dict(node)
                        enriched["topic_slug"] = topic_slug
                        collected.append(enriched)
            page_info = posts.get("pageInfo", {})
            if not isinstance(page_info, dict):
                break
            has_next_page = bool(page_info.get("hasNextPage"))
            after_value = page_info.get("endCursor")
            if not has_next_page or not isinstance(after_value, str) or not after_value:
                break
            after = after_value
        return collected

    async def search(self, queries: list[str], limit: int = 10) -> list[RawResult]:
        """Search Product Hunt and return deduplicated raw posts."""
        if not self.is_available() or not queries:
            return []
        self._last_search_diagnostics = {
            "partial_failure": False,
            "failed_queries": [],
            "timed_out_queries": [],
        }

        resolved_queries = [
            resolved_query
            for query in queries
            if (resolved_query := _resolve_query(query)).text
        ]
        if not resolved_queries:
            return []
        normalized_queries = [
            resolved_query.text for resolved_query in resolved_queries
        ]

        max_concurrency = (
            self._runtime_max_concurrent_queries or self._max_concurrent_queries
        )
        query_semaphore = asyncio.Semaphore(max_concurrency)
        unique_slugs: list[str] = []
        seen_slugs: set[str] = set()
        slug_origin_queries: dict[str, list[_ResolvedQuery]] = {}
        failed_queries: list[str] = []
        first_error: Exception | None = None

        async def discover_slugs(
            resolved_query: _ResolvedQuery,
        ) -> tuple[str, list[str] | Exception]:
            async with query_semaphore:
                try:
                    return resolved_query.text, await self._find_topic_slugs(
                        query=resolved_query.text,
                        first=5,
                    )
                except Exception as exc:  # noqa: BLE001
                    return resolved_query.text, exc

        query_slug_results = await asyncio.gather(
            *(discover_slugs(query) for query in resolved_queries),
            return_exceptions=False,
        )
        for query, slug_result in query_slug_results:
            if isinstance(slug_result, Exception):
                failed_queries.append(query)
                if first_error is None:
                    first_error = slug_result
                logger.warning(
                    "Source query failure: platform={}, query={}, error_type={}",
                    self.platform.value,
                    query,
                    type(slug_result).__name__,
                )
                continue
            for slug in slug_result:
                matched_query = next(
                    (
                        resolved_query
                        for resolved_query in resolved_queries
                        if resolved_query.text == query
                    ),
                    _ResolvedQuery(query, infer_query_family(query)),
                )
                slug_origin_queries.setdefault(slug, [])
                if matched_query not in slug_origin_queries[slug]:
                    slug_origin_queries[slug].append(matched_query)
                if slug in seen_slugs:
                    continue
                seen_slugs.add(slug)
                unique_slugs.append(slug)

        if not unique_slugs:
            unique_slugs = _fallback_topic_slugs()

        posted_after = (
            datetime.now(timezone.utc) - timedelta(days=self._posted_after_days)
        ).isoformat()
        page_size = max(1, min(limit, 20))
        max_pages = 3
        semaphore = asyncio.Semaphore(max_concurrency)

        async def fetch_slug(slug: str) -> tuple[str, list[dict[str, Any]] | Exception]:
            async with semaphore:
                try:
                    return slug, await self._fetch_posts_by_topic(
                        topic_slug=slug,
                        posted_after_iso=posted_after,
                        page_size=page_size,
                        max_pages=max_pages,
                    )
                except Exception as exc:  # noqa: BLE001
                    return slug, exc

        grouped_posts = await asyncio.gather(
            *(fetch_slug(slug) for slug in unique_slugs),
            return_exceptions=False,
        )
        collected_posts: list[dict[str, Any]] = []
        failed_slugs: list[str] = []
        for slug, posts_or_exc in grouped_posts:
            if isinstance(posts_or_exc, Exception):
                failed_slugs.append(slug)
                if first_error is None:
                    first_error = posts_or_exc
                logger.warning(
                    "Source topic fetch failure: platform={}, topic={}, error_type={}",
                    self.platform.value,
                    slug,
                    type(posts_or_exc).__name__,
                )
                continue
            collected_posts.extend(posts_or_exc)
        query_tokens = _extract_query_tokens(normalized_queries)
        enforce_token_match = any(
            re.search(r"[a-z0-9]", token) is not None for token in query_tokens
        )

        candidates: dict[str, tuple[RawResult, int, int, str]] = {}
        for post in collected_posts:
            post_url = _safe_str(post.get("url"))
            if not post_url:
                continue

            name = _safe_str(post.get("name"))
            tagline = _safe_str(post.get("tagline"))
            text_blob = f"{name} {tagline}".lower()
            score = sum(1 for token in query_tokens if token in text_blob)
            if enforce_token_match and score < 1:
                continue

            votes_count = _safe_int(post.get("votesCount"))
            created_at = _safe_str(post.get("createdAt"))
            matched_query = _select_best_query_provenance(
                post,
                slug_origin_queries.get(
                    _safe_str(post.get("topic_slug")),
                    resolved_queries,
                ),
            )
            raw_result = RawResult(
                title=name,
                description=tagline,
                url=post_url,
                platform=Platform.PRODUCT_HUNT,
                raw_data={
                    "matched_query": matched_query.text,
                    "query_family": matched_query.family,
                    "source_native_score": votes_count,
                    "engagement_proxy": votes_count,
                    "freshness_timestamp": _normalize_iso8601(created_at),
                    "post_id": post.get("id"),
                    "votes_count": votes_count,
                    "created_at": created_at,
                    "website": post.get("website"),
                    "topic_slug": post.get("topic_slug"),
                },
            )
            existing = candidates.get(post_url)
            rank_tuple = (score, votes_count, created_at)
            if existing is None or rank_tuple > (
                existing[1],
                existing[2],
                existing[3],
            ):
                candidates[post_url] = (raw_result, score, votes_count, created_at)

        sorted_candidates = sorted(
            candidates.values(),
            key=lambda item: (item[1], item[2], item[3]),
            reverse=True,
        )
        upper_bound = max(1, limit) * max(1, len(normalized_queries))
        final_results = [item[0] for item in sorted_candidates[:upper_bound]]
        if (failed_queries or failed_slugs) and final_results:
            self._last_search_diagnostics = {
                "partial_failure": True,
                "failed_queries": [*failed_queries, *failed_slugs],
                "timed_out_queries": [],
            }
            return final_results
        if (failed_queries or failed_slugs) and first_error is not None:
            raise first_error
        return final_results

    async def close(self) -> None:
        await self._client.aclose()


def _extract_query_tokens(queries: list[str]) -> set[str]:
    tokens: set[str] = set()
    for query in queries:
        normalized_query = _strip_search_qualifiers(query.lower())
        query_tokens: set[str] = set()
        for token in re.findall(r"[a-z0-9_+-]{2,}", normalized_query):
            if token in {"stars", "forks", "language", "topic", "created", "updated"}:
                continue
            query_tokens.add(token)
        for token in re.findall(r"[\u4e00-\u9fff]{2,}", normalized_query):
            query_tokens.add(token)
        if not query_tokens and normalized_query.strip():
            query_tokens.add(normalized_query.strip())
        tokens.update(query_tokens)
    return tokens


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


def _fallback_topic_slugs() -> list[str]:
    return list(_TOPIC_FALLBACK_SLUGS)


def _select_best_query_provenance(
    post: dict[str, Any],
    candidate_queries: list[_ResolvedQuery],
) -> _ResolvedQuery:
    if not candidate_queries:
        return _ResolvedQuery("", "competitor_discovery")
    if len(candidate_queries) == 1:
        return candidate_queries[0]

    text_blob = _build_post_text_blob(post)
    best_query = candidate_queries[0]
    best_score = _score_query_against_post(best_query, text_blob)
    for candidate_query in candidate_queries[1:]:
        candidate_score = _score_query_against_post(candidate_query, text_blob)
        if candidate_score > best_score:
            best_query = candidate_query
            best_score = candidate_score
    return best_query


def _build_post_text_blob(post: dict[str, Any]) -> str:
    segments = [
        _safe_str(post.get("name")),
        _safe_str(post.get("tagline")),
        _safe_str(post.get("website")),
        _safe_str(post.get("topic_slug")),
    ]
    return " ".join(segment.lower() for segment in segments if segment)


def _score_query_against_post(
    candidate_query: _ResolvedQuery,
    text_blob: str,
) -> tuple[int, int, int]:
    normalized_query = _strip_search_qualifiers(candidate_query.text.lower()).strip()
    phrase_match = int(bool(normalized_query) and normalized_query in text_blob)
    matched_tokens = [
        token
        for token in _extract_query_tokens([candidate_query.text])
        if token in text_blob
    ]
    return (
        phrase_match,
        len(matched_tokens),
        sum(len(token) for token in matched_tokens),
    )


def _strip_search_qualifiers(query: str) -> str:
    return re.sub(
        r"\b(?:stars|forks|size|language|topic|created|pushed|updated|sort|order):\S+",
        " ",
        query,
        flags=re.IGNORECASE,
    )


def _safe_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return 0
    return 0


def _safe_str(value: Any) -> str:
    if isinstance(value, str):
        return value
    return ""
