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


# ── `paid` also covers a plan whose OWN price is 0 (api/v1/subscription.py computes
# `paid = bool(payment_token) or price_minor == 0` at the call site) ───────────────────────────
def test_a_free_plan_needs_no_payment_token():
    """جهات الاتصال (plans.json, amount: 0) — same shape as the trial exemption just above,
    reached a different way: the call site passes `paid=True` when the resolved price is 0."""
    assert may_subscribe(connected=True, trial_days=0, paid=True).allowed is True


def test_a_paid_plan_with_no_token_is_still_refused():
    """REGRESSION CHECK. `paid=False` — an ordinary priced plan with no token and no free-plan
    override — refuses exactly as it always has."""
    d = may_subscribe(connected=True, trial_days=0, paid=False)
    assert d.allowed is False
    assert "لم يكتمل الدفع" in d.reason


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


def test_the_word_the_price_list_mandates_is_a_grant_not_a_dropped_key() -> None:
    """ج-4 · the writer says `unlimited`, and this reader could only read -1.

    `deploy/seed/plans.json` does not merely prefer the word — it spends a paragraph forbidding the
    number: «`unlimited` RATHER THAN -1. billing merges its own sentinel by beating every
    arithmetic; -1 is just a number to it, and two of them summed to -2 — which refuses every
    send.»

    And `granted_keys` did `int(limit)` inside a `try`, with `continue` on failure. So a feature
    carrying the sanctioned word was not a grant and not an error either — it was simply absent
    from the set, and a shop that had paid for an app would not hold it.

    NO `feature.*` CARRIES THE WORD TODAY, which is exactly why this is worth pinning rather than
    reporting: the price list is DATA, edited and reseeded without a deploy, and the first plan to
    spell it the sanctioned way would be the incident.
    """
    from app.core.subscribe import granted_keys

    assert granted_keys({"feature.loyalty": {"limit": "unlimited"}}) == {"feature.loyalty"}
    # The case the file already handled, kept so the fix cannot quietly replace it.
    assert granted_keys({"feature.loyalty": {"limit": 1}}) == {"feature.loyalty"}
    # And 0 stays a DECLARED DENY: the base carries every app at 0 so no screen has to tell
    # «not bought» from «never heard of».
    assert granted_keys({"feature.loyalty": {"limit": 0}}) == set()


# ── list_trial_plans — signup's own way of finding every trial-carrying plan, no base needed ────
def _plans_client(response, status=200):
    from app.core.subscribe import HttpPlans

    client = HttpPlans(billing_url="http://billing:8000", plans_path="/internal/billing/plans",
                       subscribe_path="/internal/billing/subscriptions",
                       subscriptions_path="/internal/billing/subscriptions", token="t")
    client._request = lambda url, body=None: (status, response)
    return client


def test_list_trial_plans_reads_every_row_that_carries_a_trial():
    client = _plans_client({"plans": [
        {"id": "plan_visit", "trial_days": 30},
        {"id": "plan_bookings", "trial_days": 30},
        {"id": "plan_seats", "trial_days": 0},          # a capacity pack — never a trial
    ]})
    assert run(client.list_trial_plans()) == ["plan_visit", "plan_bookings"]


def test_list_trial_plans_is_empty_when_the_catalogue_cannot_be_read():
    assert run(_plans_client({}, status=503).list_trial_plans()) == []


def test_list_trial_plans_is_empty_when_the_catalogue_cannot_be_read():
    assert run(_plans_client({}, status=503).list_trial_plans()) == []
