"""One phone fold, used by both onboarding.py and referrals.py — the same reasoning operations'
own core/signup.py gives for its identical function: `0501234567`, `+966501234567` and
`966501234567` must never become three different comparisons for one human, or a self-referral
check (referrals.py) compares apples to oranges and a real one slips through."""
from __future__ import annotations

import re


def canonical_phone(raw: str, *, default_cc: str) -> str:
    digits = re.sub(r"\D", "", raw or "")
    if not digits:
        return ""
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("0"):
        digits = default_cc + digits[1:]
    elif not digits.startswith(default_cc):
        digits = default_cc + digits
    elif digits[len(default_cc):].startswith("0"):
        digits = default_cc + digits[len(default_cc) + 1:]  # cc+leading-zero typo
    return "+" + digits
