"""و-1 — the fleet round was alphabetical by tenant, and one shop ate the whole page.

THE CHAIN. `insights` derived its tenant list from a page of `/operations/visits/since` with no
tenant filter. That path is a `scan_all`, and `scan_all` orders by KEY — a visit's key is
`tenant|visit_id`. So the five hundred rows it returned were five hundred visits belonging to
whichever establishment sorts first alphabetically, and the tenant list came back with ONE name
in it.

WHAT THAT MEANS ON A REAL CLUSTER. Forty shops, three hundred thousand visits. The snapshot cron
runs every night and every night it is told there is one tenant. The other thirty-nine have their
dashboard computed once — the first time somebody opens it — and served unchanged from then on:
«0 عميل نشط» to a shop whose till has not stopped ringing, for ever, and no error anywhere.

Nobody wrote a bug. The question «who exists» was answered as a side effect of «give me some
visits», and the size of one shop became able to hide every other shop.
"""
from __future__ import annotations

import asyncio

from app.adapters.datastore.memory import MemoryDataStore
from app.core.models import VISITS

NOW = 1_780_000_000


def run(c):
    return asyncio.run(c)


def _fleet(store: MemoryDataStore) -> None:
    """One enormous shop whose id sorts first, and nine ordinary ones after it."""
    for i in range(5_000):
        key = f"aaa_busy|v{i:06d}"
        run(store.put(VISITS, key, {"id": f"v{i:06d}", "tenant": "aaa_busy",
                                    "customer_id": f"c{i}", "created": NOW - i}))
    for shop in range(9):
        name = f"shop_{shop:02d}"
        for i in range(3):
            key = f"{name}|v{i}"
            run(store.put(VISITS, key, {"id": f"v{i}", "tenant": name,
                                        "customer_id": f"c{i}", "created": NOW - i}))


def _tenants_from_one_page(store: MemoryDataStore, page: int) -> set[str]:
    """What the old path did: one window of visits, and infer the tenants from it."""
    rows = run(store.scan_all(VISITS, limit=page))
    return {r["tenant"] for r in rows}


def _tenants_paged(store: MemoryDataStore, page: int = 1000) -> set[str]:
    """What the route does now: walk the whole collection keeping only the names."""
    found: set[str] = set()
    after = None
    while True:
        rows = run(store.scan_all(VISITS, limit=page, after=after))
        if not rows:
            break
        found.update(r["tenant"] for r in rows)
        if len(rows) < page:
            break
        after = f"{rows[-1]['tenant']}|{rows[-1]['id']}"
    return found


def test_one_page_of_visits_finds_exactly_one_shop():
    """The defect, reproduced. Not «most shops» — one."""
    store = MemoryDataStore()
    _fleet(store)

    assert _tenants_from_one_page(store, 500) == {"aaa_busy"}


def test_walking_the_collection_finds_all_ten():
    store = MemoryDataStore()
    _fleet(store)

    found = _tenants_paged(store)
    assert found == {"aaa_busy"} | {f"shop_{i:02d}" for i in range(9)}
    assert len(found) == 10


def test_the_names_cost_a_set_of_strings_however_many_visits_stand_behind_them():
    """Why this is a route of its own: the answer's size is the number of SHOPS, not of visits."""
    store = MemoryDataStore()
    _fleet(store)

    assert len(_tenants_paged(store)) == 10
    assert len(run(store.scan_all(VISITS, limit=100_000))) == 5_027
