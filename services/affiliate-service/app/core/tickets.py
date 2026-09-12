# =============================================================================
# affiliate-service — a shop's tickets, consent-scoped (spec §13)
# -----------------------------------------------------------------------------
# Reads AND writes ticket-service's own scoped-visibility primitive (ShareGrant, v0.16.27+ reads,
# v0.16.28+ writes) — never a shop's tickets directly, only what that shop's OWN consent grant to
# THIS marketer (grantee= affiliate_id) actually covers, and only what it PERMITS ("read" always;
# "write" only if operations-service asked for it at signup — see core/signup.py in operations).
# A durable call either way, same "peer acts on a durable fact, never an event alone" contract as
# CommissionEngine's own billing read.
#
# READS ARE STRUCTURE + PERFORMANCE ONLY. ticket-service's own projection already strips
# subject/body/meta (the shop's customer PII, not this service's — or a marketer's — to read
# wholesale); this module never asks for more than that on a READ. A WRITE necessarily carries
# real text (the marketer's own reply) — that is the one place free text crosses this boundary,
# and it is exactly the text the marketer typed himself, attributed to HIM (ticket-service's own
# grantee pseudonym, never the shop's raiser_ref) in the append-only log.
#
# BEST-EFFORT, PER TENANT, ON READS. One shop's ticket-service hiccup — or simply NO_ACTIVE_GRANT,
# the honest common case before operations-service has wired a share for this pair — must not hide
# a marketer's whole team's KPIs (see support_kpis). WRITES are never silently swallowed this way:
# a marketer who tries to reply and gets refused needs to SEE that, not have it vanish.
# =============================================================================
from __future__ import annotations

import asyncio
import urllib.parse
from typing import Any

from app.core.onboarding import Http


class TicketError(Exception):
    def __init__(self, message: str, reason: str = "") -> None:
        super().__init__(message)
        self.reason = reason


class TicketReader:
    def __init__(self, *, http: Http, ticket_service_url: str) -> None:
        self._http = http
        self._base = ticket_service_url.rstrip("/")

    async def support_kpis(self, *, tenant: str, grantee: str,
                           ticket_cap: int = 50) -> dict[str, Any]:
        """One shop's support performance for one marketer — averaged over up to `ticket_cap`
        tickets (bounded: the list route has no per-ticket KPIs, so this is N+1 calls, and a
        shop's ticket volume is never so large that a hard cap matters in practice)."""
        if not self._base:
            return {"available": False, "reason": "ticket_service_not_configured"}
        q = urllib.parse.urlencode({"tenant": tenant, "grantee": grantee})
        status, body = await asyncio.to_thread(
            self._http.call, f"{self._base}/internal/tickets?{q}", method="GET", internal=True)
        if status == 409:
            # NOT an error — the honest common case before operations-service has wired a share
            # for this (tenant, grantee) pair at signup, or a shop that revoked consent.
            return {"available": False, "reason": "no_active_grant"}
        if status != 200:
            return {"available": False, "reason": f"unreachable:{status}"}
        tickets = list((body or {}).get("tickets") or [])[:ticket_cap]

        response_times: list[float] = []
        resolution_times: list[float] = []
        escalated = 0
        for t in tickets:
            tid = t.get("id", "")
            if not tid:
                continue
            qi = urllib.parse.urlencode({"tenant": tenant, "grantee": grantee})
            s2, b2 = await asyncio.to_thread(
                self._http.call, f"{self._base}/internal/tickets/{tid}?{qi}",
                method="GET", internal=True)
            if s2 != 200:
                continue   # one ticket's own read hiccup — skip it, never abort the whole average
            kpis = (b2 or {}).get("kpis") or {}
            if kpis.get("first_response_seconds") is not None:
                response_times.append(float(kpis["first_response_seconds"]))
            if kpis.get("resolution_seconds") is not None:
                resolution_times.append(float(kpis["resolution_seconds"]))
            if kpis.get("escalated"):
                escalated += 1

        return {
            "available": True,
            "ticket_count": len(tickets),
            "avg_first_response_seconds": (
                round(sum(response_times) / len(response_times), 1) if response_times else None),
            "avg_resolution_seconds": (
                round(sum(resolution_times) / len(resolution_times), 1) if resolution_times else None),
            "escalation_rate": round(escalated / len(tickets), 4) if tickets else 0.0,
        }

    # ── the marketer's own reads over one shop (not an aggregate) ────────────────────────────
    async def list_tickets(self, *, tenant: str, grantee: str) -> list[dict[str, Any]]:
        """Every ticket this grant covers, structure only — the marketer's own inbox for one
        shop. Raises TicketError rather than degrading silently: a marketer opening his own
        ticket list needs to SEE "no consent yet" or "unreachable", not an empty list that reads
        as "no tickets"."""
        if not self._base:
            raise TicketError("خدمة التذاكر غير مُهيّأة.", reason="ticket_service_not_configured")
        q = urllib.parse.urlencode({"tenant": tenant, "grantee": grantee})
        status, body = await asyncio.to_thread(
            self._http.call, f"{self._base}/internal/tickets?{q}", method="GET", internal=True)
        if status == 409:
            raise TicketError("لا توجد موافقة فعّالة من هذا المحل.", reason="no_active_grant")
        if status != 200:
            raise TicketError("تعذّر الوصول لخدمة التذاكر.", reason=f"unreachable:{status}")
        return list((body or {}).get("tickets") or [])

    async def get_ticket(self, *, tenant: str, grantee: str, ticket_id: str) -> dict[str, Any]:
        if not self._base:
            raise TicketError("خدمة التذاكر غير مُهيّأة.", reason="ticket_service_not_configured")
        q = urllib.parse.urlencode({"tenant": tenant, "grantee": grantee})
        status, body = await asyncio.to_thread(
            self._http.call, f"{self._base}/internal/tickets/{ticket_id}?{q}",
            method="GET", internal=True)
        if status == 409:
            raise TicketError("لا توجد موافقة فعّالة من هذا المحل.", reason="no_active_grant")
        if status == 404:
            raise TicketError("التذكرة غير موجودة.", reason="not_found")
        if status != 200:
            raise TicketError("تعذّر الوصول لخدمة التذاكر.", reason=f"unreachable:{status}")
        return body or {}

    # ── writing on the shop's behalf — ONLY when the grant carries "write" (v0.16.28+) ────────
    async def reply(self, *, tenant: str, grantee: str, ticket_id: str, body: str) -> dict[str, Any]:
        if not self._base:
            raise TicketError("خدمة التذاكر غير مُهيّأة.", reason="ticket_service_not_configured")
        status, resp = await asyncio.to_thread(self._http.call,
            f"{self._base}/internal/tickets/{ticket_id}/replies", method="POST", internal=True,
            body={"tenant": tenant, "grantee": grantee, "body": body})
        if status == 409:
            raise TicketError("لا توجد موافقة فعّالة من هذا المحل.", reason="no_active_grant")
        if status == 403:
            raise TicketError("المحل لم يمنحك صلاحية الرد، فقط المشاهدة.", reason="write_not_granted")
        if status == 404:
            raise TicketError("التذكرة غير موجودة.", reason="not_found")
        if status not in (200, 201):
            raise TicketError("تعذّر إرسال الرد.", reason=f"unreachable:{status}")
        return resp or {}

    async def open_ticket(self, *, tenant: str, grantee: str, type: str, subject: str = "",
                          body: str = "", priority: str = "normal") -> dict[str, Any]:
        if not self._base:
            raise TicketError("خدمة التذاكر غير مُهيّأة.", reason="ticket_service_not_configured")
        status, resp = await asyncio.to_thread(self._http.call,
            f"{self._base}/internal/tickets", method="POST", internal=True,
            body={"tenant": tenant, "grantee": grantee, "type": type, "subject": subject,
                 "body": body, "priority": priority})
        if status == 409:
            raise TicketError("لا توجد موافقة فعّالة من هذا المحل.", reason="no_active_grant")
        if status == 403:
            raise TicketError("المحل لم يمنحك صلاحية فتح تذاكر، فقط المشاهدة.",
                              reason="write_not_granted")
        if status not in (200, 201):
            raise TicketError("تعذّر فتح التذكرة.", reason=f"unreachable:{status}")
        return resp or {}

    async def escalate(self, *, tenant: str, grantee: str, ticket_id: str, assignee: str = "",
                       level: str = "", reason: str = "") -> dict[str, Any]:
        """§13's auto-escalation primitive (v0.16.29+) — records the escalation, and when
        `assignee` is given, moves the ticket to that handle (the shop's marketing manager).
        ticket-service knows nothing about WHY (a timeout, a suspended account) — that policy is
        entirely core/escalation.py's own, driven by the KPIs this module already reads."""
        if not self._base:
            raise TicketError("خدمة التذاكر غير مُهيّأة.", reason="ticket_service_not_configured")
        status, resp = await asyncio.to_thread(self._http.call,
            f"{self._base}/internal/tickets/{ticket_id}/escalate", method="POST", internal=True,
            body={"tenant": tenant, "grantee": grantee, "assignee": assignee, "level": level,
                 "reason": reason})
        if status == 409:
            raise TicketError("لا توجد موافقة فعّالة من هذا المحل.", reason="no_active_grant")
        if status == 403:
            raise TicketError("المحل لم يمنحك صلاحية التصعيد.", reason="write_not_granted")
        if status == 404:
            raise TicketError("التذكرة غير موجودة.", reason="not_found")
        if status not in (200, 201):
            raise TicketError("تعذّر تصعيد التذكرة.", reason=f"unreachable:{status}")
        return resp or {}

    # ── provisioning a grant for a NEW party — used to give a manager his own read/write share
    # over a ticket his own team escalated to him, since ShareGrant is per-grantee, not inherited.
    async def grant_share(self, *, tenant: str, grantee: str, granted_by: str,
                          scope: dict[str, Any] | None = None,
                          write: bool = True) -> dict[str, Any]:
        if not self._base:
            raise TicketError("خدمة التذاكر غير مُهيّأة.", reason="ticket_service_not_configured")
        permissions = ["read", "write"] if write else ["read"]
        status, resp = await asyncio.to_thread(self._http.call,
            f"{self._base}/internal/tickets/shares", method="POST", internal=True,
            body={"tenant": tenant, "grantee": grantee, "granted_by": granted_by,
                 "scope": dict(scope or {}), "permissions": permissions})
        if status not in (200, 201):
            raise TicketError("تعذّر منح الصلاحية.", reason=f"unreachable:{status}")
        return resp or {}
