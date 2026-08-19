"""Admission control for in-flight analyses.

Rate limiting bounds how fast requests arrive. It says nothing about how much
work is already running — and an analysis runs for minutes while fanning out to
several concurrent source fetches and LLM calls. At 10 requests/minute one user
could hold ten of them at once on a single-process server.
"""

from __future__ import annotations

import asyncio
from unittest import mock

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


class TestTotalTimeBudget:
    """A run with no outer bound would hold its admission slot indefinitely.

    Per-stage timeouts do not bound the total: each LLM call retries three times
    per endpoint and every fallback endpoint multiplies that again. The
    arithmetic worst case is roughly ten minutes with no fallbacks and past
    twenty with two — long enough to turn the capacity cap into a slow deadlock.
    """

    @pytest.mark.asyncio
    async def test_a_hung_pipeline_is_cut_off(self, monkeypatch, tmp_path) -> None:
        from ideago.api.routes import analyze as analyze_route
        from ideago.cache.file_cache import FileCache
        from ideago.pipeline.events import EventType

        cache = FileCache(str(tmp_path / "cache"), ttl_hours=24)
        _install(monkeypatch, analysis_total_timeout_seconds=60)
        # Shrink the budget past the settings floor for a fast test.
        monkeypatch.setattr(
            analyze_route,
            "get_settings",
            lambda: type("S", (), {"analysis_total_timeout_seconds": 0.05})(),
        )

        class HangingOrchestrator:
            async def run(self, *_args, **_kwargs):
                await asyncio.Event().wait()

        with (
            mock.patch.object(analyze_route, "get_cache", return_value=cache),
            mock.patch.object(
                analyze_route, "get_orchestrator", return_value=HangingOrchestrator()
            ),
        ):
            await analyze_route._run_pipeline("a query that hangs", "report-hang")

        status = await cache.get_status("report-hang")
        assert status is not None
        assert status["status"] == "failed"
        assert status["error_code"] == "PIPELINE_TIMEOUT"

        run_state = deps.get_report_run("report-hang")
        assert run_state is not None
        errors = [e for e in run_state.history if e.type == EventType.ERROR]
        assert errors
        assert errors[-1].data["error_code"] == "PIPELINE_TIMEOUT"

    @pytest.mark.asyncio
    async def test_timing_out_releases_the_admission_slot(
        self, monkeypatch, tmp_path
    ) -> None:
        """Otherwise the cap would leak a slot on every hang."""
        from ideago.api.routes import analyze as analyze_route
        from ideago.cache.file_cache import FileCache

        cache = FileCache(str(tmp_path / "cache"), ttl_hours=24)
        _install(monkeypatch)
        monkeypatch.setattr(
            analyze_route,
            "get_settings",
            lambda: type("S", (), {"analysis_total_timeout_seconds": 0.05})(),
        )

        class HangingOrchestrator:
            async def run(self, *_args, **_kwargs):
                await asyncio.Event().wait()

        async def drive() -> None:
            with (
                mock.patch.object(analyze_route, "get_cache", return_value=cache),
                mock.patch.object(
                    analyze_route,
                    "get_orchestrator",
                    return_value=HangingOrchestrator(),
                ),
            ):
                await analyze_route._run_pipeline("hang", "report-slot", USER)

        task = asyncio.create_task(drive())
        _register("report-slot", USER, task)
        assert deps.active_analysis_count_for_user(USER) == 1
        await task
        assert deps.active_analysis_count_for_user(USER) == 0

    @pytest.mark.asyncio
    async def test_a_user_cancel_is_not_reported_as_a_timeout(
        self, monkeypatch, tmp_path
    ) -> None:
        """wait_for sits between the cancel and the pipeline; the two must not blur."""
        from ideago.api.routes import analyze as analyze_route
        from ideago.cache.file_cache import FileCache

        cache = FileCache(str(tmp_path / "cache"), ttl_hours=24)
        _install(monkeypatch)
        monkeypatch.setattr(
            analyze_route,
            "get_settings",
            lambda: type("S", (), {"analysis_total_timeout_seconds": 30})(),
        )

        class HangingOrchestrator:
            async def run(self, *_args, **_kwargs):
                await asyncio.Event().wait()

        async def drive() -> None:
            with (
                mock.patch.object(analyze_route, "get_cache", return_value=cache),
                mock.patch.object(
                    analyze_route,
                    "get_orchestrator",
                    return_value=HangingOrchestrator(),
                ),
            ):
                await analyze_route._run_pipeline("cancel me", "report-cancel", USER)

        task = asyncio.create_task(drive())
        await asyncio.sleep(0.01)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

        status = await cache.get_status("report-cancel")
        assert status is not None
        assert status["status"] == "cancelled"
        assert status["error_code"] != "PIPELINE_TIMEOUT"
