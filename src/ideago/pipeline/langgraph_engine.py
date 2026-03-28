"""LangGraph-based pipeline engine.

Supports PostgreSQL checkpointer (via Supabase DB) for production and
falls back to SQLite for local dev when no DB URL is configured.
"""

from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path
from typing import Any
from uuid import uuid4

from langgraph.graph import END, StateGraph

from ideago.cache.base import ReportRepository
from ideago.contracts.protocols import DataSource, ProgressCallback
from ideago.models.research import ResearchReport
from ideago.observability.log_config import get_logger
from ideago.pipeline.aggregator import Aggregator
from ideago.pipeline.extractor import Extractor
from ideago.pipeline.graph_state import GraphState
from ideago.pipeline.intent_parser import IntentParser
from ideago.pipeline.nodes import PipelineNodes
from ideago.pipeline.query_planning import QueryPlanner
from ideago.sources.registry import SourceRegistry

logger = get_logger(__name__)


class LangGraphEngine:
    """Coordinates the full research pipeline via LangGraph.

    When *checkpoint_db_url* (a PostgreSQL connection string) is provided the
    engine uses ``AsyncPostgresSaver`` for durable, multi-worker-safe
    checkpointing.  Otherwise it falls back to ``AsyncSqliteSaver`` using a
    local file at *checkpoint_db_path*.
    """

    def __init__(
        self,
        intent_parser: IntentParser,
        query_planner: QueryPlanner,
        extractor: Extractor,
        aggregator: Aggregator,
        registry: SourceRegistry,
        cache: ReportRepository,
        checkpoint_db_path: str,
        source_timeout: int = 30,
        extraction_timeout: int = 60,
        max_results_per_source: int = 20,
        extractor_max_results_per_source: int = 15,
        max_concurrent_llm: int = 3,
        source_global_concurrency: int = 3,
        checkpoint_db_url: str = "",
    ) -> None:
        self._intent_parser = intent_parser
        self._query_planner = query_planner
        self._extractor = extractor
        self._aggregator = aggregator
        self._registry = registry
        self._cache = cache

        self._checkpoint_db_url = checkpoint_db_url.strip()
        checkpoint_path = Path(checkpoint_db_path)
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        self._checkpoint_db_path = str(checkpoint_path)

        self._source_timeout = source_timeout
        self._extraction_timeout = extraction_timeout
        self._max_results_per_source = max_results_per_source
        self._extractor_max_results_per_source = extractor_max_results_per_source
        self._max_concurrent_llm = max_concurrent_llm
        self._source_global_concurrency = max(1, source_global_concurrency)

        if self._checkpoint_db_url:
            logger.info("Checkpoint backend: PostgreSQL")
        else:
            logger.info("Checkpoint backend: SQLite ({})", self._checkpoint_db_path)

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
        user_id: str = "",
    ) -> ResearchReport:
        """Execute graph and return the final research report."""
        per_run_metrics: dict[str, dict[str, Any]] = {}
        nodes = PipelineNodes(
            intent_parser=self._intent_parser,
            query_planner=self._query_planner,
            extractor=self._extractor,
            aggregator=self._aggregator,
            registry=self._registry,
            cache=self._cache,
            callback=callback,
            source_timeout=self._source_timeout,
            extraction_timeout=self._extraction_timeout,
            max_results_per_source=self._max_results_per_source,
            extractor_max_results_per_source=self._extractor_max_results_per_source,
            max_concurrent_llm=self._max_concurrent_llm,
            source_global_concurrency=self._source_global_concurrency,
            source_runtime_metrics=per_run_metrics,
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
                if user_id:
                    input_state["user_id"] = user_id
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

    async def _open_checkpoint_saver(self) -> tuple[Any, Any]:
        """Open the appropriate checkpoint saver.

        PostgreSQL when *checkpoint_db_url* is configured, SQLite otherwise.
        Both are opened as async context managers with cancellation safety.
        """
        if self._checkpoint_db_url:
            return await self._open_postgres_saver()
        return await self._open_sqlite_saver()

    async def _open_postgres_saver(self) -> tuple[Any, Any]:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        saver_cm = AsyncPostgresSaver.from_conn_string(self._checkpoint_db_url)
        enter_task = asyncio.create_task(saver_cm.__aenter__())
        try:
            saver = await asyncio.shield(enter_task)
        except asyncio.CancelledError:
            with contextlib.suppress(Exception):
                await enter_task
                await asyncio.shield(saver_cm.__aexit__(None, None, None))
            raise
        return saver_cm, saver

    async def _open_sqlite_saver(self) -> tuple[Any, Any]:
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

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

    def _build_graph(self, nodes: PipelineNodes, saver: Any):
        builder = StateGraph(GraphState)
        builder.add_node("parse_intent", nodes.parse_intent_node)
        builder.add_node("cache_lookup", nodes.cache_lookup_node)
        builder.add_node("plan_queries", nodes.plan_queries_node)
        builder.add_node("fetch_sources", nodes.fetch_sources_node)
        builder.add_node("pre_filter", nodes.pre_filter_node)
        builder.add_node("extract_map", nodes.extract_map_node)
        builder.add_node("merge", nodes.merge_node)
        builder.add_node("analyze", nodes.analyze_node)
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
                "fetch": "plan_queries",
            },
        )
        builder.add_edge("plan_queries", "fetch_sources")
        builder.add_edge("fetch_sources", "pre_filter")
        builder.add_edge("pre_filter", "extract_map")
        builder.add_edge("extract_map", "merge")
        builder.add_edge("merge", "analyze")
        builder.add_conditional_edges(
            "analyze",
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
