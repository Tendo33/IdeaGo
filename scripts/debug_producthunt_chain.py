"""Local probe script for Product Hunt source chain.

Usage:
    uv run python scripts/debug_producthunt_chain.py --query "api monitoring"
"""

from __future__ import annotations

import argparse
import asyncio
import json
import traceback
from typing import Any

from ideago.api.dependencies import get_orchestrator
from ideago.config.settings import get_settings
from ideago.models.research import Platform, RawResult
from ideago.sources.errors import SourceSearchError
from ideago.sources.producthunt_source import ProductHuntSource


class DebugProductHuntSource(ProductHuntSource):
    """Product Hunt source with lightweight runtime trace hooks."""

    def __init__(
        self,
        *,
        dev_token: str,
        posted_after_days: int,
        timeout: int,
        max_concurrent_queries: int,
    ) -> None:
        super().__init__(
            dev_token=dev_token,
            posted_after_days=posted_after_days,
            timeout=timeout,
            max_concurrent_queries=max_concurrent_queries,
        )
        self.graphql_calls: list[dict[str, Any]] = []
        self.topic_slugs: list[str] = []
        self.posts_by_topic: dict[str, int] = {}

    async def _graphql(
        self,
        query: str,
        variables: dict[str, Any],
    ) -> dict[str, Any]:
        operation = "unknown"
        if "query Topics" in query:
            operation = "topics"
        elif "query Posts" in query:
            operation = "posts"
        self.graphql_calls.append(
            {
                "operation": operation,
                "variables": variables,
            }
        )
        return await super()._graphql(query, variables)

    async def _find_topic_slugs(self, query: str, first: int = 5) -> list[str]:
        slugs = await super()._find_topic_slugs(query=query, first=first)
        self.topic_slugs.extend(slugs)
        return slugs

    async def _fetch_posts_by_topic(
        self,
        topic_slug: str,
        posted_after_iso: str,
        page_size: int,
        max_pages: int,
    ) -> list[dict[str, Any]]:
        posts = await super()._fetch_posts_by_topic(
            topic_slug=topic_slug,
            posted_after_iso=posted_after_iso,
            page_size=page_size,
            max_pages=max_pages,
        )
        self.posts_by_topic[topic_slug] = len(posts)
        return posts


def _mask_token(token: str) -> str:
    token = token.strip()
    if not token:
        return "<empty>"
    if len(token) <= 8:
        return f"{token[:2]}***{token[-2:]}"
    return f"{token[:4]}***{token[-4:]}"


def _serialize_result(raw: RawResult) -> dict[str, Any]:
    return {
        "title": raw.title,
        "description": raw.description,
        "url": raw.url,
        "platform": raw.platform.value,
        "raw_data": raw.raw_data,
    }


async def run_probe(args: argparse.Namespace) -> int:
    settings = get_settings()
    orchestrator = get_orchestrator()
    availability = orchestrator.get_source_availability()
    all_sources = orchestrator.get_all_sources()
    producthunt_registered = any(
        source.platform == Platform.PRODUCT_HUNT for source in all_sources
    )

    print("== Product Hunt chain diagnostics ==")
    print(
        json.dumps(
            {
                "producthunt_registered": producthunt_registered,
                "source_availability": availability,
                "settings": {
                    "producthunt_dev_token": _mask_token(
                        settings.producthunt_dev_token
                    ),
                    "producthunt_posted_after_days": settings.producthunt_posted_after_days,
                    "source_timeout_seconds": settings.source_timeout_seconds,
                    "source_query_concurrency": settings.source_query_concurrency,
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    probe_source = DebugProductHuntSource(
        dev_token=settings.producthunt_dev_token,
        posted_after_days=args.posted_after_days
        or settings.producthunt_posted_after_days,
        timeout=args.timeout or settings.source_timeout_seconds,
        max_concurrent_queries=settings.source_query_concurrency,
    )

    try:
        print("\n== Running Product Hunt search ==")
        print(
            json.dumps(
                {"queries": args.query, "limit": args.limit},
                ensure_ascii=False,
                indent=2,
            )
        )

        results = await probe_source.search(args.query, limit=args.limit)
        payload = {
            "graphql_call_count": len(probe_source.graphql_calls),
            "topic_slugs_found": list(dict.fromkeys(probe_source.topic_slugs)),
            "posts_by_topic": probe_source.posts_by_topic,
            "final_result_count": len(results),
            "sample_results": [
                _serialize_result(item) for item in results[: args.sample_size]
            ],
        }
        print("\n== Probe result ==")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    except SourceSearchError as exc:
        print("\n!! Product Hunt source raised SourceSearchError !!")
        print(str(exc))
        print("\n== Trace context ==")
        print(
            json.dumps(
                {
                    "graphql_call_count": len(probe_source.graphql_calls),
                    "topic_slugs_found": list(dict.fromkeys(probe_source.topic_slugs)),
                    "posts_by_topic": probe_source.posts_by_topic,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2
    except Exception as exc:  # noqa: BLE001
        print("\n!! Unexpected exception !!")
        print(f"{type(exc).__name__}: {exc}")
        print(traceback.format_exc())
        return 3
    finally:
        await probe_source.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Debug Product Hunt source chain and print live payload samples."
    )
    parser.add_argument(
        "--query",
        action="append",
        default=[],
        help="Search query (repeatable). Example: --query 'api monitoring'",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Max results per query group.",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=5,
        help="How many final results to print.",
    )
    parser.add_argument(
        "--posted-after-days",
        type=int,
        default=0,
        help="Override Product Hunt freshness window (days). 0 means use settings.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=0,
        help="Override Product Hunt HTTP timeout (seconds). 0 means use settings.",
    )
    args = parser.parse_args()
    if not args.query:
        args.query = ["api monitoring", "developer tools"]
    return args


def main() -> None:
    args = parse_args()
    raise SystemExit(asyncio.run(run_probe(args)))


if __name__ == "__main__":
    main()
