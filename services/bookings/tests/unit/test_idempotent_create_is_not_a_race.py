"""THE REAL BUG: the double-tap guard's own read (`by_idempotency_key`) was a plain `find()`, with
nothing serialising it against a second concurrent create carrying the SAME idempotency_key — a QA
audit found two genuinely simultaneous creates could both see "not found" before either had written
a booking, and both proceed to create one, defeating the whole point of the key.
"""
from __future__ import annotations

import asyncio

from app.adapters.datastore.memory import MemoryDataStore
from app.core.licence import NullLicence
from app.core.operations import BookingEvents, BookingOperations, DurationLookup, OperationError, SubjectRefLookup, VisitGateway
from app.core.stores import BookingStore

TENANT = "t1"


async def _lookup(tenant: str, service_ids) -> int:
    return 30


async def _no_visits(**kwargs):
    return None


async def _subject_ref(tenant: str, customer_id: str) -> str:
    return "sub_" + customer_id


class _SlowStore:
    """Delegates to a real MemoryDataStore, but `find`/`get` yield first — same technique as
    test_two_operators_cannot_take_the_same_slot.py. `claim`/`put` pass straight through
    unmodified — the fix under test is routing the idempotency check through `claim()` at all."""

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


def _ops(store) -> BookingOperations:
    return BookingOperations(datastore=store, bookings=BookingStore(store),
                             durations=DurationLookup(lookup=_lookup), licence=NullLicence(),
                             visits=VisitGateway(create=_no_visits),
                             subject_refs=SubjectRefLookup(lookup=_subject_ref),
                             events=BookingEvents(publish=None))


def test_two_simultaneous_creates_with_the_same_idempotency_key_only_one_creates():
    async def run():
        store = _SlowStore(MemoryDataStore())
        ops = _ops(store)
        out = await asyncio.gather(
            ops.create(tenant=TENANT, branch_id="b1", operator_id="op1", customer_id="c1",
                      service_ids=["svc1"], starts_at=1786860000, idempotency_key="tap-1"),
            ops.create(tenant=TENANT, branch_id="b1", operator_id="op2", customer_id="c2",
                      service_ids=["svc1"], starts_at=1786870000, idempotency_key="tap-1"),
            return_exceptions=True)
        return out

    out = asyncio.run(run())
    created_ids = {o.id for o in out if not isinstance(o, Exception)}
    refused = [o for o in out if isinstance(o, OperationError)]
    # Either both calls converge on the SAME booking (the loser's retry saw the winner's write in
    # time), or the loser is refused loudly with "busy" — never two DIFFERENT bookings for one key.
    assert len(created_ids) == 1, (
        f"two concurrent creates with the SAME idempotency_key produced {len(created_ids)} "
        f"different bookings — {out!r}")
    if refused:
        assert "قيد التنفيذ" in str(refused[0])
