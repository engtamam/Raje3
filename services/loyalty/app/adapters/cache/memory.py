"""In-memory Cache with TTL — zero infra."""
from __future__ import annotations

import time


class MemoryCache:
    driver = "memory"

    def __init__(self) -> None:
        # key -> (value, expires_at_monotonic | None)
        self._data: dict[str, tuple[str, float | None]] = {}

    def _expired(self, key: str) -> bool:
        entry = self._data.get(key)
        if entry is None:
            return True
        _, exp = entry
        if exp is not None and time.monotonic() >= exp:
            self._data.pop(key, None)
            return True
        return False

    async def get(self, key: str) -> str | None:
        if self._expired(key):
            return None
        return self._data[key][0]

    async def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        exp = time.monotonic() + ttl_seconds if ttl_seconds else None
        self._data[key] = (value, exp)


    async def set_if_absent(self, key: str, value: str, ttl_seconds: int | None = None) -> bool:
        """Claim a key only if nobody holds it. `True` means this caller won.

        WHY THE PORT NEEDED THIS. `Ledger.post` is a read-modify-write over a store whose only
        write is an unconditional upsert — no compare-and-set, no version, nothing conditional in
        the platform's datastore port. Two redemptions for the same customer inside the same second
        (a till at one branch, a phone at another) both read the same balance, both pass the
        overdraft check, and both hand a reward over: the shop gives away twice what the customer
        paid for, and the balance lands somewhere the screens cannot explain.

        A claim that is atomic AT THE CACHE closes it, because Redis SET NX is genuinely atomic
        across pods — which the datastore's upsert is not.

        THE MEMORY DRIVER IS PER-PROCESS, and that is honest rather than a compromise: the chart
        refuses replicas>1 unless every stateful port is shared, so a deployment on the memory
        driver has exactly one pod and one process — where this is a complete lock. The redis path
        is what keeps it true on the day the fleet is allowed to scale.
        """
        if not self._expired(key) and key in self._data:
            return False
        await self.set(key, value, ttl_seconds)
        return True

    async def delete(self, key: str) -> bool:
        return self._data.pop(key, None) is not None

    async def health(self) -> bool:
        return True

    async def close(self) -> None:
        self._data.clear()
