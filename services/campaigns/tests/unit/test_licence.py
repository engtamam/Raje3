"""Has this shop bought campaigns — and what happens when we cannot ask.

THE DEFECT THESE TESTS CLOSE. `feature.campaigns` separates الأساسية from الذكية, and nothing in
the fleet checked it: this service had no billing settings, no client and no gate. A shop on the
cheapest plan pressed «أطلق الحملة» and it went out — every time, for as long as the product had
existed.
"""
from __future__ import annotations

import asyncio
import json
import urllib.error
from unittest.mock import patch

import pytest

from app.core.licence import (CANNOT_ASK, HttpLicence, KEY, LicenceError, NOT_INCLUDED,
                              NullLicence, build_licence)


def run(c):
    return asyncio.run(c)


class _Resp:
    def __init__(self, payload):
        self._p = json.dumps(payload).encode()

    def read(self):
        return self._p

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def client():
    return HttpLicence(billing_url="http://billing",
                       check_path="/internal/billing/entitlements/check", token="t")


def _answer(payload=None, raise_with=None):
    def _urlopen(req, timeout=0):
        if raise_with is not None:
            raise raise_with
        _answer.seen = req.full_url
        return _Resp(payload or {})
    return _urlopen


# ── the shop that bought it ────────────────────────────────────────────────────────────────────
def test_a_shop_that_bought_campaigns_may_launch():
    with patch("urllib.request.urlopen", _answer({"allowed": True})):
        assert run(client().allowed("t1")) is True


def test_the_question_asked_is_the_key_on_the_price_list():
    """A second spelling of the key is a feature enforced somewhere and free everywhere else."""
    with patch("urllib.request.urlopen", _answer({"allowed": True})):
        run(client().allowed("t1"))
    # urlencode percent-escapes the dot's neighbours, not the dot — so the key travels readably.
    assert "key=feature.campaigns" in _answer.seen and KEY == "feature.campaigns"
    assert "tenant=t1" in _answer.seen


# ── the shop that did not ──────────────────────────────────────────────────────────────────────
def test_a_shop_without_the_app_is_refused():
    with patch("urllib.request.urlopen", _answer({"allowed": False})):
        assert run(client().allowed("t1")) is False


def test_no_live_subscription_at_all_is_also_a_refusal():
    """billing answers NOT_ENTITLED with allowed=false — the same answer to the only question
    asked here."""
    with patch("urllib.request.urlopen", _answer({"allowed": False, "error": "NOT_ENTITLED"})):
        assert run(client().allowed("t1")) is False


def test_the_refusal_carries_a_sentence_an_owner_can_act_on():
    with patch("urllib.request.urlopen", _answer({"allowed": False})):
        with pytest.raises(LicenceError) as exc:
            run(client().require("t1"))
    assert str(exc.value) == NOT_INCLUDED
    # And the action it names is a purchase, not a support ticket.
    assert "الباقات" in NOT_INCLUDED


# ── the failure modes, which are the whole point ───────────────────────────────────────────────
def test_it_fails_CLOSED_when_billing_cannot_be_reached():
    """Showing a paid surface to somebody who has not bought it cannot be taken back; a refusal
    during an outage fixes itself. The opposite choice is right for the message meter, where the
    failure would silence the product itself."""
    down = urllib.error.URLError("connection refused")
    with patch("urllib.request.urlopen", _answer(raise_with=down)):
        assert run(client().allowed("t1")) is False


def test_a_billing_error_is_a_refusal_not_a_pass():
    boom = urllib.error.HTTPError("u", 500, "boom", None, None)
    with patch("urllib.request.urlopen", _answer(raise_with=boom)):
        assert run(client().allowed("t1")) is False


def test_a_malformed_answer_is_a_refusal():
    """`{}` has no `allowed`, and a missing field must never read as yes."""
    with patch("urllib.request.urlopen", _answer({})):
        assert run(client().allowed("t1")) is False


def test_an_empty_tenant_never_reaches_billing():
    """A token with no establishment on it is not a shop, and asking would be asking about
    everybody at once."""
    called = {"n": 0}

    def _urlopen(req, timeout=0):
        called["n"] += 1
        return _Resp({"allowed": True})

    with patch("urllib.request.urlopen", _urlopen):
        assert run(client().allowed("")) is False
    assert called["n"] == 0


# ── how it is built, and the two sentences ─────────────────────────────────────────────────────
def test_without_billing_configured_it_allows_and_the_boot_guard_refuses_that_in_production():
    class S:
        BILLING_SERVICE_URL = ""
        BILLING_CHECK_PATH = "/internal/billing/entitlements/check"

    licence = build_licence(S())
    assert licence.driver == "null"
    assert run(licence.allowed("t1")) is True


def test_configured_billing_gives_the_http_client():
    class S:
        BILLING_SERVICE_URL = "http://billing-service:8000"
        BILLING_CHECK_PATH = "/internal/billing/entitlements/check"
        INTERNAL_SERVICE_TOKEN = "t"
        PEER_TIMEOUT_SECONDS = 8

    assert build_licence(S()).driver == "http"


def test_the_two_refusals_are_different_sentences():
    """«لم تشترِ» and «تعذّر السؤال» are different facts, and telling a paying shop the first one
    is worse than telling it to try again."""
    assert NOT_INCLUDED != CANNOT_ASK
