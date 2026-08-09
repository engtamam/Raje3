"""How much of the day's ceiling the engine holds back — and the three ways it could go wrong."""
from __future__ import annotations

from app.core.indicators import DAY, engine_reserve

# A Thursday, in Riyadh terms. The weekday matters to every case here.
NOW = 1_786_000_000
WEEK = 7 * DAY


def visits(spec: dict[int, int], *, now: int = NOW):
    """`spec` maps weeks-ago -> how many visits on that same weekday."""
    out = []
    for weeks_ago, count in spec.items():
        for _ in range(count):
            out.append({"occurred_at": now - weeks_ago * WEEK})
    return out


def test_a_shop_with_no_history_reserves_the_floor():
    """The first fortnight is exactly when a dropped confirmation does the most damage, and there
    is no percentile to take. The campaign waits."""
    r = engine_reserve([], now=NOW, floor=25)
    assert r["reserve"] == 25 and r["basis"] == "floor"


def test_it_takes_the_percentile_of_the_same_weekday():
    r = engine_reserve(visits({0: 40, 1: 42, 2: 38, 3: 41}), now=NOW, floor=0)
    assert r["basis"] == "percentile"
    assert r["reserve"] >= 41           # absorbs the busy week rather than averaging it away


def test_it_ignores_a_freak_peak_rather_than_reserving_for_it():
    """One Eid peak must not steal the ceiling every ordinary day for two months — which is what
    the maximum would do, and why this is a percentile."""
    ordinary = engine_reserve(visits({0: 10, 1: 11, 2: 10, 3: 12, 4: 10, 5: 11}),
                              now=NOW, floor=0)["reserve"]
    with_peak = engine_reserve(visits({0: 10, 1: 11, 2: 10, 3: 12, 4: 10, 5: 11, 6: 400}),
                               now=NOW, floor=0)["reserve"]
    assert with_peak < 400
    assert with_peak <= ordinary * 4


def test_it_does_not_average_a_busy_weekday_away():
    """Thursday is twice Tuesday in most of these shops. Reserving the average would drop half of
    Thursday's visitors — and only on Thursdays, which is the hardest pattern to notice."""
    busy = engine_reserve(visits({0: 80, 1: 78, 2: 82}), now=NOW, floor=0)["reserve"]
    assert busy >= 78


def test_another_weekday_is_not_counted():
    """A Wednesday's visits say nothing about a Thursday's."""
    other = [{"occurred_at": NOW - 3 * DAY - w * WEEK} for w in range(6)]
    assert engine_reserve(other, now=NOW, floor=7)["basis"] == "floor"


def test_it_never_reserves_more_than_its_share_of_the_ceiling():
    """A busy shop that reserved everything could never run a campaign — which is a paid feature
    it bought from us."""
    r = engine_reserve(visits({0: 900, 1: 950, 2: 920}), now=NOW,
                       ceiling=1000, cap_share=0.7, floor=0)
    assert r["reserve"] == 700 and r["basis"] == "capped"
    assert r["wanted"] > 700          # the working is kept, so the cap is explicable


def test_the_floor_wins_when_the_history_is_thin():
    r = engine_reserve(visits({0: 2, 1: 1}), now=NOW, floor=30)
    assert r["reserve"] == 30 and r["basis"] == "floor"


def test_it_only_looks_back_as_far_as_the_window():
    """A rolling window is what lets it learn: a shop that grew over two months gets a larger
    reserve with nobody touching anything."""
    old_only = visits({20: 500, 21: 500})
    assert engine_reserve(old_only, now=NOW, weeks=8, floor=5)["basis"] == "floor"


def test_it_shows_its_working():
    """A number an owner cannot question is a number he does not trust — and the day this is wrong
    we will want to see which of the three guards produced it."""
    r = engine_reserve(visits({0: 10, 1: 12}), now=NOW, floor=0)
    assert set(r) >= {"reserve", "basis", "weekday", "samples"}
    assert r["samples"] == 2
