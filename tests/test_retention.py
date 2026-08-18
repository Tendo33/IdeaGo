"""Retention jobs must actually be scheduled.

Migrations 010/011/012 shipped cleanup functions and 005 shipped
``cleanup_stale_processing_slots``. None of them were ever called, and
``auth_sessions`` had no cleanup function at all — four tables grew for the
life of the deployment. This test keeps SQL and scheduler in step.
"""

from __future__ import annotations

import re
from pathlib import Path

import httpx
import pytest

from ideago.config import settings as settings_module
from ideago.config.settings import Settings, reload_settings
from ideago.observability import retention

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "supabase" / "migrations"

# Superseded by the individually numbered files; it is a bootstrap snapshot.
_SNAPSHOT = "000_all_migrations.sql"


def _cleanup_functions_defined_in_sql() -> set[str]:
    pattern = re.compile(r"FUNCTION\s+public\.(cleanup_[a-z_]+)", re.IGNORECASE)
    found: set[str] = set()
    for path in MIGRATIONS_DIR.glob("*.sql"):
        if path.name == _SNAPSHOT:
            continue
        found.update(match.lower() for match in pattern.findall(path.read_text()))
    return found


def _scheduled_rpcs() -> set[str]:
    scheduled = {
        job.rpc for job in retention.build_retention_jobs(cleanup_interval_seconds=3600)
    }
    # Driven from their own call sites rather than the retention sweep.
    scheduled.add("cleanup_expired_reports")  # ReportRepository.cleanup_expired
    scheduled.add("cleanup_rate_limit_hits")  # rate_limit.cleanup_pg_rate_limit_hits
    return scheduled


@pytest.fixture(autouse=True)
def _restore_settings():
    yield
    settings_module.get_settings.cache_clear()
    reload_settings()


def _install(monkeypatch, **overrides):
    settings = Settings(_env_file=None, environment="development", **overrides)
    monkeypatch.setattr(settings_module, "_settings_override", settings)
    settings_module.get_settings.cache_clear()


def test_every_cleanup_function_has_a_caller() -> None:
    defined = _cleanup_functions_defined_in_sql()
    assert defined, "expected cleanup functions in supabase/migrations"

    orphans = defined - _scheduled_rpcs()

    assert not orphans, (
        f"cleanup functions defined in SQL but never invoked: {sorted(orphans)}. "
        "Add them to build_retention_jobs() or document a pg_cron schedule."
    )


def test_auth_sessions_cleanup_exists() -> None:
    """The table that previously had no retention story at all."""
    assert "cleanup_auth_sessions" in _cleanup_functions_defined_in_sql()


@pytest.mark.asyncio
async def test_no_calls_when_supabase_is_not_configured(monkeypatch) -> None:
    _install(monkeypatch)
    assert await retention.run_retention_jobs(cleanup_interval_seconds=3600) == {}


@pytest.mark.asyncio
async def test_runs_every_job_and_reports_row_counts(monkeypatch) -> None:
    _install(
        monkeypatch,
        supabase_url="https://p.supabase.co",
        supabase_service_role_key="service-role",
    )
    called: list[str] = []

    class _Client:
        async def post(self, url, headers=None, json=None):
            called.append(url.rsplit("/", 1)[-1])
            return httpx.Response(200, json=3)

    monkeypatch.setattr(retention, "get_supabase_client", lambda: _Client())

    removed = await retention.run_retention_jobs(cleanup_interval_seconds=3600)

    expected = [
        job.rpc for job in retention.build_retention_jobs(cleanup_interval_seconds=3600)
    ]
    assert called == expected
    assert all(count == 3 for count in removed.values())


@pytest.mark.asyncio
async def test_one_failing_job_does_not_stop_the_others(monkeypatch) -> None:
    """A missing function means an unapplied migration, not a reason to stop."""
    _install(
        monkeypatch,
        supabase_url="https://p.supabase.co",
        supabase_service_role_key="service-role",
    )
    attempted: list[str] = []

    class _Client:
        async def post(self, url, headers=None, json=None):
            name = url.rsplit("/", 1)[-1]
            attempted.append(name)
            if name == "cleanup_old_webhook_events":
                raise httpx.ConnectError("boom")
            return httpx.Response(404, json={"code": "PGRST202"})

    monkeypatch.setattr(retention, "get_supabase_client", lambda: _Client())

    removed = await retention.run_retention_jobs(cleanup_interval_seconds=3600)

    expected = [
        job.rpc for job in retention.build_retention_jobs(cleanup_interval_seconds=3600)
    ]
    assert attempted == expected, "every job must be attempted"
    assert removed == {}, "failed jobs report no rows removed"
