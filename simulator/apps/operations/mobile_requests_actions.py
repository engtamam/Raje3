"""App-specific Actions for services/operations' mobile/on-the-go service-request queue
(`app/api/v1/mobile_requests.py`) — real HTTP against a real, spawned instance, same discipline as
`actions.py` in this same folder (one folder per real service, per the README's own taxonomy).

TWO CAPABILITIES, TWO SCOPES, exactly as that route file's own module docstring describes:
`operations.mobile_requests_manage` (the full review queue: create/assign/accept/reject/complete/
no-show on anything) and `operations.mobile_requests_execute` (a field operator's scoped half:
list only what was assigned to THEM, mark تم/لم يتم only on that). Every action below takes
`caller_subject`/`caller_caps` explicitly (mirroring `ListOperatorsAction` in `actions.py`) — this
queue's whole design is WHO is calling, so a scenario proving the manager/execute split apart needs
to name a different subject and a different capability set per call, never one fixed identity.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from simulator.common import httpclient
from simulator.common.action import ActionResult, Context
from simulator.shared.auth import auth_header

_MANAGE_CAP = "operations.mobile_requests_manage"
_EXECUTE_CAP = "operations.mobile_requests_execute"


@dataclass
class CreateMobileRequestAction:
    """The shop's own manual door: `POST /api/v1/staff/mobile-requests` — manager-tier only (same
    tier as accept/reject), still lands PENDING like any bot-created request (field.py's own
    docstring: never quietly pre-approved just because a human at the shop typed it in)."""

    base_url: str
    tenant: str
    phone: str
    service_ids: list[str] = field(default_factory=lambda: ["svc-simulated"])
    requested_time: int = 0
    lat: float = 24.7136
    lng: float = 46.6753
    customer_name: str = ""
    operator_id: str = ""
    caller_subject: str = "owner"
    name: str = "create_mobile_request"

    async def run(self, ctx: Context) -> ActionResult:
        import time
        requested_time = self.requested_time or int(time.time()) + 3600
        body: dict[str, Any] = {
            "phone": self.phone, "customer_name": self.customer_name,
            "service_ids": self.service_ids, "requested_time": requested_time,
            "lat": self.lat, "lng": self.lng, "operator_id": self.operator_id,
        }
        headers = auth_header(tenant=self.tenant, caps=(_MANAGE_CAP,),
                              subject=self.caller_subject)
        r = await httpclient.request(
            "POST", f"{self.base_url}/api/v1/staff/mobile-requests", json=body,
            headers=headers, timeout=10.0)
        if r.status_code != 200:
            return ActionResult(ok=False, detail=f"create_mobile_request refused: "
                                                  f"{r.status_code} {r.text}")
        payload = r.json()
        ctx.data[f"mobile_request:{payload.get('id')}"] = payload
        return ActionResult(ok=True, detail="mobile request created", data=payload)


@dataclass
class ListMobileRequestsAction:
    """`GET /api/v1/staff/mobile-requests` — a manager sees the whole tenant (minus branch
    narrowing); an execute-tier caller is FORCED server-side to only their own assigned queue
    (`_scope()`'s own `assigned_to_filter`), never trusted from a query param."""

    base_url: str
    tenant: str
    caller_subject: str
    caller_caps: tuple[str, ...] = (_MANAGE_CAP,)
    status_filter: str = ""
    name: str = "list_mobile_requests"

    async def run(self, ctx: Context) -> ActionResult:
        headers = auth_header(tenant=self.tenant, caps=self.caller_caps,
                              subject=self.caller_subject)
        params = {"status_filter": self.status_filter} if self.status_filter else {}
        r = await httpclient.request(
            "GET", f"{self.base_url}/api/v1/staff/mobile-requests", params=params,
            headers=headers, timeout=10.0)
        if r.status_code != 200:
            return ActionResult(ok=False, detail=f"list_mobile_requests refused: "
                                                  f"{r.status_code} {r.text}",
                                data={"status": r.status_code})
        payload = r.json()
        return ActionResult(ok=True, detail=f"{len(payload.get('requests', []))} request(s) "
                                            f"visible", data=payload)


@dataclass
class AssignMobileRequestAction:
    """Manager-only: `POST /api/v1/staff/mobile-requests/{id}/assign` — `operator_id=""` clears an
    existing assignment, a real, distinct case (a manager taking a request back), not a no-op."""

    base_url: str
    tenant: str
    request_id: str
    operator_id: str
    caller_subject: str = "owner"
    name: str = "assign_mobile_request"

    async def run(self, ctx: Context) -> ActionResult:
        headers = auth_header(tenant=self.tenant, caps=(_MANAGE_CAP,),
                              subject=self.caller_subject)
        r = await httpclient.request(
            "POST", f"{self.base_url}/api/v1/staff/mobile-requests/{self.request_id}/assign",
            json={"operator_id": self.operator_id}, headers=headers, timeout=10.0)
        if r.status_code != 200:
            return ActionResult(ok=False, detail=f"assign_mobile_request refused: "
                                                  f"{r.status_code} {r.text}")
        return ActionResult(ok=True, detail="assigned", data=r.json())


@dataclass
class AcceptMobileRequestAction:
    """Manager-only: `POST /api/v1/staff/mobile-requests/{id}/accept`."""

    base_url: str
    tenant: str
    request_id: str
    caller_subject: str = "owner"
    name: str = "accept_mobile_request"

    async def run(self, ctx: Context) -> ActionResult:
        headers = auth_header(tenant=self.tenant, caps=(_MANAGE_CAP,),
                              subject=self.caller_subject)
        r = await httpclient.request(
            "POST", f"{self.base_url}/api/v1/staff/mobile-requests/{self.request_id}/accept",
            headers=headers, timeout=10.0)
        if r.status_code != 200:
            return ActionResult(ok=False, detail=f"accept_mobile_request refused: "
                                                  f"{r.status_code} {r.text}")
        return ActionResult(ok=True, detail="accepted", data=r.json())


@dataclass
class RejectMobileRequestAction:
    """Manager-only: `POST /api/v1/staff/mobile-requests/{id}/reject`."""

    base_url: str
    tenant: str
    request_id: str
    reason: str = ""
    caller_subject: str = "owner"
    name: str = "reject_mobile_request"

    async def run(self, ctx: Context) -> ActionResult:
        headers = auth_header(tenant=self.tenant, caps=(_MANAGE_CAP,),
                              subject=self.caller_subject)
        r = await httpclient.request(
            "POST", f"{self.base_url}/api/v1/staff/mobile-requests/{self.request_id}/reject",
            json={"reason": self.reason}, headers=headers, timeout=10.0)
        if r.status_code != 200:
            return ActionResult(ok=False, detail=f"reject_mobile_request refused: "
                                                  f"{r.status_code} {r.text}")
        return ActionResult(ok=True, detail="rejected", data=r.json())


@dataclass
class CompleteMobileRequestAction:
    """`POST /api/v1/staff/mobile-requests/{id}/complete` — records a real Visit; either capability
    tier may call it, but an execute-tier caller may only complete THEIR OWN assigned request
    (enforced server-side by `expected_assignee`, never trusted from this action's own input)."""

    base_url: str
    tenant: str
    request_id: str
    caller_subject: str = "owner"
    caller_caps: tuple[str, ...] = (_MANAGE_CAP,)
    name: str = "complete_mobile_request"

    async def run(self, ctx: Context) -> ActionResult:
        headers = auth_header(tenant=self.tenant, caps=self.caller_caps,
                              subject=self.caller_subject)
        r = await httpclient.request(
            "POST", f"{self.base_url}/api/v1/staff/mobile-requests/{self.request_id}/complete",
            headers=headers, timeout=10.0)
        if r.status_code != 200:
            return ActionResult(ok=False, detail=f"complete_mobile_request refused: "
                                                  f"{r.status_code} {r.text}")
        return ActionResult(ok=True, detail="completed", data=r.json())


@dataclass
class NoShowMobileRequestAction:
    """`POST /api/v1/staff/mobile-requests/{id}/no-show` — same either-tier/own-assignment rule as
    `CompleteMobileRequestAction` above; never creates a Visit."""

    base_url: str
    tenant: str
    request_id: str
    caller_subject: str = "owner"
    caller_caps: tuple[str, ...] = (_MANAGE_CAP,)
    name: str = "no_show_mobile_request"

    async def run(self, ctx: Context) -> ActionResult:
        headers = auth_header(tenant=self.tenant, caps=self.caller_caps,
                              subject=self.caller_subject)
        r = await httpclient.request(
            "POST", f"{self.base_url}/api/v1/staff/mobile-requests/{self.request_id}/no-show",
            headers=headers, timeout=10.0)
        if r.status_code != 200:
            return ActionResult(ok=False, detail=f"no_show_mobile_request refused: "
                                                  f"{r.status_code} {r.text}")
        return ActionResult(ok=True, detail="marked no-show", data=r.json())
