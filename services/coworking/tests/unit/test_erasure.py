from __future__ import annotations

import asyncio

from app.adapters.datastore.memory import MemoryDataStore
from app.core.bookings import BookingService
from app.core.erasure import CoworkingErasure
from app.core.joins import JoinRegistry
from app.core.pause import PauseSettings
from app.core.resources import ResourceService

TENANT = "t1"
PHONE = "+966501234567"
SALT = "s" * 32


def test_erase_deletes_join_and_redacts_bookings_but_keeps_the_schedule_fact():
    async def run():
        store = MemoryDataStore()
        resources = ResourceService(store=store)
        joins = JoinRegistry(store=store)
        pause = PauseSettings(store=store)
        bookings = BookingService(store=store, resources=resources, joins=joins, pause=pause)

        r = await resources.create(TENANT, name="كرسي 1")
        await resources.set_availability(TENANT, r.id, weekly={d: [(0, 24 * 60)] for d in range(7)},
                                         hourly_price_minor=5000)
        await joins.ensure_pending(TENANT, PHONE)
        await joins.approve(TENANT, PHONE)
        booking = await bookings.create(TENANT, resource_id=r.id, phone=PHONE,
                                        starts_at=1_800_000_000, ends_at=1_800_003_600)

        eraser = CoworkingErasure(store=store, pii_salt=SALT)
        result = await eraser.erase(TENANT, PHONE)

        assert await joins.status(TENANT, PHONE) is None
        row = await store.get("coworking_bookings", booking["id"])
        assert row["freelancer_phone"] != PHONE
        assert row["resource_id"] == r.id            # the operational fact survives
        assert row["hourly_price_minor"] == 5000
        return result

    result = asyncio.run(run())
    assert result["already_absent"] is False
    assert result["erased"]
    assert result["retained"]


def test_erase_on_a_phone_with_no_rows_reports_already_absent():
    async def run():
        store = MemoryDataStore()
        eraser = CoworkingErasure(store=store, pii_salt=SALT)
        return await eraser.erase(TENANT, PHONE)

    result = asyncio.run(run())
    assert result["already_absent"] is True


def test_erase_is_idempotent():
    async def run():
        store = MemoryDataStore()
        resources = ResourceService(store=store)
        joins = JoinRegistry(store=store)
        await joins.ensure_pending(TENANT, PHONE)
        eraser = CoworkingErasure(store=store, pii_salt=SALT)
        first = await eraser.erase(TENANT, PHONE)
        second = await eraser.erase(TENANT, PHONE)
        return first, second

    first, second = asyncio.run(run())
    assert second["already_absent"] is True
