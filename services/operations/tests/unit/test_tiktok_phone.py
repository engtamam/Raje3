"""`looks_like_real_phone` — the gate between a TikTok Shop order's own phone field and
`record_visit`'s ordinary normaliser. Every case here is a real shape TikTok or a customer could
actually produce, not a synthetic edge.
"""
from __future__ import annotations

from app.core.tiktok_phone import looks_like_real_phone


def test_a_real_saudi_number_passes():
    assert looks_like_real_phone("0501234567") is True
    assert looks_like_real_phone("+966501234567") is True


def test_blank_and_missing_fail():
    assert looks_like_real_phone("") is False
    assert looks_like_real_phone("   ") is False


def test_tiktoks_own_masked_shapes_fail():
    # Real shapes TikTok Shop's own redaction produces under "TikTok Shipping" — 1-2 visible
    # digits, the rest replaced by asterisks or bullets.
    assert looks_like_real_phone("1**-***-**23") is False
    assert looks_like_real_phone("9*********1") is False
    assert looks_like_real_phone("+966•••••••23") is False
    assert looks_like_real_phone("05xxxxxxx7") is False


def test_an_implausibly_short_number_fails_even_with_no_mask_characters():
    # No asterisk at all, but far too few digits to be a real, complete phone — a truncation or a
    # different kind of redaction TikTok might use without literal mask characters.
    assert looks_like_real_phone("0501") is False
    assert looks_like_real_phone("23") is False


def test_a_complete_foreign_number_still_passes_not_saudi_specific():
    # 11 real digits, no country-code assumption baked into the gate itself.
    assert looks_like_real_phone("+12025551234") is True


def test_arabic_indic_digits_are_folded_before_counting_never_isdigit():
    # ٠٥٠١٢٣٤٥٦٧ — the exact Arabic-keyboard shape `core/digits.py`'s own docstring warns about.
    assert looks_like_real_phone("٠٥٠١٢٣٤٥٦٧") is True
    # And a masked Arabic-Indic string must still fail — the mask check runs on the RAW string,
    # before folding, so an Arabic-typed mask character is caught the same way a Western one is.
    assert looks_like_real_phone("٠٥٠١**٤٥٦٧") is False


def test_whitespace_and_punctuation_around_real_digits_still_pass():
    assert looks_like_real_phone("+966 50 123 4567") is True
    assert looks_like_real_phone("(050) 123-4567") is True
