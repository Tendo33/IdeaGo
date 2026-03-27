"""Tests for LangGraph pipeline engine."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ideago.cache.file_cache import FileCache
from ideago.config.settings import Settings
from ideago.llm.prompt_loader import load_prompt
from ideago.models.research import (
    CommercialSignal,
    Competitor,
    EvidenceCategory,
    EvidenceItem,
    Intent,
    OpportunityScoreBreakdown,
    PainSignal,
    Platform,
    QueryFamily,
    QueryGroup,
    QueryPlan,
    QueryRewrite,
    RawResult,
    RecommendationType,
    ResearchReport,
    SourceStatus,
    WhitespaceOpportunity,
)
from ideago.pipeline import aggregator as pipeline_aggregator
from ideago.pipeline import nodes as pipeline_nodes
from ideago.pipeline.aggregator import AggregationResult, Aggregator
from ideago.pipeline.events import EventType, PipelineEvent
from ideago.pipeline.exceptions import AggregationError, ExtractionError
from ideago.pipeline.extractor import ExtractionOutput, Extractor
from ideago.pipeline.graph_state import GraphState
from ideago.pipeline.intent_parser import IntentParser
from ideago.pipeline.langgraph_engine import LangGraphEngine
from ideago.pipeline.query_builder import infer_query_family
from ideago.pipeline.query_planning import QueryPlanner
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


def test_aggregation_result_supports_decision_first_signal_carriers() -> None:
    result = AggregationResult(
        competitors=[MOCK_COMPETITOR],
        market_summary="Pain clusters exist across multiple sources.",
        go_no_go="Caution - niche wedge exists.",
        recommendation_type=RecommendationType.CAUTION,
        differentiation_angles=["SMB speed wedge"],
        pain_signals=[
            PainSignal(
                theme="Slow onboarding",
                summary="Users complain that setup takes too long.",
                intensity=0.8,
                source_platforms=[Platform.REDDIT],
            )
        ],
        commercial_signals=[
            CommercialSignal(
                theme="Willingness to pay for faster setup",
                summary="Buyers compare paid onboarding tools.",
                intent_strength=0.7,
                source_platforms=[Platform.TAVILY],
            )
        ],
        whitespace_opportunities=[
            WhitespaceOpportunity(
                title="SMB onboarding wedge",
                wedge="Instant setup",
                potential_score=0.74,
            )
        ],
        opportunity_score=OpportunityScoreBreakdown(score=0.68),
        evidence_items=[
            EvidenceItem(
                category=EvidenceCategory.PAIN,
                title="Setup complaints",
                url="https://example.com/thread",
                platform="reddit",
                snippet="Setup takes too long.",
                query_family="pain_discovery",
            )
        ],
        uncertainty_notes=["Evidence is concentrated in SMB workflows."],
    )

    assert result.pain_signals[0].theme == "Slow onboarding"
    assert result.commercial_signals[0].intent_strength == 0.7
    assert result.whitespace_opportunities[0].wedge == "Instant setup"
    assert result.opportunity_score.score == 0.68
    assert result.evidence_items[0].category == EvidenceCategory.PAIN
    assert result.uncertainty_notes == ["Evidence is concentrated in SMB workflows."]


def test_graph_state_supports_typed_signal_collections() -> None:
    state: GraphState = {
        "query": "AI status report copilot",
        "intent": MOCK_INTENT,
        "raw_by_source": {"github": MOCK_RAW_RESULTS},
        "filtered_by_source": {"github": MOCK_RAW_RESULTS},
        "source_results": [],
        "all_competitors": [MOCK_COMPETITOR],
        "merged_competitors": [MOCK_COMPETITOR],
        "extracted_pain_signals": [PainSignal(theme="Manual reporting", intensity=0.9)],
        "extracted_commercial_signals": [
            CommercialSignal(theme="Paid automation intent", intent_strength=0.6)
        ],
        "extracted_evidence_items": [
            EvidenceItem(title="Thread", category=EvidenceCategory.PAIN)
        ],
        "aggregation_result": AggregationResult(),
    }

    assert state["extracted_pain_signals"][0].theme == "Manual reporting"
    assert state["extracted_commercial_signals"][0].intent_strength == 0.6
    assert state["extracted_evidence_items"][0].category == EvidenceCategory.PAIN


def test_aggregator_prompt_supports_typed_signal_placeholders() -> None:
    prompt = load_prompt(
        "aggregator",
        competitors_json='[{"name":"Tool A"}]',
        pain_signals_json='[{"theme":"Slow onboarding"}]',
        commercial_signals_json='[{"theme":"Budgeted demand"}]',
        evidence_items_json='[{"title":"Pain thread"}]',
        original_query="fast onboarding tool",
        output_language="en",
    )

    assert "Slow onboarding" in prompt
    assert "Budgeted demand" in prompt
    assert "Pain thread" in prompt
    assert "{pain_signals_json}" not in prompt
    assert "{commercial_signals_json}" not in prompt
    assert "{evidence_items_json}" not in prompt


@pytest.mark.asyncio
async def test_aggregator_synthesizes_whitespace_and_entry_wedge_from_typed_carriers() -> (
    None
):
    aggregator = Aggregator(llm=MagicMock())
    pain_signals = [
        PainSignal(
            theme="Slow onboarding",
            summary="Users complain setup takes too long.",
            intensity=0.84,
            frequency=0.73,
            evidence_urls=["https://example.com/thread"],
            source_platforms=[Platform.REDDIT],
        )
    ]
    commercial_signals = [
        CommercialSignal(
            theme="Willingness to pay for instant setup",
            summary="Buyers compare paid options for faster rollout.",
            intent_strength=0.78,
            monetization_hint="Team onboarding package",
            evidence_urls=["https://example.com/pricing"],
            source_platforms=[Platform.TAVILY],
        )
    ]
    evidence_items = [
        EvidenceItem(
            title="Setup complaint thread",
            url="https://example.com/thread",
            platform=Platform.REDDIT,
            snippet="Setup still takes more than an hour.",
            category=EvidenceCategory.PAIN,
            query_family="pain_discovery",
        )
    ]
    payload = {
        "market_summary": "Incumbents cover broad workflows but leave setup speed underserved.",
        "recommendation_type": "caution",
        "go_no_go": "Caution - enter with a setup-speed wedge for SMB teams.",
        "differentiation_angles": [
            "Promise instant setup instead of heavyweight onboarding",
            "Package prebuilt automations for first-week activation",
        ],
        "whitespace_opportunities": [
            {
                "title": "SMB onboarding speed wedge",
                "description": "Focus on teams that need value in the first day.",
                "target_segment": "SMB operations teams",
                "wedge": "Instant setup with opinionated defaults",
                "potential_score": 0.79,
                "confidence": 0.71,
                "supporting_evidence": [
                    "https://example.com/thread",
                    "https://example.com/pricing",
                ],
            }
        ],
        "opportunity_score": {
            "pain_intensity": 0.82,
            "solution_gap": 0.76,
            "commercial_intent": 0.74,
            "freshness": 0.68,
            "competition_density": 0.42,
            "score": 0.73,
        },
        "uncertainty_notes": ["Evidence is strongest in SMB onboarding workflows."],
    }

    with (
        patch(
            "ideago.pipeline.aggregator.load_prompt",
            return_value="aggregator-prompt",
        ) as mock_load_prompt,
        patch(
            "ideago.pipeline.aggregator.invoke_json_with_optional_meta",
            new=AsyncMock(return_value=(payload, {"llm_calls": 1})),
        ) as mock_invoke,
    ):
        result = await aggregator.analyze(
            [MOCK_COMPETITOR],
            "fast onboarding tool",
            output_language="en",
            pain_signals=pain_signals,
            commercial_signals=commercial_signals,
            evidence_items=evidence_items,
        )

    assert result.recommendation_type == RecommendationType.CAUTION
    assert (
        result.whitespace_opportunities[0].wedge
        == "Instant setup with opinionated defaults"
    )
    assert result.whitespace_opportunities[0].target_segment == "SMB operations teams"
    assert result.differentiation_angles[0].startswith("Promise instant setup")
    assert result.opportunity_score.score == pytest.approx(0.73)
    assert result.pain_signals[0].theme == "Slow onboarding"
    assert result.commercial_signals[0].intent_strength == pytest.approx(0.78)
    assert result.evidence_items[0].category == EvidenceCategory.PAIN
    assert result.uncertainty_notes == [
        "Evidence is strongest in SMB onboarding workflows."
    ]
    invoke_kwargs = mock_invoke.await_args.kwargs
    assert invoke_kwargs["prompt"] == "aggregator-prompt"
    load_kwargs = mock_load_prompt.call_args.kwargs
    assert "Slow onboarding" in load_kwargs["pain_signals_json"]
    assert (
        "Willingness to pay for instant setup" in load_kwargs["commercial_signals_json"]
    )
    assert "Setup complaint thread" in load_kwargs["evidence_items_json"]


@pytest.mark.asyncio
async def test_aggregator_remains_backward_compatible_without_typed_carriers() -> None:
    aggregator = Aggregator(llm=MagicMock())
    payload = {
        "market_summary": "Crowded but still differentiated by workflow specialization.",
        "recommendation_type": "go",
        "go_no_go": "Go - there is room for a focused workflow wedge.",
        "differentiation_angles": ["Own a narrow workflow first"],
        "whitespace_opportunities": [],
        "opportunity_score": {"score": 0.58},
    }

    with (
        patch(
            "ideago.pipeline.aggregator.load_prompt", return_value="aggregator-prompt"
        ),
        patch(
            "ideago.pipeline.aggregator.invoke_json_with_optional_meta",
            new=AsyncMock(return_value=(payload, {"llm_calls": 1})),
        ),
    ):
        result = await aggregator.aggregate(
            [MOCK_COMPETITOR],
            "test idea",
            output_language="en",
        )

    assert result.market_summary.startswith("Crowded")
    assert result.recommendation_type == RecommendationType.GO
    assert result.whitespace_opportunities == []
    assert result.pain_signals == []
    assert result.commercial_signals == []


@pytest.mark.asyncio
async def test_aggregator_emits_synthesis_observability_metrics() -> None:
    aggregator = Aggregator(llm=MagicMock())
    source_url = "https://example.com/thread"
    payload = {
        "market_summary": "Signals indicate underserved setup workflows.",
        "recommendation_type": "caution",
        "go_no_go": "Caution - enter with a focused setup wedge.",
        "differentiation_angles": ["Instant setup promise"],
        "whitespace_opportunities": [],
        "opportunity_score": {"score": 0.0},
    }

    with (
        patch(
            "ideago.pipeline.aggregator.load_prompt",
            return_value="aggregator-prompt",
        ),
        patch(
            "ideago.pipeline.aggregator.invoke_json_with_optional_meta",
            new=AsyncMock(return_value=(payload, {"llm_calls": 1})),
        ),
        patch.object(pipeline_aggregator.logger, "info") as info_log,
    ):
        await aggregator.analyze(
            [MOCK_COMPETITOR],
            "fast onboarding tool",
            output_language="en",
            pain_signals=[
                PainSignal(
                    theme="Slow onboarding",
                    summary="Users report setup friction.",
                    intensity=0.8,
                    evidence_urls=[source_url],
                    source_platforms=[Platform.REDDIT],
                )
            ],
            commercial_signals=[
                CommercialSignal(
                    theme="Paid setup demand",
                    intent_strength=0.72,
                    evidence_urls=[source_url],
                    source_platforms=[Platform.TAVILY],
                )
            ],
            evidence_items=[
                EvidenceItem(
                    title="Setup pain thread",
                    url=source_url,
                    platform=Platform.REDDIT,
                    category=EvidenceCategory.PAIN,
                    query_family="pain_discovery",
                )
            ],
        )

    observability_calls = [
        call.args
        for call in info_log.call_args_list
        if call.args
        and call.args[0] == "observability_event={} payload={}"
        and call.args[1] == "aggregation_synthesis_summary"
    ]
    assert observability_calls

    payload = observability_calls[-1][2]
    assert payload["evidence_category_counts"] == {"pain": 1}
    assert payload["whitespace_opportunity_count"] >= 1
    assert payload["whitespace_generation_rate"] == pytest.approx(1.0)
    assert payload["whitespace_fallback_used"] is True


@pytest.mark.asyncio
async def test_extractor_structured_output_is_typed_and_filters_unverified_urls() -> (
    None
):
    extractor = Extractor(llm=MagicMock())
    raw_results = [
        RawResult(
            title="Signal-rich result",
            description="Contains user pain and commercial clues",
            url="https://example.com/product",
            platform=Platform.TAVILY,
        )
    ]
    payload = {
        "competitors": [
            {
                "name": "Product A",
                "links": [
                    "https://example.com/product",
                    "https://fabricated.invalid/phantom",
                ],
                "one_liner": "Competes directly on workflow automation",
                "features": ["automation", "alerts"],
                "pricing": "Freemium",
                "strengths": ["Strong integrations"],
                "weaknesses": ["Slow onboarding"],
                "relevance_score": 0.88,
                "source_platforms": ["tavily"],
                "source_urls": [
                    "https://example.com/product",
                    "https://fabricated.invalid/phantom",
                ],
            }
        ],
        "pain_signals": [
            {
                "theme": "Onboarding friction",
                "summary": "Users report setup takes too long.",
                "intensity": 0.82,
                "frequency": 0.74,
                "evidence_urls": [
                    "https://example.com/product",
                    "https://fabricated.invalid/ghost",
                ],
                "source_platforms": ["tavily"],
            }
        ],
        "commercial_signals": [
            {
                "theme": "Willingness to pay for reliability",
                "summary": "Users compare paid plans for uptime guarantees.",
                "intent_strength": 0.76,
                "monetization_hint": "Team reliability package",
                "evidence_urls": ["https://example.com/product"],
                "source_platforms": ["tavily"],
            }
        ],
        "migration_signals": [
            {
                "theme": "Switch away from incumbent",
                "summary": "Users discuss replacing current stack.",
                "switch_trigger": "Missed incident alerts",
                "switch_from": "Incumbent A",
                "switch_to": "Product A",
                "urgency": 0.7,
                "evidence_urls": [
                    "https://example.com/product",
                    "https://fabricated.invalid/ghost",
                ],
                "source_platforms": ["tavily"],
            }
        ],
        "evidence_items": [
            {
                "title": "Pain discussion thread",
                "url": "https://example.com/product",
                "platform": "tavily",
                "snippet": "Setup is still painful for first-time users.",
                "category": "pain",
                "matched_query": "markdown notes pain points",
                "query_family": "pain_discovery",
            },
            {
                "title": "Fabricated evidence",
                "url": "https://fabricated.invalid/ghost",
                "platform": "tavily",
                "snippet": "Should be removed by URL verifier",
                "category": "market",
            },
        ],
    }

    with (
        patch(
            "ideago.pipeline.extractor.load_prompt",
            return_value="extractor-prompt",
        ),
        patch(
            "ideago.pipeline.extractor.invoke_json_with_optional_meta",
            new=AsyncMock(return_value=(payload, {"llm_calls": 1})),
        ),
    ):
        structured = await extractor.extract_structured(raw_results, MOCK_INTENT)

    assert isinstance(structured, ExtractionOutput)
    assert len(structured.competitors) == 1
    assert structured.competitors[0].links == ["https://example.com/product"]
    assert structured.competitors[0].source_urls == ["https://example.com/product"]
    assert structured.pain_signals[0].evidence_urls == ["https://example.com/product"]
    assert structured.commercial_signals[0].theme.startswith("Willingness")
    assert structured.migration_signals[0].category == EvidenceCategory.MIGRATION
    assert structured.migration_signals[0].url == "https://example.com/product"
    assert len(structured.evidence_items) == 1
    assert structured.evidence_items[0].category == EvidenceCategory.PAIN


@pytest.mark.asyncio
async def test_extractor_extract_preserves_legacy_competitor_return_with_typed_side_output() -> (
    None
):
    extractor = Extractor(llm=MagicMock())
    raw_results = [
        RawResult(
            title="Competitor result",
            url="https://example.com/tool",
            platform=Platform.GITHUB,
        )
    ]
    payload = {
        "competitors": [
            {
                "name": "Tool X",
                "links": ["https://example.com/tool"],
                "one_liner": "A direct competitor",
                "features": ["sync"],
                "pricing": None,
                "strengths": ["simple UX"],
                "weaknesses": ["limited integrations"],
                "relevance_score": 0.8,
                "source_platforms": ["github"],
                "source_urls": ["https://example.com/tool"],
            }
        ],
        "pain_signals": [
            {
                "theme": "Manual workflow",
                "evidence_urls": ["https://example.com/tool"],
            }
        ],
        "commercial_signals": [
            {
                "theme": "Paid automation demand",
                "evidence_urls": ["https://example.com/tool"],
            }
        ],
        "migration_signals": [
            {
                "title": "Switch intent",
                "url": "https://example.com/tool",
                "platform": "github",
                "category": "migration",
            }
        ],
        "evidence_items": [
            {
                "title": "Migration note",
                "url": "https://example.com/tool",
                "platform": "github",
                "category": "migration",
            }
        ],
    }

    with (
        patch(
            "ideago.pipeline.extractor.load_prompt",
            return_value="extractor-prompt",
        ),
        patch(
            "ideago.pipeline.extractor.invoke_json_with_optional_meta",
            new=AsyncMock(return_value=(payload, {"llm_calls": 1})),
        ),
    ):
        competitors = await extractor.extract(raw_results, MOCK_INTENT)
        structured = extractor.pop_structured_output_for_current_task()

    assert len(competitors) == 1
    assert competitors[0].name == "Tool X"
    assert isinstance(structured, ExtractionOutput)
    assert len(structured.pain_signals) == 1
    assert len(structured.commercial_signals) == 1
    assert len(structured.migration_signals) == 1
    assert structured.evidence_items[0].category == EvidenceCategory.MIGRATION


@pytest.mark.asyncio
async def test_langgraph_engine_extraction_boundary_exposes_typed_rich_output(
    tmp_path,
) -> None:
    class BoundaryAwareExtractor(Extractor):
        def __init__(self) -> None:
            super().__init__(llm=MagicMock())
            self.boundary_output = ExtractionOutput()

        async def extract_structured(
            self,
            raw_results: list[RawResult],
            intent: Intent,
        ) -> ExtractionOutput:
            structured = await super().extract_structured(raw_results, intent)
            self.boundary_output = structured
            return structured

    extractor = BoundaryAwareExtractor()
    payload = {
        "competitors": [
            {
                "name": "Markdown Clipper Pro",
                "links": ["https://github.com/user/markdown-clipper"],
                "one_liner": "Capture and organize notes quickly",
                "features": ["clipper", "sync"],
                "pricing": "Freemium",
                "strengths": ["Fast setup"],
                "weaknesses": ["Limited templates"],
                "relevance_score": 0.84,
                "source_platforms": ["github"],
                "source_urls": ["https://github.com/user/markdown-clipper"],
            }
        ],
        "pain_signals": [
            {
                "theme": "Slow setup",
                "summary": "Users report onboarding friction.",
                "intensity": 0.81,
                "frequency": 0.72,
                "evidence_urls": ["https://github.com/user/markdown-clipper"],
                "source_platforms": ["github"],
            }
        ],
        "commercial_signals": [
            {
                "theme": "Paid upgrade intent",
                "summary": "Users compare paid tiers.",
                "intent_strength": 0.7,
                "monetization_hint": "Team plan",
                "evidence_urls": ["https://github.com/user/markdown-clipper"],
                "source_platforms": ["github"],
            }
        ],
        "migration_signals": [
            {
                "title": "Switching from incumbent",
                "url": "https://github.com/user/markdown-clipper",
                "platform": "github",
                "snippet": "Users are actively evaluating alternatives.",
                "category": "migration",
                "query_family": "migration_discovery",
            }
        ],
        "evidence_items": [
            {
                "title": "Commercial discussion",
                "url": "https://github.com/user/markdown-clipper",
                "platform": "github",
                "snippet": "Users discuss budget for premium features.",
                "category": "commercial",
                "query_family": "commercial_discovery",
            }
        ],
    }

    with (
        patch("ideago.pipeline.extractor.load_prompt", return_value="extractor-prompt"),
        patch(
            "ideago.pipeline.extractor.invoke_json_with_optional_meta",
            new=AsyncMock(return_value=(payload, {"llm_calls": 1})),
        ),
    ):
        engine, _, _, _ = _build_engine(
            tmp_path,
            sources=[MockSource(Platform.GITHUB)],
            extractor_override=extractor,
        )
        await engine.run("test idea")

    structured = extractor.boundary_output
    assert isinstance(structured, ExtractionOutput)
    assert len(structured.competitors) == 1
    assert len(structured.pain_signals) == 1
    assert len(structured.commercial_signals) == 1
    assert len(structured.migration_signals) == 1
    assert len(structured.evidence_items) == 1
    assert structured.pain_signals[0].theme == "Slow setup"
    assert structured.commercial_signals[0].intent_strength == pytest.approx(0.7)
    assert structured.migration_signals[0].category == EvidenceCategory.MIGRATION
    assert structured.evidence_items[0].category == EvidenceCategory.COMMERCIAL


@pytest.mark.asyncio
async def test_langgraph_engine_extraction_boundary_drops_signals_without_verified_evidence(
    tmp_path,
) -> None:
    class BoundaryAwareExtractor(Extractor):
        def __init__(self) -> None:
            super().__init__(llm=MagicMock())
            self.boundary_output = ExtractionOutput()

        async def extract_structured(
            self,
            raw_results: list[RawResult],
            intent: Intent,
        ) -> ExtractionOutput:
            structured = await super().extract_structured(raw_results, intent)
            self.boundary_output = structured
            return structured

    extractor = BoundaryAwareExtractor()
    payload = {
        "competitors": [
            {
                "name": "Markdown Clipper Pro",
                "links": ["https://github.com/user/markdown-clipper"],
                "one_liner": "Capture and organize notes quickly",
                "features": ["clipper", "sync"],
                "pricing": "Freemium",
                "strengths": ["Fast setup"],
                "weaknesses": ["Limited templates"],
                "relevance_score": 0.84,
                "source_platforms": ["github"],
                "source_urls": ["https://github.com/user/markdown-clipper"],
            }
        ],
        "pain_signals": [
            {
                "theme": "Fabricated pain",
                "evidence_urls": ["https://fabricated.invalid/pain"],
            }
        ],
        "commercial_signals": [
            {
                "theme": "Fabricated commercial intent",
                "evidence_urls": ["https://fabricated.invalid/commercial"],
            }
        ],
        "migration_signals": [
            {
                "title": "Fabricated migration",
                "url": "https://fabricated.invalid/migration",
                "platform": "github",
                "category": "migration",
            }
        ],
        "evidence_items": [
            {
                "title": "Fabricated evidence",
                "url": "https://fabricated.invalid/evidence",
                "platform": "github",
                "category": "pain",
            }
        ],
    }

    with (
        patch("ideago.pipeline.extractor.load_prompt", return_value="extractor-prompt"),
        patch(
            "ideago.pipeline.extractor.invoke_json_with_optional_meta",
            new=AsyncMock(return_value=(payload, {"llm_calls": 1})),
        ),
    ):
        engine, _, _, _ = _build_engine(
            tmp_path,
            sources=[MockSource(Platform.GITHUB)],
            extractor_override=extractor,
        )
        await engine.run("test idea")

    structured = extractor.boundary_output
    assert isinstance(structured, ExtractionOutput)
    assert len(structured.competitors) == 1
    assert structured.pain_signals == []
    assert structured.commercial_signals == []
    assert structured.migration_signals == []
    assert structured.evidence_items == []


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
    extractor_override: object | None = None,
    aggregator_override: object | None = None,
    planner_override: object | None = None,
) -> tuple[LangGraphEngine, EventCollector, IntentParser, Aggregator]:
    intent_parser = MagicMock(spec=IntentParser)
    intent_parser.parse = AsyncMock(return_value=intent_override or MOCK_INTENT)
    if planner_override is not None:
        query_planner = planner_override
    else:
        query_planner = MagicMock(spec=QueryPlanner)
        query_planner.plan = AsyncMock(return_value=QueryPlan())

    if extractor_override is not None:
        extractor = extractor_override
        if extraction_fails:
            extractor.extract = AsyncMock(side_effect=ExtractionError("LLM failed"))
            extractor.extract_structured = AsyncMock(
                side_effect=ExtractionError("LLM failed")
            )
    else:
        extractor = MagicMock(spec=Extractor)
        if extraction_fails:
            extractor.extract = AsyncMock(side_effect=ExtractionError("LLM failed"))
            extractor.extract_structured = AsyncMock(
                side_effect=ExtractionError("LLM failed")
            )
        else:
            extractor.extract = AsyncMock(return_value=[MOCK_COMPETITOR])
            extractor.extract_structured = AsyncMock(
                return_value=ExtractionOutput(competitors=[MOCK_COMPETITOR])
            )

    if aggregator_override is not None:
        aggregator = aggregator_override
    else:
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
        query_planner=query_planner,
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
async def test_langgraph_engine_runs_independent_query_planner_before_fetch(
    tmp_path,
) -> None:
    source = CapturingSource(Platform.TAVILY)
    planner = MagicMock(spec=QueryPlanner)
    planner.plan = AsyncMock(
        return_value=QueryPlan(
            query_groups=[
                QueryGroup(
                    family=QueryFamily.DIRECT_COMPETITOR,
                    anchor_terms=["Claude Code"],
                    comparison_anchors=["Cursor"],
                    rewritten_queries=[
                        QueryRewrite(
                            query='"Claude Code" gui',
                            family=QueryFamily.DIRECT_COMPETITOR,
                            purpose="Find direct GUI wrappers for Claude Code.",
                        )
                    ],
                )
            ]
        )
    )
    intent_override = Intent(
        keywords_en=["visual editor"],
        app_type="web",
        target_scenario="为 Claude Code 提供可视化界面",
        output_language="zh",
        exact_entities=["Claude Code"],
        comparison_anchors=["Cursor"],
        cache_key="planner-test",
    )
    engine, _, _, _ = _build_engine(
        tmp_path,
        sources=[source],
        intent_override=intent_override,
        planner_override=planner,
    )

    await engine.run("我想开发一个 Claude Code 的可视化编辑器")

    planner.plan.assert_awaited_once()
    assert any("claude code" in query.lower() for query in source.last_queries)


@pytest.mark.asyncio
async def test_langgraph_engine_retrieval_observability_includes_query_plan_coverage(
    tmp_path,
) -> None:
    source = CapturingSource(Platform.TAVILY)
    planner = MagicMock(spec=QueryPlanner)
    planner.plan = AsyncMock(
        return_value=QueryPlan(
            query_groups=[
                QueryGroup(
                    family=QueryFamily.DIRECT_COMPETITOR,
                    anchor_terms=["Claude Code"],
                    comparison_anchors=["Cursor"],
                    rewritten_queries=[
                        QueryRewrite(
                            query='"Claude Code" gui',
                            family=QueryFamily.DIRECT_COMPETITOR,
                            purpose="Find GUI wrappers.",
                        )
                    ],
                ),
                QueryGroup(
                    family=QueryFamily.ADJACENT_ANALOGY,
                    anchor_terms=["Claude Code"],
                    comparison_anchors=["Cursor"],
                    rewritten_queries=[
                        QueryRewrite(
                            query="cursor for claude code",
                            family=QueryFamily.ADJACENT_ANALOGY,
                            purpose="Find analogous products.",
                        )
                    ],
                ),
            ]
        )
    )
    intent_override = Intent(
        keywords_en=["visual editor"],
        app_type="web",
        target_scenario="为 Claude Code 提供可视化界面",
        output_language="zh",
        exact_entities=["Claude Code"],
        comparison_anchors=["Cursor"],
        cache_key="planner-observability",
    )
    engine, _, _, _ = _build_engine(
        tmp_path,
        sources=[source],
        intent_override=intent_override,
        planner_override=planner,
    )

    with patch.object(pipeline_nodes.logger, "info") as info_log:
        await engine.run("我想开发一个 Claude Code 的可视化编辑器")

    observability_calls = [
        call.args
        for call in info_log.call_args_list
        if call.args and call.args[0] == "observability_event={} payload={}"
    ]
    retrieval_payload = next(
        (
            args[2]
            for args in observability_calls
            if len(args) >= 3 and args[1] == "retrieval_orchestration_summary"
        ),
        None,
    )
    assert isinstance(retrieval_payload, dict)
    assert retrieval_payload["planner_family_coverage"] == {
        "direct_competitor": 1,
        "adjacent_analogy": 1,
    }
    assert retrieval_payload["planner_anchor_coverage"] == {
        "exact_entities": ["Claude Code"],
        "comparison_anchors": ["Cursor"],
    }


@pytest.mark.asyncio
async def test_langgraph_engine_passes_typed_extraction_carriers_to_aggregator(
    tmp_path,
) -> None:
    source_url = MOCK_RAW_RESULTS[0].url

    class StructuredExtractor:
        async def extract_structured(
            self,
            raw_results: list[RawResult],
            intent: Intent,
        ) -> ExtractionOutput:
            return ExtractionOutput(
                competitors=[MOCK_COMPETITOR],
                pain_signals=[
                    PainSignal(
                        theme="Slow onboarding",
                        summary="Users report setup friction.",
                        intensity=0.8,
                        frequency=0.7,
                        evidence_urls=[source_url],
                        source_platforms=[Platform.GITHUB],
                    )
                ],
                commercial_signals=[
                    CommercialSignal(
                        theme="Paid intent",
                        summary="Users compare paid tiers.",
                        intent_strength=0.72,
                        evidence_urls=[source_url],
                        source_platforms=[Platform.GITHUB],
                    )
                ],
                migration_signals=[
                    EvidenceItem(
                        title="Migration signal",
                        url=source_url,
                        platform=Platform.GITHUB,
                        category=EvidenceCategory.MIGRATION,
                        query_family="migration_discovery",
                    )
                ],
                evidence_items=[
                    EvidenceItem(
                        title="Pain evidence",
                        url=source_url,
                        platform=Platform.GITHUB,
                        category=EvidenceCategory.PAIN,
                        query_family="pain_discovery",
                    )
                ],
            )

        async def extract(
            self,
            raw_results: list[RawResult],
            intent: Intent,
        ) -> list[Competitor]:
            raise AssertionError("extract() should not be used when typed path exists")

        def pop_llm_metrics_for_current_task(self) -> dict[str, Any]:
            return {}

    class CapturingAggregator:
        def __init__(self) -> None:
            self.last_kwargs: dict[str, Any] = {}

        async def analyze(
            self,
            competitors: list[Competitor],
            original_query: str,
            output_language: str = "en",
            *,
            pain_signals: list[PainSignal] | None = None,
            commercial_signals: list[CommercialSignal] | None = None,
            evidence_items: list[EvidenceItem] | None = None,
        ) -> AggregationResult:
            self.last_kwargs = {
                "pain_signals": list(pain_signals or []),
                "commercial_signals": list(commercial_signals or []),
                "evidence_items": list(evidence_items or []),
            }
            return AggregationResult(
                competitors=competitors,
                market_summary="Signals consumed.",
                go_no_go="Proceed with focused wedge.",
                whitespace_opportunities=[
                    WhitespaceOpportunity(
                        title="Onboarding wedge",
                        wedge="One-click setup",
                        potential_score=0.74,
                    )
                ],
                opportunity_score=OpportunityScoreBreakdown(score=0.69),
            )

        async def aggregate(
            self,
            competitors: list[Competitor],
            original_query: str,
            output_language: str = "en",
            *,
            pain_signals: list[PainSignal] | None = None,
            commercial_signals: list[CommercialSignal] | None = None,
            evidence_items: list[EvidenceItem] | None = None,
        ) -> AggregationResult:
            return await self.analyze(
                competitors,
                original_query,
                output_language=output_language,
                pain_signals=pain_signals,
                commercial_signals=commercial_signals,
                evidence_items=evidence_items,
            )

        def pop_llm_metrics_for_current_task(self) -> dict[str, Any]:
            return {}

    aggregator = CapturingAggregator()
    engine, _, _, _ = _build_engine(
        tmp_path,
        sources=[MockSource(Platform.GITHUB)],
        extractor_override=StructuredExtractor(),
        aggregator_override=aggregator,
    )
    report = await engine.run("test idea")

    assert report.whitespace_opportunities
    assert report.opportunity_score.score == pytest.approx(0.69)
    assert len(aggregator.last_kwargs["pain_signals"]) == 1
    assert len(aggregator.last_kwargs["commercial_signals"]) == 1
    assert len(aggregator.last_kwargs["evidence_items"]) == 2
    assert any(
        item.category == EvidenceCategory.MIGRATION
        for item in aggregator.last_kwargs["evidence_items"]
    )


@pytest.mark.asyncio
async def test_langgraph_engine_assembles_v2_decision_first_report_fields(
    tmp_path,
) -> None:
    source_url = MOCK_RAW_RESULTS[0].url

    class StructuredExtractor:
        async def extract_structured(
            self,
            raw_results: list[RawResult],
            intent: Intent,
        ) -> ExtractionOutput:
            return ExtractionOutput(
                competitors=[MOCK_COMPETITOR],
                pain_signals=[
                    PainSignal(
                        theme="Slow onboarding",
                        summary="Users hit setup friction.",
                        intensity=0.82,
                        frequency=0.73,
                        evidence_urls=[source_url],
                        source_platforms=[Platform.GITHUB],
                    )
                ],
                commercial_signals=[
                    CommercialSignal(
                        theme="Willingness to pay",
                        summary="Teams compare paid features.",
                        intent_strength=0.75,
                        evidence_urls=[source_url],
                        source_platforms=[Platform.GITHUB],
                    )
                ],
                evidence_items=[
                    EvidenceItem(
                        title="Setup thread",
                        url=source_url,
                        platform=Platform.GITHUB,
                        category=EvidenceCategory.PAIN,
                        query_family="pain_discovery",
                    )
                ],
            )

        async def extract(
            self,
            raw_results: list[RawResult],
            intent: Intent,
        ) -> list[Competitor]:
            return [MOCK_COMPETITOR]

        def pop_llm_metrics_for_current_task(self) -> dict[str, Any]:
            return {}

    class DecisionFirstAggregator:
        async def analyze(
            self,
            competitors: list[Competitor],
            original_query: str,
            output_language: str = "en",
            *,
            pain_signals: list[PainSignal] | None = None,
            commercial_signals: list[CommercialSignal] | None = None,
            evidence_items: list[EvidenceItem] | None = None,
        ) -> AggregationResult:
            return AggregationResult(
                competitors=competitors,
                market_summary="Demand is real with a clear wedge.",
                go_no_go="Go with a constrained first segment.",
                recommendation_type=RecommendationType.GO,
                differentiation_angles=["Fast onboarding", "Team rollout templates"],
                pain_signals=list(pain_signals or []),
                commercial_signals=list(commercial_signals or []),
                whitespace_opportunities=[
                    WhitespaceOpportunity(
                        title="SMB rollout wedge",
                        wedge="Guided 3-minute onboarding",
                        potential_score=0.78,
                    )
                ],
                opportunity_score=OpportunityScoreBreakdown(
                    pain_intensity=0.8,
                    solution_gap=0.74,
                    commercial_intent=0.76,
                    freshness=0.63,
                    competition_density=0.45,
                    score=0.74,
                ),
                evidence_items=list(evidence_items or []),
                uncertainty_notes=["Evidence is concentrated in technical teams."],
            )

        async def aggregate(
            self,
            competitors: list[Competitor],
            original_query: str,
            output_language: str = "en",
            *,
            pain_signals: list[PainSignal] | None = None,
            commercial_signals: list[CommercialSignal] | None = None,
            evidence_items: list[EvidenceItem] | None = None,
        ) -> AggregationResult:
            return await self.analyze(
                competitors,
                original_query,
                output_language=output_language,
                pain_signals=pain_signals,
                commercial_signals=commercial_signals,
                evidence_items=evidence_items,
            )

        def pop_llm_metrics_for_current_task(self) -> dict[str, Any]:
            return {}

    engine, _, _, _ = _build_engine(
        tmp_path,
        sources=[MockSource(Platform.GITHUB)],
        extractor_override=StructuredExtractor(),
        aggregator_override=DecisionFirstAggregator(),
    )
    report = await engine.run("test idea")

    assert report.pain_signals
    assert report.commercial_signals
    assert report.whitespace_opportunities
    assert report.opportunity_score.score == pytest.approx(0.74)
    assert report.whitespace_opportunities[0].wedge == "Guided 3-minute onboarding"
    assert report.evidence_summary.evidence_items
    assert report.evidence_summary.category_counts.get("pain") == 1
    assert report.evidence_summary.uncertainty_notes == [
        "Evidence is concentrated in technical teams."
    ]


@pytest.mark.asyncio
async def test_langgraph_engine_report_boundary_falls_back_to_state_when_aggregator_omits_v2_echoes(
    tmp_path,
) -> None:
    source_url = MOCK_RAW_RESULTS[0].url

    class StructuredExtractor:
        async def extract_structured(
            self,
            raw_results: list[RawResult],
            intent: Intent,
        ) -> ExtractionOutput:
            return ExtractionOutput(
                competitors=[MOCK_COMPETITOR],
                pain_signals=[
                    PainSignal(
                        theme="Setup friction",
                        summary="Users struggle in first-run setup.",
                        intensity=0.79,
                        frequency=0.71,
                        evidence_urls=[source_url],
                        source_platforms=[Platform.GITHUB],
                    )
                ],
                commercial_signals=[
                    CommercialSignal(
                        theme="Team plan demand",
                        summary="Buyers compare paid team tiers.",
                        intent_strength=0.74,
                        evidence_urls=[source_url],
                        source_platforms=[Platform.GITHUB],
                    )
                ],
                evidence_items=[
                    EvidenceItem(
                        title="Pain evidence",
                        url=source_url,
                        platform=Platform.GITHUB,
                        category=EvidenceCategory.PAIN,
                        query_family="pain_discovery",
                    )
                ],
                migration_signals=[
                    EvidenceItem(
                        title="Migration evidence",
                        url=source_url,
                        platform=Platform.GITHUB,
                        category=EvidenceCategory.MIGRATION,
                        query_family="migration_discovery",
                    )
                ],
            )

        async def extract(
            self,
            raw_results: list[RawResult],
            intent: Intent,
        ) -> list[Competitor]:
            return [MOCK_COMPETITOR]

        def pop_llm_metrics_for_current_task(self) -> dict[str, Any]:
            return {}

    class LegacyLikeAggregator:
        async def analyze(
            self,
            competitors: list[Competitor],
            original_query: str,
            output_language: str = "en",
            *,
            pain_signals: list[PainSignal] | None = None,
            commercial_signals: list[CommercialSignal] | None = None,
            evidence_items: list[EvidenceItem] | None = None,
        ) -> AggregationResult:
            # Simulate a minimally upgraded aggregator that accepts typed kwargs
            # but does not echo them back in AggregationResult V2 fields.
            return AggregationResult(
                competitors=competitors,
                market_summary="Legacy-like aggregator summary.",
                go_no_go="Proceed with caution.",
                recommendation_type=RecommendationType.CAUTION,
                whitespace_opportunities=[
                    WhitespaceOpportunity(
                        title="SMB wedge",
                        wedge="Guided onboarding",
                        potential_score=0.7,
                    )
                ],
                opportunity_score=OpportunityScoreBreakdown(score=0.66),
                # NOTE: intentionally omitting pain_signals/commercial_signals/evidence_items
                uncertainty_notes=[],
            )

        async def aggregate(
            self,
            competitors: list[Competitor],
            original_query: str,
            output_language: str = "en",
            *,
            pain_signals: list[PainSignal] | None = None,
            commercial_signals: list[CommercialSignal] | None = None,
            evidence_items: list[EvidenceItem] | None = None,
        ) -> AggregationResult:
            return await self.analyze(
                competitors,
                original_query,
                output_language=output_language,
                pain_signals=pain_signals,
                commercial_signals=commercial_signals,
                evidence_items=evidence_items,
            )

        def pop_llm_metrics_for_current_task(self) -> dict[str, Any]:
            return {}

    engine, _, _, _ = _build_engine(
        tmp_path,
        sources=[MockSource(Platform.GITHUB)],
        extractor_override=StructuredExtractor(),
        aggregator_override=LegacyLikeAggregator(),
    )
    report = await engine.run("test idea")

    # Final report must still be assembled from graph-state typed carriers.
    assert len(report.pain_signals) == 1
    assert report.pain_signals[0].theme == "Setup friction"
    assert len(report.commercial_signals) == 1
    assert report.commercial_signals[0].theme == "Team plan demand"

    # Evidence summary must come from state fallback evidence items.
    assert report.evidence_summary.evidence_items
    assert report.evidence_summary.category_counts.get("pain") == 1
    assert report.evidence_summary.category_counts.get("migration") == 1
    # Uncertainty notes come from aggregator output (empty here), fallback should not invent notes.
    assert report.evidence_summary.uncertainty_notes == []


@pytest.mark.asyncio
async def test_langgraph_engine_confidence_reflects_trust_factors(
    tmp_path,
) -> None:
    fresh_iso = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    stale_iso = (datetime.now(timezone.utc) - timedelta(days=540)).isoformat()

    class PlatformSpecificSource:
        def __init__(self, platform: Platform) -> None:
            self._platform = platform

        @property
        def platform(self) -> Platform:
            return self._platform

        def is_available(self) -> bool:
            return True

        async def search(self, queries: list[str], limit: int = 10) -> list[RawResult]:
            return [
                RawResult(
                    title=f"{self.platform.value}-signal",
                    url=f"https://example.com/{self.platform.value}",
                    platform=self.platform,
                )
            ]

    class DegradedPlatformSource(PlatformSpecificSource):
        def consume_last_search_diagnostics(self) -> dict[str, Any]:
            return {
                "partial_failure": False,
                "failed_queries": [],
                "timed_out_queries": [],
                "used_public_fallback": True,
                "fallback_reason": "missing_credentials",
            }

    class SourceAwareExtractor:
        def __init__(self, *, stale: bool) -> None:
            self._stale = stale

        async def extract_structured(
            self,
            raw_results: list[RawResult],
            intent: Intent,
        ) -> ExtractionOutput:
            raw = raw_results[0]
            freshness_hint = stale_iso if self._stale else fresh_iso
            return ExtractionOutput(
                competitors=[
                    Competitor(
                        name=f"{raw.platform.value}-competitor",
                        links=[raw.url],
                        one_liner="Signal-rich competitor",
                        source_platforms=[raw.platform],
                        source_urls=[raw.url],
                        relevance_score=0.7,
                    )
                ],
                pain_signals=[
                    PainSignal(
                        theme=f"{raw.platform.value}-pain",
                        summary="Users report painful workflow friction.",
                        intensity=0.82 if not self._stale else 0.45,
                        frequency=0.76 if not self._stale else 0.35,
                        evidence_urls=[raw.url],
                        source_platforms=[raw.platform],
                    )
                ],
                commercial_signals=[
                    CommercialSignal(
                        theme=f"{raw.platform.value}-commercial",
                        summary="Buyers compare paid alternatives.",
                        intent_strength=0.79 if not self._stale else 0.4,
                        evidence_urls=[raw.url],
                        source_platforms=[raw.platform],
                    )
                ],
                evidence_items=[
                    EvidenceItem(
                        title=f"{raw.platform.value} evidence",
                        url=raw.url,
                        platform=raw.platform,
                        snippet="Users discuss why incumbents fall short.",
                        category=EvidenceCategory.PAIN,
                        freshness_hint=freshness_hint,
                        query_family="pain_discovery",
                    )
                ],
            )

        async def extract(
            self,
            raw_results: list[RawResult],
            intent: Intent,
        ) -> list[Competitor]:
            structured = await self.extract_structured(raw_results, intent)
            return structured.competitors

        def pop_llm_metrics_for_current_task(self) -> dict[str, Any]:
            return {}

    class EchoAggregator:
        def __init__(self, *, uncertainty_notes: list[str]) -> None:
            self._uncertainty_notes = uncertainty_notes

        async def analyze(
            self,
            competitors: list[Competitor],
            original_query: str,
            output_language: str = "en",
            *,
            pain_signals: list[PainSignal] | None = None,
            commercial_signals: list[CommercialSignal] | None = None,
            evidence_items: list[EvidenceItem] | None = None,
        ) -> AggregationResult:
            return AggregationResult(
                competitors=competitors,
                market_summary="Trust-sensitive aggregation.",
                go_no_go="Proceed based on observed trust signals.",
                recommendation_type=RecommendationType.CAUTION,
                differentiation_angles=["Target unresolved workflow friction"],
                pain_signals=list(pain_signals or []),
                commercial_signals=list(commercial_signals or []),
                whitespace_opportunities=[
                    WhitespaceOpportunity(
                        title="Workflow wedge",
                        wedge="Faster setup",
                        potential_score=0.7,
                        confidence=0.65,
                    )
                ],
                opportunity_score=OpportunityScoreBreakdown(score=0.64),
                evidence_items=list(evidence_items or []),
                uncertainty_notes=list(self._uncertainty_notes),
            )

        async def aggregate(
            self,
            competitors: list[Competitor],
            original_query: str,
            output_language: str = "en",
            *,
            pain_signals: list[PainSignal] | None = None,
            commercial_signals: list[CommercialSignal] | None = None,
            evidence_items: list[EvidenceItem] | None = None,
        ) -> AggregationResult:
            return await self.analyze(
                competitors,
                original_query,
                output_language=output_language,
                pain_signals=pain_signals,
                commercial_signals=commercial_signals,
                evidence_items=evidence_items,
            )

        def pop_llm_metrics_for_current_task(self) -> dict[str, Any]:
            return {}

    strong_engine, _, _, _ = _build_engine(
        tmp_path / "strong",
        sources=[
            PlatformSpecificSource(Platform.GITHUB),
            PlatformSpecificSource(Platform.REDDIT),
            PlatformSpecificSource(Platform.TAVILY),
        ],
        extractor_override=SourceAwareExtractor(stale=False),
        aggregator_override=EchoAggregator(uncertainty_notes=[]),
    )
    weak_engine, _, _, _ = _build_engine(
        tmp_path / "weak",
        sources=[
            PlatformSpecificSource(Platform.GITHUB),
            DegradedPlatformSource(Platform.REDDIT),
            FailingSource(),
        ],
        extractor_override=SourceAwareExtractor(stale=True),
        aggregator_override=EchoAggregator(
            uncertainty_notes=[
                "Conflicting evidence across sources.",
                "Sparse evidence outside a narrow early-adopter segment.",
            ]
        ),
    )

    strong_report = await strong_engine.run("test idea")
    weak_report = await weak_engine.run("test idea")

    assert strong_report.confidence.score > weak_report.confidence.score
    assert (
        strong_report.confidence.source_diversity
        > weak_report.confidence.source_diversity
    )
    assert (
        strong_report.confidence.evidence_density
        > weak_report.confidence.evidence_density
    )
    assert strong_report.confidence.recency_score > weak_report.confidence.recency_score
    assert (
        strong_report.confidence.degradation_penalty
        < weak_report.confidence.degradation_penalty
    )
    assert (
        strong_report.confidence.contradiction_penalty
        < weak_report.confidence.contradiction_penalty
    )
    assert strong_report.confidence.reasons
    assert any(
        "conflict" in reason.lower() or "degraded" in reason.lower()
        for reason in weak_report.confidence.reasons
    )


@pytest.mark.asyncio
async def test_langgraph_engine_complementary_cross_platform_signals_do_not_count_as_contradiction(
    tmp_path,
) -> None:
    class PlatformSpecificSource:
        def __init__(self, platform: Platform) -> None:
            self._platform = platform

        @property
        def platform(self) -> Platform:
            return self._platform

        def is_available(self) -> bool:
            return True

        async def search(self, queries: list[str], limit: int = 10) -> list[RawResult]:
            return [
                RawResult(
                    title=f"{self.platform.value}-signal",
                    url=f"https://example.com/{self.platform.value}",
                    platform=self.platform,
                )
            ]

    class ComplementaryExtractor:
        async def extract_structured(
            self,
            raw_results: list[RawResult],
            intent: Intent,
        ) -> ExtractionOutput:
            raw = raw_results[0]
            if raw.platform == Platform.GITHUB:
                return ExtractionOutput(
                    competitors=[MOCK_COMPETITOR],
                    pain_signals=[
                        PainSignal(
                            theme="Setup friction",
                            evidence_urls=[raw.url],
                            source_platforms=[Platform.GITHUB],
                        )
                    ],
                    evidence_items=[
                        EvidenceItem(
                            title="Pain evidence",
                            url=raw.url,
                            platform=Platform.GITHUB,
                            category=EvidenceCategory.PAIN,
                            query_family="pain_discovery",
                        )
                    ],
                )
            return ExtractionOutput(
                competitors=[MOCK_COMPETITOR],
                commercial_signals=[
                    CommercialSignal(
                        theme="Budgeted demand",
                        evidence_urls=[raw.url],
                        source_platforms=[Platform.REDDIT],
                    )
                ],
                evidence_items=[
                    EvidenceItem(
                        title="Commercial evidence",
                        url=raw.url,
                        platform=Platform.REDDIT,
                        category=EvidenceCategory.COMMERCIAL,
                        query_family="commercial_discovery",
                    )
                ],
            )

        async def extract(
            self,
            raw_results: list[RawResult],
            intent: Intent,
        ) -> list[Competitor]:
            structured = await self.extract_structured(raw_results, intent)
            return structured.competitors

        def pop_llm_metrics_for_current_task(self) -> dict[str, Any]:
            return {}

    class EchoAggregator:
        async def analyze(
            self,
            competitors: list[Competitor],
            original_query: str,
            output_language: str = "en",
            *,
            pain_signals: list[PainSignal] | None = None,
            commercial_signals: list[CommercialSignal] | None = None,
            evidence_items: list[EvidenceItem] | None = None,
        ) -> AggregationResult:
            return AggregationResult(
                competitors=competitors,
                market_summary="Complementary evidence from specialized channels.",
                go_no_go="Proceed with caution.",
                recommendation_type=RecommendationType.CAUTION,
                pain_signals=list(pain_signals or []),
                commercial_signals=list(commercial_signals or []),
                evidence_items=list(evidence_items or []),
                uncertainty_notes=[],
            )

        async def aggregate(
            self,
            competitors: list[Competitor],
            original_query: str,
            output_language: str = "en",
            *,
            pain_signals: list[PainSignal] | None = None,
            commercial_signals: list[CommercialSignal] | None = None,
            evidence_items: list[EvidenceItem] | None = None,
        ) -> AggregationResult:
            return await self.analyze(
                competitors,
                original_query,
                output_language=output_language,
                pain_signals=pain_signals,
                commercial_signals=commercial_signals,
                evidence_items=evidence_items,
            )

        def pop_llm_metrics_for_current_task(self) -> dict[str, Any]:
            return {}

    engine, _, _, _ = _build_engine(
        tmp_path,
        sources=[
            PlatformSpecificSource(Platform.GITHUB),
            PlatformSpecificSource(Platform.REDDIT),
        ],
        extractor_override=ComplementaryExtractor(),
        aggregator_override=EchoAggregator(),
    )

    report = await engine.run("test idea")

    assert report.confidence.contradiction_penalty == 0.0
    assert not any("conflict" in reason.lower() for reason in report.confidence.reasons)


@pytest.mark.asyncio
async def test_langgraph_engine_evidence_summary_surfaces_trust_fields(
    tmp_path,
) -> None:
    recent_iso = (datetime.now(timezone.utc) - timedelta(days=4)).isoformat()

    class GitHubOnlySource:
        @property
        def platform(self) -> Platform:
            return Platform.GITHUB

        def is_available(self) -> bool:
            return True

        async def search(self, queries: list[str], limit: int = 10) -> list[RawResult]:
            return [
                RawResult(
                    title="github-signal",
                    url="https://github.com/org/repo/issues/1",
                    platform=Platform.GITHUB,
                )
            ]

    class MixedTrustExtractor:
        async def extract_structured(
            self,
            raw_results: list[RawResult],
            intent: Intent,
        ) -> ExtractionOutput:
            raw = raw_results[0]
            if raw.platform != Platform.GITHUB:
                return ExtractionOutput(competitors=[MOCK_COMPETITOR])
            return ExtractionOutput(
                competitors=[MOCK_COMPETITOR],
                pain_signals=[
                    PainSignal(
                        theme="Onboarding friction",
                        evidence_urls=[raw.url],
                        source_platforms=[Platform.GITHUB],
                    )
                ],
                evidence_items=[
                    EvidenceItem(
                        title="GitHub complaint",
                        url=raw.url,
                        platform=Platform.GITHUB,
                        snippet="Setup still takes too long.",
                        category=EvidenceCategory.PAIN,
                        freshness_hint=recent_iso,
                        query_family="pain_discovery",
                    )
                ],
            )

        async def extract(
            self,
            raw_results: list[RawResult],
            intent: Intent,
        ) -> list[Competitor]:
            return [MOCK_COMPETITOR]

        def pop_llm_metrics_for_current_task(self) -> dict[str, Any]:
            return {}

    class TrustAwareAggregator:
        async def analyze(
            self,
            competitors: list[Competitor],
            original_query: str,
            output_language: str = "en",
            *,
            pain_signals: list[PainSignal] | None = None,
            commercial_signals: list[CommercialSignal] | None = None,
            evidence_items: list[EvidenceItem] | None = None,
        ) -> AggregationResult:
            return AggregationResult(
                competitors=competitors,
                market_summary="Mixed trust report.",
                go_no_go="Proceed carefully.",
                recommendation_type=RecommendationType.CAUTION,
                pain_signals=list(pain_signals or []),
                evidence_items=list(evidence_items or []),
                uncertainty_notes=["Evidence conflicts with degraded source coverage."],
            )

        async def aggregate(
            self,
            competitors: list[Competitor],
            original_query: str,
            output_language: str = "en",
            *,
            pain_signals: list[PainSignal] | None = None,
            commercial_signals: list[CommercialSignal] | None = None,
            evidence_items: list[EvidenceItem] | None = None,
        ) -> AggregationResult:
            return await self.analyze(
                competitors,
                original_query,
                output_language=output_language,
                pain_signals=pain_signals,
                commercial_signals=commercial_signals,
                evidence_items=evidence_items,
            )

        def pop_llm_metrics_for_current_task(self) -> dict[str, Any]:
            return {}

    class DegradedRedditSource(MockSource):
        @property
        def platform(self) -> Platform:
            return Platform.REDDIT

        async def search(self, queries: list[str], limit: int = 10) -> list[RawResult]:
            return [
                RawResult(
                    title="reddit-signal",
                    url="https://reddit.com/r/test/comments/1",
                    platform=Platform.REDDIT,
                )
            ]

        def consume_last_search_diagnostics(self) -> dict[str, Any]:
            return {
                "partial_failure": False,
                "failed_queries": [],
                "timed_out_queries": [],
                "used_public_fallback": True,
                "fallback_reason": "missing_credentials",
            }

    engine, _, _, _ = _build_engine(
        tmp_path,
        sources=[GitHubOnlySource(), DegradedRedditSource(Platform.REDDIT)],
        extractor_override=MixedTrustExtractor(),
        aggregator_override=TrustAwareAggregator(),
    )

    report = await engine.run("test idea")

    assert len(report.evidence_summary.evidence_items) == 1
    assert report.evidence_summary.source_platforms == [Platform.GITHUB]
    assert report.evidence_summary.freshness_distribution.get("recent") == 1
    assert report.evidence_summary.degraded_sources == [Platform.REDDIT]
    assert report.evidence_summary.category_counts.get("pain") == 1
    assert report.evidence_summary.uncertainty_notes == [
        "Evidence conflicts with degraded source coverage."
    ]


@pytest.mark.asyncio
async def test_langgraph_engine_evidence_summary_trust_fields_do_not_use_synthetic_competitor_fallback(
    tmp_path,
) -> None:
    class CompetitorOnlyExtractor:
        async def extract_structured(
            self,
            raw_results: list[RawResult],
            intent: Intent,
        ) -> ExtractionOutput:
            return ExtractionOutput(competitors=[MOCK_COMPETITOR])

        async def extract(
            self,
            raw_results: list[RawResult],
            intent: Intent,
        ) -> list[Competitor]:
            return [MOCK_COMPETITOR]

        def pop_llm_metrics_for_current_task(self) -> dict[str, Any]:
            return {}

    class MinimalAggregator:
        async def analyze(
            self,
            competitors: list[Competitor],
            original_query: str,
            output_language: str = "en",
            *,
            pain_signals: list[PainSignal] | None = None,
            commercial_signals: list[CommercialSignal] | None = None,
            evidence_items: list[EvidenceItem] | None = None,
        ) -> AggregationResult:
            return AggregationResult(
                competitors=competitors,
                market_summary="No structured evidence captured.",
                go_no_go="Proceed with caution.",
                recommendation_type=RecommendationType.CAUTION,
            )

        async def aggregate(
            self,
            competitors: list[Competitor],
            original_query: str,
            output_language: str = "en",
            *,
            pain_signals: list[PainSignal] | None = None,
            commercial_signals: list[CommercialSignal] | None = None,
            evidence_items: list[EvidenceItem] | None = None,
        ) -> AggregationResult:
            return await self.analyze(
                competitors,
                original_query,
                output_language=output_language,
                pain_signals=pain_signals,
                commercial_signals=commercial_signals,
                evidence_items=evidence_items,
            )

        def pop_llm_metrics_for_current_task(self) -> dict[str, Any]:
            return {}

    engine, _, _, _ = _build_engine(
        tmp_path,
        sources=[MockSource(Platform.GITHUB)],
        extractor_override=CompetitorOnlyExtractor(),
        aggregator_override=MinimalAggregator(),
    )

    report = await engine.run("test idea")

    assert report.evidence_summary.top_evidence
    assert report.evidence_summary.evidence_items == []
    assert report.evidence_summary.source_platforms == []
    assert report.evidence_summary.freshness_distribution == {}
    assert report.evidence_summary.category_counts == {}


@pytest.mark.asyncio
async def test_langgraph_engine_consumes_typed_extraction_output_into_graph_state(
    tmp_path,
) -> None:
    class StructuredExtractor:
        async def extract_structured(
            self,
            raw_results: list[RawResult],
            intent: Intent,
        ) -> ExtractionOutput:
            source_url = raw_results[0].url if raw_results else ""
            return ExtractionOutput(
                competitors=[MOCK_COMPETITOR],
                pain_signals=[
                    PainSignal(
                        theme="Slow onboarding",
                        summary="Users report setup friction.",
                        intensity=0.8,
                        frequency=0.7,
                        evidence_urls=[source_url],
                        source_platforms=[Platform.GITHUB],
                    )
                ],
                commercial_signals=[
                    CommercialSignal(
                        theme="Paid automation intent",
                        summary="Teams compare paid tiers.",
                        intent_strength=0.73,
                        monetization_hint="Team plan",
                        evidence_urls=[source_url],
                        source_platforms=[Platform.GITHUB],
                    )
                ],
                migration_signals=[
                    EvidenceItem(
                        title="Migration intent",
                        url=source_url,
                        platform=Platform.GITHUB,
                        category=EvidenceCategory.MIGRATION,
                        query_family="migration_discovery",
                    )
                ],
                evidence_items=[
                    EvidenceItem(
                        title="Pain thread",
                        url=source_url,
                        platform=Platform.GITHUB,
                        category=EvidenceCategory.PAIN,
                        query_family="pain_discovery",
                    )
                ],
            )

        async def extract(
            self,
            raw_results: list[RawResult],
            intent: Intent,
        ) -> list[Competitor]:
            raise AssertionError("extract() should not be used when typed path exists")

        def pop_llm_metrics_for_current_task(self) -> dict[str, Any]:
            return {}

    captured_state: dict[str, object] = {}
    original_merge_node = pipeline_nodes.PipelineNodes.merge_node

    async def merge_probe(
        self: pipeline_nodes.PipelineNodes,
        state: GraphState,
    ) -> GraphState:
        captured_state["pain"] = list(state.get("extracted_pain_signals", []))
        captured_state["commercial"] = list(
            state.get("extracted_commercial_signals", [])
        )
        captured_state["evidence"] = list(state.get("extracted_evidence_items", []))
        return await original_merge_node(self, state)

    with patch.object(pipeline_nodes.PipelineNodes, "merge_node", new=merge_probe):
        engine, _, _, _ = _build_engine(
            tmp_path,
            sources=[MockSource(Platform.GITHUB)],
            extractor_override=StructuredExtractor(),
        )
        report = await engine.run("test idea")

    assert report.competitors
    pain_signals = captured_state.get("pain")
    commercial_signals = captured_state.get("commercial")
    evidence_items = captured_state.get("evidence")
    assert isinstance(pain_signals, list) and pain_signals
    assert isinstance(commercial_signals, list) and commercial_signals
    assert isinstance(evidence_items, list) and evidence_items
    assert isinstance(pain_signals[0], PainSignal)
    assert isinstance(commercial_signals[0], CommercialSignal)
    assert any(
        isinstance(item, EvidenceItem) and item.category == EvidenceCategory.MIGRATION
        for item in evidence_items
    )
    assert any(
        isinstance(item, EvidenceItem) and item.category == EvidenceCategory.PAIN
        for item in evidence_items
    )


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
    assert report.evidence_summary.top_evidence
    assert report.evidence_summary.evidence_items == []
    assert report.evidence_summary.category_counts == {}
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
async def test_langgraph_engine_emits_retrieval_and_trust_observability(
    tmp_path,
) -> None:
    sources = [MockSource(Platform.GITHUB), FailingSource()]
    engine, _, _, _ = _build_engine(tmp_path, sources=sources)

    with patch.object(pipeline_nodes.logger, "info") as info_log:
        await engine.run("test idea")

    observability_calls = [
        call.args
        for call in info_log.call_args_list
        if call.args and call.args[0] == "observability_event={} payload={}"
    ]
    assert observability_calls

    payload_by_event = {
        call_args[1]: call_args[2]
        for call_args in observability_calls
        if len(call_args) >= 3 and isinstance(call_args[2], dict)
    }
    retrieval_payload = payload_by_event.get("retrieval_orchestration_summary")
    assert retrieval_payload is not None
    assert retrieval_payload["query_family_coverage"]
    assert "source_role_budget_usage" in retrieval_payload
    assert "github" in retrieval_payload["source_role_budget_usage"]
    assert "degraded_ratio" in retrieval_payload
    assert isinstance(retrieval_payload["degraded_ratio"], float)

    trust_payload = payload_by_event.get("report_trust_summary")
    assert trust_payload is not None
    assert "confidence_penalty_reasons" in trust_payload
    assert isinstance(trust_payload["confidence_penalty_reasons"], list)
    assert "degraded_ratio" in trust_payload
    assert isinstance(trust_payload["degraded_ratio"], float)


@pytest.mark.asyncio
async def test_langgraph_engine_retrieval_observability_uses_runtime_adaptive_queries(
    tmp_path,
) -> None:
    source = CapturingSource(Platform.TAVILY)
    engine, _, _, _ = _build_engine(tmp_path, sources=[source])

    def _adaptive_trimmed_budget(
        _self,
        *,
        platform_name: str,
        queries: list[str],
        default_source_query_concurrency: int,
    ) -> tuple[list[str], int]:
        del platform_name, default_source_query_concurrency
        return queries[:1], 1

    with (
        patch.object(
            pipeline_nodes._SourceAdaptiveController,  # noqa: SLF001
            "get_budget",
            autospec=True,
            side_effect=_adaptive_trimmed_budget,
        ),
        patch.object(pipeline_nodes.logger, "info") as info_log,
    ):
        await engine.run("test idea")

    assert len(source.last_queries) == 1
    observability_calls = [
        call.args
        for call in info_log.call_args_list
        if call.args and call.args[0] == "observability_event={} payload={}"
    ]
    retrieval_payload = next(
        (
            args[2]
            for args in observability_calls
            if len(args) >= 3 and args[1] == "retrieval_orchestration_summary"
        ),
        None,
    )
    assert isinstance(retrieval_payload, dict)

    coverage_total = sum(
        int(count) for count in retrieval_payload["query_family_coverage"].values()
    )
    assert coverage_total == 1
    tavily_usage = retrieval_payload["source_role_budget_usage"]["tavily"]
    assert tavily_usage["selected_query_count"] == 1
    assert tavily_usage["runtime_query_concurrency"] == 1


@pytest.mark.asyncio
async def test_langgraph_engine_report_trust_observability_only_emits_penalty_reasons(
    tmp_path,
) -> None:
    sources = [
        MockSource(Platform.GITHUB),
        MockSource(Platform.TAVILY),
        MockSource(Platform.HACKERNEWS),
    ]
    engine, _, _, _ = _build_engine(tmp_path, sources=sources)

    with patch.object(pipeline_nodes.logger, "info") as info_log:
        report = await engine.run("test idea")

    assert report.confidence.reasons
    assert any("Evidence spans" in reason for reason in report.confidence.reasons)

    observability_calls = [
        call.args
        for call in info_log.call_args_list
        if call.args and call.args[0] == "observability_event={} payload={}"
    ]
    trust_payload = next(
        (
            args[2]
            for args in observability_calls
            if len(args) >= 3 and args[1] == "report_trust_summary"
        ),
        None,
    )
    assert isinstance(trust_payload, dict)
    assert trust_payload["confidence_penalty_reasons"] == []


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
async def test_langgraph_engine_applies_source_role_budget_and_source_cap(
    tmp_path,
) -> None:
    tavily_source = CapturingSource(Platform.TAVILY)
    intent_override = MOCK_INTENT.model_copy(update={"app_type": "web"})
    custom_settings = Settings(
        source_query_caps='{"tavily": 4}',
        app_type_orchestration_profiles=(
            '{"web":{"role_query_budgets":{"market_scan":2},'
            '"family_trim_threshold":0.0}}'
        ),
    )
    with patch.object(pipeline_nodes, "get_settings", return_value=custom_settings):
        engine, _, _, _ = _build_engine(
            tmp_path,
            sources=[tavily_source],
            intent_override=intent_override,
        )
        await engine.run("test idea")

    assert len(tavily_source.last_queries) == 2


@pytest.mark.asyncio
async def test_langgraph_engine_trims_low_value_query_families_before_execution(
    tmp_path,
) -> None:
    tavily_source = CapturingSource(Platform.TAVILY)
    custom_settings = Settings(
        source_query_caps='{"tavily": 5}',
        query_family_default_weights=(
            '{"competitor_discovery":1.0,"alternative_discovery":0.95,'
            '"pain_discovery":0.9,"workflow_discovery":0.3,'
            '"commercial_discovery":0.2}'
        ),
        app_type_orchestration_profiles=(
            '{"web":{"role_query_budgets":{"market_scan":5},'
            '"family_trim_threshold":0.8}}'
        ),
    )

    with patch.object(pipeline_nodes, "get_settings", return_value=custom_settings):
        engine, _, _, _ = _build_engine(tmp_path, sources=[tavily_source])
        await engine.run("test idea")

    observed_families = {
        infer_query_family(query) for query in tavily_source.last_queries
    }
    assert "workflow_discovery" not in observed_families
    assert "commercial_discovery" not in observed_families
    assert "competitor_discovery" in observed_families


@pytest.mark.asyncio
async def test_langgraph_engine_orchestration_preserves_query_family_metadata(
    tmp_path,
) -> None:
    tavily_source = CapturingSource(Platform.TAVILY)
    engine, _, _, _ = _build_engine(tmp_path, sources=[tavily_source])

    await engine.run("test idea")

    assert tavily_source.last_queries
    assert all(
        isinstance(getattr(query, "query_family", None), str)
        and bool(getattr(query, "query_family", ""))
        for query in tavily_source.last_queries
    )
    assert any(
        getattr(query, "query_family", "") == "competitor_discovery"
        for query in tavily_source.last_queries
    )


def test_source_adaptive_controller_preserves_degradation_behavior() -> None:
    controller = pipeline_nodes._SourceAdaptiveController(  # noqa: SLF001
        runtime_metrics={},
        source_timeout=5,
    )
    queries = ["q1", "q2", "q3", "q4"]

    baseline_queries, baseline_concurrency = controller.get_budget(
        platform_name=Platform.GITHUB.value,
        queries=queries,
        default_source_query_concurrency=4,
    )
    assert baseline_queries == queries
    assert baseline_concurrency == 4

    controller.record(
        platform_name=Platform.GITHUB.value,
        status=SourceStatus.FAILED,
        duration_ms=5100,
    )
    controller.record(
        platform_name=Platform.GITHUB.value,
        status=SourceStatus.TIMEOUT,
        duration_ms=5300,
    )

    degraded_queries, degraded_concurrency = controller.get_budget(
        platform_name=Platform.GITHUB.value,
        queries=queries,
        default_source_query_concurrency=4,
    )
    assert len(degraded_queries) == 2
    assert degraded_concurrency == 2


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
