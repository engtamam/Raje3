"""One phone number, folded to one string — the whole basis of the referral code's identity.

THIS SERVICE MINTS NO ACCOUNT AND ASKS FOR NO OTP — the code itself is anonymous by design (see
docs/خطة-تطبيق-الإحالة-والمسوقين-2026-09-27.md's own "الكود قناع لرقم الجوال" decision): the same
normalized phone always maps to the same short code, platform-wide, with nothing else stored
alongside it. Copied verbatim from services/coworking/app/core/phone.py (byte-identical logic,
same reasoning that file's own docstring gives for why this is folded here rather than imported —
this fleet's services deploy independently and never import each other's code, see
`app/core/riyadh.py`'s own note on the same discipline for the clock) — matching the same normalizer
`services/operations/app/core/signup.py::canonical_phone` uses, so `0501234567`,
`+966501234567` and `966501234567` fold to the identical string everywhere in this fleet.
"""
from __future__ import annotations

import re

#: Saudi mobile — the whole fleet's own default country code (operations' own
#: AFFILIATE_PHONE_DEFAULT_CC/SIGNUP default carries the same value).
DEFAULT_CC = "966"


def canonical_phone(raw: str, *, default_cc: str = DEFAULT_CC) -> str:
    """`0501234567`, `+966501234567` and `966501234567` are ONE human. Empty/unparseable input
    folds to `""` — a caller must treat that as "no phone", never as a distinct identity of its
    own (an empty string is not a person)."""
    digits = re.sub(r"\D", "", raw or "")
    if not digits:
        return ""
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("0"):
        digits = default_cc + digits[1:]
    elif not digits.startswith(default_cc):
        digits = default_cc + digits
    return "+" + digits
