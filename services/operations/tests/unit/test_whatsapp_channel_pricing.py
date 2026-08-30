from app.core.whatsapp_channel_pricing import ChannelPricingConfig, MessageCost, price_message


def test_tier_plus_cap_free_inside_included():
    cfg = ChannelPricingConfig(strategy="tier_plus_cap", tier_included_messages=1000,
                               tier_overage_halalas_per_message=5)
    price = price_message(cfg, MessageCost("threesixtydialog", 40), messages_this_period=500)
    assert price == 0


def test_tier_plus_cap_charges_overage_past_included():
    cfg = ChannelPricingConfig(strategy="tier_plus_cap", tier_included_messages=1000,
                               tier_overage_halalas_per_message=5)
    price = price_message(cfg, MessageCost("threesixtydialog", 40), messages_this_period=1001)
    assert price == 5


def test_addon_flat_charged_only_on_first_message_of_period():
    cfg = ChannelPricingConfig(strategy="addon_on_existing_plan", addon_flat_halalas=1500)
    first = price_message(cfg, MessageCost("threesixtydialog", 40),
                          is_first_message_this_period=True)
    later = price_message(cfg, MessageCost("threesixtydialog", 40),
                          is_first_message_this_period=False)
    assert first == 1500
    assert later == 0


def test_usage_based_charges_the_configured_fraction_of_the_real_cost():
    # 120% = pass the real cost through plus a 20% markup on top of it.
    cfg = ChannelPricingConfig(strategy="usage_based", usage_margin_percent=120,
                               usage_flat_halalas_per_message=1)
    price = price_message(cfg, MessageCost("threesixtydialog", 40))
    assert price == 1 + round(40 * 1.20)


def test_usage_based_at_its_zero_default_charges_nothing_even_with_a_real_cost():
    """The invariant every strategy in this module shares: unconfigured means free — never the
    real cost passed through "at par with no markup yet", which would silently bill a shop."""
    cfg = ChannelPricingConfig(strategy="usage_based")
    assert price_message(cfg, MessageCost("threesixtydialog", 40)) == 0


def test_usage_based_never_confuses_which_provider_incurred_the_cost():
    """The real cost travels with the message, not with the strategy — a provider whose cost is
    genuinely zero (direct Meta, the establishment pays Meta itself) prices at zero even under
    usage_based, because there was never a real cost of ours to add a margin to."""
    cfg = ChannelPricingConfig(strategy="usage_based", usage_margin_percent=20)
    price = price_message(cfg, MessageCost("meta", 0))
    assert price == 0


def test_zero_config_means_zero_price_by_default():
    """deploy/services/operations.values.yaml ships every WHATSAPP_CHANNEL_PRICING_* constant at
    zero — this is the property that makes that safe: nothing here invents a number that was
    never configured, however large the real cost reported."""
    cfg = ChannelPricingConfig(strategy="usage_based")
    assert price_message(cfg, MessageCost("threesixtydialog", 999999)) == 0


def test_unknown_strategy_is_refused_not_silently_free():
    cfg = ChannelPricingConfig(strategy="made_up_strategy")
    try:
        price_message(cfg, MessageCost("threesixtydialog", 1))
        assert False, "expected ValueError"
    except ValueError:
        pass
