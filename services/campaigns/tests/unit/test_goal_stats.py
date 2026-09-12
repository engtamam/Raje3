"""The per-goal usage/reach side record — a single-key read, same move `locks.py` already made."""
from __future__ import annotations

import asyncio

from app.adapters.datastore.memory import MemoryDataStore
from app.core.goal_stats import read_goal_stats, record_reach, record_use


def run(c):
    return asyncio.run(c)


def test_a_tenant_never_used_reads_back_empty():
    st = MemoryDataStore()
    assert run(read_goal_stats(st, "t1")) == {}


def test_a_use_is_counted():
    st = MemoryDataStore()
    run(record_use(st, "t1", "win_back"))
    assert run(read_goal_stats(st, "t1")) == {"win_back": {"uses": 1, "reach": 0}}


def test_repeated_uses_accumulate():
    st = MemoryDataStore()
    run(record_use(st, "t1", "win_back"))
    run(record_use(st, "t1", "win_back"))
    run(record_use(st, "t1", "win_back"))
    assert run(read_goal_stats(st, "t1")) == {"win_back": {"uses": 3, "reach": 0}}


def test_reach_accumulates_across_runs():
    st = MemoryDataStore()
    run(record_use(st, "t1", "win_back"))
    run(record_reach(st, "t1", "win_back", 40))
    run(record_reach(st, "t1", "win_back", 12))
    assert run(read_goal_stats(st, "t1")) == {"win_back": {"uses": 1, "reach": 52}}


def test_a_zero_or_negative_reach_writes_nothing():
    st = MemoryDataStore()
    run(record_use(st, "t1", "win_back"))
    run(record_reach(st, "t1", "win_back", 0))
    run(record_reach(st, "t1", "win_back", -5))
    assert run(read_goal_stats(st, "t1")) == {"win_back": {"uses": 1, "reach": 0}}


def test_an_empty_goal_writes_nothing():
    st = MemoryDataStore()
    run(record_use(st, "t1", ""))
    run(record_reach(st, "t1", "", 10))
    assert run(read_goal_stats(st, "t1")) == {}


def test_goals_do_not_clobber_each_other():
    st = MemoryDataStore()
    run(record_use(st, "t1", "win_back"))
    run(record_use(st, "t1", "occasion"))
    run(record_reach(st, "t1", "win_back", 10))
    run(record_reach(st, "t1", "occasion", 3))
    assert run(read_goal_stats(st, "t1")) == {
        "win_back": {"uses": 1, "reach": 10},
        "occasion": {"uses": 1, "reach": 3},
    }


def test_stats_are_scoped_per_tenant():
    st = MemoryDataStore()
    run(record_use(st, "t1", "win_back"))
    run(record_use(st, "t2", "win_back"))
    run(record_reach(st, "t1", "win_back", 5))
    assert run(read_goal_stats(st, "t1")) == {"win_back": {"uses": 1, "reach": 5}}
    assert run(read_goal_stats(st, "t2")) == {"win_back": {"uses": 1, "reach": 0}}


class _SlowStore:
    """Same race-widening wrapper `test_locks.py` already uses — stalls between `get` and `put`
    so a non-atomic read-modify-write is caught deterministically instead of needing luck."""

    def __init__(self, inner):
        self._inner = inner

    async def get(self, collection, key):
        row = await self._inner.get(collection, key)
        await asyncio.sleep(0.01)
        return row

    async def put(self, collection, key, value):
        return await self._inner.put(collection, key, value)

    async def delete(self, collection, key):
        return await self._inner.delete(collection, key)

    async def claim(self, collection, key, value, *, ttl_seconds, now):
        return await self._inner.claim(collection, key, value, ttl_seconds=ttl_seconds, now=now)


def test_two_genuinely_concurrent_writers_never_lose_a_use():
    """Two campaigns of the same goal created in the same instant (two pods, or a retype race)
    must not have one writer's increment overwrite the other's — the mutex around the
    read-modify-write must serialise them rather than let them interleave."""
    st = _SlowStore(MemoryDataStore())

    async def race():
        await asyncio.gather(
            record_use(st, "t1", "win_back"),
            record_use(st, "t1", "win_back"),
        )

    run(race())
    assert run(read_goal_stats(st, "t1")) == {"win_back": {"uses": 2, "reach": 0}}
