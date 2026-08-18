"""Round-trip budget for the authenticated request path.

The audit measured six outbound Supabase calls for a single ``POST /analyze``
from a LinuxDo (custom-session) user:

  2  rate-limit middleware resolving the user (session row + profile row)
  2  route dependency resolving the same user again
  1  check_quota_available
  1  check_and_increment_quota

These tests pin the budget so the duplication cannot silently return.
"""

from __future__ import annotations

import jwt
import pytest
from fastapi import Request

from ideago.auth import dependencies as auth_deps
from ideago.auth import session_cache
from ideago.config import settings as settings_module
from ideago.config.settings import Settings, reload_settings

AUTH_SECRET = "roundtrip-budget-secret-0123456789ab"
USER_ID = "11111111-2222-3333-4444-555555555555"
SESSION_ID = "session-abc"


def _token() -> str:
    return jwt.encode(
        {
            "sub": USER_ID,
            "email": "user@example.com",
            "provider": "linuxdo",
            "sid": SESSION_ID,
            "aud": "ideago-auth",
        },
        AUTH_SECRET,
        algorithm="HS256",
    )


def _request(token: str) -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/analyze",
        "headers": [(b"authorization", f"Bearer {token}".encode())],
        "query_string": b"",
    }
    return Request(scope)


@pytest.fixture
def counted(monkeypatch):
    """Install settings and count each simulated Supabase round trip."""
    settings = Settings(
        _env_file=None,
        environment="development",
        auth_session_secret=AUTH_SECRET,
        auth_session_cache_ttl_seconds=30,
    )
    monkeypatch.setattr(settings_module, "_settings_override", settings)
    settings_module.get_settings.cache_clear()
    session_cache.clear()

    calls: list[str] = []

    async def _session_probe(session_id, *, user_id=""):
        calls.append("auth_sessions")
        return True

    async def _profile_probe(user_id):
        calls.append("profiles")
        return True

    monkeypatch.setattr(auth_deps, "is_auth_session_active", _session_probe)
    monkeypatch.setattr(auth_deps, "_is_custom_session_user_active", _profile_probe)

    yield calls

    session_cache.clear()
    settings_module.get_settings.cache_clear()
    reload_settings()


@pytest.mark.asyncio
async def test_two_resolvers_on_one_request_cost_one_lookup(counted) -> None:
    """The middleware and the route dependency must share one resolution."""
    request = _request(_token())

    first = await auth_deps.get_optional_user(request)
    second = await auth_deps.get_optional_user(request)

    assert first is not None
    assert second is first
    assert counted == ["auth_sessions", "profiles"], (
        "resolving twice on one request must not repeat the network calls"
    )


@pytest.mark.asyncio
async def test_subsequent_requests_hit_the_cache(counted) -> None:
    """Within the TTL, later requests cost zero auth round trips."""
    await auth_deps.get_optional_user(_request(_token()))
    assert len(counted) == 2

    counted.clear()
    await auth_deps.get_optional_user(_request(_token()))
    await auth_deps.get_optional_user(_request(_token()))

    assert counted == [], "cached session state must not re-issue lookups"


@pytest.mark.asyncio
async def test_cache_disabled_restores_previous_behaviour(counted, monkeypatch) -> None:
    """TTL of 0 is the documented kill switch, and it must actually work."""
    settings = Settings(
        _env_file=None,
        environment="development",
        auth_session_secret=AUTH_SECRET,
        auth_session_cache_ttl_seconds=0,
    )
    monkeypatch.setattr(settings_module, "_settings_override", settings)
    settings_module.get_settings.cache_clear()
    session_cache.clear()

    await auth_deps.get_optional_user(_request(_token()))
    await auth_deps.get_optional_user(_request(_token()))

    assert len(counted) == 4, "with caching off every request pays for both lookups"


@pytest.mark.asyncio
async def test_revoking_a_session_takes_effect_immediately(counted) -> None:
    """Caching must not delay revocation for revocations we perform ourselves."""
    await auth_deps.get_optional_user(_request(_token()))
    assert session_cache.get(SESSION_ID) is not None

    session_cache.invalidate(SESSION_ID)

    assert session_cache.get(SESSION_ID) is None
    counted.clear()
    await auth_deps.get_optional_user(_request(_token()))
    assert counted == ["auth_sessions", "profiles"], "must re-check after invalidation"


@pytest.mark.asyncio
async def test_account_deletion_invalidates_every_session_of_that_user(
    counted,
) -> None:
    await auth_deps.get_optional_user(_request(_token()))
    session_cache.put(
        "other-session",
        USER_ID,
        session_cache.SessionState(session_active=True, profile_active=True),
    )

    dropped = session_cache.invalidate_user(USER_ID)

    assert dropped == 2
    assert session_cache.get(SESSION_ID) is None
    assert session_cache.get("other-session") is None


@pytest.mark.asyncio
async def test_dead_session_skips_the_profile_lookup(counted, monkeypatch) -> None:
    """No point asking about the profile when the session is already revoked."""

    async def _revoked(session_id, *, user_id=""):
        counted.append("auth_sessions")
        return False

    monkeypatch.setattr(auth_deps, "is_auth_session_active", _revoked)

    user = await auth_deps.get_optional_user(_request(_token()))

    assert user is None
    assert counted == ["auth_sessions"]


class TestSessionCacheBounds:
    def test_entries_expire(self, monkeypatch) -> None:
        settings = Settings(
            _env_file=None,
            environment="development",
            auth_session_cache_ttl_seconds=1,
        )
        monkeypatch.setattr(settings_module, "_settings_override", settings)
        settings_module.get_settings.cache_clear()
        session_cache.clear()

        state = session_cache.SessionState(session_active=True, profile_active=True)
        session_cache.put("s1", "u1", state)
        assert session_cache.get("s1") is not None

        # Expire without sleeping: rewrite the entry with a past deadline.
        with session_cache._lock:
            _, user_id, cached = session_cache._entries["s1"]
            session_cache._entries["s1"] = (0.0, user_id, cached)

        assert session_cache.get("s1") is None
        session_cache.clear()
        settings_module.get_settings.cache_clear()
        reload_settings()

    def test_size_is_capped(self, monkeypatch) -> None:
        settings = Settings(
            _env_file=None,
            environment="development",
            auth_session_cache_ttl_seconds=300,
        )
        monkeypatch.setattr(settings_module, "_settings_override", settings)
        settings_module.get_settings.cache_clear()
        session_cache.clear()

        state = session_cache.SessionState(session_active=True, profile_active=True)
        for index in range(session_cache._MAX_ENTRIES + 50):
            session_cache.put(f"s{index}", f"u{index}", state)

        assert session_cache.size() <= session_cache._MAX_ENTRIES

        session_cache.clear()
        settings_module.get_settings.cache_clear()
        reload_settings()
