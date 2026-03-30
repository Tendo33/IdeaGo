"""In-process runtime state containers for report execution."""

from __future__ import annotations

import asyncio
import threading
import time

from ideago.pipeline.events import EventType, PipelineEvent

_TERMINAL_EVENTS = {EventType.REPORT_READY, EventType.ERROR, EventType.CANCELLED}


class ReportRunState:
    """In-memory runtime state for one report pipeline run."""

    def __init__(self, max_history: int = 200) -> None:
        self.subscribers: set[asyncio.Queue[PipelineEvent]] = set()
        self.history: list[PipelineEvent] = []
        self.is_terminal = False
        self.updated_at = time.monotonic()
        self._max_history = max_history

    async def publish(self, event: PipelineEvent) -> None:
        self.history.append(event)
        if len(self.history) > self._max_history:
            self.history.pop(0)
        self.updated_at = time.monotonic()
        if event.type in _TERMINAL_EVENTS:
            self.is_terminal = True

        for queue in list(self.subscribers):
            await queue.put(event)

    def subscribe(self) -> asyncio.Queue[PipelineEvent]:
        queue: asyncio.Queue[PipelineEvent] = asyncio.Queue()
        self.subscribers.add(queue)
        self.updated_at = time.monotonic()
        return queue

    def unsubscribe(self, queue: asyncio.Queue[PipelineEvent]) -> None:
        self.subscribers.discard(queue)
        self.updated_at = time.monotonic()

    def history_snapshot(self) -> list[PipelineEvent]:
        return list(self.history)


class ReportRunRegistry:
    def __init__(self, *, ttl_seconds: int, lock: threading.RLock) -> None:
        self._ttl_seconds = ttl_seconds
        self._lock = lock
        self._runs: dict[str, ReportRunState] = {}

    @property
    def runs(self) -> dict[str, ReportRunState]:
        return self._runs

    def cleanup_stale(self) -> None:
        now = time.monotonic()
        stale_ids = [
            report_id
            for report_id, run in self._runs.items()
            if run.is_terminal
            and not run.subscribers
            and now - run.updated_at > self._ttl_seconds
        ]
        for report_id in stale_ids:
            self._runs.pop(report_id, None)

    def get_or_create(self, report_id: str) -> ReportRunState:
        with self._lock:
            self.cleanup_stale()
            run = self._runs.get(report_id)
            if run is None:
                run = ReportRunState()
                self._runs[report_id] = run
            return run

    def get(self, report_id: str) -> ReportRunState | None:
        with self._lock:
            return self._runs.get(report_id)

    def clear(self) -> None:
        with self._lock:
            self._runs.clear()


class ProcessingDedupRegistry:
    def __init__(self, lock: threading.RLock) -> None:
        self._lock = lock
        self._reservations: dict[str, str] = {}

    @property
    def reservations(self) -> dict[str, str]:
        return self._reservations

    def reserve(self, key: str, report_id: str) -> str | None:
        with self._lock:
            existing_report_id = self._reservations.get(key)
            if existing_report_id is not None:
                return existing_report_id
            self._reservations[key] = report_id
            return None

    def assign(self, key: str, report_id: str) -> None:
        with self._lock:
            self._reservations[key] = report_id

    def release_report(self, report_id: str) -> None:
        with self._lock:
            keys_to_remove = [
                key for key, value in self._reservations.items() if value == report_id
            ]
            for key in keys_to_remove:
                self._reservations.pop(key, None)

    def has_report_id(self, report_id: str) -> bool:
        with self._lock:
            return report_id in self._reservations.values()

    def snapshot(self) -> dict[str, str]:
        with self._lock:
            return dict(self._reservations)

    def clear(self) -> None:
        with self._lock:
            self._reservations.clear()


class PipelineTaskRegistry:
    def __init__(self, lock: threading.RLock) -> None:
        self._lock = lock
        self._tasks: dict[str, asyncio.Task[None]] = {}

    @property
    def tasks(self) -> dict[str, asyncio.Task[None]]:
        return self._tasks

    def register(self, report_id: str, task: asyncio.Task[None]) -> None:
        with self._lock:
            self._tasks[report_id] = task

    def remove(self, report_id: str) -> asyncio.Task[None] | None:
        with self._lock:
            return self._tasks.pop(report_id, None)

    def get(self, report_id: str) -> asyncio.Task[None] | None:
        with self._lock:
            return self._tasks.get(report_id)

    def snapshot(self) -> list[asyncio.Task[None]]:
        with self._lock:
            return list(self._tasks.values())

    def clear(self) -> None:
        with self._lock:
            self._tasks.clear()
