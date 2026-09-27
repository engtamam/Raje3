"""Resource management (spec §1/§7) — a named, schedulable thing a shop rents out by the hour.

A "resource" is deliberately dumb: a name, an active flag, a weekly availability matrix and a
price. It knows nothing about who books it — `bookings.py` is the only thing that reads its
schedule, and `joins.py` is the only thing that decides WHO may.
"""
from __future__ import annotations

import time
import uuid
from typing import Any

from app.core.models import RESOURCES, Resource, exceptions_to_storage, weekly_to_storage


class ResourceError(Exception):
    """A refusal a caller should show verbatim — never a stack trace."""


class ResourceService:
    def __init__(self, store: Any) -> None:
        self._store = store

    async def create(self, tenant: str, *, name: str) -> Resource:
        name = (name or "").strip()
        if not name:
            raise ResourceError("اسم المورد مطلوب")
        resource = Resource(id=str(uuid.uuid4()), tenant=tenant, name=name,
                            created_at=int(time.time()))
        await self._store.put(RESOURCES, resource.id, resource.to_dict())
        return resource

    async def get(self, tenant: str, resource_id: str) -> Resource | None:
        row = await self._store.get(RESOURCES, resource_id)
        if row is None or row.get("tenant") != tenant:
            # SAME SHAPE AS "NOT FOUND" — a resource id belonging to another tenant must be
            # indistinguishable from one that does not exist at all (no cross-tenant existence
            # leak), the same posture every tenant-scoped read in this fleet takes.
            return None
        return Resource.from_dict(row)

    async def list(self, tenant: str, *, include_inactive: bool = True) -> list[Resource]:
        rows, _ = await self._store.find(RESOURCES, {"tenant": tenant}, limit=1000,
                                         sort=("created_at", "asc"))
        resources = [Resource.from_dict(r) for r in rows]
        if not include_inactive:
            resources = [r for r in resources if r.active]
        return resources

    async def update(self, tenant: str, resource_id: str, *, name: str | None = None,
                     active: bool | None = None) -> Resource:
        resource = await self.get(tenant, resource_id)
        if resource is None:
            raise ResourceError("المورد غير موجود")
        new_name = resource.name if name is None else (name.strip() or resource.name)
        new_active = resource.active if active is None else bool(active)
        updated = Resource(id=resource.id, tenant=resource.tenant, name=new_name,
                           active=new_active, hourly_price_minor=resource.hourly_price_minor,
                           weekly=resource.weekly, exceptions=resource.exceptions,
                           created_at=resource.created_at)
        # DISABLING NEVER TOUCHES EXISTING BOOKINGS (spec §7/§8's own test) — this write only
        # flips the flag `bookings.py::create` reads BEFORE accepting a NEW one; every confirmed
        # row already in `coworking_bookings` is untouched by this call, on purpose.
        await self._store.put(RESOURCES, resource.id, updated.to_dict())
        return updated

    async def set_availability(self, tenant: str, resource_id: str, *,
                               weekly: dict[int, list[tuple[int, int]]],
                               exceptions: dict[str, dict] | None = None,
                               hourly_price_minor: int | None = None) -> Resource:
        resource = await self.get(tenant, resource_id)
        if resource is None:
            raise ResourceError("المورد غير موجود")
        for day, windows in weekly.items():
            if not (0 <= int(day) <= 6):
                raise ResourceError("يوم غير صالح — يجب أن يكون بين 0 و6")
            for s, e in windows:
                if not (0 <= int(s) < int(e) <= 24 * 60):
                    raise ResourceError(f"نافذة غير صالحة: {s}-{e}")
        price = resource.hourly_price_minor if hourly_price_minor is None else int(hourly_price_minor)
        if price < 0:
            raise ResourceError("السعر لا يمكن أن يكون سالباً")
        updated = Resource(
            id=resource.id, tenant=resource.tenant, name=resource.name, active=resource.active,
            hourly_price_minor=price, weekly=weekly_to_storage(weekly),
            exceptions=exceptions_to_storage(exceptions or {}), created_at=resource.created_at)
        await self._store.put(RESOURCES, resource.id, updated.to_dict())
        return updated
