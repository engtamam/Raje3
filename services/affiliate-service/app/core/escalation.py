# =============================================================================
# affiliate-service — §13's auto-escalation: a shop's ticket moves to the manager on its own
# -----------------------------------------------------------------------------
# "خليها 24 ساعه بعدها تتصعد على طول لمديره... ولو موظف موقوف تتصعد للمدير
# مباشرة". ticket-service (v0.16.29+) supplies exactly ONE primitive — escalate a covered ticket
# and optionally reassign it — and deliberately knows nothing about WHY. Every bit of policy
# (the 24h default, the suspended-marketer rule) lives here, config-driven, never hardcoded.
#
# IDEMPOTENT BY THE TICKET'S OWN `escalated` FLAG. A sweep that runs every few minutes must never
# re-escalate a ticket it already moved last tick — `ticket_kpis.escalated` (read straight off
# ticket-service's own append-only log) is the one source of truth for "already handled", never a
# local flag this service could drift from.
#
# ONLY A PROMOTER HAS SOMEWHERE TO ESCALATE TO. A manager-owned referral's own tickets have no
# `parent_id` above them — nothing here moves those; technical support's always-on oversight
# (spec §13, unrelated to this mechanism) is the safety net for that case, not a reassignment.
#
# THE MANAGER GETS HIS OWN SHARE THE MOMENT HE FIRST RECEIVES ONE — ShareGrant is per-grantee,
# never inherited from the promoter who was escalated away from. Provisioned lazily, once, right
# here (best-effort: a failed grant delays his OWN read/reply, never blocks the escalation itself
# — the ticket has already moved either way).
# =============================================================================
from __future__ import annotations

import time
from typing import Any

from app.core.models import ACTIVE, AFFILIATES, SUSPENDED, Affiliate

_HOUR = 60 * 60


class TicketEscalationService:
    def __init__(self, *, store, referrals, tickets, timeout_hours: int = 24,
                 sweep_max: int = 200) -> None:
        self._s = store
        self._referrals = referrals
        self._tickets = tickets
        self._timeout_hours = timeout_hours
        self._sweep_max = sweep_max

    async def _affiliate(self, affiliate_id: str) -> Affiliate | None:
        row = await self._s.get(AFFILIATES, affiliate_id)
        return Affiliate.from_dict(row) if row else None

    async def sweep(self) -> dict[str, Any]:
        """One bounded pass over every referral with a manager above it — same "capped, records
        where it stopped" shape as commissions/sweep and leads/tick. Meant for a k3s CronJob."""
        if self._tickets is None:
            return {"swept": False, "reason": "tickets_not_configured"}

        referrals = await self._referrals.all_ever(limit=self._sweep_max)
        checked = 0
        escalated = 0
        errors: list[str] = []

        for ref in referrals:
            affiliate = await self._affiliate(ref.affiliate_id)
            if affiliate is None or not affiliate.parent_id:
                continue   # nobody above him — nothing this mechanism can move it to
            checked += 1
            try:
                if affiliate.status == SUSPENDED:
                    moved = await self._escalate_all_open(
                        tenant=ref.tenant, affiliate=affiliate, level="suspended",
                        reason="الموظف موقوف — تصعيد فوري لمديره")
                else:
                    moved = await self._escalate_overdue(tenant=ref.tenant, affiliate=affiliate)
                escalated += moved
            except Exception as exc:                                          # noqa: BLE001
                # One shop's ticket-service hiccup must not abort the whole sweep — every other
                # referral still gets checked.
                errors.append(f"{ref.tenant}:{str(exc)[:100]}")

        return {"swept": True, "referrals_checked": checked, "tickets_escalated": escalated,
               "errors": errors, "truncated": len(referrals) >= self._sweep_max}

    async def _escalate_overdue(self, *, tenant: str, affiliate: Affiliate) -> int:
        """Any ticket still with no first response after `timeout_hours` — the 24h default rule."""
        try:
            tickets = await self._tickets.list_tickets(tenant=tenant, grantee=affiliate.id)
        except Exception:                                                     # noqa: BLE001
            return 0   # no active grant yet, or unreachable — nothing to escalate this tick
        moved = 0
        now = time.time()
        for t in tickets:
            tid = t.get("id", "")
            if not tid or t.get("status") in ("resolved", "closed"):
                continue
            try:
                full = await self._tickets.get_ticket(tenant=tenant, grantee=affiliate.id,
                                                       ticket_id=tid)
            except Exception:                                                 # noqa: BLE001
                continue
            kpis = full.get("kpis") or {}
            if kpis.get("escalated"):
                continue   # idempotent — already moved, a prior tick handled it
            if kpis.get("first_response_at"):
                continue   # he already answered — no timeout to enforce
            created = _parse_iso(kpis.get("created_at", ""))
            if created is None or now - created < self._timeout_hours * _HOUR:
                continue
            await self._move(tenant=tenant, affiliate=affiliate, ticket_id=tid,
                             level="timeout", reason=f"لا رد خلال {self._timeout_hours} ساعة")
            moved += 1
        return moved

    async def _escalate_all_open(self, *, tenant: str, affiliate: Affiliate, level: str,
                                 reason: str) -> int:
        try:
            tickets = await self._tickets.list_tickets(tenant=tenant, grantee=affiliate.id)
        except Exception:                                                     # noqa: BLE001
            return 0
        moved = 0
        for t in tickets:
            tid = t.get("id", "")
            if not tid or t.get("status") in ("resolved", "closed"):
                continue
            try:
                full = await self._tickets.get_ticket(tenant=tenant, grantee=affiliate.id,
                                                       ticket_id=tid)
            except Exception:                                                 # noqa: BLE001
                continue
            if (full.get("kpis") or {}).get("escalated"):
                continue
            await self._move(tenant=tenant, affiliate=affiliate, ticket_id=tid, level=level,
                             reason=reason)
            moved += 1
        return moved

    async def _move(self, *, tenant: str, affiliate: Affiliate, ticket_id: str, level: str,
                    reason: str) -> None:
        await self._tickets.escalate(tenant=tenant, grantee=affiliate.id, ticket_id=ticket_id,
                                     assignee=affiliate.parent_id, level=level, reason=reason)
        # BEST-EFFORT: the manager's own share, provisioned the moment he first receives an
        # escalated ticket — never blocks the escalation itself, which already happened above.
        try:
            manager = await self._affiliate(affiliate.parent_id)
            if manager is not None and manager.status == ACTIVE:
                await self._tickets.grant_share(tenant=tenant, grantee=affiliate.parent_id,
                                                granted_by="", write=True)
        except Exception:                                                     # noqa: BLE001
            pass


def _parse_iso(value: str) -> float | None:
    if not value:
        return None
    try:
        import datetime as _dt
        return _dt.datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except (ValueError, TypeError):
        return None
