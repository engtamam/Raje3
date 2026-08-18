"""`booking_slots` — the derived index, and the one thing §4 explicitly warns is easy to get wrong:
a key built without the tenant prefix would make a cross-tenant scan possible even though `Booking`
itself is correctly isolated.
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


def test_a_tenants_slot_query_never_returns_another_tenants_booking():
    async def run():
        store = MemoryDataStore()
        bookings = BookingStore(store)
        await bookings.save(_booking(tenant="t1", id="bkg_1"))
        await bookings.save(_booking(tenant="t2", id="bkg_2"))
        return await bookings.slots_between("t1", "b1", start_bucket="2026-08-16",
                                            end_bucket="2026-08-16")

    rows = asyncio.run(run())
    assert [b.id for b in rows] == ["bkg_1"]


def test_every_slot_key_carries_the_tenant_prefix():
    async def run():
        store = MemoryDataStore()
        bookings = BookingStore(store)
        await bookings.save(_booking())
        return list(store._data.get("booking_slots", {}).keys())

    keys = asyncio.run(run())
    assert keys and all(k.startswith("t1|") for k in keys)


def test_a_reschedule_leaves_no_stale_slot_row_behind():
    async def run():
        store = MemoryDataStore()
        bookings = BookingStore(store)
        b = _booking()
        await bookings.save(b)
        b.starts_at = 1786860000 + 86400   # a day later
        await bookings.save(b)
        return list(store._data.get("booking_slots", {}).keys())

    keys = asyncio.run(run())
    assert len(keys) == 1, f"expected exactly one slot row after the reschedule, got {keys}"
