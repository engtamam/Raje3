"""THE REAL BUG: `apply_due()` used to delete the pending row by KEY, unconditionally, after
applying it — a QA audit found this is a real TOCTOU: if an operator reschedules the SAME key
(schedule()'s own "replace whatever was pending" contract) in the small window between apply_due's
own `pending()` read and its delete, the tick's delete fires against the CURRENT row — which is now
the brand-new future-dated reschedule, not the one that was actually applied — and silently wipes
it before it was ever due. No error, no audit trace of the loss.
"""
from __future__ import annotations

import asyncio

from app.adapters.datastore.memory import MemoryDataStore
from app.core.pricing_schedule import PRICING_PENDING, apply_due, pending, schedule


class _FakeRuntimeConfig:
    """Just records what apply_due asked it to set — the fix under test is entirely about the
    pending-row lifecycle, not runtime_config itself."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def set(self, *, tenant, key, value, actor_ref):
        self.calls.append({"tenant": tenant, "key": key, "value": value, "actor_ref": actor_ref})


class _RescheduleRacingStore:
    """Wraps a real MemoryDataStore. The FIRST `get(PRICING_PENDING, ...)` call after construction
    (apply_due's own new compare-read, right after applying the change) simulates a genuinely
    concurrent `schedule()` landing just before that read — by performing the reschedule itself,
    then returning the now-current (rescheduled) row. This deterministically reproduces the exact
    interleaving the bug depended on, without needing real thread/asyncio timing luck."""

    def __init__(self, inner: MemoryDataStore, *, rescheduled_row: dict) -> None:
        self._inner = inner
        self._rescheduled_row = rescheduled_row
        self._fired = False

    async def get(self, collection, key):
        if collection == PRICING_PENDING and not self._fired:
            self._fired = True
            await self._inner.put(collection, key, self._rescheduled_row)
            return dict(self._rescheduled_row)
        return await self._inner.get(collection, key)

    def __getattr__(self, name):
        return getattr(self._inner, name)


def test_a_reschedule_racing_the_tick_is_not_silently_deleted():
    async def run():
        real = MemoryDataStore()
        now = 1_800_000_000
        await schedule(real, key="PRICING_STRATEGY", value="usage_based",
                       effective_at=now - 60, actor="op1", now=now - 15 * 86_400)

        # The reschedule that "races in" — a DIFFERENT value/effective_at/scheduled_at, so the
        # compare in apply_due must tell it apart from what was actually applied.
        raced_row = {"key": "PRICING_STRATEGY", "value": "addon_on_existing_plan",
                    "effective_at": now + 15 * 86_400, "scheduled_by": "op2", "scheduled_at": now}

        store = _RescheduleRacingStore(real, rescheduled_row=raced_row)
        rc = _FakeRuntimeConfig()
        applied = await apply_due(store, rc, now=now)

        remaining = await pending(real)
        return applied, remaining, rc.calls

    applied, remaining, calls = asyncio.run(run())

    assert applied == ["PRICING_STRATEGY"]           # the originally-due change WAS applied
    assert calls[0]["value"] == "usage_based"         # with the value that was actually due

    # THE FIX: the raced-in reschedule must survive — never silently deleted.
    assert len(remaining) == 1, "the concurrent reschedule was wiped out by the tick that raced it"
    assert remaining[0].value == "addon_on_existing_plan"
    assert remaining[0].effective_at == 1_800_000_000 + 15 * 86_400
