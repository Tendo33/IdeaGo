"""Pre-filter raw results by platform-specific quality signals before LLM extraction.

Uses popularity/engagement signals already present in raw_data to rank and
truncate results, reducing token waste on low-quality entries.
"""

from __future__ import annotations

from ideago.models.research import Platform, RawResult

_DEFAULT_MAX_PER_SOURCE = 8


def filter_raw_results(
    raw_by_source: dict[str, list[RawResult]],
    *,
    max_per_source: int = _DEFAULT_MAX_PER_SOURCE,
) -> dict[str, list[RawResult]]:
    """Rank and truncate raw results per source using quality signals.

    Args:
        raw_by_source: Platform name → raw results mapping.
        max_per_source: Maximum results to keep per platform.

    Returns:
        Filtered mapping with top-N results per platform.
    """
    filtered: dict[str, list[RawResult]] = {}
    cap = max(1, max_per_source)
    for platform_name, results in raw_by_source.items():
        if not results:
            continue
        scored = sorted(results, key=_quality_score, reverse=True)
        filtered[platform_name] = scored[:cap]
    return filtered


def _quality_score(result: RawResult) -> float:
    """Compute a 0-1 quality score from platform-specific raw_data signals."""
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


def _score_tavily(raw: dict, has_description: bool) -> float:
    score = _safe_float(raw.get("score", 0))
    desc_bonus = 0.1 if has_description else 0.0
    return min(1.0, score + desc_bonus)


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
