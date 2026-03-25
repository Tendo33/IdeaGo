"""Lightweight in-process metrics collection.

Tracks request counts, latencies, and error rates without external
dependencies. Intended for the ``/api/v1/metrics`` admin endpoint.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class _Metrics:
    request_count: int = 0
    error_count: int = 0
    status_codes: dict[int, int] = field(default_factory=lambda: defaultdict(int))
    path_counts: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    latency_sum_ms: float = 0.0
    latency_max_ms: float = 0.0
    started_at: float = field(default_factory=time.monotonic)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record(self, path: str, status_code: int, latency_ms: float) -> None:
        with self._lock:
            self.request_count += 1
            if status_code >= 400:
                self.error_count += 1
            self.status_codes[status_code] += 1
            self.path_counts[path] += 1
            self.latency_sum_ms += latency_ms
            if latency_ms > self.latency_max_ms:
                self.latency_max_ms = latency_ms

    def snapshot(self) -> dict:
        with self._lock:
            avg = (
                (self.latency_sum_ms / self.request_count) if self.request_count else 0
            )
            uptime = time.monotonic() - self.started_at
            return {
                "uptime_seconds": round(uptime, 1),
                "request_count": self.request_count,
                "error_count": self.error_count,
                "avg_latency_ms": round(avg, 2),
                "max_latency_ms": round(self.latency_max_ms, 2),
                "status_codes": dict(self.status_codes),
                "top_paths": dict(
                    sorted(
                        self.path_counts.items(), key=lambda kv: kv[1], reverse=True
                    )[:20]
                ),
            }

    def reset(self) -> None:
        with self._lock:
            self.request_count = 0
            self.error_count = 0
            self.status_codes.clear()
            self.path_counts.clear()
            self.latency_sum_ms = 0.0
            self.latency_max_ms = 0.0
            self.started_at = time.monotonic()


metrics = _Metrics()
