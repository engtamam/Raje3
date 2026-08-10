"""Embedded Signup: the states, and the one that looks like a cancellation and is not."""
from __future__ import annotations

import asyncio

from app.adapters.datastore.memory import MemoryDataStore
from app.core import connect


def run(c):
    return asyncio.run(c)


def test_stopping_early_is_a_cancellation():
    assert connect.classify_cancel(connect.STEP_BUSINESS) == connect.STATE_STOPPED
    assert connect.classify_cancel(connect.STEP_VERIFY) == connect.STATE_STOPPED


def test_closing_on_the_final_screen_is_NOT_a_cancellation():
    """Meta considers the signup done at that point — the account exists. Calling it a
    cancellation would send an owner hunting for a problem he does not have, and might make him
    run the whole journey again against an account that is already connected."""
    assert connect.classify_cancel(connect.STEP_PERMISSIONS) == connect.STATE_FINISHED_UNCONFIRMED
    assert connect.classify_cancel("permissions") == connect.STATE_FINISHED_UNCONFIRMED


def test_an_unknown_step_is_treated_as_stopping_rather_than_as_finishing():
    """The safe direction: telling someone who stopped that he finished loses the connection
    silently, while telling someone who finished that he stopped costs one repeated flow."""
    assert connect.classify_cancel("SOMETHING_META_ADDED_LATER") == connect.STATE_STOPPED
    assert connect.classify_cancel("") == connect.STATE_STOPPED


def test_every_step_gets_its_own_next_action():
    """A sentence per step, and each says what to DO. 'Connection failed' answers nothing."""
    seen = set()
    for step in (connect.STEP_BUSINESS, connect.STEP_PHONE_PICKER, connect.STEP_PROFILE,
                 connect.STEP_PHONE, connect.STEP_VERIFY):
        s = connect.sentence_for(connect.Attempt(tenant="t", state=connect.STATE_STOPPED, step=step))
        assert s and s != connect._DEFAULT_SENTENCE
        seen.add(s)
    assert len(seen) == 5, "two steps share a sentence — one of them is telling the owner the wrong thing"


def test_the_finished_sentence_neither_claims_success_nor_asks_him_to_repeat():
    s = connect.sentence_for(connect.Attempt(tenant="t", state=connect.STATE_FINISHED_UNCONFIRMED))
    assert "لا حاجة" in s


def test_meta_identifiers_never_reach_the_screen():
    """A WABA id on a screen is one more thing that gets pasted into a support chat, and the owner
    has no use for any of them."""
    a = connect.Attempt(tenant="t", state=connect.STATE_CONNECTED, waba_id="W1",
                        phone_number_id="P1", business_id="B1", detail="secret reason")
    pub = a.public()
    assert "W1" not in str(pub) and "P1" not in str(pub) and "B1" not in str(pub)
    assert "secret reason" not in str(pub)


def test_the_failure_reason_is_kept_even_though_it_is_not_shown():
    """Support needs to tell 'Meta rejected the code' from 'our app secret is wrong'; the owner
    needs neither, and one of them is about us."""
    store = connect.ConnectionStore(MemoryDataStore())
    run(store.record(connect.Attempt(tenant="t", state=connect.STATE_FAILED, detail="code expired")))
    assert run(store.get("t")).detail == "code expired"


def test_the_store_keeps_the_latest_attempt_not_a_history():
    store = connect.ConnectionStore(MemoryDataStore())
    run(store.record(connect.Attempt(tenant="t", state=connect.STATE_STOPPED,
                                     step=connect.STEP_PHONE)))
    run(store.record(connect.Attempt(tenant="t", state=connect.STATE_CONNECTED)))
    assert run(store.get("t")).state == connect.STATE_CONNECTED


def test_an_unconfigured_exchange_reports_failure_rather_than_success():
    """The failure that would otherwise have a shop recording visits all week and wondering where
    its messages went."""
    ok, why = run(connect.NullExchange().exchange(
        tenant="t", code="c", waba_id="w", phone_number_id="p"))
    assert ok is False and why


def test_no_establishment_has_ever_connected_by_default():
    assert run(connect.ConnectionStore(MemoryDataStore()).get("t")) is None
