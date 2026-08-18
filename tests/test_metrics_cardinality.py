"""Metrics cardinality guard.

``path_counts`` was keyed on the raw request path, so every report UUID added
several permanent keys. ``snapshot()`` truncates its *output* to the top 20,
which hid the fact that the underlying dict never stopped growing.
"""

from __future__ import annotations

from ideago.api.http_middleware import _metrics_path
from ideago.observability.metrics import (
    _MAX_TRACKED_PATHS,
    _OVERFLOW_PATH_KEY,
    _Metrics,
)


class _FakeRoute:
    def __init__(self, path_format: str) -> None:
        self.path_format = path_format


class _FakeRequest:
    def __init__(self, scope: dict) -> None:
        self.scope = scope


def test_uses_the_route_template_not_the_concrete_path() -> None:
    request = _FakeRequest({"route": _FakeRoute("/api/v1/reports/{report_id}")})
    assert _metrics_path(request) == "/api/v1/reports/{report_id}"


def test_unmatched_requests_collapse_to_one_key() -> None:
    assert _metrics_path(_FakeRequest({})) == "<unmatched>"
    assert _metrics_path(_FakeRequest({"route": None})) == "<unmatched>"


def test_report_ids_no_longer_create_one_key_each() -> None:
    metrics = _Metrics()
    template = "/api/v1/reports/{report_id}"

    for _ in range(5000):
        metrics.record(template, 200, 1.0)

    assert len(metrics.path_counts) == 1
    assert metrics.path_counts[template] == 5000


def test_key_space_is_capped_even_for_unexpected_paths() -> None:
    """Backstop: if a dynamic path ever reaches record(), memory stays bounded."""
    metrics = _Metrics()

    for index in range(_MAX_TRACKED_PATHS + 250):
        metrics.record(f"/api/v1/reports/{index}", 200, 1.0)

    assert len(metrics.path_counts) <= _MAX_TRACKED_PATHS + 1
    assert metrics.path_counts[_OVERFLOW_PATH_KEY] == 250
    assert metrics.request_count == _MAX_TRACKED_PATHS + 250


def test_known_paths_keep_counting_after_the_cap_is_reached() -> None:
    metrics = _Metrics()
    for index in range(_MAX_TRACKED_PATHS):
        metrics.record(f"/p{index}", 200, 1.0)

    metrics.record("/p0", 200, 1.0)
    metrics.record("/brand-new", 200, 1.0)

    assert metrics.path_counts["/p0"] == 2
    assert metrics.path_counts[_OVERFLOW_PATH_KEY] == 1
