"""Merger — deterministic competitor deduplication and score adjustment.

Replaces the LLM-based dedup that was previously inside the Aggregator.
Uses URL normalization and fuzzy name matching (SequenceMatcher) to fuse
duplicates across platforms. Applies code-level score boosts based on
multi-platform presence and data completeness.
"""

from __future__ import annotations

from copy import deepcopy
from difflib import SequenceMatcher
from urllib.parse import urlparse

from ideago.models.research import Competitor
from ideago.observability.log_config import get_logger

logger = get_logger(__name__)

_NAME_SIMILARITY_THRESHOLD = 0.85
_MULTI_PLATFORM_BOOST = 0.05
_COMPLETENESS_BOOST = 0.03
_MULTI_TENANT_HOSTS = {"github.com", "gitlab.com", "bitbucket.org"}


def merge_competitors(competitors: list[Competitor]) -> list[Competitor]:
    """Fuse duplicate competitors using URL + fuzzy-name matching and adjust scores.

    Steps:
        1. Group by normalized URL → exact URL dedup.
        2. Fuzzy-match remaining names → merge near-duplicates.
        3. Apply deterministic score boosts (multi-platform, completeness).
        4. Sort by relevance_score descending.

    Returns:
        Deduplicated, score-adjusted competitor list.
    """
    if not competitors:
        return []

    url_groups: dict[str, list[Competitor]] = {}
    no_url: list[Competitor] = []

    for comp in competitors:
        canonical = _canonical_url(comp)
        if canonical:
            url_groups.setdefault(canonical, []).append(comp)
        else:
            no_url.append(comp)

    merged_by_url: list[Competitor] = []
    for group in url_groups.values():
        base = group[0].model_copy(deep=True)
        for other in group[1:]:
            base = _merge_pair(base, other)
        merged_by_url.append(base)

    all_candidates = merged_by_url + no_url
    fused = _fuzzy_name_merge(all_candidates)

    for comp in fused:
        _apply_score_boosts(comp)

    fused.sort(key=lambda c: c.relevance_score, reverse=True)
    return fused


def _canonical_url(comp: Competitor) -> str:
    """Return a single canonical URL key from links or source_urls."""
    for url in [*comp.links, *comp.source_urls]:
        norm = _canonical_entity_key(url)
        if norm:
            return norm
    return ""


def _canonical_entity_key(url: str) -> str:
    """Build a product-level key from URL for deterministic dedup."""
    try:
        parsed = urlparse(url.strip().lower())
    except ValueError:
        return ""
    host = parsed.netloc.removeprefix("www.")
    if not host:
        return ""

    path_parts = [part for part in parsed.path.split("/") if part]
    if host in _MULTI_TENANT_HOSTS:
        if len(path_parts) >= 2:
            return f"{host}/{path_parts[0]}/{path_parts[1]}"
        return host
    if host == "apps.apple.com":
        app_id = next((part for part in path_parts if part.startswith("id")), "")
        if app_id:
            return f"{host}/{app_id}"
        return host
    return host


def _normalized_url(url: str) -> str:
    """Normalize URL for overlap checks (host + normalized path)."""
    try:
        parsed = urlparse(url.strip().lower())
    except ValueError:
        return ""
    host = parsed.netloc.removeprefix("www.")
    if not host:
        return ""
    path = parsed.path.rstrip("/")
    return f"{host}{path}"


def _fuzzy_name_merge(competitors: list[Competitor]) -> list[Competitor]:
    """Merge competitors with similar names (SequenceMatcher ratio >= threshold)."""
    if len(competitors) <= 1:
        return list(competitors)

    merged: list[Competitor] = []
    consumed: set[int] = set()

    for i, base in enumerate(competitors):
        if i in consumed:
            continue
        current = base.model_copy(deep=True)
        for j in range(i + 1, len(competitors)):
            if j in consumed:
                continue
            other = competitors[j]
            if _names_similar(current.name, other.name) and _has_merge_signal(
                current, other
            ):
                current = _merge_pair(current, other)
                consumed.add(j)
                logger.debug(
                    "Fuzzy-merged '{}' ← '{}'",
                    current.name,
                    other.name,
                )
        merged.append(current)

    return merged


def _names_similar(a: str, b: str) -> bool:
    na = a.strip().lower()
    nb = b.strip().lower()
    if na == nb:
        return True
    return SequenceMatcher(None, na, nb).ratio() >= _NAME_SIMILARITY_THRESHOLD


def _has_merge_signal(left: Competitor, right: Competitor) -> bool:
    """Guard fuzzy-name merge with at least one consistency signal."""
    left_domains = _domains(left)
    right_domains = _domains(right)
    if left_domains and right_domains and left_domains.intersection(right_domains):
        return True

    left_urls = _url_keys(left)
    right_urls = _url_keys(right)
    if left_urls and right_urls and left_urls.intersection(right_urls):
        return True

    left_features = {item.strip().lower() for item in left.features if item.strip()}
    right_features = {item.strip().lower() for item in right.features if item.strip()}
    return bool(
        left_features and right_features and left_features.intersection(right_features)
    )


def _domains(comp: Competitor) -> set[str]:
    domains: set[str] = set()
    for url in [*comp.links, *comp.source_urls]:
        try:
            parsed = urlparse(url.strip().lower())
        except ValueError:
            continue
        host = parsed.netloc.removeprefix("www.")
        if host:
            domains.add(host)
    return domains


def _url_keys(comp: Competitor) -> set[str]:
    keys: set[str] = set()
    for url in [*comp.links, *comp.source_urls]:
        key = _normalized_url(url)
        if key:
            keys.add(key)
    return keys


def _merge_pair(base: Competitor, incoming: Competitor) -> Competitor:
    """Merge two competitor records, preferring richer data."""
    merged = deepcopy(base)
    merged.name = (
        merged.name if len(merged.name) >= len(incoming.name) else incoming.name
    )
    merged.one_liner = (
        merged.one_liner
        if len(merged.one_liner) >= len(incoming.one_liner)
        else incoming.one_liner
    )
    merged.links = _unique_strs([*merged.links, *incoming.links])
    merged.source_urls = _unique_strs([*merged.source_urls, *incoming.source_urls])
    merged.features = _unique_strs([*merged.features, *incoming.features])
    merged.strengths = _unique_strs([*merged.strengths, *incoming.strengths])
    merged.weaknesses = _unique_strs([*merged.weaknesses, *incoming.weaknesses])
    merged.source_platforms = list(
        dict.fromkeys([*merged.source_platforms, *incoming.source_platforms])
    )
    merged.relevance_score = max(merged.relevance_score, incoming.relevance_score)
    if not merged.pricing and incoming.pricing:
        merged.pricing = incoming.pricing
    return merged


def _apply_score_boosts(comp: Competitor) -> None:
    """Deterministic score adjustments based on data signals."""
    boost = 0.0
    if len(comp.source_platforms) >= 2:
        boost += _MULTI_PLATFORM_BOOST * (len(comp.source_platforms) - 1)
    has_features = len(comp.features) >= 2
    has_pricing = bool(comp.pricing)
    has_strengths = len(comp.strengths) >= 1
    if has_features and has_pricing and has_strengths:
        boost += _COMPLETENESS_BOOST

    if boost > 0:
        comp.relevance_score = min(1.0, round(comp.relevance_score + boost, 3))


def _unique_strs(values: list[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for value in values:
        stripped = value.strip()
        if not stripped:
            continue
        marker = stripped.lower()
        if marker in seen:
            continue
        seen.add(marker)
        unique.append(stripped)
    return unique
