"""Benchmark auth token subject extraction and auth fallback paths.

Usage:
  uv run python scripts/benchmark_extract_token_subject.py --iterations 200
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from dataclasses import dataclass
from typing import Any
from unittest.mock import patch

import jwt

from ideago.auth import dependencies as auth_deps


@dataclass
class ScenarioResult:
    name: str
    iterations: int
    avg_ms: float
    median_ms: float
    p95_ms: float
    outcome: str


def _percentile(samples: list[float], percentile: float) -> float:
    if not samples:
        return 0.0
    ordered = sorted(samples)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * percentile))))
    return ordered[index]


def _run_sync_benchmark(name: str, iterations: int, fn) -> ScenarioResult:
    samples: list[float] = []
    outcome = ""
    for _ in range(iterations):
        started = time.perf_counter()
        value = fn()
        samples.append((time.perf_counter() - started) * 1000)
        outcome = str(value)
    return ScenarioResult(
        name=name,
        iterations=iterations,
        avg_ms=statistics.fmean(samples),
        median_ms=statistics.median(samples),
        p95_ms=_percentile(samples, 0.95),
        outcome=outcome,
    )


async def _run_async_benchmark(name: str, iterations: int, fn) -> ScenarioResult:
    samples: list[float] = []
    outcome = ""
    for _ in range(iterations):
        started = time.perf_counter()
        value = await fn()
        samples.append((time.perf_counter() - started) * 1000)
        outcome = str(value)
    return ScenarioResult(
        name=name,
        iterations=iterations,
        avg_ms=statistics.fmean(samples),
        median_ms=statistics.median(samples),
        p95_ms=_percentile(samples, 0.95),
        outcome=outcome,
    )


def _build_settings(**overrides: Any) -> Any:
    defaults = {
        "auth_session_secret": "benchmark-secret-benchmark-secret-1234",
        "supabase_url": "https://example.supabase.co",
        "supabase_jwt_audience": "authenticated",
        "get_supabase_jwt_issuer": lambda self: "https://example.supabase.co/auth/v1",
        "supabase_anon_key": "anon-key",
        "supabase_service_role_key": "service-role",
    }
    defaults.update(overrides)
    return type("Settings", (), defaults)()


def _build_ideago_token(secret: str) -> str:
    return jwt.encode(
        {"sub": "user-123", "aud": "ideago-auth"},
        secret,
        algorithm="HS256",
    )


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=200)
    args = parser.parse_args()

    ideago_settings = _build_settings()
    ideago_token = _build_ideago_token(ideago_settings.auth_session_secret)

    async def verify_supabase_hit(
        _token: str,
    ) -> auth_deps._SupabaseJwtVerificationResult:
        return auth_deps._SupabaseJwtVerificationResult({"sub": "supa-user"}, False)

    async def verify_supabase_invalid(
        _token: str,
    ) -> auth_deps._SupabaseJwtVerificationResult:
        return auth_deps._SupabaseJwtVerificationResult(None, False)

    async def verify_supabase_remote_fallback(
        _token: str,
    ) -> auth_deps._SupabaseJwtVerificationResult:
        return auth_deps._SupabaseJwtVerificationResult(None, True)

    async def remote_user_lookup(_token: str) -> dict[str, str]:
        await asyncio.sleep(0)
        return {"id": "remote-user", "email": "remote@example.com"}

    with patch("ideago.auth.dependencies.get_settings", return_value=ideago_settings):
        ideago_result = _run_sync_benchmark(
            "extract_token_subject.ideago_jwt",
            args.iterations,
            lambda: auth_deps.extract_token_subject(ideago_token),
        )

    with (
        patch(
            "ideago.auth.dependencies.get_settings",
            return_value=_build_settings(auth_session_secret=""),
        ),
        patch("ideago.auth.dependencies._verify_supabase_jwt", new=verify_supabase_hit),
    ):
        supabase_hit = _run_sync_benchmark(
            "extract_token_subject.supabase_jwks_hit",
            args.iterations,
            lambda: auth_deps.extract_token_subject("supabase-token"),
        )

    with (
        patch(
            "ideago.auth.dependencies.get_settings",
            return_value=_build_settings(auth_session_secret=""),
        ),
        patch(
            "ideago.auth.dependencies._verify_supabase_jwt", new=verify_supabase_invalid
        ),
    ):
        invalid_token = _run_sync_benchmark(
            "extract_token_subject.invalid_token",
            args.iterations,
            lambda: auth_deps.extract_token_subject("invalid-token"),
        )

    with (
        patch(
            "ideago.auth.dependencies.get_settings",
            return_value=_build_settings(auth_session_secret=""),
        ),
        patch(
            "ideago.auth.dependencies._verify_supabase_jwt",
            new=verify_supabase_remote_fallback,
        ),
        patch(
            "ideago.auth.dependencies._verify_supabase_token_remote",
            new=remote_user_lookup,
        ),
    ):
        remote_fallback = await _run_async_benchmark(
            "_authenticate_token.remote_fallback",
            args.iterations,
            lambda: auth_deps._authenticate_token("remote-token"),
        )

    summary = {
        "iterations": args.iterations,
        "scenarios": [
            ideago_result.__dict__,
            supabase_hit.__dict__,
            invalid_token.__dict__,
            remote_fallback.__dict__,
        ],
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
