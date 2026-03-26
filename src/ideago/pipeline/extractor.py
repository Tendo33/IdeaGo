"""Extractor — uses LLM to extract competitors from raw search results.

使用 LLM 从原始搜索结果中提取竞品信息。
"""

from __future__ import annotations

import asyncio
import json
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from pydantic import Field

from ideago.llm.chat_model import ChatModelClient
from ideago.llm.invoke_helpers import invoke_json_with_optional_meta
from ideago.llm.prompt_loader import load_prompt
from ideago.models.base import BaseModel
from ideago.models.research import (
    CommercialSignal,
    Competitor,
    EvidenceCategory,
    EvidenceItem,
    Intent,
    PainSignal,
    Platform,
    RawResult,
)
from ideago.observability.log_config import get_logger
from ideago.pipeline.exceptions import ExtractionError

logger = get_logger(__name__)


def _localized_text(output_language: str, zh: str, en: str) -> str:
    return zh if output_language == "zh" else en


class ExtractionOutput(BaseModel):
    """Typed extraction output for competitor and evidence signals."""

    competitors: list[Competitor] = Field(default_factory=list)
    pain_signals: list[PainSignal] = Field(default_factory=list)
    commercial_signals: list[CommercialSignal] = Field(default_factory=list)
    migration_signals: list[EvidenceItem] = Field(default_factory=list)
    evidence_items: list[EvidenceItem] = Field(default_factory=list)


class Extractor:
    """Extracts structured Competitor objects from raw search results using LLM."""

    def __init__(self, llm: ChatModelClient) -> None:
        self._llm = llm
        self._llm_metrics_by_task: dict[int, dict[str, Any]] = {}
        self._structured_output_by_task: dict[int, ExtractionOutput] = {}
        self._latest_structured_output = ExtractionOutput()

    async def extract(
        self,
        raw_results: list[RawResult],
        intent: Intent,
    ) -> list[Competitor]:
        """Extract competitors from raw results of a single platform.

        Args:
            raw_results: Raw search results from one data source.
            intent: Parsed user intent with keywords, app_type, and scenario.

        Returns:
            List of extracted Competitor objects. Invalid entries are skipped.
        """
        structured = await self.extract_structured(raw_results, intent)
        return structured.competitors

    async def extract_structured(
        self,
        raw_results: list[RawResult],
        intent: Intent,
    ) -> ExtractionOutput:
        """Extract typed competitors + signals + evidence from one source payload."""
        if not raw_results:
            return ExtractionOutput()

        try:
            platform = raw_results[0].platform
            allowed_urls = {
                _normalize_url(r.url) for r in raw_results if _normalize_url(r.url)
            }
            raw_json = json.dumps(
                [
                    _serialize_raw_for_extraction(raw_result)
                    for raw_result in raw_results
                ],
                ensure_ascii=False,
            )
            prompt_name = (
                "extractor_appstore" if platform == Platform.APPSTORE else "extractor"
            )
            prompt = load_prompt(
                prompt_name,
                platform=platform.value,
                raw_results_json=raw_json,
                keywords=", ".join(intent.keywords_en),
                app_type=intent.app_type,
                target_scenario=intent.target_scenario,
                output_language=intent.output_language,
            )
            data, llm_metrics = await invoke_json_with_optional_meta(
                llm=self._llm,
                prompt=prompt,
                system="You are a competitor analysis expert. Return only valid JSON.",
            )
            self._store_metrics_for_current_task(llm_metrics)
            structured = self._parse_structured_output(
                payload=data,
                allowed_urls=allowed_urls,
                output_language=intent.output_language,
            )
            self._store_structured_output_for_current_task(structured)
            logger.debug(
                (
                    "Extractor LLM response for {}: competitors={}, pain={}, "
                    "commercial={}, migration={}, evidence={}"
                ),
                platform.value,
                len(structured.competitors),
                len(structured.pain_signals),
                len(structured.commercial_signals),
                len(structured.migration_signals),
                len(structured.evidence_items),
            )
            return structured
        except ExtractionError:
            raise
        except Exception as exc:
            raise ExtractionError(f"Failed to extract competitors: {exc}") from exc

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

    def pop_structured_output_for_current_task(self) -> ExtractionOutput:
        task = asyncio.current_task()
        if task is None:
            return ExtractionOutput()
        return self._structured_output_by_task.pop(id(task), ExtractionOutput())

    def _store_structured_output_for_current_task(
        self,
        output: ExtractionOutput,
    ) -> None:
        task = asyncio.current_task()
        self._latest_structured_output = output
        if task is None:
            return
        self._structured_output_by_task[id(task)] = output

    def get_last_structured_output(self) -> ExtractionOutput:
        """Return latest typed extraction output snapshot."""
        return self._latest_structured_output

    def _parse_structured_output(
        self,
        *,
        payload: object,
        allowed_urls: set[str],
        output_language: str,
    ) -> ExtractionOutput:
        if not isinstance(payload, dict):
            raise ExtractionError("Extractor response payload must be a JSON object")

        competitors = self._parse_competitors(
            raw_items=payload.get("competitors"),
            allowed_urls=allowed_urls,
            output_language=output_language,
        )
        pain_signals = self._parse_pain_signals(
            raw_items=payload.get("pain_signals"),
            allowed_urls=allowed_urls,
        )
        commercial_signals = self._parse_commercial_signals(
            raw_items=payload.get("commercial_signals"),
            allowed_urls=allowed_urls,
        )
        migration_signals = self._parse_migration_signals(
            raw_items=payload.get("migration_signals"),
            allowed_urls=allowed_urls,
        )
        evidence_items = self._parse_evidence_items(
            raw_items=payload.get("evidence_items"),
            allowed_urls=allowed_urls,
        )
        return ExtractionOutput(
            competitors=competitors,
            pain_signals=pain_signals,
            commercial_signals=commercial_signals,
            migration_signals=migration_signals,
            evidence_items=evidence_items,
        )

    def _parse_competitors(
        self,
        *,
        raw_items: object,
        allowed_urls: set[str],
        output_language: str,
    ) -> list[Competitor]:
        if not isinstance(raw_items, list):
            return []
        result: list[Competitor] = []
        for entry in raw_items:
            try:
                comp = Competitor.model_validate(entry)
            except Exception:
                logger.warning("Skipping invalid competitor entry: {}", entry)
                continue
            filtered_links = [
                link for link in comp.links if _normalize_url(link) in allowed_urls
            ]
            filtered_source_urls = [
                url for url in comp.source_urls if _normalize_url(url) in allowed_urls
            ]
            if not filtered_links:
                logger.warning(
                    "Dropping competitor '{}' due to unverifiable links",
                    comp.name,
                )
                continue
            if len(filtered_links) < len(comp.links):
                logger.info(
                    "Filtered {} fabricated links for competitor '{}'",
                    len(comp.links) - len(filtered_links),
                    comp.name,
                )
            normalized_comp = comp.model_copy(
                update={
                    "links": filtered_links,
                    "source_urls": filtered_source_urls or filtered_links,
                }
            )
            result.append(
                _backfill_competitor_tradeoffs(
                    normalized_comp,
                    output_language=output_language,
                )
            )
        return result

    def _parse_pain_signals(
        self,
        *,
        raw_items: object,
        allowed_urls: set[str],
    ) -> list[PainSignal]:
        if not isinstance(raw_items, list):
            return []
        signals: list[PainSignal] = []
        for entry in raw_items:
            try:
                signal = PainSignal.model_validate(entry)
            except Exception:
                logger.warning("Skipping invalid pain signal: {}", entry)
                continue
            filtered_evidence_urls = _filter_allowed_urls(
                signal.evidence_urls, allowed_urls
            )
            if not filtered_evidence_urls:
                logger.warning(
                    "Dropping pain signal '{}' due to unverifiable evidence urls",
                    signal.theme,
                )
                continue
            signals.append(
                signal.model_copy(update={"evidence_urls": filtered_evidence_urls})
            )
        return signals

    def _parse_commercial_signals(
        self,
        *,
        raw_items: object,
        allowed_urls: set[str],
    ) -> list[CommercialSignal]:
        if not isinstance(raw_items, list):
            return []
        signals: list[CommercialSignal] = []
        for entry in raw_items:
            try:
                signal = CommercialSignal.model_validate(entry)
            except Exception:
                logger.warning("Skipping invalid commercial signal: {}", entry)
                continue
            filtered_evidence_urls = _filter_allowed_urls(
                signal.evidence_urls, allowed_urls
            )
            if not filtered_evidence_urls:
                logger.warning(
                    "Dropping commercial signal '{}' due to unverifiable evidence urls",
                    signal.theme,
                )
                continue
            signals.append(
                signal.model_copy(update={"evidence_urls": filtered_evidence_urls})
            )
        return signals

    def _parse_migration_signals(
        self,
        *,
        raw_items: object,
        allowed_urls: set[str],
    ) -> list[EvidenceItem]:
        if not isinstance(raw_items, list):
            return []
        signals: list[EvidenceItem] = []
        for entry in raw_items:
            candidate = self._normalize_migration_entry(entry)
            if candidate is None:
                logger.warning("Skipping invalid migration signal: {}", entry)
                continue
            try:
                signal = EvidenceItem.model_validate(candidate)
            except Exception:
                logger.warning("Skipping invalid migration signal: {}", entry)
                continue
            normalized_url = _normalize_url(signal.url)
            if not normalized_url or normalized_url not in allowed_urls:
                logger.warning(
                    "Dropping migration signal '{}' due to unverifiable evidence url",
                    signal.title,
                )
                continue
            signals.append(
                signal.model_copy(update={"category": EvidenceCategory.MIGRATION})
            )
        return signals

    def _parse_evidence_items(
        self,
        *,
        raw_items: object,
        allowed_urls: set[str],
    ) -> list[EvidenceItem]:
        if not isinstance(raw_items, list):
            return []
        evidence_items: list[EvidenceItem] = []
        for entry in raw_items:
            try:
                evidence = EvidenceItem.model_validate(entry)
            except Exception:
                logger.warning("Skipping invalid evidence item: {}", entry)
                continue
            if evidence.url and _normalize_url(evidence.url) not in allowed_urls:
                logger.warning(
                    "Dropping evidence '{}' due to unverifiable url",
                    evidence.title,
                )
                continue
            evidence_items.append(evidence)
        return evidence_items

    @staticmethod
    def _normalize_migration_entry(entry: object) -> dict[str, Any] | None:
        if not isinstance(entry, dict):
            return None
        raw_urls = entry.get("evidence_urls")
        url = entry.get("url")
        if (not isinstance(url, str) or not url.strip()) and isinstance(raw_urls, list):
            first_url = next(
                (item for item in raw_urls if isinstance(item, str) and item.strip()),
                "",
            )
            url = first_url
        platform_value = entry.get("platform")
        if not platform_value:
            source_platforms = entry.get("source_platforms")
            if isinstance(source_platforms, list) and source_platforms:
                platform_value = source_platforms[0]
        return {
            "title": entry.get("title") or entry.get("theme") or "Migration signal",
            "url": url or "",
            "platform": platform_value,
            "snippet": entry.get("snippet")
            or entry.get("summary")
            or entry.get("switch_trigger")
            or "",
            "category": "migration",
            "freshness_hint": entry.get("freshness_hint") or "",
            "matched_query": entry.get("matched_query") or "",
            "query_family": entry.get("query_family") or "migration_discovery",
        }


def _normalize_url(url: str) -> str:
    """Normalize URL for strict source-link verification."""
    if not url:
        return ""
    try:
        parsed = urlsplit(url.strip())
    except ValueError:
        return ""
    if not parsed.scheme or not parsed.netloc:
        return ""
    path = parsed.path.rstrip("/")
    return urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            "",
            "",
        )
    )


def _filter_allowed_urls(urls: list[str], allowed_urls: set[str]) -> list[str]:
    return [url for url in urls if _normalize_url(url) in allowed_urls]


def _backfill_competitor_tradeoffs(
    competitor: Competitor,
    *,
    output_language: str,
) -> Competitor:
    strengths = _normalize_string_list(competitor.strengths)
    weaknesses = _normalize_string_list(competitor.weaknesses)
    features = _normalize_string_list(competitor.features)

    if not strengths:
        strengths = _build_fallback_strengths(
            competitor=competitor,
            features=features,
            output_language=output_language,
        )
    if not weaknesses:
        weaknesses = _build_fallback_weaknesses(
            competitor=competitor,
            features=features,
            output_language=output_language,
        )

    return competitor.model_copy(
        update={
            "strengths": strengths,
            "weaknesses": weaknesses,
        }
    )


def _build_fallback_strengths(
    *,
    competitor: Competitor,
    features: list[str],
    output_language: str,
) -> list[str]:
    fallback: list[str] = []
    if features:
        lead_features = ", ".join(features[:2])
        fallback.append(
            _localized_text(
                output_language,
                f"覆盖的能力点较明确，重点包括 {lead_features}。",
                f"Feature coverage is explicit, especially around {lead_features}.",
            )
        )
    if competitor.pricing:
        fallback.append(
            _localized_text(
                output_language,
                "定价信息公开，便于采购方快速判断预算匹配度。",
                "Pricing is explicitly stated, which helps buyers evaluate fit quickly.",
            )
        )
    if not fallback and competitor.one_liner.strip():
        fallback.append(
            _localized_text(
                output_language,
                "定位描述相对清晰，能快速看出产品主要解决的问题。",
                "The positioning is clear enough to understand the primary use case quickly.",
            )
        )
    return fallback[:2]


def _build_fallback_weaknesses(
    *,
    competitor: Competitor,
    features: list[str],
    output_language: str,
) -> list[str]:
    fallback: list[str] = []
    if len(competitor.source_platforms) <= 1:
        fallback.append(
            _localized_text(
                output_language,
                "当前证据主要来自单一来源，集成深度、部署复杂度等细节仍不够明确。",
                "Current evidence comes from a single source, so integration depth and deployment complexity remain unclear.",
            )
        )
    if not competitor.pricing:
        fallback.append(
            _localized_text(
                output_language,
                "现有材料没有给出明确价格，采购门槛与商业模式仍需进一步核实。",
                "Pricing is not explicit in the available evidence, so buying friction and business model still need verification.",
            )
        )
    elif len(features) < 2:
        fallback.append(
            _localized_text(
                output_language,
                "公开信息对功能边界描述有限，暂时难以判断能力覆盖是否完整。",
                "Public information only describes a narrow slice of functionality, making overall coverage harder to assess.",
            )
        )
    if not fallback:
        fallback.append(
            _localized_text(
                output_language,
                "现有公开材料更偏概览描述，真实落地效果仍需要更多一手验证。",
                "Available material is still high-level, so real-world execution quality needs more first-hand validation.",
            )
        )
    return fallback[:2]


def _normalize_string_list(values: list[str]) -> list[str]:
    return [
        value.strip() for value in values if isinstance(value, str) and value.strip()
    ]


def _serialize_raw_for_extraction(raw: RawResult) -> dict[str, Any]:
    if raw.platform != Platform.APPSTORE:
        return raw.model_dump(mode="json", exclude={"raw_data", "fetched_at"})

    appstore_meta = {
        "track_id": raw.raw_data.get("track_id"),
        "bundle_id": raw.raw_data.get("bundle_id"),
        "seller_name": raw.raw_data.get("seller_name"),
        "primary_genre_name": raw.raw_data.get("primary_genre_name"),
        "rating": raw.raw_data.get("rating"),
        "rating_count": raw.raw_data.get("rating_count"),
        "price_numeric": raw.raw_data.get("price_numeric"),
        "price_label": raw.raw_data.get("price_label"),
        "currency": raw.raw_data.get("currency"),
        "version": raw.raw_data.get("version"),
        "release_date_iso": raw.raw_data.get("release_date_iso"),
        "canonical_track_url": raw.raw_data.get("canonical_track_url"),
    }
    return {
        "title": raw.title,
        "description": raw.description,
        "url": raw.url,
        "platform": raw.platform.value,
        "appstore_meta": appstore_meta,
    }
