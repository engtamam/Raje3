"""The campaign record and the audience — the two places a campaign can be wrong quietly."""
from __future__ import annotations

import asyncio

import pytest

from app.core.audience import DAY, DEFAULT_MAX_AUDIENCE, resolve
from app.core.models import (GOAL_TEMPLATE, Campaign, Run, in_window, validate_loyalty_window,
                             validate_window)

NOW = 1_800_000_000
# NOW, in Riyadh local time, is Friday (weekday 4) at 11:00 — pinned here once so every window
# test below states its own boundary against a fact, not a re-derived guess.


def run(c):
    return asyncio.run(c)


def cust(ref, *, last_days=10, interval=60, visits=5, **extra):
    d = {"subject_ref": ref, "last_visit": NOW - last_days * DAY,
         "interval_days": interval, "visit_count": visits}
    d.update(extra)
    return d


def rows(*items):
    async def _c(tenant):
        return list(items)
    return _c


def audience(goal, *items, **kw):
    return run(resolve(goal=goal, tenant="t1", now=NOW, customers=rows(*items), **kw))


# ── the record ─────────────────────────────────────────────────────────────────────────────────
def test_the_goal_decides_the_template_and_the_class_not_the_owner():
    """Every campaign is promotional, and the owner never sees a class."""
    for goal, (tmpl, cls) in GOAL_TEMPLATE.items():
        c = Campaign(tenant="t1", goal=goal)
        assert c.template_type == tmpl and c.cls == cls


def test_the_goal_decides_who_fires_it():
    """Absence is continuous, so win-back is standing; news is not, so an announcement is once."""
    assert Campaign(tenant="t1", goal="win_back").is_standing
    assert not Campaign(tenant="t1", goal="announce").is_standing


def test_the_template_is_stored_at_creation_not_recomputed():
    """A template swapped underneath a live campaign is a message the owner never approved."""
    c = Campaign(tenant="t1", goal="announce", template_type="mkt_offer", cls="marketing")
    assert c.template_type == "mkt_offer"


def test_a_run_is_recorded_even_when_it_sends_nothing():
    """A standing campaign that matched nobody for a week is information, and silence looks
    identical to a broken cron."""
    r = Run(tenant="t1", campaign_id="cmp_1", at=NOW)
    assert r.matched == 0 and r.sent == 0 and r.key.startswith("t1|cmp_1|")


def test_two_runs_at_the_same_second_do_not_overwrite_each_other():
    a = Run(tenant="t1", campaign_id="cmp_1", at=NOW)
    b = Run(tenant="t1", campaign_id="cmp_1", at=NOW)
    assert a.key != b.key


# ── win-back: the customer's own rhythm, not a fixed number ────────────────────────────────────
def test_absence_is_measured_against_the_customers_own_cycle():
    """A car wash customer who comes weekly is absent after three weeks; a workshop customer is
    not absent until six months. One number for both sends the wrong message to whichever is not
    the average."""
    weekly_absent = cust("a", last_days=20, interval=7)
    workshop_fine = cust("b", last_days=20, interval=180)
    got = audience("win_back", weekly_absent, workshop_fine)
    assert [c.subject_ref for c in got.candidates] == ["a"]


def test_the_reason_is_carried_so_the_owner_can_sanity_check_the_rule():
    got = audience("win_back", cust("a", last_days=94, interval=60))
    assert "94" in got.candidates[0].why and "60" in got.candidates[0].why


def test_a_customer_who_never_visited_is_not_absent():
    assert audience("win_back", cust("a", last_days=0) | {"last_visit": 0}).count == 0


def test_loyalty_needs_both_the_visits_and_the_recency():
    many_but_old = cust("a", visits=9, last_days=400)
    few_but_recent = cust("b", visits=1, last_days=3)
    good = cust("c", visits=6, last_days=10)
    got = audience("reward_loyal", many_but_old, few_but_recent, good)
    assert [c.subject_ref for c in got.candidates] == ["c"]


def test_an_announcement_reaches_everyone_the_gate_allows():
    """Narrowing an announcement is the owner's job through a different goal, not a hidden
    filter here."""
    assert audience("announce", cust("a"), cust("b"), cust("c")).count == 3


def test_an_occasion_campaign_reaches_nobody_rather_than_everybody():
    """A campaign that reaches every customer regardless of the date is worse than one that
    reaches nobody, because it goes out under the shop's name claiming a day that is not theirs."""
    assert audience("occasion", cust("a"), cust("b")).count == 0
    # NOW is 2027-01-15 11:00 Riyadh (module docstring) — one year earlier, same date.
    assert audience("occasion", cust("a", created=NOW - 365 * DAY)).count == 1


# ── the two properties that matter more than the rules ─────────────────────────────────────────
def test_the_preview_count_excludes_everyone_the_gate_would_refuse():
    """A preview that promises 47 and delivers 31 teaches the owner our numbers are decoration."""
    async def gate(subject):
        return subject != "b"
    got = audience("announce", cust("a"), cust("b"), cust("c"), gate_check=gate)
    assert got.count == 2 and got.excluded == 1


def test_a_standing_campaign_never_reaches_the_same_person_twice():
    """The dedup is the run history, not a flag on the customer — a flag has to be cleared by
    something, and whatever clears it is the bug."""
    got = audience("announce", cust("a"), cust("b"), already_reached={"a"})
    assert [c.subject_ref for c in got.candidates] == ["b"]


def test_a_truncated_audience_says_so():
    """A truncation nobody is told about reads as 'everyone was reached', which is the most
    misleading thing a campaign screen can say."""
    many = [cust(f"s{i}") for i in range(DEFAULT_MAX_AUDIENCE + 10)]
    got = run(resolve(goal="announce", tenant="t1", now=NOW, customers=rows(*many)))
    assert got.truncated and got.count == DEFAULT_MAX_AUDIENCE


def test_a_row_with_no_subject_is_skipped_rather_than_crashing_the_run():
    got = audience("announce", {"subject_ref": ""}, cust("a"))
    assert got.count == 1


def test_the_same_function_serves_the_preview_and_the_send():
    """The only reliable way to keep two numbers equal is to have one implementation."""
    import inspect

    from app.core import audience as mod
    assert len([n for n in dir(mod) if n.startswith("resolve")]) == 1
    assert "gate_check" in inspect.signature(mod.resolve).parameters


# ── the owner's own window (2026-09-12) ──────────────────────────────────────────────────────────
def test_a_campaign_with_no_window_set_defaults_to_the_whole_day():
    c = Campaign(tenant="t1", goal="service_offer")
    assert c.window_start_hour == 0 and c.window_end_hour == 24 and c.window_weekdays == []


def test_validate_window_refuses_an_end_before_or_equal_to_the_start():
    assert validate_window(start_hour=10, end_hour=10, weekdays=None)
    assert validate_window(start_hour=14, end_hour=8, weekdays=None)


def test_validate_window_refuses_hours_outside_0_24():
    assert validate_window(start_hour=-1, end_hour=10, weekdays=None)
    assert validate_window(start_hour=8, end_hour=25, weekdays=None)


def test_validate_window_refuses_an_unknown_weekday():
    assert validate_window(start_hour=8, end_hour=20, weekdays=[7])


def test_validate_window_accepts_a_coherent_window():
    assert validate_window(start_hour=8, end_hour=20, weekdays=[4, 5]) == ""


def test_a_campaign_with_no_window_is_always_in_window():
    assert in_window(start_hour=0, end_hour=24, weekdays=None, now=NOW)


# ── «كافئ المخلصين»'s own audience thresholds (2026-09-13) ──────────────────────────────────────
def test_validate_loyalty_window_refuses_a_window_outside_7_to_365():
    assert validate_loyalty_window(window_days=6, min_visits=3)
    assert validate_loyalty_window(window_days=366, min_visits=3)


def test_validate_loyalty_window_refuses_min_visits_outside_1_to_50():
    assert validate_loyalty_window(window_days=90, min_visits=0)
    assert validate_loyalty_window(window_days=90, min_visits=51)


def test_validate_loyalty_window_accepts_the_defaults_and_the_full_range_edges():
    assert validate_loyalty_window(window_days=90, min_visits=3) == ""
    assert validate_loyalty_window(window_days=7, min_visits=1) == ""
    assert validate_loyalty_window(window_days=365, min_visits=50) == ""


def test_a_campaign_never_touching_the_thresholds_gets_todays_defaults():
    c = Campaign(tenant="t1", goal="reward_loyal")
    assert c.loyalty_window_days == 90 and c.loyalty_min_visits == 3


def test_in_window_checks_the_hour_in_riyadh_local_time():
    # NOW is 11:00 Riyadh.
    assert in_window(start_hour=8, end_hour=20, weekdays=None, now=NOW)
    assert not in_window(start_hour=12, end_hour=20, weekdays=None, now=NOW)
    assert not in_window(start_hour=0, end_hour=11, weekdays=None, now=NOW)


def test_in_window_checks_the_weekday_when_one_is_set():
    # NOW is a Friday (weekday 4).
    assert in_window(start_hour=0, end_hour=24, weekdays=[4], now=NOW)
    assert not in_window(start_hour=0, end_hour=24, weekdays=[0, 1, 2], now=NOW)
