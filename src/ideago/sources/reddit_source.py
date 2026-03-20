"""Reddit data source — searches via Reddit OAuth2 API.

通过 Reddit OAuth2 API 搜索社区讨论帖，用于竞品发现和需求验证。
需要在 https://www.reddit.com/prefs/apps 创建 "script" 类型应用获取凭证。
"""

from __future__ import annotations

import asyncio
import time

import httpx

from ideago.models.research import Platform, RawResult
from ideago.observability.log_config import get_logger
from ideago.sources.errors import SourceSearchError
from ideago.utils.text_utils import decode_entities_and_strip_html

logger = get_logger(__name__)

_APP_USER_AGENT = "IdeaGo/0.3 (competitor-research-engine)"
_TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
_TOKEN_REFRESH_BUFFER = 60
_INTER_REQUEST_DELAY = 1.0


class RedditSource:
    """Searches Reddit posts using the OAuth2 Application-Only flow."""

    _BASE_URL = "https://oauth.reddit.com"

    def __init__(
        self,
        client_id: str = "",
        client_secret: str = "",
        timeout: int = 30,
        max_concurrent_queries: int = 2,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._client = httpx.AsyncClient(
            base_url=self._BASE_URL,
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
        }

    @property
    def platform(self) -> Platform:
        return Platform.REDDIT

    def is_available(self) -> bool:
        return bool(self._client_id and self._client_secret)

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

    async def _search_single_query(self, query: str, limit: int) -> list[RawResult]:
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
                post_id = post.get("id", "")
                if not post_id:
                    continue

                title = post.get("title", "")
                selftext = decode_entities_and_strip_html(post.get("selftext", ""))
                permalink = post.get("permalink", "")
                url = f"https://www.reddit.com{permalink}" if permalink else ""

                result.append(
                    RawResult(
                        title=title,
                        description=selftext[:500] if selftext else "",
                        url=url,
                        platform=Platform.REDDIT,
                        raw_data={
                            "post_id": post_id,
                            "subreddit": post.get("subreddit", ""),
                            "score": post.get("score", 0),
                            "num_comments": post.get("num_comments", 0),
                            "created_utc": post.get("created_utc", 0),
                            "link_url": post.get("url", ""),
                            "upvote_ratio": post.get("upvote_ratio", 0),
                        },
                    )
                )
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

    async def search(self, queries: list[str], limit: int = 10) -> list[RawResult]:
        """Search Reddit posts for each query and return combined, deduplicated results."""
        if not queries or not self.is_available():
            return []

        self._last_search_diagnostics = {
            "partial_failure": False,
            "failed_queries": [],
            "timed_out_queries": [],
        }
        seen_ids: set[str] = set()
        max_concurrency = (
            self._runtime_max_concurrent_queries or self._max_concurrent_queries
        )
        semaphore = asyncio.Semaphore(max_concurrency)
        request_lock = asyncio.Lock()

        async def run_query(query: str) -> tuple[str, list[RawResult] | Exception]:
            async with semaphore:
                try:
                    async with request_lock:
                        result = await self._search_single_query(query, limit)
                        await asyncio.sleep(_INTER_REQUEST_DELAY)
                    return query, result
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
            }
            return results
        if failed_queries and first_error is not None:
            raise first_error
        return results

    async def close(self) -> None:
        await self._client.aclose()
        await self._auth_client.aclose()
