"""proofs 2, 3 and 4 — the three numbers that describe our own effect, and must not flatter it."""
from app.core import indicators as I
from app.core import holdout as H

DAY = 86400
NOW = 1_800_000_000


# ── proof 2 — the holdout comparison ───────────────────────────────────────────────────────────
def test_the_comparison_refuses_a_thin_sample():
    """Fifteen a side is already thin; below it one returning customer moves the answer by seven
    points, and we would be claiming a triumph on the strength of one man changing his oil."""
    visits = [{"subject_ref": f"c{i}", "occurred_at": NOW - 10 * DAY} for i in range(12)]
    r = I.holdout_comparison(visits, tenant="shop-1", now=NOW)
    assert r["ready"] is False and r["reason"] == "learning"


def test_the_comparison_reports_both_rates_and_no_verdict():
    visits = []
    for i in range(500):
        ref = f"c{i}"
        visits.append({"subject_ref": ref, "occurred_at": NOW - 100 * DAY})
        held = H.is_holdout("shop-1", ref)
        if (not held and i % 2 == 0) or (held and i % 5 == 0):
            visits.append({"subject_ref": ref, "occurred_at": NOW - 20 * DAY})
    r = I.holdout_comparison(visits, tenant="shop-1", now=NOW)
    assert r["ready"] is True
    assert r["reached_rate"] > r["held_rate"]
    assert r["gap"] == round(r["reached_rate"] - r["held_rate"], 3)
    # no claim, no adjective, no "raje3 improved you by": just the two numbers
    assert set(r) == {"ready", "held", "reached", "held_rate", "reached_rate", "gap", "window_days"}


# ── proof 3 — visits credited to a message ─────────────────────────────────────────────────────
def test_a_customer_who_had_already_come_back_is_not_credited():
    """The self-flattery this whole indicator is written against: counting somebody who was in the
    shop last week, got a message, came again, and is then read as proof the message worked."""
    visits = [{"subject_ref": "a", "occurred_at": NOW - 9 * DAY},   # before the message
              {"subject_ref": "a", "occurred_at": NOW - 2 * DAY}]   # after it
    sends = [{"subject_ref": "a", "at": NOW - 5 * DAY}]
    assert I.returned_after_reminder(visits, sends, now=NOW)["visits"] == 0


def test_a_visit_inside_the_window_is_credited_once():
    visits = [{"subject_ref": "b", "occurred_at": NOW - 3 * DAY}]
    sends = [{"subject_ref": "b", "at": NOW - 6 * DAY}]
    assert I.returned_after_reminder(visits, sends, now=NOW)["visits"] == 1


def test_a_visit_long_after_the_message_is_not_ours():
    visits = [{"subject_ref": "c", "occurred_at": NOW - 1 * DAY}]
    sends = [{"subject_ref": "c", "at": NOW - 25 * DAY}]     # 24 days apart, window is 14
    assert I.returned_after_reminder(visits, sends, now=NOW)["visits"] == 0


# ── proof 4 — stops per thousand ───────────────────────────────────────────────────────────────
def test_no_warning_before_two_hundred_messages():
    """One stop in fifty is twenty per thousand — a red light on a shop that has done nothing."""
    r = I.opt_out_rate(50, 1)
    assert r["ready"] is False and r["need"] == 200


def test_the_rate_is_per_thousand_and_rounded_once():
    r = I.opt_out_rate(1000, 7)
    assert r["ready"] is True and r["rate"] == 7.0
