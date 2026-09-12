"""THE REAL BUG (loyalty-r2-002, QA audit round 2, 2026-09-12): `rating_bonus` posted to the
ledger with no `SpendLock` at all — unlike every other point-of-sale ledger writer in this
service (`earn`, `redeem`, the expiry sweep, `adjust`), which were all brought under it. Same
shape as `Earner.from_visit`'s own race (see `test_earn_is_not_a_race.py`): `Ledger.already_posted`
(keyed on tenant/source/reason) is a plain `find()` read, and the entry it checks for does not
exist until AFTER `post()` finishes writing — so two concurrent rating-bonus credits for the SAME
visit (a retry from `reminders`, which owns no idempotency of its own here) both see "not yet
credited" and both award points.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

from app.adapters.cache.memory import MemoryCache
from app.adapters.datastore.memory import MemoryDataStore
from app.api.internal import RatingBonusIn, rating_bonus
from app.core.ledger import Ledger
from app.core.spend_lock import SpendBusy

TENANT = "t1"
SUBJECT = "sub_rating_1"


class _SlowStore:
    """Yields on `find`/`get` — the calls `already_posted`/`balance` actually make — so two
    `asyncio.gather`ed calls genuinely interleave, same technique as the earn/redeem/expiry
    race tests in this suite."""

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


class _Auditor:
    async def record(self, *a, **kw):
        return None


def _make_request(container):
    app = SimpleNamespace(state=SimpleNamespace(container=container, auditor=_Auditor()))
    return SimpleNamespace(app=app, client=None)


def test_two_simultaneous_credits_for_the_same_rating_only_earn_once():
    async def run():
        store = _SlowStore(MemoryDataStore())
        ledger = Ledger(store)
        container = SimpleNamespace(ledger=ledger, cache=MemoryCache(), licence=None)
        request = _make_request(container)
        body = RatingBonusIn(tenant=TENANT, visit_id="vis_rating_1", subject_ref=SUBJECT,
                             points=20, actor="reminders")

        results = await asyncio.gather(
            rating_bonus(request, body), rating_bonus(request, body), return_exceptions=True,
        )
        return results, await ledger.balance(TENANT, SUBJECT)

    results, bal = asyncio.run(run())
    # ONE WINS AND EARNS, THE OTHER IS TOLD "BUSY" — never a silent second award. Unlike `earn`
    # (called by an at-most-once bus that retries on `SpendBusy`), this route has no caller-side
    # retry contract, so the raised `SpendBusy` propagating out (rather than being swallowed into
    # a 200) is itself the correct, visible refusal.
    earned = [r for r in results if isinstance(r, dict) and r.get("earned")]
    busy = [r for r in results if isinstance(r, SpendBusy)]
    assert len(earned) == 1 and len(busy) == 1, (
        f"expected exactly one winner and one SpendBusy — got {results!r}, balance={bal.points}")
    assert bal.points == 20, f"expected exactly one credit of 20 points, balance is {bal.points}"
