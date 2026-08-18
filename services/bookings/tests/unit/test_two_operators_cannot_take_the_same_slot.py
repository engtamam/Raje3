"""The double-booking race — same shape as operations' `test_two_managers_cannot_take_the_same_
last_seat.py`: the check and the write were never one act, and two staff confirming the same
operator's slot at the same moment both read "free" unless the confirm is serialised.

WHAT MAKES THE TEST REAL. `MemoryDataStore.find`/`get` never actually suspend the event loop (no
internal `await` on real I/O), so two `asyncio.gather`ed calls to `BookingOperations.create()`
would never genuinely interleave against it — the test would pass even with the lock deleted,
for the same reason `seats.py`'s test injects a `sleep(0)` into its gauge double. `_SlowStore`
below does the equivalent here: a thin wrapper that yields on `find`/`get` (the calls
`_refuse_if_conflicting` makes), approximating the real round trip Postgres has. `claim`/`put`/
`delete` pass straight through — the lock's own atomicity is never weakened by this wrapper.

SABOTAGE CHECK: replace `claiming` in `app/core/operations.py` with a context manager that yields
unconditionally (no real claim), and `test_only_one_of_two_simultaneous_bookings_wins` fails with
2 bookings created for the same operator at the same 15-minute bucket.
"""
from __future__ import annotations

import asyncio

import pytest
from app.adapters.datastore.memory import MemoryDataStore
from app.core.licence import NullLicence
from app.core.lock import SlotClaimBusy
from app.core.operations import BookingOperations, DurationLookup, OperationError
from app.core.stores import BookingStore


class _SlowStore:
    """Delegates to a real MemoryDataStore, but `find`/`get` yield first — see module doc."""

    def __init__(self, inner: MemoryDataStore) -> None:
        self._inner = inner

    async def find(self, *a, **kw):
        await asyncio.sleep(0)
        return await self._inner.find(*a, **kw)

    async def get(self, *a, **kw):
        await asyncio.sleep(0)
        return await self._inner.get(*a, **kw)

    def __getattr__(self, name):
        return getattr(self._inner, name)


async def _lookup(tenant: str, service_ids) -> int:
    return 30


async def _no_visits(**kwargs):
    return None


def _ops(store) -> BookingOperations:
    from app.core.operations import VisitGateway
    return BookingOperations(datastore=store, bookings=BookingStore(store),
                             durations=DurationLookup(lookup=_lookup), licence=NullLicence(),
                             visits=VisitGateway(create=_no_visits))


def test_only_one_of_two_simultaneous_bookings_wins():
    async def run():
        store = _SlowStore(MemoryDataStore())
        ops = _ops(store)
        out = await asyncio.gather(
            ops.create(tenant="t1", branch_id="b1", operator_id="op1", customer_id="c1",
                      service_ids=["svc1"], starts_at=1786860000),
            ops.create(tenant="t1", branch_id="b1", operator_id="op1", customer_id="c2",
                      service_ids=["svc1"], starts_at=1786860060),   # one minute later, SAME
                                                                     # 15-min lock bucket
            return_exceptions=True)
        created = [o for o in out if not isinstance(o, Exception)]
        refused = [o for o in out if isinstance(o, Exception)]
        return created, refused

    created, refused = asyncio.run(run())

    assert len(created) == 1, "two bookings for one operator's same slot both succeeded"
    assert len(refused) == 1, "the loser must be told, not silently dropped"
    assert isinstance(refused[0], (SlotClaimBusy, OperationError))
    assert str(refused[0]).strip(), "an empty message is a 500 wearing a status code"


def test_different_operators_do_not_queue_behind_each_other():
    """ONE LANE PER OPERATOR — a lock shared across staff would refuse a booking for operator B
    because operator A's slot is being confirmed at the same instant."""
    async def run():
        store = _SlowStore(MemoryDataStore())
        ops = _ops(store)
        out = await asyncio.gather(
            ops.create(tenant="t1", branch_id="b1", operator_id="op1", customer_id="c1",
                      service_ids=["svc1"], starts_at=1786860000),
            ops.create(tenant="t1", branch_id="b1", operator_id="op2", customer_id="c2",
                      service_ids=["svc1"], starts_at=1786860000),
            return_exceptions=True)
        return [o for o in out if isinstance(o, Exception)]

    errors = asyncio.run(run())
    assert errors == [], "two different operators' slots must not contend"
