"""A row saved before 2026-09-08 still carries `series_id`/`series_seq` (dead fields — written by
every save via `Booking.__dict__`, read by nothing: `for_series`, the one method that would have
used them, had no caller anywhere in this codebase). `Booking` no longer declares either field, so
`_from_row` must still POP both from the row before construction — otherwise `Booking(**row)`
raises on the very first read of any booking written before this change, on any live deployment
with real data.
"""
from __future__ import annotations

import asyncio

from app.adapters.datastore.memory import MemoryDataStore
from app.core.models import Booking
from app.core.stores import BookingStore, _key


def _run(coro):
    return asyncio.run(coro)


def _seed_old_row(store: MemoryDataStore, tenant: str, booking_id: str, *,
                  series_id, series_seq) -> None:
    row = {
        "id": booking_id, "tenant": tenant, "branch_id": "b1", "operator_id": "op1",
        "customer_id": "c1", "service_ids": ["svc1"], "starts_at": 1786860000,
        "duration_minutes": 30, "status": "booked",
        # THE EXACT OLD SHAPE — every real row on disk before this change has both keys, since
        # `BookingStore.save` wrote `b.__dict__` (every dataclass field, defaults included) and
        # both defaulted to None on every booking ever created (the feature never had a caller).
        "series_id": series_id, "series_seq": series_seq,
    }
    _run(store.put(BookingStore.collection, _key(tenant, booking_id), row))


def test_an_old_row_with_the_dead_fields_null_still_reads_fine():
    ds = MemoryDataStore()
    _seed_old_row(ds, "t1", "bkg_1", series_id=None, series_seq=None)
    booking = _run(BookingStore(ds).get("t1", "bkg_1"))
    assert booking is not None
    assert booking.id == "bkg_1"


def test_an_old_row_with_the_dead_fields_actually_set_still_reads_fine():
    """The overwhelmingly common case (both None) is not the only one this must survive — a
    handful of rows may have had a real value written to `series_id`/`series_seq` at some point
    (the fields existed and were assignable, even with no reader). Dropping them must be silent
    either way, never a crash tied to whether the old value happened to be null."""
    ds = MemoryDataStore()
    _seed_old_row(ds, "t1", "bkg_2", series_id="ser_abc", series_seq=2)
    booking = _run(BookingStore(ds).get("t1", "bkg_2"))
    assert booking is not None
    assert booking.id == "bkg_2"


def test_the_read_booking_carries_no_trace_of_the_dead_fields():
    ds = MemoryDataStore()
    _seed_old_row(ds, "t1", "bkg_3", series_id="ser_xyz", series_seq=0)
    booking = _run(BookingStore(ds).get("t1", "bkg_3"))
    assert not hasattr(booking, "series_id")
    assert not hasattr(booking, "series_seq")


def test_a_freshly_created_booking_never_carries_the_dead_fields_either():
    """The dataclass itself no longer declares them — this is the structural half of the removal,
    not just the read-migration half above."""
    b = Booking(id="bkg_4", tenant="t1", branch_id="b1", operator_id="op1", customer_id="c1",
               service_ids=("svc1",), starts_at=1786860000, duration_minutes=30)
    assert not hasattr(b, "series_id")
    assert not hasattr(b, "series_seq")
    assert "series_id" not in b.__dict__
    assert "series_seq" not in b.__dict__


def test_saving_and_rereading_a_fresh_booking_round_trips_clean():
    """End to end: a booking created under the NEW shape, saved, and read back — no dead keys
    anywhere in the stored row or the object that comes back."""
    ds = MemoryDataStore()
    store = BookingStore(ds)
    b = Booking(id="bkg_5", tenant="t1", branch_id="b1", operator_id="op1", customer_id="c1",
               service_ids=("svc1",), starts_at=1786860000, duration_minutes=30)
    _run(store.save(b))
    stored_row = _run(ds.get(BookingStore.collection, _key("t1", "bkg_5")))
    assert "series_id" not in stored_row
    assert "series_seq" not in stored_row
    reread = _run(store.get("t1", "bkg_5"))
    assert reread is not None
    assert reread.id == "bkg_5"
