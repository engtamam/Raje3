"""save_if_unchanged's rev check must be atomic with its write.

bookings-r2-001 (QA audit, 2026-09-12): the check and the write used to be two separate awaited
steps with nothing between them — two writers reading the same `current.rev` could both pass the
check and the second `save()` would silently clobber the first's edit.
"""
from __future__ import annotations

import asyncio

from app.adapters.datastore.memory import MemoryDataStore
from app.core.models import Booking
from app.core.stores import BookingStore, ConcurrentEditError

TENANT = "t1"


class _SlowStore:
    """Wraps a real store but stalls between `get` and `put`, widening the race window so a
    non-atomic read-modify-write is caught deterministically instead of needing luck."""

    def __init__(self, inner):
        self._inner = inner

    async def get(self, collection, key):
        row = await self._inner.get(collection, key)
        await asyncio.sleep(0.01)
        return row

    async def put(self, collection, key, value):
        return await self._inner.put(collection, key, value)

    async def delete(self, collection, key):
        return await self._inner.delete(collection, key)

    async def claim(self, collection, key, value, *, ttl_seconds, now):
        return await self._inner.claim(collection, key, value, ttl_seconds=ttl_seconds, now=now)


def run(c):
    return asyncio.run(c)


def _booking(**over) -> Booking:
    kw = dict(id="bkg_1", tenant=TENANT, branch_id="brn_1", operator_id="op_1",
              customer_id="cust_1")
    kw.update(over)
    return Booking(**kw)


def test_two_genuinely_concurrent_writers_never_both_win():
    """One must win, the other must be refused with ConcurrentEditError — never both silently
    succeed with the loser's stale write surviving."""
    inner = MemoryDataStore()
    store = BookingStore(_SlowStore(inner))
    saved = run(store.save(_booking()))
    assert saved.rev == 1

    # BOTH WRITERS READ THE SAME ROW BEFORE EITHER WRITES — the actual race: two callers who
    # fetched the booking at rev=1 and now each want to apply their own change on top of it.
    # `save()` increments `b.rev` off the OBJECT PASSED IN, so each writer's copy must carry the
    # rev it actually read (1), never a freshly-constructed default of 0 — that would silently
    # test something else entirely (two brand-new, unrelated `rev=0` objects racing).
    import dataclasses
    b1 = dataclasses.replace(saved, customer_id="from_writer_1")
    b2 = dataclasses.replace(saved, customer_id="from_writer_2")

    async def race():
        return await asyncio.gather(
            store.save_if_unchanged(b1, expected_rev=1),
            store.save_if_unchanged(b2, expected_rev=1),
            return_exceptions=True,
        )

    results = run(race())
    successes = [r for r in results if isinstance(r, Booking)]
    failures = [r for r in results if isinstance(r, ConcurrentEditError)]
    assert len(successes) == 1
    assert len(failures) == 1

    final = run(store.get(TENANT, "bkg_1"))
    # The row on disk matches the WINNER's write — never a value that neither writer produced,
    # and never the loser's silently applied over the winner's.
    assert final.customer_id == successes[0].customer_id
    assert final.rev == 2
