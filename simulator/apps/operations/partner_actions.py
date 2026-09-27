"""App-specific Actions for services/operations' partner (till-company/reseller commission)
console — `app/api/v1/platform.py`'s own `/platform/partners*` (us managing partners) and
`app/api/v1/partner.py`'s own `/partner/*` (a partner reading its OWN shops/statements, scoped by
a `partner` JWT claim, never a path parameter — see that route's own module docstring on why: "a
partner id in a URL is a partner id an attacker can change").

FIRST-ATTRIBUTION, NEVER REWRITTEN (core/partners.py's own module docstring) — the internal
`/internal/operations/partner-stamp` door is what a real integration calls at tenant creation, and
this simulator's own `StampTenantAction` drives that exact door, real HTTP, real hashing, never a
direct datastore write.
"""
from __future__ import annotations

from dataclasses import dataclass

from simulator.common import httpclient
from simulator.common.action import ActionResult, Context
from simulator.shared.auth import auth_header
from simulator.shared.service_env import INTERNAL_SERVICE_TOKEN

_PLATFORM_CAP = "platform.operations"
_PARTNER_CAP = "partner.read"


@dataclass
class CreatePartnerAction:
    """`POST /api/v1/platform/partners` — us registering a reseller and minting its ONE-TIME-
    visible key. Platform-tier (`platform.operations`), no tenant needed at all — this is not a
    shop's own action."""

    base_url: str
    partner_name: str
    commission_rate: float = 0.1
    name: str = "create_partner"

    async def run(self, ctx: Context) -> ActionResult:
        headers = auth_header(tenant="", caps=(_PLATFORM_CAP,))
        body = {"name": self.partner_name, "commission_rate": self.commission_rate}
        r = await httpclient.request("POST", f"{self.base_url}/api/v1/platform/partners",
                                     json=body, headers=headers, timeout=10.0)
        if r.status_code != 200:
            return ActionResult(ok=False, detail=f"create_partner: unexpected HTTP "
                                                  f"{r.status_code} {r.text}")
        payload = r.json()
        if not payload.get("partner"):
            return ActionResult(ok=False, detail=payload.get("error") or "create refused",
                                data=payload)
        return ActionResult(ok=True, detail="partner created", data=payload)


@dataclass
class StampTenantAction:
    """`POST /internal/operations/partner-stamp` — attribute a real tenant to a real partner key,
    first-wins, permanently (core/partners.py's own whole reason for existing). `partner_key=""`
    stamps the tenant as a direct signup instead — a real, decided fact, not an absence."""

    base_url: str
    tenant: str
    partner_key: str = ""
    name: str = "stamp_tenant"

    async def run(self, ctx: Context) -> ActionResult:
        r = await httpclient.request(
            "POST", f"{self.base_url}/internal/operations/partner-stamp",
            json={"tenant": self.tenant, "partner_key": self.partner_key},
            headers={"X-Internal-Token": INTERNAL_SERVICE_TOKEN}, timeout=10.0)
        if r.status_code != 200:
            return ActionResult(ok=False, detail=f"stamp_tenant: unexpected HTTP {r.status_code} "
                                                  f"{r.text}")
        return ActionResult(ok=True, detail="tenant stamped", data=r.json())


@dataclass
class MyShopsAction:
    """`GET /api/v1/partner/shops` — the establishments THIS partner brought, scoped by a real
    `partner` JWT claim (never a path parameter, see this module's own docstring on why)."""

    base_url: str
    partner_id: str
    name: str = "my_shops"

    async def run(self, ctx: Context) -> ActionResult:
        headers = auth_header(tenant="", caps=(_PARTNER_CAP,),
                              extra_claims={"partner": self.partner_id})
        r = await httpclient.request("GET", f"{self.base_url}/api/v1/partner/shops",
                                     headers=headers, timeout=10.0)
        if r.status_code != 200:
            return ActionResult(ok=False, detail=f"my_shops refused: {r.status_code} {r.text}")
        return ActionResult(ok=True, detail="shops read", data=r.json())


@dataclass
class MyStatementsAction:
    """`GET /api/v1/partner/statements` — this partner's own commission statements, newest first;
    read-only, computed elsewhere (that route's own docstring: "a partner must never be able to
    trigger a recomputation")."""

    base_url: str
    partner_id: str
    name: str = "my_statements"

    async def run(self, ctx: Context) -> ActionResult:
        headers = auth_header(tenant="", caps=(_PARTNER_CAP,),
                              extra_claims={"partner": self.partner_id})
        r = await httpclient.request("GET", f"{self.base_url}/api/v1/partner/statements",
                                     headers=headers, timeout=10.0)
        if r.status_code != 200:
            return ActionResult(ok=False, detail=f"my_statements refused: {r.status_code} "
                                                  f"{r.text}")
        return ActionResult(ok=True, detail="statements read", data=r.json())
