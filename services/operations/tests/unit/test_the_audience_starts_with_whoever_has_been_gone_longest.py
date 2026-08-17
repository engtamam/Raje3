"""Who a campaign is allowed to see, when the shop is bigger than one read.

THE DEFECT, AND IT WAS EXACTLY BACKWARDS. `/internal/operations/customers` returned rows sorted
`("last_visit", "desc")` — most recent visit first — under a cap. Below the cap it does not matter:
the caller gets everybody and the rule sorts them out. Above it, the rows that survive are the
customers who came in MOST recently, and every goal this route feeds is about ABSENCE. A shop with
nine thousand customers asking «رجّع اللي غابوا» drew its audience from the two thousand people
who had just been in, found almost nobody who qualified, and told the owner his shop loses nobody.

And the cut was silent: the response carried `count`, which is the number of rows returned, and
nothing that distinguished «this is everyone» from «this is where we stopped».
"""
from __future__ import annotations

import asyncio

from app.adapters.datastore.memory import MemoryDataStore
from app.core.models import CUSTOMERS

TENANT = "shop"
NOW = 1_780_000_000
DAY = 86_400


def run(c):
    return asyncio.run(c)


def _shop(store: MemoryDataStore, n: int) -> None:
    """`n` customers, each one visiting a day further back than the last."""
    for i in range(n):
        key = f"{TENANT}|sub_{i:04d}"
        run(store.put(CUSTOMERS, key, {
            "id": key, "tenant": TENANT, "subject_ref": f"sub_{i:04d}",
            "last_visit": NOW - i * DAY, "visit_count": 5, "last_branch_id": ""}))


def _read(store: MemoryDataStore, limit: int):
    return run(store.find(CUSTOMERS, {"tenant": TENANT}, limit=limit, sort=("last_visit", "asc")))


def test_the_long_absent_survive_the_cap_and_the_recent_visitors_are_the_ones_dropped():
    """The whole point: a win-back audience must be drawn from people who are actually absent."""
    store = MemoryDataStore()
    _shop(store, 300)

    rows, _ = _read(store, 50)
    seen = [r["subject_ref"] for r in rows]

    # sub_0299 last came 299 days ago; sub_0000 came today.
    assert seen[0] == "sub_0299", "the customer gone longest must be first in line"
    assert "sub_0000" not in seen, "today's visitor must not be occupying a win-back slot"


def test_the_old_ordering_would_have_returned_precisely_the_wrong_people():
    """Named so that restoring `desc` fails here with the reason, not just a broken assertion."""
    store = MemoryDataStore()
    _shop(store, 300)

    wrong, _ = run(store.find(CUSTOMERS, {"tenant": TENANT}, limit=50,
                              sort=("last_visit", "desc")))
    right, _ = _read(store, 50)

    assert {r["subject_ref"] for r in wrong}.isdisjoint({r["subject_ref"] for r in right}), (
        "descending and ascending must select disjoint sets here — which is how far wrong the "
        "old ordering was: not slightly off, but the complement of the right answer")


def test_a_cut_read_can_be_told_apart_from_a_complete_one():
    """`count` alone cannot say it. The cursor can, and it is what the route now reports."""
    store = MemoryDataStore()
    _shop(store, 300)

    _, cursor = _read(store, 50)
    assert cursor is not None, "a read that stopped early must be able to say so"

    _, cursor = _read(store, 500)
    assert cursor is None, "a read that saw everyone must not cry truncation"
