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
from dataclasses import dataclass
from typing import Any


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
    back to the flat legacy rate, it never blocks a reply)."""
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
    return halalas_per_million / 1000


def units_per_1k_tokens(usd_per_million: float, *, usd_to_sar: float, margin_multiplier: float,
                        units_per_halala: int) -> float:
    """The customer-facing "وحدات الذكاء" number for 1000 tokens at this model's real cost — the
    FIXED display scale (units_per_halala) wrapped around the actual per-model burn rate above."""
    return halalas_per_1k_tokens(
        usd_per_million, usd_to_sar=usd_to_sar,
        margin_multiplier=margin_multiplier) * max(0, units_per_halala)


def model_rate_halalas_per_1k(cfg: AiUnitPricingConfig, model_name: str, *,
                              fallback_halalas_per_1k: float) -> tuple[float, float]:
    """(input_halalas_per_1k, output_halalas_per_1k) for the model ACTUALLY in use this turn
    (ASSISTANT_MODEL_NAME's live value). A model missing from `cfg.model_costs` — not yet priced
    by an operator — gets the flat legacy rate in BOTH directions rather than blocking the AI: a
    missing price entry is an operator gap, never a reason to refuse every reply, the same
    fail-safe posture every other optional-config default on this service already takes."""
    cost = cfg.model_costs.get(model_name)
    if cost is None:
        return fallback_halalas_per_1k, fallback_halalas_per_1k
    return (
        halalas_per_1k_tokens(cost.input_usd_per_million, usd_to_sar=cfg.usd_to_sar,
                              margin_multiplier=cfg.input_margin_multiplier),
        halalas_per_1k_tokens(cost.output_usd_per_million, usd_to_sar=cfg.usd_to_sar,
                              margin_multiplier=cfg.output_margin_multiplier))
