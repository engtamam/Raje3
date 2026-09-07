"""Average invoice value across every AI-made booking — package or plain service alike, replacing
`upsell_report.py`'s old `avg_ticket_increase_minor`, which only ever priced an ACCEPTED PACKAGE
upsell (never a plain single-service booking) and was never actually an "increase" — no baseline
was ever tracked, just the package's own raw price. This module answers a different, more honest
question: "what does the average booking whatsapp-assistant actually makes turn into, on a real
invoice" — needing bookings-service's own rows filtered by `created_by`, which upsell_report.py's
own module docstring named as a documented follow-up (bookings-service had no such route until this
pass — see that service's api/internal.py `/internal/bookings/by-actor`).

A SEPARATE MODULE FROM upsell_report.py, DELIBERATELY: upsell_report answers "did the AI's upsell
OFFER get accepted" purely off its own local ledger (`wa_upsell_ledger`); this module answers "what
did the AI's bookings actually turn into money-wise" and needs a real peer call to bookings-service
plus live catalogue price resolution on every row — a different data source and a genuinely
different concern, not the same stat with an extra column bolted on.

PRICE RESOLUTION, PER BOOKING — mirrors this service's own existing resolution pattern
(context_builder.py/tools.py), nothing new invented:
  1. `price_override_minor`, when set (not None) — the owner's own explicit number for that booking.
  2. else, if `service_ids` is set — the SUM of each service's own `price_minor` from the live
     catalogue (service_catalog.py).
  3. else, if `package_id` is set — that package's own `price_minor` (package_catalog.py).
A booking whose services/package can no longer be resolved (deleted since it was booked) is
EXCLUDED from the average, never counted as 0 — the SAME honesty rule pricing_report.py/
upsell_report.py already established for an unpriced row.

WHICH BOOKINGS COUNT — THE CALL MADE HERE, STATED PLAINLY: only `status == "attended"` bookings
feed the average. This session's own earlier ROI discussion concluded "attended" is the honest
measure of REAL, REALIZED revenue — a booked-but-not-yet-attended appointment is still just an
intention, and a cancelled/no-show one earned nothing. `status_breakdown` (counts of every
non-cancelled status actually seen: booked/attended/no_show) rides alongside the average for free,
so a future console screen can show the "committed value across every open booking" framing too,
without this module having to guess which framing the console will eventually want.

PER BRANCH, CURRENT-VS-PREVIOUS-EQUAL-WINDOW — the SAME shape upsell_report.py/pricing_report.py
already use, mirrored exactly rather than inventing a fourth shape.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_ALL_BRANCHES = "_all"   # same sentinel upsell_report.py/insights' Snapshot use


def _price_maps(services: list[dict[str, Any]], packages: list[dict[str, Any]]
                ) -> tuple[dict[str, int], dict[str, int]]:
    service_prices = {str(s["id"]): int(s.get("price_minor") or 0)
                      for s in services if s.get("id") and s.get("price_minor") is not None}
    package_prices = {str(p["id"]): int(p["price_minor"]) for p in packages
                      if p.get("id") and p.get("price_minor") is not None}
    return service_prices, package_prices


def _resolve_price(booking: dict[str, Any], service_prices: dict[str, int],
                   package_prices: dict[str, int]) -> int | None:
    """None means genuinely unresolvable — NEVER coerced to 0 (see module docstring)."""
    override = booking.get("price_override_minor")
    if override is not None:
        return int(override)
    service_ids = booking.get("service_ids") or []
    if service_ids:
        total = 0
        for sid in service_ids:
            price = service_prices.get(str(sid))
            if price is None:
                return None   # ONE unresolvable service makes the whole booking unpriced —
                              # a partial sum would understate it silently.
            total += price
        return total
    package_id = booking.get("package_id") or ""
    if package_id:
        return package_prices.get(str(package_id))
    return None


@dataclass(frozen=True)
class BranchInvoiceStats:
    branch_id: str                     # "_all" = every branch combined
    status_breakdown: dict[str, int]   # counts of every non-cancelled status seen: booked/attended/no_show
    attended_priced: int               # attended bookings that fed the average
    attended_unpriced: int             # attended bookings excluded — service/package no longer resolvable
    avg_invoice_value_minor: int | None   # None = no priced attended booking exists yet in-window

    def as_dict(self) -> dict[str, Any]:
        return {
            "branch_id": self.branch_id, "status_breakdown": dict(self.status_breakdown),
            "attended_priced": self.attended_priced, "attended_unpriced": self.attended_unpriced,
            "avg_invoice_value_minor": self.avg_invoice_value_minor,
        }


@dataclass(frozen=True)
class InvoiceReport:
    days: int
    current: dict[str, BranchInvoiceStats]
    previous: dict[str, BranchInvoiceStats]
    truncated: bool   # the underlying bookings-service scan hit its own cap — see by-actor's note

    def as_dict(self) -> dict[str, Any]:
        return {
            "days": self.days, "truncated": self.truncated,
            "current": {b: s.as_dict() for b, s in self.current.items()},
            "previous": {b: s.as_dict() for b, s in self.previous.items()},
        }


def _stats_for(branch_id: str, rows: list[dict[str, Any]], service_prices: dict[str, int],
              package_prices: dict[str, int]) -> BranchInvoiceStats:
    breakdown: dict[str, int] = {}
    for r in rows:
        status = str(r.get("status") or "")
        breakdown[status] = breakdown.get(status, 0) + 1
    attended = [r for r in rows if r.get("status") == "attended"]
    priced = [_resolve_price(r, service_prices, package_prices) for r in attended]
    known = [p for p in priced if p is not None]
    unknown = len(priced) - len(known)
    avg = round(sum(known) / len(known)) if known else None
    return BranchInvoiceStats(branch_id=branch_id, status_breakdown=breakdown,
                              attended_priced=len(known), attended_unpriced=unknown,
                              avg_invoice_value_minor=avg)


def _by_branch(rows: list[dict[str, Any]], service_prices: dict[str, int],
              package_prices: dict[str, int]) -> dict[str, BranchInvoiceStats]:
    out = {_ALL_BRANCHES: _stats_for(_ALL_BRANCHES, rows, service_prices, package_prices)}
    branch_ids = {str(r.get("branch_id") or "") for r in rows if r.get("branch_id")}
    for b in sorted(branch_ids):
        out[b] = _stats_for(b, [r for r in rows if r.get("branch_id") == b],
                            service_prices, package_prices)
    return out


async def report(actor_report: Any, service_catalog: Any, package_catalog: Any, *, tenant: str,
                 created_by: str, days: int, now: int) -> InvoiceReport:
    """Trailing `days` vs the equal-length window immediately before it, over `created_by`'s own
    bookings — CANCELLED bookings are dropped entirely up front (they represent no committed value
    and would only clutter `status_breakdown`); everything else feeds it, only `attended` feeds the
    average. Two peer calls (one per window) rather than one wide scan split in Python — the peer
    itself already takes `since`/`until`, so there is no reason to over-fetch."""
    window = days * 86_400
    cur_since = now - window
    prev_since = now - 2 * window

    services, packages = await service_catalog.list_active(tenant), await package_catalog.list_active(tenant)
    service_prices, package_prices = _price_maps(services, packages)

    cur = await actor_report.by_actor(tenant, created_by, since=cur_since, until=now)
    prev = await actor_report.by_actor(tenant, created_by, since=prev_since, until=cur_since)

    cur_rows = [r for r in cur.get("bookings") or [] if r.get("status") != "cancelled"]
    prev_rows = [r for r in prev.get("bookings") or [] if r.get("status") != "cancelled"]

    return InvoiceReport(
        days=days, current=_by_branch(cur_rows, service_prices, package_prices),
        previous=_by_branch(prev_rows, service_prices, package_prices),
        truncated=bool(cur.get("truncated")) or bool(prev.get("truncated")))
