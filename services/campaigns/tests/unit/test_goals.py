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


# ── a template type that is not sendable yet ────────────────────────────────────────────────────
def test_a_blocked_type_is_shown_with_the_real_reason_rather_than_hidden():
    """Hiding it means an owner who wants it cannot find out it exists. The reason on the card is
    reminders' OWN sentence — never a guess, and never a promise that pressing does anything: an
    owner never sees the words «قالب» or «اعتماد» (Messages.tsx's own rule), so there is no switch
    here for him to press."""
    got = by_goal(cards(now=NOW, enabled_types={"mkt_winback"},
                        blocked_reasons={"mkt_announcement": "قوالب mkt_announcement ما زالت قيد "
                                                              "مراجعة واتساب — سترسل تلقائياً عند "
                                                              "اعتمادها."}))
    assert got["win_back"].available
    assert got["announce"].needs_enabling and not got["announce"].available
    assert "قيد مراجعة واتساب" in got["announce"].unavailable_reason
    # THE INTERNAL NAME NEVER REACHES HIM. It came in embedded in reminders' own sentence and must
    # be swapped for the card's own title before it is ever shown.
    assert "mkt_announcement" not in got["announce"].unavailable_reason
    assert "أعلن جديدك" in got["announce"].unavailable_reason


def test_a_blocked_type_with_no_known_reason_still_says_something_honest():
    """`blocked_reasons` can be silent for a type reminders never explained (an older peer, a
    partial response) — the card must still read as a real state, not a blank."""
    got = by_goal(cards(now=NOW, enabled_types={"mkt_winback"}))
    assert got["announce"].needs_enabling and not got["announce"].available
    assert got["announce"].unavailable_reason
    assert "اضغط للتفعيل" not in got["announce"].unavailable_reason


def test_no_filter_means_everything_is_available():
    assert all(c.available for c in cards(now=NOW))


# ── one place for a new goal ───────────────────────────────────────────────────────────────────
def test_a_goal_resolves_to_everything_the_system_needs():
    """One place, so adding a goal is two rows — not a change in four files where the fourth is
    forgotten."""
    r = resolve_goal("win_back")
    assert r["template_type"] == "mkt_winback"
    assert r["cls"] == "marketing" and r["trigger"] == "standing"


def test_a_goals_class_is_a_fact_about_the_message_not_a_choice():
    """THE CLASS IS NEVER THE OWNER'S, and this used to read «awareness is the only non-marketing
    goal» — which was a count, not a rule. A count breaks the day the product grows, and it did:
    a shop that discovers a defective batch has to be able to warn the people using it, and that
    message is neither an offer nor a tip. It reaches customers who opted OUT of offers, because
    it is not one — filing it as marketing would silence it for exactly the people most likely to
    be hurt.

    What must never change is that the class comes from the GOAL, so no campaign can dress itself
    as something it is not."""
    assert resolve_goal("awareness")["cls"] == "awareness"
    assert resolve_goal("safety")["cls"] == "warning"
    assert resolve_goal("win_back")["cls"] == "marketing"
    # AND EVERY GOAL HAS ONE, whatever it is. A goal with no class would be a message with no rule.
    assert all(resolve_goal(goal)["cls"] for goal in CARDS)


def test_an_unknown_goal_is_refused_with_the_valid_ones_listed():
    with pytest.raises(ValueError) as exc:
        resolve_goal("send_everything")
    assert "win_back" in str(exc.value)


def test_a_goal_names_the_blanks_its_message_actually_has():
    """ط-4 · The words are Meta's; the blanks are the only thing the shop decides.

    THE SCREEN USED TO DRAW ONE FREE TEXT BOX FOR EVERY GOAL, labelled «سطرك في الرسالة». For
    four of the six that was false: `mkt_offer` is «لك خصم {{3}} على {{4}}. ساري حتى {{5}}» — an
    amount, a service and a date, and nowhere at all for a sentence. The owner typed one, pressed
    launch, and the message went out without it. Nothing failed; he simply never saw his words
    again.

    So a goal now carries the blanks its own template declares — by KIND, in order — and the
    screen draws exactly those. Asserted on two goals whose shapes differ, because a list that is
    right for one and empty for the other is the failure this is about.
    """
    fills = {
        "mkt_offer": ["system", "system", "amount", "catalogue", "date"],
        "mkt_announcement": ["system", "system", "owner"],
    }
    by_goal = {c.goal: c for c in cards(now=0, fills_by_type=fills)}

    # THE TYPED ONES, AND NOT THE TWO WE FILL. `system` never becomes a question: his name and
    # his shop's name are ours to know, and asking for them would be asking him to type what we
    # already have.
    assert by_goal["service_offer"].blanks == ["amount", "catalogue", "date"]
    # AND THE ONE GOAL THAT GENUINELY HAS A FREE BLANK KEEPS IT. «جديد في {{2}}: {{3}}» has
    # nothing but his own words to put there — the fix is not to take the box away everywhere.
    assert by_goal["announce"].blanks == ["owner"]


def test_a_goal_whose_template_declares_nothing_asks_for_nothing():
    """AND THE ABSENCE IS NOT A GUESS EITHER.

    A template we could not resolve — never seeded, still in Meta's review, or a shop that has
    switched the type off — leaves the screen with no blanks to draw. Drawing a free box on that
    silence is exactly how the wrong one appeared for four goals in the first place: an empty
    declaration read as «he may write anything».
    """
    by_goal = {c.goal: c for c in cards(now=0, fills_by_type={})}
    assert by_goal["service_offer"].blanks == []
    assert by_goal["announce"].blanks == []


# ── package_offer (packages feature) ──────────────────────────────────────────────────────────

def test_package_offer_has_its_own_card():
    by_goal = {c.goal: c for c in cards(now=NOW)}
    assert "package_offer" in by_goal
    assert by_goal["package_offer"].title and by_goal["package_offer"].line


def test_package_offer_is_a_manual_offer_goal_same_as_service_offer():
    spec = resolve_goal("package_offer")
    assert spec["trigger"] == "manual"
    from app.core.models import offers_something
    assert offers_something("package_offer") is True


def test_package_offer_shares_the_mkt_offer_template_and_marketing_class():
    spec = resolve_goal("package_offer")
    assert spec["template_type"] == "mkt_offer"
    assert spec["cls"] == "marketing"


def test_package_offer_reuses_the_catalogue_blank_kind():
    """No new blank kind was invented — a package fills the SAME 'catalogue' slot a service
    would, since both are simply 'what he sells'."""
    by_goal = {c.goal: c for c in cards(now=NOW, fills_by_type={"mkt_offer": ["amount", "catalogue", "date"]})}
    assert by_goal["package_offer"].blanks == ["amount", "catalogue", "date"]
