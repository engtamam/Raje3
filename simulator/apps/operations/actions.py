"""App-specific Actions for services/operations — real HTTP against a real, spawned instance
(see `service.py` in this same folder). Each one is exactly what a real till/console/owner would
do over the wire: no shortcuts through the service's own Python code, no direct datastore access.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

import httpx

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
        async with httpx.AsyncClient() as client:
            r = await client.post(f"{self.base_url}/api/v1/affiliates", json=body,
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
        async with httpx.AsyncClient() as client:
            r = await client.post(f"{self.base_url}/api/v1/till/referral/register", json=body,
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
