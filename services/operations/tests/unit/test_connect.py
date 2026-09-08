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


def test_the_finished_sentence_does_not_promise_a_check_nobody_performs():
    """د-6 · THIS TEST USED TO ASSERT THE DEFECT.

    It required «لا حاجة لإعادة العملية» — the sentence that told an owner to wait while we
    finished the connection. Nothing finishes it: the exchange needs the code from the popup,
    the code lives thirty seconds, and no path anywhere completes it later. He waited for
    minutes that never came, and then the health sweep found no credentials and told him his
    connection had been CUT.

    The honest sentence names what happened and what finishes it — pressing the button again,
    which does not create a second account.
    """
    s = connect.sentence_for(connect.Attempt(tenant="t", state=connect.STATE_FINISHED_UNCONFIRMED))

    assert "لا حاجة" not in s, "a promise nobody keeps"
    assert "دقائق" not in s, "nothing is checking, so no waiting time may be quoted"
    assert "مرة أخرى" in s, "the one act that finishes it must be in the sentence"
    assert "حساب جديد" in s, "and the fear that stops him pressing it must be answered"


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


# ── the sweep's work list ──────────────────────────────────────────────────────────────────────
def _store_with(states):
    st = MemoryDataStore()
    store = connect.ConnectionStore(st)
    for i, state in enumerate(states):
        run(store.record(connect.Attempt(tenant=f"t{i}", state=state)))
    return store


def test_the_sweep_reads_both_live_states():
    """`finished_unconfirmed` is the shop we are LEAST sure of — the popup closed on Meta's final
    screen, so the account exists and we never heard the code. A sweep that read only `connected`
    would skip exactly those."""
    store = _store_with([connect.STATE_CONNECTED, connect.STATE_FINISHED_UNCONFIRMED,
                         connect.STATE_STOPPED, connect.STATE_FAILED])
    assert sorted(run(store.live_tenants())) == ["t0", "t1"]


def test_no_connections_is_an_empty_list_not_an_error():
    assert run(connect.ConnectionStore(MemoryDataStore()).live_tenants()) == []


# ── the misconfiguration that killed the connect request ───────────────────────────────────────
class _S:
    WHATSAPP_ONBOARDING_DRIVER = "http"
    WHATSAPP_ONBOARDING_PATH = "/internal/whatsapp/embedded-signup"
    NOTIFICATION_SERVICE_URL = ""
    INTERNAL_SERVICE_TOKEN = "t"
    PEER_TIMEOUT_SECONDS = 8


def test_driver_http_with_no_peer_url_falls_back_instead_of_building_a_relative_url():
    """`"" + "/internal/…"` is a relative URL, and urllib raises ValueError building the Request —
    outside the exchange's own try, so the owner's connect request 500s and Meta's thirty-second
    code dies with it. The deployment shipped exactly this state."""
    assert connect.build_exchange(_S()).configured is False

    _S.NOTIFICATION_SERVICE_URL = "http://notification-service:8000"
    assert connect.build_exchange(_S()).configured is True


# ── an outage of OURS must not be read as «try again» (هـ-5) ──────────────────────────────────
def test_an_unwired_exchange_tells_the_owner_the_fault_is_ours():
    """He completed every screen Meta showed him. Told «حاول مرة أخرى» he repeats the whole
    journey, fails identically, and goes looking through his Facebook account for a fault that is
    on our side of the wire — while the register route on the SAME journey says «عُطلٌ عندنا»."""
    _, why = run(connect.NullExchange().exchange(
        tenant="t", code="c", waba_id="w", phone_number_id="p"))
    said = connect.sentence_for(connect.Attempt(tenant="t", state=connect.STATE_FAILED,
                                                detail=why))
    assert "عندنا" in said
    assert "حاول مرة أخرى" not in said


def test_an_unreachable_peer_says_it_is_ours_and_still_asks_him_to_retry():
    """The other half. Unreachable is transient, so the retry IS the right advice — but he must
    know it is not his account that failed, or he spends the wait editing settings that are fine."""
    said = connect.sentence_for(connect.Attempt(
        tenant="t", state=connect.STATE_FAILED,
        detail=f"{connect.EXCHANGE_UNREACHABLE}: connection refused"))
    assert "عندنا" in said
    assert "أعد المحاولة" in said


def test_a_code_meta_refused_is_still_his_to_retry():
    """A rejection from Meta is not ours, and blaming ourselves for it would leave him waiting for
    a fix nobody is making. Only the two named reasons change the sentence."""
    said = connect.sentence_for(connect.Attempt(tenant="t", state=connect.STATE_FAILED,
                                                detail="400"))
    assert "عندنا" not in said
    assert "حاول مرة أخرى" in said


def test_the_driver_may_not_be_switched_on_with_nowhere_to_send_in_production():
    """`build_exchange` falls back to the null driver, which is right — and silent, which is how a
    deployment served traffic looking configured while refusing every connection."""
    import pytest

    from app.config import Settings

    s = Settings(ENV="production", WHATSAPP_ONBOARDING_DRIVER="http",
                 NOTIFICATION_SERVICE_URL="", INTERNAL_SERVICE_TOKEN="x" * 40)
    with pytest.raises(ValueError, match="NOTIFICATION_SERVICE_URL"):
        s.assert_onboarding_config_ok()


# ── GET /whatsapp/config's own core: what the console needs to open the popup ─────────────────
class _NoUrl:
    NOTIFICATION_SERVICE_URL = ""
    WHATSAPP_META_CONFIG_PATH = "/internal/whatsapp/config"
    INTERNAL_SERVICE_TOKEN = "t"
    PEER_TIMEOUT_SECONDS = 8


def test_no_notification_service_url_falls_back_to_the_null_config():
    """Same reasoning as `build_exchange` right above it — a relative URL would raise building the
    request, outside any try, and the console's popup button would break rather than stay
    honestly disabled."""
    assert isinstance(connect.build_meta_config(_NoUrl()), connect.NullMetaConfig)


def test_a_notification_service_url_builds_the_http_config_reader():
    class _S(_NoUrl):
        NOTIFICATION_SERVICE_URL = "http://notification-service:8000"
    assert isinstance(connect.build_meta_config(_S()), connect.HttpMetaConfig)


def test_the_null_config_answers_not_configured_never_a_broken_shape():
    out = run(connect.NullMetaConfig().read())
    assert out == {"configured": False}


def test_an_unreachable_peer_reads_as_not_configured_never_a_raised_error():
    """The exact case the docstring names: a network fault must collapse into the SAME
    `configured: false` the console already renders as its one honest sentence — never a raw
    exception reaching the route, never a distinct error shape the console would have to learn."""
    reader = connect.HttpMetaConfig(base_url="http://unreachable.invalid:1", path="/x",
                                    token="t", timeout=1)
    out = run(reader.read())
    assert out == {"configured": False}
