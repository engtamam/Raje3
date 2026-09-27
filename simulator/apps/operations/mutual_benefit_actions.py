"""App-specific Actions for services/operations' mutual-benefit (shop-to-shop referral
partnership) door (`app/api/v1/staff.py`'s own `/staff/mutual-benefit/*` routes, backed by
`app/core/mutual_benefit.py`). Same real service as every other `apps/operations/` action.

A REAL, DOCUMENTED ENVIRONMENTAL LIMIT, not a gap in these actions: `propose()` refuses with
`NOT_SUBSCRIBED` (402) unless a real billing/plans peer is wired (`BILLING_PLANS_DRIVER=http`) AND
the proposing tenant actually holds an active subscription for `feature.mutual_benefit` — the
default `NullPlans` driver every spawned operations instance boots with (no billing peer configured
anywhere in this simulator yet) answers `plan_id_for_key` with `""`, which `_is_subscribed` reads
as "always refuse" by design (`NullPlans`'s own docstring: "a trial of zero is the strict default
... the permissive default would let an unconfigured deployment take money for a plan nobody can
read"). So `propose()` is provably, correctly gated here — proven, not worked around — and a full
accept/reject lifecycle needs a real billing-service peer wired in, not yet part of this fleet.
"""
from __future__ import annotations

from dataclasses import dataclass

from simulator.common import httpclient
from simulator.common.action import ActionResult, Context
from simulator.shared.auth import auth_header

_MANAGE_CAP = "operations.manage"
_READ_CAP = "operations.read"


@dataclass
class SignupShopAction:
    """The real, unauthenticated door: `POST /api/v1/signup` (services/operations/app/api/v1/
    signup.py::open_shop) — creates a REAL tenant with a REAL owner phone registered in
    `signup.py`'s own `PHONE_INDEX`, the ONLY way `MutualBenefitEngine._lookup_tenant_by_phone`
    can ever resolve a real shop_b. NOT YET USABLE IN THIS SIMULATOR: `open_shop` itself calls out
    to a THIRD real peer, `TENANT_SERVICE_URL` (`platform/services/tenant-service`, `POST /internal/
    tenants`), which no `apps/` module here spawns yet — alongside `SIGNUP_REQUIRE_OTP=false` and a
    real identity-service, a full signup needs a real three-service Fleet not yet built. Kept here,
    real and ready, for whenever that peer is wired in."""

    base_url: str
    phone: str
    password: str
    shop_name: str
    name: str = "signup_shop"

    async def run(self, ctx: Context) -> ActionResult:
        body = {"phone": self.phone, "password": self.password, "shop_name": self.shop_name}
        r = await httpclient.request("POST", f"{self.base_url}/api/v1/signup", json=body,
                                     timeout=10.0)
        if r.status_code != 200:
            return ActionResult(ok=False, detail=f"signup_shop: unexpected HTTP {r.status_code} "
                                                  f"{r.text}")
        payload = r.json()
        if not payload.get("ok"):
            return ActionResult(ok=False, detail=payload.get("message") or "signup refused",
                                data=payload)
        return ActionResult(ok=True, detail="shop signed up", data=payload)


@dataclass
class ProposeMutualBenefitAction:
    """`POST /api/v1/staff/mutual-benefit/agreements` — see this module's own docstring for why
    this is expected to refuse with 402 (`NOT_SUBSCRIBED`) in every environment this simulator
    currently spawns, no billing peer being wired anywhere yet."""

    base_url: str
    tenant: str
    shop_b_phone: str
    condition_type: str = "min_total_minor"
    condition_value: str = "1"
    grant_validity_days: int = 30
    agreement_duration_days: int = 365
    name: str = "propose_mutual_benefit"

    async def run(self, ctx: Context) -> ActionResult:
        headers = auth_header(tenant=self.tenant, caps=(_MANAGE_CAP,))
        body = {
            "shop_b_phone": self.shop_b_phone, "condition_type": self.condition_type,
            "condition_value": self.condition_value,
            "grant_validity_days": self.grant_validity_days,
            "agreement_duration_days": self.agreement_duration_days,
        }
        r = await httpclient.request(
            "POST", f"{self.base_url}/api/v1/staff/mutual-benefit/agreements", json=body,
            headers=headers, timeout=10.0)
        if r.status_code != 200:
            return ActionResult(ok=False, detail=f"propose_mutual_benefit: HTTP {r.status_code} "
                                                  f"{r.text}", data={"status": r.status_code})
        payload = r.json()
        ctx.data[f"mutual_benefit:{payload.get('id')}"] = payload
        return ActionResult(ok=True, detail="agreement proposed", data=payload)


@dataclass
class ListMutualBenefitsAction:
    """`GET /api/v1/staff/mutual-benefit/agreements` — `operations.read` (a marketer also holds
    this), unlike propose/accept/reject which stay `operations.manage`."""

    base_url: str
    tenant: str
    name: str = "list_mutual_benefits"

    async def run(self, ctx: Context) -> ActionResult:
        headers = auth_header(tenant=self.tenant, caps=(_READ_CAP,))
        r = await httpclient.request(
            "GET", f"{self.base_url}/api/v1/staff/mutual-benefit/agreements",
            headers=headers, timeout=10.0)
        if r.status_code != 200:
            return ActionResult(ok=False, detail=f"list_mutual_benefits refused: "
                                                  f"{r.status_code} {r.text}")
        payload = r.json()
        return ActionResult(ok=True, detail=f"{len(payload.get('agreements', []))} agreement(s)",
                            data=payload)
