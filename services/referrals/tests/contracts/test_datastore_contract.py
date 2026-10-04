"""DataStore contract — every DataStore adapter must satisfy this."""
from __future__ import annotations

import os

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from tests.contracts.util import run

# The postgres adapter is held to the SAME contract, against a REAL server, whenever
# DATASTORE_TEST_DSN is set. Without this parameter the contract only ever proved that the
# in-memory adapter agrees with itself — and its asyncio.Lock serialises writers, hiding every
# race a real database has to handle. Sixteen of these files had no postgres param at all, and
# the CI gate could not see it: the gate fails on a SKIPPED param, and a param that does not
# exist is never skipped.
#
#   docker run -d -e POSTGRES_PASSWORD=pw -p 5432:5432 postgres:16-alpine
#   DATASTORE_TEST_DSN=postgresql://postgres:pw@127.0.0.1:5432/postgres pytest tests/contracts
_PG_DSN = os.environ.get("DATASTORE_TEST_DSN", "")


def _memory():
    return MemoryDataStore()


def _postgres():
    from app.adapters.datastore.postgres import PostgresDataStore

    store = PostgresDataStore(_PG_DSN)

    async def _reset():
        pool = await store._ensure()
        await pool.execute("TRUNCATE kv_store")

    run(_reset())
    return store


_PARAMS = [pytest.param(_memory, id="memory")]
if _PG_DSN:
    _PARAMS.append(pytest.param(_postgres, id="postgres"))
else:
    _PARAMS.append(pytest.param(
        _postgres, id="postgres",
        marks=pytest.mark.skip(reason="set DATASTORE_TEST_DSN to run the postgres contract")))


@pytest.fixture(params=_PARAMS)
def store(request):
    s = request.param()
    yield s
    run(s.close())


def test_put_get_roundtrip(store):
    run(store.put("things", "a", {"n": 1}))
    assert run(store.get("things", "a")) == {"n": 1}


def test_get_missing_returns_none(store):
    assert run(store.get("things", "nope")) is None


def test_delete(store):
    run(store.put("things", "a", {"n": 1}))
    assert run(store.delete("things", "a")) is True
    assert run(store.delete("things", "a")) is False
    assert run(store.get("things", "a")) is None


def test_list_and_collection_isolation(store):
    run(store.put("c1", "a", {"n": 1}))
    run(store.put("c1", "b", {"n": 2}))
    run(store.put("c2", "a", {"n": 9}))
    assert len(run(store.list("c1"))) == 2
    assert len(run(store.list("c2"))) == 1


def test_returned_value_is_isolated_copy(store):
    run(store.put("c", "a", {"n": 1}))
    got = run(store.get("c", "a"))
    got["n"] = 999
    assert run(store.get("c", "a")) == {"n": 1}


def test_health(store):
    assert run(store.health()) is True


# ── find(): the primitive that replaced the full-collection scan ─────────────
# These must hold IDENTICALLY on both adapters. Where they do not, a repository that passes its
# unit tests against the memory store is wrong in production and nothing says so.


def _seed_rows(store, collection="rows"):
    for i in range(6):
        run(store.put(collection, f"k{i}", {"id": f"k{i}", "tenant": "t1" if i < 4 else "t2",
                                            "status": "open" if i % 2 == 0 else "done",
                                            "created": f"2026-01-{i + 1:02d}"}))


def test_find_pushes_the_filter_down(store):
    _seed_rows(store)
    rows, _ = run(store.find("rows", {"tenant": "t1"}, limit=100))
    assert {r["id"] for r in rows} == {"k0", "k1", "k2", "k3"}


def test_find_supports_membership(store):
    _seed_rows(store)
    rows, _ = run(store.find("rows", {"tenant": "t1", "status": ["open", "done"]}, limit=100))
    assert len(rows) == 4


def test_find_refuses_an_empty_filter(store):
    """`find(c, {})` would return every tenant's rows — a leak one typo away."""
    from app.ports.errors import ConfigError

    with pytest.raises(ConfigError):
        run(store.find("rows", {}))


def test_find_refuses_an_unknown_sort_direction(store):
    from app.ports.errors import ConfigError

    with pytest.raises(ConfigError):
        run(store.find("rows", {"tenant": "t1"}, sort=("created", "sideways")))


def test_find_orders_both_ways(store):
    _seed_rows(store)
    asc, _ = run(store.find("rows", {"tenant": "t1"}, limit=10, sort=("created", "asc")))
    desc, _ = run(store.find("rows", {"tenant": "t1"}, limit=10, sort=("created", "desc")))
    assert [r["id"] for r in asc] == ["k0", "k1", "k2", "k3"]
    assert [r["id"] for r in desc] == ["k3", "k2", "k1", "k0"]


def test_find_orders_numeric_values_numerically(store):
    # A NUMERIC sort field must order numerically, not as text. Text ordering put "100" before "9",
    # mis-ordering every "oldest-first" priority view (audit compliance-05 / identity-02). Memory has
    # always been numeric; this pins postgres to the same contract.
    for i, ts in enumerate([9.0, 100.0, 20.0, 3.0]):
        run(store.put("nums", f"n{i}", {"id": f"n{i}", "tenant": "t1", "created": ts}))
    asc, _ = run(store.find("nums", {"tenant": "t1"}, limit=10, sort=("created", "asc")))
    assert [r["created"] for r in asc] == [3.0, 9.0, 20.0, 100.0]


def test_find_pages_without_overlap_or_gap(store):
    _seed_rows(store)
    seen, cursor = [], None
    while True:
        page, cursor = run(store.find("rows", {"tenant": "t1"}, limit=2, after=cursor))
        seen.extend(r["id"] for r in page)
        if not cursor:
            break
    assert sorted(seen) == ["k0", "k1", "k2", "k3"]
    assert len(seen) == len(set(seen))


def test_find_returns_no_cursor_on_the_last_page(store):
    _seed_rows(store)
    rows, cursor = run(store.find("rows", {"tenant": "t1"}, limit=100))
    assert len(rows) == 4 and cursor is None


def test_a_row_inserted_between_pages_is_never_skipped(store):
    """An OFFSET would skip one here. A keyset cursor cannot."""
    _seed_rows(store)
    page1, cursor = run(store.find("rows", {"tenant": "t1"}, limit=2))       # newest two
    run(store.put("rows", "new", {"id": "new", "tenant": "t1", "status": "open",
                                  "created": "2026-12-31"}))                 # arrives at the top
    page2, _ = run(store.find("rows", {"tenant": "t1"}, limit=4, after=cursor))
    ids = [r["id"] for r in page1] + [r["id"] for r in page2]
    assert len(ids) == len(set(ids)), "a row came back twice"
    assert {"k0", "k1"} <= set(ids), "a row was skipped"


def test_rows_sharing_a_sort_value_do_not_straddle_a_page_boundary(store):
    """Without the id tie-break the order is not total, and a page boundary drops a row."""
    for i in range(6):
        run(store.put("tied", f"t{i}", {"id": f"t{i}", "tenant": "t1", "created": "same"}))
    seen, cursor = [], None
    while True:
        page, cursor = run(store.find("tied", {"tenant": "t1"}, limit=2, after=cursor))
        seen.extend(r["id"] for r in page)
        if not cursor:
            break
    assert sorted(seen) == [f"t{i}" for i in range(6)]


def test_a_corrupt_cursor_restarts_rather_than_crashing(store):
    _seed_rows(store)
    rows, _ = run(store.find("rows", {"tenant": "t1"}, after="not-a-real-cursor"))
    assert len(rows) == 4


def test_find_returns_an_isolated_copy(store):
    _seed_rows(store)
    rows, _ = run(store.find("rows", {"tenant": "t1"}, limit=1))
    rows[0]["tenant"] = "MUTATED"
    again, _ = run(store.find("rows", {"tenant": "t1"}, limit=1))
    assert again[0]["tenant"] == "t1"


def test_find_on_an_absent_field_matches_nothing(store):
    """An "operator" is just a field name that does not exist. Nothing is evaluated."""
    _seed_rows(store)
    rows, _ = run(store.find("rows", {"$ne": "t1"}, limit=10))
    assert rows == []


def test_scan_all_is_deterministic_when_truncated(store):
    """It may truncate — it must not truncate ARBITRARILY. The old list() had no ORDER BY."""
    _seed_rows(store)
    first = [r["id"] for r in run(store.scan_all("rows", 3))]
    second = [r["id"] for r in run(store.scan_all("rows", 3))]
    assert first == second and len(first) == 3


# ── claim(): the atomic take-if-absent-or-expired primitive ──────────────────────────────────
# A REAL GAP THIS PINS DOWN — `claim()` exists on the port (added 2026-09-07, coworking/campaigns
# both depend on it for their own double-booking/double-payout locks) but not one service in this
# fleet had a contract test proving BOTH adapters actually honour it before this file did. A memory
# adapter that "claims" via plain dict assignment and a postgres adapter whose ON CONFLICT clause
# has a typo would both pass every OTHER test here and silently double-grant the exact thing this
# primitive exists to prevent.


def test_claim_wins_when_nobody_holds_the_key(store):
    won = run(store.claim("locks", "k1", {"who": "a"}, ttl_seconds=30, now=1000.0))
    assert won is True
    assert run(store.get("locks", "k1"))["who"] == "a"


def test_claim_loses_against_an_unexpired_holder(store):
    run(store.claim("locks", "k1", {"who": "a"}, ttl_seconds=30, now=1000.0))
    lost = run(store.claim("locks", "k1", {"who": "b"}, ttl_seconds=30, now=1010.0))
    assert lost is False
    # THE LOSER'S VALUE NEVER LANDS — a claim that overwrote the row on failure would let a racing
    # second caller silently replace the winner's own payload even while correctly returning False.
    assert run(store.get("locks", "k1"))["who"] == "a"


def test_claim_wins_again_once_the_holder_has_expired(store):
    run(store.claim("locks", "k1", {"who": "a"}, ttl_seconds=10, now=1000.0))
    won = run(store.claim("locks", "k1", {"who": "b"}, ttl_seconds=30, now=1011.0))
    assert won is True
    assert run(store.get("locks", "k1"))["who"] == "b"


def test_claim_is_atomic_under_real_concurrency(store):
    """Sequential calls prove the LOGIC; this proves the ATOMICITY — the one thing a naive
    read-then-write "claim" (get, check absent, put) cannot give you, and the one thing this
    primitive exists to replace. Mirrors campaigns' own concurrent-contribution stress test:
    a store wrapper that forces real interleaving (an await between every "check" and "write" a
    racy implementation would perform) is the only way a bug here would ever actually show up —
    a fast in-process loop with no real interleaving would pass a broken implementation too."""
    import asyncio

    attempts = 12
    results: list[bool] = []

    async def _one():
        results.append(await store.claim("race", "k1", {"n": 1}, ttl_seconds=30, now=1000.0))

    async def _all():
        await asyncio.gather(*(_one() for _ in range(attempts)))

    run(_all())
    assert results.count(True) == 1, "more than one concurrent claim on the same key won"
    assert results.count(False) == attempts - 1
