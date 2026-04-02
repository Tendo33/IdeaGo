"""Shared FastAPI dependencies — singleton services wired from config.

FastAPI 依赖注入：从配置构建单例服务实例。
"""

from __future__ import annotations

import asyncio
import contextlib
import threading

import httpx

from ideago.api.runtime_state import (
    PipelineTaskRegistry,
    ProcessingDedupRegistry,
    ReportRunRegistry,
    ReportRunState,
)
from ideago.cache.base import ReportRepository
from ideago.config.settings import get_settings
from ideago.llm.chat_model import ChatModelClient
from ideago.observability.error_catalog import log_error_event
from ideago.observability.log_config import get_logger
from ideago.pipeline.aggregator import Aggregator
from ideago.pipeline.extractor import Extractor
from ideago.pipeline.intent_parser import IntentParser
from ideago.pipeline.langgraph_engine import LangGraphEngine
from ideago.pipeline.query_planning import QueryPlanner
from ideago.sources.appstore_source import AppStoreSource
from ideago.sources.github_source import GitHubSource
from ideago.sources.hackernews_source import HackerNewsSource
from ideago.sources.producthunt_source import ProductHuntSource
from ideago.sources.reddit_source import RedditSource
from ideago.sources.registry import SourceRegistry
from ideago.sources.tavily_source import TavilySource

logger = get_logger(__name__)

_orchestrator: LangGraphEngine | None = None
_cache: ReportRepository | None = None
_runtime_state_lock = threading.RLock()
_REPORT_RUN_TTL_SECONDS = 600
_dedup_http_client: httpx.AsyncClient | None = None
_report_run_registry = ReportRunRegistry(
    ttl_seconds=_REPORT_RUN_TTL_SECONDS,
    lock=_runtime_state_lock,
)
_processing_dedup_registry = ProcessingDedupRegistry(_runtime_state_lock)
_pipeline_task_registry = PipelineTaskRegistry(_runtime_state_lock)

# Backward-compatible dict aliases used by tests.
_report_runs = _report_run_registry.runs
_processing_reports = _processing_dedup_registry.reservations
_pipeline_tasks = _pipeline_task_registry.tasks


def get_cache() -> ReportRepository:
    global _cache
    if _cache is None:
        settings = get_settings()
        if settings.supabase_url and settings.supabase_service_role_key:
            from ideago.cache.supabase_cache import SupabaseReportRepository

            _cache = SupabaseReportRepository(
                ttl_hours=settings.anonymous_cache_ttl_hours,
            )
        else:
            if settings.environment == "production":
                raise RuntimeError(
                    "FileCache cannot be used in production. "
                    "Configure SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY."
                )
            from ideago.cache.file_cache import FileCache

            logger.warning(
                "Using local FileCache (dev-only). "
                "Configure Supabase for multi-tenant data isolation."
            )
            _cache = FileCache(
                settings.cache_dir,
                settings.anonymous_cache_ttl_hours,
                max_entries=settings.file_cache_max_entries,
            )
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
        max_age = settings.source_max_age_days
        registry = SourceRegistry()
        registry.register(
            GitHubSource(
                token=settings.github_token,
                timeout=settings.source_timeout_seconds,
                max_concurrent_queries=settings.source_query_concurrency,
                max_age_days=max_age,
            )
        )
        registry.register(
            TavilySource(
                api_key=settings.tavily_api_key,
                base_url=settings.tavily_base_url,
                timeout=settings.source_timeout_seconds,
                max_concurrent_queries=settings.source_query_concurrency,
                max_age_days=max_age,
            )
        )
        registry.register(
            HackerNewsSource(
                timeout=settings.source_timeout_seconds,
                max_concurrent_queries=settings.source_query_concurrency,
                max_age_days=max_age,
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
                enable_public_fallback=settings.reddit_enable_public_fallback,
                public_fallback_limit=settings.reddit_public_fallback_limit,
                public_fallback_delay_seconds=settings.reddit_public_fallback_delay_seconds,
                max_age_days=max_age,
            )
        )

        _orchestrator = LangGraphEngine(
            intent_parser=IntentParser(llm),
            query_planner=QueryPlanner(llm),
            extractor=Extractor(llm),
            aggregator=Aggregator(llm),
            registry=registry,
            cache=get_cache(),
            checkpoint_db_path=settings.langgraph_checkpoint_db_path,
            source_timeout=settings.source_timeout_seconds,
            extraction_timeout=settings.extraction_timeout_seconds,
            aggregation_timeout=settings.aggregation_timeout_seconds,
            max_results_per_source=settings.max_results_per_source,
            extractor_max_results_per_source=settings.extractor_max_results_per_source,
            source_global_concurrency=settings.source_global_concurrency,
            checkpoint_db_url=settings.supabase_db_url,
        )
    return _orchestrator


def cleanup_report_runs() -> None:
    """Drop finished report run states after TTL to avoid memory growth."""
    _report_run_registry.cleanup_stale()


def get_or_create_report_run(report_id: str) -> ReportRunState:
    """Get or create runtime event state for a report."""
    return _report_run_registry.get_or_create(report_id)


def get_report_run(report_id: str) -> ReportRunState | None:
    """Get runtime event state for a report if present."""
    return _report_run_registry.get(report_id)


def _supabase_dedup_configured() -> bool:
    """Return True when Supabase REST is available for distributed dedup."""
    settings = get_settings()
    return bool(settings.supabase_url and settings.supabase_service_role_key)


def _get_dedup_client() -> httpx.AsyncClient:
    global _dedup_http_client
    if _dedup_http_client is None:
        _dedup_http_client = httpx.AsyncClient(
            timeout=10.0,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
    return _dedup_http_client


def _dedup_headers() -> dict[str, str]:
    settings = get_settings()
    return {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Content-Type": "application/json",
    }


async def _pg_reserve(key: str, report_id: str, user_id: str) -> str | None:
    """Try to reserve a slot via Supabase RPC. Returns existing report_id or None."""
    settings = get_settings()
    try:
        resp = await _get_dedup_client().post(
            f"{settings.supabase_url}/rest/v1/rpc/reserve_processing_slot",
            headers=_dedup_headers(),
            json={"p_key": key, "p_report_id": report_id, "p_user_id": user_id},
        )
        if resp.status_code == 200:
            result = resp.json()
            return result if isinstance(result, str) else None
        log_error_event(
            logger,
            error_code="DEDUP_PG_RESERVE_FAILED",
            subsystem="processing_dedup",
            details={"status_code": resp.status_code},
            message="reserve_processing_slot RPC returned non-200",
        )
    except httpx.TimeoutException:
        log_error_event(
            logger,
            error_code="DEDUP_PG_RESERVE_TIMEOUT",
            subsystem="processing_dedup",
            message="reserve_processing_slot RPC timeout",
        )
    except httpx.HTTPError:
        log_error_event(
            logger,
            error_code="DEDUP_PG_RESERVE_HTTP_ERROR",
            subsystem="processing_dedup",
            message="reserve_processing_slot RPC HTTP error",
            include_exception=True,
        )
    except Exception:
        log_error_event(
            logger,
            error_code="DEDUP_PG_RESERVE_UNEXPECTED",
            subsystem="processing_dedup",
            message="reserve_processing_slot RPC unexpected error",
            include_exception=True,
        )
    return None


async def _pg_release(report_id: str) -> None:
    """Release PG-backed processing slot for a report."""
    settings = get_settings()
    try:
        await _get_dedup_client().post(
            f"{settings.supabase_url}/rest/v1/rpc/release_processing_slot",
            headers=_dedup_headers(),
            json={"p_report_id": report_id},
        )
    except httpx.TimeoutException:
        log_error_event(
            logger,
            error_code="DEDUP_PG_RELEASE_TIMEOUT",
            subsystem="processing_dedup",
            message="release_processing_slot RPC timeout",
        )
    except httpx.HTTPError:
        log_error_event(
            logger,
            error_code="DEDUP_PG_RELEASE_HTTP_ERROR",
            subsystem="processing_dedup",
            message="release_processing_slot RPC HTTP error",
            include_exception=True,
        )
    except Exception:
        log_error_event(
            logger,
            error_code="DEDUP_PG_RELEASE_UNEXPECTED",
            subsystem="processing_dedup",
            message="release_processing_slot RPC unexpected error",
            include_exception=True,
        )


async def _pg_is_processing(report_id: str) -> bool:
    """Check PG-backed processing state."""
    settings = get_settings()
    try:
        resp = await _get_dedup_client().post(
            f"{settings.supabase_url}/rest/v1/rpc/is_report_processing",
            headers=_dedup_headers(),
            json={"p_report_id": report_id},
        )
        if resp.status_code == 200:
            return resp.json() is True
        log_error_event(
            logger,
            error_code="DEDUP_PG_IS_PROCESSING_FAILED",
            subsystem="processing_dedup",
            details={"status_code": resp.status_code},
            message="is_report_processing RPC returned non-200",
        )
    except httpx.TimeoutException:
        log_error_event(
            logger,
            error_code="DEDUP_PG_IS_PROCESSING_TIMEOUT",
            subsystem="processing_dedup",
            message="is_report_processing RPC timeout",
        )
    except httpx.HTTPError:
        log_error_event(
            logger,
            error_code="DEDUP_PG_IS_PROCESSING_HTTP_ERROR",
            subsystem="processing_dedup",
            message="is_report_processing RPC HTTP error",
            include_exception=True,
        )
    except Exception:
        log_error_event(
            logger,
            error_code="DEDUP_PG_IS_PROCESSING_UNEXPECTED",
            subsystem="processing_dedup",
            message="is_report_processing RPC unexpected error",
            include_exception=True,
        )
    return False


async def reserve_processing_report(
    query_hash: str, report_id: str, *, user_id: str = ""
) -> str | None:
    """Atomically reserve processing slot; return existing active report_id if present.

    Uses PostgreSQL RPC when Supabase is configured (multi-worker safe),
    falls back to in-memory dict otherwise.  Always updates the local dict
    so that SSE and task tracking work within this process.
    """
    key = f"{user_id}:{query_hash}" if user_id else query_hash

    if _supabase_dedup_configured():
        existing = await _pg_reserve(key, report_id, user_id)
        if existing is not None:
            return existing
        _processing_dedup_registry.assign(key, report_id)
        return None

    return _processing_dedup_registry.reserve(key, report_id)


async def register_pipeline_task(report_id: str, task: asyncio.Task[None]) -> None:
    """Atomically register pipeline task."""
    _pipeline_task_registry.register(report_id, task)


async def remove_pipeline_task(report_id: str) -> asyncio.Task[None] | None:
    """Atomically remove pipeline task."""
    return _pipeline_task_registry.remove(report_id)


async def get_pipeline_task_for_report(report_id: str) -> asyncio.Task[None] | None:
    """Atomically read pipeline task for report."""
    return _pipeline_task_registry.get(report_id)


async def release_processing_report(report_id: str) -> None:
    """Atomically clear all processing entries for report_id.

    Cleans both PG (when configured) and local in-memory state.
    """
    if _supabase_dedup_configured():
        await _pg_release(report_id)

    _processing_dedup_registry.release_report(report_id)


async def is_processing_report(report_id: str) -> bool:
    """Check whether report_id is still present in processing map.

    Checks both local dict and PG (when configured).
    """
    if _processing_dedup_registry.has_report_id(report_id):
        return True

    if _supabase_dedup_configured():
        return await _pg_is_processing(report_id)

    return False


def set_pipeline_task(report_id: str, task: asyncio.Task[None]) -> None:
    _pipeline_task_registry.register(report_id, task)


async def shutdown_runtime_state() -> None:
    """Cancel running pipeline tasks and clear in-memory runtime state."""
    global _dedup_http_client
    tasks = _pipeline_task_registry.snapshot()

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

    _pipeline_task_registry.clear()
    _processing_dedup_registry.clear()
    _report_run_registry.clear()

    if _dedup_http_client is not None:
        await _dedup_http_client.aclose()
        _dedup_http_client = None


def get_processing_reports() -> dict[str, str]:
    """Snapshot of query-hash → report_id for deduplication.

    Returns a shallow copy so callers never mutate the live dict.
    """
    return _processing_dedup_registry.snapshot()


def is_report_id_processing(report_id: str) -> bool:
    """Check if a specific report_id is in the local processing map (sync)."""
    return _processing_dedup_registry.has_report_id(report_id)
