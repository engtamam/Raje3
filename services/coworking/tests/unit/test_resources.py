from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.resources import ResourceError, ResourceService

TENANT = "t1"


def test_create_then_list():
    async def run():
        svc = ResourceService(store=MemoryDataStore())
        r = await svc.create(TENANT, name="كرسي 1")
        rows = await svc.list(TENANT)
        return r, rows

    r, rows = asyncio.run(run())
    assert r.active is True
    assert r.hourly_price_minor == 0
    assert len(rows) == 1 and rows[0].id == r.id


def test_blank_name_refused():
    async def run():
        svc = ResourceService(store=MemoryDataStore())
        with pytest.raises(ResourceError):
            await svc.create(TENANT, name="   ")

    asyncio.run(run())


def test_update_active_flag_never_touches_name():
    async def run():
        svc = ResourceService(store=MemoryDataStore())
        r = await svc.create(TENANT, name="كرسي 1")
        updated = await svc.update(TENANT, r.id, active=False)
        return updated

    updated = asyncio.run(run())
    assert updated.active is False
    assert updated.name == "كرسي 1"


def test_get_from_another_tenant_is_indistinguishable_from_missing():
    async def run():
        svc = ResourceService(store=MemoryDataStore())
        r = await svc.create("shopA", name="كرسي 1")
        return await svc.get("shopB", r.id)

    assert asyncio.run(run()) is None


def test_set_availability_rejects_bad_windows():
    async def run():
        svc = ResourceService(store=MemoryDataStore())
        r = await svc.create(TENANT, name="كرسي 1")
        with pytest.raises(ResourceError):
            await svc.set_availability(TENANT, r.id, weekly={0: [(700, 500)]},
                                       hourly_price_minor=1000)

    asyncio.run(run())


def test_set_availability_rejects_negative_price():
    async def run():
        svc = ResourceService(store=MemoryDataStore())
        r = await svc.create(TENANT, name="كرسي 1")
        with pytest.raises(ResourceError):
            await svc.set_availability(TENANT, r.id, weekly={0: [(540, 600)]},
                                       hourly_price_minor=-1)

    asyncio.run(run())


def test_set_availability_round_trips():
    async def run():
        svc = ResourceService(store=MemoryDataStore())
        r = await svc.create(TENANT, name="كرسي 1")
        updated = await svc.set_availability(
            TENANT, r.id, weekly={0: [(540, 720)]},
            exceptions={"2026-09-27": {"closed": True, "windows": []}},
            hourly_price_minor=5000)
        return updated

    updated = asyncio.run(run())
    assert updated.hourly_price_minor == 5000
    assert updated.weekly == {"0": [[540, 720]]}
    assert updated.exceptions["2026-09-27"]["closed"] is True
