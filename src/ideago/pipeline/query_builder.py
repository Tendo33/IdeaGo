"""Deterministic per-platform query generation from semantic intent.

Takes an Intent (keywords + app_type) and produces optimized search queries
tailored to each platform's API semantics — no extra LLM calls required.
"""

from __future__ import annotations

import re
from collections import OrderedDict
from itertools import combinations
from typing import Any

from ideago.models.research import Intent, Platform, QueryPlan
from ideago.pipeline.query_planning import (
    adapt_query_plan_for_platform,
)

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


class QueryString(str):
    """String-compatible query value that preserves its exact source family."""

    __slots__ = ("query_family",)
    query_family: str

    def __new__(cls, value: str, *, query_family: str) -> QueryString:
        obj = super().__new__(cls, value)
        obj.query_family = query_family
        return obj


def infer_query_family(query: str) -> str:
    """Infer the research-intent family for a flat query string."""
    preserved_family = getattr(query, "query_family", None)
    if isinstance(preserved_family, str) and preserved_family:
        return preserved_family

    normalized = query.strip().lower()
    if not normalized:
        return "competitor_discovery"
    if "switch from" in normalized or "migration" in normalized:
        return "migration_discovery"
    if "pricing" in normalized or "price" in normalized or "paid" in normalized:
        return "commercial_discovery"
    if "pain" in normalized or "frustrat" in normalized or "complaint" in normalized:
        return "pain_discovery"
    if "alternative" in normalized:
        return "alternative_discovery"
    if "workflow" in normalized or "recommend" in normalized:
        return "workflow_discovery"
    if "show hn" in normalized or "ask hn" in normalized:
        return "discussion_discovery"
    if "topic:" in normalized:
        return "ecosystem_discovery"
    if normalized in set(_DEFAULT_HINTS["ph_topics"]) or "-apps" in normalized:
        return "launch_discovery"
    if (
        "competitor" in normalized
        or "竞品" in normalized
        or normalized.startswith("best ")
    ):
        return "competitor_discovery"
    return "competitor_discovery"


def build_query_families(
    platform: Platform,
    intent: Intent,
    *,
    query_plan: QueryPlan | None = None,
) -> dict[str, list[QueryString]]:
    """Build deterministic query groups keyed by research intent family."""
    keywords = _clean_keywords(intent.keywords_en)
    if not keywords:
        return {}

    hints = _APP_TYPE_HINTS.get(intent.app_type.lower(), _DEFAULT_HINTS)
    builders = {
        Platform.GITHUB: _build_github_families,
        Platform.APPSTORE: _build_appstore_families,
        Platform.PRODUCT_HUNT: _build_producthunt_families,
        Platform.HACKERNEWS: _build_hackernews_families,
        Platform.TAVILY: _build_tavily_families,
        Platform.REDDIT: _build_reddit_families,
    }
    builder_fn = builders.get(platform)
    if builder_fn is None:
        generic_query = _build_generic(keywords)
        return (
            {
                "competitor_discovery": _dedup_and_cap(
                    generic_query, "competitor_discovery"
                )
            }
            if generic_query
            else {}
        )

    raw_families = builder_fn(keywords, intent, hints)
    planned_families = OrderedDict()
    if query_plan is not None:
        planned_families = _normalize_planned_families(
            adapt_query_plan_for_platform(platform, query_plan, intent)
        )
    merged_families = _merge_query_families(planned_families, raw_families)
    return {
        family: deduped_queries
        for family, queries in merged_families.items()
        if (deduped_queries := _dedup_and_cap(queries, family))
    }


def build_queries(
    platform: Platform,
    intent: Intent,
    *,
    query_plan: QueryPlan | None = None,
) -> list[QueryString]:
    """Generate platform-optimized search queries from semantic intent.

    Args:
        platform: Target data source platform.
        intent: Parsed user intent with keywords and app_type.

    Returns:
        Deduplicated list of search query strings, capped at _MAX_QUERIES_PER_PLATFORM.
    """
    families = build_query_families(platform, intent, query_plan=query_plan)
    return _flatten_families_with_cap(
        families,
        max_queries=_MAX_QUERIES_PER_PLATFORM,
    )


def _build_github_families(
    keywords: list[str],
    intent: Intent,
    hints: dict[str, Any],
) -> OrderedDict[str, list[str]]:
    queries: OrderedDict[str, list[str]] = OrderedDict()

    joined = " ".join(keywords[:_MAX_JOINED_KEYWORDS])
    competitor_queries: list[str] = []
    if joined:
        competitor_queries.append(joined)

    topic_parts = [f"topic:{_slugify(kw)}" for kw in keywords[:3]]
    workflow_queries: list[str] = []
    if topic_parts:
        workflow_queries.append(" ".join(topic_parts))

    ecosystem_queries: list[str] = []
    for extra in hints.get("github_extra", []):
        combined = f"{keywords[0]} {extra}" if keywords else extra
        ecosystem_queries.append(combined)

    queries["competitor_discovery"] = competitor_queries
    queries["workflow_discovery"] = workflow_queries
    queries["ecosystem_discovery"] = ecosystem_queries
    return queries


def _build_appstore_families(
    keywords: list[str],
    intent: Intent,
    hints: dict[str, Any],
) -> OrderedDict[str, list[str]]:
    queries: OrderedDict[str, list[str]] = OrderedDict()
    competitor_queries: list[str] = []

    for kw in keywords[:2]:
        competitor_queries.append(kw)

    workflow_queries: list[str] = []
    for genre in hints.get("appstore_genre", []):
        workflow_queries.append(genre)

    pain_queries: list[str] = []
    for kw in keywords[:2]:
        # Keep both terms in one primary phrase so it survives global cap pressure.
        pain_queries.append(f"{kw} review problem")
        pain_queries.append(f"{kw} review")
        pain_queries.append(f"{kw} problem")
    for pair in combinations(keywords[:3], 2):
        pain_queries.append(" ".join(pair))

    queries["competitor_discovery"] = competitor_queries
    queries["workflow_discovery"] = workflow_queries
    queries["pain_discovery"] = pain_queries
    return queries


def _build_producthunt_families(
    keywords: list[str],
    intent: Intent,
    hints: dict[str, Any],
) -> OrderedDict[str, list[str]]:
    queries: OrderedDict[str, list[str]] = OrderedDict()
    launch_queries: list[str] = []

    for topic in hints.get("ph_topics", []):
        launch_queries.append(topic)

    competitor_queries: list[str] = []
    for kw in keywords[:2]:
        competitor_queries.append(kw)

    positioning_queries: list[str] = []
    for kw in keywords[:2]:
        positioning_queries.append(f"{kw} positioning")
        positioning_queries.append(f"{kw} launch")

    queries["launch_discovery"] = launch_queries
    queries["competitor_discovery"] = competitor_queries
    queries["positioning_discovery"] = positioning_queries
    return queries


def _build_hackernews_families(
    keywords: list[str],
    intent: Intent,
    hints: dict[str, Any],
) -> OrderedDict[str, list[str]]:
    queries: OrderedDict[str, list[str]] = OrderedDict()
    discussion_queries: list[str] = []

    joined = " ".join(keywords[:_MAX_JOINED_KEYWORDS])
    if joined:
        discussion_queries.append(joined)

    workflow_queries: list[str] = []
    for pair in combinations(keywords[:4], 2):
        workflow_queries.append(" ".join(pair))

    competitor_queries: list[str] = []
    for extra in hints.get("hn_extra", []):
        competitor_queries.append(extra)

    queries["discussion_discovery"] = discussion_queries
    queries["workflow_discovery"] = workflow_queries
    queries["competitor_discovery"] = competitor_queries
    return queries


def _build_tavily_families(
    keywords: list[str],
    intent: Intent,
    hints: dict[str, Any],
) -> OrderedDict[str, list[str]]:
    queries: OrderedDict[str, list[str]] = OrderedDict()
    joined = " ".join(keywords[:_MAX_JOINED_KEYWORDS])

    competitor_queries: list[str] = []
    alternative_queries: list[str] = []
    pain_queries: list[str] = []
    workflow_queries: list[str] = []
    commercial_queries: list[str] = []

    if joined:
        alternative_queries.append(f"{joined} alternative")
        # Keep both "best" and "competitor" semantics in the first slot so
        # build_queries() still preserves them when capped.
        competitor_queries.append(f"best {joined} competitor")
        competitor_queries.append(f"{joined} competitor")
        pain_queries.append(f"{joined} pain points")
        workflow_queries.append(f"{joined} workflow")
        commercial_queries.append(f"{joined} pricing")

    if intent.keywords_zh:
        zh_joined = " ".join(intent.keywords_zh[:3])
        competitor_queries.insert(0, f"{zh_joined} 竞品")

    queries["competitor_discovery"] = competitor_queries
    queries["alternative_discovery"] = alternative_queries
    queries["pain_discovery"] = pain_queries
    queries["workflow_discovery"] = workflow_queries
    queries["commercial_discovery"] = commercial_queries
    return queries


def _build_reddit_families(
    keywords: list[str],
    intent: Intent,
    hints: dict[str, Any],
) -> OrderedDict[str, list[str]]:
    queries: OrderedDict[str, list[str]] = OrderedDict()
    joined = " ".join(keywords[:_MAX_JOINED_KEYWORDS])

    alternative_queries: list[str] = []
    pain_queries: list[str] = []
    migration_queries: list[str] = []
    workflow_queries: list[str] = []

    if joined:
        alternative_queries.append(f"{joined} alternative")
        pain_queries.append(f"{joined} pain")
        workflow_queries.append(f"{joined} recommend")
        migration_queries.append(f"switch from {keywords[0]}")

    for pair in combinations(keywords[:4], 2):
        workflow_queries.append(" ".join(pair))

    for extra in hints.get("reddit_extra", []):
        pain_queries.append(f"{keywords[0]} {extra}" if keywords else extra)

    queries["pain_discovery"] = pain_queries
    queries["alternative_discovery"] = alternative_queries
    queries["migration_discovery"] = migration_queries
    queries["workflow_discovery"] = workflow_queries
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


def _dedup_and_cap(
    queries: list[str | QueryString],
    family: str,
) -> list[QueryString]:
    """Deduplicate queries preserving order, cap at max count."""
    seen: set[str] = set()
    result: list[QueryString] = []
    for query in queries:
        normalized_query = _normalize_query(query, family=family)
        if normalized_query is None:
            continue

        normalized = str(normalized_query)
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(normalized_query)
    return result[:_MAX_QUERIES_PER_PLATFORM]


def _flatten_families_with_cap(
    families: dict[str, list[QueryString]],
    *,
    max_queries: int,
) -> list[QueryString]:
    """Flatten query families while preserving family representation under cap."""
    if max_queries <= 0:
        return []
    if not families:
        return []

    ordered_families = [
        (name, queries) for name, queries in families.items() if queries
    ]
    if not ordered_families:
        return []

    result: list[QueryString] = []
    seen: set[str] = set()
    family_offsets: dict[str, int] = {}

    # Pass 1: ensure each family gets at least one query when cap allows.
    for family_name, queries in ordered_families:
        family_offsets[family_name] = 1
        if len(result) >= max_queries:
            break
        candidate = _normalize_query(queries[0], family=family_name)
        if candidate is None:
            continue

        candidate_text = str(candidate)
        key = candidate_text.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(candidate)

    # Pass 2: round-robin fill remaining slots deterministically.
    while len(result) < max_queries:
        progressed = False
        for family_name, queries in ordered_families:
            offset = family_offsets.get(family_name, 0)
            if offset >= len(queries):
                continue
            family_offsets[family_name] = offset + 1
            candidate = _normalize_query(queries[offset], family=family_name)
            if candidate is None:
                continue

            candidate_text = str(candidate)
            key = candidate_text.lower()
            if key in seen:
                continue
            seen.add(key)
            result.append(candidate)
            progressed = True
            if len(result) >= max_queries:
                break
        if not progressed:
            break
    return result


def _normalize_query(
    query: str | QueryString,
    *,
    family: str,
) -> QueryString | None:
    normalized = str(query).strip()
    if not normalized:
        return None

    query_family = getattr(query, "query_family", None) or family
    return QueryString(normalized, query_family=query_family)


def _normalize_planned_families(
    families: dict[str, list[str]],
) -> OrderedDict[str, list[QueryString]]:
    normalized: OrderedDict[str, list[QueryString]] = OrderedDict()
    for family, queries in families.items():
        normalized[family] = [
            QueryString(query.strip(), query_family=family)
            for query in queries
            if query.strip()
        ]
    return normalized


def _merge_query_families(
    planned_families: OrderedDict[str, list[QueryString]],
    legacy_families: OrderedDict[str, list[str]],
) -> OrderedDict[str, list[str | QueryString]]:
    merged: OrderedDict[str, list[str | QueryString]] = OrderedDict()
    for family_name, planned_queries in planned_families.items():
        merged[family_name] = list(planned_queries)
    for family_name, legacy_queries in legacy_families.items():
        existing: list[str | QueryString] = merged.setdefault(family_name, [])
        existing.extend(legacy_queries)
    return merged
