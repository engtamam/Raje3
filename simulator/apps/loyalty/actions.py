"""App-specific Actions for services/loyalty — real HTTP against a real, spawned instance (see
`service.py` in this same folder). Second real app in the fleet after operations, proving the
whole `common/` engine is genuinely app-agnostic.

TWO TIERS, LIKE THE REAL SERVICE ITSELF: `EarnPointsAction` drives the INTERNAL door
(`/internal/loyalty/earn`, `X-Internal-Token`) — the same door the real event bus/catch-up calls,
never a shortcut into the ledger directly; every other action here drives the ordinary
capability-gated `/api/v1/loyalty/*` door a real operator/manager token would use.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from simulator.common import httpclient
from simulator.common.action import ActionResult, Context
from simulator.shared.auth import auth_header
from simulator.shared.service_env import INTERNAL_SERVICE_TOKEN


@dataclass
class SetGeneralPointsAction:
    """`PUT /api/v1/loyalty/settings/general` — the flat "points per visit" rule every tenant
    starts with NOTHING configured for (a real, deliberate default — earning with no points set
    is `{"earned": 0, "reason": "no points configured"}`, never an invented number). A scenario
    that wants `EarnPointsAction` to actually award something sets this first, the same as a real
    owner would from the settings screen before a single visit is ever recorded."""

    base_url: str
    tenant: str
    points: int
    name: str = "set_general_points"

    async def run(self, ctx: Context) -> ActionResult:
        headers = auth_header(tenant=self.tenant, caps=("loyalty.manage",))
        r = await httpclient.request(
            "PUT", f"{self.base_url}/api/v1/loyalty/settings/general", json={"points": self.points},
            headers=headers, timeout=10.0)
        if r.status_code != 200:
            return ActionResult(ok=False, detail=f"set_general_points refused: {r.status_code} "
                                                  f"{r.text}")
        return ActionResult(ok=True, detail="general points set", data=r.json())


@dataclass
class EarnPointsAction:
    """The internal door: `POST /internal/loyalty/earn` — awards points for one visit, idempotent
    on `visit_id` (services/loyalty/app/api/internal.py::earn). This is the ONLY way a real point
    ever enters the ledger; there is no public "grant yourself points" route, by design."""

    base_url: str
    tenant: str
    visit_id: str
    subject_ref: str
    # NON-EMPTY BY DEFAULT, DELIBERATELY: `EarnTree.points_for` sums a rate PER SERVICE ID in this
    # list (falling back to the general rate for each one it has no override for) — an empty list
    # sums zero elements and earns nothing no matter how high the general rate is configured, the
    # same "a made-up id is fine, no real catalogue entry needed" convention `RecordVisitAction`
    # already uses for the identical reason.
    service_ids: list[str] = field(default_factory=lambda: ["svc-simulated"])
    amount_halalas: int = 0
    name: str = "earn_points"

    async def run(self, ctx: Context) -> ActionResult:
        body = {"tenant": self.tenant, "visit_id": self.visit_id, "subject_ref": self.subject_ref,
                "service_ids": self.service_ids, "amount_halalas": self.amount_halalas}
        r = await httpclient.request(
            "POST", f"{self.base_url}/internal/loyalty/earn", json=body,
            headers={"X-Internal-Token": INTERNAL_SERVICE_TOKEN}, timeout=10.0)
        if r.status_code != 200:
            return ActionResult(ok=False, detail=f"earn_points: unexpected HTTP {r.status_code} "
                                                  f"{r.text}")
        payload = r.json()
        return ActionResult(ok=True, detail=f"earned {payload.get('earned', 0)} point(s)",
                            data=payload)


@dataclass
class BalanceAction:
    """`GET /api/v1/loyalty/balance/{subject_ref}` — the field screen's own read: total points and
    only the rewards this balance can afford."""

    base_url: str
    tenant: str
    subject_ref: str
    name: str = "loyalty_balance"

    async def run(self, ctx: Context) -> ActionResult:
        headers = auth_header(tenant=self.tenant, caps=("loyalty.read",))
        r = await httpclient.request(
            "GET", f"{self.base_url}/api/v1/loyalty/balance/{self.subject_ref}",
            headers=headers, timeout=10.0)
        if r.status_code != 200:
            return ActionResult(ok=False, detail=f"loyalty_balance refused: {r.status_code} "
                                                  f"{r.text}")
        return ActionResult(ok=True, detail="balance read", data=r.json())


@dataclass
class CreateRewardAction:
    """The owner/manager's own action: `POST /api/v1/loyalty/rewards`. `type="item"` needs neither
    a real catalogue service id (`type="service"`) nor a discount amount (`type="discount"`) — the
    simplest of the three real reward shapes to compose a scenario around."""

    base_url: str
    tenant: str
    reward_name: str
    cost: int
    reward_type: str = "item"
    name: str = "create_reward"

    async def run(self, ctx: Context) -> ActionResult:
        headers = auth_header(tenant=self.tenant, caps=("loyalty.manage",))
        body = {"name": self.reward_name, "cost": self.cost, "type": self.reward_type}
        r = await httpclient.request("POST", f"{self.base_url}/api/v1/loyalty/rewards", json=body,
                                     headers=headers, timeout=10.0)
        if r.status_code != 200:
            return ActionResult(ok=False, detail=f"create_reward refused: {r.status_code} "
                                                  f"{r.text}")
        payload = r.json()
        ctx.data[f"reward:{self.reward_name}"] = payload
        return ActionResult(ok=True, detail="reward created", data=payload)


@dataclass
class RedeemAction:
    """`POST /api/v1/loyalty/redeem` — `idempotency_key` is REQUIRED by the real route itself (a
    field phone in a service lane retries; a retry without a key is a second real spend)."""

    base_url: str
    tenant: str
    subject_ref: str
    reward_id: str
    idempotency_key: str
    name: str = "redeem"

    async def run(self, ctx: Context) -> ActionResult:
        headers = auth_header(tenant=self.tenant, caps=("loyalty.redeem",))
        body = {"subject_ref": self.subject_ref, "reward_id": self.reward_id,
               "idempotency_key": self.idempotency_key}
        r = await httpclient.request("POST", f"{self.base_url}/api/v1/loyalty/redeem", json=body,
                                     headers=headers, timeout=10.0)
        if r.status_code != 200:
            return ActionResult(ok=False, detail=f"redeem: unexpected HTTP {r.status_code} "
                                                  f"{r.text}")
        payload = r.json()
        if payload.get("error"):
            return ActionResult(ok=False, detail=payload.get("reason") or "redeem refused",
                                data=payload)
        return ActionResult(ok=True, detail="redeemed", data=payload)


@dataclass
class AdjustPointsAction:
    """The manager's own repair action: `POST /api/v1/loyalty/adjust` — "the apology the product
    could not make" (that route's own docstring): a manual grant/take-back with a written reason,
    never restarting the expiry clock."""

    base_url: str
    tenant: str
    subject_ref: str
    delta: int
    note: str
    idempotency_key: str
    name: str = "adjust_points"

    async def run(self, ctx: Context) -> ActionResult:
        headers = auth_header(tenant=self.tenant, caps=("loyalty.manage",))
        body = {"subject_ref": self.subject_ref, "delta": self.delta, "note": self.note,
               "idempotency_key": self.idempotency_key}
        r = await httpclient.request("POST", f"{self.base_url}/api/v1/loyalty/adjust", json=body,
                                     headers=headers, timeout=10.0)
        if r.status_code != 200:
            return ActionResult(ok=False, detail=f"adjust_points: unexpected HTTP {r.status_code} "
                                                  f"{r.text}")
        payload = r.json()
        if payload.get("ok") is False:
            return ActionResult(ok=False, detail=payload.get("reason") or "adjust refused",
                                data=payload)
        return ActionResult(ok=True, detail="adjusted", data=payload)
