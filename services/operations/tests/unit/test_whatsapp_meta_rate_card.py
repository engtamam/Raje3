import pytest

from app.core.whatsapp_meta_rate_card import (BillableUnits, MetaRateCard, UnknownPricingModel,
                                              cost_halalas, rate_for)

# "966" — the E.164 calling code notification-service actually reports (confirmed against their
# real implementation), never an ISO country code. See BillableUnits.country's own docstring.
SA = "966"


def _units(**kw):
    base = {"provider": "threesixtydialog", "pricing_model": "CBP",
           "category": "marketing", "country": SA, "count": 1}
    base.update(kw)
    return BillableUnits(**base)


def test_no_rates_configured_means_the_default_zero():
    card = MetaRateCard(rates={})
    assert rate_for(card, _units()) == 0
    assert cost_halalas(card, _units(count=500)) == 0


def test_a_seeded_rate_is_used_for_its_exact_category_and_calling_code():
    card = MetaRateCard(rates={("marketing", SA): 25, ("utility", SA): 12})
    assert rate_for(card, _units(category="marketing", country=SA)) == 25
    assert rate_for(card, _units(category="utility", country=SA)) == 12


def test_an_unpriced_corridor_falls_back_to_the_configured_default_not_a_guess():
    card = MetaRateCard(rates={("marketing", SA): 25}, default_halalas=5)
    assert rate_for(card, _units(category="marketing", country="20")) == 5   # Egypt's calling code


def test_an_unrecognised_calling_code_is_the_empty_string_not_a_wrong_guess():
    """notification-service reports "" for a prefix it could not recognise — this must fall back
    to the same configured default as any other unpriced corridor, never raise or fabricate one."""
    card = MetaRateCard(rates={("marketing", SA): 25}, default_halalas=5)
    assert rate_for(card, _units(category="marketing", country="")) == 5


def test_service_category_is_always_free_even_if_a_rate_exists_for_it():
    card = MetaRateCard(rates={("service", SA): 999})
    assert rate_for(card, _units(category="service", country=SA)) == 0


def test_cost_scales_with_the_real_message_count():
    card = MetaRateCard(rates={("marketing", SA): 25})
    assert cost_halalas(card, _units(category="marketing", country=SA, count=40)) == 1000


def test_an_unknown_pricing_model_is_refused_not_silently_priced_as_cbp():
    card = MetaRateCard(rates={("marketing", SA): 25})
    with pytest.raises(UnknownPricingModel):
        rate_for(card, _units(pricing_model="NBP"))


def test_from_settings_parses_the_json_rate_card():
    class _Settings:
        WHATSAPP_META_RATE_CARD_JSON = '{"marketing:966": 25, "utility:966": 12}'
        WHATSAPP_META_RATE_CARD_DEFAULT_HALALAS = 3

    card = MetaRateCard.from_settings(_Settings())
    assert card.rates == {("marketing", SA): 25, ("utility", SA): 12}
    assert card.default_halalas == 3


def test_from_settings_with_empty_json_is_the_all_zero_default():
    class _Settings:
        WHATSAPP_META_RATE_CARD_JSON = ""
        WHATSAPP_META_RATE_CARD_DEFAULT_HALALAS = 0

    card = MetaRateCard.from_settings(_Settings())
    assert card.rates == {}
    assert rate_for(card, _units()) == 0
