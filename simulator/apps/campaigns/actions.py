"""App-specific Actions for services/campaigns — real HTTP against a real, spawned instance."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from simulator.common import httpclient
from simulator.common.action import ActionResult, Context
from simulator.shared.auth import auth_header

_READ_CAP = "campaigns.read"
_MANAGE_CAP = "campaigns.manage"


@dataclass
class GoalsAction:
    """`GET /api/v1/campaigns/goals` — the five cards, with their own locks and reasons; the
    console renders exactly what this returns rather than computing availability itself."""

    base_url: str
    tenant: str
    name: str = "campaign_goals"

    async def run(self, ctx: Context) -> ActionResult:
        headers = auth_header(tenant=self.tenant, caps=(_READ_CAP,))
        r = await httpclient.request("GET", f"{self.base_url}/api/v1/campaigns/goals",
                                     headers=headers, timeout=10.0)
        if r.status_code != 200:
            return ActionResult(ok=False, detail=f"campaign_goals refused: {r.status_code} "
                                                  f"{r.text}")
        return ActionResult(ok=True, detail="goals read", data=r.json())


@dataclass
class CreateCampaignAction:
    """`POST /api/v1/campaigns` — creates the campaign, and fires it immediately if manual
    (`goal="announce"` needs no offer/service scoping at all — the simplest of the five real
    goals to compose a scenario around).

    NEEDS A REAL, META-APPROVED WHATSAPP TEMPLATE FOR THE GOAL to actually succeed
    (`core/templates.py`'s own gate) — a genuine external peer this simulator has no fleet for yet.
    Every call in this simulator's own current test suite therefore proves the correct refusal
    ("لا يوجد قالب مفعّل لهذا الهدف"), not a successful launch — a real, honest environmental
    limit, the same shape `mutual_benefit_actions.py`'s own module docstring names for a different
    peer."""

    base_url: str
    tenant: str
    goal: str = "announce"
    owner_text: str = ""
    name: str = "create_campaign"

    async def run(self, ctx: Context) -> ActionResult:
        headers = auth_header(tenant=self.tenant, caps=(_MANAGE_CAP,))
        body: dict[str, Any] = {"goal": self.goal, "owner_text": self.owner_text}
        r = await httpclient.request("POST", f"{self.base_url}/api/v1/campaigns", json=body,
                                     headers=headers, timeout=10.0)
        if r.status_code != 200:
            return ActionResult(ok=False, detail=f"create_campaign: unexpected HTTP "
                                                  f"{r.status_code} {r.text}")
        payload = r.json()
        if payload.get("error"):
            return ActionResult(ok=False, detail=payload.get("reason") or "campaign refused",
                                data=payload)
        ctx.data[f"campaign:{payload.get('id')}"] = payload
        return ActionResult(ok=True, detail="campaign created", data=payload)


@dataclass
class ListCampaignsAction:
    """`GET /api/v1/campaigns` — drained (never a stale page-one-and-count), so `count` is always
    the real total regardless of how many campaigns this tenant has."""

    base_url: str
    tenant: str
    state: str = ""
    name: str = "list_campaigns"

    async def run(self, ctx: Context) -> ActionResult:
        headers = auth_header(tenant=self.tenant, caps=(_READ_CAP,))
        params = {"state": self.state} if self.state else {}
        r = await httpclient.request("GET", f"{self.base_url}/api/v1/campaigns", params=params,
                                     headers=headers, timeout=10.0)
        if r.status_code != 200:
            return ActionResult(ok=False, detail=f"list_campaigns refused: {r.status_code} "
                                                  f"{r.text}")
        return ActionResult(ok=True, detail="campaigns read", data=r.json())


@dataclass
class PauseCampaignAction:
    """`POST /api/v1/campaigns/{id}/pause` — stops a STANDING campaign; paused, never deleted."""

    base_url: str
    tenant: str
    campaign_id: str
    name: str = "pause_campaign"

    async def run(self, ctx: Context) -> ActionResult:
        headers = auth_header(tenant=self.tenant, caps=(_MANAGE_CAP,))
        r = await httpclient.request(
            "POST", f"{self.base_url}/api/v1/campaigns/{self.campaign_id}/pause",
            headers=headers, timeout=10.0)
        if r.status_code != 200:
            return ActionResult(ok=False, detail=f"pause_campaign: unexpected HTTP "
                                                  f"{r.status_code} {r.text}",
                                data={"status": r.status_code})
        return ActionResult(ok=True, detail="campaign paused", data=r.json())
