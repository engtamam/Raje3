"""محلّي's own "أثر الذكاء الاصطناعي" card — ONE SHOP'S OWN NUMBERS, composed from the three
report modules that already exist for the platform-admin panel (pricing_report.py, upsell_report.py,
invoice_report.py), each called in its TENANT-SCOPED mode specifically.

WHY A SEPARATE MODULE RATHER THAN REUSING THE ADMIN REPORTS DIRECTLY. Those three functions default
to a platform-wide aggregate (`tenant=None`) — correct for our own internal panel, and a real
cross-shop data leak if a shop-facing route ever called them that way by accident (exactly the class
of bug a QA audit found and fixed elsewhere this same day: services/notification-service's delivery
log). This module is the one place that ALWAYS passes a real `tenant`, never `None`, so a shop-facing
route built on top of it structurally cannot leak another shop's numbers — the isolation is the
module's own job, not something every future caller has to remember.

WHAT "معدل التحويل" MEANS HERE, STATED PLAINLY: of every distinct conversation the assistant had
with a customer in the window (`pricing_report`'s own `conversations`), how many turned into a real,
non-cancelled booking (`invoice_report`'s own `status_breakdown`, summed — booked, attended, or
no_show all count as "a booking happened"; only cancelled is excluded, same as invoice_report's own
rule). A conversation that never became a booking is not counted against the shop as a "loss" here —
plenty of WhatsApp conversations are legitimately about something else (a question, a reschedule) —
this is a REACH number ("how often does talking to the AI end in a booking"), not a sales-funnel
efficiency score.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core import invoice_report as _invoice
from app.core import pricing_report as _pricing
from app.core import upsell_report as _upsell

_ALL_BRANCHES = "_all"   # same sentinel every sibling report module uses


@dataclass(frozen=True)
class ShopImpactReport:
    days: int
    conversations: int                      # distinct customers the AI talked to in the window
    ai_bookings: int                        # non-cancelled bookings the AI made in the window
    conversion_rate: float | None           # ai_bookings / conversations — None, never 0, if no
                                             # conversations happened yet (nothing to divide by)
    avg_invoice_value_minor: int | None     # invoice_report's own honest average — None if no
                                             # priced, attended AI booking exists yet
    upsell_offered: int
    upsell_accepted: int
    upsell_acceptance_rate: float | None
    truncated: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "days": self.days, "conversations": self.conversations,
            "ai_bookings": self.ai_bookings, "conversion_rate": self.conversion_rate,
            "avg_invoice_value_minor": self.avg_invoice_value_minor,
            "upsell_offered": self.upsell_offered, "upsell_accepted": self.upsell_accepted,
            "upsell_acceptance_rate": self.upsell_acceptance_rate, "truncated": self.truncated,
        }


async def report(*, datastore: Any, actor_report: Any, service_catalog: Any, package_catalog: Any,
                 tenant: str, created_by: str, days: int, now: int) -> ShopImpactReport:
    """`tenant` is REQUIRED (no default) — deliberately, unlike the three modules this composes,
    each of which defaults to the platform-wide aggregate. There is no legitimate caller of this
    specific function that wants every shop combined; that caller belongs on the admin panel's own
    routes instead, calling the underlying modules directly with `tenant=None`."""
    if not tenant:
        raise ValueError("shop_impact_report.report() requires a real tenant — never platform-wide")

    usage = await _pricing.report(datastore, days=days, now=now, tenant=tenant)
    upsell = await _upsell.report(datastore, days=days, now=now, tenant=tenant)
    invoices = await _invoice.report(actor_report, service_catalog, package_catalog,
                                     tenant=tenant, created_by=created_by, days=days, now=now)

    inv_all = invoices.current.get(_ALL_BRANCHES)
    ai_bookings = sum(inv_all.status_breakdown.values()) if inv_all else 0
    conversion_rate = round(ai_bookings / usage.conversations, 4) if usage.conversations else None

    up_all = upsell.current.get(_ALL_BRANCHES)

    return ShopImpactReport(
        days=days, conversations=usage.conversations, ai_bookings=ai_bookings,
        conversion_rate=conversion_rate,
        avg_invoice_value_minor=inv_all.avg_invoice_value_minor if inv_all else None,
        upsell_offered=up_all.offered if up_all else 0,
        upsell_accepted=up_all.accepted if up_all else 0,
        upsell_acceptance_rate=up_all.acceptance_rate if up_all else None,
        truncated=usage.truncated or invoices.truncated)
