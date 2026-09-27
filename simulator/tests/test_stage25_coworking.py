"""A ninth real, independent app wired into the simulator: services/coworking
(`apps/coworking/`) — a genuine change of pace after four apps in a row that each hit a real,
different external-peer limit: fully self-contained, no peer needed anywhere in its own admin
surface. Real HTTP against a real, spawned instance.
"""
from __future__ import annotations

import asyncio

from simulator.apps.coworking.actions import (
    BlockPhoneAction, CreateResourceAction, ListBookingsAction, ListJoinsAction,
    ListResourcesAction, SetAvailabilityAction, SetPauseAction,
)
from simulator.apps.coworking.service import spawn as spawn_coworking
from simulator.common.engine import run_one

TENANT = "sim-coworking"


def run(coro):
    return asyncio.run(coro)


def test_creating_a_resource_setting_its_availability_and_reading_it_back():
    async def _go():
        async with spawn_coworking() as svc:
            created = await run_one(CreateResourceAction(
                base_url=svc.base_url, tenant=TENANT, resource_name="غرفة اجتماعات"))
            priced = await run_one(SetAvailabilityAction(
                base_url=svc.base_url, tenant=TENANT, resource_id=created.data["id"],
                hourly_price_minor=5000))
            listed = await run_one(ListResourcesAction(base_url=svc.base_url, tenant=TENANT))
            return created, priced, listed

    created, priced, listed = run(_go())
    assert created.ok, created
    assert priced.ok, priced
    assert priced.data["hourly_price_minor"] == 5000
    assert listed.ok, listed
    assert any(r["id"] == created.data["id"] for r in listed.data["resources"])


def test_blocking_a_phone_with_no_prior_join_request_at_all_still_works():
    """`core/joins.py`'s own real, documented rule: a phone can be blocked pre-emptively, before
    it ever asked to join."""

    async def _go():
        async with spawn_coworking() as svc:
            return await run_one(BlockPhoneAction(
                base_url=svc.base_url, tenant=TENANT, phone="0511111111"))

    result = run(_go())
    assert result.ok, result


def test_a_fresh_tenant_has_no_joins_or_bookings_yet():
    async def _go():
        async with spawn_coworking() as svc:
            joins = await run_one(ListJoinsAction(
                base_url=svc.base_url, tenant="sim-coworking-empty"))
            bookings = await run_one(ListBookingsAction(
                base_url=svc.base_url, tenant="sim-coworking-empty"))
            return joins, bookings

    joins, bookings = run(_go())
    assert joins.ok and joins.data["joins"] == []
    assert bookings.ok and bookings.data["bookings"] == []


def test_pausing_the_tenant_then_reading_it_back_holds():
    async def _go():
        async with spawn_coworking() as svc:
            paused = await run_one(SetPauseAction(
                base_url=svc.base_url, tenant="sim-coworking-pause", paused=True))
            resumed = await run_one(SetPauseAction(
                base_url=svc.base_url, tenant="sim-coworking-pause", paused=False))
            return paused, resumed

    paused, resumed = run(_go())
    assert paused.ok and paused.data["paused"] is True
    assert resumed.ok and resumed.data["paused"] is False
