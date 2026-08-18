"""State-consistency regressions fixed on 2026-08-18."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from ideago.api import app as app_module
from ideago.api.routes import analyze as analyze_route
from ideago.auth import supabase_admin
from ideago.billing import stripe_service
from ideago.config import settings as settings_module
from ideago.config.settings import Settings, reload_settings
from ideago.pipeline.events import EventType, PipelineEvent


@pytest.fixture(autouse=True)
def _restore_settings():
    yield
    settings_module.get_settings.cache_clear()
    reload_settings()


def _install(monkeypatch, **overrides):
    settings = Settings(_env_file=None, **overrides)
    monkeypatch.setattr(settings_module, "_settings_override", settings)
    settings_module.get_settings.cache_clear()
    monkeypatch.setattr(app_module, "_init_sentry", lambda _s: None)
    return settings


class TestShortCircuitResponsesCarryCorsHeaders:
    """CORS must wrap everything, or the SPA cannot read 429 / 403 bodies.

    Starlette's ``add_middleware`` inserts at position 0, so the last registered
    middleware is the outermost. CORS used to be registered first, i.e.
    innermost, so responses that short-circuited above it reached a
    cross-origin browser with no Access-Control-Allow-Origin header.
    """

    ORIGIN = "http://localhost:5173"

    def test_csrf_rejection_is_readable_cross_origin(self, monkeypatch) -> None:
        _install(monkeypatch, environment="development")
        with TestClient(app_module.create_app()) as client:
            response = client.post(
                "/api/v1/analyze",
                json={"query": "an idea worth validating"},
                headers={"Origin": self.ORIGIN},
            )

        assert response.status_code == 403
        assert response.json()["error"]["code"] == "CSRF_MISSING_HEADER"
        assert response.headers["access-control-allow-origin"] == self.ORIGIN

    def test_trace_id_is_exposed_to_cross_origin_javascript(self, monkeypatch) -> None:
        _install(monkeypatch, environment="development")
        with TestClient(app_module.create_app()) as client:
            response = client.get("/api/v1/health", headers={"Origin": self.ORIGIN})

        assert response.headers["access-control-allow-origin"] == self.ORIGIN
        exposed = response.headers.get("access-control-expose-headers", "")
        assert "X-Trace-Id" in exposed

    def test_cors_is_the_outermost_middleware(self, monkeypatch) -> None:
        """Pin the ordering itself, not just one symptom of getting it wrong."""
        from starlette.middleware.cors import CORSMiddleware

        _install(monkeypatch, environment="development")
        app = app_module.create_app()

        assert app.user_middleware[0].cls is CORSMiddleware


class TestCacheHitRefundsQuota:
    """A cached answer costs no LLM work, so it must not consume quota."""

    def test_cache_hit_event_is_flagged(self) -> None:
        event = PipelineEvent(
            type=EventType.REPORT_READY,
            stage="cache",
            message="Found cached report",
            data={"report_id": "r-1", "cache_hit": True},
        )
        run_state = type("RunState", (), {"history_snapshot": lambda self: [event]})()

        assert analyze_route._was_served_from_cache(run_state) is True

    def test_freshly_computed_report_is_not_flagged(self) -> None:
        event = PipelineEvent(
            type=EventType.REPORT_READY,
            stage="complete",
            message="Report ready",
            data={"report_id": "r-1"},
        )
        run_state = type("RunState", (), {"history_snapshot": lambda self: [event]})()

        assert analyze_route._was_served_from_cache(run_state) is False

    def test_no_events_is_not_a_cache_hit(self) -> None:
        run_state = type("RunState", (), {"history_snapshot": lambda self: []})()
        assert analyze_route._was_served_from_cache(run_state) is False


class TestWebhookClaimIsReleasedOnFailure:
    """Claim-before-process must not swallow events when processing fails."""

    @pytest.mark.asyncio
    async def test_failure_releases_the_claim(self, monkeypatch) -> None:
        _install(
            monkeypatch,
            environment="development",
            supabase_url="https://p.supabase.co",
            supabase_service_role_key="service-role",
        )
        released: list[str] = []

        async def _fail(_event):
            raise RuntimeError("processing blew up")

        async def _record_release(event_id):
            released.append(event_id)

        monkeypatch.setattr(
            stripe_service, "_try_claim_event", AsyncMock(return_value=True)
        )
        monkeypatch.setattr(stripe_service, "_process_webhook_event", _fail)
        monkeypatch.setattr(stripe_service, "_release_event_claim", _record_release)

        event = type(
            "Event", (), {"id": "evt_boom", "type": "checkout.session.completed"}
        )()

        with pytest.raises(RuntimeError):
            await stripe_service.handle_webhook_event(event)

        assert released == ["evt_boom"], (
            "an unreleased claim makes Stripe's retry a silent no-op"
        )

    @pytest.mark.asyncio
    async def test_success_keeps_the_claim(self, monkeypatch) -> None:
        released: list[str] = []

        monkeypatch.setattr(
            stripe_service, "_try_claim_event", AsyncMock(return_value=True)
        )
        monkeypatch.setattr(
            stripe_service, "_process_webhook_event", AsyncMock(return_value=None)
        )
        monkeypatch.setattr(
            stripe_service,
            "_release_event_claim",
            lambda event_id: released.append(event_id),
        )

        event = type(
            "Event", (), {"id": "evt_ok", "type": "checkout.session.completed"}
        )()
        await stripe_service.handle_webhook_event(event)

        assert released == [], "a processed event must stay claimed"

    @pytest.mark.asyncio
    async def test_already_claimed_event_is_skipped(self, monkeypatch) -> None:
        processed = AsyncMock()
        monkeypatch.setattr(
            stripe_service, "_try_claim_event", AsyncMock(return_value=False)
        )
        monkeypatch.setattr(stripe_service, "_process_webhook_event", processed)

        event = type("Event", (), {"id": "evt_dup", "type": "x"})()
        await stripe_service.handle_webhook_event(event)

        processed.assert_not_awaited()


class TestQuotaRefundHasNoLostUpdate:
    """The read-modify-write fallback dropped concurrent refunds."""

    @pytest.mark.asyncio
    async def test_rpc_success_is_reported(self, monkeypatch) -> None:
        _install(
            monkeypatch,
            environment="development",
            supabase_url="https://p.supabase.co",
            supabase_service_role_key="service-role",
        )
        client = AsyncMock()
        client.post = AsyncMock(return_value=httpx.Response(200, json=True))
        monkeypatch.setattr(supabase_admin, "_get_client", lambda: client)

        assert await supabase_admin.refund_quota_charge("u1") is True

    @pytest.mark.asyncio
    async def test_rpc_failure_does_not_fall_back_to_a_racy_write(
        self, monkeypatch
    ) -> None:
        _install(
            monkeypatch,
            environment="development",
            supabase_url="https://p.supabase.co",
            supabase_service_role_key="service-role",
        )
        client = AsyncMock()
        client.post = AsyncMock(
            return_value=httpx.Response(500, json={"code": "XX000"})
        )
        client.patch = AsyncMock()
        monkeypatch.setattr(supabase_admin, "_get_client", lambda: client)

        with patch.object(supabase_admin, "get_profile", new=AsyncMock()) as profile:
            result = await supabase_admin.refund_quota_charge("u1")

        assert result is False
        client.patch.assert_not_awaited(), "no read-modify-write fallback"
        profile.assert_not_awaited(), "must not read the profile to compute a new value"

    @pytest.mark.asyncio
    async def test_failure_is_recorded_for_reconciliation(self, monkeypatch) -> None:
        _install(
            monkeypatch,
            environment="development",
            supabase_url="https://p.supabase.co",
            supabase_service_role_key="service-role",
        )
        client = AsyncMock()
        client.post = AsyncMock(side_effect=RuntimeError("network down"))
        monkeypatch.setattr(supabase_admin, "_get_client", lambda: client)

        recorded: list[tuple] = []
        monkeypatch.setattr(
            supabase_admin.app_metrics,
            "increment_event",
            lambda name, **kw: recorded.append((name, kw.get("reason"))),
        )

        assert await supabase_admin.refund_quota_charge("u1") is False
        assert ("quota_refund_failed", "rpc_exception") in recorded
