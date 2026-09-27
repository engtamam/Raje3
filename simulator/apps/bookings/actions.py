"""App-specific Actions for services/bookings — real HTTP against a real, spawned instance. See
`service.py`'s own module docstring: `CreateBookingAction` genuinely needs a real
OPERATIONS_SERVICE_URL peer wired (bookings asks operations for a service's own duration in
minutes over real HTTP), so every scenario using this file needs a real Fleet, never bookings
spawned alone.

`branch_id`/`operator_id`/`customer_id` need no real row anywhere: `_require_branch`'s own resolver
is `None` unless a real `branch_scope` peer is wired (services/bookings/app/api/v1/bookings.py),
the same lenient default every other cross-service reference in this simulator already relies on.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from simulator.common import httpclient
from simulator.common.action import ActionResult, Context
from simulator.shared.auth import auth_header

_READ_CAP = "bookings.read"
_WRITE_CAP = "bookings.write"


@dataclass
class CreateBookingAction:
    """`POST /api/v1/bookings` — needs a real, DURATION-CONFIGURED service id (see
    `apps/operations/actions.py::CreateServiceAction`) or `create()` refuses with "مدة هذه الخدمة
    غير مضبوطة", a real, documented refusal, never a crash."""

    base_url: str
    tenant: str
    branch_id: str
    operator_id: str
    customer_id: str
    service_ids: list[str]
    starts_at: int
    note: str = ""
    idempotency_key: str = ""
    name: str = "create_booking"

    async def run(self, ctx: Context) -> ActionResult:
        headers = auth_header(tenant=self.tenant, caps=(_WRITE_CAP,))
        body: dict[str, Any] = {
            "branch_id": self.branch_id, "operator_id": self.operator_id,
            "customer_id": self.customer_id, "service_ids": self.service_ids,
            "starts_at": self.starts_at, "note": self.note,
        }
        if self.idempotency_key:
            body["idempotency_key"] = self.idempotency_key
        r = await httpclient.request("POST", f"{self.base_url}/api/v1/bookings", json=body,
                                     headers=headers, timeout=10.0)
        if r.status_code != 200:
            return ActionResult(ok=False, detail=f"create_booking: unexpected HTTP "
                                                  f"{r.status_code} {r.text}")
        payload = r.json()
        if payload.get("error"):
            return ActionResult(ok=False, detail=payload.get("reason") or "booking refused",
                                data=payload)
        ctx.data[f"booking:{payload.get('id')}"] = payload
        return ActionResult(ok=True, detail="booking created", data=payload)


@dataclass
class ListBookingsAction:
    """`GET /api/v1/bookings?branch_id=&date=` — `date` is the route's own bucket key (a day),
    not a free-form range; see that route's own docstring for the exact format it expects."""

    base_url: str
    tenant: str
    branch_id: str
    date: str
    name: str = "list_bookings"

    async def run(self, ctx: Context) -> ActionResult:
        headers = auth_header(tenant=self.tenant, caps=(_READ_CAP,))
        r = await httpclient.request(
            "GET", f"{self.base_url}/api/v1/bookings",
            params={"branch_id": self.branch_id, "date": self.date}, headers=headers, timeout=10.0)
        if r.status_code != 200:
            return ActionResult(ok=False, detail=f"list_bookings refused: {r.status_code} "
                                                  f"{r.text}")
        payload = r.json()
        return ActionResult(ok=True, detail=f"{len(payload.get('bookings', []))} booking(s)",
                            data=payload)


@dataclass
class RescheduleBookingAction:
    """`PATCH /api/v1/bookings/{id}/reschedule` — "the drag-and-drop IS this call" (that route's
    own docstring): a new time, and optionally a different operator, in one write."""

    base_url: str
    tenant: str
    booking_id: str
    starts_at: int
    operator_id: str = ""
    name: str = "reschedule_booking"

    async def run(self, ctx: Context) -> ActionResult:
        headers = auth_header(tenant=self.tenant, caps=(_WRITE_CAP,))
        body: dict[str, Any] = {"starts_at": self.starts_at}
        if self.operator_id:
            body["operator_id"] = self.operator_id
        r = await httpclient.request(
            "PATCH", f"{self.base_url}/api/v1/bookings/{self.booking_id}/reschedule", json=body,
            headers=headers, timeout=10.0)
        if r.status_code != 200:
            return ActionResult(ok=False, detail=f"reschedule_booking: unexpected HTTP "
                                                  f"{r.status_code} {r.text}")
        payload = r.json()
        if payload.get("error"):
            return ActionResult(ok=False, detail=payload.get("reason") or "reschedule refused",
                                data=payload)
        return ActionResult(ok=True, detail="rescheduled", data=payload)


@dataclass
class CancelBookingAction:
    """`PATCH /api/v1/bookings/{id}/cancel`."""

    base_url: str
    tenant: str
    booking_id: str
    reason: str = ""
    name: str = "cancel_booking"

    async def run(self, ctx: Context) -> ActionResult:
        headers = auth_header(tenant=self.tenant, caps=(_WRITE_CAP,))
        r = await httpclient.request(
            "PATCH", f"{self.base_url}/api/v1/bookings/{self.booking_id}/cancel",
            json={"reason": self.reason}, headers=headers, timeout=10.0)
        if r.status_code != 200:
            return ActionResult(ok=False, detail=f"cancel_booking: unexpected HTTP "
                                                  f"{r.status_code} {r.text}")
        payload = r.json()
        if payload.get("error"):
            return ActionResult(ok=False, detail=payload.get("reason") or "cancel refused",
                                data=payload)
        return ActionResult(ok=True, detail="cancelled", data=payload)


@dataclass
class AttendBookingAction:
    """`PATCH /api/v1/bookings/{id}/attend` — the customer showed up; records a real Visit on
    operations' own side (same cross-service seam `MobileRequestService.complete` already uses)."""

    base_url: str
    tenant: str
    booking_id: str
    name: str = "attend_booking"

    async def run(self, ctx: Context) -> ActionResult:
        headers = auth_header(tenant=self.tenant, caps=(_WRITE_CAP,))
        r = await httpclient.request(
            "PATCH", f"{self.base_url}/api/v1/bookings/{self.booking_id}/attend", json={},
            headers=headers, timeout=10.0)
        if r.status_code != 200:
            return ActionResult(ok=False, detail=f"attend_booking: unexpected HTTP "
                                                  f"{r.status_code} {r.text}")
        payload = r.json()
        if payload.get("error"):
            return ActionResult(ok=False, detail=payload.get("reason") or "attend refused",
                                data=payload)
        return ActionResult(ok=True, detail="attended", data=payload)


@dataclass
class NoShowBookingAction:
    """`PATCH /api/v1/bookings/{id}/no-show`."""

    base_url: str
    tenant: str
    booking_id: str
    name: str = "no_show_booking"

    async def run(self, ctx: Context) -> ActionResult:
        headers = auth_header(tenant=self.tenant, caps=(_WRITE_CAP,))
        r = await httpclient.request(
            "PATCH", f"{self.base_url}/api/v1/bookings/{self.booking_id}/no-show", json={},
            headers=headers, timeout=10.0)
        if r.status_code != 200:
            return ActionResult(ok=False, detail=f"no_show_booking: unexpected HTTP "
                                                  f"{r.status_code} {r.text}")
        payload = r.json()
        if payload.get("error"):
            return ActionResult(ok=False, detail=payload.get("reason") or "no-show refused",
                                data=payload)
        return ActionResult(ok=True, detail="marked no-show", data=payload)
