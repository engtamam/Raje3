"""Has this shop bought the bookings app — and what happens when we cannot ask.

Mirrors services/loyalty/tests/unit/test_licence.py exactly: same shape, `feature.bookings`
instead of `feature.loyalty`. See app/core/licence.py for the read/write asymmetry these tests
assert.
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
def test_a_shop_that_bought_bookings_may_grow_it():
    with patch("urllib.request.urlopen", _answer({"allowed": True})):
        assert run(client().allowed("t1")) is True


def test_the_question_asked_is_the_key_on_the_price_list():
    """A second spelling of the key is a feature enforced somewhere and free everywhere else."""
    with patch("urllib.request.urlopen", _answer({"allowed": True})):
        run(client().allowed("t1"))
    assert "key=feature.bookings" in _answer.seen and KEY == "feature.bookings"
    assert "tenant=t1" in _answer.seen


# ── the shop that did not ──────────────────────────────────────────────────────────────────────
def test_a_shop_without_the_app_is_refused():
    with patch("urllib.request.urlopen", _answer({"allowed": False})):
        assert run(client().allowed("t1")) is False


def test_no_live_subscription_at_all_is_also_a_refusal():
    with patch("urllib.request.urlopen", _answer({"allowed": False, "error": "NOT_ENTITLED"})):
        assert run(client().allowed("t1")) is False


def test_the_refusal_carries_a_sentence_an_owner_can_act_on():
    with patch("urllib.request.urlopen", _answer({"allowed": False})):
        with pytest.raises(LicenceError) as exc:
            run(client().require("t1"))
    assert str(exc.value) == NOT_INCLUDED
    assert "الباقات" in NOT_INCLUDED


# ── the failure modes, which are the whole point ───────────────────────────────────────────────
def test_it_fails_CLOSED_when_billing_cannot_be_reached():
    """It guards the growing half only, so a refusal during an outage costs the shop a booking it
    can retry — never an appointment a customer is standing at the counter holding."""
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
    assert NOT_INCLUDED != CANNOT_ASK
    assert isinstance(NullLicence().driver, str)


# ── the boot guard, which config.py's own test file does not know about yet ───────────────────
def test_production_without_billing_config_refuses_to_boot():
    from app.config import Settings

    s = Settings(ENV="production", INTERNAL_SERVICE_TOKEN="x" * 32, PII_SALT="x" * 32)
    with pytest.raises(ValueError, match="BILLING_SERVICE_URL"):
        s.assert_licence_config_ok()


def test_production_with_billing_config_boots_clean():
    from app.config import Settings

    s = Settings(ENV="production", INTERNAL_SERVICE_TOKEN="x" * 32, PII_SALT="x" * 32,
                BILLING_SERVICE_URL="http://billing-service:8000",
                BILLING_CHECK_PATH="/internal/billing/entitlements/check")
    s.assert_licence_config_ok()  # must not raise
