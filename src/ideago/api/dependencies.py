"""Shared FastAPI dependencies — singleton services wired from config.

FastAPI 依赖注入：从配置构建单例服务实例。
"""

from __future__ import annotations

import asyncio

from ideago.cache.file_cache import FileCache
from ideago.config.settings import get_settings
from ideago.llm.client import LLMClient
from ideago.pipeline.aggregator import Aggregator
from ideago.pipeline.extractor import Extractor
from ideago.pipeline.intent_parser import IntentParser
from ideago.pipeline.orchestrator import Orchestrator
from ideago.sources.github_source import GitHubSource
from ideago.sources.hackernews_source import HackerNewsSource
from ideago.sources.registry import SourceRegistry
from ideago.sources.tavily_source import TavilySource

_orchestrator: Orchestrator | None = None
_cache: FileCache | None = None
_report_queues: dict[str, asyncio.Queue] = {}
_processing_reports: dict[str, str] = {}


def get_cache() -> FileCache:
    global _cache
    if _cache is None:
        settings = get_settings()
        _cache = FileCache(settings.cache_dir, settings.cache_ttl_hours)
    return _cache


def get_orchestrator() -> Orchestrator:
    global _orchestrator
    if _orchestrator is None:
        settings = get_settings()
        llm = LLMClient(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            timeout=settings.openai_timeout_seconds,
        )
        registry = SourceRegistry()
        registry.register(
            GitHubSource(
                token=settings.github_token, timeout=settings.source_timeout_seconds
            )
        )
        registry.register(
            TavilySource(
                api_key=settings.tavily_api_key, timeout=settings.source_timeout_seconds
            )
        )
        registry.register(HackerNewsSource(timeout=settings.source_timeout_seconds))

        _orchestrator = Orchestrator(
            intent_parser=IntentParser(llm),
            extractor=Extractor(llm),
            aggregator=Aggregator(llm),
            registry=registry,
            cache=get_cache(),
            source_timeout=settings.source_timeout_seconds,
            extraction_timeout=settings.extraction_timeout_seconds,
            max_results_per_source=settings.max_results_per_source,
        )
    return _orchestrator


def get_report_queue(report_id: str) -> asyncio.Queue:
    """Get or create an event queue for a report."""
    if report_id not in _report_queues:
        _report_queues[report_id] = asyncio.Queue()
    return _report_queues[report_id]


def remove_report_queue(report_id: str) -> None:
    """Clean up event queue for a report."""
    _report_queues.pop(report_id, None)


def get_processing_reports() -> dict[str, str]:
    """Map of query hash → report_id for deduplication."""
    return _processing_reports
