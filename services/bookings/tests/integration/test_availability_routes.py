"""`/internal/availability/*` — the first real caller of `app/core/availability.py`.

Stage 2 has no store yet (docs/خطة-تنفيذ-الحجوزات.md §2/§3): the schedule and busy intervals
arrive in the request body rather than being read from a booking store. What this proves is the
BOUNDARY — the internal-token gate, the JSON shape converting cleanly into the pure layer's
dataclasses, and that a bad duration is refused by Pydantic before the derivation ever sees it.
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

TOKEN = "t" * 40


def _make_app(**env_over) -> TestClient:
    from app.config import get_settings

    env = {
        "ENV": "test",
        "INTERNAL_SERVICE_TOKEN": TOKEN,
        "PII_SALT": "s" * 32,
    }
    env.update(env_over)
    os.environ.update(env)
    get_settings.cache_clear()
    from app.main import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


@pytest.fixture(scope="module")
def env_guard():
    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)
    from app.config import get_settings
    get_settings.cache_clear()


SUNDAY_9_TO_13 = {"weekly": {"6": [{"start_minute": 540, "end_minute": 780}]}}


def test_no_token_is_refused(env_guard):
    client = _make_app()
    r = client.post("/internal/availability/check", json={
        "schedule": SUNDAY_9_TO_13, "duration_minutes": 30,
        "window_start": 1786000000, "window_end": 1786100000})
    assert r.status_code == 401


def test_a_real_window_returns_real_slots(env_guard):
    client = _make_app()
    # 2026-08-16 09:00 Riyadh and the next 4 hours, epoch seconds.
    start = 1786860000
    r = client.post("/internal/availability/check",
                    headers={"X-Internal-Token": TOKEN},
                    json={"schedule": SUNDAY_9_TO_13, "duration_minutes": 30,
                          "window_start": start, "window_end": start + 4 * 3600})
    assert r.status_code == 200
    slots = r.json()["slots"]
    assert len(slots) > 0
    assert slots[0]["starts_at"] == start


def test_zero_duration_is_refused_at_the_boundary_not_the_derivation(env_guard):
    """`Field(gt=0)` on the request model refuses this as 422 before `free_slots` is ever
    called — the boundary enforces "refuses rather than guesses" one layer earlier."""
    client = _make_app()
    r = client.post("/internal/availability/check",
                    headers={"X-Internal-Token": TOKEN},
                    json={"schedule": SUNDAY_9_TO_13, "duration_minutes": 0,
                          "window_start": 1786860000, "window_end": 1786960800})
    assert r.status_code == 422


def test_nearest_returns_null_when_nothing_is_free(env_guard):
    client = _make_app()
    r = client.post("/internal/availability/nearest",
                    headers={"X-Internal-Token": TOKEN},
                    json={"schedule": {"weekly": {}}, "duration_minutes": 30,
                          "after": 1786860000, "search_days": 2})
    assert r.status_code == 200
    assert r.json()["slot"] is None


def test_nearest_finds_the_real_next_opening(env_guard):
    client = _make_app()
    start = 1786860000  # 2026-08-16 09:00 Riyadh
    r = client.post("/internal/availability/nearest",
                    headers={"X-Internal-Token": TOKEN},
                    json={"schedule": SUNDAY_9_TO_13, "duration_minutes": 30, "after": start})
    assert r.status_code == 200
    assert r.json()["slot"]["starts_at"] == start


def test_an_exception_day_closes_what_the_weekly_schedule_would_open():
    from app.api.internal import ScheduleIn
    from app.core.availability import free_slots

    schedule = {"weekly": SUNDAY_9_TO_13["weekly"],
               "exceptions": {"2026-08-16": {"closed": True, "windows": []}}}
    slots = free_slots(ScheduleIn(**schedule).to_schedule(), [],
                       duration_minutes=30, window_start=1786860000, window_end=1786960800)
    assert slots == []
