"""THE REAL BUG: `Earner.from_visit` posts to the ledger with no lock at all — unlike redemption
(`core/redeem.py`, wrapped in `SpendLock`), which was fixed for exactly this shape. The event bus
that drives earning is at-most-once BY CONTRACT (this file's own module docstring), so a redelivery
processed concurrently with the original is a real, expected occurrence, not a hypothetical.

`Ledger.already_posted()` (keyed on tenant/source/reason) is a plain `find()` read, and the ledger
entry it's checking for doesn't exist until AFTER `post()` finishes writing — so two concurrent
`from_visit()` calls for the SAME visit both see "not yet posted" before either has written
anything, and both award points.
"""
from __future__ import annotations

import asyncio

from app.adapters.cache.memory import MemoryCache
from app.adapters.datastore.memory import MemoryDataStore
from app.core.earn import Earner
from app.core.earning import EarnStore
from app.core.ledger import Ledger
from app.core.spend_lock import SpendBusy

TENANT = "t1"
SUBJECT = "sub_1"


class _SlowStore:
    """Yields on `find`/`get` — the calls `already_posted`/`balance` actually make — so two
    `asyncio.gather`ed calls genuinely interleave, same technique as the bookings/campaigns/
    affiliate-service race tests."""

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


def test_two_simultaneous_deliveries_of_the_same_visit_only_earn_once():
    async def run():
        store = _SlowStore(MemoryDataStore())
        ledger = Ledger(store)
        settings = EarnStore(store)
        await settings.set_general(TENANT, {"points": 10})
        earner = Earner(ledger, settings, cache=MemoryCache())

        results = await asyncio.gather(
            earner.from_visit(TENANT, visit_id="vis_1", subject_ref=SUBJECT,
                             service_ids=["svc1"], tree=await settings.load(TENANT)),
            earner.from_visit(TENANT, visit_id="vis_1", subject_ref=SUBJECT,
                             service_ids=["svc1"], tree=await settings.load(TENANT)),
            return_exceptions=True,
        )
        return results, await ledger.balance(TENANT, SUBJECT)

    results, bal = asyncio.run(run())
    # ONE WINS AND EARNS, THE OTHER IS TOLD "BUSY" (never a silent second award) — the same shape
    # redemption's own SpendLock already guarantees. A bus consumer that gets SpendBusy retries,
    # and by the time it does, `already_posted` correctly finds the entry and returns a duplicate.
    earned = [r for r in results if isinstance(r, dict) and r.get("earned")]
    busy = [r for r in results if isinstance(r, SpendBusy)]
    assert len(earned) == 1 and len(busy) == 1, (
        f"expected exactly one winner and one SpendBusy — got {results!r}, balance={bal.points}")
    assert bal.points == 10, f"expected exactly one award of 10 points, balance is {bal.points}"
