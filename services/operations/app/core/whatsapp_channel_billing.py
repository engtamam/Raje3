"""Turn one tenant/period's RAW WhatsApp usage report into what we actually charge — the join
between `whatsapp_meta_rate_card.py` (what the provider charged US, per message) and
`whatsapp_channel_pricing.py` (what we charge the shop for it), applied to a whole period's
already-aggregated breakdown rather than one message at a time.

WHY THIS IS ITS OWN MODULE, NOT A METHOD ON EITHER SIBLING. Each of those two modules prices ONE
message; this one is the only place that knows the SHAPE of notification-service's own report
(`{tenant, period, breakdown: [{category, country, pricing_model, billable, messages}], ...}`, see
that route's own docstring) — so it is the one place that shape can drift without either pricing
module needing to know a report exists at all.

ONLY `usage_based` PRICES AGAINST AN AGGREGATE REPORT, AND THIS REFUSES ANY OTHER STRATEGY.
`tier_plus_cap` needs the shop's RUNNING total across the period (a message crosses the included
cap partway through), and `addon_on_existing_plan` needs to know which message was the period's
FIRST — both facts this report has already collapsed away by grouping into (category, country,
pricing_model, billable) buckets. Pricing every row as if it were `usage_based` regardless of the
strategy actually configured would silently answer a different question than the one the operator
set up, so this raises instead of guessing.

A NON-BILLABLE ROW (Meta's own `billable: false` — free, in-window "service" replies) IS NEVER
CHARGED A MARGIN EITHER, even though `usage_based`'s flat component would otherwise apply
regardless of the real cost being zero. Meta gave that message away; charging the shop a margin
on top of a real cost of zero is not "our margin on their cost", it is inventing a charge for
something nobody was ever billed for — so this module gates on the report's own `billable` flag
before pricing a row at all, not on the rate card alone.

A ROW WHOSE `pricing_model` THE RATE CARD DOES NOT RECOGNISE DOES NOT SINK THE WHOLE BILL. Meta's
own billing model can change (see whatsapp_meta_rate_card's own docstring), and one stale or
unexpected row must not make an operator unable to see every OTHER row's charge while it gets
fixed — so a per-row failure is recorded on that row (`error`) and contributes zero, not raised
past this function.
"""
from __future__ import annotations

from typing import Any

from app.core.whatsapp_channel_pricing import ChannelPricingConfig, MessageCost, usage_based
from app.core.whatsapp_meta_rate_card import BillableUnits, MetaRateCard, UnknownPricingModel, rate_for

_PRICEABLE_AGAINST_A_PERIOD_REPORT = "usage_based"


def bill_period(card: MetaRateCard, cfg: ChannelPricingConfig, usage: dict[str, Any]) -> dict[str, Any]:
    """`usage` is exactly notification-service's `GET /internal/whatsapp/channel-usage` response.
    Returns the same shape, each breakdown row extended with `real_cost_halalas_per_message` and
    `charged_halalas_total`, plus a `charged_halalas_total` for the whole period."""
    if cfg.strategy != _PRICEABLE_AGAINST_A_PERIOD_REPORT:
        raise ValueError(
            f"whatsapp_channel_billing only prices the {_PRICEABLE_AGAINST_A_PERIOD_REPORT!r} "
            f"strategy against an aggregate usage report — got {cfg.strategy!r}. The other "
            f"strategies need the per-message sequence a period report has already collapsed away.")
    rows: list[dict[str, Any]] = []
    total = 0
    for row in usage.get("breakdown", []):
        count = int(row.get("messages", 0) or 0)
        if not row.get("billable"):
            # Meta gave this one away (free, in-window) — no real cost AND no margin on top of one.
            rows.append({**row, "real_cost_halalas_per_message": 0,
                        "charged_halalas_per_message": 0, "charged_halalas_total": 0})
            continue
        try:
            units = BillableUnits(
                provider="", pricing_model=str(row.get("pricing_model", "")),
                category=str(row.get("category", "")), country=str(row.get("country", "")), count=1)
            per_message = rate_for(card, units)
        except UnknownPricingModel as exc:
            rows.append({**row, "error": str(exc), "charged_halalas_total": 0})
            continue
        charged_per_message = usage_based(cfg, MessageCost(provider="", real_cost_halalas=per_message))
        row_total = charged_per_message * count
        total += row_total
        rows.append({**row, "real_cost_halalas_per_message": per_message,
                    "charged_halalas_per_message": charged_per_message,
                    "charged_halalas_total": row_total})
    return {"tenant": usage.get("tenant", ""), "period": usage.get("period", ""),
            "total_messages": usage.get("total_messages", 0),
            "billable_messages": usage.get("billable_messages", 0),
            "truncated": bool(usage.get("truncated", False)),
            "breakdown": rows, "charged_halalas_total": total}
