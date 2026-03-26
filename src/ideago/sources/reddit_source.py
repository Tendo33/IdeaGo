"""Reddit data source — searches via Reddit OAuth2 API.

通过 Reddit OAuth2 API 搜索社区讨论帖，用于竞品发现和需求验证。
需要在 https://www.reddit.com/prefs/apps 创建 "script" 类型应用获取凭证。
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import NamedTuple

import httpx

from ideago.models.research import Platform, RawResult
from ideago.observability.log_config import get_logger
from ideago.pipeline.query_builder import infer_query_family
from ideago.sources.errors import SourceSearchError
from ideago.utils.text_utils import decode_entities_and_strip_html

logger = get_logger(__name__)

_APP_USER_AGENT = "IdeaGo/0.3 (competitor-research-engine)"
_TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
_TOKEN_REFRESH_BUFFER = 60
_INTER_REQUEST_DELAY = 1.0
_PUBLIC_INTER_REQUEST_DELAY = 1.5
_PUBLIC_SEARCH_LIMIT_CAP = 10
_PUBLIC_SEARCH_URL = "https://www.reddit.com/search.json"


class _ResolvedQuery(NamedTuple):
    text: str
    family: str


def _to_int(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int | float):
        return int(value)
    if isinstance(value, str) and value.strip():
        try:
            return int(float(value))
        except ValueError:
            return 0
    return 0


def _to_iso_datetime_from_unix(value: object) -> str | None:
    if isinstance(value, bool):
        return None
    timestamp: float | None
    if isinstance(value, int | float):
        timestamp = float(value)
    elif isinstance(value, str) and value.strip():
        try:
            timestamp = float(value.strip())
        except ValueError:
            return None
    else:
        return None
    try:
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
    except (OverflowError, OSError, ValueError):
        return None


class RedditSource:
    """Searches Reddit posts using the OAuth2 Application-Only flow."""

    _BASE_URL = "https://oauth.reddit.com"

    def __init__(
        self,
        client_id: str = "",
        client_secret: str = "",
        timeout: int = 30,
        max_concurrent_queries: int = 2,
        enable_public_fallback: bool = False,
        public_fallback_limit: int = _PUBLIC_SEARCH_LIMIT_CAP,
        public_fallback_delay_seconds: float = _PUBLIC_INTER_REQUEST_DELAY,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._enable_public_fallback = enable_public_fallback
        self._public_fallback_limit = max(1, min(public_fallback_limit, 25))
        self._public_fallback_delay_seconds = max(0.0, public_fallback_delay_seconds)
        self._client = httpx.AsyncClient(
            base_url=self._BASE_URL,
            timeout=timeout,
            headers={"User-Agent": _APP_USER_AGENT},
            follow_redirects=True,
        )
        self._public_client = httpx.AsyncClient(
            timeout=timeout,
            headers={"User-Agent": _APP_USER_AGENT},
            follow_redirects=True,
        )
        self._auth_client = httpx.AsyncClient(
            timeout=15,
            headers={"User-Agent": _APP_USER_AGENT},
        )
        self._max_concurrent_queries = max(1, max_concurrent_queries)
        self._runtime_max_concurrent_queries: int | None = None
        self._access_token: str | None = None
        self._token_expires_at: float = 0.0
        self._token_lock = asyncio.Lock()
        self._last_search_diagnostics: dict[str, object] = {
            "partial_failure": False,
            "failed_queries": [],
            "timed_out_queries": [],
            "used_public_fallback": False,
            "fallback_reason": "none",
        }

    @property
    def platform(self) -> Platform:
        return Platform.REDDIT

    def _has_oauth_credentials(self) -> bool:
        return bool(self._client_id and self._client_secret)

    def is_available(self) -> bool:
        return bool(
            self._has_oauth_credentials()
            or (
                not self._client_id
                and not self._client_secret
                and self._enable_public_fallback
            )
        )

    def set_runtime_max_concurrent_queries(self, value: int | None) -> None:
        self._runtime_max_concurrent_queries = max(1, int(value)) if value else None

    def consume_last_search_diagnostics(self) -> dict[str, object]:
        payload = self._last_search_diagnostics
        self._last_search_diagnostics = {
            "partial_failure": False,
            "failed_queries": [],
            "timed_out_queries": [],
            "used_public_fallback": False,
            "fallback_reason": "none",
        }
        return payload

    def _reset_search_diagnostics(
        self,
        *,
        used_public_fallback: bool = False,
        fallback_reason: str = "none",
    ) -> None:
        self._last_search_diagnostics = {
            "partial_failure": False,
            "failed_queries": [],
            "timed_out_queries": [],
            "used_public_fallback": used_public_fallback,
            "fallback_reason": fallback_reason,
        }

    def _should_use_public_fallback(self) -> tuple[bool, str]:
        if self._has_oauth_credentials():
            return False, "none"
        if self._client_id or self._client_secret:
            return False, "partial_credentials"
        if not self._enable_public_fallback:
            return False, "disabled_by_config"
        return True, "missing_credentials"

    def _build_raw_result_from_post(
        self,
        post: dict[str, object],
        *,
        resolved_query: _ResolvedQuery,
        auth_mode: str,
    ) -> RawResult | None:
        post_id = str(post.get("id", "") or "")
        if not post_id:
            return None

        title = str(post.get("title", "") or "")
        selftext = decode_entities_and_strip_html(str(post.get("selftext", "") or ""))
        permalink = str(post.get("permalink", "") or "")
        url = f"https://www.reddit.com{permalink}" if permalink else ""
        score = post.get("score", 0)
        num_comments = post.get("num_comments", 0)
        created_utc = post.get("created_utc", 0)

        return RawResult(
            title=title,
            description=selftext[:500] if selftext else "",
            url=url,
            platform=Platform.REDDIT,
            raw_data={
                "matched_query": resolved_query.text,
                "query_family": resolved_query.family,
                "source_native_score": score,
                "engagement_proxy": _to_int(score) + _to_int(num_comments),
                "freshness_timestamp": _to_iso_datetime_from_unix(created_utc),
                "post_id": post_id,
                "subreddit": str(post.get("subreddit", "") or ""),
                "score": score,
                "num_comments": num_comments,
                "created_utc": created_utc,
                "link_url": str(post.get("url", "") or ""),
                "upvote_ratio": post.get("upvote_ratio", 0),
                "auth_mode": auth_mode,
            },
        )

    async def _ensure_token(self) -> str:
        """Obtain or refresh the OAuth2 application-only access token."""
        async with self._token_lock:
            if (
                self._access_token
                and time.monotonic() < self._token_expires_at - _TOKEN_REFRESH_BUFFER
            ):
                return self._access_token

            try:
                resp = await self._auth_client.post(
                    _TOKEN_URL,
                    auth=(self._client_id, self._client_secret),
                    data={"grant_type": "client_credentials"},
                )
                if resp.status_code != 200:
                    logger.warning(
                        "Reddit token request failed with status {status}",
                        status=resp.status_code,
                    )
                    raise SourceSearchError(
                        self.platform.value,
                        f"OAuth token request failed (status={resp.status_code})",
                        status_code=resp.status_code,
                    )
                body = resp.json()
                self._access_token = body["access_token"]
                expires_in = int(body.get("expires_in", 3600))
                self._token_expires_at = time.monotonic() + expires_in
                logger.debug("Reddit OAuth token acquired, expires in {}s", expires_in)
                return self._access_token
            except httpx.HTTPError as exc:
                logger.warning("Reddit OAuth token request error: {exc}", exc=exc)
                raise SourceSearchError(
                    self.platform.value, f"OAuth token error: {exc}"
                ) from exc

    async def _search_single_query_oauth(
        self,
        resolved_query: _ResolvedQuery,
        limit: int,
    ) -> list[RawResult]:
        query = resolved_query.text
        token = await self._ensure_token()
        try:
            resp = await self._client.get(
                "/search",
                params={
                    "q": query,
                    "limit": min(limit, 25),
                    "sort": "relevance",
                    "t": "year",
                    "type": "link",
                },
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code == 401:
                self._access_token = None
                logger.warning(
                    "Reddit token expired mid-request for '{query}', will retry",
                    query=query,
                )
                raise SourceSearchError(
                    self.platform.value,
                    "OAuth token expired",
                    status_code=401,
                )
            if resp.status_code == 429:
                logger.warning("Reddit rate-limited for query '{query}'", query=query)
                raise SourceSearchError(
                    self.platform.value,
                    "Reddit rate limit exceeded",
                    status_code=429,
                )
            if resp.status_code != 200:
                logger.warning(
                    "Reddit API returned {status} for query '{query}'",
                    status=resp.status_code,
                    query=query,
                )
                raise SourceSearchError(
                    self.platform.value,
                    "Reddit API non-200 response",
                    status_code=resp.status_code,
                )

            data = resp.json()
            children = data.get("data", {}).get("children", [])
            result: list[RawResult] = []
            for child in children:
                post = child.get("data", {})
                built = self._build_raw_result_from_post(
                    post,
                    resolved_query=resolved_query,
                    auth_mode="oauth",
                )
                if built is not None:
                    result.append(built)
            return result
        except httpx.HTTPError as exc:
            logger.warning(
                "Reddit search failed for '{query}': {exc}", query=query, exc=exc
            )
            raise SourceSearchError(self.platform.value, str(exc)) from exc
        except ValueError as exc:
            logger.warning(
                "Reddit returned invalid JSON for '{query}': {exc}",
                query=query,
                exc=exc,
            )
            raise SourceSearchError(
                self.platform.value, "Invalid JSON response"
            ) from exc

    async def _search_single_query_public(
        self,
        resolved_query: _ResolvedQuery,
        limit: int,
    ) -> list[RawResult]:
        query = resolved_query.text
        try:
            resp = await self._public_client.get(
                _PUBLIC_SEARCH_URL,
                params={
                    "q": query,
                    "limit": min(limit, self._public_fallback_limit),
                    "sort": "relevance",
                    "t": "year",
                    "type": "link",
                },
            )
            if resp.status_code == 429:
                logger.warning(
                    "Reddit public fallback rate-limited for query '{query}'",
                    query=query,
                )
                raise SourceSearchError(
                    self.platform.value,
                    "Reddit public fallback rate limit exceeded",
                    status_code=429,
                )
            if resp.status_code != 200:
                logger.warning(
                    "Reddit public fallback returned {status} for query '{query}'",
                    status=resp.status_code,
                    query=query,
                )
                raise SourceSearchError(
                    self.platform.value,
                    "Reddit public fallback non-200 response",
                    status_code=resp.status_code,
                )

            data = resp.json()
            children = data.get("data", {}).get("children", [])
            result: list[RawResult] = []
            for child in children:
                post = child.get("data", {})
                built = self._build_raw_result_from_post(
                    post,
                    resolved_query=resolved_query,
                    auth_mode="public_fallback",
                )
                if built is not None:
                    result.append(built)
            return result
        except httpx.HTTPError as exc:
            logger.warning(
                "Reddit public fallback failed for '{query}': {exc}",
                query=query,
                exc=exc,
            )
            raise SourceSearchError(self.platform.value, str(exc)) from exc
        except ValueError as exc:
            logger.warning(
                "Reddit public fallback returned invalid JSON for '{query}': {exc}",
                query=query,
                exc=exc,
            )
            raise SourceSearchError(
                self.platform.value, "Invalid JSON response"
            ) from exc

    async def search(self, queries: list[str], limit: int = 10) -> list[RawResult]:
        """Search Reddit posts for each query and return combined, deduplicated results."""
        if not queries:
            return []
        resolved_queries = [
            resolved_query
            for query in queries
            if (resolved_query := _resolve_query(query)).text
        ]
        if not resolved_queries:
            return []

        use_public_fallback, fallback_reason = self._should_use_public_fallback()
        if not self.is_available() and not use_public_fallback:
            self._reset_search_diagnostics(fallback_reason=fallback_reason)
            if fallback_reason == "disabled_by_config":
                logger.info(
                    "Reddit search skipped because OAuth credentials are missing "
                    "and public fallback is disabled"
                )
            elif fallback_reason == "partial_credentials":
                logger.warning(
                    "Reddit search skipped because OAuth credentials are incomplete"
                )
            return []

        self._reset_search_diagnostics(
            used_public_fallback=use_public_fallback,
            fallback_reason=fallback_reason,
        )
        seen_ids: set[str] = set()
        max_concurrency = (
            1
            if use_public_fallback
            else (self._runtime_max_concurrent_queries or self._max_concurrent_queries)
        )
        semaphore = asyncio.Semaphore(max_concurrency)
        request_lock = asyncio.Lock()
        inter_request_delay = (
            self._public_fallback_delay_seconds
            if use_public_fallback
            else _INTER_REQUEST_DELAY
        )

        async def run_query(
            resolved_query: _ResolvedQuery,
        ) -> tuple[str, list[RawResult] | Exception]:
            async with semaphore:
                try:
                    async with request_lock:
                        if use_public_fallback:
                            result = await self._search_single_query_public(
                                resolved_query,
                                limit,
                            )
                        else:
                            result = await self._search_single_query_oauth(
                                resolved_query,
                                limit,
                            )
                        await asyncio.sleep(inter_request_delay)
                    return resolved_query.text, result
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
                post_id = str(result.raw_data.get("post_id", ""))
                if not post_id or post_id in seen_ids:
                    continue
                seen_ids.add(post_id)
                results.append(result)
        if failed_queries and results:
            self._last_search_diagnostics = {
                "partial_failure": True,
                "failed_queries": failed_queries,
                "timed_out_queries": timed_out_queries,
                "used_public_fallback": use_public_fallback,
                "fallback_reason": fallback_reason,
            }
            return results
        if failed_queries and first_error is not None:
            raise first_error
        return results

    async def close(self) -> None:
        await self._client.aclose()
        await self._public_client.aclose()
        await self._auth_client.aclose()


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
