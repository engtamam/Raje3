"""Shapes and collection names — Phase 2 of docs/خطة-تطبيق-الإحالة-والمسوقين-2026-09-27.md.

A "campaign" here is the shop's own referral program configuration: which of the three modes
rewards a referrer under, the anti-fraud rules that gate it, which of the eight reward types the
referrer gets, and the mandatory reward the NEW customer gets in return (the "win-win" rule the
owner's own spec insists on — no campaign may promise the referrer something without also naming
what the person they brought in gets).

PHASE 2 IS CONFIG ONLY. Nothing here is ever applied at a till — that is Phase 3's own job, through
the `EntitlementGateway` third-source seam already decided in the architecture study, not built yet.
A campaign row created here does nothing on its own; it is a fact waiting for a reader that does
not exist until the next phase.

TERMS ARE IMMUTABLE ONCE CREATED, same rule and same reason `mutual_benefit`'s own grant terms
take (services/operations/app/core/mutual_benefit.py's own history): a shop editing a live
campaign's reward mid-flight would mean two different sets of referrers were promised two
different things under the same code, with no record of which promise applied when. A changed mind
is a NEW campaign, never a PATCH on an old one. The only thing that ever changes after creation is
`active` — pausing/resuming, never touching what it pays out.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

CAMPAIGNS = "referral_campaigns"

# ── referral modes (spec §2) ─────────────────────────────────────────────────────────────────────
MODE_ONCE = "once"
MODE_X_TIMES = "x_times"
MODE_LIFETIME = "lifetime"
MODES = (MODE_ONCE, MODE_X_TIMES, MODE_LIFETIME)

# ── the referrer's own reward — all eight, config only this phase (spec §4a/§4b) ─────────────────
REWARD_FIXED_POINTS = "fixed_points"
REWARD_INVOICE_PERCENTAGE = "invoice_percentage"
REWARD_POINTS_MATCH = "points_match"
REWARD_MILESTONE_FREE_ITEM = "milestone_free_item"
REWARD_CASHBACK_POINTS = "cashback_points"
REWARD_STATUS_MULTIPLIER = "status_multiplier"
REWARD_TIME_BOOST = "time_boost"
REWARD_MYSTERY_BOX = "mystery_box"
REWARD_TYPES = (
    REWARD_FIXED_POINTS, REWARD_INVOICE_PERCENTAGE, REWARD_POINTS_MATCH,
    REWARD_MILESTONE_FREE_ITEM, REWARD_CASHBACK_POINTS, REWARD_STATUS_MULTIPLIER,
    REWARD_TIME_BOOST, REWARD_MYSTERY_BOX,
)

# ── the NEW customer's own reward (spec §4c, "قاعدة الطرفين") — a smaller, separate catalogue.
# Never the eight above: the new customer is offered something to hand the code over at the till,
# not a referral reward of their own (they have not referred anyone yet).
NEW_CUSTOMER_DISCOUNT_PERCENT = "discount_percent"
NEW_CUSTOMER_WELCOME_POINTS = "welcome_points"
NEW_CUSTOMER_REWARD_TYPES = (NEW_CUSTOMER_DISCOUNT_PERCENT, NEW_CUSTOMER_WELCOME_POINTS)

USAGE_CAP_PERIODS = ("day", "week", "month")


@dataclass(frozen=True)
class Campaign:
    id: str
    tenant: str
    created_at: int
    mode: str
    x_times_limit: int
    min_spend_minor: int
    usage_cap_period: str
    usage_cap_limit: int
    reward_type: str
    reward_params: dict[str, Any]
    new_customer_reward_type: str
    new_customer_reward_params: dict[str, Any]
    active: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "tenant": self.tenant, "created_at": self.created_at,
            "mode": self.mode, "x_times_limit": self.x_times_limit,
            "min_spend_minor": self.min_spend_minor,
            "usage_cap_period": self.usage_cap_period, "usage_cap_limit": self.usage_cap_limit,
            "reward_type": self.reward_type, "reward_params": self.reward_params,
            "new_customer_reward_type": self.new_customer_reward_type,
            "new_customer_reward_params": self.new_customer_reward_params,
            "active": self.active,
        }

    @staticmethod
    def from_dict(row: dict[str, Any]) -> "Campaign":
        return Campaign(
            id=row["id"], tenant=row["tenant"], created_at=int(row.get("created_at") or 0),
            mode=row["mode"], x_times_limit=int(row.get("x_times_limit") or 0),
            min_spend_minor=int(row.get("min_spend_minor") or 0),
            usage_cap_period=row.get("usage_cap_period") or "",
            usage_cap_limit=int(row.get("usage_cap_limit") or 0),
            reward_type=row["reward_type"], reward_params=dict(row.get("reward_params") or {}),
            new_customer_reward_type=row["new_customer_reward_type"],
            new_customer_reward_params=dict(row.get("new_customer_reward_params") or {}),
            active=bool(row.get("active", True)),
        )
