"""Short-lived cache for custom-session auth state.

Every authenticated request from a LinuxDo (custom-session) user used to cost
two PostgREST round trips: one to check the session row is not revoked, one to
check the profile is not deleted or pending deletion. The rate-limit middleware
resolved the user independently of the route dependency, so both ran twice —
four network calls before the handler even started.

Caching that state for a few seconds removes almost all of them.

The trade-off is explicit: a revocation becomes visible after at most
``auth_session_cache_ttl_seconds``. To keep that window at zero in practice,
every code path that revokes access invalidates the cache directly — logout,
account deletion, and deletion-pending marking. The TTL only covers revocations
that happen outside this process (another replica, or a direct DB edit).

Set ``AUTH_SESSION_CACHE_TTL_SECONDS=0`` to disable caching entirely and return
to the previous behaviour without a code change.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from ideago.config.settings import get_settings

# Bounds memory on a long-running process. Entries are short-lived anyway; this
# only matters under a burst of distinct sessions.
_MAX_ENTRIES = 1000


@dataclass(frozen=True)
class SessionState:
    """Resolved liveness of a custom session and its owning profile."""

    session_active: bool
    profile_active: bool

    @property
    def is_usable(self) -> bool:
        return self.session_active and self.profile_active


_lock = threading.RLock()
# session_id -> (expires_at_monotonic, user_id, state)
_entries: dict[str, tuple[float, str, SessionState]] = {}


def _ttl_seconds() -> float:
    return float(getattr(get_settings(), "auth_session_cache_ttl_seconds", 0) or 0)


def get(session_id: str) -> SessionState | None:
    """Return cached state for a session, or None when absent/expired/disabled."""
    if not session_id or _ttl_seconds() <= 0:
        return None
    now = time.monotonic()
    with _lock:
        entry = _entries.get(session_id)
        if entry is None:
            return None
        expires_at, _user_id, state = entry
        if now >= expires_at:
            _entries.pop(session_id, None)
            return None
        return state


def put(session_id: str, user_id: str, state: SessionState) -> None:
    """Cache resolved session state. No-op when caching is disabled."""
    ttl = _ttl_seconds()
    if not session_id or ttl <= 0:
        return
    with _lock:
        if len(_entries) >= _MAX_ENTRIES:
            _evict_expired_locked()
            if len(_entries) >= _MAX_ENTRIES:
                # Still full: drop the entry closest to expiry.
                oldest = min(_entries.items(), key=lambda kv: kv[1][0])[0]
                _entries.pop(oldest, None)
        _entries[session_id] = (time.monotonic() + ttl, user_id, state)


def invalidate(session_id: str) -> None:
    """Drop one session immediately (logout, explicit revoke)."""
    if not session_id:
        return
    with _lock:
        _entries.pop(session_id, None)


def invalidate_user(user_id: str) -> int:
    """Drop every session for a user (account deletion, deletion-pending)."""
    if not user_id:
        return 0
    with _lock:
        stale = [sid for sid, (_, uid, _) in _entries.items() if uid == user_id]
        for session_id in stale:
            _entries.pop(session_id, None)
        return len(stale)


def _evict_expired_locked() -> int:
    now = time.monotonic()
    expired = [sid for sid, (expires_at, _, _) in _entries.items() if now >= expires_at]
    for session_id in expired:
        _entries.pop(session_id, None)
    return len(expired)


def evict_expired() -> int:
    """Drop expired entries. Called from the periodic maintenance task."""
    with _lock:
        return _evict_expired_locked()


def clear() -> None:
    """Drop everything (shutdown, tests)."""
    with _lock:
        _entries.clear()


def size() -> int:
    with _lock:
        return len(_entries)
