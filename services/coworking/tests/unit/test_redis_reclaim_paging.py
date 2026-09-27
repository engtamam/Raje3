"""RedisQueue.reclaim() — the property worth a test: it never pulls the whole inflight list into
memory at once, yet still reclaims every expired entry across it.

THE BUG: `reclaim()` used to `LRANGE queue:x:inflight 0 -1` — one call, the whole list, regardless
of size. Fixed to page through `_RECLAIM_PAGE`-sized windows. A fake redis client below records
the (start, stop) arguments every `lrange` call is made with, so this asserts no window is ever
wider than the page size, AND that every expired entry across a list several pages long is still
reclaimed (paging must not skip or double-count entries as `LREM` shifts the list under it).
"""
from __future__ import annotations

import json

import pytest

from app.adapters.queue.redis import RedisQueue, _RECLAIM_PAGE


class _FakeRedis:
    """Just enough of the redis.asyncio surface for `reclaim()` — a plain in-memory list + hash,
    with `lrange` windows recorded so the test can assert they stay bounded."""

    def __init__(self) -> None:
        self.lists: dict[str, list[str]] = {}
        self.hashes: dict[str, dict[str, str]] = {}
        self.lrange_calls: list[tuple[int, int]] = []

    async def lrange(self, key: str, start: int, stop: int) -> list[str]:
        self.lrange_calls.append((start, stop))
        items = self.lists.get(key, [])
        if stop == -1:
            return items[start:]
        return items[start:stop + 1]

    async def lrem(self, key: str, count: int, value: str) -> int:
        items = self.lists.get(key, [])
        try:
            items.remove(value)
        except ValueError:
            return 0
        return 1

    async def hget(self, key: str, field: str) -> str | None:
        return self.hashes.get(key, {}).get(field)

    async def hdel(self, key: str, field: str) -> int:
        return 1 if self.hashes.get(key, {}).pop(field, None) is not None else 0

    async def rpush(self, key: str, value: str) -> int:
        self.lists.setdefault(key, []).append(value)
        return len(self.lists[key])


def _make_queue() -> tuple[RedisQueue, _FakeRedis]:
    q = RedisQueue.__new__(RedisQueue)   # bypass __init__'s `load("redis.asyncio", ...)`
    fake = _FakeRedis()
    q._client = fake
    return q, fake


@pytest.mark.anyio
async def test_reclaim_never_asks_for_more_than_one_page_at_once():
    q, fake = _make_queue()
    inflight = q._inflight("jobs")
    leases = q._leases("jobs")
    n = _RECLAIM_PAGE * 3 + 7   # several pages' worth, deliberately not a clean multiple
    for i in range(n):
        raw = json.dumps({"id": str(i), "payload": {}})
        fake.lists.setdefault(inflight, []).append(raw)
        fake.hashes.setdefault(leases, {})[raw] = json.dumps({"token": "t", "expires": 0})

    reclaimed = await q.reclaim("jobs")

    assert reclaimed == n
    assert all(stop - start + 1 <= _RECLAIM_PAGE for start, stop in fake.lrange_calls)
    assert fake.lists[inflight] == []                       # every one moved back to ready
    assert len(fake.lists[q._k("jobs")]) == n


@pytest.mark.anyio
async def test_reclaim_skips_leases_still_inside_their_window():
    q, fake = _make_queue()
    inflight = q._inflight("jobs")
    leases = q._leases("jobs")
    expired = json.dumps({"id": "expired", "payload": {}})
    live = json.dumps({"id": "live", "payload": {}})
    fake.lists[inflight] = [expired, live]
    fake.hashes[leases] = {
        expired: json.dumps({"token": "t", "expires": 0}),
        live: json.dumps({"token": "t", "expires": 9_999_999_999}),
    }

    reclaimed = await q.reclaim("jobs")

    assert reclaimed == 1
    assert fake.lists[inflight] == [live]
    assert fake.lists[q._k("jobs")] == [expired]
