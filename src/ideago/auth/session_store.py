"""Backend-managed custom auth session storage."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import httpx

from ideago.config.settings import get_settings
from ideago.observability.log_config import get_logger

logger = get_logger(__name__)

_session_http_client: httpx.AsyncClient | None = None
_memory_sessions: dict[str, dict[str, str | None]] = {}


def _is_configured() -> bool:
    settings = get_settings()
    return bool(settings.supabase_url and settings.supabase_service_role_key)


def _headers() -> dict[str, str]:
    settings = get_settings()
    return {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Content-Type": "application/json",
    }


def _base_url() -> str:
    return f"{get_settings().supabase_url}/rest/v1/auth_sessions"


def _get_client() -> httpx.AsyncClient:
    global _session_http_client
    if _session_http_client is None:
        _session_http_client = httpx.AsyncClient(
            timeout=10.0,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
    return _session_http_client


async def close_auth_session_client() -> None:
    global _session_http_client
    if _session_http_client is not None:
        await _session_http_client.aclose()
        _session_http_client = None
    _memory_sessions.clear()


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def create_auth_session(user_id: str, *, provider: str = "linuxdo") -> str:
    session_id = uuid.uuid4().hex
    if not _is_configured():
        _memory_sessions[session_id] = {
            "session_id": session_id,
            "user_id": user_id,
            "provider": provider,
            "created_at": _utcnow_iso(),
            "revoked_at": None,
        }
        return session_id

    resp = await _get_client().post(
        _base_url(),
        headers={**_headers(), "Prefer": "return=minimal"},
        json={
            "session_id": session_id,
            "user_id": user_id,
            "provider": provider,
        },
    )
    if resp.status_code not in {200, 201, 204}:
        logger.warning(
            "create_auth_session failed: {} {}",
            resp.status_code,
            resp.text[:200],
        )
        raise RuntimeError("create_auth_session_failed")
    return session_id


async def get_auth_session(session_id: str) -> dict[str, str | None] | None:
    if not session_id:
        return None
    if not _is_configured():
        return _memory_sessions.get(session_id)

    try:
        resp = await _get_client().get(
            _base_url(),
            headers={**_headers(), "Accept": "application/json"},
            params={
                "session_id": f"eq.{session_id}",
                "select": "session_id,user_id,provider,created_at,revoked_at",
                "limit": "1",
            },
        )
        if resp.status_code != 200:
            logger.warning(
                "get_auth_session failed: {} {}",
                resp.status_code,
                resp.text[:200],
            )
            return None
        rows = resp.json()
        if isinstance(rows, list) and rows:
            row = rows[0]
            if isinstance(row, dict):
                return {
                    "session_id": str(row.get("session_id") or ""),
                    "user_id": str(row.get("user_id") or ""),
                    "provider": str(row.get("provider") or ""),
                    "created_at": str(row.get("created_at") or ""),
                    "revoked_at": (
                        str(row.get("revoked_at")) if row.get("revoked_at") else None
                    ),
                }
    except Exception:
        logger.opt(exception=True).warning("get_auth_session error")
    return None


async def is_auth_session_active(session_id: str, *, user_id: str = "") -> bool:
    session = await get_auth_session(session_id)
    if session is None:
        return False
    if user_id and str(session.get("user_id") or "") != user_id:
        return False
    return not bool(session.get("revoked_at"))


async def revoke_auth_session(session_id: str) -> bool:
    if not session_id:
        return False
    if not _is_configured():
        session = _memory_sessions.get(session_id)
        if session is None:
            return False
        session["revoked_at"] = _utcnow_iso()
        return True

    try:
        resp = await _get_client().patch(
            _base_url(),
            headers={**_headers(), "Prefer": "return=minimal"},
            params={"session_id": f"eq.{session_id}", "revoked_at": "is.null"},
            json={"revoked_at": _utcnow_iso()},
        )
        return resp.status_code in {200, 204}
    except Exception:
        logger.opt(exception=True).warning("revoke_auth_session error")
        return False
