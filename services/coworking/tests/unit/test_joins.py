from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.joins import JoinError, JoinRegistry

TENANT = "t1"
PHONE = "+966501234567"


def test_no_row_means_no_status():
    async def run():
        joins = JoinRegistry(store=MemoryDataStore())
        return await joins.status(TENANT, PHONE)

    assert asyncio.run(run()) is None


def test_ensure_pending_then_approve():
    async def run():
        joins = JoinRegistry(store=MemoryDataStore())
        await joins.ensure_pending(TENANT, PHONE)
        assert await joins.status(TENANT, PHONE) == "pending"
        await joins.approve(TENANT, PHONE)
        return await joins.status(TENANT, PHONE)

    assert asyncio.run(run()) == "approved"


def test_approve_without_a_pending_request_refuses():
    async def run():
        joins = JoinRegistry(store=MemoryDataStore())
        with pytest.raises(JoinError):
            await joins.approve(TENANT, PHONE)

    asyncio.run(run())


def test_reject_deletes_the_row_so_a_retry_is_possible():
    async def run():
        joins = JoinRegistry(store=MemoryDataStore())
        await joins.ensure_pending(TENANT, PHONE)
        await joins.reject(TENANT, PHONE)
        assert await joins.status(TENANT, PHONE) is None
        # Retrying lands back in pending — reject is not a permanent verdict.
        await joins.ensure_pending(TENANT, PHONE)
        return await joins.status(TENANT, PHONE)

    assert asyncio.run(run()) == "pending"


def test_block_works_with_no_prior_row_at_all():
    async def run():
        joins = JoinRegistry(store=MemoryDataStore())
        await joins.block(TENANT, PHONE)
        return await joins.status(TENANT, PHONE)

    assert asyncio.run(run()) == "blocked"


def test_block_overrides_an_existing_approval():
    async def run():
        joins = JoinRegistry(store=MemoryDataStore())
        await joins.ensure_pending(TENANT, PHONE)
        await joins.approve(TENANT, PHONE)
        await joins.block(TENANT, PHONE)
        return await joins.status(TENANT, PHONE)

    assert asyncio.run(run()) == "blocked"


def test_unblock_requires_a_fresh_join_request_not_straight_to_approved():
    async def run():
        joins = JoinRegistry(store=MemoryDataStore())
        await joins.block(TENANT, PHONE)
        await joins.unblock(TENANT, PHONE)
        return await joins.status(TENANT, PHONE)

    assert asyncio.run(run()) is None


def test_scoped_per_shop_not_globally():
    async def run():
        joins = JoinRegistry(store=MemoryDataStore())
        await joins.ensure_pending("shopA", PHONE)
        await joins.approve("shopA", PHONE)
        return await joins.status("shopB", PHONE)

    assert asyncio.run(run()) is None
