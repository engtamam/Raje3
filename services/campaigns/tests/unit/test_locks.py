"""The awareness lock side record — a single-key read instead of a campaign scan."""
from __future__ import annotations

import asyncio

from app.adapters.datastore.memory import MemoryDataStore
from app.core.locks import read_locks, record_lock


def run(c):
    return asyncio.run(c)


def test_a_tenant_with_no_locks_reads_back_empty():
    st = MemoryDataStore()
    assert run(read_locks(st, "t1")) == {}


def test_a_recorded_lock_is_read_back():
    st = MemoryDataStore()
    run(record_lock(st, "t1", "awareness", 1_000))
    assert run(read_locks(st, "t1")) == {"awareness": 1_000}


def test_recording_a_lower_until_does_not_lower_it():
    """Matches the scan it replaced, which took the MAX across every campaign carrying a lock for
    that goal — a second, earlier lock must not shorten one already recorded."""
    st = MemoryDataStore()
    run(record_lock(st, "t1", "awareness", 2_000))
    run(record_lock(st, "t1", "awareness", 500))
    assert run(read_locks(st, "t1")) == {"awareness": 2_000}


def test_recording_a_later_until_raises_it():
    st = MemoryDataStore()
    run(record_lock(st, "t1", "awareness", 500))
    run(record_lock(st, "t1", "awareness", 2_000))
    assert run(read_locks(st, "t1")) == {"awareness": 2_000}


def test_locks_for_different_goals_do_not_clobber_each_other():
    st = MemoryDataStore()
    run(record_lock(st, "t1", "awareness", 1_000))
    run(record_lock(st, "t1", "service_offer", 2_000))
    assert run(read_locks(st, "t1")) == {"awareness": 1_000, "service_offer": 2_000}


def test_locks_are_scoped_per_tenant():
    st = MemoryDataStore()
    run(record_lock(st, "t1", "awareness", 1_000))
    run(record_lock(st, "t2", "awareness", 2_000))
    assert run(read_locks(st, "t1")) == {"awareness": 1_000}
    assert run(read_locks(st, "t2")) == {"awareness": 2_000}


def test_an_empty_goal_or_zero_until_writes_nothing():
    st = MemoryDataStore()
    run(record_lock(st, "t1", "", 1_000))
    run(record_lock(st, "t1", "awareness", 0))
    assert run(read_locks(st, "t1")) == {}
