"""Any brand colour, still readable — the one thing that is not negotiable."""
from __future__ import annotations

import pytest

from app.core.theme import MIN_CONTRAST, build_theme, contrast, ink_for, luminance, mix


def test_luminance_orders_colours_the_way_an_eye_does():
    """Green carries most of the perceived brightness — which is why a saturated blue looks dark
    and a saturated yellow does not, at the same 'value'."""
    assert luminance("#ffffff") > luminance("#00ff00") > luminance("#0000ff")
    assert luminance("#000000") == 0.0


def test_ink_flips_with_the_background():
    assert ink_for("#ffffff") == "#111827"
    assert ink_for("#0F5F4E") == "#F9FAFB"


@pytest.mark.parametrize("brand", ["#0F5F4E", "#1D4ED8", "#B91C1C", "#7C2D12", "#111111"])
def test_a_usable_brand_colour_is_kept_as_it_is(brand):
    """The shop's identity survives intact when it can carry text."""
    t = build_theme(brand)
    assert t.brand_applied and t.accent.lower() == brand.lower()
    assert contrast(t.accent, t.accent_ink) >= MIN_CONTRAST


@pytest.mark.parametrize("brand", ["#FFFF00", "#F5F5F5", "#87CEEB", "#FFC0CB"])
def test_a_pale_colour_is_darkened_so_the_control_can_be_SEEN(brand):
    """The gap the first version of this test pointed at without naming: near-white with dark ink
    is 16:1 and entirely readable — and completely invisible as a button on a white page. A shop
    would supply their pale brand colour, every control would vanish, and nothing would fail."""
    from app.core.theme import MIN_UI_CONTRAST
    t = build_theme(brand)
    assert not t.brand_applied
    assert contrast(t.accent, t.accent_ink) >= MIN_CONTRAST
    assert contrast(t.accent, t.surface) >= MIN_UI_CONTRAST


@pytest.mark.parametrize("brand", ["#FFFF00", "#F5F5F5", "#87CEEB", "#FFC0CB"])
def test_the_adjusted_colour_is_still_theirs(brand):
    """A shop that gave us pale mint gets deep mint, not our green — we move along their hue."""
    t = build_theme(brand)
    assert t.accent != "#0F5F4E"


def test_the_soft_tint_is_readable_too():
    """A quiet panel still has words on it."""
    for brand in ("#0F5F4E", "#FFFF00", "#111111", None):
        t = build_theme(brand)
        assert contrast(t.accent_soft, t.accent_soft_ink) >= MIN_CONTRAST


def test_a_missing_or_nonsense_colour_falls_back_without_erroring():
    """A page that 500s because an owner typed a word into a colour field punishes the customer
    for the owner's typo."""
    for bad in (None, "", "   ", "أخضر", "rgb(1,2,3)", "#12345", "not-a-colour"):
        t = build_theme(bad)
        assert not t.brand_applied
        assert contrast(t.accent, t.accent_ink) >= MIN_CONTRAST


def test_the_adjustment_is_reported_rather_than_hidden():
    """brand_applied=False is what lets the console TELL the owner their colour was adjusted,
    instead of quietly ignoring what they chose."""
    assert build_theme("#F5F5F5").brand_applied is False
    assert build_theme("#0F5F4E").brand_applied is True


def test_mix_is_bounded_and_matches_the_ends():
    assert mix("#000000", "#ffffff", 0) == "#000000"
    assert mix("#000000", "#ffffff", 1) == "#ffffff"
    assert mix("#000000", "#ffffff", 5) == "#ffffff"
    assert mix("#000000", "#ffffff", -3) == "#000000"


def test_the_css_variables_carry_every_token_the_page_uses():
    css = build_theme("#0F5F4E").css_variables()
    for token in ("--accent:", "--accent-ink:", "--surface:", "--text:", "--border:"):
        assert token in css
