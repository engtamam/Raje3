"""DataStoreInboundMessageStore.mark_processed / attach_subject_ref — atomic now.

whatsapp-assistant-002 (QA audit, 2026-09-12): both used to be a plain get-then-put on the same
row `record_if_new` was itself fixed (2026-09-07) to stop doing, for the identical reason —
`mark_processed` runs from a `finally` block, so a write still in flight from the other function
could lose one of the two fields. A short claim()-backed mutex around the get-then-put now
closes it.
"""
from __future__ import annotations

import asyncio

from app.adapters.datastore.memory import MemoryDataStore
from app.adapters.inbound_store.datastore_backed import build
from app.core.models import INBOUND_MESSAGES

TENANT = "t1"
WAMID = "wamid_1"


class _SlowStore:
    """Wraps a real store but stalls between `get` and `put`, widening the race window so a
    non-atomic read-modify-write is caught deterministically instead of needing luck."""

    def __init__(self, inner):
        self._inner = inner

    async def get(self, collection, key):
        row = await self._inner.get(collection, key)
        await asyncio.sleep(0.01)
        return row

    async def put(self, collection, key, value):
        return await self._inner.put(collection, key, value)

    async def delete(self, collection, key):
        return await self._inner.delete(collection, key)

    async def claim(self, collection, key, value, *, ttl_seconds, now):
        return await self._inner.claim(collection, key, value, ttl_seconds=ttl_seconds, now=now)


async def test_two_genuinely_concurrent_writers_never_lose_either_field():
    inner = MemoryDataStore()
    store = _SlowStore(inner)
    inbound = build(store)
    await inbound.record_if_new(TENANT, WAMID, {"text": "hi"})

    await asyncio.gather(
        inbound.mark_processed(TENANT, WAMID),
        inbound.attach_subject_ref(TENANT, WAMID, "sub_abc"),
    )

    row = await inner.get(INBOUND_MESSAGES, f"{TENANT}|{WAMID}")
    assert row["processed"] is True
    assert row["subject_ref"] == "sub_abc"


async def test_mark_processed_and_attach_subject_ref_still_work_sequentially():
    store = MemoryDataStore()
    inbound = build(store)
    await inbound.record_if_new(TENANT, WAMID, {"text": "hi"})
    await inbound.attach_subject_ref(TENANT, WAMID, "sub_abc")
    await inbound.mark_processed(TENANT, WAMID)

    row = await inbound.get(TENANT, WAMID)
    assert row["processed"] is True
    assert row["subject_ref"] == "sub_abc"


async def test_a_wamid_never_recorded_is_a_silent_no_op_for_either():
    store = MemoryDataStore()
    inbound = build(store)
    await inbound.mark_processed(TENANT, "never_seen")
    await inbound.attach_subject_ref(TENANT, "never_seen", "sub_x")
    assert await inbound.get(TENANT, "never_seen") is None
