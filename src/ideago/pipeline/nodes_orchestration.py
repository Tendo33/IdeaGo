"""Query orchestration helpers for pipeline nodes."""

from __future__ import annotations

from typing import TypeVar

from ideago.models.research import Intent, Platform, QueryPlan
from ideago.observability.log_config import get_logger
from ideago.pipeline.query_builder import (
    QueryString,
    build_query_families,
    infer_query_family,
)

logger = get_logger(__name__)

_DEFAULT_SOURCE_QUERY_CAP = 5
_DEFAULT_ROLE_QUERY_BUDGET = 4
_DEFAULT_QUERY_FAMILY_WEIGHT = 1.0
_MANDATORY_QUERY_FAMILIES = {"competitor_discovery"}
_SOURCE_ROLE_BY_PLATFORM: dict[Platform, str] = {
    Platform.GITHUB: "builder_signal",
    Platform.TAVILY: "market_scan",
    Platform.APPSTORE: "user_feedback",
    Platform.REDDIT: "user_feedback",
    Platform.PRODUCT_HUNT: "launch_signal",
    Platform.HACKERNEWS: "discussion_signal",
}
_QueryTextT = TypeVar("_QueryTextT", bound=str)


def build_orchestrated_queries(
    *,
    platform: Platform,
    intent: Intent,
    query_plan: QueryPlan | None,
    source_query_caps: dict[str, int],
    family_default_weights: dict[str, float],
    orchestration_profiles: dict[str, dict[str, object]],
) -> tuple[list[str], dict[str, object]]:
    """Build weighted, capped query list for one source platform."""
    families = build_query_families(
        platform=platform,
        intent=intent,
        query_plan=query_plan,
    )
    if not families:
        return [], {
            "source_role": _SOURCE_ROLE_BY_PLATFORM.get(platform, "general"),
            "source_cap": _DEFAULT_SOURCE_QUERY_CAP,
            "role_cap": _DEFAULT_ROLE_QUERY_BUDGET,
            "effective_cap": 1,
            "selected_query_count": 0,
            "selected_family_counts": {},
        }

    profile = _resolve_orchestration_profile(orchestration_profiles, intent.app_type)
    source_role = _SOURCE_ROLE_BY_PLATFORM.get(platform, "general")
    source_cap = source_query_caps.get(platform.value, _DEFAULT_SOURCE_QUERY_CAP)
    role_cap = _resolve_role_budget(profile, source_role)
    effective_cap = max(1, min(source_cap, role_cap))
    family_weights = _merge_family_weights(family_default_weights, profile)
    trim_threshold = _safe_non_negative_float(
        profile.get("family_trim_threshold"),
        fallback=0.0,
    )
    trimmed_families = _trim_query_families(
        families=families,
        family_weights=family_weights,
        trim_threshold=trim_threshold,
    )
    queries = _weighted_family_queries(
        families=trimmed_families,
        family_weights=family_weights,
        max_queries=effective_cap,
    )
    selected_family_counts = build_query_family_coverage(queries)
    observability_payload: dict[str, object] = {
        "source_role": source_role,
        "source_cap": source_cap,
        "role_cap": role_cap,
        "effective_cap": effective_cap,
        "selected_query_count": len(queries),
        "selected_family_counts": selected_family_counts,
    }
    logger.debug(
        "Orchestration profile: platform={}, role={}, app_type={}, selected_queries={}, cap={}",
        platform.value,
        source_role,
        intent.app_type,
        len(queries),
        effective_cap,
    )
    return queries, observability_payload


def build_query_family_coverage(queries: list[str]) -> dict[str, int]:
    coverage: dict[str, int] = {}
    for query in queries:
        family = infer_query_family(query).strip().lower()
        if not family:
            continue
        coverage[family] = coverage.get(family, 0) + 1
    return coverage


def _resolve_orchestration_profile(
    orchestration_profiles: dict[str, dict[str, object]],
    app_type: str,
) -> dict[str, object]:
    app_key = app_type.strip().lower()
    profile = orchestration_profiles.get(app_key)
    if isinstance(profile, dict):
        return profile
    fallback = orchestration_profiles.get("default", {})
    return fallback if isinstance(fallback, dict) else {}


def _resolve_role_budget(profile: dict[str, object], source_role: str) -> int:
    role_budgets = profile.get("role_query_budgets", {})
    if not isinstance(role_budgets, dict):
        return _DEFAULT_ROLE_QUERY_BUDGET
    role_cap = _safe_positive_int(role_budgets.get(source_role))
    if role_cap is not None:
        return role_cap
    general_cap = _safe_positive_int(role_budgets.get("general"))
    if general_cap is not None:
        return general_cap
    return _DEFAULT_ROLE_QUERY_BUDGET


def _merge_family_weights(
    family_default_weights: dict[str, float],
    profile: dict[str, object],
) -> dict[str, float]:
    merged: dict[str, float] = {
        key: _safe_non_negative_float(value, fallback=_DEFAULT_QUERY_FAMILY_WEIGHT)
        for key, value in family_default_weights.items()
    }
    raw_overrides = profile.get("family_weight_overrides", {})
    if not isinstance(raw_overrides, dict):
        return merged
    for family_name, raw_weight in raw_overrides.items():
        family_key = str(family_name).strip().lower()
        if family_key not in merged:
            continue
        merged[family_key] = _safe_non_negative_float(
            raw_weight,
            fallback=merged[family_key],
        )
    return merged


def _trim_query_families(
    *,
    families: dict[str, list[_QueryTextT]],
    family_weights: dict[str, float],
    trim_threshold: float,
) -> dict[str, list[_QueryTextT]]:
    trimmed: dict[str, list[_QueryTextT]] = {}
    for family_name, queries in families.items():
        weight = family_weights.get(family_name, _DEFAULT_QUERY_FAMILY_WEIGHT)
        if weight >= trim_threshold or family_name in _MANDATORY_QUERY_FAMILIES:
            trimmed[family_name] = queries
    if trimmed:
        return trimmed
    best_family = max(
        families.keys(),
        key=lambda name: family_weights.get(name, _DEFAULT_QUERY_FAMILY_WEIGHT),
    )
    return {best_family: families[best_family]}


def _weighted_family_queries(
    *,
    families: dict[str, list[_QueryTextT]],
    family_weights: dict[str, float],
    max_queries: int,
) -> list[str]:
    if max_queries <= 0:
        return []
    ordered_families = [
        (name, queries)
        for name, queries in families.items()
        if queries and any(query.strip() for query in queries)
    ]
    if not ordered_families:
        return []

    sort_indexes = {name: index for index, (name, _) in enumerate(ordered_families)}
    sorted_family_names = sorted(
        [name for name, _ in ordered_families],
        key=lambda name: (
            -family_weights.get(name, _DEFAULT_QUERY_FAMILY_WEIGHT),
            sort_indexes[name],
        ),
    )
    query_offsets = {name: 0 for name in sorted_family_names}
    source_queries = {name: families[name] for name in sorted_family_names}

    weighted_cycle: list[str] = []
    for family_name in sorted_family_names:
        weight = family_weights.get(family_name, _DEFAULT_QUERY_FAMILY_WEIGHT)
        tickets = max(1, min(6, int(round(weight * 2))))
        weighted_cycle.extend([family_name] * tickets)
    if not weighted_cycle:
        return []

    result: list[str] = []
    seen: set[str] = set()
    while len(result) < max_queries:
        progressed = False
        for family_name in weighted_cycle:
            offset = query_offsets[family_name]
            queries = source_queries[family_name]
            while offset < len(queries):
                original_candidate = queries[offset]
                offset += 1
                candidate = _normalize_query_object(original_candidate)
                candidate_text = candidate.strip()
                if not candidate_text:
                    continue
                lowered = candidate_text.lower()
                if lowered in seen:
                    continue
                seen.add(lowered)
                result.append(candidate)
                progressed = True
                break
            query_offsets[family_name] = offset
            if len(result) >= max_queries:
                break
        if not progressed:
            break
    return result


def _normalize_query_object(value: str) -> str:
    """Trim query text while preserving string-subclass metadata when possible."""
    normalized = value.strip()
    if normalized == value:
        return value

    query_family = getattr(value, "query_family", None)
    if isinstance(query_family, str) and query_family:
        return QueryString(normalized, query_family=query_family)
    return normalized


def _safe_positive_int(value: object) -> int | None:
    if isinstance(value, bool):
        return 1 if value else None
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, float):
        parsed = int(value)
    elif isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            parsed = int(stripped)
        except ValueError:
            return None
    else:
        return None
    if parsed <= 0:
        return None
    return parsed


def _safe_non_negative_float(value: object, *, fallback: float) -> float:
    if isinstance(value, int | float):
        parsed = float(value)
    elif isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return fallback
        try:
            parsed = float(stripped)
        except ValueError:
            return fallback
    else:
        return fallback
    if parsed < 0:
        return fallback
    return parsed
