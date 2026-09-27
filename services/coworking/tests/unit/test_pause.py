from __future__ import annotations

import asyncio

from app.adapters.datastore.memory import MemoryDataStore
from app.core.pause import PauseSettings


def test_default_is_not_paused():
    async def run():
        p = PauseSettings(store=MemoryDataStore())
        return await p.is_paused("t1")

    assert asyncio.run(run()) is False


def test_set_and_read_back():
    async def run():
        p = PauseSettings(store=MemoryDataStore())
        await p.set_paused("t1", True)
        return await p.is_paused("t1")

    assert asyncio.run(run()) is True


def test_scoped_per_tenant():
    async def run():
        p = PauseSettings(store=MemoryDataStore())
        await p.set_paused("t1", True)
        return await p.is_paused("t2")

    assert asyncio.run(run()) is False
