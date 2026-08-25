from app.core.pricing import ConversationCost, PricingConfig, price_conversation


def test_tier_plus_cap_free_inside_included():
    cfg = PricingConfig(strategy="tier_plus_cap", tier_included_conversations=10,
                        tier_overage_halalas_per_conversation=50)
    price = price_conversation(cfg, ConversationCost(100, 100), conversations_this_period=5)
    assert price == 0


def test_tier_plus_cap_charges_overage_past_included():
    cfg = PricingConfig(strategy="tier_plus_cap", tier_included_conversations=10,
                        tier_overage_halalas_per_conversation=50)
    price = price_conversation(cfg, ConversationCost(100, 100), conversations_this_period=11)
    assert price == 50


def test_addon_flat_charged_only_on_first_conversation_of_period():
    cfg = PricingConfig(strategy="addon_on_existing_plan", addon_flat_halalas=2000)
    first = price_conversation(cfg, ConversationCost(0, 0),
                               is_first_conversation_this_period=True)
    later = price_conversation(cfg, ConversationCost(0, 0),
                               is_first_conversation_this_period=False)
    assert first == 2000
    assert later == 0


def test_usage_based_scales_with_real_token_counts():
    cfg = PricingConfig(strategy="usage_based", usage_halalas_per_1k_tokens=10,
                        usage_halalas_per_conversation=5)
    cheap = price_conversation(cfg, ConversationCost(100, 100))
    expensive = price_conversation(cfg, ConversationCost(5000, 5000))
    assert cheap == 5 + round(200 / 1000 * 10)
    assert expensive > cheap


def test_zero_config_means_zero_price_by_default():
    """The values file ships every pricing constant at zero — this is the property that makes
    that safe: nothing here invents a number that was never configured."""
    cfg = PricingConfig(strategy="usage_based")
    assert price_conversation(cfg, ConversationCost(999999, 999999)) == 0


def test_unknown_strategy_is_refused_not_silently_free():
    cfg = PricingConfig(strategy="made_up_strategy")
    try:
        price_conversation(cfg, ConversationCost(1, 1))
        assert False, "expected ValueError"
    except ValueError:
        pass
