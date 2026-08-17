"""«BOUNDED AND RESUMABLE» was written in the docstring and was half true.

Bounded, yes. Resumable, no — there was no cursor anywhere in `sweep`. Every run read the same
`limit` rows, `created_at asc`, for ever. `more` was computed, returned, and read by nobody.

WHAT IT COSTS A REAL SHOP. Fifty thousand balances. Within a few weeks the oldest five hundred
have all been expired down to zero, so each night they are read, skipped as `points <= 0`, and
still fill the window. The other 49,500 customers never expire, and never receive the fourteen-day
warning that their points are about to go. The tick reports `expired: 0, seen: 500` — which is
indistinguishable from a sweep that has nothing to do.

And the reason the cursor could not simply be added is one layer down: `scan_all` had no `after`
at all. A walker whose store cannot say where it stopped can only ever walk the beginning.
"""
from __future__ import annotations

import asyncio

from app.adapters.datastore.memory import MemoryDataStore
from app.core.expiry import Expiry
from app.core.ledger import Ledger
from app.core.models import BALANCES

DAY = 86_400
NOW = 1_780_000_000
TENANT = "shop"


def run(c):
    return asyncio.run(c)


def _balances(store: MemoryDataStore, n: int, *, points: int, last_movement: int) -> None:
    for i in range(n):
        key = f"{TENANT}|sub_{i:04d}"
        run(store.put(BALANCES, key, {
            "id": key, "tenant": TENANT, "subject_ref": f"sub_{i:04d}", "points": points,
            "last_movement_at": last_movement, "created_at": last_movement + i,
            "expiry_warned_at": 0}))


def _sweeper(store: MemoryDataStore) -> Expiry:
    return Expiry(store, Ledger(store), days=365, warn_days=14)


def test_a_second_pass_sees_the_customers_the_first_one_did_not():
    """The whole defect: run twice, and the second run must be somewhere else."""
    store = MemoryDataStore()
    _balances(store, 12, points=50, last_movement=NOW - 400 * DAY)
    exp = _sweeper(store)

    first = run(exp.sweep(now=NOW, tenant=TENANT, limit=5))
    second = run(exp.sweep(now=NOW, tenant=TENANT, limit=5))

    assert first["expired"] == 5
    assert second["expired"] == 5, "the second pass must expire five DIFFERENT balances"
    assert first["more"] and second["more"]

    third = run(exp.sweep(now=NOW, tenant=TENANT, limit=5))
    assert third["expired"] == 2 and not third["more"], "the tail, and then the end"


def test_everybody_is_reached_eventually_and_nobody_is_stranded():
    """Fifty balances, ten at a time. All fifty must expire — not the first ten, five times."""
    store = MemoryDataStore()
    _balances(store, 50, points=30, last_movement=NOW - 400 * DAY)
    exp = _sweeper(store)

    total = 0
    for _ in range(10):
        total += run(exp.sweep(now=NOW, tenant=TENANT, limit=10))["expired"]
    assert total == 50


def test_the_cursor_wraps_so_the_newest_balances_are_not_swept_last_for_ever():
    """Reaching the end and starting again is correct; stopping at the end is the same bug."""
    store = MemoryDataStore()
    _balances(store, 6, points=10, last_movement=NOW - 400 * DAY)
    exp = _sweeper(store)

    run(exp.sweep(now=NOW, tenant=TENANT, limit=10))       # sees all six, cursor exhausted
    again = run(exp.sweep(now=NOW, tenant=TENANT, limit=10))
    assert again["seen"] == 6, "the next lap starts from the beginning, not from nowhere"


def test_the_store_can_say_where_a_scan_stopped():
    """The layer underneath, tested on its own because `sweep` cannot be fixed without it."""
    store = MemoryDataStore()
    _balances(store, 8, points=1, last_movement=NOW)

    page = run(store.scan_all(BALANCES, limit=3))
    assert len(page) == 3
    rest = run(store.scan_all(BALANCES, limit=3, after=page[-1]["id"]))
    assert [r["id"] for r in rest] != [r["id"] for r in page]
    assert len(rest) == 3
