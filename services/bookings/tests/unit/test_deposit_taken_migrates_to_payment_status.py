"""A row saved before 2026-08-19 still carries `deposit_taken: bool`, and this deploy must read it
without a backfill job running first — `_from_row` is the one place that boolean becomes the new
`payment_status: str` (docs: models.py's own PAYMENT_STATES note).
"""
from __future__ import annotations

import asyncio

from app.adapters.datastore.memory import MemoryDataStore
from app.core.stores import BookingStore, _key


def _run(coro):
    return asyncio.run(coro)


def _seed_old_row(store: MemoryDataStore, tenant: str, booking_id: str, deposit_taken: bool) -> None:
    row = {
        "id": booking_id, "tenant": tenant, "branch_id": "b1", "operator_id": "op1",
        "customer_id": "c1", "service_ids": ["svc1"], "starts_at": 1786860000,
        "duration_minutes": 30, "status": "booked", "deposit_taken": deposit_taken,
    }
    _run(store.put(BookingStore.collection, _key(tenant, booking_id), row))


def test_an_old_row_with_deposit_taken_true_reads_as_deposit():
    ds = MemoryDataStore()
    _seed_old_row(ds, "t1", "bkg_1", deposit_taken=True)
    booking = _run(BookingStore(ds).get("t1", "bkg_1"))
    assert booking.payment_status == "deposit"


def test_an_old_row_with_deposit_taken_false_reads_as_none():
    ds = MemoryDataStore()
    _seed_old_row(ds, "t1", "bkg_2", deposit_taken=False)
    booking = _run(BookingStore(ds).get("t1", "bkg_2"))
    assert booking.payment_status == "none"
