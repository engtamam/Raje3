# =============================================================================
# affiliate-service — reading a shop's ticket support performance (spec §13), consent-scoped
# -----------------------------------------------------------------------------
# Reads ticket-service's own v0.16.27 scoped-visibility primitive (ShareGrant) — never a shop's
# tickets directly, only what that shop's OWN consent grant to THIS marketer (grantee=
# affiliate_id) actually covers. A durable read, same "peer reads a durable fact, never an event
# alone" contract as CommissionEngine's own billing read.
#
# STRUCTURE + PERFORMANCE ONLY. ticket-service's own projection already strips subject/body/meta
# (the shop's customer PII, not this service's — or a marketer's — to read); this module never
# asks for more than that.
#
# BEST-EFFORT, PER TENANT. One shop's ticket-service hiccup — or simply NO_ACTIVE_GRANT, the
# honest common case before operations-service wires the share at signup — must not hide a
# marketer's whole team's KPIs. Same reasoning as CommissionEngine.revenue_for's own per-shop
# best-effort loop.
# =============================================================================
from __future__ import annotations

import urllib.parse
from typing import Any

from app.core.onboarding import Http


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
        status, body = self._http.call(f"{self._base}/internal/tickets?{q}",
                                       method="GET", internal=True)
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
            s2, b2 = self._http.call(f"{self._base}/internal/tickets/{tid}?{qi}",
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
