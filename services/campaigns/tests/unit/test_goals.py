"""The five cards, and the lock that has to be visible to be a rule."""
from __future__ import annotations

import pytest

from app.core.goals import CARDS, DAY, cards, lock_after_send, resolve_goal

NOW = 1_800_000_000


def by_goal(items):
    return {c.goal: c for c in items}


# ── the cards ──────────────────────────────────────────────────────────────────────────────────
def test_every_card_says_what_it_does_in_the_owners_words():
    """'Standing campaign' is our word; theirs is 'bring back the ones who stopped coming'."""
    for c in cards(now=NOW):
        assert c.title and c.line and c.behaviour
        assert "standing" not in c.behaviour and "campaign" not in c.behaviour.lower()


def test_the_behaviour_is_a_sentence_not_a_type():
    got = by_goal(cards(now=NOW))
    assert got["win_back"].behaviour == "تعمل تلقائياً كل يوم"
    assert got["announce"].behaviour == "تُرسَل مرة واحدة"


def test_all_five_goals_have_a_card():
    assert set(by_goal(cards(now=NOW))) == set(CARDS)


# ── the lock ───────────────────────────────────────────────────────────────────────────────────
def test_a_locked_card_stays_visible_and_says_why():
    """A card that disappears reads as a fault and generates a support ticket; one that explains
    itself reads as a rule and generates nothing."""
    got = by_goal(cards(now=NOW, locks={"awareness": NOW + 23 * DAY}))["awareness"]
    assert not got.available and "متاح بعد" in got.unavailable_reason


def test_the_reason_carries_a_number_of_days_not_a_date():
    """'Available in 23 days' is arithmetic the owner does not have to do; a date is arithmetic
    they do."""
    got = by_goal(cards(now=NOW, locks={"awareness": NOW + 23 * DAY}))["awareness"]
    assert "23" in got.unavailable_reason


def test_a_lock_that_has_passed_frees_the_card():
    got = by_goal(cards(now=NOW, locks={"awareness": NOW - DAY}))["awareness"]
    assert got.available and not got.unavailable_reason


def test_a_partial_day_still_reads_as_at_least_one():
    got = by_goal(cards(now=NOW, locks={"awareness": NOW + 3600}))["awareness"]
    assert "1 يوم" in got.unavailable_reason


def test_only_awareness_locks_and_only_when_something_was_sent():
    """Locking after a run that reached nobody costs the owner a month for a send that never
    happened, and they would have no way to tell the difference."""
    assert lock_after_send("awareness", now=NOW, sent=3) == NOW + 30 * DAY
    assert lock_after_send("awareness", now=NOW, sent=0) == 0
    assert lock_after_send("announce", now=NOW, sent=3) == 0


# ── a template type the tenant has not enabled ─────────────────────────────────────────────────
def test_a_disabled_type_is_shown_with_the_fix_rather_than_hidden():
    """Hiding it means an owner who wants it cannot find out it exists — and sending them to the
    settings screen and back is where people stop, because they lost their place."""
    got = by_goal(cards(now=NOW, enabled_types={"mkt_winback"}))
    assert got["win_back"].available
    assert got["announce"].needs_enabling and not got["announce"].available
    assert "اضغط للتفعيل" in got["announce"].unavailable_reason


def test_no_filter_means_everything_is_available():
    assert all(c.available for c in cards(now=NOW))


# ── one place for a new goal ───────────────────────────────────────────────────────────────────
def test_a_goal_resolves_to_everything_the_system_needs():
    """One place, so adding a goal is two rows — not a change in four files where the fourth is
    forgotten."""
    r = resolve_goal("win_back")
    assert r["template_type"] == "mkt_winback"
    assert r["cls"] == "marketing" and r["trigger"] == "standing"


def test_awareness_is_the_only_non_marketing_goal():
    classes = {resolve_goal(g)["cls"] for g in CARDS}
    assert classes == {"marketing", "awareness"}
    assert resolve_goal("awareness")["cls"] == "awareness"


def test_an_unknown_goal_is_refused_with_the_valid_ones_listed():
    with pytest.raises(ValueError) as exc:
        resolve_goal("send_everything")
    assert "win_back" in str(exc.value)
