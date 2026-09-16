"""Is this actually a phone number, or TikTok's own mask wearing one?

TikTok Shop's default "TikTok Shipping" mode redacts the buyer's phone to 1-2 visible digits
before it ever reaches a seller's API — `"1**-***-**23"`, `"9*********1"`, or similar, depending on
locale. Running that string through the ordinary phone normaliser (`operations.py::_normalise_phone`)
would silently strip the mask characters and keep whatever bare digits remain — a FEW real digits
that look syntactically fine but identify nobody, and worse, could coincide with a different real
customer's own number by pure chance and silently misfile a visit onto a stranger.

So this is a SEPARATE, deliberately stricter gate, checked BEFORE the ordinary normaliser ever
runs — not a replacement for it. A string that fails this check never reaches `record_visit` with
a real `phone=`; the caller (`api/v1/tiktok.py`) passes `anonymous=True` instead.
"""
from __future__ import annotations

import re

from app.core.digits import WESTERN, western

# Any of these appearing anywhere in the raw string is TikTok's own redaction, not a typo a
# customer could have made — a real phone never legitimately contains a literal mask character.
_MASK_CHARS = re.compile(r"[*xX•●]")

# Fewer real digits than this cannot be a genuine phone number under any of the shapes this
# product already accepts (Saudi mobile is 9 digits after the country code alone). Deliberately
# generous rather than Saudi-specific — a foreign buyer's real, complete number should still pass;
# this only catches numbers that are OBVIOUSLY too short to be complete.
_MIN_REAL_DIGITS = 8


def looks_like_real_phone(raw: str) -> bool:
    """`True` only for a string worth handing to the ordinary phone normaliser at all. `False` for
    blank, masked, or implausibly short input — the caller's own signal to record the visit
    against the tenant's one anonymous placeholder instead of refusing the sale.

    FOLDED TO WESTERN DIGITS BEFORE COUNTING, NEVER `str.isdigit()` — the exact trap
    `core/digits.py`'s own module docstring documents and
    `ci/check_a_digit_from_an_arabic_keyboard_is_still_a_digit.py` refuses: an Arabic-Indic digit
    answers `True` to `isdigit()` but is not one of the ten characters this product treats as a
    digit anywhere else, and a mask check that used it would count differently depending on which
    keyboard produced the string TikTok itself already redacted.
    """
    if not raw or not raw.strip():
        return False
    if _MASK_CHARS.search(raw):
        return False
    digits = "".join(c for c in western(raw) if c in WESTERN)
    return len(digits) >= _MIN_REAL_DIGITS
