"""The one rule our subscribe path exists to enforce."""
from __future__ import annotations

import asyncio

from app.core.subscribe import Decision, NullConnections, may_subscribe


def run(c):
    return asyncio.run(c)


# ── the rule ───────────────────────────────────────────────────────────────────────────────────
def test_paying_no_longer_waits_on_the_connection():
    """THE RULE WAS THE OTHER WAY ROUND. It sent a man who had decided to buy off to do a
    ten-minute errand with Meta at the moment his intent was highest — and the ones who did not
    come back were lost to the queue we put in front of the till, not to the product. Paying is
    itself the strongest reason to finish connecting."""
    assert may_subscribe(connected=False, trial_days=0).allowed


def test_a_paid_plan_with_a_connection_goes_through():
    assert may_subscribe(connected=True, trial_days=0).allowed


def test_the_trial_needs_nothing():
    """This is what makes the rule fair rather than a wall. The trial is for TRYING — the field
    screen, the customers, the points and the indicators all work without WhatsApp, and gating the
    evaluation on a step whose purpose is only visible afterwards is how an evaluation ends."""
    assert may_subscribe(connected=False, trial_days=14).allowed


def test_it_says_what_is_left_and_how_long_it_takes():
    """A SILENT YES WOULD BE THE REAL SALE OF SOMETHING UNDELIVERABLE. He may pay unconnected, but
    he must not learn it from the absence of messages a week later — so the success carries the
    one sentence naming the remaining step and its length."""
    d = may_subscribe(connected=False, trial_days=0)
    assert "ربط" in d.notice and "دقائق" in d.notice


def test_the_notice_says_what_already_works():
    """Otherwise it reads as "you bought nothing yet", which is false: visits, customers, points
    and indicators all work from the first minute."""
    assert "الزيارات" in may_subscribe(connected=False, trial_days=0).notice


def test_a_connected_shop_is_told_nothing():
    """A notice with nothing owed is noise, and noise is what teaches people to skip notices."""
    assert may_subscribe(connected=True, trial_days=0).notice == ""


def test_the_refusal_never_mentions_verification():
    """CONNECTION, NOT VERIFICATION, and confusing them turns a ten-minute step into an indefinite
    one: business verification takes days, is not required to send at all, and only raises the
    ceiling. Gating payment on it would hold a shop behind a queue at Meta."""
    d = may_subscribe(connected=False, trial_days=0)
    assert "توثيق" not in d.notice


# ── the default when we cannot tell ────────────────────────────────────────────────────────────
def test_unknown_reads_as_not_connected():
    """It no longer blocks a payment — it decides whether the owner is TOLD to connect. Being
    wrong now costs him one notice he did not need, which is the cheap direction."""
    assert run(NullConnections().connected("shop")) is False


def test_the_decision_is_pure_and_readable():
    """The rule can be read and tested without a cluster. Everything around it is plumbing."""
    assert isinstance(may_subscribe(connected=True, trial_days=0), Decision)
