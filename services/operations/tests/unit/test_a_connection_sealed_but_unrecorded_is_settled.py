"""ز-12 — the credentials were in the vault and every screen said «غير مربوط».

The exchange is the point of no return: it spends Meta's code — thirty seconds of life, single use
— and hands the platform a token to seal. Our own row was written AFTER it, so a crash in between
left nothing here at all:

    seal succeeds at the platform  ->  pod dies  ->  no row, no screen, no way back

The shop was connected and could not be told so. The code was gone, so pressing the button again
could not finish what had already succeeded, and the owner's only route was a support conversation
about a connection that had worked.

The repair is not cleverness, it is ORDER: write the question down before asking it, and let the
hourly health pass read the answer off the only party that knows.
"""
from __future__ import annotations

import asyncio

from app.core.connect import (STATE_CONNECTED, STATE_EXCHANGING, STATE_FINISHED_UNCONFIRMED,
                              STATE_STOPPED, Attempt, health_sweep, sentence_for)

TENANT = "shop"


def run(c):
    return asyncio.run(c)


class _Store:
    def __init__(self, attempts: list[Attempt]):
        self.attempts = attempts

    async def live_connections(self, *, limit: int = 500):
        return [a for a in self.attempts
                if a.state in (STATE_CONNECTED, STATE_FINISHED_UNCONFIRMED, STATE_EXCHANGING)]

    async def record(self, attempt):
        return attempt


class _Registration:
    """The platform, which is the only party that knows whether the seal landed."""

    configured = True

    def __init__(self, answer: dict):
        self.answer = answer
        self.asked: list[str] = []

    async def status(self, who: str, phone_number_id: str = "") -> dict:
        self.asked.append(who)
        return self.answer


def _mid_exchange() -> Attempt:
    return Attempt(tenant=TENANT, state=STATE_EXCHANGING, waba_id="wa_1",
                   phone_number_id="pn_1", business_id="bz_1")


def test_a_seal_that_landed_becomes_a_connection():
    """THE DEFECT. The credentials exist; only our write was lost. Nobody should have to redo a
    journey whose one-use code is already spent."""
    attempt = _mid_exchange()
    store = _Store([attempt])

    out = run(health_sweep(store, _Registration({"ok": True})))

    assert attempt.state == STATE_CONNECTED
    assert out["settled"] == 1 and out["stopped"] == 0


def test_a_seal_that_never_landed_is_not_called_a_disconnection():
    """«انقطع ربط واتساب» announces the end of something that never began — and sends an owner
    looking for a permission he never granted."""
    attempt = _mid_exchange()
    store = _Store([attempt])

    out = run(health_sweep(store, _Registration({"ok": False, "reason": "NOT_CONNECTED"})))

    assert attempt.state == STATE_FINISHED_UNCONFIRMED, "the honest state: press the button again"
    assert attempt.state != STATE_STOPPED
    assert out["settled"] == 1 and out["stopped"] == 0


def test_an_answer_we_could_not_read_changes_nothing():
    """A network blip must not decide a connection either way. It stays the question it was."""
    attempt = _mid_exchange()
    store = _Store([attempt])

    out = run(health_sweep(store, _Registration({"ok": False, "reason": "TIMEOUT"})))

    assert attempt.state == STATE_EXCHANGING
    assert out["unreadable"] == 1 and out["settled"] == 0


def test_a_real_disconnection_is_still_a_disconnection():
    """The other direction, which a careless fix breaks: a connected row whose access ended must
    still be stopped, and must not be quietly «settled»."""
    attempt = Attempt(tenant=TENANT, state=STATE_CONNECTED, waba_id="wa_1",
                      phone_number_id="pn_1")
    store = _Store([attempt])

    out = run(health_sweep(store, _Registration({"ok": False, "reason": "NOT_CONNECTED"})))

    assert attempt.state == STATE_STOPPED
    assert out["stopped"] == 1 and out["settled"] == 0


def test_the_owner_is_told_neither_connected_nor_cancelled():
    """He is owed the truth for the one minute we genuinely do not know it."""
    line = sentence_for(_mid_exchange())

    assert "جارٍ إتمام الربط" in line
    assert "جاهز للإرسال" not in line, "claiming a connection we have not confirmed is the defect"


def test_the_real_work_list_includes_the_rows_mid_exchange():
    """THE FAKE STORE ABOVE CANNOT PROVE THIS, and a first attempt at this file thought it could.

    Its `live_connections` filtered by the same three states the sweep cares about, so removing
    `exchanging` from the REAL store's query changed nothing and every test still passed — the
    check was reading its own answer back. This one asks `ConnectionStore` itself.
    """
    from app.core.connect import ConnectionStore

    class _Datastore:
        def __init__(self):
            self.asked: list[str] = []

        async def find(self, collection, where, **kw):
            self.asked.append(str(where.get("state") or ""))
            return [], None

    ds = _Datastore()
    run(ConnectionStore(ds).live_connections())

    assert STATE_EXCHANGING in ds.asked, "a row mid-exchange would never be settled by anything"
    assert STATE_CONNECTED in ds.asked and STATE_FINISHED_UNCONFIRMED in ds.asked


def test_the_branch_number_is_asked_about_under_its_own_identity():
    """Credentials are sealed against the sending identity; asking under the bare tenant would ask
    about a different number and settle this one on somebody else's answer."""
    attempt = _mid_exchange()
    attempt.branch_id = "br_jeddah"
    reg = _Registration({"ok": True})

    run(health_sweep(_Store([attempt]), reg))

    assert reg.asked and reg.asked[0] != TENANT and TENANT in reg.asked[0]
