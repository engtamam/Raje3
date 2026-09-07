"""proof 1 — the return rate as a line, and the three ways it must refuse to lie."""
from app.core import indicators

DAY = 86400
NOW = 1_800_000_000


def _shop(early_repeat: int, late_repeat: int) -> list[dict]:
    """40 customers a year ago and 50 in the last five months, with the repeats we ask for."""
    v = []
    for c in range(40):
        v.append({"subject_ref": f"a{c}", "occurred_at": NOW - 340 * DAY})
        if c < early_repeat:
            v.append({"subject_ref": f"a{c}", "occurred_at": NOW - 310 * DAY})
    for c in range(50):
        v.append({"subject_ref": f"b{c}", "occurred_at": NOW - 120 * DAY})
        if c < late_repeat:
            v.append({"subject_ref": f"b{c}", "occurred_at": NOW - 30 * DAY})
    return v


def test_the_line_moves_with_the_shop():
    r = indicators.retention_series(_shop(early_repeat=0, late_repeat=30), now=NOW)
    assert r["learning"] is False
    assert r["last"] > r["first"]
    assert r["delta"] > 0


def test_a_thin_window_is_a_gap_and_never_a_zero():
    """A month with six customers in it must not draw a point at all.

    THIS IS THE WHOLE POINT OF THE INDICATOR. 0.0 reads as «nobody came back», which is a verdict;
    a gap reads as «we do not know yet», which is the truth.
    """
    v = [{"subject_ref": f"c{i}", "occurred_at": NOW - 200 * DAY} for i in range(6)]
    r = indicators.retention_series(v, now=NOW)
    assert r["learning"] is True
    assert r["points"] == []
    assert r["need"] == 20


def test_the_measurement_does_not_change_shape_over_the_line():
    """Every point is the same window length — otherwise the line shows our method changing."""
    r = indicators.retention_series(_shop(early_repeat=8, late_repeat=30), now=NOW, points=6)
    ats = [p["at"] for p in r["points"]]
    gaps = {b - a for a, b in zip(ats, ats[1:])}
    assert gaps == {30 * DAY}


def test_an_empty_shop_is_learning_not_zero():
    r = indicators.retention_series([], now=NOW)
    assert r["learning"] is True and r["have"] == 0


def test_the_per_customer_index_is_built_once_per_window_not_twice(monkeypatch):
    """THE DUPLICATE WORK THIS CLOSES. `retention_series` used to call `_by_customer(slice_)` for
    `people` and then `return_rate(slice_)`, which called `_by_customer` again on the identical
    slice — two builds per window instead of one. Proved by counting real `_by_customer` calls,
    not just that the numbers came out right: a fix that still built the index twice would still
    pass a value-only test."""
    calls = {"n": 0}
    real = indicators._by_customer

    def counting(visits):
        calls["n"] += 1
        return real(visits)

    monkeypatch.setattr(indicators, "_by_customer", counting)

    r = indicators.retention_series(_shop(early_repeat=8, late_repeat=30), now=NOW, points=6)

    assert r["learning"] is False
    assert calls["n"] == 6, f"expected exactly one build per window (6), got {calls['n']}"
