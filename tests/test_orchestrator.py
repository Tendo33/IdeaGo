"""Tests for pipeline orchestrator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

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
from ideago.pipeline.aggregator import AggregationResult, Aggregator
from ideago.pipeline.events import EventType, PipelineEvent
from ideago.pipeline.extractor import Extractor
from ideago.pipeline.intent_parser import IntentParser
from ideago.pipeline.orchestrator import Orchestrator
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


def _build_orchestrator(
    tmp_path,
    sources: list | None = None,
    cache_hit: ResearchReport | None = None,
    extraction_fails: bool = False,
) -> tuple[Orchestrator, EventCollector]:
    intent_parser = MagicMock(spec=IntentParser)
    intent_parser.parse = AsyncMock(return_value=MOCK_INTENT)

    extractor = MagicMock(spec=Extractor)
    if extraction_fails:
        extractor.extract = AsyncMock(side_effect=RuntimeError("LLM failed"))
    else:
        extractor.extract = AsyncMock(return_value=[MOCK_COMPETITOR])

    aggregator = MagicMock(spec=Aggregator)
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

    orchestrator = Orchestrator(
        intent_parser=intent_parser,
        extractor=extractor,
        aggregator=aggregator,
        registry=registry,
        cache=cache,
        source_timeout=5,
        extraction_timeout=5,
    )
    collector = EventCollector()
    return orchestrator, collector


@pytest.mark.asyncio
async def test_orchestrator_full_pipeline(tmp_path) -> None:
    orch, collector = _build_orchestrator(tmp_path)
    report = await orch.run("test idea", callback=collector)

    assert isinstance(report, ResearchReport)
    assert report.query == "test idea"
    assert len(report.competitors) == 1
    assert report.market_summary != ""

    event_types = [e.type for e in collector.events]
    assert EventType.INTENT_PARSED in event_types
    assert EventType.SOURCE_STARTED in event_types
    assert EventType.SOURCE_COMPLETED in event_types
    assert EventType.REPORT_READY in event_types


@pytest.mark.asyncio
async def test_orchestrator_cache_hit_skips_pipeline(tmp_path) -> None:
    cached_report = ResearchReport(
        query="test idea",
        intent=MOCK_INTENT,
        competitors=[MOCK_COMPETITOR],
    )
    orch, collector = _build_orchestrator(tmp_path, cache_hit=cached_report)
    report = await orch.run("test idea", callback=collector)

    assert report.id == cached_report.id
    event_types = [e.type for e in collector.events]
    assert EventType.REPORT_READY in event_types
    assert EventType.SOURCE_STARTED not in event_types


@pytest.mark.asyncio
async def test_orchestrator_source_failure_partial_result(tmp_path) -> None:
    sources = [MockSource(Platform.GITHUB), FailingSource()]
    orch, collector = _build_orchestrator(tmp_path, sources=sources)
    report = await orch.run("test idea", callback=collector)

    assert len(report.source_results) == 2
    statuses = {sr.platform.value: sr.status.value for sr in report.source_results}
    assert statuses["github"] == "ok"
    assert statuses["tavily"] == "failed"

    event_types = [e.type for e in collector.events]
    assert EventType.SOURCE_FAILED in event_types


@pytest.mark.asyncio
async def test_orchestrator_extraction_failure_degrades(tmp_path) -> None:
    orch, collector = _build_orchestrator(tmp_path, extraction_fails=True)
    report = await orch.run("test idea", callback=collector)

    assert len(report.competitors) >= 1
    degraded = [sr for sr in report.source_results if sr.status.value == "degraded"]
    assert len(degraded) == 1
