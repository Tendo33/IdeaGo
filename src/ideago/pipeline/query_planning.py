"""Intent-aware query planning and rewriting before platform adaptation."""

from __future__ import annotations

import asyncio
import json
from collections import OrderedDict
from typing import Any

from ideago.llm.chat_model import ChatModelClient
from ideago.llm.invoke_helpers import invoke_json_with_optional_meta
from ideago.llm.prompt_loader import load_prompt
from ideago.models.research import (
    Intent,
    Platform,
    QueryFamily,
    QueryGroup,
    QueryPlan,
    QueryRewrite,
)
from ideago.observability.log_config import get_logger

logger = get_logger(__name__)
_MAX_REWRITES_PER_GROUP = 4
_MAX_GROUPS = 6
_MIN_GROUPS = 2
_QUERY_FAMILY_ALIASES = {
    "adjacent_analogue": QueryFamily.ADJACENT_ANALOGY.value,
    "workflow_interface_variant": QueryFamily.WORKFLOW_INTERFACE.value,
}


class QueryPlanner:
    """LLM-first query planner with deterministic fallback."""

    def __init__(self, llm: ChatModelClient) -> None:
        self._llm = llm
        self._llm_metrics_by_task: dict[int, dict[str, Any]] = {}

    async def plan(self, intent: Intent) -> QueryPlan:
        """Generate a typed query plan, falling back to deterministic rules."""
        fallback_plan = build_query_plan(intent)
        try:
            prompt = load_prompt(
                "query_planning_rewriting",
                intent_json=json.dumps(
                    intent.model_dump(mode="json"), ensure_ascii=False
                ),
            )
            data, llm_metrics = await invoke_json_with_optional_meta(
                llm=self._llm,
                prompt=prompt,
                system="You are a search strategist. Return only valid JSON.",
            )
            self._store_metrics_for_current_task(llm_metrics)
            normalized_data = _normalize_query_plan_payload(data)
            normalized = _normalize_query_plan(
                QueryPlan.model_validate(normalized_data),
                fallback_plan=fallback_plan,
            )
            if normalized.query_groups:
                return normalized
        except Exception as exc:  # noqa: BLE001
            logger.warning("Query planner LLM fallback engaged: {}", exc)
        return fallback_plan

    def pop_llm_metrics_for_current_task(self) -> dict[str, Any]:
        task = asyncio.current_task()
        if task is None:
            return {}
        return self._llm_metrics_by_task.pop(id(task), {})

    def _store_metrics_for_current_task(self, metrics: dict[str, Any]) -> None:
        task = asyncio.current_task()
        if task is None:
            return
        self._llm_metrics_by_task[id(task)] = metrics


def build_query_plan(intent: Intent) -> QueryPlan:
    """Create a typed query plan from intent anchors, comparisons, and keywords."""
    anchor_terms = _dedupe_preserve_order(intent.exact_entities) or _fallback_anchors(
        intent
    )
    comparison_anchors = _dedupe_preserve_order(intent.comparison_anchors)
    keywords = _clean_keywords(intent.keywords_en)

    groups: list[QueryGroup] = []
    if anchor_terms:
        groups.append(
            QueryGroup(
                family=QueryFamily.DIRECT_COMPETITOR,
                anchor_terms=anchor_terms,
                comparison_anchors=comparison_anchors,
                rewritten_queries=_build_direct_competitor_rewrites(
                    anchor_terms=anchor_terms,
                    keywords=keywords,
                ),
            )
        )
        groups.append(
            QueryGroup(
                family=QueryFamily.WORKFLOW_INTERFACE,
                anchor_terms=anchor_terms,
                comparison_anchors=comparison_anchors,
                rewritten_queries=_build_workflow_interface_rewrites(
                    anchor_terms=anchor_terms,
                    keywords=keywords,
                ),
            )
        )
    if comparison_anchors:
        groups.append(
            QueryGroup(
                family=QueryFamily.ADJACENT_ANALOGY,
                anchor_terms=anchor_terms,
                comparison_anchors=comparison_anchors,
                rewritten_queries=_build_adjacent_analogy_rewrites(
                    anchor_terms=anchor_terms,
                    comparison_anchors=comparison_anchors,
                ),
            )
        )

    if keywords:
        groups.append(
            QueryGroup(
                family=QueryFamily.PAIN_DISCOVERY,
                anchor_terms=anchor_terms,
                comparison_anchors=comparison_anchors,
                rewritten_queries=_build_generic_rewrites(
                    family=QueryFamily.PAIN_DISCOVERY,
                    base_terms=anchor_terms or keywords[:1],
                    suffixes=["pain points", "friction", "complaints"],
                    purpose="Find recurring user pain signals around the product shape.",
                ),
            )
        )
        groups.append(
            QueryGroup(
                family=QueryFamily.COMMERCIAL_DISCOVERY,
                anchor_terms=anchor_terms,
                comparison_anchors=comparison_anchors,
                rewritten_queries=_build_generic_rewrites(
                    family=QueryFamily.COMMERCIAL_DISCOVERY,
                    base_terms=anchor_terms or keywords[:1],
                    suffixes=["pricing", "paid plan", "buying intent"],
                    purpose="Find demand and monetization evidence.",
                ),
            )
        )
        groups.append(
            QueryGroup(
                family=QueryFamily.DISCUSSION_DISCOVERY,
                anchor_terms=anchor_terms,
                comparison_anchors=comparison_anchors,
                rewritten_queries=_build_generic_rewrites(
                    family=QueryFamily.DISCUSSION_DISCOVERY,
                    base_terms=anchor_terms or keywords[:1],
                    suffixes=["discussion", "recommend", "review"],
                    purpose="Find discussion and recommendation threads.",
                ),
            )
        )

    return _normalize_query_plan(
        QueryPlan(query_groups=[group for group in groups if group.rewritten_queries]),
        fallback_plan=None,
    )


def adapt_query_plan_for_platform(
    platform: Platform,
    plan: QueryPlan,
    intent: Intent,
) -> dict[str, list[str]]:
    """Translate planning groups into legacy platform query families."""
    families: OrderedDict[str, list[str]] = OrderedDict()
    keywords = _clean_keywords(intent.keywords_en)

    for group in plan.query_groups:
        for rewrite in group.rewritten_queries:
            family_name = _map_family_to_platform_bucket(platform, group.family)
            if not family_name:
                continue
            platform_query = _adapt_rewrite_for_platform(
                platform=platform,
                rewrite_query=rewrite.query,
                anchor_terms=group.anchor_terms,
                keywords=keywords,
            )
            if not platform_query:
                continue
            families.setdefault(family_name, []).append(platform_query)

    return families


def build_plan_family_coverage(plan: QueryPlan) -> dict[str, int]:
    """Summarize query-plan family coverage for observability."""
    coverage: dict[str, int] = {}
    for group in plan.query_groups:
        family = group.family.value
        coverage[family] = coverage.get(family, 0) + 1
    return coverage


def build_plan_anchor_coverage(plan: QueryPlan) -> dict[str, list[str]]:
    """Summarize preserved anchors for observability and downstream reporting."""
    exact_entities = _dedupe_preserve_order(
        [anchor for group in plan.query_groups for anchor in group.anchor_terms]
    )
    comparison_anchors = _dedupe_preserve_order(
        [anchor for group in plan.query_groups for anchor in group.comparison_anchors]
    )
    return {
        "exact_entities": exact_entities,
        "comparison_anchors": comparison_anchors,
    }


def _fallback_anchors(intent: Intent) -> list[str]:
    if intent.keywords_en:
        return [intent.keywords_en[0]]
    return []


def _build_direct_competitor_rewrites(
    *,
    anchor_terms: list[str],
    keywords: list[str],
) -> list[QueryRewrite]:
    anchor = anchor_terms[0]
    keyword = keywords[0] if keywords else "tool"
    candidates = [
        f'"{anchor}" {keyword}',
        f"{anchor} visual editor",
        f"{anchor} gui",
        f"{anchor} interface",
    ]
    return _make_rewrites(
        QueryFamily.DIRECT_COMPETITOR,
        candidates,
        "Find direct products built around the exact anchor entity.",
    )


def _build_workflow_interface_rewrites(
    *,
    anchor_terms: list[str],
    keywords: list[str],
) -> list[QueryRewrite]:
    anchor = anchor_terms[0]
    keyword = keywords[0] if keywords else "workflow"
    candidates = [
        f"visual interface for {anchor}",
        f"{anchor} workflow editor",
        f"gui for {anchor}",
        f"{anchor} {keyword}",
    ]
    return _make_rewrites(
        QueryFamily.WORKFLOW_INTERFACE,
        candidates,
        "Find UI and workflow interface variants around the anchor entity.",
    )


def _build_adjacent_analogy_rewrites(
    *,
    anchor_terms: list[str],
    comparison_anchors: list[str],
) -> list[QueryRewrite]:
    anchor = anchor_terms[0] if anchor_terms else ""
    comparison = comparison_anchors[0]
    candidates = [
        f"{comparison} for {anchor}".strip(),
        f"agent IDE for {anchor}".strip(),
        f"{anchor} desktop client".strip(),
        f"{comparison} alternative for {anchor}".strip(),
    ]
    return _make_rewrites(
        QueryFamily.ADJACENT_ANALOGY,
        candidates,
        "Find analogue products that express the intended product shape.",
    )


def _build_generic_rewrites(
    *,
    family: QueryFamily,
    base_terms: list[str],
    suffixes: list[str],
    purpose: str,
) -> list[QueryRewrite]:
    base = base_terms[0]
    return _make_rewrites(
        family,
        [f"{base} {suffix}" for suffix in suffixes],
        purpose,
    )


def _make_rewrites(
    family: QueryFamily,
    candidates: list[str],
    purpose: str,
) -> list[QueryRewrite]:
    seen: set[str] = set()
    rewrites: list[QueryRewrite] = []
    for candidate in candidates:
        normalized = candidate.strip()
        if not normalized:
            continue
        lowered = normalized.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        rewrites.append(QueryRewrite(query=normalized, family=family, purpose=purpose))
        if len(rewrites) >= _MAX_REWRITES_PER_GROUP:
            break
    return rewrites


def _map_family_to_platform_bucket(
    platform: Platform,
    family: QueryFamily,
) -> str:
    if family == QueryFamily.DIRECT_COMPETITOR:
        return "competitor_discovery"
    if family == QueryFamily.ADJACENT_ANALOGY:
        return (
            "ecosystem_discovery"
            if platform == Platform.GITHUB
            else "alternative_discovery"
        )
    if family == QueryFamily.WORKFLOW_INTERFACE:
        return "workflow_discovery"
    if family == QueryFamily.PAIN_DISCOVERY:
        return "pain_discovery"
    if family == QueryFamily.COMMERCIAL_DISCOVERY:
        return "commercial_discovery"
    if family == QueryFamily.DISCUSSION_DISCOVERY:
        return (
            "discussion_discovery"
            if platform == Platform.HACKERNEWS
            else "workflow_discovery"
        )
    return "competitor_discovery"


def _adapt_rewrite_for_platform(
    *,
    platform: Platform,
    rewrite_query: str,
    anchor_terms: list[str],
    keywords: list[str],
) -> str:
    anchor = anchor_terms[0] if anchor_terms else ""
    keyword = keywords[0] if keywords else ""

    if platform == Platform.GITHUB:
        if "workflow editor" in rewrite_query.lower():
            slug_terms = [f"topic:{_slugify(term)}" for term in keywords[:2] if term]
            slug_terms.append(f"{anchor} gui".strip())
            return " ".join(part for part in slug_terms if part).strip()
        return rewrite_query.strip()

    if platform == Platform.TAVILY:
        return rewrite_query.strip()

    if platform == Platform.REDDIT:
        if "interface" in rewrite_query.lower() or "gui" in rewrite_query.lower():
            return f"{anchor} recommend".strip()
        return rewrite_query.strip()

    if platform == Platform.HACKERNEWS:
        if "interface" in rewrite_query.lower():
            return f"{anchor} show hn".strip()
        return rewrite_query.strip()

    if platform == Platform.PRODUCT_HUNT:
        if anchor:
            return f"{anchor} developer tools".strip()
        return rewrite_query.strip()

    if platform == Platform.APPSTORE and keyword:
        return keyword

    return rewrite_query.strip()


def _normalize_query_plan(
    plan: QueryPlan,
    *,
    fallback_plan: QueryPlan | None,
) -> QueryPlan:
    """Apply hard caps, dedupe, and anchor-preservation rules."""
    normalized_groups: list[QueryGroup] = []
    seen_families: set[str] = set()
    fallback_groups_by_family = {
        group.family.value: group
        for group in (fallback_plan.query_groups if fallback_plan else [])
    }

    for raw_group in plan.query_groups:
        family_key = raw_group.family.value
        if family_key in seen_families:
            continue
        normalized_rewrites = _normalize_rewrites(
            raw_group.rewritten_queries,
            fallback_group=fallback_groups_by_family.get(family_key),
        )
        if not normalized_rewrites:
            continue
        normalized_groups.append(
            QueryGroup(
                family=raw_group.family,
                anchor_terms=_dedupe_preserve_order(raw_group.anchor_terms),
                comparison_anchors=_dedupe_preserve_order(raw_group.comparison_anchors),
                rewritten_queries=normalized_rewrites,
            )
        )
        seen_families.add(family_key)
        if len(normalized_groups) >= _MAX_GROUPS:
            break

    if fallback_plan and len(normalized_groups) < _MIN_GROUPS:
        for fallback_group in fallback_plan.query_groups:
            family_key = fallback_group.family.value
            if family_key in seen_families:
                continue
            normalized_groups.append(fallback_group)
            seen_families.add(family_key)
            if len(normalized_groups) >= _MIN_GROUPS:
                break

    return QueryPlan(query_groups=normalized_groups[:_MAX_GROUPS])


def _normalize_query_plan_payload(payload: Any) -> Any:
    """Normalize known LLM family aliases before typed validation."""
    if isinstance(payload, dict):
        normalized_payload: dict[str, Any] = {}
        for key, value in payload.items():
            if key == "family" and isinstance(value, str):
                normalized_payload[key] = _QUERY_FAMILY_ALIASES.get(
                    value.strip(), value.strip()
                )
            else:
                normalized_payload[key] = _normalize_query_plan_payload(value)
        return normalized_payload
    if isinstance(payload, list):
        return [_normalize_query_plan_payload(item) for item in payload]
    return payload


def _normalize_rewrites(
    rewrites: list[QueryRewrite],
    *,
    fallback_group: QueryGroup | None,
) -> list[QueryRewrite]:
    seen: set[str] = set()
    normalized: list[QueryRewrite] = []
    required_anchors = fallback_group.anchor_terms if fallback_group else []

    for rewrite in rewrites:
        query = rewrite.query.strip()
        if not query:
            continue
        lowered = query.lower()
        if lowered in seen:
            continue
        if required_anchors and not any(
            anchor.strip().lower() in lowered for anchor in required_anchors
        ):
            continue
        seen.add(lowered)
        normalized.append(
            QueryRewrite(
                query=query,
                family=rewrite.family,
                purpose=rewrite.purpose.strip(),
            )
        )
        if len(normalized) >= _MAX_REWRITES_PER_GROUP:
            break

    if normalized or fallback_group is None:
        return normalized
    return fallback_group.rewritten_queries[:_MAX_REWRITES_PER_GROUP]


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = value.strip()
        if not normalized:
            continue
        lowered = normalized.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        result.append(normalized)
    return result


def _clean_keywords(keywords: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for keyword in keywords:
        normalized = keyword.strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _slugify(text: str) -> str:
    return "-".join(
        part for part in text.lower().strip().replace("_", " ").split() if part
    )
