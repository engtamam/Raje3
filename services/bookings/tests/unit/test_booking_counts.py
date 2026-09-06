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
    """`find()`'s own default page is 100 rows. A busy shop's year is bigger than that — this
    proves `counts_between` pages through every row rather than trusting a single page."""
    async def run():
        store = MemoryDataStore()
        bookings = BookingStore(store)
        # 250 bookings, spread across 250 different days, well over one `find()` page.
        for i in range(250):
            await bookings.save(_booking(id=f"bkg_{i}", starts_at=1786860000 + i * 86400))
        return await bookings.counts_between(
            "t1", "b1", start_bucket="2000-01-01", end_bucket="2100-01-01")

    counts = asyncio.run(run())
    assert len(counts) == 250
    assert all(v == 1 for v in counts.values())
