"""App-specific Actions for services/operations — real HTTP against a real, spawned instance
(see `service.py` in this same folder). Each one is exactly what a real till/console/owner would
do over the wire: no shortcuts through the service's own Python code, no direct datastore access.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from simulator.common import httpclient
from simulator.common.action import ActionResult, Context
from simulator.shared.auth import auth_header


@dataclass
class AddAffiliateAction:
    """The owner's own action: `POST /api/v1/affiliates` — onboard a marketer directly, by phone,
    with a custom code and negotiated terms (services/operations/app/core/affiliates.py)."""

    base_url: str
    tenant: str
    phone: str
    code: str
    discount_percent: int
    reward_type: str = "fixed_points"
    reward_params: dict[str, Any] = field(default_factory=lambda: {"points": 40})
    name: str = "add_affiliate"

    async def run(self, ctx: Context) -> ActionResult:
        body = {"phone": self.phone, "code": self.code, "discount_percent": self.discount_percent,
                "reward_type": self.reward_type, "reward_params": self.reward_params}
        headers = auth_header(tenant=self.tenant, caps=("operations.manage",))
        r = await httpclient.request("POST", f"{self.base_url}/api/v1/affiliates", json=body,
                                     headers=headers, timeout=10.0)
        if r.status_code != 200:
            return ActionResult(ok=False, detail=f"add_affiliate refused: {r.status_code} {r.text}")
        payload = r.json()
        ctx.data[f"affiliate:{self.code}"] = payload
        return ActionResult(ok=True, detail="affiliate added", data=payload)


@dataclass
class RegisterReferralAction:
    """A cashier's own action: `POST /api/v1/till/referral/register` — validate a code a new
    customer presented (services/operations/app/core/referral_redemption.py::register). This is
    the exact route whose usage-cap/duplicate-grant races this project found and fixed by hand
    earlier this session — the whole reason it is the first real action wired into the simulator."""

    base_url: str
    tenant: str
    code: str
    beneficiary_phone: str
    invoice_minor: int = 0
    name: str = "register_referral"

    async def run(self, ctx: Context) -> ActionResult:
        body = {"code": self.code, "phone": self.beneficiary_phone,
               "invoice_minor": self.invoice_minor}
        headers = auth_header(tenant=self.tenant, caps=("operations.record",))
        r = await httpclient.request(
            "POST", f"{self.base_url}/api/v1/till/referral/register", json=body,
            headers=headers, timeout=10.0)
        if r.status_code != 200:
            return ActionResult(ok=False,
                                detail=f"register_referral: unexpected HTTP {r.status_code}")
        payload = r.json()
        # `ok` here is the ROUTE's own verdict (a clean refusal is still HTTP 200, per
        # till.py's own convention — "كود الإحالة غير صالح" is a normal, well-formed answer, not
        # a server error) — the Action's own success means "the HTTP call worked", the payload's
        # own "ok" field is the business answer a scenario actually cares about.
        return ActionResult(ok=payload.get("ok") is True,
                            detail=payload.get("message") or "registered", data=payload)


@dataclass
class RegisterUniqueReferralAction:
    """Stage 8's own load-testing variant: mints a fresh, random beneficiary phone on EVERY
    invocation, so N calls represent N independent new customers (genuine load), never N callers
    racing over the SAME one — that is `RegisterReferralAction`'s own job (stage 5's capstone
    race proof). Composes `RegisterReferralAction` rather than duplicating its own HTTP logic."""

    base_url: str
    tenant: str
    code: str
    invoice_minor: int = 0
    name: str = "register_referral_unique"

    async def run(self, ctx: Context) -> ActionResult:
        phone = f"05{random.randint(10_000_000, 99_999_999)}"
        inner = RegisterReferralAction(base_url=self.base_url, tenant=self.tenant, code=self.code,
                                       beneficiary_phone=phone, invoice_minor=self.invoice_minor)
        return await inner.run(ctx)


@dataclass
class RecordVisitAction:
    """The shop floor's own action: `POST /api/v1/field/visits` (services/operations/app/api/v1/
    field.py::record_visit) — "this endpoint is the product, as far as the shop floor is
    concerned" in that route's own words. Unlike the till door (`till.py`), a human operator is
    NEVER required to send an `idempotency_key` — see that route's own comment on why a human
    retyping the same visit twice is recording a second real visit, not a retry.

    `service_ids` needs no real catalogue entry to work here: the field door only rejects an EMPTY
    list or a blank id (core/operations.py::record_visit, `allow_unknown_services` stays False on
    this path) — a made-up id is simply priced at 0 and recorded as-is, exactly like a shop that
    added a service today and typed its name before saving the catalogue row."""

    base_url: str
    tenant: str
    phone: str
    service_ids: list[str] = field(default_factory=lambda: ["svc-simulated"])
    branch_id: str = ""
    idempotency_key: str = ""
    name: str = "record_visit"

    async def run(self, ctx: Context) -> ActionResult:
        body: dict[str, Any] = {"phone": self.phone, "service_ids": self.service_ids}
        if self.branch_id:
            body["branch_id"] = self.branch_id
        if self.idempotency_key:
            body["idempotency_key"] = self.idempotency_key
        headers = auth_header(tenant=self.tenant, caps=("operations.record",))
        r = await httpclient.request("POST", f"{self.base_url}/api/v1/field/visits", json=body,
                                     headers=headers, timeout=10.0)
        if r.status_code != 201:
            return ActionResult(ok=False, detail=f"record_visit: unexpected HTTP {r.status_code} "
                                                  f"{r.text}")
        payload = r.json()
        # `record_visit` is one of this route's own "returned, not raised" refusals — a business
        # rule failing (an empty phone, no service chosen) still answers HTTP 201 with
        # `{"recorded": False, ...}` rather than a 4xx (see that route's own comment on why: the
        # platform strips a raised HTTPException's detail, and the reason IS the whole answer).
        if "recorded" in payload and payload["recorded"] is False:
            return ActionResult(ok=False, detail=payload.get("reason") or "recording refused",
                                data=payload)
        return ActionResult(ok=True, detail="visit recorded", data=payload)


@dataclass
class RecordUniqueVisitAction:
    """Stage-8-style load variant: a fresh, random customer phone on every invocation, so N calls
    represent N independent new customers — never N callers racing to record the SAME visit twice
    (that is `RecordVisitAction`'s own idempotency-key job). Composes `RecordVisitAction` rather
    than duplicating its own HTTP logic, the same pattern `RegisterUniqueReferralAction` uses."""

    base_url: str
    tenant: str
    branch_id: str = ""
    name: str = "record_visit_unique"

    async def run(self, ctx: Context) -> ActionResult:
        phone = f"05{random.randint(10_000_000, 99_999_999)}"
        inner = RecordVisitAction(base_url=self.base_url, tenant=self.tenant, phone=phone,
                                  branch_id=self.branch_id)
        return await inner.run(ctx)


@dataclass
class CreateBranchAction:
    """The owner's own action: `POST /api/v1/staff/branches` (services/operations/app/api/v1/
    staff.py). The tenant's first-ever branch call also silently creates its own "main" branch
    first (`B.ensure_main`) — real platform behaviour, not something this action works around."""

    base_url: str
    tenant: str
    branch_name: str
    city: str = "الرياض"
    # REQUIRED FROM THE SECOND BRANCH ON (services/operations/app/api/v1/staff.py's own
    # create_branch docstring) — a real coordinate, not a placeholder, so a scenario creating
    # more than one branch does not need to know this rule to get past it.
    lat: float = 24.7136
    lng: float = 46.6753
    name: str = "create_branch"

    async def run(self, ctx: Context) -> ActionResult:
        headers = auth_header(tenant=self.tenant, caps=("operations.manage",))
        body = {"name": self.branch_name, "city": self.city, "lat": self.lat, "lng": self.lng}
        r = await httpclient.request("POST", f"{self.base_url}/api/v1/staff/branches", json=body,
                                     headers=headers, timeout=10.0)
        if r.status_code != 201:
            return ActionResult(ok=False, detail=f"create_branch refused: {r.status_code} {r.text}")
        payload = r.json()
        ctx.data[f"branch:{self.branch_name}"] = payload
        return ActionResult(ok=True, detail="branch created", data=payload)


@dataclass
class HireMemberAction:
    """The owner's own action: `POST /api/v1/staff/members` — a REAL login, not a PIN (services/
    operations/app/api/v1/staff.py::hire_member). This is the only way to give someone a
    `person_id` that `branch_scope()` can ever match against a JWT's own `sub` claim — needs a
    real spawned identity-service behind `IDENTITY_SERVICE_URL` (see apps/identity/service.py)."""

    base_url: str
    tenant: str
    phone: str
    password: str
    role: str
    branch_id: str
    member_name: str = "Test Member"
    name: str = "hire_member"

    async def run(self, ctx: Context) -> ActionResult:
        headers = auth_header(tenant=self.tenant, caps=("operations.manage",))
        body = {"name": self.member_name, "phone": self.phone, "password": self.password,
               "role": self.role, "branch_id": self.branch_id}
        r = await httpclient.request("POST", f"{self.base_url}/api/v1/staff/members", json=body,
                                     headers=headers, timeout=10.0)
        if r.status_code != 201:
            return ActionResult(ok=False, detail=f"hire_member refused: {r.status_code} {r.text}")
        payload = r.json()
        ctx.data[f"member:{self.phone}"] = payload
        return ActionResult(ok=True, detail="member hired", data=payload)


@dataclass
class SetOperatorScopeAction:
    """The owner's own action: `PATCH /api/v1/staff/operators/{id}` — the one route that can set
    `visible_branch_ids`, `visible_all`, or deactivate (`active=False`) someone after hiring."""

    base_url: str
    tenant: str
    operator_id: str
    visible_all: bool | None = None
    visible_branch_ids: list[str] | None = None
    active: bool | None = None
    name: str = "set_operator_scope"

    async def run(self, ctx: Context) -> ActionResult:
        headers = auth_header(tenant=self.tenant, caps=("operations.manage",))
        body: dict[str, Any] = {}
        if self.visible_all is not None:
            body["visible_all"] = self.visible_all
        if self.visible_branch_ids is not None:
            body["visible_branch_ids"] = self.visible_branch_ids
        if self.active is not None:
            body["active"] = self.active
        r = await httpclient.request(
            "PATCH", f"{self.base_url}/api/v1/staff/operators/{self.operator_id}", json=body,
            headers=headers, timeout=10.0)
        if r.status_code != 200:
            return ActionResult(ok=False, detail=f"set_operator_scope refused: {r.status_code} "
                                                  f"{r.text}")
        return ActionResult(ok=True, detail="scope updated", data=r.json())


@dataclass
class ListOperatorsAction:
    """`GET /api/v1/staff/operators` — the exact route `branch_scope()` narrows (services/
    operations/app/api/v1/staff.py::list_operators). `caller_subject` (the `sub` claim) is what
    `branch_scope()` matches against a real Operator row's own `person_id`."""

    base_url: str
    tenant: str
    caller_subject: str
    caller_caps: tuple[str, ...] = ("operations.read", "bookings.read")
    name: str = "list_operators"

    async def run(self, ctx: Context) -> ActionResult:
        headers = auth_header(tenant=self.tenant, caps=self.caller_caps,
                              subject=self.caller_subject)
        r = await httpclient.request("GET", f"{self.base_url}/api/v1/staff/operators",
                                     headers=headers, timeout=10.0)
        if r.status_code != 200:
            return ActionResult(ok=False, detail=f"list_operators refused: {r.status_code} "
                                                  f"{r.text}", data={"status": r.status_code})
        payload = r.json()
        return ActionResult(ok=True, detail=f"{len(payload.get('operators', []))} operator(s) "
                                            f"visible", data=payload)
