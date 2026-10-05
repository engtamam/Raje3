"""operations-001 (QA audit, 2026-09-12): two genuinely concurrent `record_visit` calls for the
SAME existing customer used to both read the same `visit_count`, both increment, and the later
`save()` silently overwrite the earlier one. Proved end to end through `Operations.record_visit`
itself, with a real cache wired (so the lock actually engages) and a slow-yielding store wrapper
(so the two coroutines genuinely interleave — the same technique bookings' own double-booking
race test and this service's own till_offer.py race test both use).
"""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.cache.memory import MemoryCache
from app.adapters.datastore.memory import MemoryDataStore
from app.core.customer_counter_lock import CustomerCounterBusy
from app.core.operations import Operations

SALT = "s" * 32
T = "shop"
PHONE = "0501234567"


def run(coro):
    return asyncio.run(coro)


class _SlowStore:
    """Delegates to a real MemoryDataStore, but `get` yields first — see module doc."""

    def __init__(self, inner: MemoryDataStore) -> None:
        self._inner = inner

    async def get(self, *a, **kw):
        await asyncio.sleep(0)
        return await self._inner.get(*a, **kw)

    def __getattr__(self, name):
        return getattr(self._inner, name)


@pytest.fixture()
def ops():
    store = _SlowStore(MemoryDataStore())
    return Operations(store=store, pii_salt=SALT, cache=MemoryCache()), store


def test_two_concurrent_visits_for_the_same_customer_never_lose_an_increment(ops):
    operations, store = ops
    # Seed the customer with a first visit so the SECOND round below hits the "already existed"
    # (locked) branch, not the brand-new-customer (unlocked, nothing to race) one.
    first = run(operations.record_visit(tenant=T, phone=PHONE, service_ids=["svc1"], name="أول"))
    customer_id = first.customer.id

    async def go():
        return await asyncio.gather(
            operations.record_visit(tenant=T, phone=PHONE, service_ids=["svc1"],
                                    idempotency_key="visit-a"),
            operations.record_visit(tenant=T, phone=PHONE, service_ids=["svc1"],
                                    idempotency_key="visit-b"),
            return_exceptions=True)

    results = run(go())
    busy = [r for r in results if isinstance(r, CustomerCounterBusy)]

    # BOTH CONCURRENT VISITS LAND AND BOTH ARE COUNTED. The losing call used to be refused — but
    # only AFTER its visit row was saved, so the shop held three visits and a counter of two, and
    # the refused one never ran its seams (no points, no reminder). The lock now waits its turn.
    assert not busy, f"neither call may be refused for a lock held only milliseconds, got {results}"
    assert all(not isinstance(r, Exception) for r in results), results

    from app.core.models import CUSTOMERS, VISITS
    row = run(store._inner.get(CUSTOMERS, f"{T}|{customer_id}"))
    visits, _ = run(store._inner.find(VISITS, {"tenant": T, "customer_id": customer_id}, limit=50))
    assert len(visits) == 3
    assert row["visit_count"] == len(visits), (
        f"the counter must agree with the visits actually saved: {row['visit_count']} vs {len(visits)}"
    )


def test_replaying_an_older_visits_key_never_counts_it_twice(ops):
    """A queue retrying a request that had in fact succeeded — after ANOTHER visit for the same
    customer landed in between — must change nothing. The replay used to ask the customer's
    `counted_visit_id` (which only remembers the last visit counted), saw a different id, and
    counted the older visit a second time."""
    operations, store = ops
    first = run(operations.record_visit(tenant=T, phone=PHONE, service_ids=["svc1"],
                                        idempotency_key="visit-1"))
    run(operations.record_visit(tenant=T, phone=PHONE, service_ids=["svc1"],
                                idempotency_key="visit-2"))
    run(operations.record_visit(tenant=T, phone=PHONE, service_ids=["svc1"],
                                idempotency_key="visit-3"))
    # Every key replayed, oldest first — each is a duplicate and none may move the counter.
    for key in ("visit-1", "visit-2", "visit-3", "visit-1"):
        replay = run(operations.record_visit(tenant=T, phone=PHONE, service_ids=["svc1"],
                                             idempotency_key=key))
        assert replay.duplicate

    from app.core.models import CUSTOMERS, VISITS
    row = run(store._inner.get(CUSTOMERS, f"{T}|{first.customer.id}"))
    visits, _ = run(store._inner.find(VISITS, {"tenant": T, "customer_id": first.customer.id},
                                      limit=50))
    assert len(visits) == 3
    assert row["visit_count"] == 3, f"replays re-counted visits: visit_count={row['visit_count']}"
    assert all(v.get("counted") for v in visits)


def test_a_visit_saved_before_its_counters_is_counted_once_by_its_retry(ops):
    """The crash window `Visit.counted` exists for: the visit row is written uncounted and the
    process dies before the counters move. The retry of its key must count it — exactly once."""
    operations, store = ops
    first = run(operations.record_visit(tenant=T, phone=PHONE, service_ids=["svc1"],
                                        idempotency_key="visit-1"))
    from app.core.models import CUSTOMERS, VISITS
    # The interrupted write, reproduced: the visit on record uncounted, the counter behind it.
    vkey, ckey = f"{T}|{first.visit.id}", f"{T}|{first.customer.id}"
    v = run(store._inner.get(VISITS, vkey))
    run(store._inner.put(VISITS, vkey, {**v, "counted": False}))
    c = run(store._inner.get(CUSTOMERS, ckey))
    run(store._inner.put(CUSTOMERS, ckey, {**c, "visit_count": 0, "counted_visit_id": ""}))

    for _ in range(2):
        run(operations.record_visit(tenant=T, phone=PHONE, service_ids=["svc1"],
                                    idempotency_key="visit-1"))
    assert run(store._inner.get(CUSTOMERS, ckey))["visit_count"] == 1
