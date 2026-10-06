"""Resource management (spec §1/§7) — a named, schedulable thing a shop rents out by the hour.

A "resource" is deliberately dumb: a name, an active flag, a weekly availability matrix and a
price. It knows nothing about who books it — `bookings.py` is the only thing that reads its
schedule, and `joins.py` is the only thing that decides WHO may.
"""
from __future__ import annotations

import time
import uuid
from typing import Any

from app.core.models import RENTAL_HOURLY, RENTAL_PERIODS, RESOURCES, Resource, exceptions_to_storage, weekly_to_storage


class ResourceError(Exception):
    """A refusal a caller should show verbatim — never a stack trace."""


def _validate_rental_shape(rental_period: str, quantity: int, period_price_minor: int) -> None:
    if rental_period not in RENTAL_PERIODS:
        raise ResourceError(f"نوع إيجار غير معروف: {rental_period}")
    if quantity < 1:
        raise ResourceError("الكمية يجب أن تكون 1 على الأقل")
    if period_price_minor < 0:
        raise ResourceError("السعر لا يمكن أن يكون سالباً")


class ResourceService:
    def __init__(self, store: Any) -> None:
        self._store = store

    async def create(self, tenant: str, *, name: str, branch_id: str = "",
                     description: str = "", rental_period: str = RENTAL_HOURLY,
                     quantity: int = 1, period_price_minor: int = 0) -> Resource:
        name = (name or "").strip()
        if not name:
            raise ResourceError("اسم المورد مطلوب")
        _validate_rental_shape(rental_period, quantity, period_price_minor)
        resource = Resource(id=str(uuid.uuid4()), tenant=tenant, name=name,
                            created_at=int(time.time()), branch_id=branch_id.strip(),
                            description=description.strip(), rental_period=rental_period,
                            quantity=quantity, period_price_minor=period_price_minor)
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
                     active: bool | None = None, branch_id: str | None = None,
                     description: str | None = None, quantity: int | None = None,
                     period_price_minor: int | None = None) -> Resource:
        resource = await self.get(tenant, resource_id)
        if resource is None:
            raise ResourceError("المورد غير موجود")
        if name is not None and not name.strip():
            raise ResourceError("اسم المورد لا يمكن أن يكون فارغاً")
        new_name = resource.name if name is None else name.strip()
        new_active = resource.active if active is None else bool(active)
        new_branch = resource.branch_id if branch_id is None else branch_id.strip()
        new_description = resource.description if description is None else description.strip()
        new_quantity = resource.quantity if quantity is None else quantity
        new_period_price = (resource.period_price_minor if period_price_minor is None
                            else period_price_minor)
        # rental_period IS NEVER EDITABLE HERE, ON PURPOSE — flipping an "hourly" resource with
        # live bookings into a "month" one (or back) would orphan every existing booking/
        # membership under the wrong engine mid-life. A shop that chose wrong creates a new
        # resource and retires this one (`active=False`), the same recovery path a wrong NAME or
        # branch already has.
        _validate_rental_shape(resource.rental_period, new_quantity, new_period_price)
        updated = Resource(id=resource.id, tenant=resource.tenant, name=new_name,
                           active=new_active, hourly_price_minor=resource.hourly_price_minor,
                           weekly=resource.weekly, exceptions=resource.exceptions,
                           created_at=resource.created_at, branch_id=new_branch,
                           description=new_description, image_key=resource.image_key,
                           rental_period=resource.rental_period, quantity=new_quantity,
                           period_price_minor=new_period_price)
        # DISABLING NEVER TOUCHES EXISTING BOOKINGS (spec §7/§8's own test) — this write only
        # flips the flag `bookings.py::create` reads BEFORE accepting a NEW one; every confirmed
        # row already in `coworking_bookings` is untouched by this call, on purpose.
        await self._store.put(RESOURCES, resource.id, updated.to_dict())
        return updated

    async def set_image(self, tenant: str, resource_id: str, *, image_key: str) -> Resource:
        """Saves the KEY `catalogue_image.py::store_image` already wrote — this method never
        touches `ObjectStore` itself, matching that module's own "the caller still has to save it
        onto the row" contract."""
        resource = await self.get(tenant, resource_id)
        if resource is None:
            raise ResourceError("المورد غير موجود")
        updated = Resource(
            id=resource.id, tenant=resource.tenant, name=resource.name, active=resource.active,
            hourly_price_minor=resource.hourly_price_minor, weekly=resource.weekly,
            exceptions=resource.exceptions, created_at=resource.created_at,
            branch_id=resource.branch_id, description=resource.description, image_key=image_key,
            rental_period=resource.rental_period, quantity=resource.quantity,
            period_price_minor=resource.period_price_minor)
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
            exceptions=exceptions_to_storage(exceptions or {}), created_at=resource.created_at,
            branch_id=resource.branch_id, description=resource.description,
            image_key=resource.image_key, rental_period=resource.rental_period,
            quantity=resource.quantity, period_price_minor=resource.period_price_minor)
        await self._store.put(RESOURCES, resource.id, updated.to_dict())
        return updated
