"""Meta's own WhatsApp per-message rate card — a FACT we source and date, not a decision we make.

WHY THIS MODULE EXISTS, AND WHY IT IS NOT PART OF whatsapp_channel_pricing.py. notification-service
(platform/ submodule) does not — and by design should not — know Meta's rates: those rates vary by
recipient market and template CATEGORY (auth/utility/marketing), Meta revises them, and baking a
rate table into the sender would mean the sender silently drifts out of date every time Meta changes
a price, with nothing here to notice. So notification-service reports what actually happened — real
billable message COUNTS per (category, calling code), read from Meta's own delivery-status webhook
`pricing` object (which carries no country of its own — notification-service derives the E.164
calling code from the recipient's own phone number, confirmed against their real implementation)
— and this module is the one place those counts become halalas.

REAL SHAPE, CONFIRMED AGAINST notification-service's OWN CODE (not assumed): `GET /internal/
whatsapp/channel-usage?tenant=&period=YYYY-MM` returns `{tenant, period, total_messages,
billable_messages, breakdown: [{category, country, pricing_model, billable, messages}], truncated}`
— `country` there is the calling code described above, and `messages` is the count this module
calls `count`. `pricing_model` is passed through byte-for-byte from Meta's own field, exactly so a
future change away from CBP is a live fact both sides can react to, not a silently stale read.

THIS IS META'S PUBLISHED COST TO US, NOT WHAT WE CHARGE THE SHOP. Converting units to halalas here
answers "what did this tenant's messages cost us" — the `real_cost_halalas` input
whatsapp_channel_pricing.py's strategies already expect. What we then charge the shop (margin, flat
add-on, tier) is that OTHER module's job, unchanged by this one.

A CONVERSATION-BASED PRICING MODEL (CBP) IS ASSUMED TODAY, honestly, because it is what Meta
actually bills under as of when this was written — see the `pricing_model` field the peer already
agreed to pass through from the status webhook precisely so a future change is a live fact this
module can react to, not a silent misread. If `pricing_model` is ever anything other than "CBP",
`rate_for` refuses rather than guessing a stale-shaped answer.

RATES ARE ZERO BY DEFAULT, same convention as every other pricing module on this platform — a
tenant's real cost is reported as 0 halalas until someone seeds real numbers here, never invented.
No CI gate on prices in code applies the same way here as it does to what WE charge (ci/check_
no_prices.py polices what we bill a customer) — this table is what a THIRD PARTY (Meta) charges US,
sourced from their own published rate card, not our own price list. It is still config-driven
rather than hand-typed into request-handling code, for the same reason every other number on this
platform is: a rate that changes needs a data update, never a deploy.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class UnknownPricingModel(Exception):
    """Meta reported a `pricing_model` other than the one this rate card was built against — a
    real signal that the cost basis itself changed, not something to guess a stale rate for."""


@dataclass(frozen=True)
class BillableUnits:
    """One tenant/period's real, billable WhatsApp message counts — exactly the shape
    notification-service's internal usage-reporting route reports, read from Meta's own delivery-
    status webhook `pricing` object. Meta-direct (the establishment pays Meta itself) reports
    nothing at all; this dataclass only ever describes a provider-billed driver's real usage."""
    provider: str
    pricing_model: str          # "CBP" today — see module docstring
    category: str                # "authentication" | "utility" | "marketing" | "service" (free)
    # AN E.164 CALLING CODE ("966"), NOT AN ISO 3166-1 COUNTRY — confirmed against
    # notification-service's real implementation: Meta's own pricing object carries no country at
    # all, so the calling code is derived from the recipient's phone number prefix on their side.
    # "" means an unrecognised prefix — never a wrong guess. A calling code is not always a single
    # resolved market (+1, +7 and a few others are shared by more than one country) — RESOLVING
    # that ambiguity, if it ever matters for a real rate difference, is this module's job, not
    # notification-service's; the rate card below is keyed on the calling code directly rather
    # than pretending to already know the market.
    country: str
    count: int


@dataclass(frozen=True)
class MetaRateCard:
    """`{(category, country): halalas per message}`. `default_halalas` answers a (category,
    country) pair with no explicit entry — deliberately 0, not an average or a guess: an unpriced
    corridor must read as "we have not sourced this rate yet", never as a plausible-looking
    number nobody actually confirmed against Meta's own published list."""
    rates: dict[tuple[str, str], int]
    default_halalas: int = 0

    @classmethod
    def from_settings(cls, settings: Any) -> "MetaRateCard":
        """Reads WHATSAPP_META_RATE_CARD_JSON — a JSON object of "category:country": halalas,
        e.g. {"marketing:966": 25, "utility:966": 12} — the second half is the E.164 calling
        code notification-service reports (see module docstring), not an ISO country code.
        Empty/unset means every rate is the default
        (0) — the safe, honest state until someone actually sources Meta's current published
        rates and seeds them here, dated, the same way every other pricing constant on this
        platform starts at zero."""
        import json
        raw = settings.WHATSAPP_META_RATE_CARD_JSON
        if not raw:
            return cls(rates={})
        parsed = json.loads(raw)
        rates: dict[tuple[str, str], int] = {}
        for key, halalas in parsed.items():
            category, _, country = key.partition(":")
            rates[(category, country)] = int(halalas)
        return cls(rates=rates, default_halalas=int(settings.WHATSAPP_META_RATE_CARD_DEFAULT_HALALAS))


def rate_for(card: MetaRateCard, units: BillableUnits) -> int:
    """Halalas per message for this (category, country) pair, under the ASSUMED pricing model.
    "service" (free, in-window replies) is not a real charge — 0 unconditionally, never looked up
    — Meta does not bill these, and a rate-card entry accidentally covering that key must not be
    allowed to charge for something Meta itself gave away."""
    if units.category == "service":
        return 0
    if units.pricing_model != "CBP":
        raise UnknownPricingModel(
            f"rate card built for CBP, got pricing_model={units.pricing_model!r} — Meta's "
            f"billing model changed; this needs a real update, not a guessed rate")
    return card.rates.get((units.category, units.country), card.default_halalas)


def cost_halalas(card: MetaRateCard, units: BillableUnits) -> int:
    """The real cost this tenant's period of `units.count` messages incurred — the number that
    feeds directly into whatsapp_channel_pricing.MessageCost.real_cost_halalas."""
    return rate_for(card, units) * units.count
