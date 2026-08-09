"""When the trial notice fires — and the cases where it must not."""
from __future__ import annotations

import asyncio

from app.adapters.datastore.memory import MemoryDataStore
from app.core.trial_notice import (DAY, MILESTONES, TEMPLATE, TrialWatch, TrialWatchStore,
                                   due_milestone, text)

NOW = 1_800_000_000


def run(c):
    return asyncio.run(c)


# ── which milestone, if any ────────────────────────────────────────────────────────────────────
def test_nothing_is_sent_early_in_the_trial():
    assert due_milestone(NOW + 12 * DAY, NOW, []) is None


def test_the_seven_day_notice_fires_at_seven_days():
    assert due_milestone(NOW + 7 * DAY, NOW, []) == 7


def test_each_milestone_fires_once_and_only_once():
    """Not once per day — once. The cron runs hourly, is re-run after a failure, and may be
    deployed twice; none of that may produce a second message for the same milestone."""
    assert due_milestone(NOW + 6 * DAY, NOW, [7]) is None
    assert due_milestone(NOW + 3 * DAY, NOW, [7]) == 3
    assert due_milestone(NOW + 3 * DAY, NOW, [7, 3]) is None


def test_a_missed_milestone_is_skipped_rather_than_replayed():
    """If the cron was down for four days and he now has 2 left, he gets the 3-day notice and
    never the 7-day one. 'Your trial ends in 7 days' sent to somebody with 2 left is wrong in the
    direction that costs him the decision."""
    assert due_milestone(NOW + 2 * DAY, NOW, []) == 3
    # And having had it, he is owed NOTHING until the next milestone is actually reached. This
    # assertion said 1 at first, which was the test being wrong rather than the code: at two days
    # out the one-day milestone has not arrived. What it did catch was worse — the code answered
    # SEVEN, because 2 <= 7 and the 7-day notice had never been sent.
    assert due_milestone(NOW + 2 * DAY, NOW, [3]) is None
    assert due_milestone(NOW + 1 * DAY, NOW, [3]) == 1


def test_the_last_notice_is_a_day_out():
    assert due_milestone(NOW + 1 * DAY, NOW, [7, 3]) == 1


def test_nothing_is_sent_once_the_trial_is_over():
    """The stop speaks for itself. A warning about a thing that already happened reads as a system
    that has not noticed."""
    assert due_milestone(NOW - 1, NOW, []) is None
    assert due_milestone(NOW - 5 * DAY, NOW, [7]) is None


def test_the_milestones_fall_rather_than_repeat():
    """One notice a week out is read on a Tuesday and forgotten by the Sunday it matters; a daily
    countdown is noise, and noise is what gets silenced."""
    assert MILESTONES == (7, 3, 1)


# ── the text, which is what decides the message's class ────────────────────────────────────────
def test_the_text_carries_the_date_and_where_to_go():
    t = text(3, "مغسلة النخيل", "2026-08-20")
    assert "مغسلة النخيل" in t and "2026-08-20" in t and "لوحة التحكم" in t


def test_tomorrow_is_said_as_tomorrow():
    assert "غداً" in text(1, "م", "2026-08-20")


def test_the_text_names_no_price_and_no_plan():
    """THE TEMPLATE IS UNSILENCEABLE, so the text has to earn that. The thing that decides a
    message's class is its words: name a price and this becomes marketing by its text (§8.4.1),
    and then a notice about his own subscription falls behind quiet hours and a consent he never
    thought to give himself."""
    for days in MILESTONES:
        t = text(days, "مغسلة النخيل", "2026-08-20")
        for word in ("ريال", "148", "298", "598", "رقِّ", "خصم", "عرض"):
            assert word not in t


def test_it_uses_the_template_that_already_exists():
    assert TEMPLATE == "per_account_notice"


# ── the store ──────────────────────────────────────────────────────────────────────────────────
def store():
    return TrialWatchStore(MemoryDataStore())


def test_a_watch_is_recorded_and_read_back():
    s = store()
    run(s.put(TrialWatch(tenant="t1", trial_end=NOW + 7 * DAY, subscription_id="sub_1")))
    assert int(run(s.get("t1"))["trial_end"]) == NOW + 7 * DAY


def test_due_returns_only_the_tenants_owed_something():
    s = store()
    run(s.put(TrialWatch(tenant="early", trial_end=NOW + 12 * DAY)))
    run(s.put(TrialWatch(tenant="owed", trial_end=NOW + 3 * DAY)))
    run(s.put(TrialWatch(tenant="over", trial_end=NOW - DAY)))
    due = run(s.due(now=NOW))
    assert [(r["tenant"], m) for r, m in due] == [("owed", 3)]


def test_marking_sent_stops_it_recurring():
    s = store()
    run(s.put(TrialWatch(tenant="t1", trial_end=NOW + 3 * DAY)))
    assert run(s.due(now=NOW))
    run(s.mark_sent("t1", 3))
    assert not run(s.due(now=NOW))


def test_a_later_milestone_still_comes_after_an_earlier_one_was_sent():
    s = store()
    run(s.put(TrialWatch(tenant="t1", trial_end=NOW + 7 * DAY)))
    run(s.mark_sent("t1", 7))
    assert not run(s.due(now=NOW))
    assert [(r["tenant"], m) for r, m in run(s.due(now=NOW + 6 * DAY))] == [("t1", 1)]
