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


def test_slots_between_hydrates_with_one_batched_read_not_one_per_row():
    """THE N+1 THIS CLOSES. `slots_between` used to call `self.get()` once per matching slot row —
    `nearest_slot`'s own `limit=500` call meant up to 500 sequential round trips to answer one
    click. Proved by counting real `get_many`/`get` calls against the store, not just the returned
    rows: a fix that still hydrated one row at a time would pass a value-only assertion."""
    async def run():
        store = MemoryDataStore()
        bookings = BookingStore(store)
        for i in range(5):
            await bookings.save(_booking(id=f"bkg_{i}", starts_at=1786860000 + i * 1800))

        calls = {"get": 0, "get_many": 0}
        real_get, real_get_many = store.get, store.get_many

        async def counting_get(collection, key):
            calls["get"] += 1
            return await real_get(collection, key)

        async def counting_get_many(collection, keys):
            calls["get_many"] += 1
            return await real_get_many(collection, keys)

        store.get = counting_get
        store.get_many = counting_get_many

        rows = await bookings.slots_between("t1", "b1", start_bucket="2026-08-16",
                                            end_bucket="2026-08-16")
        return rows, calls

    rows, calls = asyncio.run(run())
    assert len(rows) == 5
    assert calls == {"get": 0, "get_many": 1}, (
        f"expected one batched get_many, got {calls}")
    # AND THE ORDER SURVIVES THE BATCH — the index's own bucket/created ordering, not whatever
    # order a dict happens to iterate keys in.
    assert [b.id for b in rows] == [f"bkg_{i}" for i in range(5)]


def test_slots_between_still_finds_a_current_range_past_500_older_rows():
    """bookings-001 (QA audit, 2026-09-12): a single unbounded `find(limit=500, sort=bucket asc)`
    with no `after` cursor returned only a branch's OLDEST 500 slot rows — so a branch with more
    history than that answered "no conflict" for its own current/future date range no matter how
    full it actually was, which is the one re-check the whole double-booking design relies on.
    600 old rows (all on 2026-01-01, well before the window asked for) plus one real row on
    2026-08-16 — the old code would drop the 2026-08-16 row from the very first page."""
    async def run():
        store = MemoryDataStore()
        bookings = BookingStore(store)
        for i in range(600):
            await bookings.save(_booking(id=f"old_{i}", starts_at=1735689600 + i))  # 2025-01-01, ascending
        await bookings.save(_booking(id="bkg_real", starts_at=1786860000))          # 2026-08-16
        return await bookings.slots_between("t1", "b1", start_bucket="2026-08-16",
                                            end_bucket="2026-08-16")

    rows = asyncio.run(run())
    assert [b.id for b in rows] == ["bkg_real"], (
        "the real, in-range row must be found even with 600 older rows ahead of it in the index")
