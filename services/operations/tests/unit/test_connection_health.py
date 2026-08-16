"""Detecting a connection that ended somewhere we cannot see.

THE FAILURE THIS CLOSES. An owner removes our app in his Business Manager, or Meta disables the
number. Nothing tells us: the row stays `connected`, «حسابي» keeps saying مربوط, and every message
is attempted against credentials that no longer exist. He finds out from a customer.

AND THE FAILURE THIS MUST NOT INTRODUCE, which is the harder half. A sweep that treats «could not
ask» as «disconnected» stops a healthy shop's reminders on a network blip and sends its owner
through the whole connect journey for nothing. So only a DEFINITE answer may flip a row.
"""
from __future__ import annotations

import asyncio

from app.core import connect

CONNECTIONS = connect.CONNECTIONS


def run(c):
    return asyncio.run(c)


class Store:
    def __init__(self, rows=None):
        self.rows = dict(rows or {})

    async def put(self, coll, key, row):
        self.rows[key] = row
        return row

    async def get(self, coll, key):
        return self.rows.get(key)

    async def find(self, coll, where, **kw):
        return [r for r in self.rows.values()
                if all(r.get(k) == v for k, v in where.items())], None


class Meta:
    """Answers keyed by sending identity, so a branch's number is distinguishable from the shop's."""

    def __init__(self, answers, *, configured=True):
        self.answers, self.asked, self._configured = answers, [], configured

    @property
    def configured(self):
        return self._configured

    async def status(self, tenant, phone_number_id=""):
        self.asked.append((tenant, phone_number_id))
        return self.answers.get(tenant, {"ok": True})


def row(tenant, *, state=connect.STATE_CONNECTED, branch="", pn="pn_1"):
    return connect.Attempt(tenant=tenant, state=state, branch_id=branch,
                           phone_number_id=pn, waba_id="waba_1").to_dict()


def store_with(*attempts):
    return Store({a["id"]: a for a in attempts})


def test_a_revoked_connection_is_stopped_and_says_what_to_do():
    """THE DEFECT ITSELF."""
    s = store_with(row("tnt_gone"))
    out = run(connect.health_sweep(connect.ConnectionStore(s),
                                   Meta({"tnt_gone": {"ok": False, "reason": "NOT_CONNECTED"}})))

    assert out["stopped"] == 1 and out["checked"] == 1
    saved = s.rows["tnt_gone"]
    assert saved["state"] == connect.STATE_STOPPED
    assert "افتح الربط مرة أخرى" in saved["detail"], "a state with no next step is not an answer"


def test_an_unreadable_answer_changes_nothing():
    """THE FAILURE THE FIX COULD HAVE INTRODUCED. An unreachable Graph is not a disconnection, and
    treating it as one silences a shop that is working perfectly."""
    for unreadable in ({"ok": False, "reason": "UNREACHABLE: timed out"},
                       {"ok": False, "reason": "META_ERROR:transient"},
                       {}):
        s = store_with(row("tnt_ok"))
        out = run(connect.health_sweep(connect.ConnectionStore(s), Meta({"tnt_ok": unreadable})))

        assert out["stopped"] == 0, unreadable
        assert out["unreadable"] == 1, unreadable
        assert s.rows["tnt_ok"]["state"] == connect.STATE_CONNECTED, unreadable


def test_a_healthy_number_is_left_exactly_as_it_was():
    s = store_with(row("tnt_live"))
    before = dict(s.rows["tnt_live"])
    out = run(connect.health_sweep(connect.ConnectionStore(s),
                                   Meta({"tnt_live": {"ok": True, "quality_rating": "GREEN"}})))

    assert (out["checked"], out["stopped"], out["unreadable"]) == (1, 0, 0)
    assert s.rows["tnt_live"] == before


def test_one_branch_losing_access_does_not_stop_the_others():
    """A chain loses access one number at a time. The sweep asks under the SENDING IDENTITY — the
    same key the credentials were sealed against — or it condemns numbers it never asked about."""
    s = store_with(row("tnt_ch", branch="brn_jed", pn="pn_jed"),
                   row("tnt_ch", branch="brn_ryd", pn="pn_ryd"))
    meta = Meta({"tnt_ch:brn_jed": {"ok": False, "reason": "NOT_CONNECTED"}})

    out = run(connect.health_sweep(connect.ConnectionStore(s), meta))

    assert out["stopped"] == 1 and out["stopped_keys"] == ["tnt_ch|brn_jed"]
    assert s.rows["tnt_ch|brn_jed"]["state"] == connect.STATE_STOPPED
    assert s.rows["tnt_ch|brn_ryd"]["state"] == connect.STATE_CONNECTED
    assert ("tnt_ch:brn_ryd", "pn_ryd") in meta.asked, "each number asked about under its own identity"


def test_the_unconfirmed_connection_is_swept_too():
    """`finished_unconfirmed` means Meta created the account and we did not hear the code — the
    state we are LEAST sure of, and therefore the last one a health sweep should skip."""
    s = store_with(row("tnt_unc", state=connect.STATE_FINISHED_UNCONFIRMED))
    out = run(connect.health_sweep(connect.ConnectionStore(s),
                                   Meta({"tnt_unc": {"ok": False, "reason": "NOT_CONNECTED"}})))

    assert out["checked"] == 1 and out["stopped"] == 1


def test_a_stopped_connection_is_not_asked_about_again():
    s = store_with(row("tnt_off", state=connect.STATE_STOPPED))
    meta = Meta({})
    assert run(connect.health_sweep(connect.ConnectionStore(s), meta))["checked"] == 0
    assert meta.asked == []


def test_an_unconfigured_deployment_says_so_instead_of_reporting_health():
    """Before Meta's credentials exist, this sweep can read nothing. Returning zeros with no reason
    would read as «the whole fleet is fine» — the silent-success shape this product keeps hitting."""
    s = store_with(row("tnt_x"))
    out = run(connect.health_sweep(connect.ConnectionStore(s), Meta({}, configured=False)))

    assert out["reason"] == "NOT_CONFIGURED"
    assert out["checked"] == 0
    assert s.rows["tnt_x"]["state"] == connect.STATE_CONNECTED


def test_the_owner_reads_that_access_ended_not_that_he_never_finished():
    """THE SENTENCE, which is the only part of this a shop ever sees.

    A stopped row used to fall through to «لم يكتمل الربط. افتح الربط مرة أخرى وأكمل الخطوات» —
    true for someone who closed the popup, and badly wrong for a shop that sent for a year and then
    had its access revoked. It sends him looking for a step he completed long ago.
    """
    s = store_with(row("tnt_said"))
    run(connect.health_sweep(connect.ConnectionStore(s),
                             Meta({"tnt_said": {"ok": False, "reason": "NOT_CONNECTED"}})))

    said = connect.sentence_for(run(connect.ConnectionStore(s).get("tnt_said")))
    assert "انقطع ربط واتساب" in said
    assert "أكمل الخطوات" not in said


def test_an_abandoned_journey_still_reads_as_an_abandoned_journey():
    """The other half: a cancel carries a `step`, and its own sentence must survive the fix above."""
    at = connect.Attempt(tenant="t", state=connect.STATE_STOPPED, step=connect.STEP_VERIFY,
                         detail="whatever")
    assert "رمز التحقق" in connect.sentence_for(at)


# --- د-6 · a connection that never completed is not a connection that was cut ------------------


def test_a_connection_that_never_completed_is_not_reported_as_cut():
    """د-6 · THE FALSE DIAGNOSIS THAT FOLLOWED THE FALSE PROMISE.

    A `finished_unconfirmed` row is the popup closing on Meta's last screen: the account exists and
    we never received the code — which lives thirty seconds, so the exchange never happened and no
    credentials were ever sealed. Meta therefore answers NOT_CONNECTED, truthfully, and the sweep
    wrote «انقطع ربط واتساب — لم يعد لدينا إذن الوصول».

    Nothing was cut. He never granted the access the sentence says he withdrew, so he goes looking
    through Business Manager for a permission that was never there — after being told to wait a few
    minutes for a check nobody performs.
    """
    s = store_with(row("tnt_half", state=connect.STATE_FINISHED_UNCONFIRMED))

    out = run(connect.health_sweep(connect.ConnectionStore(s),
                                   Meta({"tnt_half": {"ok": False, "reason": "NOT_CONNECTED"}})))

    assert out["stopped"] == 1, "the row must not stay live — nothing can send from it"
    said = next(iter(s.rows.values()))["detail"]
    assert said == connect.UNFINISHED_SENTENCE
    assert "انقطع" not in said, "nothing was cut — it never connected"
    assert "مرة أخرى" in said, "and the act that finishes it must be named"


def test_a_connection_that_worked_and_ended_still_says_it_was_cut():
    """The other half of the same rule: on a row that WAS connected, «no credentials» does mean the
    access ended, and softening that would send an owner waiting for a completion instead of
    re-granting a permission somebody removed."""
    s = store_with(row("tnt_was_live", state=connect.STATE_CONNECTED))

    run(connect.health_sweep(connect.ConnectionStore(s),
                             Meta({"tnt_was_live": {"ok": False, "reason": "NOT_CONNECTED"}})))

    assert next(iter(s.rows.values()))["detail"] == connect.DISCONNECTED_SENTENCE
