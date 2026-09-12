"""`BookingStore.no_show_summary` — the rating app's staff-performance report's own no-show half
(operations service merges this in beside visits/ratings, see
services/operations/tests/unit/test_staff_performance.py). Reads `BOOKING_SLOTS`, same derived
index `counts_between` reads beside it.
"""
from __future__ import annotations

import asyncio

from app.core.models import STATUS_ATTENDED, STATUS_BOOKED, STATUS_NO_SHOW, Booking
from app.core.stores import BookingStore


def _booking(**over) -> Booking:
    base = dict(id="bkg_1", tenant="t1", branch_id="b1", operator_id="op1", customer_id="c1",
               service_ids=("svc1",), starts_at=1786860000, duration_minutes=30,
               created=1786860000, updated=1786860000, status=STATUS_BOOKED)
    base.update(over)
    return Booking(**base)


def _run(coro):
    return asyncio.run(coro)


def test_tallies_total_and_no_show_per_operator():
    async def run():
        from app.adapters.datastore.memory import MemoryDataStore
        store = MemoryDataStore()
        bookings = BookingStore(store)
        # op1: two bookings, one a no-show
        await bookings.save(_booking(id="bkg_1", operator_id="op1", status=STATUS_NO_SHOW))
        await bookings.save(_booking(id="bkg_2", operator_id="op1", status=STATUS_ATTENDED,
                                     starts_at=1786860000 + 3600))
        # op2: one booking, attended
        await bookings.save(_booking(id="bkg_3", operator_id="op2", status=STATUS_ATTENDED))
        return await bookings.no_show_summary(
            "t1", start_bucket="2026-01-01", end_bucket="2026-12-31")

    totals = _run(run())
    assert totals["op1"] == {"total": 2, "no_show": 1}
    assert totals["op2"] == {"total": 1, "no_show": 0}


def test_a_booking_with_no_operator_is_excluded():
    async def run():
        from app.adapters.datastore.memory import MemoryDataStore
        store = MemoryDataStore()
        bookings = BookingStore(store)
        await bookings.save(_booking(id="bkg_1", operator_id="", status=STATUS_NO_SHOW))
        return await bookings.no_show_summary(
            "t1", start_bucket="2026-01-01", end_bucket="2026-12-31")

    assert _run(run()) == {}


def test_branch_filter_narrows_to_that_branch_only():
    async def run():
        from app.adapters.datastore.memory import MemoryDataStore
        store = MemoryDataStore()
        bookings = BookingStore(store)
        await bookings.save(_booking(id="bkg_1", branch_id="b1", operator_id="op1",
                                     status=STATUS_NO_SHOW))
        await bookings.save(_booking(id="bkg_2", branch_id="b2", operator_id="op1",
                                     status=STATUS_ATTENDED))
        return await bookings.no_show_summary(
            "t1", start_bucket="2026-01-01", end_bucket="2026-12-31", branch_id="b1")

    totals = _run(run())
    assert totals == {"op1": {"total": 1, "no_show": 1}}


def test_omitting_branch_id_covers_every_branch():
    async def run():
        from app.adapters.datastore.memory import MemoryDataStore
        store = MemoryDataStore()
        bookings = BookingStore(store)
        await bookings.save(_booking(id="bkg_1", branch_id="b1", operator_id="op1",
                                     status=STATUS_NO_SHOW))
        await bookings.save(_booking(id="bkg_2", branch_id="b2", operator_id="op1",
                                     status=STATUS_ATTENDED))
        return await bookings.no_show_summary(
            "t1", start_bucket="2026-01-01", end_bucket="2026-12-31")

    totals = _run(run())
    assert totals == {"op1": {"total": 2, "no_show": 1}}


def test_a_second_tenants_bookings_never_leak_in():
    async def run():
        from app.adapters.datastore.memory import MemoryDataStore
        store = MemoryDataStore()
        bookings = BookingStore(store)
        await bookings.save(_booking(id="bkg_1", tenant="t1", operator_id="op1",
                                     status=STATUS_NO_SHOW))
        await bookings.save(_booking(id="bkg_2", tenant="t2", operator_id="op1",
                                     status=STATUS_NO_SHOW))
        return await bookings.no_show_summary(
            "t1", start_bucket="2026-01-01", end_bucket="2026-12-31")

    totals = _run(run())
    assert totals == {"op1": {"total": 1, "no_show": 1}}


def test_outside_the_bucket_range_is_not_counted():
    async def run():
        from app.adapters.datastore.memory import MemoryDataStore
        store = MemoryDataStore()
        bookings = BookingStore(store)
        # 2026-08-16
        await bookings.save(_booking(id="bkg_1", operator_id="op1", status=STATUS_NO_SHOW,
                                     starts_at=1786860000))
        return await bookings.no_show_summary(
            "t1", start_bucket="2026-09-01", end_bucket="2026-09-30")

    assert _run(run()) == {}
