"""App-specific Actions for services/coworking — real HTTP against a real, spawned instance.
Fully self-contained: per-tenant CRUD (resources, join requests, bookings, a tenant-level pause
switch), no peer needed at all.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from simulator.common import httpclient
from simulator.common.action import ActionResult, Context
from simulator.shared.auth import auth_header

_MANAGE_CAP = "coworking.manage"


@dataclass
class CreateResourceAction:
    """`POST /api/v1/coworking/resources`."""

    base_url: str
    tenant: str
    resource_name: str
    name: str = "create_coworking_resource"

    async def run(self, ctx: Context) -> ActionResult:
        headers = auth_header(tenant=self.tenant, caps=(_MANAGE_CAP,))
        r = await httpclient.request(
            "POST", f"{self.base_url}/api/v1/coworking/resources",
            json={"name": self.resource_name}, headers=headers, timeout=10.0)
        if r.status_code != 200:
            return ActionResult(ok=False, detail=f"create_coworking_resource refused: "
                                                  f"{r.status_code} {r.text}")
        payload = r.json()
        if payload.get("error"):
            return ActionResult(ok=False, detail=payload.get("reason") or "create refused",
                                data=payload)
        ctx.data[f"coworking_resource:{payload.get('id')}"] = payload
        return ActionResult(ok=True, detail="resource created", data=payload)


@dataclass
class ListResourcesAction:
    """`GET /api/v1/coworking/resources`."""

    base_url: str
    tenant: str
    name: str = "list_coworking_resources"

    async def run(self, ctx: Context) -> ActionResult:
        headers = auth_header(tenant=self.tenant, caps=(_MANAGE_CAP,))
        r = await httpclient.request("GET", f"{self.base_url}/api/v1/coworking/resources",
                                     headers=headers, timeout=10.0)
        if r.status_code != 200:
            return ActionResult(ok=False, detail=f"list_coworking_resources refused: "
                                                  f"{r.status_code} {r.text}")
        return ActionResult(ok=True, detail="resources read", data=r.json())


@dataclass
class SetAvailabilityAction:
    """`PUT /api/v1/coworking/resources/{id}/availability` — an empty `weekly`/`exceptions` is a
    real, valid answer ("closed every day until configured"), never a required field."""

    base_url: str
    tenant: str
    resource_id: str
    hourly_price_minor: int = 1000
    weekly: dict[str, list[dict[str, int]]] = field(default_factory=dict)
    name: str = "set_coworking_availability"

    async def run(self, ctx: Context) -> ActionResult:
        headers = auth_header(tenant=self.tenant, caps=(_MANAGE_CAP,))
        body = {"weekly": self.weekly, "exceptions": {},
               "hourly_price_minor": self.hourly_price_minor}
        r = await httpclient.request(
            "PUT", f"{self.base_url}/api/v1/coworking/resources/{self.resource_id}/availability",
            json=body, headers=headers, timeout=10.0)
        if r.status_code != 200:
            return ActionResult(ok=False, detail=f"set_coworking_availability refused: "
                                                  f"{r.status_code} {r.text}")
        payload = r.json()
        if payload.get("error"):
            return ActionResult(ok=False, detail=payload.get("reason") or "refused", data=payload)
        return ActionResult(ok=True, detail="availability set", data=payload)


@dataclass
class BlockPhoneAction:
    """`POST /api/v1/coworking/joins/{phone}/block` — answerable even with NO prior join request
    at all (`core/joins.py`'s own module docstring)."""

    base_url: str
    tenant: str
    phone: str
    name: str = "block_coworking_phone"

    async def run(self, ctx: Context) -> ActionResult:
        headers = auth_header(tenant=self.tenant, caps=(_MANAGE_CAP,))
        r = await httpclient.request(
            "POST", f"{self.base_url}/api/v1/coworking/joins/{self.phone}/block",
            headers=headers, timeout=10.0)
        if r.status_code != 200:
            return ActionResult(ok=False, detail=f"block_coworking_phone refused: "
                                                  f"{r.status_code} {r.text}")
        return ActionResult(ok=True, detail="phone blocked", data=r.json())


@dataclass
class ListJoinsAction:
    """`GET /api/v1/coworking/joins`."""

    base_url: str
    tenant: str
    name: str = "list_coworking_joins"

    async def run(self, ctx: Context) -> ActionResult:
        headers = auth_header(tenant=self.tenant, caps=(_MANAGE_CAP,))
        r = await httpclient.request("GET", f"{self.base_url}/api/v1/coworking/joins",
                                     headers=headers, timeout=10.0)
        if r.status_code != 200:
            return ActionResult(ok=False, detail=f"list_coworking_joins refused: "
                                                  f"{r.status_code} {r.text}")
        return ActionResult(ok=True, detail="joins read", data=r.json())


@dataclass
class ListBookingsAction:
    """`GET /api/v1/coworking/bookings`."""

    base_url: str
    tenant: str
    name: str = "list_coworking_bookings"

    async def run(self, ctx: Context) -> ActionResult:
        headers = auth_header(tenant=self.tenant, caps=(_MANAGE_CAP,))
        r = await httpclient.request("GET", f"{self.base_url}/api/v1/coworking/bookings",
                                     headers=headers, timeout=10.0)
        if r.status_code != 200:
            return ActionResult(ok=False, detail=f"list_coworking_bookings refused: "
                                                  f"{r.status_code} {r.text}")
        return ActionResult(ok=True, detail="bookings read", data=r.json())


@dataclass
class SetPauseAction:
    """`PUT /api/v1/coworking/pause` — the tenant-level "stop taking new bookings" switch."""

    base_url: str
    tenant: str
    paused: bool
    name: str = "set_coworking_pause"

    async def run(self, ctx: Context) -> ActionResult:
        headers = auth_header(tenant=self.tenant, caps=(_MANAGE_CAP,))
        r = await httpclient.request("PUT", f"{self.base_url}/api/v1/coworking/pause",
                                     json={"paused": self.paused}, headers=headers, timeout=10.0)
        if r.status_code != 200:
            return ActionResult(ok=False, detail=f"set_coworking_pause: unexpected HTTP "
                                                  f"{r.status_code} {r.text}")
        return ActionResult(ok=True, detail="pause set", data=r.json())
