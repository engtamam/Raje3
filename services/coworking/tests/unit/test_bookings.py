"""`app/core/bookings.py` — the whole spec acceptance table, table-driven where it can be.

`_SlowStore` (same trick as bookings' own `test_two_operators_cannot_take_the_same_slot.py`) makes
`find`/`get` actually yield the event loop, so an `asyncio.gather` of two overlapping booking
attempts genuinely interleaves against `MemoryDataStore` instead of running to completion one at a
time — without it, the concurrency test below would pass even with the lock deleted.
"""
from __future__ import annotations

import asyncio
import time

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.bookings import BookingRefused, BookingService, JoinRequired
from app.core.joins import JoinRegistry
from app.core.pause import PauseSettings
from app.core.resources import ResourceService

TENANT = "shop1"
PHONE = "+966501234567"

# A Sunday 09:00-17:00 window (day 6 in date.weekday()'s own numbering — Sunday).
SUNDAY_2026_08_16 = 1786860000 - (1786860000 % 86400)  # midnight-ish anchor, exact value unused


class _SlowStore:
    def __init__(self, inner: MemoryDataStore) -> None:
        self._inner = inner

    async def find(self, *a, **kw):
        await asyncio.sleep(0)
        return await self._inner.find(*a, **kw)

    async def get(self, *a, **kw):
        await asyncio.sleep(0)
        return await self._inner.get(*a, **kw)

    def __getattr__(self, name):
        return getattr(self._inner, name)


def _services(store):
    resources = ResourceService(store=store)
    joins = JoinRegistry(store=store)
    pause = PauseSettings(store=store)
    bookings = BookingService(store=store, resources=resources, joins=joins, pause=pause)
    return resources, joins, pause, bookings


async def _resource_open_all_week(resources, tenant="t1", price=5000):
    r = await resources.create(tenant, name="كرسي 1")
    weekly = {d: [(0, 24 * 60)] for d in range(7)}   # open every day, all day — simplest fixture
    await resources.set_availability(tenant, r.id, weekly=weekly, hourly_price_minor=price)
    return r


def test_first_attempt_becomes_a_join_request_not_a_booking():
    async def run():
        store = MemoryDataStore()
        resources, joins, pause, bookings = _services(store)
        r = await _resource_open_all_week(resources, TENANT)
        with pytest.raises(JoinRequired):
            await bookings.create(TENANT, resource_id=r.id, phone=PHONE,
                                  starts_at=1_800_000_000, ends_at=1_800_003_600)
        assert await joins.status(TENANT, PHONE) == "pending"

    asyncio.run(run())


def test_pending_phone_is_refused_with_its_own_reason():
    async def run():
        store = MemoryDataStore()
        resources, joins, pause, bookings = _services(store)
        r = await _resource_open_all_week(resources, TENANT)
        await joins.ensure_pending(TENANT, PHONE)
        with pytest.raises(BookingRefused) as exc:
            await bookings.create(TENANT, resource_id=r.id, phone=PHONE,
                                  starts_at=1_800_000_000, ends_at=1_800_003_600)
        assert exc.value.reason == "PENDING_APPROVAL"

    asyncio.run(run())


def test_blocked_phone_is_refused_distinctly_from_pending():
    async def run():
        store = MemoryDataStore()
        resources, joins, pause, bookings = _services(store)
        r = await _resource_open_all_week(resources, TENANT)
        await joins.block(TENANT, PHONE)
        with pytest.raises(BookingRefused) as exc:
            await bookings.create(TENANT, resource_id=r.id, phone=PHONE,
                                  starts_at=1_800_000_000, ends_at=1_800_003_600)
        assert exc.value.reason == "BLOCKED"

    asyncio.run(run())


def test_approved_phone_books_successfully_and_price_is_snapshotted():
    async def run():
        store = MemoryDataStore()
        resources, joins, pause, bookings = _services(store)
        r = await _resource_open_all_week(resources, TENANT, price=7500)
        await joins.ensure_pending(TENANT, PHONE)
        await joins.approve(TENANT, PHONE)
        booking = await bookings.create(TENANT, resource_id=r.id, phone=PHONE,
                                        starts_at=1_800_000_000, ends_at=1_800_003_600)
        assert booking["status"] == "confirmed"
        assert booking["hourly_price_minor"] == 7500

        # The shop raises the price AFTER the booking — the booking's own stamped rate must never
        # silently change (spec §3's own "historical fact").
        await resources.set_availability(TENANT, r.id, weekly={d: [(0, 24 * 60)] for d in range(7)},
                                         hourly_price_minor=999999)
        rows = await bookings.list_for_tenant(TENANT)
        assert rows[0]["hourly_price_minor"] == 7500

    asyncio.run(run())


def test_shop_paused_refuses_new_bookings_but_keeps_existing_ones():
    async def run():
        store = MemoryDataStore()
        resources, joins, pause, bookings = _services(store)
        r = await _resource_open_all_week(resources, TENANT)
        await joins.ensure_pending(TENANT, PHONE)
        await joins.approve(TENANT, PHONE)
        first = await bookings.create(TENANT, resource_id=r.id, phone=PHONE,
                                      starts_at=1_800_000_000, ends_at=1_800_003_600)

        await pause.set_paused(TENANT, True)
        with pytest.raises(BookingRefused) as exc:
            await bookings.create(TENANT, resource_id=r.id, phone=PHONE,
                                  starts_at=1_800_100_000, ends_at=1_800_103_600)
        assert exc.value.reason == "SHOP_PAUSED"

        rows = await bookings.list_for_tenant(TENANT)
        assert any(b["id"] == first["id"] and b["status"] == "confirmed" for b in rows)

        await pause.set_paused(TENANT, False)
        second = await bookings.create(TENANT, resource_id=r.id, phone=PHONE,
                                       starts_at=1_800_100_000, ends_at=1_800_103_600)
        assert second["status"] == "confirmed"

    asyncio.run(run())


def test_owner_cancel_frees_the_slot_again():
    async def run():
        store = MemoryDataStore()
        resources, joins, pause, bookings = _services(store)
        r = await _resource_open_all_week(resources, TENANT)
        await joins.ensure_pending(TENANT, PHONE)
        await joins.approve(TENANT, PHONE)
        booking = await bookings.create(TENANT, resource_id=r.id, phone=PHONE,
                                        starts_at=1_800_000_000, ends_at=1_800_003_600)

        with pytest.raises(BookingRefused):
            await bookings.create(TENANT, resource_id=r.id, phone=PHONE,
                                  starts_at=1_800_000_000, ends_at=1_800_003_600)

        await bookings.cancel(TENANT, booking["id"])
        second = await bookings.create(TENANT, resource_id=r.id, phone=PHONE,
                                       starts_at=1_800_000_000, ends_at=1_800_003_600)
        assert second["status"] == "confirmed"

    asyncio.run(run())


def test_disabling_a_resource_keeps_existing_bookings_but_blocks_new_ones():
    async def run():
        store = MemoryDataStore()
        resources, joins, pause, bookings = _services(store)
        r = await _resource_open_all_week(resources, TENANT)
        await joins.ensure_pending(TENANT, PHONE)
        await joins.approve(TENANT, PHONE)
        booking = await bookings.create(TENANT, resource_id=r.id, phone=PHONE,
                                        starts_at=1_800_000_000, ends_at=1_800_003_600)

        await resources.update(TENANT, r.id, active=False)

        rows = await bookings.list_for_tenant(TENANT)
        assert any(b["id"] == booking["id"] and b["status"] == "confirmed" for b in rows)

        with pytest.raises(BookingRefused) as exc:
            await bookings.create(TENANT, resource_id=r.id, phone=PHONE,
                                  starts_at=1_800_100_000, ends_at=1_800_103_600)
        assert exc.value.reason == "RESOURCE_INACTIVE"

    asyncio.run(run())


def test_window_outside_working_hours_is_refused():
    async def run():
        store = MemoryDataStore()
        resources, joins, pause, bookings = _services(store)
        r = await resources.create(TENANT, name="كرسي 1")
        # Only Monday (weekday 0) 09:00-12:00 is open.
        await resources.set_availability(TENANT, r.id, weekly={0: [(540, 720)]},
                                         hourly_price_minor=5000)
        await joins.ensure_pending(TENANT, PHONE)
        await joins.approve(TENANT, PHONE)

        # A known Sunday 10:00 Riyadh (2026-08-16 is a Sunday, weekday 6 — closed).
        import datetime as _dt

        from app.core.riyadh import RIYADH
        sunday_10am = int(_dt.datetime(2026, 8, 16, 10, 0, tzinfo=RIYADH).timestamp())
        with pytest.raises(BookingRefused) as exc:
            await bookings.create(TENANT, resource_id=r.id, phone=PHONE,
                                  starts_at=sunday_10am, ends_at=sunday_10am + 3600)
        assert exc.value.reason == "SLOT_UNAVAILABLE"

    asyncio.run(run())


def test_cross_tenant_own_bookings_never_leak():
    async def run():
        store = MemoryDataStore()
        resources, joins, pause, bookings = _services(store)
        r1 = await _resource_open_all_week(resources, "shopA")
        r2 = await _resource_open_all_week(resources, "shopB")
        await joins.ensure_pending("shopA", PHONE)
        await joins.approve("shopA", PHONE)
        await joins.ensure_pending("shopB", PHONE)
        await joins.approve("shopB", PHONE)
        await bookings.create("shopA", resource_id=r1.id, phone=PHONE,
                              starts_at=1_800_000_000, ends_at=1_800_003_600)
        await bookings.create("shopB", resource_id=r2.id, phone=PHONE,
                              starts_at=1_800_000_000, ends_at=1_800_003_600)

        mine_a = await bookings.list_for_phone("shopA", PHONE)
        mine_b = await bookings.list_for_phone("shopB", PHONE)
        assert len(mine_a) == 1 and mine_a[0]["tenant"] == "shopA"
        assert len(mine_b) == 1 and mine_b[0]["tenant"] == "shopB"

    asyncio.run(run())


# ── the double-booking race ──────────────────────────────────────────────────────────────────────
def test_only_one_of_two_overlapping_bookings_wins():
    async def run():
        store = _SlowStore(MemoryDataStore())
        resources = ResourceService(store=store)
        joins = JoinRegistry(store=store)
        pause = PauseSettings(store=store)
        bookings = BookingService(store=store, resources=resources, joins=joins, pause=pause)
        r = await _resource_open_all_week(resources, TENANT)
        await joins.ensure_pending(TENANT, PHONE)
        await joins.approve(TENANT, PHONE)

        out = await asyncio.gather(
            bookings.create(TENANT, resource_id=r.id, phone=PHONE,
                            starts_at=1_800_000_000, ends_at=1_800_003_600),
            bookings.create(TENANT, resource_id=r.id, phone=PHONE,
                            starts_at=1_800_000_600, ends_at=1_800_004_200),  # overlaps the first
            return_exceptions=True)
        created = [o for o in out if not isinstance(o, Exception)]
        refused = [o for o in out if isinstance(o, Exception)]
        return created, refused

    created, refused = asyncio.run(run())
    assert len(created) == 1, "two overlapping bookings for one resource both succeeded"
    assert len(refused) == 1, "the loser must be told, not silently dropped"
    assert isinstance(refused[0], BookingRefused)
    assert str(refused[0]).strip()


def test_different_resources_do_not_queue_behind_each_other():
    async def run():
        store = _SlowStore(MemoryDataStore())
        resources = ResourceService(store=store)
        joins = JoinRegistry(store=store)
        pause = PauseSettings(store=store)
        bookings = BookingService(store=store, resources=resources, joins=joins, pause=pause)
        r1 = await _resource_open_all_week(resources, TENANT)
        r2 = await _resource_open_all_week(resources, TENANT)
        await joins.ensure_pending(TENANT, PHONE)
        await joins.approve(TENANT, PHONE)

        out = await asyncio.gather(
            bookings.create(TENANT, resource_id=r1.id, phone=PHONE,
                            starts_at=1_800_000_000, ends_at=1_800_003_600),
            bookings.create(TENANT, resource_id=r2.id, phone=PHONE,
                            starts_at=1_800_000_000, ends_at=1_800_003_600),
            return_exceptions=True)
        return [o for o in out if isinstance(o, Exception)]

    errors = asyncio.run(run())
    assert errors == [], "two different resources' slots must not contend"


# ── capacity (owner decision 2026-10-06): a resource may hold more than one booking at once ────
async def _resource_open_all_week_with_quantity(resources, tenant, quantity, price=5000):
    r = await resources.create(tenant, name="قاعة اجتماعات", quantity=quantity)
    weekly = {d: [(0, 24 * 60)] for d in range(7)}
    await resources.set_availability(tenant, r.id, weekly=weekly, hourly_price_minor=price)
    return r


def test_quantity_defaults_to_one_so_every_old_resource_keeps_the_old_exclusive_behaviour():
    async def run():
        store = MemoryDataStore()
        resources, joins, pause, bookings = _services(store)
        r = await _resource_open_all_week(resources, TENANT)
        assert r.quantity == 1

    asyncio.run(run())


def test_capacity_lets_exactly_quantity_overlapping_bookings_through_and_refuses_the_next():
    async def run():
        store = MemoryDataStore()
        resources, joins, pause, bookings = _services(store)
        r = await _resource_open_all_week_with_quantity(resources, TENANT, quantity=3)
        await joins.ensure_pending(TENANT, PHONE)
        await joins.approve(TENANT, PHONE)
        for _ in range(3):
            booking = await bookings.create(TENANT, resource_id=r.id, phone=PHONE,
                                            starts_at=1_800_000_000, ends_at=1_800_003_600)
            assert booking["status"] == "confirmed"
        with pytest.raises(BookingRefused) as exc:
            await bookings.create(TENANT, resource_id=r.id, phone=PHONE,
                                  starts_at=1_800_000_000, ends_at=1_800_003_600)
        assert exc.value.reason == "SLOT_UNAVAILABLE"

    asyncio.run(run())


def test_capacity_only_counts_bookings_that_actually_overlap():
    async def run():
        store = MemoryDataStore()
        resources, joins, pause, bookings = _services(store)
        r = await _resource_open_all_week_with_quantity(resources, TENANT, quantity=1)
        await joins.ensure_pending(TENANT, PHONE)
        await joins.approve(TENANT, PHONE)
        await bookings.create(TENANT, resource_id=r.id, phone=PHONE,
                              starts_at=1_800_000_000, ends_at=1_800_003_600)
        # A quantity-of-1 resource still accepts a SECOND booking once the first one's window has
        # genuinely ended — capacity must never be confused with "ever booked at all".
        later = await bookings.create(TENANT, resource_id=r.id, phone=PHONE,
                                      starts_at=1_800_003_600, ends_at=1_800_007_200)
        assert later["status"] == "confirmed"

    asyncio.run(run())


def test_cancelling_one_booking_frees_capacity_for_a_new_one():
    async def run():
        store = MemoryDataStore()
        resources, joins, pause, bookings = _services(store)
        r = await _resource_open_all_week_with_quantity(resources, TENANT, quantity=2)
        await joins.ensure_pending(TENANT, PHONE)
        await joins.approve(TENANT, PHONE)
        first = await bookings.create(TENANT, resource_id=r.id, phone=PHONE,
                                      starts_at=1_800_000_000, ends_at=1_800_003_600)
        await bookings.create(TENANT, resource_id=r.id, phone=PHONE,
                              starts_at=1_800_000_000, ends_at=1_800_003_600)
        with pytest.raises(BookingRefused):
            await bookings.create(TENANT, resource_id=r.id, phone=PHONE,
                                  starts_at=1_800_000_000, ends_at=1_800_003_600)
        await bookings.cancel(TENANT, first["id"])
        third = await bookings.create(TENANT, resource_id=r.id, phone=PHONE,
                                      starts_at=1_800_000_000, ends_at=1_800_003_600)
        assert third["status"] == "confirmed"

    asyncio.run(run())


def test_capacity_race_exactly_quantity_concurrent_requests_succeed_the_rest_refused():
    """The hard version of the double-booking race, generalised to N>1: `quantity + 2` requests
    fired at once for the SAME overlapping window on a `quantity`-capacity resource must leave
    EXACTLY `quantity` winners — not one (the old exclusive behaviour, which would mean capacity
    was silently ignored under contention) and not more than `quantity` (the lock doing nothing)."""
    QUANTITY = 5
    CONTENDERS = 7

    async def run():
        store = _SlowStore(MemoryDataStore())
        resources = ResourceService(store=store)
        joins = JoinRegistry(store=store)
        pause = PauseSettings(store=store)
        bookings = BookingService(store=store, resources=resources, joins=joins, pause=pause)
        r = await _resource_open_all_week_with_quantity(resources, TENANT, quantity=QUANTITY)
        await joins.ensure_pending(TENANT, PHONE)
        await joins.approve(TENANT, PHONE)

        out = await asyncio.gather(
            *[bookings.create(TENANT, resource_id=r.id, phone=PHONE,
                              starts_at=1_800_000_000 + i, ends_at=1_800_003_600 + i)
              for i in range(CONTENDERS)],  # all overlap the same window
            return_exceptions=True)
        created = [o for o in out if not isinstance(o, Exception)]
        refused = [o for o in out if isinstance(o, Exception)]
        return created, refused

    created, refused = asyncio.run(run())
    assert len(created) == QUANTITY, (
        f"expected exactly {QUANTITY} winners for a {QUANTITY}-capacity resource under "
        f"{CONTENDERS}-way contention, got {len(created)}")
    assert len(refused) == CONTENDERS - QUANTITY
    assert all(isinstance(e, BookingRefused) and e.reason == "SLOT_UNAVAILABLE" for e in refused)
