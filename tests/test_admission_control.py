"""Admission control for in-flight analyses.

Rate limiting bounds how fast requests arrive. It says nothing about how much
work is already running — and an analysis runs for minutes while fanning out to
several concurrent source fetches and LLM calls. At 10 requests/minute one user
could hold ten of them at once on a single-process server.
"""

from __future__ import annotations

import asyncio

import pytest

from ideago.api import dependencies as deps
from ideago.api.errors import AppError
from ideago.api.routes import analyze as analyze_route
from ideago.config import settings as settings_module
from ideago.config.settings import Settings, reload_settings

USER = "user-1"
OTHER = "user-2"


@pytest.fixture(autouse=True)
def _clean_registry():
    deps._pipeline_task_registry.clear()
    yield
    deps._pipeline_task_registry.clear()
    settings_module.get_settings.cache_clear()
    reload_settings()


def _install(monkeypatch, **overrides):
    settings = Settings(_env_file=None, environment="development", **overrides)
    monkeypatch.setattr(settings_module, "_settings_override", settings)
    settings_module.get_settings.cache_clear()


async def _never_finishes() -> None:
    await asyncio.Event().wait()


def _register(report_id: str, user_id: str, task: asyncio.Task) -> None:
    deps._pipeline_task_registry.register(report_id, task, user_id=user_id)


@pytest.mark.asyncio
async def test_allows_work_below_the_cap(monkeypatch) -> None:
    _install(monkeypatch, max_concurrent_analyses_per_user=2)
    task = asyncio.create_task(_never_finishes())
    _register("r1", USER, task)
    try:
        analyze_route._assert_capacity_available(USER)  # must not raise
    finally:
        task.cancel()


@pytest.mark.asyncio
async def test_rejects_a_user_at_their_own_cap(monkeypatch) -> None:
    _install(monkeypatch, max_concurrent_analyses_per_user=2)
    tasks = [asyncio.create_task(_never_finishes()) for _ in range(2)]
    for i, task in enumerate(tasks):
        _register(f"r{i}", USER, task)
    try:
        with pytest.raises(AppError) as exc:
            analyze_route._assert_capacity_available(USER)
        assert exc.value.status_code == 429
        assert exc.value.detail["code"] == "ANALYSIS_CAPACITY_EXCEEDED"
    finally:
        for task in tasks:
            task.cancel()


@pytest.mark.asyncio
async def test_one_user_cannot_starve_another(monkeypatch) -> None:
    """The per-user cap is what stops a single account eating the whole budget."""
    _install(monkeypatch, max_concurrent_analyses_per_user=2, max_concurrent_analyses=8)
    tasks = [asyncio.create_task(_never_finishes()) for _ in range(2)]
    for i, task in enumerate(tasks):
        _register(f"r{i}", USER, task)
    try:
        with pytest.raises(AppError):
            analyze_route._assert_capacity_available(USER)
        analyze_route._assert_capacity_available(OTHER)  # unaffected
    finally:
        for task in tasks:
            task.cancel()


@pytest.mark.asyncio
async def test_rejects_everyone_when_the_server_is_saturated(monkeypatch) -> None:
    _install(
        monkeypatch, max_concurrent_analyses=3, max_concurrent_analyses_per_user=50
    )
    tasks = [asyncio.create_task(_never_finishes()) for _ in range(3)]
    for i, task in enumerate(tasks):
        _register(f"r{i}", f"u{i}", task)
    try:
        with pytest.raises(AppError) as exc:
            analyze_route._assert_capacity_available("fresh-user")
        assert exc.value.status_code == 503
    finally:
        for task in tasks:
            task.cancel()


@pytest.mark.asyncio
async def test_finished_tasks_free_their_slot(monkeypatch) -> None:
    """A completed run must not keep occupying capacity."""
    _install(monkeypatch, max_concurrent_analyses_per_user=1)

    async def _done() -> None:
        return None

    task = asyncio.create_task(_done())
    await task
    _register("r1", USER, task)

    analyze_route._assert_capacity_available(USER)  # must not raise
    assert deps.active_analysis_count() == 0


@pytest.mark.asyncio
async def test_removal_releases_capacity(monkeypatch) -> None:
    _install(monkeypatch, max_concurrent_analyses_per_user=1)
    task = asyncio.create_task(_never_finishes())
    _register("r1", USER, task)
    try:
        with pytest.raises(AppError):
            analyze_route._assert_capacity_available(USER)
        await deps.remove_pipeline_task("r1")
        analyze_route._assert_capacity_available(USER)  # must not raise
    finally:
        task.cancel()


@pytest.mark.asyncio
async def test_counts_are_scoped_per_user(monkeypatch) -> None:
    _install(monkeypatch, max_concurrent_analyses_per_user=5)
    tasks = [asyncio.create_task(_never_finishes()) for _ in range(3)]
    _register("a", USER, tasks[0])
    _register("b", USER, tasks[1])
    _register("c", OTHER, tasks[2])
    try:
        assert deps.active_analysis_count_for_user(USER) == 2
        assert deps.active_analysis_count_for_user(OTHER) == 1
        assert deps.active_analysis_count() == 3
    finally:
        for task in tasks:
            task.cancel()
