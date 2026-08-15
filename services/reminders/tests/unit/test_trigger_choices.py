"""The shop's own answers: does this trigger run, and in whose words."""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core import triggers as T
from app.core.trigger_choices import ChoiceStore


def run(c):
    return asyncio.run(c)


@pytest.fixture
def store():
    return ChoiceStore(MemoryDataStore())


def test_a_shop_that_has_chosen_nothing_still_sends():
    """The engine is what he bought. A product whose messages all arrive switched off does
    nothing on the day it is installed."""
    choices = run(ChoiceStore(MemoryDataStore()).load("t1"))
    assert all(choices.enabled(t.id) for t in T.TRIGGERS)


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
    run(store.set("t1", "service_due", on=False))
    run(store.set("t1", "service_due", template="shop_reminder_1"))
    c = run(store.load("t1"))
    assert c.enabled("service_due") is False
    assert c.template_name("service_due") == "shop_reminder_1"


def test_going_back_to_our_text_deletes_rather_than_storing_a_blank(store):
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


def test_an_unknown_trigger_is_refused_rather_than_stored(store):
    with pytest.raises(ValueError):
        run(store.set("t1", "no_such_trigger", on=True))


def test_the_screen_gets_the_catalogue_and_the_answers_together(store):
    run(store.set("t1", "after_visit", on=False))
    rows = run(store.load("t1")).public()
    assert len(rows) == len(T.TRIGGERS)
    off = next(r for r in rows if r["id"] == "after_visit")
    assert off["on"] is False and off["label"] and off["when"]
    # And never our vocabulary — he has no use for a class or a template type (§10.8.1.2).
    assert "cls" not in off and "template_type" not in off


# ── the row → trigger mapping the engine enforces the switch through ───────────────────────────
def test_a_ladder_rung_is_its_own_trigger_not_the_reminder_that_made_it():
    """They share a template type, and they are separate switches: an owner who wants reminders
    may not want to be reminded of the reminder."""
    assert T.for_row("reminder", "svc_service_reminder") == "service_due"
    assert T.for_row("ladder_1", "svc_service_reminder") == "no_response"
    assert T.for_row("ladder_2", "svc_service_reminder") == "no_response"


def test_a_row_we_cannot_attribute_keeps_sending():
    """A switch we cannot attribute must not silence a message the shop expects — and guessing a
    trigger would apply somebody else's switch to it."""
    assert T.for_row("something_new", "svc_service_reminder") == ""
