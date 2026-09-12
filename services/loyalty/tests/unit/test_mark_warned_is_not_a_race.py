"""THE REAL BUG: `Expiry.mark_warned` read the whole balance row, set `expiry_warned_at`, and wrote
the whole row back with no lock at all — unlike every other read-modify-write on a balance in this
service (`earn`, `redeem`, the expiry sweep's own expire path), which all hold `SpendLock`. A `tick`
can be mid-loop, stamping hundreds of warned rows one at a time, for exactly as long as a customer
can be standing at a till moving that same balance. Because the OLD `mark_warned` never even tried
to take the lock, it could read a balance mid-`earn` (before the entry AND balance write land) and
then write its own stale copy back AFTER `earn` finishes — silently reverting the customer's points
to what they were before his visit. `SpendLock` closes that window: `mark_warned` now contends for
the exact same lane `earn` holds, so it is refused (and skips the stamp for this pass) rather than
clobbering an in-flight write.
"""
from __future__ import annotations

import asyncio

from app.adapters.cache.memory import MemoryCache
from app.adapters.datastore.memory import MemoryDataStore
from app.core.earn import Earner
from app.core.earning import EarnStore
from app.core.expiry import Expiry
from app.core.ledger import Ledger

T = "shop"
S = "ref_abcdef123456"
NOW = 1_800_000_000


class _SlowStore:
    """Yields on `get` — the call `Ledger.balance` makes inside `earn`'s locked section — so
    `mark_warned`'s own lock attempt genuinely lands WHILE `earn` still holds the lock, same
    technique as the other race tests in this suite."""

    def __init__(self, inner: MemoryDataStore) -> None:
        self._inner = inner

    async def get(self, *a, **kw):
        await asyncio.sleep(0)
        return await self._inner.get(*a, **kw)

    def __getattr__(self, name):
        return getattr(self._inner, name)


def run(c):
    return asyncio.run(c)


def test_a_visit_in_flight_is_not_reverted_by_a_concurrent_stamp():
    store = _SlowStore(MemoryDataStore())
    ledger = Ledger(store)
    cache = MemoryCache()
    exp = Expiry(store, ledger, cache=cache)
    settings = EarnStore(store)
    run(settings.set_general(T, {"points": 20}))
    earner = Earner(ledger, settings, cache=cache)

    run(ledger.post(tenant=T, subject_ref=S, delta=100, reason="earn", source="v1", now=NOW))

    async def go():
        return await asyncio.gather(
            earner.from_visit(T, visit_id="v2", subject_ref=S, service_ids=["svc1"],
                              tree=await settings.load(T)),
            exp.mark_warned(T, S, NOW),
            return_exceptions=True,
        )

    results = run(go())
    assert not any(isinstance(r, Exception) for r in results), results

    bal = run(ledger.balance(T, S))
    # THE VISIT'S POINTS MUST SURVIVE — before the fix, `mark_warned` (never even trying the lock)
    # could read the balance before `earn`'s write landed and write its stale copy back after,
    # silently reverting the 20 points from `v2`.
    assert bal.points == 120, f"expected the concurrent earn to survive, balance is {bal.points}"
