"""LangGraph-based pipeline engine."""

from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path
from typing import Any
from uuid import uuid4

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, StateGraph

from ideago.cache.file_cache import FileCache
from ideago.contracts.protocols import DataSource, ProgressCallback
from ideago.models.research import ResearchReport
from ideago.pipeline.aggregator import Aggregator
from ideago.pipeline.extractor import Extractor
from ideago.pipeline.graph_state import GraphState
from ideago.pipeline.intent_parser import IntentParser
from ideago.pipeline.nodes import PipelineNodes
from ideago.sources.registry import SourceRegistry


class LangGraphEngine:
    """Coordinates the full research pipeline via LangGraph."""

    def __init__(
        self,
        intent_parser: IntentParser,
        extractor: Extractor,
        aggregator: Aggregator,
        registry: SourceRegistry,
        cache: FileCache,
        checkpoint_db_path: str,
        source_timeout: int = 30,
        extraction_timeout: int = 60,
        max_results_per_source: int = 10,
        max_concurrent_llm: int = 3,
        source_global_concurrency: int = 3,
    ) -> None:
        self._intent_parser = intent_parser
        self._extractor = extractor
        self._aggregator = aggregator
        self._registry = registry
        self._cache = cache
        checkpoint_path = Path(checkpoint_db_path)
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        self._checkpoint_db_path = str(checkpoint_path)
        self._source_timeout = source_timeout
        self._extraction_timeout = extraction_timeout
        self._max_results_per_source = max_results_per_source
        self._max_concurrent_llm = max_concurrent_llm
        self._source_global_concurrency = max(1, source_global_concurrency)
        self._source_runtime_metrics: dict[str, dict[str, Any]] = {}

    def get_all_sources(self) -> list[DataSource]:
        """Return all registered source plugins."""
        return self._registry.get_all()

    def get_source_availability(self) -> dict[str, bool]:
        """Return source availability map for health checks."""
        return {
            source.platform.value: source.is_available()
            for source in self._registry.get_all()
        }

    async def run(
        self,
        query: str,
        callback: ProgressCallback | None = None,
        report_id: str | None = None,
    ) -> ResearchReport:
        """Execute graph and return the final research report."""
        nodes = PipelineNodes(
            intent_parser=self._intent_parser,
            extractor=self._extractor,
            aggregator=self._aggregator,
            registry=self._registry,
            cache=self._cache,
            callback=callback,
            source_timeout=self._source_timeout,
            extraction_timeout=self._extraction_timeout,
            max_results_per_source=self._max_results_per_source,
            max_concurrent_llm=self._max_concurrent_llm,
            source_global_concurrency=self._source_global_concurrency,
            source_runtime_metrics=self._source_runtime_metrics,
        )
        thread_id = report_id or str(uuid4())
        config = {"configurable": {"thread_id": thread_id}}
        saver_cm, saver = await self._open_checkpoint_saver()
        exc_type = None
        exc = None
        tb = None
        try:
            await saver.setup()
            graph = self._build_graph(nodes, saver)
            snapshot = await graph.aget_state(config)
            if snapshot.next:
                result_state = await graph.ainvoke(None, config=config)
            else:
                input_state: GraphState = {"query": query}
                if report_id:
                    input_state["report_id"] = report_id
                result_state = await graph.ainvoke(input_state, config=config)
        except BaseException as run_exc:  # noqa: BLE001
            exc_type = type(run_exc)
            exc = run_exc
            tb = run_exc.__traceback__
            raise
        finally:
            await asyncio.shield(saver_cm.__aexit__(exc_type, exc, tb))

        report = result_state.get("report")
        if not isinstance(report, ResearchReport):
            raise RuntimeError("Pipeline finished without report")
        return report

    async def _open_checkpoint_saver(self) -> tuple[Any, AsyncSqliteSaver]:
        """Open sqlite saver with cancellation-safe enter to avoid leaked connections."""
        saver_cm = AsyncSqliteSaver.from_conn_string(self._checkpoint_db_path)
        enter_task = asyncio.create_task(saver_cm.__aenter__())
        try:
            saver = await asyncio.shield(enter_task)
        except asyncio.CancelledError:
            with contextlib.suppress(Exception):
                await enter_task
                await asyncio.shield(saver_cm.__aexit__(None, None, None))
            raise
        return saver_cm, saver

    def _build_graph(self, nodes: PipelineNodes, saver: AsyncSqliteSaver):
        builder = StateGraph(GraphState)
        builder.add_node("parse_intent", nodes.parse_intent_node)
        builder.add_node("cache_lookup", nodes.cache_lookup_node)
        builder.add_node("fetch_sources", nodes.fetch_sources_node)
        builder.add_node("extract_map", nodes.extract_map_node)
        builder.add_node("aggregate", nodes.aggregate_node)
        builder.add_node("assemble_report", nodes.assemble_report_node)
        builder.add_node("persist_report", nodes.persist_report_node)
        builder.add_node("terminal_error", nodes.terminal_error_node)

        builder.set_entry_point("parse_intent")
        builder.add_edge("parse_intent", "cache_lookup")
        builder.add_conditional_edges(
            "cache_lookup",
            self._route_after_cache,
            {
                "cached": END,
                "fetch": "fetch_sources",
            },
        )
        builder.add_edge("fetch_sources", "extract_map")
        builder.add_edge("extract_map", "aggregate")
        builder.add_conditional_edges(
            "aggregate",
            self._route_after_aggregate,
            {
                "ok": "assemble_report",
                "error": "terminal_error",
            },
        )
        builder.add_edge("assemble_report", "persist_report")
        builder.add_edge("persist_report", END)
        builder.add_edge("terminal_error", END)
        return builder.compile(checkpointer=saver, name="ideago_pipeline")

    @staticmethod
    def _route_after_cache(state: GraphState) -> str:
        return "cached" if state.get("is_cache_hit") else "fetch"

    @staticmethod
    def _route_after_aggregate(state: GraphState) -> str:
        return "error" if state.get("error_code") else "ok"
