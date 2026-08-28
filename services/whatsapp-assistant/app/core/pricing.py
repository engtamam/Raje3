"""Pricing — SHAPE for a decision nobody has made yet, not the decision itself.

Every number here is config, sourced from deploy/services/whatsapp-assistant.values.yaml — the same
convention as reminders' WAFA_TIER_* caps: a business number frozen into code is a rewrite waiting
to happen, and this platform does not know yet which of the three shapes below is the right one for
this product. What it DOES know is the real cost basis to price against: actual Gemini input/output
token counts, persisted per conversation (see core/models.ConversationState.input_tokens/
output_tokens and core/models.COST_LEDGER), never an estimate.

THREE NAMED, SWITCHABLE STRATEGIES — config selects one via PRICING_STRATEGY:

  tier_plus_cap          base package + an included conversation cap + metered overage past it.
                         The shape most SaaS messaging add-ons ship with.
  addon_on_existing_plan  a flat add-on price on top of whatever subscription tier the shop already
                         holds — simplest to sell, cheapest to explain, no metering at all.
  usage_based             per-conversation or per-1k-tokens, metered from the real token counts.
                         Fairest to a shop that barely uses it; least predictable for one that
                         adopts it heavily.

NOT A FINAL PRICING DECISION. This module computes what each strategy WOULD charge given a
conversation's real token counts — it is scaffolding for the pricing conversation the business has
not had yet, not a shipped price list. Every constant below is zero by default in config, which
means every computed price is zero until someone sets real numbers.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PricingConfig:
    strategy: str
    tier_base_halalas: int = 0
    tier_included_conversations: int = 0
    tier_overage_halalas_per_conversation: int = 0
    addon_flat_halalas: int = 0
    usage_halalas_per_1k_tokens: int = 0
    usage_halalas_per_conversation: int = 0

    @classmethod
    def from_settings(cls, settings: Any) -> "PricingConfig":
        return cls(
            strategy=settings.PRICING_STRATEGY,
            tier_base_halalas=settings.PRICING_TIER_BASE_HALALAS,
            tier_included_conversations=settings.PRICING_TIER_INCLUDED_CONVERSATIONS,
            tier_overage_halalas_per_conversation=(
                settings.PRICING_TIER_OVERAGE_HALALAS_PER_CONVERSATION),
            addon_flat_halalas=settings.PRICING_ADDON_FLAT_HALALAS,
            usage_halalas_per_1k_tokens=settings.PRICING_USAGE_HALALAS_PER_1K_TOKENS,
            usage_halalas_per_conversation=settings.PRICING_USAGE_HALALAS_PER_CONVERSATION)


@dataclass(frozen=True)
class ConversationCost:
    input_tokens: int
    output_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


def tier_plus_cap(cfg: PricingConfig, *, conversations_this_period: int) -> int:
    """Base package + included cap + overage past it. Returns halalas for THIS conversation's
    marginal cost — zero while inside the included cap, the overage rate once past it."""
    if conversations_this_period <= cfg.tier_included_conversations:
        return 0
    return cfg.tier_overage_halalas_per_conversation


def addon_on_existing_plan(cfg: PricingConfig, *, is_first_conversation_this_period: bool) -> int:
    """A flat add-on charged once per billing period, not per conversation — so the marginal cost
    of every conversation after the first in a period is zero; the period's own charge is the flat
    add-on, billed once by whatever already bills the subscription tier."""
    return cfg.addon_flat_halalas if is_first_conversation_this_period else 0


def usage_based(cfg: PricingConfig, cost: ConversationCost) -> int:
    """Metered on the REAL token counts. Two components, both additive, both zero unless
    configured: a flat per-conversation charge and a per-1k-token rate."""
    per_conv = cfg.usage_halalas_per_conversation
    per_tokens = (cost.total_tokens / 1000.0) * cfg.usage_halalas_per_1k_tokens
    return per_conv + round(per_tokens)


_STRATEGIES = frozenset({"tier_plus_cap", "addon_on_existing_plan", "usage_based"})


def price_conversation(cfg: PricingConfig, cost: ConversationCost, *,
                       conversations_this_period: int = 0,
                       is_first_conversation_this_period: bool = False) -> int:
    """Dispatch to the configured strategy. Unknown strategy is refused, not silently zeroed —
    a typo in PRICING_STRATEGY must not read as "everything is free"."""
    if cfg.strategy not in _STRATEGIES:
        raise ValueError(f"unknown PRICING_STRATEGY: {cfg.strategy!r} — allowed: "
                         f"{', '.join(sorted(_STRATEGIES))}")
    if cfg.strategy == "tier_plus_cap":
        return tier_plus_cap(cfg, conversations_this_period=conversations_this_period)
    if cfg.strategy == "addon_on_existing_plan":
        return addon_on_existing_plan(
            cfg, is_first_conversation_this_period=is_first_conversation_this_period)
    return usage_based(cfg, cost)
