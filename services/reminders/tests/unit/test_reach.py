"""Unique customers in a rolling 24 hours — the number WhatsApp's ceiling actually counts."""
from __future__ import annotations

import asyncio

from app.adapters.datastore.memory import MemoryDataStore
from app.core.reach import DEFAULT_WINDOW as WINDOW
from app.core.reach import Reach

T = "shop"
NOW = 1_800_000_000


def run(c):
    return asyncio.run(c)


def reach():
    return Reach(MemoryDataStore())


# ── people, not messages ───────────────────────────────────────────────────────────────────────
def test_three_messages_to_one_person_count_as_one():
    """THE WHOLE REASON THIS EXISTS. Counting messages would report the shop closer to its ceiling
    than it is, and we would hold back sends WhatsApp would have accepted — silently."""
    r = reach()
    for _ in range(3):
        run(r.record(T, "sub_a", now=NOW))
    assert run(r.count(T, now=NOW)) == 1


def test_three_people_count_as_three():
    r = reach()
    for who in ("sub_a", "sub_b", "sub_c"):
        run(r.record(T, who, now=NOW))
    assert run(r.count(T, now=NOW)) == 3


def test_a_second_message_to_someone_already_reached_is_free():
    """A confirmation and a follow-up to the same customer use one of the day's allowance."""
    r = reach()
    run(r.record(T, "sub_a", now=NOW))
    assert run(r.would_be_new(T, "sub_a", now=NOW)) is False
    assert run(r.would_be_new(T, "sub_b", now=NOW)) is True


# ── the window rolls ───────────────────────────────────────────────────────────────────────────
def test_someone_reached_23_hours_ago_still_counts():
    r = reach()
    run(r.record(T, "sub_a", now=NOW))
    assert run(r.count(T, now=NOW + 23 * 3600)) == 1


def test_someone_reached_25_hours_ago_does_not():
    r = reach()
    run(r.record(T, "sub_a", now=NOW))
    assert run(r.count(T, now=NOW + 25 * 3600)) == 0
    assert run(r.would_be_new(T, "sub_a", now=NOW + 25 * 3600)) is True


def test_the_window_is_not_a_calendar_day():
    """A midnight reset would let a shop send its whole allowance at 23:30 and again at 00:30 —
    and WhatsApp, measuring the real window, would refuse the second half while our own numbers
    said everything was fine."""
    r = reach()
    run(r.record(T, "sub_a", now=NOW))
    # One second short of the window: still counted, whatever the clock says.
    assert run(r.count(T, now=NOW + WINDOW - 1)) == 1
    assert run(r.count(T, now=NOW + WINDOW)) == 0


def test_one_shop_never_sees_another():
    r = reach()
    run(r.record("a", "sub_x", now=NOW))
    run(r.record("b", "sub_y", now=NOW))
    assert run(r.count("a", now=NOW)) == 1


# ── it does not grow for ever ──────────────────────────────────────────────────────────────────
def test_one_row_per_person_however_many_messages():
    """The question is when we last reached them, never how many times. A row per message would
    grow without bound and answer a question the ceiling does not ask."""
    store = MemoryDataStore()
    r = Reach(store)
    for _ in range(5):
        run(r.record(T, "sub_a", now=NOW))
    assert len(run(store.scan_all("reached_24h", 100))) == 1


def test_pruning_drops_what_has_aged_out_and_keeps_what_has_not():
    store = MemoryDataStore()
    r = Reach(store)
    run(r.record(T, "old", now=NOW))
    run(r.record(T, "new", now=NOW + 23 * 3600))
    assert run(r.prune(now=NOW + 25 * 3600)) == 1
    assert run(r.count(T, now=NOW + 25 * 3600)) == 1
