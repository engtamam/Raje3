"""Consuming `operations.order.changed` — WhatsApp Direct Ordering's own six statuses.

See `Scheduler.on_order`'s own docstring for why each status is its own one-shot schedule (never
one mutable slot per order the way a booking's confirmation is), and why there is no retraction
window.
"""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core import adaptive, engagement
from app.core import reasons as T
from app.core.scheduling import Scheduler

NOW = 1_800_000_000


def run(c):
    return asyncio.run(c)


@pytest.fixture
def sch():
    store = MemoryDataStore()
    return Scheduler(store=store, cfg=adaptive.AdaptiveConfig(), eng_cfg=engagement.EngagementConfig()), store


def order_event(**over):
    e = {"tenant": "t1", "subject_ref": "sub_a", "order_id": "ord_abc123def456", "status": "confirmed",
        "branch_id": "b1"}
    e.update(over)
    return e


def test_a_confirmed_order_schedules_immediately_no_delay(sch):
    scheduler, store = sch
    outcome = run(scheduler.on_order(order_event(), now=NOW))
    assert len(outcome.scheduled) == 1

    rows, _ = run(store.find("schedules", {"tenant": "t1"}, limit=10))
    assert len(rows) == 1
    row = rows[0]
    assert row["kind"] == "order_confirmed"
    assert row["service_id"] == "ord_abc123def456", "the order id must be the key's uniqueness"
    assert row["due_at"] == NOW, "no retraction window — an order confirmation sends immediately"
    assert row["template_type"] == T.get("order_confirmed").template_type


def test_the_order_number_is_short_and_never_the_raw_internal_id(sch):
    scheduler, store = sch
    run(scheduler.on_order(order_event(order_id="ord_abc123def456"), now=NOW))
    rows, _ = run(store.find("schedules", {"tenant": "t1"}, limit=10))
    assert rows[0]["order_number"] == "#DEF456"
    assert "ord_" not in rows[0]["order_number"]


@pytest.mark.parametrize("status,kind", [
    ("confirmed", "order_confirmed"),
    ("preparing", "order_preparing"),
    ("ready", "order_ready"),
    ("out_for_delivery", "order_out_for_delivery"),
    ("delivered", "order_delivered"),
    ("cancelled", "order_cancelled"),
])
def test_every_real_status_maps_to_its_own_reason(sch, status, kind):
    scheduler, store = sch
    outcome = run(scheduler.on_order(order_event(status=status), now=NOW))
    assert len(outcome.scheduled) == 1
    rows, _ = run(store.find("schedules", {"tenant": "t1"}, limit=10))
    assert rows[0]["kind"] == kind


def test_each_status_is_its_own_row_not_a_shared_mutable_slot(sch):
    """Unlike a booking's single reschedulable confirmation, an order's statuses are genuinely
    separate messages — a shop must be able to receive "confirmed" AND later "ready" as two
    actual sends, never one overwriting the other."""
    scheduler, store = sch
    run(scheduler.on_order(order_event(status="confirmed"), now=NOW))
    run(scheduler.on_order(order_event(status="ready"), now=NOW + 600))
    rows, _ = run(store.find("schedules", {"tenant": "t1"}, limit=10))
    assert len(rows) == 2


def test_a_redelivered_event_for_the_same_status_upserts_not_duplicates(sch):
    scheduler, store = sch
    run(scheduler.on_order(order_event(status="ready"), now=NOW))
    run(scheduler.on_order(order_event(status="ready"), now=NOW + 1))
    rows, _ = run(store.find("schedules", {"tenant": "t1"}, limit=10))
    assert len(rows) == 1


def test_an_unrecognised_status_refuses_to_guess(sch):
    scheduler, store = sch
    outcome = run(scheduler.on_order(order_event(status="some_future_status"), now=NOW))
    assert outcome.scheduled == []
    rows, _ = run(store.find("schedules", {"tenant": "t1"}, limit=10))
    assert rows == []


def test_missing_identity_fields_refuse_rather_than_schedule_blank(sch):
    scheduler, store = sch
    outcome = run(scheduler.on_order(order_event(order_id=""), now=NOW))
    assert outcome.scheduled == []
    rows, _ = run(store.find("schedules", {"tenant": "t1"}, limit=10))
    assert rows == []


def test_two_different_orders_do_not_collide(sch):
    scheduler, store = sch
    run(scheduler.on_order(order_event(order_id="ord_111111111111", status="confirmed"), now=NOW))
    run(scheduler.on_order(order_event(order_id="ord_222222222222", status="confirmed"), now=NOW))
    rows, _ = run(store.find("schedules", {"tenant": "t1"}, limit=10))
    assert len(rows) == 2
