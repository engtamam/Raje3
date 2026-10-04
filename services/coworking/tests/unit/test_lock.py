from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.lock import SlotClaimBusy, _span_buckets, claiming


def test_span_buckets_always_at_least_one():
    assert _span_buckets(1000, 1000) == _span_buckets(1000, 1001)


def test_span_buckets_shares_a_lane_for_overlapping_spans():
    a = set(_span_buckets(1_800_000_000, 1_800_003_600))
    b = set(_span_buckets(1_800_000_600, 1_800_004_200))
    assert a & b, "two genuinely overlapping spans must share at least one lane"


def test_second_claim_on_same_lane_fails_while_held():
    async def run():
        store = MemoryDataStore()
        async with claiming(store, tenant="t1", resource_id="r1",
                            starts_at=1_800_000_000, ends_at=1_800_003_600, now=0.0):
            with pytest.raises(SlotClaimBusy):
                async with claiming(store, tenant="t1", resource_id="r1",
                                    starts_at=1_800_000_000, ends_at=1_800_003_600, now=0.0):
                    pass

    asyncio.run(run())


def test_lane_is_released_after_the_context_exits():
    async def run():
        store = MemoryDataStore()
        async with claiming(store, tenant="t1", resource_id="r1",
                            starts_at=1_800_000_000, ends_at=1_800_003_600, now=0.0):
            pass
        # Must succeed now that the first claim released its lanes.
        async with claiming(store, tenant="t1", resource_id="r1",
                            starts_at=1_800_000_000, ends_at=1_800_003_600, now=0.0):
            pass

    asyncio.run(run())
