"""PostgresDataStore/PhoneSearchReadOnly's lazy pool create — the race worth a test:

THE BUG: `_ensure()`/`_get_pool()` checked `self._pool is None` with no lock around it. Two
concurrent first-requests could both see `None`, both await `create_pool(...)`, and the loser's
assignment silently discarded whichever pool the winner already opened — leaking its connections
for the life of the process (nothing holds a reference to it any more to `close()` it).

Fixed with an `asyncio.Lock` guarding the create — this drives two concurrent callers through a
fake `asyncpg` whose `create_pool` yields control (so the race window is real, not accidental
serialisation from never awaiting) and asserts it is called exactly once.
"""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.phone_search_ro import PhoneSearchReadOnly
from app.adapters.datastore.postgres import PostgresDataStore


class _FakeConnection:
    async def execute(self, *args, **kwargs):
        return "OK"

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _FakePool:
    def acquire(self, *args, **kwargs):
        return _FakeConnection()


class _FakeAsyncpg:
    """Counts `create_pool` calls and yields control before returning, so two coroutines racing
    `_ensure()`/`_get_pool()` genuinely interleave rather than one finishing before the other even
    starts — exactly the shape a real network round trip to open a pool has."""

    def __init__(self) -> None:
        self.create_pool_calls = 0

    async def create_pool(self, *args, **kwargs):
        self.create_pool_calls += 1
        await asyncio.sleep(0)   # the race window a missing lock used to leave open
        return _FakePool()


@pytest.mark.anyio
async def test_postgres_datastore_creates_the_pool_exactly_once_under_concurrency():
    store = PostgresDataStore("postgres://fake/db")
    fake = _FakeAsyncpg()
    store._asyncpg = fake   # bypass the real driver — this test is about the lock, not asyncpg

    await asyncio.gather(store._ensure(), store._ensure(), store._ensure())

    assert fake.create_pool_calls == 1


@pytest.mark.anyio
async def test_phone_search_ro_creates_the_pool_exactly_once_under_concurrency():
    reader = PhoneSearchReadOnly("postgres://fake/db")
    fake = _FakeAsyncpg()
    reader._asyncpg = fake

    await asyncio.gather(reader._get_pool(), reader._get_pool(), reader._get_pool())

    assert fake.create_pool_calls == 1
