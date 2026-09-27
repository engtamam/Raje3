"""Tenant-level pause (spec §5) — one flag, one meaning: no NEW booking succeeds while it is on.

Deliberately the only thing this flag touches. `bookings.py::create` is the one call site that
reads it, and it reads it BEFORE anything else (before the join gate, before availability) — a
paused shop refuses everyone, not just new freelancers. Nothing here ever looks at, cancels, or
hides an already-confirmed booking; those stay exactly as they were until the shop cancels one by
hand, same as the spec's own acceptance test demands.
"""
from __future__ import annotations

from typing import Any

from app.core.models import SETTINGS


class PauseSettings:
    def __init__(self, store: Any) -> None:
        self._store = store

    async def is_paused(self, tenant: str) -> bool:
        row = await self._store.get(SETTINGS, tenant)
        return bool(row and row.get("paused"))

    async def set_paused(self, tenant: str, paused: bool) -> bool:
        row = await self._store.get(SETTINGS, tenant) or {"tenant": tenant}
        row["paused"] = bool(paused)
        await self._store.put(SETTINGS, tenant, row)
        return row["paused"]
