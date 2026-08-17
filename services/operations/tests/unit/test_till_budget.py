"""The ceiling that makes «read the whole customer book» impossible without touching the counter.

WHAT THIS LOCKS DOWN. `GET /till/customer?phone=…` returns a name, a visit count, a points balance
and the rewards the customer can take. Right at a counter; also an extraction interface if you
iterate the phone number space. The per-window rate limit bounds a burst and nothing else — a till
credential lives for years in a vendor's hands, and patience defeats a per-minute budget.

So the allowance is a RATIO to work actually done. These assert the two ends of it: a busy counter
never meets the ceiling, and a credential that reads far more than it serves does.
"""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.till_budget import (FACTOR, FLOOR, LookupRefused, allowance, count_lookup,
                                  note_visit)

T = "shop"
CRED = "svc_till_abc"
DAY = 1_780_000_000        # a fixed instant, so the day bucket never depends on when tests run


def run(c):
    return asyncio.run(c)


def test_the_quiet_morning_is_not_broken_by_the_control():
    """The first customer is looked up before any visit exists — a floor, or the product breaks."""
    store = MemoryDataStore()
    for _ in range(FLOOR):
        run(count_lookup(store, T, CRED, now=DAY))

    with pytest.raises(LookupRefused):
        run(count_lookup(store, T, CRED, now=DAY))


def test_work_buys_lookups():
    store = MemoryDataStore()
    run(note_visit(store, T, CRED, now=DAY))
    assert allowance(1) == FLOOR + FACTOR

    for _ in range(FLOOR + FACTOR):
        run(count_lookup(store, T, CRED, now=DAY))
    with pytest.raises(LookupRefused):
        run(count_lookup(store, T, CRED, now=DAY))


def test_a_busy_counter_never_meets_the_ceiling():
    """Forty visits and eighty lookups — two lookups per customer served, twice a real counter."""
    store = MemoryDataStore()
    for _ in range(40):
        run(note_visit(store, T, CRED, now=DAY))
    for _ in range(80):
        run(count_lookup(store, T, CRED, now=DAY))       # must not raise


def test_extraction_is_refused_long_before_the_book_is_read():
    """The whole point: a shop with thousands of customers cannot be walked in a day."""
    store = MemoryDataStore()
    run(note_visit(store, T, CRED, now=DAY))

    reads = 0
    with pytest.raises(LookupRefused):
        for _ in range(5_000):
            run(count_lookup(store, T, CRED, now=DAY))
            reads += 1
    assert reads < 100, "an extractor got further than a counter ever would"


def test_the_counter_resets_with_the_day():
    """Yesterday's usage must not refuse today's first customer."""
    store = MemoryDataStore()
    for _ in range(FLOOR):
        run(count_lookup(store, T, CRED, now=DAY))
    with pytest.raises(LookupRefused):
        run(count_lookup(store, T, CRED, now=DAY))

    run(count_lookup(store, T, CRED, now=DAY + 86_400))   # a new day, a new allowance


def test_two_credentials_do_not_share_a_budget():
    """One vendor holds hundreds of these; one busy shop must not fund another's extraction."""
    store = MemoryDataStore()
    for _ in range(FLOOR):
        run(count_lookup(store, T, CRED, now=DAY))
    run(count_lookup(store, T, "svc_till_other", now=DAY))

    # And a second tenant is separate too — the credential name alone must not be the key.
    run(count_lookup(store, "other-shop", CRED, now=DAY))


def test_an_unreadable_counter_refuses_rather_than_allows():
    """FAIL CLOSED. «Could not read the counter» is not «no counter»."""

    class Broken(MemoryDataStore):
        async def get(self, collection, key):
            raise RuntimeError("store unavailable")

    with pytest.raises(LookupRefused):
        run(count_lookup(Broken(), T, CRED, now=DAY))


def test_the_lookup_allowance_turns_over_at_the_shops_midnight_not_utcs() -> None:
    """و-10, the same defect on a daily key.

    `_day` used `time.gmtime`, so the allowance reset at 03:00 Riyadh. A shop still serving after
    midnight lost its budget mid-shift, and the FLOOR of forty lookups — the morning's grace —
    arrived three hours into the next day's work.
    """
    import calendar
    import datetime as dt

    from app.core.till_budget import _day

    before = calendar.timegm(
        dt.datetime(2026, 8, 31, 20, 0, tzinfo=dt.timezone.utc).utctimetuple())   # 23:00 Riyadh
    after = calendar.timegm(
        dt.datetime(2026, 8, 31, 21, 30, tzinfo=dt.timezone.utc).utctimetuple())  # 00:30 Riyadh

    assert _day(before) == "2026-08-31"
    assert _day(after) == "2026-09-01", (
        "23:00 and 00:30 Riyadh fall in the same allowance day — the counter is keyed on UTC, so "
        "it turns over at 03:00 local instead of at the shop's midnight")
