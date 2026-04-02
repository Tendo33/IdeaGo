"""Pre-filter raw results by platform-specific quality signals before LLM extraction.

Uses popularity/engagement signals already present in raw_data to rank and
truncate results, reducing token waste on low-quality entries.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ideago.models.research import OpportunityScoreBreakdown, Platform, RawResult

_DEFAULT_MAX_PER_SOURCE = 8
_DEFAULT_MAX_AGE_DAYS = 0
_PAIN_TERMS = (
    "pain",
    "complaint",
    "problem",
    "issue",
    "friction",
    "frustrat",
    "annoy",
    "broken",
    "missing",
    "slow",
    "noisy",
    "brittle",
)
_ALTERNATIVE_TERMS = (
    "alternative",
    "switch",
    "replace",
    "replacement",
    "migrate",
    "migration",
    "instead",
    "better option",
    "recommend",
)
_COMMERCIAL_TERMS = (
    "pricing",
    "price",
    "paid",
    "budget",
    "cost",
    "buy",
    "purchase",
    "revenue",
    "subscription",
    "upgrade",
    "roi",
)
_FAMILY_BASE_COMPONENTS: dict[str, tuple[float, float, float]] = {
    "pain_discovery": (0.72, 0.18, 0.0),
    "alternative_discovery": (0.18, 0.78, 0.0),
    "migration_discovery": (0.45, 0.72, 0.0),
    "commercial_discovery": (0.12, 0.15, 0.82),
    "workflow_discovery": (0.16, 0.34, 0.18),
    "discussion_discovery": (0.22, 0.18, 0.0),
    "positioning_discovery": (0.08, 0.28, 0.16),
    "launch_discovery": (0.0, 0.2, 0.22),
    "ecosystem_discovery": (0.0, 0.12, 0.08),
    "competitor_discovery": (0.0, 0.08, 0.0),
}
_FAMILY_COMPETITION_PENALTY: dict[str, float] = {
    "competitor_discovery": 0.38,
    "launch_discovery": 0.28,
    "ecosystem_discovery": 0.24,
    "workflow_discovery": 0.14,
    "positioning_discovery": 0.14,
    "discussion_discovery": 0.1,
    "alternative_discovery": 0.08,
    "migration_discovery": 0.06,
    "pain_discovery": 0.04,
    "commercial_discovery": 0.04,
}


def filter_raw_results(
    raw_by_source: dict[str, list[RawResult]],
    *,
    max_per_source: int = _DEFAULT_MAX_PER_SOURCE,
    max_age_days: int = _DEFAULT_MAX_AGE_DAYS,
) -> dict[str, list[RawResult]]:
    """Rank and truncate raw results per source using quality signals.

    Args:
        raw_by_source: Platform name → raw results mapping.
        max_per_source: Maximum results to keep per platform.
        max_age_days: Drop results with a known timestamp older than this.
            Zero disables the hard cutoff.

    Returns:
        Filtered mapping with top-N results per platform.
    """
    cutoff = (
        datetime.now(timezone.utc) - timedelta(days=max_age_days)
        if max_age_days > 0
        else None
    )
    filtered: dict[str, list[RawResult]] = {}
    cap = max(1, max_per_source)
    for platform_name, results in raw_by_source.items():
        if not results:
            continue
        candidates = (
            [r for r in results if not _is_too_old(r, cutoff)] if cutoff else results
        )
        scored = sorted(candidates, key=_quality_score, reverse=True)
        filtered[platform_name] = scored[:cap]
    return filtered


def _is_too_old(result: RawResult, cutoff: datetime) -> bool:
    """Return True when the result has a known timestamp older than *cutoff*."""
    ts = _parse_iso8601(result.raw_data.get("freshness_timestamp"))
    if ts is None:
        return False
    return ts < cutoff


def _quality_score(result: RawResult) -> float:
    """Compute deterministic opportunity score from result metadata."""
    breakdown = build_opportunity_score_breakdown(result)
    result.raw_data["opportunity_score_breakdown"] = breakdown.model_dump(mode="json")
    result.raw_data["opportunity_score"] = breakdown.score
    return breakdown.score


def build_opportunity_score_breakdown(result: RawResult) -> OpportunityScoreBreakdown:
    """Build a deterministic opportunity score from raw-result metadata."""
    platform = result.platform
    raw = result.raw_data
    has_description = bool(result.description and result.description.strip())
    if platform == Platform.GOOGLE_TRENDS:
        return OpportunityScoreBreakdown(score=0.5 if has_description else 0.1)

    query_family = _safe_str(raw.get("query_family")).lower()
    signal_text = _signal_text(result)
    popularity = _popularity_signal(result)
    engagement = _engagement_signal(raw)

    base_pain, base_gap, base_commercial = _FAMILY_BASE_COMPONENTS.get(
        query_family,
        (0.0, 0.0, 0.0),
    )
    pain_intensity = _clamp01(
        base_pain
        + _term_signal(signal_text, _PAIN_TERMS, weight=0.12, cap=0.24)
        + _signal_density_boost(
            query_family, engagement, categories={"pain", "migration"}
        )
        + _platform_pain_boost(platform, raw)
    )
    solution_gap = _clamp01(
        base_gap
        + _term_signal(signal_text, _ALTERNATIVE_TERMS, weight=0.12, cap=0.24)
        + _signal_density_boost(
            query_family,
            engagement,
            categories={"alternative", "migration", "workflow"},
        )
        + _platform_solution_gap_boost(platform, raw)
    )
    commercial_intent = _clamp01(
        base_commercial
        + _term_signal(signal_text, _COMMERCIAL_TERMS, weight=0.12, cap=0.24)
        + _signal_density_boost(
            query_family,
            engagement,
            categories={"commercial", "workflow"},
        )
        + _platform_commercial_boost(platform, raw)
    )
    freshness = _freshness_signal(raw.get("freshness_timestamp"), result.fetched_at)
    competition_density = _clamp01(
        popularity * 0.72 + _FAMILY_COMPETITION_PENALTY.get(query_family, 0.12)
    )
    signal_strength = max(pain_intensity, solution_gap, commercial_intent)
    popularity_support = popularity * (0.22 + signal_strength * 0.06)
    score = _clamp01(
        0.02
        + popularity_support
        + (0.05 if has_description else 0.0)
        + pain_intensity * 0.34
        + solution_gap * 0.32
        + commercial_intent * 0.3
        + freshness * 0.08
        - competition_density * 0.14
    )

    return OpportunityScoreBreakdown(
        pain_intensity=pain_intensity,
        solution_gap=solution_gap,
        commercial_intent=commercial_intent,
        freshness=freshness,
        competition_density=competition_density,
        score=score,
    )


def _popularity_signal(result: RawResult) -> float:
    platform = result.platform
    raw = result.raw_data
    has_description = bool(result.description and result.description.strip())

    if platform == Platform.GITHUB:
        return _score_github(raw, has_description)
    if platform == Platform.HACKERNEWS:
        return _score_hackernews(raw)
    if platform == Platform.APPSTORE:
        return _score_appstore(raw)
    if platform == Platform.PRODUCT_HUNT:
        return _score_producthunt(raw)
    if platform == Platform.TAVILY:
        return _score_tavily(raw, has_description)
    if platform == Platform.REDDIT:
        return _score_reddit(raw)
    return 0.5 if has_description else 0.1


def _score_github(raw: dict, has_description: bool) -> float:
    stars = _safe_int(raw.get("stargazers_count", 0))
    forks = _safe_int(raw.get("forks_count", 0))
    star_score = min(1.0, stars / 500)
    fork_score = min(1.0, forks / 100) * 0.2
    desc_bonus = 0.1 if has_description else 0.0
    return min(1.0, star_score + fork_score + desc_bonus)


def _score_hackernews(raw: dict) -> float:
    points = _safe_int(raw.get("points", 0))
    comments = _safe_int(raw.get("num_comments", 0))
    point_score = min(1.0, points / 200)
    comment_score = min(1.0, comments / 50) * 0.3
    return min(1.0, point_score + comment_score)


def _score_appstore(raw: dict) -> float:
    rating_count = _safe_int(raw.get("user_rating_count") or raw.get("rating_count", 0))
    rating = _safe_float(raw.get("average_user_rating") or raw.get("rating", 0))
    count_score = min(1.0, rating_count / 5000)
    rating_score = (rating / 5.0) * 0.3 if rating > 0 else 0.0
    return min(1.0, count_score + rating_score)


def _score_producthunt(raw: dict) -> float:
    votes = _safe_int(raw.get("votes_count", 0))
    return min(1.0, votes / 300)


def _score_reddit(raw: dict) -> float:
    score = _safe_int(raw.get("score", 0))
    comments = _safe_int(raw.get("num_comments", 0))
    score_part = min(1.0, score / 200)
    comment_part = min(1.0, comments / 50) * 0.3
    return min(1.0, score_part + comment_part)


def _score_tavily(raw: dict, has_description: bool) -> float:
    score = _safe_float(raw.get("score", 0))
    desc_bonus = 0.1 if has_description else 0.0
    return min(1.0, score + desc_bonus)


def _signal_text(result: RawResult) -> str:
    raw = result.raw_data
    segments = (
        _safe_str(raw.get("matched_query")),
        _safe_str(result.title),
        _safe_str(result.description),
        _safe_str(raw.get("snippet")),
    )
    return " ".join(segment.lower() for segment in segments if segment)


def _term_signal(
    signal_text: str,
    terms: tuple[str, ...],
    *,
    weight: float,
    cap: float,
) -> float:
    if not signal_text:
        return 0.0
    hits = sum(1 for term in terms if term in signal_text)
    return min(cap, hits * weight)


def _signal_density_boost(
    query_family: str,
    engagement: float,
    *,
    categories: set[str],
) -> float:
    if not query_family:
        return 0.0
    if not any(category in query_family for category in categories):
        return 0.0
    return min(0.18, engagement * 0.18)


def _platform_pain_boost(platform: Platform, raw: dict[str, object]) -> float:
    if platform == Platform.APPSTORE:
        rating = _safe_float(raw.get("average_user_rating") or raw.get("rating"))
        if 0 < rating < 3.6:
            return min(0.2, (3.6 - rating) / 3.6)
    return 0.0


def _platform_solution_gap_boost(platform: Platform, raw: dict[str, object]) -> float:
    if platform == Platform.REDDIT:
        comments = _safe_int(raw.get("num_comments", 0))
        return min(0.12, comments / 120)
    if platform == Platform.HACKERNEWS:
        comments = _safe_int(raw.get("num_comments", 0))
        return min(0.12, comments / 140)
    return 0.0


def _platform_commercial_boost(platform: Platform, raw: dict[str, object]) -> float:
    if platform == Platform.APPSTORE:
        price = _safe_float(raw.get("price") or raw.get("price_numeric"))
        if price > 0:
            return min(0.16, price / 25)
    if platform == Platform.PRODUCT_HUNT:
        votes = _safe_int(raw.get("votes_count", 0))
        return min(0.08, votes / 500)
    return 0.0


def _engagement_signal(raw: dict[str, object]) -> float:
    explicit_proxy = _safe_float(raw.get("engagement_proxy"))
    if explicit_proxy > 0:
        if explicit_proxy <= 1.0:
            return explicit_proxy
        return min(1.0, explicit_proxy / 500)
    return min(
        1.0,
        (
            _safe_int(raw.get("num_comments"))
            + _safe_int(raw.get("votes_count"))
            + _safe_int(raw.get("user_rating_count") or raw.get("rating_count"))
        )
        / 500,
    )


def _freshness_signal(value: object, fetched_at: datetime) -> float:
    parsed = _parse_iso8601(value)
    if parsed is None:
        return 0.0
    anchor = fetched_at.astimezone(timezone.utc)
    age_days = max(0.0, (anchor - parsed).total_seconds() / 86400)
    if age_days <= 30:
        return 1.0
    if age_days <= 90:
        return 0.8
    if age_days <= 180:
        return 0.6
    if age_days <= 365:
        return 0.4
    if age_days <= 730:
        return 0.2
    return 0.0


def _parse_iso8601(value: object) -> datetime | None:
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
    return parsed


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _safe_str(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    return ""


def _safe_int(value: object) -> int:
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


def _safe_float(value: object) -> float:
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return 0.0
    return 0.0
