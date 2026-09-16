"""`core/server_load.py::is_idle` — the threshold arithmetic and the unsupported-platform
fallback, without depending on this test runner's own real CPU load (flaky by nature)."""
from __future__ import annotations

from app.core import server_load


def test_idle_when_load_is_well_under_the_threshold(monkeypatch):
    monkeypatch.setattr(server_load.os, "getloadavg", lambda: (1.0, 1.0, 1.0), raising=False)
    monkeypatch.setattr(server_load.os, "cpu_count", lambda: 4)
    assert server_load.is_idle(0.7) is True


def test_busy_when_load_crosses_the_threshold(monkeypatch):
    monkeypatch.setattr(server_load.os, "getloadavg", lambda: (3.5, 3.0, 2.5), raising=False)
    monkeypatch.setattr(server_load.os, "cpu_count", lambda: 4)
    assert server_load.is_idle(0.7) is False


def test_exactly_at_the_threshold_counts_as_idle(monkeypatch):
    monkeypatch.setattr(server_load.os, "getloadavg", lambda: (2.8, 2.8, 2.8), raising=False)
    monkeypatch.setattr(server_load.os, "cpu_count", lambda: 4)
    assert server_load.is_idle(0.7) is True


def test_unsupported_platform_defaults_to_idle(monkeypatch):
    def _boom():
        raise AttributeError("getloadavg not available on this platform")
    monkeypatch.setattr(server_load.os, "getloadavg", _boom, raising=False)
    assert server_load.is_idle(0.7) is True
