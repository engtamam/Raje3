"""app/core/ai_unit_pricing.py — the per-model burn-rate formula, and the model-cost registry
parser. The formula's own worked example (Gemini 3.1 Flash Lite, this service's current deployed
default) is the fixture every test below is anchored to.
"""
from __future__ import annotations

import asyncio

from app.core.ai_unit_pricing import (
    AiUnitPricingConfig, ModelCost, halalas_per_1k_tokens, model_rate_halalas_per_1k,
    parse_model_costs, units_per_1k_tokens,
)


def run(c):
    return asyncio.run(c)


# ── the formula itself ──────────────────────────────────────────────────────────────────────────
def test_worked_example_input_side_gemini_3_1_flash_lite():
    # $0.25/M -> x3.75 SAR/USD = 0.9375 SAR/M -> x5 input margin = 4.6875 SAR/M priced
    # -> x100 halalas/SAR = 468.75 halalas/M -> /1000 = 0.46875 halalas per 1k tokens.
    rate = halalas_per_1k_tokens(0.25, usd_to_sar=3.75, margin_multiplier=5.0)
    assert rate == 0.46875


def test_worked_example_output_side_gemini_3_1_flash_lite():
    # $1.50/M -> x3.75 = 5.625 SAR/M -> x2 output margin = 11.25 SAR/M priced -> x100 = 1125
    # halalas/M -> /1000 = 1.125 halalas per 1k tokens.
    rate = halalas_per_1k_tokens(1.50, usd_to_sar=3.75, margin_multiplier=2.0)
    assert rate == 1.125


def test_worked_example_units_per_1k_input():
    # 0.46875 halalas/1k x 1000 units/halala = 468.75 units per 1000 input tokens (~469).
    units = units_per_1k_tokens(0.25, usd_to_sar=3.75, margin_multiplier=5.0, units_per_halala=1000)
    assert units == 468.75
    assert round(units) == 469


def test_worked_example_units_per_1k_output():
    # 1.125 halalas/1k x 1000 units/halala = 1125 units per 1000 output tokens, exactly.
    units = units_per_1k_tokens(1.50, usd_to_sar=3.75, margin_multiplier=2.0, units_per_halala=1000)
    assert units == 1125.0


def test_no_premium_layer_anywhere_the_admin_entered_price_is_the_real_price():
    """The formula must have no hidden multiplier beyond usd_to_sar and the margin — an
    admin-entered $/M figure IS the real, region-correct cost as-is, by design."""
    zero_margin_no_fx = halalas_per_1k_tokens(1.0, usd_to_sar=1.0, margin_multiplier=1.0)
    # 1 usd/M -> 1 SAR/M (fx=1) -> x1 margin = 1 SAR/M -> x100 halalas/SAR = 100 halalas/M
    # -> /1000 = 0.1 halalas/1k. No hidden step changes this.
    assert zero_margin_no_fx == 0.1


def test_negative_inputs_never_produce_a_negative_rate():
    assert halalas_per_1k_tokens(-5, usd_to_sar=3.75, margin_multiplier=5.0) == 0.0
    assert halalas_per_1k_tokens(1.0, usd_to_sar=-1.0, margin_multiplier=5.0) == 0.0
    assert halalas_per_1k_tokens(1.0, usd_to_sar=3.75, margin_multiplier=-5.0) == 0.0


# ── model-cost registry parsing ─────────────────────────────────────────────────────────────────
def test_parse_model_costs_reads_a_valid_registry():
    raw = ('{"gemini-3.1-flash-lite": {"input_usd_per_million": 0.25, '
          '"output_usd_per_million": 1.5}}')
    costs = parse_model_costs(raw)
    assert costs == {"gemini-3.1-flash-lite": ModelCost(0.25, 1.5)}


def test_parse_model_costs_on_malformed_json_returns_empty_not_raises():
    assert parse_model_costs("{not json") == {}
    assert parse_model_costs("") == {}
    assert parse_model_costs("[]") == {}   # a list, not a dict of models


def test_parse_model_costs_drops_a_row_missing_a_required_field():
    raw = '{"model-a": {"input_usd_per_million": 1.0}, "model-b": {"input_usd_per_million": 1.0, "output_usd_per_million": 2.0}}'
    costs = parse_model_costs(raw)
    assert "model-a" not in costs
    assert costs["model-b"] == ModelCost(1.0, 2.0)


# ── model_rate_halalas_per_1k — the caller conversation.py actually uses ───────────────────────
def test_model_rate_uses_the_registry_when_the_model_is_known():
    cfg = AiUnitPricingConfig(
        units_per_halala=1000, input_margin_multiplier=5.0, output_margin_multiplier=2.0,
        usd_to_sar=3.75, model_costs={"gemini-3.1-flash-lite": ModelCost(0.25, 1.50)})
    input_rate, output_rate = model_rate_halalas_per_1k(
        cfg, "gemini-3.1-flash-lite", fallback_halalas_per_1k=99.0)
    assert input_rate == 0.46875
    assert output_rate == 1.125


def test_model_rate_falls_back_to_the_flat_rate_for_an_unpriced_model():
    """A model missing from the registry must never block the AI — it gets the flat legacy rate
    in both directions rather than a KeyError or a refusal."""
    cfg = AiUnitPricingConfig(
        units_per_halala=1000, input_margin_multiplier=5.0, output_margin_multiplier=2.0,
        usd_to_sar=3.75, model_costs={})
    input_rate, output_rate = model_rate_halalas_per_1k(
        cfg, "some-new-unpriced-model", fallback_halalas_per_1k=42.0)
    assert input_rate == 42.0 and output_rate == 42.0


def test_a_cheap_model_and_an_expensive_model_produce_visibly_different_rates():
    """Real per-model differentiation — the whole point of this module over the old flat rate."""
    cfg = AiUnitPricingConfig(
        units_per_halala=1000, input_margin_multiplier=5.0, output_margin_multiplier=2.0,
        usd_to_sar=3.75,
        model_costs={
            "cheap-model": ModelCost(0.10, 0.40),
            "expensive-model": ModelCost(3.00, 15.00),
        })
    cheap_in, cheap_out = model_rate_halalas_per_1k(cfg, "cheap-model", fallback_halalas_per_1k=0)
    exp_in, exp_out = model_rate_halalas_per_1k(cfg, "expensive-model", fallback_halalas_per_1k=0)
    assert exp_in > cheap_in
    assert exp_out > cheap_out
    assert exp_in > cheap_in * 10   # a real, large gap — not noise


# ── AiUnitPricingConfig.from_runtime / from_settings ───────────────────────────────────────────
class _Settings:
    PRICING_AI_UNIT_UNITS_PER_HALALA = 1000
    PRICING_AI_UNIT_INPUT_MARGIN_MULTIPLIER = 5.0
    PRICING_AI_UNIT_OUTPUT_MARGIN_MULTIPLIER = 2.0
    PRICING_AI_UNIT_USD_TO_SAR = 3.75
    PRICING_AI_UNIT_MODEL_COSTS_JSON = (
        '{"gemini-3.1-flash-lite": {"input_usd_per_million": 0.25, "output_usd_per_million": 1.5}}')


def test_from_settings_reads_the_deploy_time_defaults():
    cfg = AiUnitPricingConfig.from_settings(_Settings())
    assert cfg.units_per_halala == 1000
    assert cfg.input_margin_multiplier == 5.0
    assert cfg.model_costs["gemini-3.1-flash-lite"] == ModelCost(0.25, 1.5)


def test_from_runtime_with_no_runtime_config_falls_back_to_settings():
    cfg = run(AiUnitPricingConfig.from_runtime(None, _Settings()))
    assert cfg.usd_to_sar == 3.75


class _FakeRuntimeConfig:
    """Minimal stand-in — only `.get()`, matching what AiUnitPricingConfig.from_runtime calls."""

    def __init__(self, overrides: dict):
        self._overrides = overrides

    async def get(self, *, tenant: str, key: str, default):
        return self._overrides.get(key, default)


def test_from_runtime_prefers_a_live_override_over_the_deploy_time_default():
    rc = _FakeRuntimeConfig({"PRICING_AI_UNIT_INPUT_MARGIN_MULTIPLIER": 8.0})
    cfg = run(AiUnitPricingConfig.from_runtime(rc, _Settings()))
    assert cfg.input_margin_multiplier == 8.0
    assert cfg.output_margin_multiplier == 2.0   # untouched key keeps the deploy-time default
