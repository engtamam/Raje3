"""One phone number, folded to one string — the freelancer's ENTIRE identity in this app.

THIS SERVICE HAS NO OTP, NO PASSWORD, AND NO IDENTITY-SERVICE ACCOUNT FOR A FREELANCER (spec
§5) — a genuinely new pattern in this fleet. Every other "phone is identity" precedent already in
this codebase is a different shape: operations' own `canonical_phone()`
(services/operations/app/core/signup.py) folds a shop OWNER's phone before a password is checked
against it, and the WhatsApp flow's identity is Meta's own cryptographically-verified sender, never
a string a stranger typed into a form. A stranger who opens the shop's public link and types a
number is trusted to be that number, going forward, for THIS ONE TENANT — the join-request gate
(spec §6) is what stands in for the verification a password or an OTP would otherwise give.

FOLDED HERE, NOT IMPORTED, on purpose — this fleet's services deploy independently and never
import each other's code (see `app/core/riyadh.py`'s own note on the same discipline for the
clock). The logic is intentionally the same shape as `signup.py::canonical_phone` so the same
human typing `0501234567`, `+966501234567` or `966501234567` folds to the identical string there
and here, without the two files ever sharing an import.
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
