"""The datastore's lazy first connection is made ONCE, however many requests arrive together.

Without the lock in `PostgresDataStore._ensure`, a fresh process's first burst of concurrent
requests each saw no pool, each opened one (leaking every pool but the last), and each raced
`CREATE TABLE IF NOT EXISTS` — which Postgres can refuse outright with a pg_type unique violation,
so the burst answered 500s. Found live: a fresh local stack's first concurrent booking creates.
A fake asyncpg stands in for the driver so this needs no database; its `create_pool` yields, which
is what lets the concurrent callers genuinely interleave the way real network I/O does.
"""
from __future__ import annotations

import asyncio

from app.adapters.datastore.postgres import PostgresDataStore


class _Con:
    def __init__(self, log: list[str]) -> None:
        self._log = log

    async def execute(self, sql: str, *args) -> str:
        await asyncio.sleep(0)
        self._log.append(sql.split("(")[0].strip())
        return "OK"


class _Acquire:
    def __init__(self, con: _Con) -> None:
        self._con = con

    async def __aenter__(self) -> _Con:
        return self._con

    async def __aexit__(self, *exc) -> None:
        return None


class _Pool:
    def __init__(self, log: list[str]) -> None:
        self._con = _Con(log)

    def acquire(self) -> _Acquire:
        return _Acquire(self._con)


class _FakeAsyncpg:
    def __init__(self) -> None:
        self.pools: list[_Pool] = []
        self.ddl: list[str] = []

    async def create_pool(self, *a, **kw) -> _Pool:
        await asyncio.sleep(0.01)          # a real connect takes time — long enough to interleave
        pool = _Pool(self.ddl)
        self.pools.append(pool)
        return pool


def test_concurrent_first_requests_open_one_pool_and_create_the_table_once():
    store = PostgresDataStore("postgresql://u:p@localhost/db")
    fake = _FakeAsyncpg()
    store._asyncpg = fake

    async def go():
        return await asyncio.gather(*(store._ensure() for _ in range(8)))

    pools = asyncio.run(go())
    assert len(fake.pools) == 1, f"{len(fake.pools)} pools opened for one store"
    assert all(p is fake.pools[0] for p in pools)
    assert sum(1 for s in fake.ddl if s.startswith("CREATE TABLE")) == 1
