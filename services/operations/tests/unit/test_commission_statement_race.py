"""Verified race (operations audit, 2026-09-12): `StatementStore.save` (the monthly sweep
recomputing a statement) and `StatementStore.set_state` (an operator marking it paid or disputed)
are both get-then-put on the SAME row with no compare-and-set. Landing at the same moment, `save`
can read the row BEFORE the operator's write lands and then overwrite it, silently reverting a
statement an operator just marked paid back to "issued" — exactly what `save`'s own docstring says
must never happen. Proved with the same slow-yielding store wrapper this service's own
test_customer_counter_race.py uses to force genuine interleaving.
"""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.commission import PAID, StatementBusy, StatementStore, build

JAN = 1_767_225_600
FEB = 1_769_904_000


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


def _statement():
    stamps = [{"tenant": "shop1", "partner_id": "prt_1", "commission_rate": 0.25}]
    settlements = {"shop1": {"settled_minor": 20000, "refunded_minor": 0}}
    return build(partner_id="prt_1", period_start=JAN, period_end=FEB,
                 stamps=stamps, settlements=settlements)


def test_a_recompute_racing_a_mark_paid_never_reverts_the_paid_status():
    store = _SlowStore(MemoryDataStore())
    statements = StatementStore(store)

    # Seed the row first, as the monthly sweep's first run would.
    run(statements.save(_statement()))

    async def go():
        return await asyncio.gather(
            statements.save(_statement()),
            statements.set_state("prt_1", JAN, state=PAID, actor="ops",
                                 reference="WIRE-1", at=1_767_300_000),
            return_exceptions=True)

    results = run(go())
    busy = [r for r in results if isinstance(r, StatementBusy)]
    ok = [r for r in results if not isinstance(r, Exception)]

    # ONE WINS, ONE IS REFUSED LOUDLY — never both silently succeeding with the paid status lost.
    assert len(busy) == 1, f"expected exactly one contender refused, got {results}"
    assert len(ok) == 1

    row = run(store._inner.get("commission_statements", "_platform|prt_1|1767225600"))
    # WHOEVER WON, THE ROW IS NEVER LEFT "issued" AFTER A SUCCESSFUL mark_paid: either set_state
    # ran (status is PAID) or it was refused as busy (status stays whatever save left it), but a
    # recompute must never be the one that silently clobbers a PAID row back to issued.
    if isinstance(results[1], dict):  # set_state's slot won
        assert row["status"] == PAID
