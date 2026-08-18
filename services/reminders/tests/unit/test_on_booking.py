"""Consuming `bookings.booking.*` — the confirmation, and the cancel that keeps it honest.

See `Scheduler.on_booking`'s own docstring for why this is the event-only fast path with no
catch-up (unlike `on_visit`), and why `service_id` carries `booking_id` in the schedule key.
"""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core import adaptive, engagement
from app.core.scheduling import Scheduler
from app.core.stores import ScheduleStore

NOW = 1_800_000_000


def run(c):
    return asyncio.run(c)


@pytest.fixture
def sch():
    store = MemoryDataStore()
    return Scheduler(store=store, cfg=adaptive.AdaptiveConfig(), eng_cfg=engagement.EngagementConfig(),
                     booking_confirm_delay_seconds=120), store


def booking_event(**over):
    e = {"tenant": "t1", "subject_ref": "sub_a", "booking_id": "bkg_1", "kind": "created",
         "starts_at": 1786860000, "branch_id": "b1"}
    e.update(over)
    return e


def test_a_created_booking_schedules_one_confirmation(sch):
    scheduler, store = sch
    outcome = run(scheduler.on_booking(booking_event(), now=NOW))
    assert len(outcome.scheduled) == 1

    rows, _ = run(store.find("schedules", {"tenant": "t1"}, limit=10))
    assert len(rows) == 1
    row = rows[0]
    assert row["kind"] == "booking_confirmation"
    assert row["service_id"] == "bkg_1", "the booking id must be the key's uniqueness, not a real service"
    assert row["due_at"] == NOW + 120
    assert row["appt_time"], "the appointment time must be phrased at scheduling time, not left blank"


def test_two_different_bookings_for_the_same_customer_do_not_collide(sch):
    scheduler, store = sch
    run(scheduler.on_booking(booking_event(booking_id="bkg_1", starts_at=1786860000), now=NOW))
    run(scheduler.on_booking(booking_event(booking_id="bkg_2", starts_at=1786946400), now=NOW))

    rows, _ = run(store.find("schedules", {"tenant": "t1"}, limit=10))
    assert len(rows) == 2, "the second booking's confirmation must not overwrite the first's"


def test_a_cancelled_booking_drops_its_pending_confirmation(sch):
    scheduler, store = sch
    run(scheduler.on_booking(booking_event(kind="created"), now=NOW))
    outcome = run(scheduler.on_booking(booking_event(kind="cancelled"), now=NOW + 10))

    assert outcome.cancelled == 1
    rows, _ = run(store.find("schedules", {"tenant": "t1"}, limit=10))
    assert rows[0]["state"] == "cancelled"


def test_attended_and_no_show_also_drop_a_pending_confirmation(sch):
    for kind in ("attended", "no_show"):
        scheduler, store = sch
        run(scheduler.on_booking(booking_event(kind="created"), now=NOW))
        outcome = run(scheduler.on_booking(booking_event(kind=kind), now=NOW + 10))
        assert outcome.cancelled == 1, kind


def test_a_reschedule_moves_the_appointment_time_shown(sch):
    scheduler, store = sch
    run(scheduler.on_booking(booking_event(kind="created", starts_at=1786860000), now=NOW))
    run(scheduler.on_booking(booking_event(kind="rescheduled", starts_at=1786946400), now=NOW + 5))

    rows, _ = run(store.find("schedules", {"tenant": "t1"}, limit=10))
    assert len(rows) == 1, "a reschedule replaces the same row, keyed by booking id"
    assert rows[0]["due_at"] == NOW + 5 + 120


def test_missing_identity_fields_refuse_rather_than_schedule_blank(sch):
    scheduler, store = sch
    outcome = run(scheduler.on_booking(booking_event(booking_id=""), now=NOW))
    assert outcome.scheduled == []
    rows, _ = run(store.find("schedules", {"tenant": "t1"}, limit=10))
    assert rows == []
