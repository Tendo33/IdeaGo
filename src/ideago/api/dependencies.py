"""Shared FastAPI dependencies — singleton services wired from config.

FastAPI 依赖注入：从配置构建单例服务实例。
"""

from __future__ import annotations

import asyncio
import contextlib
import threading
import time

from ideago.cache.base import ReportRepository
from ideago.config.settings import get_settings
from ideago.llm.chat_model import ChatModelClient
from ideago.pipeline.aggregator import Aggregator
from ideago.pipeline.events import EventType, PipelineEvent
from ideago.pipeline.extractor import Extractor
from ideago.pipeline.intent_parser import IntentParser
from ideago.pipeline.langgraph_engine import LangGraphEngine
from ideago.sources.appstore_source import AppStoreSource
from ideago.sources.github_source import GitHubSource
from ideago.sources.hackernews_source import HackerNewsSource
from ideago.sources.producthunt_source import ProductHuntSource
from ideago.sources.reddit_source import RedditSource
from ideago.sources.registry import SourceRegistry
from ideago.sources.tavily_source import TavilySource

_orchestrator: LangGraphEngine | None = None
_cache: ReportRepository | None = None
_report_runs: dict[str, ReportRunState] = {}
_processing_reports: dict[str, str] = {}
_pipeline_tasks: dict[str, asyncio.Task[None]] = {}
_runtime_state_lock = threading.RLock()
_REPORT_RUN_TTL_SECONDS = 600
_TERMINAL_EVENTS = {EventType.REPORT_READY, EventType.ERROR, EventType.CANCELLED}


class ReportRunState:
    """In-memory runtime state for one report pipeline run."""

    def __init__(self, max_history: int = 200) -> None:
        self.subscribers: set[asyncio.Queue[PipelineEvent]] = set()
        self.history: list[PipelineEvent] = []
        self.is_terminal = False
        self.updated_at = time.monotonic()
        self._max_history = max_history

    async def publish(self, event: PipelineEvent) -> None:
        """Store and fan out an event to all active SSE subscribers."""
        self.history.append(event)
        if len(self.history) > self._max_history:
            self.history.pop(0)
        self.updated_at = time.monotonic()
        if event.type in _TERMINAL_EVENTS:
            self.is_terminal = True

        for queue in list(self.subscribers):
            await queue.put(event)

    def subscribe(self) -> asyncio.Queue[PipelineEvent]:
        """Create and register an SSE subscriber queue."""
        queue: asyncio.Queue[PipelineEvent] = asyncio.Queue()
        self.subscribers.add(queue)
        self.updated_at = time.monotonic()
        return queue

    def unsubscribe(self, queue: asyncio.Queue[PipelineEvent]) -> None:
        """Detach an SSE subscriber queue."""
        self.subscribers.discard(queue)
        self.updated_at = time.monotonic()

    def history_snapshot(self) -> list[PipelineEvent]:
        return list(self.history)


def get_cache() -> ReportRepository:
    global _cache
    if _cache is None:
        settings = get_settings()
        if settings.supabase_url and settings.supabase_service_role_key:
            from ideago.cache.supabase_cache import SupabaseReportRepository

            _cache = SupabaseReportRepository(ttl_hours=settings.cache_ttl_hours)
        else:
            from ideago.cache.file_cache import FileCache

            _cache = FileCache(settings.cache_dir, settings.cache_ttl_hours)
    return _cache


def get_orchestrator() -> LangGraphEngine:
    global _orchestrator
    if _orchestrator is None:
        settings = get_settings()
        llm = ChatModelClient(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            base_url=settings.openai_base_url,
            timeout=settings.openai_timeout_seconds,
            max_retries=settings.langgraph_max_retries,
            json_parse_max_retries=settings.langgraph_json_parse_max_retries,
            fallback_endpoints=settings.get_openai_fallback_endpoints(),
        )
        registry = SourceRegistry()
        registry.register(
            GitHubSource(
                token=settings.github_token,
                timeout=settings.source_timeout_seconds,
                max_concurrent_queries=settings.source_query_concurrency,
            )
        )
        registry.register(
            TavilySource(
                api_key=settings.tavily_api_key,
                base_url=settings.tavily_base_url,
                timeout=settings.source_timeout_seconds,
                max_concurrent_queries=settings.source_query_concurrency,
            )
        )
        registry.register(
            HackerNewsSource(
                timeout=settings.source_timeout_seconds,
                max_concurrent_queries=settings.source_query_concurrency,
            )
        )
        registry.register(
            AppStoreSource(
                timeout=settings.source_timeout_seconds,
                max_concurrent_queries=settings.source_query_concurrency,
                country=settings.appstore_country,
            )
        )
        registry.register(
            ProductHuntSource(
                dev_token=settings.producthunt_dev_token,
                posted_after_days=settings.producthunt_posted_after_days,
                timeout=settings.source_timeout_seconds,
                max_concurrent_queries=settings.source_query_concurrency,
            )
        )
        registry.register(
            RedditSource(
                client_id=settings.reddit_client_id,
                client_secret=settings.reddit_client_secret,
                timeout=settings.source_timeout_seconds,
                max_concurrent_queries=settings.source_query_concurrency,
            )
        )

        _orchestrator = LangGraphEngine(
            intent_parser=IntentParser(llm),
            extractor=Extractor(llm),
            aggregator=Aggregator(llm),
            registry=registry,
            cache=get_cache(),
            checkpoint_db_path=settings.langgraph_checkpoint_db_path,
            source_timeout=settings.source_timeout_seconds,
            extraction_timeout=settings.extraction_timeout_seconds,
            max_results_per_source=settings.max_results_per_source,
            source_global_concurrency=settings.source_global_concurrency,
        )
    return _orchestrator


def cleanup_report_runs() -> None:
    """Drop finished report run states after TTL to avoid memory growth."""
    now = time.monotonic()
    stale_ids = [
        report_id
        for report_id, run in _report_runs.items()
        if run.is_terminal
        and not run.subscribers
        and now - run.updated_at > _REPORT_RUN_TTL_SECONDS
    ]
    for report_id in stale_ids:
        _report_runs.pop(report_id, None)


def get_or_create_report_run(report_id: str) -> ReportRunState:
    """Get or create runtime event state for a report."""
    cleanup_report_runs()
    run = _report_runs.get(report_id)
    if run is None:
        run = ReportRunState()
        _report_runs[report_id] = run
    return run


def get_report_run(report_id: str) -> ReportRunState | None:
    """Get runtime event state for a report if present."""
    cleanup_report_runs()
    return _report_runs.get(report_id)


async def reserve_processing_report(query_hash: str, report_id: str) -> str | None:
    """Atomically reserve processing slot; return existing active report_id if present."""
    with _runtime_state_lock:
        existing_report_id = _processing_reports.get(query_hash)
        if existing_report_id is not None:
            return existing_report_id
        _processing_reports[query_hash] = report_id
        return None


async def register_pipeline_task(report_id: str, task: asyncio.Task[None]) -> None:
    """Atomically register pipeline task."""
    with _runtime_state_lock:
        _pipeline_tasks[report_id] = task


async def remove_pipeline_task(report_id: str) -> asyncio.Task[None] | None:
    """Atomically remove pipeline task."""
    with _runtime_state_lock:
        return _pipeline_tasks.pop(report_id, None)


async def get_pipeline_task_for_report(report_id: str) -> asyncio.Task[None] | None:
    """Atomically read pipeline task for report."""
    with _runtime_state_lock:
        return _pipeline_tasks.get(report_id)


async def release_processing_report(report_id: str) -> None:
    """Atomically clear all processing entries for report_id."""
    with _runtime_state_lock:
        keys_to_remove = [k for k, v in _processing_reports.items() if v == report_id]
        for key in keys_to_remove:
            _processing_reports.pop(key, None)


async def is_processing_report(report_id: str) -> bool:
    """Check whether report_id is still present in processing map."""
    with _runtime_state_lock:
        return report_id in _processing_reports.values()


def set_pipeline_task(report_id: str, task: asyncio.Task[None]) -> None:
    with _runtime_state_lock:
        _pipeline_tasks[report_id] = task


async def shutdown_runtime_state() -> None:
    """Cancel running pipeline tasks and clear in-memory runtime state."""
    with _runtime_state_lock:
        tasks = list(_pipeline_tasks.values())

    current_loop = asyncio.get_running_loop()
    local_tasks: list[asyncio.Task[None]] = []

    for task in tasks:
        if task.done():
            continue
        task_loop = task.get_loop()
        if task_loop is current_loop:
            task.cancel()
            local_tasks.append(task)
            continue
        if task_loop.is_closed():
            continue
        with contextlib.suppress(RuntimeError):
            task_loop.call_soon_threadsafe(task.cancel)

    if local_tasks:
        await asyncio.gather(*local_tasks, return_exceptions=True)

    with _runtime_state_lock:
        _pipeline_tasks.clear()
        _processing_reports.clear()
        _report_runs.clear()


def get_processing_reports() -> dict[str, str]:
    """Map of query hash → report_id for deduplication."""
    return _processing_reports
