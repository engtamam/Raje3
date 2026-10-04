"""Phase 5a of docs/خطة-تطبيق-الإحالة-والمسوقين-2026-09-27.md — read-only performance reporting
over `core/referral_redemption.py`'s own grants and `core/affiliates.py`'s own affiliate rows.
Nothing here writes anything; every number is derived from data those two modules already wrote.

WHAT THIS DELIBERATELY DOES NOT REPORT, AND WHY (so a reader never wonders if a number was simply
forgotten):
  - A viral/K-factor. That needs a REFERRAL CHAIN (who referred the person who referred this
    person) — this system tracks one hop only (referrer -> beneficiary), by the plan doc's own
    design (services/referrals' own identity table is phone<->code, never a graph). A K-factor
    computed from single-hop data would be a fabricated number wearing a real one's name.
  - Clicks, impressions, or an "EPC" (earnings per click). Nothing in this product ever records a
    code being SHOWN or CLICKED — only a code being REGISTERED at the till. Reporting a
    click-through rate with no click event would be inventing the denominator.
  - Customer lifetime-value uplift. That needs tracking a customer's OWN spend over many visits
    after the referral, compared to a baseline — a real, separate longitudinal study this reporting
    layer does not attempt; a single-snapshot "uplift" number would be a guess dressed as data.

THE ONE NUMBER EVERY OTHER NUMBER HERE IS WEIGHED AGAINST: `cost_ratio` (reward cost ÷ revenue
attributed). A redemption count or a leaderboard rank alone is exactly the "vanity metric" pattern
industry guides warn against — activity that LOOKS like success but hides what it actually cost.
Every count in this module is paired with a currency figure for that reason, never reported alone.

THE REFERENCE CONVERSION RATE (100 points = 1 riyal, plan doc §7's own "قاعدة تحويل توضيحية...
رقم مرجعي فقط") is used ONLY here, to express a point-based reward's cost in the same currency
unit as revenue for one comparable ratio — never to credit, debit, or move anything real. No
service anywhere else in this fleet multiplies by it.

PERIODS ARE MEASURED BY THE EVENT THEY DESCRIBE, NOT ONE SHARED CLOCK — `registered_count` counts
grants by their own `created` timestamp (when the code was typed in), while `redeemed_count`,
`revenue_minor`, and every cost figure count by `redeemed_at` (when the money actually moved). A
grant registered in one period and redeemed weeks into the next must never have its revenue
attributed to the period it was merely TYPED IN — the industry-standard split between a program's
"opened" funnel stage and its "converted" one, applied here to avoid misdating real money.
"""
from __future__ import annotations

import time
from typing import Any

from app.core.affiliates import AFFILIATES, Affiliate
from app.core.referral_redemption import GRANTS, NEW_CUSTOMER_DISCOUNT_PERCENT, NEW_CUSTOMER_WELCOME_POINTS

# 100 points == 1 riyal == 100 halalas, so 1 point == 1 halala at this reference rate — see this
# module's own docstring for why it is a comparison unit only, never a real conversion.
_POINTS_TO_MINOR = 1


def _now() -> int:
    return int(time.time())


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _new_customer_cost_minor(grant: dict[str, Any]) -> int:
    """What the SHOP gave the new customer to redeem this grant — the other half of the reward
    cost, alongside the referrer's own credit below. Both must be counted, or `cost_ratio` would
    understate the program's real cost by exactly the win-win half the plan doc makes mandatory."""
    reward_type = grant.get("new_customer_reward_type") or ""
    params = grant.get("new_customer_reward_params") or {}
    if reward_type == NEW_CUSTOMER_DISCOUNT_PERCENT:
        invoice_minor = int(grant.get("invoice_minor") or 0)
        percent = int(params.get("percent") or 0)
        return (invoice_minor * percent) // 100
    if reward_type == NEW_CUSTOMER_WELCOME_POINTS:
        return int(params.get("points") or 0) * _POINTS_TO_MINOR
    return 0


def _referrer_cost_minor(grant: dict[str, Any]) -> int:
    """What the referrer/affiliate was actually credited — `referrer_reward_credited` is the
    honest flag (see redeem()'s own note on a lapsed licence answering 200 with nothing earned),
    so an uncredited grant costs the report nothing, exactly as it cost the shop nothing."""
    if not grant.get("referrer_reward_credited"):
        return 0
    return int(grant.get("referrer_points_credited") or 0) * _POINTS_TO_MINOR


class ReferralReportService:
    def __init__(self, store: Any) -> None:
        self._s = store

    async def _grants(self, tenant: str) -> list[dict[str, Any]]:
        rows, _ = await self._s.find(GRANTS, {"tenant": tenant}, limit=100000)
        return rows

    async def summary(self, tenant: str, *, since: int = 0,
                      until: int | None = None) -> dict[str, Any]:
        until = until if until is not None else _now()
        rows = await self._grants(tenant)
        registered = [r for r in rows if since <= int(r.get("created") or 0) <= until]
        redeemed = [r for r in rows
                   if r.get("redeemed_at") and since <= int(r["redeemed_at"]) <= until]

        revenue_minor = sum(int(r.get("invoice_minor") or 0) for r in redeemed)
        reward_cost_minor = sum(_referrer_cost_minor(r) + _new_customer_cost_minor(r)
                                for r in redeemed)
        new_customers = len({r["beneficiary_phone"] for r in redeemed
                            if r.get("beneficiary_phone")})

        return {
            "since": since, "until": until,
            "registered_count": len(registered),
            "redeemed_count": len(redeemed),
            "conversion_rate": _ratio(len(redeemed), len(registered)),
            "new_customers_acquired": new_customers,
            "revenue_minor": revenue_minor,
            "reward_cost_minor": reward_cost_minor,
            "cost_ratio": _ratio(reward_cost_minor, revenue_minor),
        }

    async def leaderboard(self, tenant: str, *, since: int = 0, until: int | None = None,
                          limit: int = 20) -> list[dict[str, Any]]:
        """Ranked by revenue driven, NEVER by redemption count alone — a high-count, low-ticket
        referrer must never outrank a low-count, high-ticket one just for showing up more often
        (this module's own docstring on the vanity-metric pattern). `redemptions` is still
        returned alongside, so a caller who wants the other ordering has the real number to sort
        by, never a rank that hid it."""
        until = until if until is not None else _now()
        rows = await self._grants(tenant)
        redeemed = [r for r in rows
                   if r.get("redeemed_at") and since <= int(r["redeemed_at"]) <= until]

        groups: dict[tuple[str, str], dict[str, Any]] = {}
        for r in redeemed:
            key = (r.get("referrer_phone") or "", r.get("source") or "referral")
            g = groups.setdefault(key, {
                "referrer_phone": key[0], "source": key[1], "redemptions": 0,
                "revenue_minor": 0, "reward_cost_minor": 0, "last_redeemed_at": 0,
            })
            g["redemptions"] += 1
            g["revenue_minor"] += int(r.get("invoice_minor") or 0)
            g["reward_cost_minor"] += _referrer_cost_minor(r)
            g["last_redeemed_at"] = max(g["last_redeemed_at"], int(r["redeemed_at"]))

        ranked = sorted(groups.values(), key=lambda g: g["revenue_minor"], reverse=True)
        return ranked[:max(0, limit)]

    async def campaign_breakdown(self, tenant: str, *, since: int = 0,
                                 until: int | None = None) -> list[dict[str, Any]]:
        """ORDINARY CAMPAIGN GRANTS ONLY — an affiliate's own code has no campaign at all
        (`campaign_id == ""`, see `register()`'s own affiliate short-circuit), so it can never
        appear here; see `affiliate_breakdown` for that tier's own equivalent."""
        until = until if until is not None else _now()
        rows = [r for r in await self._grants(tenant) if r.get("campaign_id")]
        registered = [r for r in rows if since <= int(r.get("created") or 0) <= until]

        by_campaign: dict[str, dict[str, Any]] = {}
        for r in registered:
            cid = r["campaign_id"]
            g = by_campaign.setdefault(cid, {"campaign_id": cid, "registered": 0, "redeemed": 0,
                                             "revenue_minor": 0})
            g["registered"] += 1
            if r.get("redeemed_at") and since <= int(r["redeemed_at"]) <= until:
                g["redeemed"] += 1
                g["revenue_minor"] += int(r.get("invoice_minor") or 0)

        result = list(by_campaign.values())
        for g in result:
            g["conversion_rate"] = _ratio(g["redeemed"], g["registered"])
        return sorted(result, key=lambda g: g["revenue_minor"], reverse=True)

    async def affiliate_breakdown(self, tenant: str) -> list[dict[str, Any]]:
        """EVERY AFFILIATE EVER ADDED, active or not — a paused affiliate can still hold a real
        unsettled balance an owner needs to see to know whether a settlement is owed; hiding a
        deactivated row would hide exactly the balance this report exists to surface."""
        rows, _ = await self._s.find(AFFILIATES, {"tenant": tenant}, limit=1000)
        affiliates = [Affiliate.from_dict(r) for r in rows]
        redeemed = [r for r in await self._grants(tenant)
                   if r.get("source") == "affiliate" and r.get("redeemed_at")]

        by_affiliate: dict[str, dict[str, Any]] = {}
        for r in redeemed:
            aid = r.get("affiliate_id") or ""
            g = by_affiliate.setdefault(
                aid, {"redemptions": 0, "revenue_minor": 0, "last_redeemed_at": 0})
            g["redemptions"] += 1
            g["revenue_minor"] += int(r.get("invoice_minor") or 0)
            g["last_redeemed_at"] = max(g["last_redeemed_at"], int(r["redeemed_at"]))

        out = []
        for a in affiliates:
            stats = by_affiliate.get(
                a.id, {"redemptions": 0, "revenue_minor": 0, "last_redeemed_at": 0})
            out.append({
                "affiliate_id": a.id, "phone": a.phone, "code": a.code, "active": a.active,
                "redemptions": stats["redemptions"], "revenue_minor": stats["revenue_minor"],
                "last_redeemed_at": stats["last_redeemed_at"],
                "unsettled_points": a.unsettled_points,
                "total_earned_points": a.total_earned_points,
            })
        return sorted(out, key=lambda g: g["revenue_minor"], reverse=True)
