"""Extraction/fallback helpers for pipeline nodes."""

from __future__ import annotations

from typing import Any

from ideago.contracts.protocols import DataSource
from ideago.models.research import Competitor, Intent, Platform, RawResult
from ideago.pipeline.exceptions import ExtractionError
from ideago.pipeline.extractor import ExtractionOutput as TypedExtractionOutput
from ideago.pipeline.extractor import Extractor
from ideago.utils.text_utils import decode_entities_and_strip_html


def extraction_degraded_message(output_language: str) -> str:
    return _localized_text(
        output_language,
        "结构化提取暂不可用，当前展示原始结果。",
        "Extraction unavailable; showing raw results.",
    )


def degrade_raw_to_competitors(
    raw_results: list[RawResult],
    output_language: str = "en",
) -> list[Competitor]:
    """Convert raw results to minimal Competitor objects when LLM extraction fails."""
    from ideago.pipeline.pre_filter import _quality_score, _safe_int

    result: list[Competitor] = []
    for raw in raw_results:
        if not raw.url:
            continue
        normalized_description = decode_entities_and_strip_html(raw.description)
        one_liner = (
            normalized_description[:200]
            if normalized_description
            else _localized_text(
                output_language,
                "暂无可用描述",
                "No description available",
            )
        )
        relevance = max(0.1, round(_quality_score(raw) * 0.6, 2))

        features: list[str] = []
        rd = raw.raw_data
        if raw.platform == Platform.GITHUB:
            lang = rd.get("language")
            if lang:
                features.append(lang)
            stars = _safe_int(rd.get("stargazers_count", 0))
            if stars:
                features.append(
                    _localized_text(
                        output_language,
                        f"{stars} 星标",
                        f"{stars} stars",
                    )
                )
        elif raw.platform == Platform.APPSTORE:
            genre = rd.get("primary_genre_name")
            if genre:
                features.append(genre)
            price = rd.get("price_label")
            if price:
                features.append(price)
        elif raw.platform == Platform.REDDIT:
            subreddit = rd.get("subreddit")
            if subreddit:
                features.append(f"r/{subreddit}")
            score = _safe_int(rd.get("score", 0))
            if score:
                features.append(
                    _localized_text(
                        output_language,
                        f"{score} 赞同",
                        f"{score} upvotes",
                    )
                )
            comments = _safe_int(rd.get("num_comments", 0))
            if comments:
                features.append(
                    _localized_text(
                        output_language,
                        f"{comments} 条评论",
                        f"{comments} comments",
                    )
                )

        result.append(
            Competitor(
                name=raw.title or "Unknown",
                links=[raw.url],
                one_liner=one_liner,
                features=features,
                source_platforms=[raw.platform],
                source_urls=[raw.url],
                relevance_score=relevance,
            )
        )
    return result


async def extract_typed_output(
    extractor: Extractor,
    raw_results: list[RawResult],
    intent: Intent,
) -> TypedExtractionOutput:
    """Consume typed extractor contract while keeping competitors-only compatibility."""
    extract_structured = getattr(extractor, "extract_structured", None)
    if callable(extract_structured):
        structured = await extract_structured(raw_results, intent)
        if isinstance(structured, TypedExtractionOutput):
            return structured
        raise ExtractionError(
            "Extractor.extract_structured() must return typed ExtractionOutput"
        )

    competitors = await extractor.extract(raw_results, intent)
    typed_competitors = [item for item in competitors if isinstance(item, Competitor)]
    if len(typed_competitors) != len(competitors):
        raise ExtractionError("Extractor.extract() returned invalid competitor entries")

    pop_structured_output = getattr(
        extractor, "pop_structured_output_for_current_task", None
    )
    if callable(pop_structured_output):
        structured = pop_structured_output()
        if isinstance(structured, TypedExtractionOutput):
            if structured.competitors:
                return structured
            return structured.model_copy(update={"competitors": typed_competitors})

    return TypedExtractionOutput(competitors=typed_competitors)


def safe_get_source_query_concurrency(source: DataSource) -> int:
    value = getattr(source, "_max_concurrent_queries", 2)
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return 2


def safe_set_source_query_concurrency(source: DataSource, value: int) -> None:
    setter = getattr(source, "set_runtime_max_concurrent_queries", None)
    if callable(setter):
        setter(max(1, value))


def safe_consume_source_diagnostics(source: DataSource) -> dict[str, Any]:
    consumer = getattr(source, "consume_last_search_diagnostics", None)
    if not callable(consumer):
        return {}
    payload = consumer()
    return payload if isinstance(payload, dict) else {}


def _localized_text(output_language: str, zh: str, en: str) -> str:
    return zh if output_language == "zh" else en
