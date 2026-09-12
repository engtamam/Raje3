"""operations-r2-001 (QA audit round 2, 2026-09-12): two invoices for the same brand-new product,
arriving in two different requests close together, used to both read their own "not found yet"
catalogue snapshot and both create a row for it — one product ending up as two identical services.
Proved end to end through `invoices.resolve` itself, with a real cache wired (so
`InvoiceServiceCreateLock` actually engages) and a slow-yielding datastore wrapper (so the two
coroutines genuinely interleave — same technique `test_customer_counter_race.py` already uses for
the sibling defect in the same audit).
"""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.cache.memory import MemoryCache
from app.adapters.datastore.memory import MemoryDataStore
from app.core import invoices as I
from app.core.invoice_service_lock import InvoiceServiceCreateBusy
from app.core.stores import ServiceStore, new_id

NOW = 1_800_000_000
TENANT = "t1"
PRODUCT_ID = "P-NEW"


def run(coro):
    return asyncio.run(coro)


class _SlowStore:
    """Delegates to a real MemoryDataStore, but `find` yields first — enough for a second,
    concurrent `resolve()` call to also read "not found yet" before either one creates the row."""

    def __init__(self, inner: MemoryDataStore) -> None:
        self._inner = inner

    async def find(self, *a, **kw):
        await asyncio.sleep(0)
        return await self._inner.find(*a, **kw)

    def __getattr__(self, name):
        return getattr(self._inner, name)


@pytest.fixture()
def wired():
    store = ServiceStore(_SlowStore(MemoryDataStore()))
    cache = MemoryCache()
    return store, cache


def test_two_concurrent_invoices_for_the_same_new_product_create_one_service(wired):
    store, cache = wired

    async def one_invoice():
        # `existing=None`: each call pays for its own fresh catalogue read, exactly the shape
        # `record_visits_batch` uses for the FIRST item of a new tenant, and the one that raced.
        return await I.resolve(
            I.parse_lines([{"product_id": PRODUCT_ID, "name": "غسيل خارجي"}]),
            tenant=TENANT, service_store=store, new_id=new_id, now=NOW, cache=cache)

    async def go():
        return await asyncio.gather(one_invoice(), one_invoice(), return_exceptions=True)

    results = run(go())
    succeeded = [r for r in results if not isinstance(r, Exception)]
    busy = [r for r in results if isinstance(r, InvoiceServiceCreateBusy)]

    # AT LEAST ONE MUST GO THROUGH, and whichever one arrives second — whether it won the claim
    # after the first released it, or lost the claim outright — must never have minted a SECOND
    # row for the same product.
    assert succeeded or busy, f"both calls raised something unexpected: {results}"
    for r in succeeded:
        assert len(r.created_services) <= 1

    catalogue = run(store.list(TENANT, active_only=False))
    matching = [s for s in catalogue if s.external_id == PRODUCT_ID]
    assert len(matching) == 1, (
        f"expected exactly one service for {PRODUCT_ID!r}, got {len(matching)}: {matching}")
