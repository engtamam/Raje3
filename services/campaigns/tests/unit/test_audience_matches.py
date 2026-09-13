"""`_matches` — the goal-matching dispatch table, checked directly against every goal.

Written when the if/elif chain became a dict of matcher functions, to pin the exact same
per-goal behaviour the chain had (an unknown goal still matches nobody, etc).
"""
from __future__ import annotations

from app.core.audience import _matches

DAY = 86400
NOW = 1_800_000_000


def test_win_back_matches_1_5x_the_customers_own_interval():
    row = {"last_visit": NOW - 20 * DAY, "interval_days": 10}
    ok, why = _matches("win_back", row, now=NOW, window_days=14, min_visits=2)
    assert ok and why


def test_win_back_does_not_match_before_1_5x():
    row = {"last_visit": NOW - 12 * DAY, "interval_days": 10}
    ok, _ = _matches("win_back", row, now=NOW, window_days=14, min_visits=2)
    assert not ok


def test_win_back_does_not_match_a_customer_with_no_visit():
    ok, _ = _matches("win_back", {}, now=NOW, window_days=14, min_visits=2)
    assert not ok


def test_reward_loyal_matches_enough_visits_inside_the_window():
    row = {"visit_count": 5, "last_visit": NOW - 5 * DAY}
    ok, _ = _matches("reward_loyal", row, now=NOW, window_days=30, min_visits=3)
    assert ok


def test_reward_loyal_does_not_match_too_few_visits():
    row = {"visit_count": 1, "last_visit": NOW - 5 * DAY}
    ok, _ = _matches("reward_loyal", row, now=NOW, window_days=30, min_visits=3)
    assert not ok


def test_announce_matches_everyone():
    ok, why = _matches("announce", {}, now=NOW, window_days=14, min_visits=2)
    assert ok and why == "كل العملاء"


def test_package_offer_matches_everyone_same_as_broadcast():
    # 2026-09-12 regression — this goal was missing from `_MATCHERS` entirely, so every
    # package_offer campaign matched zero candidates (`_matches` falls back to `(False, "")` for
    # any goal not in the dict). It shares `_match_broadcast`, deliberately: no cycle lock (the
    # cycle lock only ever engages when `service_id` is set, which a package_offer campaign
    # never carries), same as `announce`.
    ok, why = _matches("package_offer", {}, now=NOW, window_days=14, min_visits=2)
    assert ok and why == "كل العملاء"


def test_service_offer_requires_a_service_id():
    ok, _ = _matches("service_offer", {}, now=NOW, window_days=14, min_visits=2, service_id="")
    assert not ok
    ok, _ = _matches("service_offer", {}, now=NOW, window_days=14, min_visits=2,
                     service_id="svc_1")
    assert ok


def test_occasion_matches_the_anniversary_of_the_customers_own_record():
    """A birthday we were never given, replaced with a date we actually hold: `created`, a year
    or more back, on the same Riyadh-local month and day."""
    # NOW is 2027-01-15 11:00 Riyadh — one year earlier, same date.
    ok, _ = _matches("occasion", {"created": NOW - 365 * DAY}, now=NOW, window_days=14, min_visits=2)
    assert ok
    ok, _ = _matches("occasion", {}, now=NOW, window_days=14, min_visits=2)
    assert not ok


def test_occasion_does_not_match_a_customer_created_today():
    """No anniversary yet — `years >= 1` is the guard, not "any earlier `created`"."""
    ok, _ = _matches("occasion", {"created": NOW}, now=NOW, window_days=14, min_visits=2)
    assert not ok


def test_occasion_does_not_match_a_different_day_of_the_year():
    ok, _ = _matches("occasion", {"created": NOW - 366 * DAY}, now=NOW, window_days=14, min_visits=2)
    assert not ok


def test_an_unknown_goal_matches_nobody():
    ok, why = _matches("not_a_real_goal", {"visit_count": 999}, now=NOW, window_days=14,
                       min_visits=1)
    assert not ok and why == ""
