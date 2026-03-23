"""Tests for LangGraph pipeline engine."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ideago.cache.file_cache import FileCache
from ideago.models.research import (
    Competitor,
    Intent,
    Platform,
    RawResult,
    RecommendationType,
    ResearchReport,
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
    output_language="en",
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


class CapturingSource(MockSource):
    def __init__(self, platform: Platform):
        super().__init__(platform)
        self.last_queries: list[str] = []

    async def search(self, queries: list[str], limit: int = 10) -> list[RawResult]:
        self.last_queries = list(queries)
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


class RecordingSource:
    shared_in_flight = 0
    shared_max_in_flight = 0

    def __init__(self, platform: Platform, delay_s: float = 0.03):
        self._platform = platform
        self._delay_s = delay_s
        self.in_flight = 0
        self.max_in_flight = 0
        self.last_runtime_concurrency: int | None = None
        self.last_queries_count = 0
        self._should_fail = False

    @property
    def platform(self) -> Platform:
        return self._platform

    def is_available(self) -> bool:
        return True

    def set_runtime_max_concurrent_queries(self, value: int | None) -> None:
        self.last_runtime_concurrency = value

    def set_should_fail(self, value: bool) -> None:
        self._should_fail = value

    def consume_last_search_diagnostics(self) -> dict:
        return {
            "partial_failure": False,
            "failed_queries": [],
            "timed_out_queries": [],
        }

    async def search(self, queries: list[str], limit: int = 10) -> list[RawResult]:
        self.last_queries_count = len(queries)
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        RecordingSource.shared_in_flight += 1
        RecordingSource.shared_max_in_flight = max(
            RecordingSource.shared_max_in_flight, RecordingSource.shared_in_flight
        )
        await asyncio.sleep(self._delay_s)
        self.in_flight -= 1
        RecordingSource.shared_in_flight -= 1
        if self._should_fail:
            raise ConnectionError("synthetic source failure")
        return [
            RawResult(
                title=f"{self.platform.value}-result",
                url=f"https://example.com/{self.platform.value}",
                platform=self.platform,
            )
        ]


class PublicFallbackSource(MockSource):
    @property
    def platform(self) -> Platform:
        return Platform.REDDIT

    def consume_last_search_diagnostics(self) -> dict:
        return {
            "partial_failure": False,
            "failed_queries": [],
            "timed_out_queries": [],
            "used_public_fallback": True,
            "fallback_reason": "missing_credentials",
        }


class EmptySource:
    @property
    def platform(self) -> Platform:
        return Platform.TAVILY

    def is_available(self) -> bool:
        return True

    async def search(self, queries: list[str], limit: int = 10) -> list[RawResult]:
        return []


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
    intent_override: Intent | None = None,
    source_global_concurrency: int = 3,
) -> tuple[LangGraphEngine, EventCollector, IntentParser, Aggregator]:
    intent_parser = MagicMock(spec=IntentParser)
    intent_parser.parse = AsyncMock(return_value=intent_override or MOCK_INTENT)

    extractor = MagicMock(spec=Extractor)
    if extraction_fails:
        extractor.extract = AsyncMock(side_effect=ExtractionError("LLM failed"))
    else:
        extractor.extract = AsyncMock(return_value=[MOCK_COMPETITOR])

    aggregator = MagicMock(spec=Aggregator)
    if aggregation_side_effect is not None:
        aggregator.analyze = AsyncMock(side_effect=aggregation_side_effect)
        aggregator.aggregate = AsyncMock(side_effect=aggregation_side_effect)
    else:
        aggregator.analyze = AsyncMock(return_value=MOCK_AGG_RESULT)
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
        source_global_concurrency=source_global_concurrency,
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
async def test_langgraph_engine_marks_public_fallback_source_as_degraded(
    tmp_path,
) -> None:
    engine, _, _, _ = _build_engine(
        tmp_path, sources=[PublicFallbackSource(Platform.REDDIT)]
    )
    report = await engine.run("test idea")

    assert len(report.source_results) == 1
    assert report.source_results[0].platform == Platform.REDDIT
    assert report.source_results[0].status.value == "degraded"
    assert "public Reddit fallback" in (report.source_results[0].error_msg or "")


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
    assert "Analysis failed" in report.market_summary
    assert report.confidence.sample_size >= 1
    assert report.cost_breakdown.llm_calls >= 0
    assert report.evidence_summary.evidence_items
    assert report.report_meta.llm_fault_tolerance.last_error_class in {
        "",
        "unknown_error",
    }


@pytest.mark.asyncio
async def test_langgraph_engine_chinese_fallback_content(tmp_path) -> None:
    zh_intent = Intent(
        keywords_en=["markdown", "notes"],
        app_type="browser-extension",
        target_scenario="用浏览器记录 Markdown 笔记",
        output_language="zh",
        cache_key="zh-intent",
    )
    engine, _, _, _ = _build_engine(
        tmp_path,
        aggregation_side_effect=AggregationError("aggregation crash"),
        intent_override=zh_intent,
    )

    report = await engine.run("帮我做一个 Markdown 笔记插件")

    assert "分析失败" in report.market_summary
    assert "无法给出明确结论" in report.go_no_go
    assert "生成" in report.confidence.freshness_hint


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
async def test_langgraph_engine_uses_query_builder_for_github_and_producthunt(
    tmp_path,
) -> None:
    github_source = CapturingSource(Platform.GITHUB)
    producthunt_source = CapturingSource(Platform.PRODUCT_HUNT)
    intent_override = Intent(
        keywords_en=["api monitoring", "alerting dashboard"],
        app_type="web",
        target_scenario="Track API latency and alert on incidents",
        output_language="en",
        cache_key="custom-intent",
    )
    engine, _, _, _ = _build_engine(
        tmp_path,
        sources=[github_source, producthunt_source],
        intent_override=intent_override,
    )

    await engine.run("test idea")

    assert len(github_source.last_queries) >= 2
    assert any("api monitoring" in q for q in github_source.last_queries)
    assert any("topic:" in q for q in github_source.last_queries)

    assert len(producthunt_source.last_queries) >= 2
    assert any(
        topic in producthunt_source.last_queries
        for topic in ["saas", "web-app", "productivity"]
    )


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
    assert aggregator.analyze.call_count == 2


@pytest.mark.asyncio
async def test_langgraph_engine_downgrades_go_when_evidence_is_weak(tmp_path) -> None:
    weak_go_result = AggregationResult(
        competitors=[],
        market_summary="Sparse evidence gathered.",
        go_no_go="Go - looks promising.",
        recommendation_type=RecommendationType.GO,
        differentiation_angles=[],
    )
    engine, _, _, _ = _build_engine(
        tmp_path,
        sources=[EmptySource()],
        aggregation_side_effect=[weak_go_result],
    )

    report = await engine.run("test idea")

    assert report.recommendation_type == RecommendationType.CAUTION
    assert "insufficient evidence" in report.go_no_go.lower()
    assert report.report_meta.quality_warnings
    assert any(
        "low evidence confidence" in warning.lower()
        for warning in report.report_meta.quality_warnings
    )


@pytest.mark.asyncio
async def test_langgraph_engine_keeps_go_when_evidence_is_strong(tmp_path) -> None:
    strong_go_result = AggregationResult(
        competitors=[MOCK_COMPETITOR],
        market_summary="Evidence is sufficient.",
        go_no_go="Go - evidence supports execution.",
        recommendation_type=RecommendationType.GO,
        differentiation_angles=["Niche focus"],
    )
    engine, _, _, _ = _build_engine(
        tmp_path,
        sources=[MockSource(Platform.GITHUB)],
        aggregation_side_effect=[strong_go_result],
    )

    report = await engine.run("test idea")

    assert report.recommendation_type == RecommendationType.GO
    assert report.report_meta.quality_warnings == []


@pytest.mark.asyncio
async def test_langgraph_engine_closes_saver_when_cancelled_during_enter(
    tmp_path,
) -> None:
    engine, _, _, _ = _build_engine(tmp_path)
    enter_gate = asyncio.Event()
    close_called = False

    class FakeSaver:
        async def setup(self) -> None:
            return None

    class FakeSaverContextManager:
        async def __aenter__(self) -> FakeSaver:
            await enter_gate.wait()
            return FakeSaver()

        async def __aexit__(self, _exc_type, _exc, _tb) -> None:
            nonlocal close_called
            close_called = True

    with patch(
        "langgraph.checkpoint.sqlite.aio.AsyncSqliteSaver.from_conn_string",
        return_value=FakeSaverContextManager(),
    ):
        run_task = asyncio.create_task(engine.run("cancel-safe-enter"))
        await asyncio.sleep(0)
        run_task.cancel()
        enter_gate.set()
        with pytest.raises(asyncio.CancelledError):
            await run_task

    assert close_called is True


@pytest.mark.asyncio
async def test_langgraph_engine_respects_source_global_concurrency(tmp_path) -> None:
    RecordingSource.shared_in_flight = 0
    RecordingSource.shared_max_in_flight = 0
    sources = [
        RecordingSource(Platform.GITHUB),
        RecordingSource(Platform.HACKERNEWS),
        RecordingSource(Platform.TAVILY),
    ]
    engine, _, _, _ = _build_engine(
        tmp_path,
        sources=sources,
        source_global_concurrency=1,
    )

    await engine.run("test idea")

    assert RecordingSource.shared_max_in_flight == 1


@pytest.mark.asyncio
async def test_langgraph_engine_adaptive_metrics_isolated_per_run(tmp_path) -> None:
    """Adaptive metrics are per-run: prior failures don't degrade subsequent runs."""
    source = RecordingSource(Platform.GITHUB)
    intent_override = Intent(
        keywords_en=["api", "monitoring", "alerts", "latency"],
        app_type="web",
        target_scenario="Track reliability incidents",
        output_language="en",
        cache_key="adaptive-intent",
    )
    engine, _, intent_parser, _ = _build_engine(
        tmp_path,
        sources=[source],
        intent_override=intent_override,
    )
    parse_count = 0

    async def parse_with_unique_cache(_query: str) -> Intent:
        nonlocal parse_count
        parse_count += 1
        return intent_override.model_copy(
            update={"cache_key": f"adaptive-{parse_count}"}
        )

    intent_parser.parse = AsyncMock(side_effect=parse_with_unique_cache)

    from ideago.pipeline.query_builder import build_queries

    full_query_count = len(build_queries(Platform.GITHUB, intent_override))

    source.set_should_fail(True)
    await engine.run("test idea 1", report_id="adaptive-1")
    await engine.run("test idea 2", report_id="adaptive-2")

    source.set_should_fail(False)
    await engine.run("test idea 3", report_id="adaptive-3")

    assert source.last_queries_count == full_query_count
