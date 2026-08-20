# =============================================================================
# affiliate-service — turning a REAL payment into a commission (spec §4, slices ٥/٦/٧)
# -----------------------------------------------------------------------------
# THE DURABLE READ, NEVER THE EVENT BUS. billing-service's own app/core/events.py is explicit:
# "The event bus is at-most-once and best effort... It is NOT how a money consequence is
# delivered... Anything that MUST happen goes through a durable, idempotent path and reads the
# fact back; the event only makes that path faster." This engine is built to that contract —
# sync() reads billing's own GET /internal/billing/invoices (v0.16.26+, added specifically for
# this: see the platform release note) rather than trusting a subscription to `payment.succeeded`
# to never miss a delivery. An event MAY call sync() sooner (a future increment — see the module's
# own TODO at the bottom); nothing here depends on one ever arriving.
#
# IDEMPOTENT BY CONSTRUCTION. A Commission's `id` IS the invoice id it was earned on — billing's
# own paid-invoice history is itself idempotent (the same invoice never appears twice, never
# changes which tenant it belongs to), so syncing the same history twice writes the same one row,
# never two. This is what makes sync() safe to call on a schedule, on a retry, or twice by
# accident, all at once.
#
# TWO KINDS, ONE ROW SHAPE (spec §4):
#   CONVERSION   billing's paid_sequence == 1 — the tenant's first-ever paid invoice. Eligible
#                only while the Referral it is keyed on is still within its conversion window
#                (ReferralRegistry.expires_at) — see _sync_conversion for the lapse check.
#   RENEWAL      billing's subscription_paid_sequence == Settings.AFFILIATE_RENEWAL_AT_NTH + 1
#                (renewal number N is the (N+1)th payment on that subscription). Disabled when
#                AFFILIATE_RENEWAL_AT_NTH is 0 — a silently-configured "renewal 0" would pay
#                every single renewal, which is not a policy anyone chose.
# =============================================================================
from __future__ import annotations

import time
from typing import Any

from app.core.models import (
    CONFIRMED,
    CONVERSION,
    COMMISSIONS,
    LAPSED,
    PENDING,
    RENEWAL,
    REFERRED,
    REVOKED,
    VOIDED,
    Commission,
)
from app.core.onboarding import Http


class CommissionEngine:
    def __init__(self, *, store, http: Http, billing_url: str, referrals,
                 hold_days: int = 7, renewal_at_nth: int = 0,
                 renewal_amount_halalas: int = 0) -> None:
        self._store = store
        self._http = http
        self._billing = billing_url.rstrip("/")
        self._referrals = referrals
        self._hold_days = hold_days
        self._renewal_at_nth = renewal_at_nth
        self._renewal_amount = renewal_amount_halalas

    async def sync(self, tenant: str) -> dict[str, Any]:
        """Reconcile ONE tenant's commissions against billing's own paid-invoice history. Safe to
        call repeatedly — see the module docstring on why every write here is idempotent."""
        if not self._billing:
            # No billing integration configured — a local/dev run, or a deployment that has not
            # wired this yet. Reported, not raised: the caller (an admin action, or a future
            # webhook) should see "nothing happened and here is why" rather than a 500.
            return {"synced": False, "reason": "billing_not_configured"}

        referral = await self._referrals.of_tenant(tenant)
        if referral is None:
            return {"synced": False, "reason": "no_referral"}
        if referral.status == REVOKED:
            # An admin already decided this referral earns nothing. No further reads, no further
            # commissions — same finality REJECTED gives an Application.
            return {"synced": False, "reason": "referral_revoked"}

        status, body = self._http.call(
            f"{self._billing}/internal/billing/invoices?tenant={tenant}&status=paid",
            method="GET", internal=True)
        if status != 200:
            return {"synced": False, "reason": f"billing_unreachable:{status}"}
        invoices = list((body or {}).get("invoices") or [])

        created: list[str] = []
        voided: list[str] = []

        for inv in invoices:
            if int(inv.get("paid_sequence", 0)) == 1:
                out = await self._sync_conversion(tenant, referral, inv)
            elif (self._renewal_at_nth > 0
                  and int(inv.get("subscription_paid_sequence", 0)) == self._renewal_at_nth + 1):
                out = await self._sync_renewal(tenant, referral, inv)
            else:
                continue
            if out == "created":
                created.append(str(inv.get("id", "")))
            elif out == "voided":
                voided.append(str(inv.get("id", "")))

        return {"synced": True, "created": created, "voided": voided}

    async def _sync_conversion(self, tenant: str, referral, inv: dict) -> str:
        existing = await self._store.get(COMMISSIONS, str(inv.get("id", "")))
        if existing is not None:
            return await self._reconcile_refund(Commission.from_dict(existing), inv)

        if referral.status == LAPSED:
            return "skipped"   # already decided — see lapse_if_expired's own idempotency

        paid_at = str(inv.get("paid_at") or "")
        paid_epoch = _parse_iso(paid_at)
        if referral.status == REFERRED and paid_epoch is not None and paid_epoch > referral.expires_at:
            # THE WINDOW LAPSED. This is the ONE place lapse_if_expired is meant to be called
            # from (see its own docstring) — the moment somebody is actually about to pay it.
            await self._referrals.lapse_if_expired(tenant, now=paid_epoch)
            return "skipped"

        if int(inv.get("refunded_minor", 0)) >= int(inv.get("amount_minor", 0)) and inv.get("amount_minor"):
            # FULLY REFUNDED BEFORE WE EVER SAW IT PAID — no commission is created at all, rather
            # than created-then-voided. Nothing was ever really earned.
            return "skipped"

        await self._create(tenant=tenant, affiliate_id=referral.affiliate_id, kind=CONVERSION,
                           amount_halalas=referral.commission_amount_halalas,
                           invoice_id=str(inv.get("id", "")), paid_at=paid_at)
        return "created"

    async def _sync_renewal(self, tenant: str, referral, inv: dict) -> str:
        if self._renewal_amount <= 0:
            # A renewal NUMBER configured with no AMOUNT is not a policy anyone chose either —
            # same "both halves or neither" reasoning as AFFILIATE_RENEWAL_AT_NTH being 0 alone.
            return "skipped"
        existing = await self._store.get(COMMISSIONS, str(inv.get("id", "")))
        if existing is not None:
            return await self._reconcile_refund(Commission.from_dict(existing), inv)
        if referral.status == REVOKED:
            return "skipped"

        if int(inv.get("refunded_minor", 0)) >= int(inv.get("amount_minor", 0)) and inv.get("amount_minor"):
            return "skipped"

        await self._create(tenant=tenant, affiliate_id=referral.affiliate_id, kind=RENEWAL,
                           amount_halalas=self._renewal_amount,
                           invoice_id=str(inv.get("id", "")), paid_at=str(inv.get("paid_at") or ""))
        return "created"

    async def _reconcile_refund(self, commission: Commission, inv: dict) -> str:
        """A refund that lands AFTER we already created the row — during the hold, most likely.
        Only a still-PENDING commission is voided here; a CONFIRMED one is a dispute for an admin
        to resolve by hand (same "system proposes, human decides" principle already applied to a
        suspended affiliate's pending commissions elsewhere in this file's own doc section)."""
        if commission.status != PENDING:
            return "unchanged"
        if int(inv.get("refunded_minor", 0)) < int(inv.get("amount_minor", 0) or 0):
            return "unchanged"
        commission.status = VOIDED
        await self._store.put(COMMISSIONS, commission.id, commission.to_dict())
        return "voided"

    async def _create(self, *, tenant: str, affiliate_id: str, kind: str, amount_halalas: int,
                      invoice_id: str, paid_at: str) -> None:
        now = int(time.time())
        paid_epoch = _parse_iso(paid_at)
        base = paid_epoch if paid_epoch is not None else now
        commission = Commission(
            id=invoice_id, tenant=tenant, affiliate_id=affiliate_id, kind=kind,
            amount_halalas=amount_halalas, status=PENDING, earned_at=paid_at,
            confirms_at=base + self._hold_days * 24 * 60 * 60, created_at=now,
        )
        await self._store.put(COMMISSIONS, commission.id, commission.to_dict())

    # ── "مُستحقة" -> "مؤكدة" ─────────────────────────────────────────────────────────────────
    async def confirm_if_due(self, commission_id: str, *, now: int | None = None) -> Commission | None:
        """Called at the moment somebody is about to act on a commission (a withdrawal request,
        an admin's own review — a later slice), never by a sweep — same lazy-check shape as
        ReferralRegistry.lapse_if_expired, and the same reasoning: nothing needs to know a hold
        has lapsed until somebody is about to rely on that fact."""
        row = await self._store.get(COMMISSIONS, commission_id)
        commission = Commission.from_dict(row) if row else None
        if commission is None or commission.status != PENDING:
            return commission
        if (now if now is not None else int(time.time())) < commission.confirms_at:
            return commission
        commission.status = CONFIRMED
        await self._store.put(COMMISSIONS, commission.id, commission.to_dict())
        return commission

    async def of_affiliate(self, affiliate_id: str, *, limit: int = 200) -> list[Commission]:
        rows, _ = await self._store.find(COMMISSIONS, {"affiliate_id": affiliate_id}, limit=limit,
                                         sort=("created_at", "asc"))
        return [Commission.from_dict(r) for r in rows]

    async def totals_for(self, affiliate_id: str) -> dict[str, int]:
        """One affiliate's own earnings, split by what a manager actually needs to answer "هل
        فريقي شغّال؟": CONFIRMED (withdrawable), PENDING still on hold, and how many referrals
        ever converted. `confirm_if_due` is deliberately NOT called here — a manager viewing his
        team is not "the moment somebody is about to act on a commission" (see confirm_if_due's
        own docstring); the promoter's own `/me/commissions` read remains the one place a hold
        actually advances, so a manager glancing at his team never silently flips a promoter's
        commission state from under him."""
        rows = await self.of_affiliate(affiliate_id)
        confirmed = sum(r.amount_halalas for r in rows if r.status == CONFIRMED)
        pending = sum(r.amount_halalas for r in rows if r.status == PENDING)
        return {"confirmed_halalas": confirmed, "pending_halalas": pending,
                "commission_count": len(rows)}

    async def team_summary(self, member_ids: list[str]) -> dict[str, Any]:
        """spec §10: a manager's real revenue transparency — per-promoter totals, the shops each
        of them actually brought and what those shops actually PAID (`revenue_for`), and the team
        sum of both. Reads each member's own commissions/revenue the same way his own dashboard
        would; nothing here is a second, driftable copy of that math."""
        members = []
        team_confirmed = 0
        team_pending = 0
        team_revenue = 0
        team_revenue_partial = False
        for member_id in member_ids:
            totals = await self.totals_for(member_id)
            revenue = await self.revenue_for(member_id)
            members.append({"affiliate_id": member_id, **totals, **revenue})
            team_confirmed += totals["confirmed_halalas"]
            team_pending += totals["pending_halalas"]
            team_revenue += revenue["total_net_revenue_minor"]
            team_revenue_partial = team_revenue_partial or revenue["revenue_partial"]
        return {"members": members, "team_confirmed_halalas": team_confirmed,
                "team_pending_halalas": team_pending,
                "team_net_revenue_minor": team_revenue,
                "team_revenue_partial": team_revenue_partial}

    async def revenue_for(self, affiliate_id: str) -> dict[str, Any]:
        """spec §10's own words: "الإيراد الحقيقي... قيمة الاشتراك الفعلية اللي دفعتها، لا رقماً
        مجرداً" — a manager checking his own math needs to see what the shop actually PAID, not
        just what we owe him for it. Reads billing's own durable paid-invoice history per referred
        shop, net of refunds — the SAME read sync() uses, so this can never drift from what
        actually decided a commission; it is simply never turned into money here.

        Best-effort per shop: an unreachable billing (or no integration configured) reports that
        shop's own revenue as unknown (`None`) rather than failing the whole read — one shop's
        billing hiccup must not hide a manager's entire team from him."""
        referrals = await self._referrals.of_affiliate(affiliate_id)
        shops = []
        total = 0
        partial = False
        for ref in referrals:
            net = None
            if self._billing:
                status, body = self._http.call(
                    f"{self._billing}/internal/billing/invoices?tenant={ref.tenant}&status=paid",
                    method="GET", internal=True)
                if status == 200:
                    invoices = list((body or {}).get("invoices") or [])
                    net = sum(int(inv.get("amount_minor", 0)) - int(inv.get("refunded_minor", 0))
                             for inv in invoices)
            shops.append({"tenant": ref.tenant, "shop_name": ref.shop_name,
                         "net_revenue_minor": net})
            if net is None:
                partial = True     # one shop's billing hiccup must not hide the rest of the sum
            else:
                total += net
        return {"shops": shops, "total_net_revenue_minor": total, "revenue_partial": partial}


def _parse_iso(value: str) -> int | None:
    """billing's own paid_at, folded to epoch seconds — or None for a blank/malformed one, which
    the caller treats as "cannot judge the window, so do not lapse a referral on bad data"."""
    if not value:
        return None
    try:
        import datetime as _dt
        return int(_dt.datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())
    except (ValueError, TypeError):
        return None


# TODO(next increment): a webhook receiver that calls sync() the moment billing's own
# payment.succeeded/invoice.paid events arrive, so a marketer's commission usually shows up in
# seconds rather than waiting on whatever triggers a periodic sync — sync() itself is already the
# durable source of truth either way, so this is purely a latency improvement, never a
# correctness one.
