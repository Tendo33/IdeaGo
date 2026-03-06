"""Tests for LangGraph pipeline engine."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ideago.cache.file_cache import FileCache
from ideago.models.research import (
    Competitor,
    Intent,
    Platform,
    RawResult,
    ResearchReport,
    SearchQuery,
)
from ideago.pipeline import nodes as pipeline_nodes
from ideago.pipeline.aggregator import AggregationResult, Aggregator
from ideago.pipeline.events import EventType, PipelineEvent
from ideago.pipeline.exceptions import AggregationError, ExtractionError
from ideago.pipeline.extractor import Extractor
from ideago.pipeline.intent_parser import IntentParser
from ideago.pipeline.langgraph_engine import LangGraphEngine
from ideago.sources.registry import SourceRegistry

MOCK_INTENT = Intent(
    keywords_en=["markdown", "notes"],
    app_type="browser-extension",
    target_scenario="Take markdown notes",
    search_queries=[
        SearchQuery(platform=Platform.GITHUB, queries=["markdown notes"]),
        SearchQuery(platform=Platform.HACKERNEWS, queries=["markdown notes"]),
    ],
    cache_key="abc123",
)

MOCK_RAW_RESULTS = [
    RawResult(
        title="markdown-clipper",
        url="https://github.com/user/markdown-clipper",
        platform=Platform.GITHUB,
    ),
]

MOCK_COMPETITOR = Competitor(
    name="markdown-clipper",
    links=["https://github.com/user/markdown-clipper"],
    one_liner="Clip as markdown",
    source_platforms=[Platform.GITHUB],
    source_urls=["https://github.com/user/markdown-clipper"],
    relevance_score=0.8,
)

MOCK_AGG_RESULT = AggregationResult(
    competitors=[MOCK_COMPETITOR],
    market_summary="The space has several players.",
    go_no_go="Go with caution.",
    differentiation_angles=["Mobile support"],
)


class MockSource:
    def __init__(self, platform: Platform):
        self._platform = platform

    @property
    def platform(self) -> Platform:
        return self._platform

    def is_available(self) -> bool:
        return True

    async def search(self, queries: list[str], limit: int = 10) -> list[RawResult]:
        return MOCK_RAW_RESULTS


class HtmlSource:
    @property
    def platform(self) -> Platform:
        return Platform.HACKERNEWS

    def is_available(self) -> bool:
        return True

    async def search(self, queries: list[str], limit: int = 10) -> list[RawResult]:
        return [
            RawResult(
                title="Show HN: API monitor",
                description=(
                    "Hi HN, I&#x27;m Simon. <p>I built "
                    '<a href="https://apitally.io">Apitally</a></p>'
                ),
                url="https://news.ycombinator.com/item?id=123",
                platform=Platform.HACKERNEWS,
            )
        ]


class FailingSource:
    @property
    def platform(self) -> Platform:
        return Platform.TAVILY

    def is_available(self) -> bool:
        return True

    async def search(self, queries: list[str], limit: int = 10) -> list[RawResult]:
        raise ConnectionError("API down")


class EventCollector:
    def __init__(self):
        self.events: list[PipelineEvent] = []

    async def on_event(self, event: PipelineEvent) -> None:
        self.events.append(event)


def _build_engine(
    tmp_path,
    sources: list | None = None,
    cache_hit: ResearchReport | None = None,
    extraction_fails: bool = False,
    aggregation_side_effect: object | None = None,
) -> tuple[LangGraphEngine, EventCollector, IntentParser, Aggregator]:
    intent_parser = MagicMock(spec=IntentParser)
    intent_parser.parse = AsyncMock(return_value=MOCK_INTENT)

    extractor = MagicMock(spec=Extractor)
    if extraction_fails:
        extractor.extract = AsyncMock(side_effect=ExtractionError("LLM failed"))
    else:
        extractor.extract = AsyncMock(return_value=[MOCK_COMPETITOR])

    aggregator = MagicMock(spec=Aggregator)
    if aggregation_side_effect is not None:
        aggregator.aggregate = AsyncMock(side_effect=aggregation_side_effect)
    else:
        aggregator.aggregate = AsyncMock(return_value=MOCK_AGG_RESULT)

    registry = SourceRegistry()
    for src in sources or [MockSource(Platform.GITHUB)]:
        registry.register(src)

    cache = FileCache(str(tmp_path / "cache"), ttl_hours=24)
    if cache_hit:
        import json

        cache._dir.mkdir(parents=True, exist_ok=True)
        report_path = cache._dir / f"{cache_hit.id}.json"
        report_path.write_text(cache_hit.model_dump_json(indent=2), encoding="utf-8")
        index_path = cache._dir / "_index.json"
        index_entry = {
            "report_id": cache_hit.id,
            "query": cache_hit.query,
            "cache_key": cache_hit.intent.cache_key,
            "created_at": cache_hit.created_at.isoformat(),
            "competitor_count": len(cache_hit.competitors),
        }
        index_path.write_text(json.dumps([index_entry]), encoding="utf-8")

    engine = LangGraphEngine(
        intent_parser=intent_parser,
        extractor=extractor,
        aggregator=aggregator,
        registry=registry,
        cache=cache,
        checkpoint_db_path=str(tmp_path / "checkpoint.db"),
        source_timeout=5,
        extraction_timeout=5,
    )
    collector = EventCollector()
    return engine, collector, intent_parser, aggregator


@pytest.mark.asyncio
async def test_langgraph_engine_full_pipeline(tmp_path) -> None:
    engine, collector, _, _ = _build_engine(tmp_path)
    report = await engine.run("test idea", callback=collector)

    assert isinstance(report, ResearchReport)
    assert report.query == "test idea"
    assert len(report.competitors) == 1
    assert report.market_summary != ""
    assert report.confidence.sample_size >= 1
    assert 0 <= report.confidence.score <= 100
    assert isinstance(report.evidence_summary.top_evidence, list)
    assert report.cost_breakdown.source_calls >= 1
    assert report.report_meta.llm_fault_tolerance.endpoints_tried == []
    assert report.confidence.freshness_hint.startswith("Generated ")
    assert report.confidence.freshness_hint != "Generated moments ago"

    event_types = [e.type for e in collector.events]
    assert EventType.INTENT_PARSED in event_types
    assert EventType.SOURCE_STARTED in event_types
    assert EventType.SOURCE_COMPLETED in event_types
    assert EventType.REPORT_READY in event_types
    intent_event = next(
        e for e in collector.events if e.type == EventType.INTENT_PARSED
    )
    assert intent_event.data.get("target_scenario") == MOCK_INTENT.target_scenario


@pytest.mark.asyncio
async def test_langgraph_engine_cache_hit_skips_pipeline(tmp_path) -> None:
    cached_report = ResearchReport(
        query="test idea",
        intent=MOCK_INTENT,
        competitors=[MOCK_COMPETITOR],
    )
    engine, collector, _, _ = _build_engine(tmp_path, cache_hit=cached_report)
    report = await engine.run("test idea", callback=collector)

    assert report.id == cached_report.id
    event_types = [e.type for e in collector.events]
    assert EventType.REPORT_READY in event_types
    assert EventType.SOURCE_STARTED not in event_types


@pytest.mark.asyncio
async def test_langgraph_engine_source_failure_partial_result(tmp_path) -> None:
    sources = [MockSource(Platform.GITHUB), FailingSource()]
    engine, collector, _, _ = _build_engine(tmp_path, sources=sources)
    report = await engine.run("test idea", callback=collector)

    assert len(report.source_results) == 2
    statuses = {sr.platform.value: sr.status.value for sr in report.source_results}
    assert statuses["github"] == "ok"
    assert statuses["tavily"] == "failed"

    event_types = [e.type for e in collector.events]
    assert EventType.SOURCE_FAILED in event_types


@pytest.mark.asyncio
async def test_langgraph_engine_extraction_failure_degrades(tmp_path) -> None:
    engine, collector, _, _ = _build_engine(tmp_path, extraction_fails=True)
    report = await engine.run("test idea", callback=collector)

    assert len(report.competitors) >= 1
    degraded = [sr for sr in report.source_results if sr.status.value == "degraded"]
    assert len(degraded) == 1
    assert degraded[0].error_msg == "Extraction unavailable; showing raw results."
    assert "LLM extraction failed:" not in (degraded[0].error_msg or "")


@pytest.mark.asyncio
async def test_langgraph_engine_degraded_competitor_sanitizes_html_one_liner(
    tmp_path,
) -> None:
    engine, _, _, _ = _build_engine(
        tmp_path,
        sources=[HtmlSource()],
        extraction_fails=True,
    )
    report = await engine.run("test idea")

    degraded = [sr for sr in report.source_results if sr.status.value == "degraded"]
    assert len(degraded) == 1
    assert degraded[0].competitors
    one_liner = degraded[0].competitors[0].one_liner
    assert one_liner == "Hi HN, I'm Simon. I built Apitally"
    assert "<" not in one_liner
    assert "&#x27;" not in one_liner


@pytest.mark.asyncio
async def test_langgraph_engine_aggregation_failure_fallback(tmp_path) -> None:
    engine, _, _, _ = _build_engine(
        tmp_path,
        aggregation_side_effect=AggregationError("aggregation crash"),
    )
    report = await engine.run("test idea")

    assert report.competitors
    assert "Aggregation failed" in report.market_summary
    assert report.confidence.sample_size >= 1
    assert report.cost_breakdown.llm_calls >= 0
    assert report.evidence_summary.evidence_items
    assert report.report_meta.llm_fault_tolerance.last_error_class in {
        "",
        "unknown_error",
    }


@pytest.mark.asyncio
async def test_langgraph_engine_logs_extraction_counts_by_channel(tmp_path) -> None:
    sources = [MockSource(Platform.GITHUB), MockSource(Platform.HACKERNEWS)]
    engine, _, _, _ = _build_engine(tmp_path, sources=sources)

    with patch.object(pipeline_nodes.logger, "info") as info_log:
        await engine.run("test idea")

    per_channel_calls = [
        call.args
        for call in info_log.call_args_list
        if call.args and call.args[0] == "Extracted {} structured competitors from {}"
    ]
    assert per_channel_calls

    observed_channels = {args[2] for args in per_channel_calls}
    assert observed_channels == {"github", "hackernews"}

    summary_calls = [
        call.args
        for call in info_log.call_args_list
        if call.args and call.args[0] == "Per-source extracted content counts: {}"
    ]
    assert summary_calls
    latest_summary = summary_calls[-1][1]
    assert latest_summary == {"github": 1, "hackernews": 1}


@pytest.mark.asyncio
async def test_langgraph_engine_resume_from_checkpoint(tmp_path) -> None:
    aggregation_side_effect = [
        RuntimeError("crash in aggregation"),
        MOCK_AGG_RESULT,
    ]
    engine, _, intent_parser, aggregator = _build_engine(
        tmp_path,
        aggregation_side_effect=aggregation_side_effect,
    )

    with pytest.raises(RuntimeError):
        await engine.run("test idea", report_id="resume-report-id")

    report = await engine.run("test idea", report_id="resume-report-id")
    assert report.query == "test idea"
    assert intent_parser.parse.call_count == 1
    assert aggregator.aggregate.call_count == 2
