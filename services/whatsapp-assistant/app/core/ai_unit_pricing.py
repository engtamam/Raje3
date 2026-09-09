"""AI-unit burn rate — a FIXED, model-independent display exchange rate wrapped around a genuinely
per-model cost.

TWO SEPARATE NUMBERS, NEVER CONFLATED. "وحدات الذكاء" (AI units) is what a shop sees on its wallet
balance — a display scale, `units_per_halala`, that NEVER changes regardless of which model is
running (1 halala is always the same number of units). What DOES vary per model is how many
HALALAS a turn actually costs, because Google prices every model differently and charges roughly
8x more per output token than per input token — see `ModelCost` below. This module is the bridge:
`model_rate_halalas_per_1k` turns a model's real cost into the halala rate wallet_balance.py's
reserve/confirm math actually spends, and `units_per_1k_tokens` turns that same real cost into the
unit number the console/customer-facing balance displays it as.

NO REGIONAL MARKUP, NO SYNTHETIC ADJUSTMENT, ANYWHERE IN THIS PIPELINE. `ModelCost.input_usd_per_
million`/`output_usd_per_million` are entered by an operator as the REAL, CONFIRMED price for
whatever region/project this platform actually connects to — read off the real GCP invoice or the
official regional pricing page once a real project exists, typed in as-is. There is no premium
multiplier step: the admin-entered number IS already the region-correct number by definition,
whatever it turns out to be. The only conversion applied is USD -> SAR (Google bills in USD; this
platform prices in SAR) and the margin (see below) — nothing else.

INPUT AND OUTPUT MARGINS ARE SEPARATE, DELIBERATELY. Output tokens cost Google far more per token
than input tokens for every model checked — collapsing the two into one blended multiplier would
either under-price output (losing money on every reply) or over-price input (losing the sale on
every context-heavy turn). `input_margin_multiplier`/`output_margin_multiplier` default to 5/2.

A PRICING KEY LIKE EVERY OTHER ONE — see core/pricing_schedule.py's own docstring for why. Every
field on `AiUnitPricingConfig` is admin-editable only through the SAME scheduled-change gate the
seven original PRICING_* keys already go through (app/runtime_policy.py's own "SECOND SLICE" note),
never applied instantly: a shop that woke up to a costlier model with no notice has a real grievance.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any

# THE ONE BASIS EVERY RATE IN THIS MODULE, AND wallet_balance.py's OWN RESERVE MATH, IS
# DENOMINATED IN — "halalas per 1000 tokens". Named rather than a bare `1000` repeated at each of
# the three sites that convert a raw token count into "how many pricing units is that" (this
# module's own `halalas_per_1k_tokens`/`real_cost_halalas`, and wallet_balance.py's
# `estimated_hold_halalas`): a literal at each site is how one of them could silently drift to a
# different scale (1024? per-single-token?) while the others stayed at 1000, splitting the
# reserve's estimate from the confirm's real charge for no product reason at all — one constant,
# imported everywhere it is used, makes that impossible by construction.
TOKENS_PER_PRICING_UNIT = 1000


@dataclass(frozen=True)
class ModelCost:
    """Real Google price for ONE model, USD per million tokens — never a blended/estimated number,
    the actual figure off the real invoice/pricing page for whatever region this platform's own
    GCP project actually bills in."""
    input_usd_per_million: float
    output_usd_per_million: float


def parse_model_costs(raw: str) -> dict[str, ModelCost]:
    """`PRICING_AI_UNIT_MODEL_COSTS_JSON` -> {model_name: ModelCost}. Malformed JSON, a non-dict
    top level, or a row missing either field is DROPPED rather than raising — the same fail-safe
    posture `model_rate_halalas_per_1k` below relies on (a model missing from this registry falls
    back to the most expensive OTHER registered model's rate, never to zero; it never blocks a
    reply either way)."""
    try:
        data = json.loads(raw or "{}")
    except ValueError:
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, ModelCost] = {}
    for name, row in data.items():
        if not isinstance(row, dict):
            continue
        try:
            out[str(name)] = ModelCost(
                input_usd_per_million=float(row["input_usd_per_million"]),
                output_usd_per_million=float(row["output_usd_per_million"]))
        except (KeyError, TypeError, ValueError):
            continue
    return out


@dataclass(frozen=True)
class AiUnitPricingConfig:
    units_per_halala: int
    input_margin_multiplier: float
    output_margin_multiplier: float
    usd_to_sar: float
    model_costs: dict[str, ModelCost]

    @classmethod
    def from_settings(cls, settings: Any) -> "AiUnitPricingConfig":
        """Deploy-time answer only — see PricingConfig.from_settings' own note, same reasoning."""
        return cls(
            units_per_halala=settings.PRICING_AI_UNIT_UNITS_PER_HALALA,
            input_margin_multiplier=settings.PRICING_AI_UNIT_INPUT_MARGIN_MULTIPLIER,
            output_margin_multiplier=settings.PRICING_AI_UNIT_OUTPUT_MARGIN_MULTIPLIER,
            usd_to_sar=settings.PRICING_AI_UNIT_USD_TO_SAR,
            model_costs=parse_model_costs(settings.PRICING_AI_UNIT_MODEL_COSTS_JSON))

    @classmethod
    async def from_runtime(cls, runtime_config: Any, settings: Any, *,
                           tenant: str = "") -> "AiUnitPricingConfig":
        """THE LIVE ANSWER — every field resolved through RuntimeConfig.get(), same shape as
        PricingConfig.from_runtime right above it in the sibling module. `runtime_config=None`
        falls back to the deploy-time settings."""
        if runtime_config is None:
            return cls.from_settings(settings)

        async def _get(key: str) -> Any:
            return await runtime_config.get(tenant=tenant, key=key, default=getattr(settings, key))

        return cls(
            units_per_halala=int(await _get("PRICING_AI_UNIT_UNITS_PER_HALALA")),
            input_margin_multiplier=float(await _get("PRICING_AI_UNIT_INPUT_MARGIN_MULTIPLIER")),
            output_margin_multiplier=float(await _get("PRICING_AI_UNIT_OUTPUT_MARGIN_MULTIPLIER")),
            usd_to_sar=float(await _get("PRICING_AI_UNIT_USD_TO_SAR")),
            model_costs=parse_model_costs(str(await _get("PRICING_AI_UNIT_MODEL_COSTS_JSON"))))


def halalas_per_1k_tokens(usd_per_million: float, *, usd_to_sar: float,
                          margin_multiplier: float) -> float:
    """Real Google cost (USD/million tokens, the region-correct number as-is, no markup) -> SAR ->
    priced up by the margin -> halalas per 1000 tokens, the unit wallet_balance.py's reserve/
    confirm math is actually denominated in."""
    sar_per_million = max(0.0, usd_per_million) * max(0.0, usd_to_sar)
    priced_sar_per_million = sar_per_million * max(0.0, margin_multiplier)
    halalas_per_million = priced_sar_per_million * 100          # 1 SAR = 100 halalas
    return halalas_per_million / (1_000_000 / TOKENS_PER_PRICING_UNIT)


def units_per_1k_tokens(usd_per_million: float, *, usd_to_sar: float, margin_multiplier: float,
                        units_per_halala: int) -> float:
    """The customer-facing "وحدات الذكاء" number for 1000 tokens at this model's real cost — the
    FIXED display scale (units_per_halala) wrapped around the actual per-model burn rate above."""
    return halalas_per_1k_tokens(
        usd_per_million, usd_to_sar=usd_to_sar,
        margin_multiplier=margin_multiplier) * max(0, units_per_halala)


def model_rate_halalas_per_1k(cfg: AiUnitPricingConfig, model_name: str, *,
                              fallback_halalas_per_1k: float,
                              ) -> tuple[float, float, bool]:
    """(input_halalas_per_1k, output_halalas_per_1k, used_fallback) for the model ACTUALLY in use
    this turn (ASSISTANT_MODEL_NAME's live value).

    A model missing from `cfg.model_costs` — not yet priced by an operator — must never be
    treated as FREE: this is never a reason to refuse the reply (a missing price entry is an
    operator gap, not a reason to stop the AI — same fail-safe posture every other optional-
    config default on this service already takes), but the direction of the fail-safe matters.
    So the substitute is the MOST EXPENSIVE model already registered in `cfg.model_costs` — this
    can only ever OVER-charge relative to the unpriced model's true (unknown) cost, never give it
    away. `fallback_halalas_per_1k` (the old flat legacy rate) is the last resort, used only when
    `cfg.model_costs` is empty entirely — an operator who has priced NOTHING has no "most
    expensive known model" to fall back to. Was previously this legacy rate directly for every
    unpriced model, including a deploy where it is wired at 0 — silently making every reply on an
    unpriced model free, with no signal anywhere that it was happening. `used_fallback` tells the
    caller a substitute rate was used at all, so it can be logged/audited rather than pass
    invisibly (see core/conversation.py's own call site)."""
    cost = cfg.model_costs.get(model_name)
    if cost is not None:
        return (
            halalas_per_1k_tokens(cost.input_usd_per_million, usd_to_sar=cfg.usd_to_sar,
                                  margin_multiplier=cfg.input_margin_multiplier),
            halalas_per_1k_tokens(cost.output_usd_per_million, usd_to_sar=cfg.usd_to_sar,
                                  margin_multiplier=cfg.output_margin_multiplier),
            False)
    if not cfg.model_costs:
        return fallback_halalas_per_1k, fallback_halalas_per_1k, True
    priciest = max(
        cfg.model_costs.values(),
        key=lambda c: max(c.input_usd_per_million, c.output_usd_per_million))
    return (
        halalas_per_1k_tokens(priciest.input_usd_per_million, usd_to_sar=cfg.usd_to_sar,
                              margin_multiplier=cfg.input_margin_multiplier),
        halalas_per_1k_tokens(priciest.output_usd_per_million, usd_to_sar=cfg.usd_to_sar,
                              margin_multiplier=cfg.output_margin_multiplier),
        True)


def real_cost_halalas(cfg: AiUnitPricingConfig, model_name: str, *, input_tokens: int,
                      output_tokens: int, fallback_halalas_per_1k: float) -> tuple[int, bool]:
    """(cost_halalas, used_fallback) — the ACTUAL charge for one turn, now that the real
    input/output token counts are known (after the LLM call, unlike `_reserve_llm_hold`'s own
    conservative blended ceiling priced BEFORE it). Enabled by wallet-service v0.19.2's own
    confirm(hold_id, final_net=...) — see core/conversation.py's own call site and
    core/wallet_balance.py's module docstring for why this could not be built before that shipped.

    UNLIKE THE RESERVE'S SINGLE BLENDED RATE, this prices input and output SEPARATELY at their
    own real rates — the actual per-component cost, not a worst-case stand-in for a split that was
    unknown at reserve time. `math.ceil` per component, matching `estimated_hold_halalas`'s own
    rounding direction (never round a real charge down)."""
    input_rate, output_rate, used_fallback = model_rate_halalas_per_1k(
        cfg, model_name, fallback_halalas_per_1k=fallback_halalas_per_1k)
    cost = (math.ceil(max(0, input_tokens) / TOKENS_PER_PRICING_UNIT * input_rate)
           + math.ceil(max(0, output_tokens) / TOKENS_PER_PRICING_UNIT * output_rate))
    return cost, used_fallback
