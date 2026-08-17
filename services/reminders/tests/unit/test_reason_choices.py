"""The shop's own answers: does this reason run, and in whose words."""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core import reasons as T
from app.core.reason_choices import ChoiceStore


def run(c):
    return asyncio.run(c)


@pytest.fixture
def store():
    return ChoiceStore(MemoryDataStore())


def _own(store, *, name: str, reason_id: str, status: str = "approved"):
    """Give the shop a template it actually owns, so a test points at something real.

    THE TESTS USED TO POINT AT A NAME NOTHING HAD WRITTEN, and passed — which is how the defect
    survived: a trigger could be aimed at any string, including a row drafted for a DIFFERENT
    reason, and the message then went out under a text written for another event. Pointing is a
    reference now, so a test creates what it refers to."""
    run(store._s.put("custom_templates", name, {
        "id": name, "tenant": "t1", "name": name, "reason_id": reason_id,
        "status": status, "body": "نص", "variables": ["1"], "fills": ["system"]}))


def test_a_shop_that_has_chosen_nothing_still_sends():
    """The engine is what he bought. A product whose messages all arrive switched off does
    nothing on the day it is installed."""
    choices = run(ChoiceStore(MemoryDataStore()).load("t1"))
    assert all(choices.enabled(t.id) for t in T.REASONS)


def test_switching_off_survives_because_presence_is_what_counts(store):
    """`{"on": False}` read with `or` becomes the default, and the owner who switched it off
    watches it keep sending. The settings tree learned this once already."""
    run(store.set("t1", "after_visit", on=False))
    assert run(store.load("t1")).enabled("after_visit") is False
    # AND ONLY THAT ONE. A switch that quietly reached its neighbours would be worse than none.
    assert run(store.load("t1")).enabled("service_due") is True


def test_switching_back_on_is_a_value_not_a_deletion(store):
    run(store.set("t1", "after_visit", on=False))
    run(store.set("t1", "after_visit", on=True))
    assert run(store.load("t1")).enabled("after_visit") is True


def test_the_text_and_the_switch_do_not_disturb_each_other(store):
    _own(store, name="shop_reminder_1", reason_id="service_due")
    run(store.set("t1", "service_due", on=False))
    run(store.set("t1", "service_due", template="shop_reminder_1"))
    c = run(store.load("t1"))
    assert c.enabled("service_due") is False
    assert c.template_name("service_due") == "shop_reminder_1"


def test_going_back_to_our_text_deletes_rather_than_storing_a_blank(store):
    _own(store, name="shop_reminder_1", reason_id="service_due")
    run(store.set("t1", "service_due", template="shop_reminder_1"))
    run(store.set("t1", "service_due", template=""))
    assert run(store.load("t1")).template_name("service_due") == ""


def test_the_privacy_code_cannot_be_switched_off_or_reworded(store):
    """A statutory right with a clock running — not a preference."""
    with pytest.raises(ValueError):
        run(store.set("t1", "privacy_code", on=False))
    with pytest.raises(ValueError):
        run(store.set("t1", "privacy_code", template="mine"))


def test_a_row_written_by_some_future_bug_cannot_silence_a_right(store):
    """Belt and braces: the write refuses, and the read refuses to honour it anyway."""
    c = run(store.load("t1"))
    c.rows["privacy_code"] = {"on": False}
    assert c.enabled("privacy_code") is True


def test_an_unknown_reason_is_refused_rather_than_stored(store):
    with pytest.raises(ValueError):
        run(store.set("t1", "no_such_reason", on=True))


def test_the_screen_gets_the_catalogue_and_the_answers_together(store):
    run(store.set("t1", "after_visit", on=False))
    rows = run(store.load("t1")).public()
    assert len(rows) == len(T.REASONS)
    off = next(r for r in rows if r["id"] == "after_visit")
    assert off["on"] is False and off["label"] and off["when"]
    # And never our vocabulary — he has no use for a class or a template type (§10.8.1.2).
    assert "template_type" not in off  # the class now travels (see test_reasons); the name does not and "template_type" not in off


# ── the row → reason mapping the engine enforces the switch through ───────────────────────────
def test_a_ladder_rung_is_its_own_reason_not_the_reminder_that_made_it():
    """They share a template type, and they are separate switches: an owner who wants reminders
    may not want to be reminded of the reminder."""
    assert T.for_row("reminder", "svc_service_reminder") == "service_due"
    assert T.for_row("ladder_1", "svc_service_reminder") == "no_response"
    assert T.for_row("ladder_2", "svc_service_reminder") == "no_response"


def test_a_row_we_cannot_attribute_keeps_sending():
    """A switch we cannot attribute must not silence a message the shop expects — and guessing a
    reason would apply somebody else's switch to it."""
    assert T.for_row("something_new", "svc_service_reminder") == ""


# ── the peer paths: loyalty, insights and every campaign come through send_one ─────────────────
def test_a_template_serving_two_reasons_is_silenced_only_when_both_are_off():
    """`mkt_loyalty_activation` answers both "his balance reaches a reward" and "he became a
    regular". Silencing on a guess would switch off a message the owner never touched."""
    assert T.candidates("campaign", "mkt_loyalty_activation") == (
        "reward_within_reach", "loyal_customer")


def test_a_peer_send_with_one_owner_is_attributed_exactly():
    assert T.candidates("campaign", "mkt_winback") == ("gone_missing",)
    assert T.candidates("", "per_weekly_digest") == ("weekly_digest",)


# ── a trigger may only point at a text that is his, for this reason, and approved ──────────────
def test_a_trigger_cannot_be_pointed_at_a_name_the_shop_does_not_own(store):
    """A typo'd or foreign name was stored raw. `choose()` accepts anything when the approved-set
    peer is unreadable, so the send was attempted against a name the shop's WhatsApp account does
    not hold — and failed where nobody was looking."""
    with pytest.raises(ValueError) as exc:
        run(store.set("t1", "service_due", template="nakheel_visit_redeemed_1"))
    assert "قوالب محلّك" in str(exc.value)
    assert run(store.load("t1")).template_name("service_due") == ""


def test_a_text_written_for_one_reason_cannot_answer_another(store):
    """THE DEFECT, exactly. A row drafted against `visit_redeemed` — whose blanks are reward,
    points and balance — could be made to answer `service_due`, whose only blank is the service.
    The message then goes out in the shop's name under a text written for a different event,
    filled from a different table. `custom_templates.check()` enforces the agreement, but at DRAFT
    time, against the reason the draft was written for; nothing re-asked when the pointing changed."""
    _own(store, name="shop_redeemed_1", reason_id="visit_redeemed")
    with pytest.raises(ValueError) as exc:
        run(store.set("t1", "service_due", template="shop_redeemed_1"))
    assert "كُتب لداعٍ آخر" in str(exc.value)


def test_a_text_meta_has_not_approved_cannot_be_wired_yet(store):
    """Wiring a pending text is a trigger that silently sends nothing until Meta answers — and the
    owner has no way to tell that from a trigger that is simply not firing."""
    _own(store, name="shop_pending_1", reason_id="service_due", status="pending")
    with pytest.raises(ValueError) as exc:
        run(store.set("t1", "service_due", template="shop_pending_1"))
    assert "لم تعتمده واتساب" in str(exc.value)
