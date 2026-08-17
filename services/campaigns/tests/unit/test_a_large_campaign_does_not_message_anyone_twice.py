"""The exclusion set is the only thing standing between a customer and a second copy of an offer.

WHAT BROKE, AND HOW LOUD IT WAS NOT. `_already_reached` asked the store for the campaign's reached
rows with `limit=10000, sort=("at", "asc")` and threw away the cursor. Below ten thousand that is
the whole set and everything works. Above it, the rows that fall off the end are the ones written
LAST — the people reached most recently. They come back as candidates on the next pass, are sent
to again, and the run counts them as `sent` exactly like a first-time recipient. There is no error,
no warning, and no way to tell the second message from the first in any report we produce.

These tests use a small page size rather than ten thousand rows, because the defect is the shape,
not the number: a store that returns fewer rows than exist, and a caller that cannot tell.
"""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.drain import TooMuchToRead, drain
from app.adapters.datastore.memory import MemoryDataStore

TENANT = "shop"
CAMPAIGN = "cmp_1"
REACHED = "campaign_reached"


def run(c):
    return asyncio.run(c)


def _fill(store: MemoryDataStore, n: int) -> list[str]:
    subjects = [f"sub_{i:04d}" for i in range(n)]
    for i, s in enumerate(subjects):
        key = f"{TENANT}|{CAMPAIGN}|{s}"
        run(store.put(REACHED, key, {"id": key, "tenant": TENANT, "campaign_id": CAMPAIGN,
                                     "subject_ref": s, "at": 1_700_000_000 + i}))
    return subjects


def test_everyone_already_reached_is_still_in_the_set_past_one_page():
    """The whole defect in one assertion: nobody who was reached may go missing."""
    store = MemoryDataStore()
    subjects = _fill(store, 250)

    rows = run(drain(store, REACHED, {"tenant": TENANT, "campaign_id": CAMPAIGN},
                     sort=("at", "asc"), page=25))
    assert {r["subject_ref"] for r in rows} == set(subjects)


def test_the_most_recently_reached_are_the_ones_a_single_page_loses():
    """Named because it is the cruel part: the people at risk are the ones we JUST messaged."""
    store = MemoryDataStore()
    subjects = _fill(store, 250)

    # What the old code did — one capped, ascending read, cursor discarded.
    page, _ = run(store.find(REACHED, {"tenant": TENANT, "campaign_id": CAMPAIGN},
                             limit=25, sort=("at", "asc")))
    truncated = {r["subject_ref"] for r in page}
    drained = {r["subject_ref"] for r in
               run(drain(store, REACHED, {"tenant": TENANT, "campaign_id": CAMPAIGN},
                         sort=("at", "asc"), page=25))}

    missing = drained - truncated
    assert subjects[-1] in missing, "the last person reached must be the first one lost"
    assert len(missing) == 225


def test_a_set_too_large_to_read_raises_rather_than_returning_part_of_itself():
    """FAIL LOUDLY. A partial exclusion set is indistinguishable from a complete one."""
    store = MemoryDataStore()
    _fill(store, 300)

    with pytest.raises(TooMuchToRead):
        run(drain(store, REACHED, {"tenant": TENANT, "campaign_id": CAMPAIGN},
                  sort=("at", "asc"), page=25, budget=100))


def test_an_empty_set_is_an_empty_set_and_not_an_error():
    """A campaign that has reached nobody is the normal first pass, not a failure."""
    store = MemoryDataStore()
    assert run(drain(store, REACHED, {"tenant": TENANT, "campaign_id": CAMPAIGN},
                     sort=("at", "asc"), page=25)) == []
