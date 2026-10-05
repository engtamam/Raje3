"""operations-001/002 (QA audit, 2026-09-12): the customer-counter lock itself, proved directly —
same technique offer_lock.py's own race test uses (till_offer.py), one holder sleeps WHILE holding
the lock so a genuinely concurrent second acquire has something real to contend with."""
from __future__ import annotations

import asyncio

from app.adapters.cache.memory import MemoryCache
from app.core.customer_counter_lock import CustomerCounterBusy, CustomerCounterLock


def run(coro):
    return asyncio.run(coro)


def test_a_second_concurrent_lock_waits_for_the_first_and_never_overlaps_it():
    """The second claimant waits its turn — it is neither refused (its caller has already saved a
    visit that would then go uncounted) nor let in while the first still holds the lock."""
    cache = MemoryCache()
    inside: list[str] = []

    async def holder():
        async with CustomerCounterLock(cache, "t1", "cus_1"):
            inside.append("holder-in")
            await asyncio.sleep(0.05)
            inside.append("holder-out")
            return "held"

    async def racer():
        await asyncio.sleep(0.01)   # starts after `holder` has already taken the lock
        async with CustomerCounterLock(cache, "t1", "cus_1"):
            inside.append("racer-in")
            return "held"

    async def go():
        return await asyncio.gather(holder(), racer())

    assert run(go()) == ["held", "held"]
    assert inside == ["holder-in", "holder-out", "racer-in"], (
        "the racer must only get in after the holder has left — never alongside it"
    )


def test_a_lock_still_held_past_the_wait_is_refused_not_silently_allowed():
    cache = MemoryCache()

    async def holder():
        async with CustomerCounterLock(cache, "t1", "cus_1"):
            await asyncio.sleep(0.3)
            return "held"

    async def racer():
        await asyncio.sleep(0.01)
        try:
            async with CustomerCounterLock(cache, "t1", "cus_1", wait_seconds=0.1):
                return "held"
        except CustomerCounterBusy:
            return "busy"

    async def go():
        return await asyncio.gather(holder(), racer())

    assert run(go()) == ["held", "busy"], (
        "a lock that outlives the wait (a writer that died holding it) must still be refused, "
        "never silently allowed through to race it"
    )


def test_two_different_customers_never_contend():
    cache = MemoryCache()

    async def take(customer_id):
        async with CustomerCounterLock(cache, "t1", customer_id):
            await asyncio.sleep(0.02)
            return "held"

    async def go():
        return await asyncio.gather(take("cus_a"), take("cus_b"))

    assert run(go()) == ["held", "held"]


def test_the_lock_releases_after_use_so_a_later_call_can_take_it():
    cache = MemoryCache()

    async def go():
        async with CustomerCounterLock(cache, "t1", "cus_1"):
            pass
        async with CustomerCounterLock(cache, "t1", "cus_1"):
            return "held again"

    assert run(go()) == "held again"


def test_no_cache_at_all_never_refuses():
    """A local run or a test with the cache port unwired — same posture as OfferApplyLock: a
    process with no cache has no second caller to race against."""
    async def go():
        async with CustomerCounterLock(None, "t1", "cus_1"):
            return "ok"

    assert run(go()) == "ok"
