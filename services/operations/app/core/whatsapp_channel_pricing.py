"""WhatsApp channel pricing — SHAPE for a decision nobody has made yet, not the decision itself.

Same convention, same honesty, as services/whatsapp-assistant/app/core/pricing.py's own module
docstring — this is that module's sibling, for a DIFFERENT cost basis.

WHY THIS IS SEPARATE FROM whatsapp-assistant's OWN pricing.py, DESPITE THE IDENTICAL SHAPE. That
module prices Gemini token usage — a cost this service never sees, incurred entirely inside
whatsapp-assistant's own process. This module prices the WhatsApp CHANNEL itself — the cost of
sending a message at all, which today is usually zero to us: with the direct-Meta provider, the
establishment pays Meta on its own card, and plans.json says so explicitly ("we do not sell
messages... the establishment contracts with Meta directly"). That stops being true the moment a
provider like 360dialog is used under a Partner-Paid commercial model: WE get billed by the
provider, and now WE must decide whether and how to pass that cost to the shop. Two different
questions, two different cost bases, two different modules — conflating them would make one
module answer for money it never actually moved.

THE REAL COST NUMBER COMES FROM WHOEVER ACTUALLY SENT THE MESSAGE — notification-service
(platform/ submodule), which this service does not own and does not reimplement. This module never
invents a cost; it only turns a REAL reported cost (halalas, read from notification-service's own
internal usage-reporting route once that exists) into what we would charge the shop for it.

THREE NAMED, SWITCHABLE STRATEGIES — the same three shapes whatsapp-assistant's pricing.py
offers, because they are the three shapes any metered add-on on this platform tends to take, not
because this module copies that one's code:

  tier_plus_cap          base package + an included message cap + metered overage past it.
  addon_on_existing_plan  a flat add-on price on top of whatever subscription tier the shop
                         already holds — simplest to sell, cheapest to explain, no metering.
  usage_based             a margin over the REAL cost notification-service reports, optionally
                         plus a flat per-message component. Fairest; least predictable for a
                         shop that sends heavily.

NOT A FINAL PRICING DECISION. Every constant below is zero by default in config, which means
every computed price is zero until someone sets real numbers — exactly like its sibling module.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ChannelPricingConfig:
    strategy: str
    tier_base_halalas: int = 0
    tier_included_messages: int = 0
    tier_overage_halalas_per_message: int = 0
    addon_flat_halalas: int = 0
    # WHAT FRACTION OF THE REAL COST TO CHARGE THE SHOP — 0 means absorb it entirely (the safe,
    # zero-by-default state every other strategy here shares), 100 means pass it through at par,
    # above 100 is cost plus a markup. NOT an additive "100 + markup" — that shape would charge
    # the real cost even at its own zero default, breaking the one invariant every strategy in
    # this module promises: unconfigured means free, never "free of markup but still billed at
    # cost". A PERCENTAGE, NOT A HALALAS RATE, unlike whatsapp-assistant's own
    # usage_halalas_per_1k_tokens — because this strategy's cost basis is already a real halalas
    # number (what the provider actually charged us), not a token count needing a rate invented
    # for it, and inventing one here would double-count a cost that already
    # has a real number attached.
    usage_margin_percent: int = 0
    usage_flat_halalas_per_message: int = 0

    @classmethod
    def from_settings(cls, settings: Any) -> "ChannelPricingConfig":
        return cls(
            strategy=settings.WHATSAPP_CHANNEL_PRICING_STRATEGY,
            tier_base_halalas=settings.WHATSAPP_CHANNEL_PRICING_TIER_BASE_HALALAS,
            tier_included_messages=settings.WHATSAPP_CHANNEL_PRICING_TIER_INCLUDED_MESSAGES,
            tier_overage_halalas_per_message=(
                settings.WHATSAPP_CHANNEL_PRICING_TIER_OVERAGE_HALALAS_PER_MESSAGE),
            addon_flat_halalas=settings.WHATSAPP_CHANNEL_PRICING_ADDON_FLAT_HALALAS,
            usage_margin_percent=settings.WHATSAPP_CHANNEL_PRICING_USAGE_MARGIN_PERCENT,
            usage_flat_halalas_per_message=(
                settings.WHATSAPP_CHANNEL_PRICING_USAGE_FLAT_HALALAS_PER_MESSAGE))


@dataclass(frozen=True)
class MessageCost:
    """What the SEND actually cost us for this one message — real halalas, reported by
    notification-service, never estimated here. `provider` is carried through for the caller's own
    bookkeeping/attribution, even though every strategy below prices the same regardless of which
    provider incurred it — the number is real either way, and this module does not need to know
    which provider produced it to price it."""
    provider: str
    real_cost_halalas: int


def tier_plus_cap(cfg: ChannelPricingConfig, *, messages_this_period: int) -> int:
    """Base package + included cap + overage past it. Returns halalas for THIS message's marginal
    charge to the shop — zero while inside the included cap, the overage rate once past it."""
    if messages_this_period <= cfg.tier_included_messages:
        return 0
    return cfg.tier_overage_halalas_per_message


def addon_on_existing_plan(cfg: ChannelPricingConfig, *, is_first_message_this_period: bool) -> int:
    """A flat add-on charged once per billing period, not per message — the marginal charge of
    every message after the first in a period is zero; the period's own charge is the flat
    add-on, billed once by whatever already bills the subscription tier."""
    return cfg.addon_flat_halalas if is_first_message_this_period else 0


def usage_based(cfg: ChannelPricingConfig, cost: MessageCost) -> int:
    """`usage_margin_percent` of the REAL cost, plus an optional flat per-message component. At
    its zero default this charges nothing at all — the same safe default every strategy in this
    module shares — never the real cost "at par with no markup yet", which would silently bill a
    shop for money nobody has decided to charge them."""
    charged = cost.real_cost_halalas * cfg.usage_margin_percent / 100.0
    return cfg.usage_flat_halalas_per_message + round(charged)


_STRATEGIES = frozenset({"tier_plus_cap", "addon_on_existing_plan", "usage_based"})


def price_message(cfg: ChannelPricingConfig, cost: MessageCost, *,
                  messages_this_period: int = 0,
                  is_first_message_this_period: bool = False) -> int:
    """Dispatch to the configured strategy. Unknown strategy is refused, not silently zeroed — a
    typo in WHATSAPP_CHANNEL_PRICING_STRATEGY must not read as "every message is free"."""
    if cfg.strategy not in _STRATEGIES:
        raise ValueError(f"unknown WHATSAPP_CHANNEL_PRICING_STRATEGY: {cfg.strategy!r} — allowed: "
                         f"{', '.join(sorted(_STRATEGIES))}")
    if cfg.strategy == "tier_plus_cap":
        return tier_plus_cap(cfg, messages_this_period=messages_this_period)
    if cfg.strategy == "addon_on_existing_plan":
        return addon_on_existing_plan(
            cfg, is_first_message_this_period=is_first_message_this_period)
    return usage_based(cfg, cost)
