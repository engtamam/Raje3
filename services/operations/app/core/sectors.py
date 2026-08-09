"""Sectors — DATA IN THE DATASTORE, edited from the platform console at runtime.

THE FILE IS A SEED, NOT THE SOURCE OF TRUTH. An earlier version of this read a JSON file at boot,
and that was wrong for the reason that matters: adding a sector, fixing a service name, or changing
a cycle would have meant a ConfigMap edit and a restart. Sectors are content our own operators
curate — they will change on a Tuesday afternoon because a customer asked — and content that needs
a deploy is content that does not get edited.

So: the sectors live in the datastore, editable through the platform console
(/api/v1/platform/sectors, capability `platform.operations`). The JSON file is applied ONCE, when
the table is empty, so a fresh install is not a blank product.

PLATFORM-SCOPED, NOT TENANT-SCOPED. There is one sector table for the whole product, and it is not
an establishment's to edit — a tyre shop must not be able to rename "بنشر" for everyone else. The
rows carry the reserved tenant `_platform`, which no real tenant can ever hold: a tenant id is
issued by tenant-service and never begins with an underscore.

TWO RULES THAT DECIDE THE CONTENT ITSELF, both learned from what breaks a product on day one:

1. DEFAULTS SHIP FULL, NEVER EMPTY. An establishment that must build its own service list before
   recording a first visit will not record a first visit — the owner signs up, meets a blank grid,
   and closes the tab. Opinionated defaults that are slightly wrong beat nothing that is right.

2. FIELDS ARE PER SECTOR (spec §4.6). The plate renders in vehicle sectors ONLY. A women's salon
   asked for a plate number is a screen built for somebody else, and that one detail tells an owner
   this product was not made for them.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from app.core.models import Service
from app.core.stores import ServiceStore, new_id

SECTORS = "sectors"
FIELD_SPECS = "sector_fields"

# The reserved owner of platform-wide rows. Underscore-prefixed on purpose: tenant ids are issued
# by tenant-service and never take this shape, so no establishment can ever collide with it.
PLATFORM = "_platform"


class SectorError(Exception):
    """A refusal a console user can act on: an unknown sector, a duplicate key, a bad file."""


class SectorCatalogue:
    """Reads and writes the sector table. No caching.

    Deliberately uncached: these are read when a tenant is created and when the signup screen is
    drawn — rare, not hot. A cache here would buy nothing measurable and would cost the thing the
    console is for, which is seeing an edit take effect immediately.
    """

    def __init__(self, store) -> None:
        self._s = store

    # ── reads ─────────────────────────────────────────────────────────────────────────────────
    async def list(self) -> list[dict[str, Any]]:
        rows, _ = await self._s.find(SECTORS, {"tenant": PLATFORM}, limit=200,
                                     sort=("sort", "asc"))
        return rows

    async def get(self, key: str) -> dict[str, Any] | None:
        return await self._s.get(SECTORS, f"{PLATFORM}|{key}")

    async def fields(self) -> dict[str, Any]:
        row = await self._s.get(FIELD_SPECS, f"{PLATFORM}|fields")
        return (row or {}).get("specs", {})

    async def fields_for(self, key: str) -> list[dict[str, Any]]:
        """Full descriptors, not names — so the screen never needs its own copy of what a field
        means. A second copy is a second thing to keep in step, and it will not be kept in step."""
        sector = await self.get(key)
        if not sector:
            return []
        specs = await self.fields()
        return [{"name": n, **specs[n]} for n in sector.get("fields", []) if n in specs]

    async def tracks_vehicle(self, key: str) -> bool:
        sector = await self.get(key)
        return bool(sector) and sector.get("asset") == "vehicle"

    # ── writes: the platform console ──────────────────────────────────────────────────────────
    async def upsert(self, sector: dict[str, Any]) -> dict[str, Any]:
        key = (sector.get("key") or "").strip()
        if not key:
            raise SectorError("a sector needs a `key` — without one it can never be selected")
        if key.startswith("_"):
            raise SectorError("a sector key must not start with '_' — that prefix is reserved")
        row = {
            "id": key, "tenant": PLATFORM, "key": key,
            "name": (sector.get("name") or key).strip(),
            "asset": sector.get("asset", "none"),
            "fields": list(sector.get("fields", [])),
            "services": list(sector.get("services", [])),
            "sort": int(sector.get("sort", 0)),
            "active": bool(sector.get("active", True)),
            "updated": int(time.time()),
        }
        await self._s.put(SECTORS, f"{PLATFORM}|{key}", row)
        return row

    async def set_field_specs(self, specs: dict[str, Any]) -> dict[str, Any]:
        row = {"id": "fields", "tenant": PLATFORM, "specs": specs, "updated": int(time.time())}
        await self._s.put(FIELD_SPECS, f"{PLATFORM}|fields", row)
        return row

    async def deactivate(self, key: str) -> bool:
        """Deactivate, never delete.

        Establishments already point at this sector. Deleting it would leave them referring to
        something that no longer exists, and the symptom would be a signup screen that works and a
        tenant record that does not resolve.
        """
        row = await self.get(key)
        if row is None:
            return False
        row["active"] = False
        row["updated"] = int(time.time())
        await self._s.put(SECTORS, f"{PLATFORM}|{key}", row)
        return True

    # ── the one-time seed ─────────────────────────────────────────────────────────────────────
    async def seed_from_file(self, path: str) -> int:
        """Apply the shipped defaults ONCE, when the table is empty.

        Only when empty: re-applying on every boot would silently undo an operator's edits, which
        is the worst kind of bug — the console appears to work, and the change is gone tomorrow.
        """
        if not path:
            return 0
        if await self.list():
            return 0
        p = Path(path)
        if not p.is_file():
            raise SectorError(f"SECTORS_SEED_FILE points at {path!r}, which does not exist — the "
                              f"sector table is empty and every new establishment would get a "
                              f"blank service grid")
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SectorError(f"the sector seed file is not valid JSON: {exc}") from exc

        await self.set_field_specs({k: v for k, v in data.get("fields", {}).items()
                                    if not k.startswith("_")})
        n = 0
        for entry in data.get("sectors", []):
            await self.upsert(entry)
            n += 1
        return n

    # ── seeding a tenant's catalogue ──────────────────────────────────────────────────────────
    async def seed_tenant(self, *, tenant: str, sector_key: str) -> int:
        """Give a new establishment its catalogue. Returns how many services were created.

        IDEMPOTENT BY NAME. Re-running adds nothing, so a retried provisioning step cannot produce
        a catalogue listing every service twice — a mess the owner cleans by hand, on day one.
        """
        sector = await self.get(sector_key)
        if sector is None or not sector.get("active", True):
            keys = [s.get("key") for s in await self.list() if s.get("active", True)]
            raise SectorError(f"unknown or inactive sector {sector_key!r} — one of {keys}")

        svc_store = ServiceStore(self._s)
        existing = {s.name for s in await svc_store.list(tenant, active_only=False)}
        now = int(time.time())
        created = 0
        for entry in sector.get("services", []):
            name = (entry.get("name") or "").strip()
            if not name or name in existing:
                continue
            await svc_store.save(Service(
                id=new_id("srv"), tenant=tenant, name=name,
                cycle_days=int(entry.get("cycle_days", 0)),
                # No price. It varies by city, by shop and by the day — shipping a number ships a
                # wrong one to almost everybody, and a wrong price on a screen is worse than none.
                price_minor=0,
                sort=int(entry.get("sort", 0)),
                catchall=bool(entry.get("catchall", False)), created=now))
            created += 1
        return created
