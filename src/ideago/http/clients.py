"""Shared HTTP clients.

Creating an ``httpx.AsyncClient`` per call costs a fresh TLS handshake every
time. Most of the codebase already used module-level clients closed during
lifespan teardown, but several call sites (LinuxDo OAuth, Turnstile, admin
stats, health probes, Stripe's PostgREST calls) still built throwaway clients.

Clients are split by purpose rather than shared as one, because the timeouts
carry real meaning: a health probe must fail fast, a PostgREST write must be
allowed to finish.
"""

from __future__ import annotations

import httpx

_supabase_client: httpx.AsyncClient | None = None
_external_client: httpx.AsyncClient | None = None
_probe_client: httpx.AsyncClient | None = None


def get_supabase_client() -> httpx.AsyncClient:
    """Client for PostgREST / RPC / Supabase auth-admin traffic."""
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = httpx.AsyncClient(
            timeout=10.0,
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
        )
    return _supabase_client


def get_external_client() -> httpx.AsyncClient:
    """Client for third-party providers (LinuxDo OAuth, Turnstile)."""
    global _external_client
    if _external_client is None:
        _external_client = httpx.AsyncClient(
            timeout=10.0,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
    return _external_client


def get_probe_client() -> httpx.AsyncClient:
    """Client for health probes and audit writes — must fail fast."""
    global _probe_client
    if _probe_client is None:
        _probe_client = httpx.AsyncClient(
            timeout=5.0,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )
    return _probe_client


async def close_all_clients() -> None:
    """Close every shared client. Called during application shutdown."""
    global _supabase_client, _external_client, _probe_client
    for client in (_supabase_client, _external_client, _probe_client):
        if client is not None:
            await client.aclose()
    _supabase_client = None
    _external_client = None
    _probe_client = None
