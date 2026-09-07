"""In-memory DataStore — zero infra. Deep-copies values to avoid aliasing."""
from __future__ import annotations

import copy
from typing import Any

from app.adapters.datastore import cursor as _cursor
from app.ports.datastore import SORT_DIRECTIONS
from app.ports.errors import ConfigError


class MemoryDataStore:
    driver = "memory"

    def __init__(self) -> None:
        self._data: dict[str, dict[str, dict[str, Any]]] = {}

    async def get(self, collection: str, key: str) -> dict[str, Any] | None:
        row = self._data.get(collection, {}).get(key)
        return copy.deepcopy(row) if row is not None else None

    async def put(self, collection: str, key: str, value: dict[str, Any]) -> None:
        self._data.setdefault(collection, {})[key] = copy.deepcopy(value)

    async def delete(self, collection: str, key: str) -> bool:
        return self._data.get(collection, {}).pop(key, None) is not None

    async def claim(self, collection: str, key: str, value: dict[str, Any],
                    *, ttl_seconds: float, now: float) -> bool:
        """See the port. Atomic here because nothing is awaited between the read and the write —
        an `await` inserted anywhere in this method hands the event loop to the other caller
        mid-decision and both are told they won. There is no await below, and there must not be."""
        held = self._data.setdefault(collection, {}).get(key)
        if held is not None and float(held.get("expires") or 0) > now:
            return False
        row = dict(value)
        row["expires"] = now + float(ttl_seconds)
        self._data[collection][key] = copy.deepcopy(row)
        return True

    @staticmethod
    def _matches(row: dict[str, Any], where: dict[str, Any]) -> bool:
        """Equality only. `{f: v}` or `{f: [v1, v2]}`. No operators => nothing to inject."""
        for field, expected in where.items():
            actual = row.get(field)
            if isinstance(expected, (list, tuple, set)):
                if actual not in expected:
                    return False
            elif actual != expected:
                return False
        return True

    async def find(
        self,
        collection: str,
        where: dict[str, Any],
        *,
        limit: int = 100,
        after: str | None = None,
        sort: tuple[str, str] = ("created", "desc"),
    ) -> tuple[list[dict[str, Any]], str | None]:
        if not where:
            raise ConfigError("find() requires a non-empty `where` - use scan_all() to read all")
        field, direction = sort
        if direction not in SORT_DIRECTIONS:
            raise ConfigError(f"sort direction must be one of {SORT_DIRECTIONS}: {direction!r}")
        limit = max(1, int(limit))

        rows = [r for r in self._data.get(collection, {}).values() if self._matches(r, where)]
        descending = direction == "desc"
        rows.sort(key=lambda r: (_cursor._key(r.get(field)), str(r.get("id", ""))),
                  reverse=descending)

        position = _cursor.decode(after) if after else None
        if position is not None:
            rows = [r for r in rows
                    if _cursor.after(r.get(field), str(r.get("id", "")), position, descending)]

        page = rows[:limit]
        next_cursor = None
        if len(rows) > limit and page:
            last = page[-1]
            next_cursor = _cursor.encode(last.get(field), str(last.get("id", "")))
        return copy.deepcopy(page), next_cursor

    async def scan_all(self, collection: str, limit: int,
                       after: str | None = None) -> list[dict[str, Any]]:
        """Every row, in KEY ORDER, resumable from `after`.

        `after` EXISTS BECAUSE A SWEEP WITHOUT IT IS NOT A SWEEP. The points-expiry pass called
        this every night with `limit=500` and read the same five hundred rows for ever: a shop
        with fifty thousand balances had 49,500 customers whose points never expired and who never
        received the fourteen-day warning — while the tick reported `expired: 0, seen: 500`, which
        is what a healthy sweep looks like. A walker that cannot say where it stopped can only ever
        walk the beginning.

        Key order, not insertion order, so the sequence is stable across processes and a cursor
        taken by one pod means the same thing to the next.
        """
        keys = sorted(self._data.get(collection, {}))
        if after:
            keys = [k for k in keys if k > after]
        rows = [self._data[collection][k] for k in keys[: max(0, int(limit))]]
        return copy.deepcopy(rows)

    async def list(self, collection: str, limit: int = 100) -> list[dict[str, Any]]:
        return await self.scan_all(collection, limit)

    async def health(self) -> bool:
        return True

    async def close(self) -> None:
        self._data.clear()
