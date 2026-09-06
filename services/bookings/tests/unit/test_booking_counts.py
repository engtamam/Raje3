"""`counts_between` — the month/year view's own query: counts only, never a hydrated `Booking`,
and correct across a range spanning multiple months (docs/خطة-تصميم-تقويم-الحجوزات.md §1).
"""
from __future__ import annotations

import asyncio

from app.adapters.datastore.memory import MemoryDataStore
from app.core.models import Booking
from app.core.stores import BookingStore


def _booking(**over) -> Booking:
    base = dict(id="bkg_1", tenant="t1", branch_id="b1", operator_id="op1", customer_id="c1",
               service_ids=("svc1",), starts_at=1786860000, duration_minutes=30,
               created=1786860000, updated=1786860000)
    base.update(over)
    return Booking(**base)


def test_counts_are_correct_across_a_multi_month_range():
    async def run():
        store = MemoryDataStore()
        bookings = BookingStore(store)
        # 2026-08-16, three bookings same day
        for i in range(3):
            await bookings.save(_booking(id=f"bkg_aug_{i}", starts_at=1786860000))
        # 2026-09-15, one booking, a month later
        await bookings.save(_booking(id="bkg_sep_1", starts_at=1786860000 + 30 * 86400))
        # 2026-10-01, one booking, two months later — outside the queried range below
        await bookings.save(_booking(id="bkg_oct_1", starts_at=1786860000 + 46 * 86400))
        return await bookings.counts_between(
            "t1", "b1", start_bucket="2026-08-01", end_bucket="2026-09-30")

    counts = asyncio.run(run())
    assert counts == {"2026-08-16": 3, "2026-09-15": 1}


def test_a_second_branch_and_a_second_tenant_are_never_counted():
    async def run():
        store = MemoryDataStore()
        bookings = BookingStore(store)
        await bookings.save(_booking(id="bkg_1", tenant="t1", branch_id="b1"))
        await bookings.save(_booking(id="bkg_2", tenant="t1", branch_id="b2"))
        await bookings.save(_booking(id="bkg_3", tenant="t2", branch_id="b1"))
        return await bookings.counts_between(
            "t1", "b1", start_bucket="2026-01-01", end_bucket="2026-12-31")

    counts = asyncio.run(run())
    assert counts == {"2026-08-16": 1}


def test_a_cancelled_or_zero_day_still_only_counts_rows_that_exist():
    async def run():
        store = MemoryDataStore()
        bookings = BookingStore(store)
        return await bookings.counts_between(
            "t1", "b1", start_bucket="2026-01-01", end_bucket="2026-12-31")

    counts = asyncio.run(run())
    assert counts == {}


def test_counts_hold_across_more_than_one_page_of_the_underlying_index():
    """`counts_between` itself asks `find()` for pages of 500 — this proves it PAGES rather than
    trusting the first one back, with a row count genuinely past that (550), not merely past
    `find()`'s own unrelated default of 100. A weaker version of this test (250 rows) passed
    trivially in ONE call to `find()` regardless of whether the pagination loop was even
    correct — verified directly by counting real `find()` calls before writing this version."""
    async def run():
        store = MemoryDataStore()
        bookings = BookingStore(store)
        calls = 0
        orig_find = store.find

        async def counting_find(*a, **kw):
            nonlocal calls
            calls += 1
            return await orig_find(*a, **kw)

        store.find = counting_find
        # 550 bookings, spread across 550 different days — past `counts_between`'s own
        # `limit=500`, so a correct implementation must call `find()` at least twice.
        for i in range(550):
            await bookings.save(_booking(id=f"bkg_{i}", starts_at=1786860000 + i * 86400))
        counts = await bookings.counts_between(
            "t1", "b1", start_bucket="2000-01-01", end_bucket="2100-01-01")
        return counts, calls

    counts, calls = asyncio.run(run())
    assert len(counts) == 550
    assert all(v == 1 for v in counts.values())
    assert calls >= 2
