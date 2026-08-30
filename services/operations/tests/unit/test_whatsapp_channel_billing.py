"""bill_period — the join between a raw usage report and what we'd actually charge for it."""
from __future__ import annotations

import pytest

from app.core.whatsapp_channel_billing import bill_period
from app.core.whatsapp_channel_pricing import ChannelPricingConfig
from app.core.whatsapp_meta_rate_card import MetaRateCard

USAGE = {
    "tenant": "acme", "period": "2026-08", "total_messages": 12, "billable_messages": 10,
    "truncated": False,
    "breakdown": [
        {"category": "marketing", "country": "966", "pricing_model": "CBP",
         "billable": True, "messages": 10},
        {"category": "service", "country": "966", "pricing_model": "CBP",
         "billable": False, "messages": 2},
    ],
}


def _cfg(**kw):
    base = dict(strategy="usage_based", usage_margin_percent=100,
               usage_flat_halalas_per_message=5)
    base.update(kw)
    return ChannelPricingConfig(**base)


def test_zero_config_means_zero_charge_even_with_real_usage():
    card = MetaRateCard(rates={})
    cfg = _cfg(usage_margin_percent=0, usage_flat_halalas_per_message=0)
    out = bill_period(card, cfg, USAGE)
    assert out["charged_halalas_total"] == 0
    assert all(r["charged_halalas_total"] == 0 for r in out["breakdown"])


def test_flat_margin_charges_every_paid_message_the_flat_amount_with_no_sourced_rate():
    """No rate card seeded (real cost unsourced, reads 0) — the flat component still charges,
    which is exactly "charge 5 halalas margin per message" before we've sourced Meta's rates."""
    card = MetaRateCard(rates={})
    cfg = _cfg()
    out = bill_period(card, cfg, USAGE)
    marketing_row = out["breakdown"][0]
    assert marketing_row["real_cost_halalas_per_message"] == 0
    assert marketing_row["charged_halalas_per_message"] == 5
    assert marketing_row["charged_halalas_total"] == 50          # 10 messages * 5 halalas
    service_row = out["breakdown"][1]
    assert service_row["charged_halalas_total"] == 0               # non-billable — no margin either
    assert out["charged_halalas_total"] == 50


def test_cost_plus_flat_once_a_real_rate_is_sourced():
    card = MetaRateCard(rates={("marketing", "966"): 25})
    cfg = _cfg()
    out = bill_period(card, cfg, USAGE)
    marketing_row = out["breakdown"][0]
    assert marketing_row["real_cost_halalas_per_message"] == 25
    assert marketing_row["charged_halalas_per_message"] == 30      # 25 cost + 5 margin
    assert marketing_row["charged_halalas_total"] == 300           # * 10 messages


def test_an_unknown_pricing_model_zeroes_only_its_own_row_not_the_whole_bill():
    usage = {**USAGE, "breakdown": [
        USAGE["breakdown"][0],
        {"category": "marketing", "country": "20", "pricing_model": "NBP",
         "billable": True, "messages": 3},
    ]}
    card = MetaRateCard(rates={("marketing", "966"): 25})
    cfg = _cfg()
    out = bill_period(card, cfg, usage)
    assert out["breakdown"][0]["charged_halalas_total"] == 300     # unaffected
    assert out["breakdown"][1]["charged_halalas_total"] == 0
    assert "error" in out["breakdown"][1]
    assert out["charged_halalas_total"] == 300                     # the bad row contributes zero


def test_refuses_any_strategy_that_is_not_usage_based():
    card = MetaRateCard(rates={})
    cfg = _cfg(strategy="tier_plus_cap")
    with pytest.raises(ValueError):
        bill_period(card, cfg, USAGE)


def test_a_non_billable_row_is_never_charged_a_margin_even_with_a_real_rate_seeded():
    """Meta gave the message away (billable: false) — a seeded rate for that (category, country)
    must not matter, and neither must the flat margin: nothing was ever billed to us for it."""
    usage = {**USAGE, "breakdown": [
        {"category": "service", "country": "966", "pricing_model": "CBP",
         "billable": False, "messages": 40},
    ]}
    card = MetaRateCard(rates={("service", "966"): 999})   # even a (wrongly) seeded rate
    cfg = _cfg()
    out = bill_period(card, cfg, usage)
    assert out["breakdown"][0]["charged_halalas_total"] == 0
    assert out["charged_halalas_total"] == 0


def test_an_empty_breakdown_bills_nothing():
    card = MetaRateCard(rates={})
    cfg = _cfg()
    out = bill_period(card, cfg, {**USAGE, "breakdown": []})
    assert out["breakdown"] == []
    assert out["charged_halalas_total"] == 0
