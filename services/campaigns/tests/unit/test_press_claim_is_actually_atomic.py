"""THE REAL BUG: `press.claim()` used to be a plain `store.get()` then, much later, `store.put()` —
a genuine check-then-act race, even though the datastore port has ALWAYS exposed a real atomic
`store.claim()` primitive built for exactly this (see `ports/datastore.py`'s own docstring: "the one
operation put cannot express"). `press.py` just never called it.

`test_two_presses_are_one_campaign.py` proves the SEQUENTIAL behaviour is right; this proves the
concurrent case actually is too — two genuinely simultaneous presses (no `await` gap needed to see
the bug, since `claim()`'s own contract says one statement, no room for a lost decision).
"""
from __future__ import annotations

import asyncio

from app.adapters.datastore.memory import MemoryDataStore
from app.core.press import claim, key_for

TENANT = "shop"
NOW = 1_780_000_000


class _RacyStore:
    """Wraps a real MemoryDataStore, but yields on `get`/`put` — approximating a real round trip,
    same technique `test_two_operators_cannot_take_the_same_slot.py` in bookings uses. `claim`
    passes straight through: MemoryDataStore's own `claim` has no `await` inside it by design (its
    own docstring says so), so wrapping it here would not change anything — the fix under test is
    press.py routing through THAT method instead of get+put."""

    def __init__(self, inner: MemoryDataStore) -> None:
        self._inner = inner

    async def get(self, *a, **kw):
        await asyncio.sleep(0)
        return await self._inner.get(*a, **kw)

    async def put(self, *a, **kw):
        await asyncio.sleep(0)
        return await self._inner.put(*a, **kw)

    def __getattr__(self, name):
        return getattr(self._inner, name)


def test_two_simultaneous_presses_of_the_same_intention_only_one_gets_to_create():
    key = key_for(TENANT, goal="win_back", owner_text="خصم 20%", service_id="", branch_id="",
                 offer_value="20%", expires_at=NOW + 604_800, fire_at=0)

    async def run():
        store = _RacyStore(MemoryDataStore())
        out = await asyncio.gather(
            claim(store, TENANT, key, now=NOW),
            claim(store, TENANT, key, now=NOW),
        )
        return out

    first, second = asyncio.run(run())
    winners = [p for p in (first, second) if p.first]
    assert len(winners) == 1, (
        "two simultaneous presses of the identical intention both won the claim — "
        f"got {len(winners)} winners, the exact double-campaign/double-charge bug this module "
        "exists to prevent")
