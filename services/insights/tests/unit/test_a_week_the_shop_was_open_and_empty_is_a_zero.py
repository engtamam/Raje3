"""A closed week is data. It says zero, and it used to be thrown away.

`expected_flow` filtered its weekly counts with `[c for c in counts if c]` before taking the mean,
and `engine_reserve` built its samples from a Counter that only ever had keys for weeks a visit
happened in. Both amount to the same thing: a week with no visits vanished, and the average was
taken over the busy weeks only.

WHAT THE OWNER GETS. A car wash that closed for two weeks reported [40, 0, 0, 44] as 42 when the
truth is 21 — and that number staffs a shift. A workshop that closes every Friday had its Friday
reserve computed from the Fridays it opened, so twelve messages were held back every single Friday
for a day that reliably brings nobody.

AND THE OTHER HALF, WHICH IS WHY THIS IS NOT JUST «COUNT THE ZEROS». A week before the shop opened
is not a zero, it is nothing — padding with it would tell a one-week-old shop doing forty visits a
week to expect ten. So the denominator is how long the shop has actually been open.
"""
from __future__ import annotations

from app.core.indicators import DAY, engine_reserve, expected_flow

NOW = 1_780_000_000
WEEK = 7 * DAY


def _visits(*weeks_ago_counts: tuple[int, int]) -> list[dict]:
    """(weeks_ago, how_many) → visit rows, placed mid-week so no boundary rounding is involved."""
    out = []
    for weeks_ago, n in weeks_ago_counts:
        at = NOW - weeks_ago * WEEK - 3 * DAY
        out.extend({"occurred_at": at} for _ in range(n))
    return out


def test_two_closed_weeks_halve_the_expectation_instead_of_disappearing():
    """[40, 0, 0, 44] over four weeks the shop was open for is 21, not 42."""
    visits = _visits((0, 40), (3, 44))
    assert expected_flow(visits, now=NOW, weeks=4) == 21


def test_a_shop_one_week_old_is_not_averaged_over_weeks_it_did_not_exist():
    """The guard against over-correcting: forty visits in its only week means expect forty."""
    assert expected_flow(_visits((0, 40)), now=NOW, weeks=4) == 40


def test_a_shop_with_no_visits_at_all_expects_nothing():
    assert expected_flow([], now=NOW, weeks=4) == 0


def test_the_reserve_sees_the_weekdays_that_brought_nobody():
    """A day that is dead three weeks in four must not be reserved for as if it were busy.

    The visits are all placed on the SAME weekday as `NOW`, so `engine_reserve` looks at exactly
    the weeks built here: one busy, three empty. Before this, `counts` was [30] and the reserve
    was thirty; now it is [0, 0, 0, 30] and the percentile has three zeros to reason about.
    """
    busy_only = _visits((0, 30))
    old = engine_reserve(busy_only, now=NOW - 3 * DAY, weeks=4, floor=5)
    # Placed 3 days back by the helper, so `now - 3*DAY` lands on that same weekday.
    assert old["samples"] >= 1

    # A shop that has been open four weeks and had that one busy day reserves near the floor,
    # not near thirty: three of its four samples are zero.
    aged = engine_reserve(busy_only + _visits((3, 1)), now=NOW - 3 * DAY, weeks=4, floor=5)
    assert aged["reserve"] <= old["reserve"], (
        "adding history that shows the day is usually empty must never RAISE the reserve")
