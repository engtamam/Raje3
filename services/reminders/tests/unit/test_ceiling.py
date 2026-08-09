"""The shop's WhatsApp ceiling — and what happens when we cannot read it."""
from __future__ import annotations

import asyncio

from app.core.ceiling import Ceiling, NullCeiling


def run(c):
    return asyncio.run(c)


def test_unknown_is_not_zero():
    """The peer refuses to fabricate a ceiling, and we must honour that rather than paper over it:
    a fabricated ceiling is worse than a known-unknown, because everything downstream then plans
    confidently against fiction."""
    c = Ceiling()
    assert not c.known() and c.limit == 0


def test_unlimited_is_known():
    """-1 is a real answer — the largest tier. Treating it as unknown would make the biggest
    establishments the ones we plan worst for."""
    c = Ceiling(limit=-1)
    assert c.known() and c.unlimited()


def test_a_real_tier_is_known():
    assert Ceiling(limit=250, tier="TIER_250").known()


def test_remaining_counts_down_from_the_ceiling():
    assert Ceiling(limit=250).remaining(reached_today=40) == 210


def test_remaining_never_goes_negative():
    """A shop already over its ceiling has zero left, not a negative allowance somebody might
    add to."""
    assert Ceiling(limit=250).remaining(reached_today=300) == 0


def test_unlimited_and_unknown_both_mean_do_not_hold_back():
    """Unknown behaves as unbounded HERE deliberately: we lose the planning, never the sending."""
    assert Ceiling(limit=-1).remaining(10) == -1
    assert Ceiling().remaining(10) == -1


def test_the_quality_rating_is_carried_even_though_nothing_reads_it_yet():
    """A tier falls after quality does, so YELLOW is the only advance notice available."""
    assert Ceiling(limit=250, quality="YELLOW").quality == "YELLOW"


def test_the_null_driver_answers_unknown():
    assert not run(NullCeiling().read("shop")).known()
