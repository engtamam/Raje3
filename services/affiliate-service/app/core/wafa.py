# =============================================================================
# affiliate-service — «برنامج دعم الوفاء» (Tamam, 2026-08-20): a monthly stipend for marketers who
# keep SERVICING the shops they brought, replacing the retired RENEWAL commission (see
# core/commission.py's own note on why a flat cut on elapsed time was removed).
# -----------------------------------------------------------------------------
# THE TIER: floor(active_shops / tier_shops) * tier_amount — 50 shops = 500 SAR, 100 = 1000,
# 400 = 4000 (spec §8). Computed fresh at request time from a live count, never cached.
#
# ELIGIBLE ≠ ENTITLED — spec §8's own words: "غير آلية بالكامل". Reaching the shop-count
# threshold only unlocks the ABILITY to ask; a human decides based on REAL measurable
# performance, not shop count alone (a marketer who dumps 50 shops and vanishes must not
# out-earn one who actually keeps them). Two layers:
#   MANAGER   sees the same metrics (performance_for), gives an ADVISORY decision — he knows this
#             promoter best, but never binds the platform (he could be biased toward his own
#             team).
#   ADMIN     the platform's own BINDING call — may grant DESPITE a manager's rejection, or
#             refuse DESPITE a manager's approval. The manager's decision rides along on the row
#             as a documented input, never silently overridden without a trace.
#
# THE COOLDOWN ANCHORS TO THE REQUEST, NEVER THE DECISION (Tamam, 2026-08-20). If it anchored to
# `granted_at`, an admin one week slow to decide would push every future cycle a week later,
# compounding — a "monthly" stipend that drifts later every month is not a salary, it is a queue.
# Anchoring to `requested_at` of the LAST GRANTED request means the admin's review speed has ZERO
# effect on the marketer's next eligible date. A REJECTED request never sets this anchor at all —
# being wrongly refused must not cost him a real cycle once he is actually eligible again.
# =============================================================================
from __future__ import annotations

import time
from typing import Any

from app.core.models import (
    AFFILIATES,
    COMMISSIONS,
    CONFIRMED,
    LAPSED,
    PENDING,
    REFERRED,
    REVOKED,
    VOIDED,
    WAFA_APPROVE,
    WAFA_DECISIONS,
    WAFA_GRANTED,
    WAFA_REJECT,
    WAFA_REJECTED,
    WAFA_REQUESTED,
    WAFA_REQUESTS,
    Affiliate,
    Commission,
    WafaRequest,
    new_id,
)

_DAY = 24 * 60 * 60


class WafaError(Exception):
    def __init__(self, message: str, reason: str = "") -> None:
        super().__init__(message)
        self.reason = reason


class WafaService:
    def __init__(self, *, store, referrals, tier_shops: int = 50,
                 tier_amount_halalas: int = 50000, cooldown_days: int = 30,
                 retention_min: float = 0.70, refund_max: float = 0.15, tickets=None) -> None:
        self._s = store
        self._referrals = referrals
        self._tier_shops = tier_shops
        self._tier_amount = tier_amount_halalas
        self._cooldown_days = cooldown_days
        self._retention_min = retention_min
        self._refund_max = refund_max
        #: core/tickets.py's TicketReader, or None (spec §13, Tamam 2026-08-20). Optional and
        #: additive on purpose — see performance_for's own note on why it never changes
        #: `_recommend`'s formula yet.
        self._tickets = tickets

    # ── the measurable performance behind every recommendation ──────────────────────────────
    async def performance_for(self, affiliate_id: str) -> dict[str, Any]:
        """The exact metrics both the manager's own eyes (GET /me/team) and the system's own
        recommendation are built from — one computation, never two driftable copies. All
        measurable from data this service already owns; `support_kpis` (spec §13) is real
        support performance read from ticket-service's own consent-scoped share — additive and
        best-effort (a shop with no consent grant yet, or a ticket-service hiccup, degrades to
        `available: False`, never hides the rest of this dict). Deliberately NOT folded into
        `_recommend`'s own threshold yet — changing what decides a real payment is a separate
        policy call, not a side effect of adding a new read."""
        referrals = await self._referrals.of_affiliate(affiliate_id, limit=2000)
        active = sum(1 for r in referrals if r.status == REFERRED)
        ended = sum(1 for r in referrals if r.status in (LAPSED, REVOKED))
        total = active + ended
        # No referral has ended yet ⇒ no evidence AGAINST him ⇒ full retention, not zero.
        retention_rate = (active / total) if total else 1.0

        rows, _ = await self._s.find(COMMISSIONS, {"affiliate_id": affiliate_id}, limit=2000)
        commissions = [Commission.from_dict(r) for r in rows]
        voided = sum(1 for c in commissions if c.status == VOIDED)
        earned = sum(1 for c in commissions if c.status in (CONFIRMED, PENDING, VOIDED))
        refund_rate = (voided / earned) if earned else 0.0

        support = await self._aggregate_support_kpis(affiliate_id, referrals)
        return {"active_shops": active, "retention_rate": round(retention_rate, 4),
               "refund_rate": round(refund_rate, 4), "support_kpis": support}

    async def _aggregate_support_kpis(self, affiliate_id: str, referrals: list) -> dict[str, Any]:
        if self._tickets is None:
            return {"available": False, "reason": "tickets_not_configured"}
        per_shop = []
        for ref in referrals:
            out = await self._tickets.support_kpis(tenant=ref.tenant, grantee=affiliate_id)
            if out.get("available"):
                per_shop.append(out)
        if not per_shop:
            return {"available": False, "reason": "no_shared_tickets"}
        response_times = [s["avg_first_response_seconds"] for s in per_shop
                          if s.get("avg_first_response_seconds") is not None]
        resolution_times = [s["avg_resolution_seconds"] for s in per_shop
                            if s.get("avg_resolution_seconds") is not None]
        total_tickets = sum(s.get("ticket_count", 0) for s in per_shop)
        escalated_weighted = sum(s.get("escalation_rate", 0.0) * s.get("ticket_count", 0)
                                 for s in per_shop)
        return {
            "available": True,
            "shops_with_shared_tickets": len(per_shop),
            "ticket_count": total_tickets,
            "avg_first_response_seconds": (
                round(sum(response_times) / len(response_times), 1) if response_times else None),
            "avg_resolution_seconds": (
                round(sum(resolution_times) / len(resolution_times), 1) if resolution_times else None),
            "escalation_rate": round(escalated_weighted / total_tickets, 4) if total_tickets else 0.0,
        }

    def tier_amount(self, active_shops: int) -> int:
        return (active_shops // self._tier_shops) * self._tier_amount

    async def eligibility_preview(self, affiliate_id: str) -> dict[str, Any]:
        """A promoter's own "how close am I" read — the exact gap request() left: today
        active_shops/the threshold are computed inside request() and only surfaced by actually
        filing one (which REFUSES below threshold). A home screen needs this BEFORE a request
        exists, so it can show real progress instead of nothing at all."""
        perf = await self.performance_for(affiliate_id)
        active = perf["active_shops"]
        # Distance to the NEXT tier boundary — `active % tier_shops` is 0 both at "none yet" and
        # "sitting exactly on a boundary", and in both cases the next tier is a full tier away.
        remainder = active % self._tier_shops
        shops_until_next = self._tier_shops - remainder if remainder else self._tier_shops
        return {
            "active_shops": active, "tier_shops": self._tier_shops,
            "shops_until_next_tier": shops_until_next,
            "eligible": active >= self._tier_shops,
            "current_tier_amount_halalas": self.tier_amount(active),
            "retention_rate": perf["retention_rate"], "refund_rate": perf["refund_rate"],
            # SAME NUMBERS `performance_for` COMPUTES FOR HIM ALREADY, dropped from this response
            # until now — a manager could see his OWN team's support KPIs (GET /me/team) but never
            # his own, even though he is a marketer himself (Tamam, 2026-08-23: "مدير التسويق
            # يعتبر مسوّي، عنده نفس المؤشرات لنفسه"). Same best-effort shape (`available: False`
            # when no shop has shared its tickets yet, never a missing key).
            "support_kpis": perf["support_kpis"],
        }

    def _recommend(self, perf: dict[str, Any]) -> str:
        if perf["retention_rate"] >= self._retention_min and perf["refund_rate"] <= self._refund_max:
            return WAFA_APPROVE
        return WAFA_REJECT

    # ── the marketer's own request ────────────────────────────────────────────────────────────
    async def request(self, affiliate_id: str) -> dict[str, Any]:
        row = await self._s.get(AFFILIATES, affiliate_id)
        affiliate = Affiliate.from_dict(row) if row else None
        if affiliate is None:
            raise WafaError("المسوّق غير موجود.", reason="not_found")

        if await self._open_request_for(affiliate_id) is not None:
            raise WafaError("عندك طلب دعم وفاء قائم بالفعل.", reason="already_pending")

        last_granted = await self._last_granted(affiliate_id)
        now = int(time.time())
        if last_granted is not None:
            cooldown_ends = last_granted.requested_at + self._cooldown_days * _DAY
            if now < cooldown_ends:
                raise WafaError(
                    f"عندك دفعة دعم وفاء قبل أقل من {self._cooldown_days} يوماً — الطلب الجاي "
                    "متاح لاحقاً.", reason="cooldown")

        perf = await self.performance_for(affiliate_id)
        if perf["active_shops"] < self._tier_shops:
            raise WafaError(f"تحتاج {self._tier_shops} منشأة نشطة على الأقل.",
                            reason="below_threshold")

        wafa = WafaRequest(
            id=new_id(), affiliate_id=affiliate_id, active_shops=perf["active_shops"],
            tier_amount_halalas=self.tier_amount(perf["active_shops"]), status=WAFA_REQUESTED,
            requested_at=now, system_recommendation=self._recommend(perf),
            system_retention_rate=perf["retention_rate"], system_refund_rate=perf["refund_rate"],
        )
        await self._s.put(WAFA_REQUESTS, wafa.id, wafa.to_dict())
        return wafa.to_dict()

    async def _open_request_for(self, affiliate_id: str) -> WafaRequest | None:
        rows, _ = await self._s.find(
            WAFA_REQUESTS, {"affiliate_id": affiliate_id, "status": WAFA_REQUESTED}, limit=1)
        return WafaRequest.from_dict(rows[0]) if rows else None

    async def _last_granted(self, affiliate_id: str) -> WafaRequest | None:
        rows, _ = await self._s.find(
            WAFA_REQUESTS, {"affiliate_id": affiliate_id, "status": WAFA_GRANTED}, limit=1,
            sort=("requested_at", "desc"))
        return WafaRequest.from_dict(rows[0]) if rows else None

    async def of_affiliate(self, affiliate_id: str, *, limit: int = 100) -> list[WafaRequest]:
        rows, _ = await self._s.find(WAFA_REQUESTS, {"affiliate_id": affiliate_id}, limit=limit,
                                     sort=("requested_at", "desc"))
        return [WafaRequest.from_dict(r) for r in rows]

    async def get(self, wafa_id: str) -> WafaRequest | None:
        row = await self._s.get(WAFA_REQUESTS, wafa_id)
        return WafaRequest.from_dict(row) if row else None

    # ── the manager's advisory decision — never binding ──────────────────────────────────────
    async def manager_decide(self, wafa_id: str, *, decision: str, decided_by: str,
                             reason: str = "") -> WafaRequest:
        if decision not in WAFA_DECISIONS:
            raise WafaError("قرار غير معروف.", reason="bad_decision")
        wafa = await self.get(wafa_id)
        if wafa is None:
            raise WafaError("الطلب غير موجود.", reason="not_found")
        if wafa.status != WAFA_REQUESTED:
            raise WafaError("هذا الطلب تم البتّ فيه بالفعل.", reason="already_decided")
        wafa.manager_decision = decision
        wafa.manager_decided_by = decided_by
        wafa.manager_decided_at = int(time.time())
        wafa.manager_reason = reason[:500]
        await self._s.put(WAFA_REQUESTS, wafa.id, wafa.to_dict())
        return wafa

    # ── the platform's binding decision ───────────────────────────────────────────────────────
    async def admin_decide(self, wafa_id: str, *, decision: str, decided_by: str,
                           reason: str = "") -> WafaRequest:
        if decision not in WAFA_DECISIONS:
            raise WafaError("قرار غير معروف.", reason="bad_decision")
        wafa = await self.get(wafa_id)
        if wafa is None:
            raise WafaError("الطلب غير موجود.", reason="not_found")
        if wafa.status != WAFA_REQUESTED:
            raise WafaError("هذا الطلب تم البتّ فيه بالفعل.", reason="already_decided")

        wafa.decided_by = decided_by
        wafa.decided_at = int(time.time())
        wafa.reason = reason[:500]
        if decision == WAFA_APPROVE:
            wafa.status = WAFA_GRANTED
            wafa.granted_at = wafa.requested_at   # NEVER `now` — see module docstring
        else:
            wafa.status = WAFA_REJECTED
        await self._s.put(WAFA_REQUESTS, wafa.id, wafa.to_dict())
        return wafa

    async def list_pending(self, *, limit: int = 200) -> list[WafaRequest]:
        rows, _ = await self._s.find(WAFA_REQUESTS, {"status": WAFA_REQUESTED}, limit=limit,
                                     sort=("requested_at", "asc"))
        return [WafaRequest.from_dict(r) for r in rows]
