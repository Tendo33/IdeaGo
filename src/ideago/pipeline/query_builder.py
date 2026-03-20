"""Deterministic per-platform query generation from semantic intent.

Takes an Intent (keywords + app_type) and produces optimized search queries
tailored to each platform's API semantics — no extra LLM calls required.
"""

from __future__ import annotations

import re
from itertools import combinations
from typing import Any

from ideago.models.research import Intent, Platform

_MAX_QUERIES_PER_PLATFORM = 5
_MAX_JOINED_KEYWORDS = 4

_APP_TYPE_HINTS: dict[str, dict[str, Any]] = {
    "browser-extension": {
        "github_extra": ["chrome extension"],
        "appstore_genre": ["productivity"],
        "ph_topics": ["browser-extensions", "chrome-extensions", "productivity"],
        "hn_extra": ["chrome extension"],
        "tavily_phrasing": "browser extension",
        "reddit_extra": ["extension", "addon"],
    },
    "mobile": {
        "github_extra": ["mobile app"],
        "appstore_genre": ["lifestyle", "utilities"],
        "ph_topics": ["mobile-apps", "ios", "android"],
        "hn_extra": ["mobile app"],
        "tavily_phrasing": "mobile app",
        "reddit_extra": ["app", "mobile"],
    },
    "web": {
        "github_extra": ["web app", "saas"],
        "appstore_genre": [],
        "ph_topics": ["saas", "web-app", "productivity"],
        "hn_extra": ["web app", "saas"],
        "tavily_phrasing": "web application",
        "reddit_extra": ["webapp", "saas"],
    },
    "desktop": {
        "github_extra": ["desktop app"],
        "appstore_genre": ["utilities"],
        "ph_topics": ["mac", "windows", "desktop-apps"],
        "hn_extra": ["desktop app"],
        "tavily_phrasing": "desktop application",
        "reddit_extra": ["desktop", "software"],
    },
    "cli": {
        "github_extra": ["cli tool", "command line"],
        "appstore_genre": [],
        "ph_topics": ["developer-tools", "command-line-tools"],
        "hn_extra": ["cli tool"],
        "tavily_phrasing": "command line tool",
        "reddit_extra": ["cli", "terminal"],
    },
    "api": {
        "github_extra": ["api", "sdk"],
        "appstore_genre": [],
        "ph_topics": ["developer-tools", "apis"],
        "hn_extra": ["api", "developer tool"],
        "tavily_phrasing": "API service",
        "reddit_extra": ["api", "sdk"],
    },
}

_DEFAULT_HINTS: dict[str, Any] = {
    "github_extra": [],
    "appstore_genre": ["productivity"],
    "ph_topics": ["productivity", "developer-tools"],
    "hn_extra": [],
    "tavily_phrasing": "tool",
    "reddit_extra": [],
}


def build_queries(platform: Platform, intent: Intent) -> list[str]:
    """Generate platform-optimized search queries from semantic intent.

    Args:
        platform: Target data source platform.
        intent: Parsed user intent with keywords and app_type.

    Returns:
        Deduplicated list of search query strings, capped at _MAX_QUERIES_PER_PLATFORM.
    """
    keywords = _clean_keywords(intent.keywords_en)
    if not keywords:
        return []

    hints = _APP_TYPE_HINTS.get(intent.app_type.lower(), _DEFAULT_HINTS)
    builders = {
        Platform.GITHUB: _build_github,
        Platform.APPSTORE: _build_appstore,
        Platform.PRODUCT_HUNT: _build_producthunt,
        Platform.HACKERNEWS: _build_hackernews,
        Platform.TAVILY: _build_tavily,
        Platform.REDDIT: _build_reddit,
    }
    builder_fn = builders.get(platform)
    if builder_fn is None:
        return _build_generic(keywords)

    raw = builder_fn(keywords, intent, hints)
    return _dedup_and_cap(raw)


def _build_github(
    keywords: list[str],
    intent: Intent,
    hints: dict[str, Any],
) -> list[str]:
    queries: list[str] = []

    joined = " ".join(keywords[:_MAX_JOINED_KEYWORDS])
    if joined:
        queries.append(joined)

    topic_parts = [f"topic:{_slugify(kw)}" for kw in keywords[:3]]
    if topic_parts:
        queries.append(" ".join(topic_parts))

    for extra in hints.get("github_extra", []):
        combined = f"{keywords[0]} {extra}" if keywords else extra
        queries.append(combined)

    return queries


def _build_appstore(
    keywords: list[str],
    intent: Intent,
    hints: dict[str, Any],
) -> list[str]:
    queries: list[str] = []

    for kw in keywords[:2]:
        queries.append(kw)

    for genre in hints.get("appstore_genre", []):
        queries.append(genre)

    for pair in combinations(keywords[:3], 2):
        queries.append(" ".join(pair))

    return queries


def _build_producthunt(
    keywords: list[str],
    intent: Intent,
    hints: dict[str, Any],
) -> list[str]:
    queries: list[str] = []

    for topic in hints.get("ph_topics", []):
        queries.append(topic)

    for kw in keywords[:2]:
        queries.append(kw)

    return queries


def _build_hackernews(
    keywords: list[str],
    intent: Intent,
    hints: dict[str, Any],
) -> list[str]:
    queries: list[str] = []

    joined = " ".join(keywords[:_MAX_JOINED_KEYWORDS])
    if joined:
        queries.append(joined)

    for pair in combinations(keywords[:4], 2):
        queries.append(" ".join(pair))

    for extra in hints.get("hn_extra", []):
        queries.append(extra)

    return queries


def _build_tavily(
    keywords: list[str],
    intent: Intent,
    hints: dict[str, Any],
) -> list[str]:
    queries: list[str] = []
    joined = " ".join(keywords[:_MAX_JOINED_KEYWORDS])

    if joined:
        queries.append(f"{joined} alternative")
        queries.append(f"{joined} competitor")

    phrasing = hints.get("tavily_phrasing", "tool")
    queries.append(f"best {joined} {phrasing}")

    if intent.keywords_zh:
        zh_joined = " ".join(intent.keywords_zh[:3])
        queries.append(f"{zh_joined} 竞品")

    return queries


def _build_reddit(
    keywords: list[str],
    intent: Intent,
    hints: dict[str, Any],
) -> list[str]:
    queries: list[str] = []
    joined = " ".join(keywords[:_MAX_JOINED_KEYWORDS])

    if joined:
        queries.append(f"{joined} alternative")
        queries.append(f"{joined} recommend")

    for pair in combinations(keywords[:4], 2):
        queries.append(" ".join(pair))

    for extra in hints.get("reddit_extra", []):
        queries.append(f"{keywords[0]} {extra}" if keywords else extra)

    return queries


def _build_generic(keywords: list[str]) -> list[str]:
    joined = " ".join(keywords[:_MAX_JOINED_KEYWORDS])
    return [joined] if joined else []


def _clean_keywords(keywords: list[str]) -> list[str]:
    """Normalize and deduplicate keywords."""
    seen: set[str] = set()
    result: list[str] = []
    for kw in keywords:
        normalized = kw.strip().lower()
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result


def _slugify(text: str) -> str:
    """Convert text to GitHub topic-style slug (lowercase, hyphens)."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower().strip())
    return slug.strip("-")


def _dedup_and_cap(queries: list[str]) -> list[str]:
    """Deduplicate queries preserving order, cap at max count."""
    seen: set[str] = set()
    result: list[str] = []
    for query in queries:
        normalized = query.strip()
        key = normalized.lower()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(normalized)
    return result[:_MAX_QUERIES_PER_PLATFORM]
