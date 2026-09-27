"""App-specific Actions for services/referrals — the global, standalone anonymous-referral-code
campaign engine. Real HTTP against a real, spawned instance; fully self-contained (per-tenant
CRUD, no peer needed)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from simulator.common import httpclient
from simulator.common.action import ActionResult, Context
from simulator.shared.auth import auth_header

_MANAGE_CAP = "referrals.manage"


@dataclass
class CreateCampaignAction:
    """`POST /api/v1/referrals/campaigns` — `mode="once"` needs no extra caps/limits at all, the
    simplest of the three real modes; `reward_type="fixed_points"` and
    `new_customer_reward_type="welcome_points"` need no extra params either."""

    base_url: str
    tenant: str
    mode: str = "once"
    reward_type: str = "fixed_points"
    reward_params: dict[str, Any] = field(default_factory=lambda: {"points": 50})
    new_customer_reward_type: str = "welcome_points"
    new_customer_reward_params: dict[str, Any] = field(default_factory=lambda: {"points": 20})
    name: str = "create_referral_campaign"

    async def run(self, ctx: Context) -> ActionResult:
        headers = auth_header(tenant=self.tenant, caps=(_MANAGE_CAP,))
        body = {
            "mode": self.mode, "reward_type": self.reward_type,
            "reward_params": self.reward_params,
            "new_customer_reward_type": self.new_customer_reward_type,
            "new_customer_reward_params": self.new_customer_reward_params,
        }
        r = await httpclient.request("POST", f"{self.base_url}/api/v1/referrals/campaigns",
                                     json=body, headers=headers, timeout=10.0)
        if r.status_code != 200:
            return ActionResult(ok=False, detail=f"create_referral_campaign: unexpected HTTP "
                                                  f"{r.status_code} {r.text}")
        payload = r.json()
        if payload.get("error"):
            return ActionResult(ok=False, detail=payload.get("reason") or "campaign refused",
                                data=payload)
        ctx.data[f"referral_campaign:{payload.get('id')}"] = payload
        return ActionResult(ok=True, detail="referral campaign created", data=payload)


@dataclass
class ListCampaignsAction:
    """`GET /api/v1/referrals/campaigns`."""

    base_url: str
    tenant: str
    active_only: bool = False
    name: str = "list_referral_campaigns"

    async def run(self, ctx: Context) -> ActionResult:
        headers = auth_header(tenant=self.tenant, caps=(_MANAGE_CAP,))
        r = await httpclient.request(
            "GET", f"{self.base_url}/api/v1/referrals/campaigns",
            params={"active_only": self.active_only}, headers=headers, timeout=10.0)
        if r.status_code != 200:
            return ActionResult(ok=False, detail=f"list_referral_campaigns refused: "
                                                  f"{r.status_code} {r.text}")
        return ActionResult(ok=True, detail="campaigns read", data=r.json())


@dataclass
class GetCampaignAction:
    """`GET /api/v1/referrals/campaigns/{id}`."""

    base_url: str
    tenant: str
    campaign_id: str
    name: str = "get_referral_campaign"

    async def run(self, ctx: Context) -> ActionResult:
        headers = auth_header(tenant=self.tenant, caps=(_MANAGE_CAP,))
        r = await httpclient.request(
            "GET", f"{self.base_url}/api/v1/referrals/campaigns/{self.campaign_id}",
            headers=headers, timeout=10.0)
        if r.status_code != 200:
            return ActionResult(ok=False, detail=f"get_referral_campaign refused: "
                                                  f"{r.status_code} {r.text}",
                                data={"status": r.status_code})
        return ActionResult(ok=True, detail="campaign read", data=r.json())
