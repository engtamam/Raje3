"""reminders-r2-001 (QA audit round 2, 2026-09-12): `/reminders/redemption` used to read the
pending schedule row and blind-upsert it back, bypassing `Tick._claim()`'s own row-claim lock
entirely — a tick claiming/sending that same row concurrently with the merge could have the claim
stomped, or a closed `sent` row reverted back to `pending`. The fix routes the merge through the
IDENTICAL `_CLAIM_LOCKS`-keyed lock `_claim()` uses, so the two paths now serialise against each
other rather than racing.

Raced with the same slow-yielding-store technique
`test_tick.py::test_two_replicas_sharing_one_store_never_both_win_the_same_claim` uses: wrapping
`.get()` with a real suspension point (`asyncio.sleep(0)`) so the two coroutines genuinely
interleave rather than one running to completion before the other starts.
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from types import SimpleNamespace

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.api import internal as I
from app.core import gate as G
from app.core.models import Schedule, as_row
from app.core.stores import ScheduleStore
from app.core.tick import CLAIM_LOCK_TTL_SECONDS, _CLAIM_LOCKS, Tick

from test_tick import ECFG, FakeSender  # same fixtures/helpers the tick suite already builds


def run(c):
    return asyncio.run(c)


def at(hour, day=15):
    return int(datetime(2026, 6, day, hour, tzinfo=G.RIYADH).timestamp())


def _engine(store):
    return Tick(store=store, sender=FakeSender(), limits=G.Limits(), eng_cfg=ECFG,
                public_base_url="https://my.example.sa")


def _fake_request(container) -> SimpleNamespace:
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(container=container)))


@pytest.fixture
def st():
    return MemoryDataStore()


def _redemption_row(st) -> Schedule:
    s = Schedule(tenant="t1", subject_ref="subject_a1", service_id="oil", kind="visit_confirmation",
                 due_at=at(9), cls="service", template_type="svc_visit_confirmation")
    run(ScheduleStore(st).upsert(s.tenant, s.key, as_row(s)))
    return s


def test_redemption_refuses_to_stomp_a_row_a_tick_already_claimed(st):
    """Sequential version of the race, and the direct proof of the bug described in the finding:
    a tick claims the row first (moving it to `sending`), and the redemption merge — which read
    the row as `pending` before that claim — must not blind-upsert its stale copy over it."""
    s = _redemption_row(st)
    row = run(ScheduleStore(st).get(s.key))

    engine = _engine(st)
    claimed = run(engine._claim("t1", dict(row), at(10)))
    assert claimed is True

    container = SimpleNamespace(datastore=st)
    body = I.RedemptionIn(tenant="t1", subject_ref="subject_a1", reward_name="قهوة مجانية",
                          cost=50, remaining=100)
    out = run(I.redemption(_fake_request(container), body))

    assert out == {"merged": False, "reason": "no pending visit confirmation"}, (
        "a redemption reaching a row already moved to 'sending' must decline, not overwrite it")
    stored = run(ScheduleStore(st).get(s.key))
    assert stored["state"] == "sending", (
        "the old bug reverted a claimed row back to 'pending' via a blind upsert of the stale copy")
    assert "redeemed_name" not in stored, (
        "a redemption that lost the race must never have written its fields onto the claimed row")


def test_redemption_and_a_ticks_claim_never_both_act_on_the_same_stale_read(st):
    """The genuinely concurrent version: a `_SlowStore` inserts a real suspension point in `.get`,
    so `Tick._claim()` and `/reminders/redemption` — racing over the SAME `_CLAIM_LOCKS` key — must
    serialise rather than each acting on a snapshot the other has since invalidated."""
    s = _redemption_row(st)
    row = run(ScheduleStore(st).get(s.key))

    class _SlowStore:
        def __init__(self, inner):
            self._inner = inner

        async def get(self, *a, **kw):
            await asyncio.sleep(0)
            return await self._inner.get(*a, **kw)

        def __getattr__(self, name):
            return getattr(self._inner, name)

    slow = _SlowStore(st)
    engine = _engine(slow)
    container = SimpleNamespace(datastore=slow)
    body = I.RedemptionIn(tenant="t1", subject_ref="subject_a1", reward_name="قهوة مجانية",
                          cost=50, remaining=100)

    async def race():
        return await asyncio.gather(
            engine._claim("t1", dict(row), at(10)),
            I.redemption(_fake_request(container), body))

    claimed, merged = run(race())

    # THE LOCK, NOT LUCK, DECIDES THE OUTCOME. Exactly which of the two legitimate refusal reasons
    # ("the lock is held" vs. "the row is no longer pending by the time I could look") comes back
    # depends on the exact interleaving order asyncio happens to pick — both are the lock working.
    # What must NEVER happen, in either order, is `merged: True`: that would mean redemption wrote
    # its fields onto a row a tick had already claimed for sending, the exact stomp this test guards.
    assert claimed is True
    assert merged["merged"] is False, (
        "without the shared lock this used to blind-upsert the stale 'pending' copy it already "
        "read, right over the row the tick was mid-claim on")
    stored = run(ScheduleStore(st).get(s.key))
    assert stored["state"] == "sending", "the claim must win the race cleanly, with no stomped write"
    assert "redeemed_name" not in stored, (
        "a redemption that lost the race must never have written its fields onto the claimed row")
