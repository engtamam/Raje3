"""The one rule our subscribe path exists to enforce."""
from __future__ import annotations

import asyncio

from app.core.subscribe import Decision, NullConnections, may_subscribe


def run(c):
    return asyncio.run(c)


# ── the rule ───────────────────────────────────────────────────────────────────────────────────
def test_a_paid_plan_needs_a_connection():
    """A shop that pays and cannot send has bought nothing, and discovering that together a week
    later is the refund conversation nobody wins."""
    d = may_subscribe(connected=False, trial_days=0)
    assert not d.allowed


def test_a_paid_plan_with_a_connection_goes_through():
    assert may_subscribe(connected=True, trial_days=0).allowed


def test_the_trial_needs_nothing():
    """This is what makes the rule fair rather than a wall. The trial is for TRYING — the field
    screen, the customers, the points and the indicators all work without WhatsApp, and gating the
    evaluation on a step whose purpose is only visible afterwards is how an evaluation ends."""
    assert may_subscribe(connected=False, trial_days=14).allowed


def test_the_refusal_says_what_to_do_and_how_long_it_takes():
    """'Not allowed' answers nothing. Connecting is minutes, and saying so is the difference
    between a step and a wall."""
    d = may_subscribe(connected=False, trial_days=0)
    assert "اربط" in d.reason and "دقائق" in d.reason


def test_the_refusal_never_mentions_verification():
    """CONNECTION, NOT VERIFICATION, and confusing them turns a ten-minute step into an indefinite
    one: business verification takes days, is not required to send at all, and only raises the
    ceiling. Gating payment on it would hold a shop behind a queue at Meta."""
    d = may_subscribe(connected=False, trial_days=0)
    assert "توثيق" not in d.reason


# ── the default when we cannot tell ────────────────────────────────────────────────────────────
def test_unknown_reads_as_not_connected():
    """The one direction where being wrong costs a refund and a customer rather than a retry."""
    assert run(NullConnections().connected("shop")) is False


def test_the_decision_is_pure_and_readable():
    """The rule can be read and tested without a cluster. Everything around it is plumbing."""
    assert isinstance(may_subscribe(connected=True, trial_days=0), Decision)
