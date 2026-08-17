"""ح-5 — the statement stopped being reproducible by the person it is paid to.

    return int(self.net_minor * self.rate)

under a docstring that said «never on a float» and defended `int()` as deterministic. Truncation
IS deterministic. It truncates a number binary floating point had already got wrong:

    100000 * 0.29  ->  28999.999999999996  ->  int()  ->  28999

AND NOBODY CHOSE THAT. A partner on 30% was paid exactly, because 0.30 lands close enough; a
partner on 29% was short, because 0.29 has no exact binary form. Two partners, the same code, and
nothing in the file tells you which of them is which without running it.

THE HALALA IS NOT THE POINT. The point is that a partner who computes 29% of the net and compares
gets a different number than we do, and the difference has no explanation anywhere he can read.
That is what turns a statement into an argument.
"""
from __future__ import annotations

from decimal import Decimal

from app.core.commission import Line

TENANT = "shop"


def _line(settled: int, rate: float, refunded: int = 0) -> Line:
    return Line(tenant=TENANT, settled_minor=settled, refunded_minor=refunded, rate=rate)


def test_the_rate_that_used_to_be_wrong():
    """29% of 1,000.00 is 290.00. It was 289.99."""
    assert _line(100_000, 0.29).commission_minor == 29_000


def test_and_the_rate_that_happened_to_be_right_still_is():
    """0.30 was correct by luck rather than by construction. It must stay correct by construction."""
    assert _line(100_000, 0.30).commission_minor == 30_000


def test_every_rate_we_actually_sell_matches_what_a_person_gets_on_paper():
    """The whole point of the fix: our number and the partner's arithmetic agree.

    `Decimal(str(rate))` is what makes this hold — `Decimal(0.29)` would inherit the float's error
    and move the bug rather than remove it.
    """
    for rate in (0.10, 0.15, 0.20, 0.25, 0.29, 0.30, 0.35):
        for settled in (100_000, 29_900, 1_499, 7):
            on_paper = int((Decimal(settled) * Decimal(str(rate))).to_integral_value(rounding="ROUND_DOWN"))
            assert _line(settled, rate).commission_minor == on_paper, (rate, settled)


def test_rounding_is_down_and_that_is_the_policy():
    """We never over-pay by a halala. 1,499 at 29% is 434.71; the partner gets 434."""
    assert _line(1_499, 0.29).commission_minor == 434


def test_a_refund_comes_off_before_the_rate_is_applied():
    """The commission is on money that stayed with us, and the arithmetic order says so."""
    assert _line(100_000, 0.29, refunded=50_000).commission_minor == 14_500


def test_a_refund_larger_than_the_payment_is_not_a_negative_commission():
    """We do not invoice a partner. `net_minor` floors at zero and this must follow it."""
    assert _line(10_000, 0.29, refunded=99_000).commission_minor == 0
