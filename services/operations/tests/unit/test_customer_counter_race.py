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
    succeeded = [r for r in results if not isinstance(r, Exception)]
    busy = [r for r in results if isinstance(r, CustomerCounterBusy)]

    # ONE OF THE TWO GENUINELY CONCURRENT CALLS WINS THE LOCK; THE OTHER IS REFUSED LOUDLY — never
    # both silently "succeeding" with one increment lost between them.
    assert len(succeeded) == 1, f"expected exactly one winner, got {results}"
    assert len(busy) == 1

    from app.core.models import CUSTOMERS
    row = run(store._inner.get(CUSTOMERS, f"{T}|{customer_id}"))
    assert row["visit_count"] == 2, (
        f"expected exactly 2 counted visits (the seed + the one winner), got {row['visit_count']}"
    )
