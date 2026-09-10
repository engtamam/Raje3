"""RenewalProvider — reads a due invoice through billing's internal tier, mints a platform.billing
bearer for the pay-link write (billing has no internal-tier twin for it, see the module's own
docstring), and answers the LoyaltyProvider-shaped balance/rewards/redeem contract.

`tenant` in every call below is what the Flow engine actually sends — always "_platform" (this is
one platform-owned Flow, never cloned per shop) — and is never read; `customer` carries the real
composite "{tenant}:{invoice_id}" the trigger seeded. Tests pass tenant="_platform" throughout to
match the real call shape, not as a formality."""
from __future__ import annotations

import asyncio
import json
from unittest.mock import patch

import pytest

from app.adapters.renewal_provider import (NullRenewalProvider, RenewalProvider,
                                           RenewalUnavailable, build_renewal_provider)


def run(c):
    return asyncio.run(c)


def _provider(**over):
    kwargs = dict(billing_url="http://billing", identity_url="http://identity",
                 internal_token="itok", client_id="cid", client_secret="csecret")
    kwargs.update(over)
    return RenewalProvider(**kwargs)


class _Resp:
    def __init__(self, payload, status=200):
        self._p = json.dumps(payload).encode()
        self.status = status

    def read(self):
        return self._p

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


_INVOICE = {"id": "inv_1", "tenant": "t1", "status": "open", "currency": "SAR",
           "total_minor": 15000, "settled_minor": 0, "amount_due_minor": 15000,
           "lines": [{"description": "تطبيق الحجوزات"}, {"description": "تطبيق التذكيرات"}]}


def test_balance_reads_amount_due_and_formats_it():
    p = _provider()
    with patch("urllib.request.urlopen", return_value=_Resp(_INVOICE)):
        out = run(p.balance(tenant="_platform", customer="t1:inv_1"))
    assert out == {"label": "المستحق: 150.00 SAR"}


def test_balance_reads_the_real_tenant_from_customer_not_the_engines_own_arg():
    p = _provider()
    seen_tenants = []

    def _urlopen(req, timeout=0):
        seen_tenants.append(req.full_url)
        return _Resp(_INVOICE)

    with patch("urllib.request.urlopen", _urlopen):
        run(p.balance(tenant="_platform", customer="t1:inv_1"))
    assert any("tenant=t1" in u for u in seen_tenants)
    assert not any("tenant=_platform" in u for u in seen_tenants)


def test_balance_on_a_missing_invoice_says_none_open():
    p = _provider()
    import urllib.error
    with patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError(
            "u", 404, "not found", {}, None)):
        out = run(p.balance(tenant="_platform", customer="t1:inv_1"))
    assert out == {"label": "لا توجد فاتورة تجديد مفتوحة حالياً"}


def test_balance_on_a_malformed_customer_never_calls_billing():
    p = _provider()
    with patch("urllib.request.urlopen") as m:
        out = run(p.balance(tenant="_platform", customer="not-composite"))
    assert out == {"label": "لا توجد فاتورة تجديد مفتوحة حالياً"}
    m.assert_not_called()


def test_rewards_offers_exactly_one_option_naming_the_apps():
    p = _provider()
    with patch("urllib.request.urlopen", return_value=_Resp(_INVOICE)):
        out = run(p.rewards(tenant="_platform", customer="t1:inv_1"))
    assert len(out) == 1
    assert out[0]["id"] == "t1:inv_1"
    assert "150.00" in out[0]["title"]
    assert "تطبيق الحجوزات" in out[0]["description"] and "تطبيق التذكيرات" in out[0]["description"]


def test_rewards_on_a_malformed_customer_is_empty_never_calls_billing():
    p = _provider()
    with patch("urllib.request.urlopen") as m:
        out = run(p.rewards(tenant="_platform", customer="bad"))
    assert out == []
    m.assert_not_called()


def test_redeem_refuses_a_reward_that_does_not_match_the_seeded_invoice():
    p = _provider()
    out = run(p.redeem(tenant="_platform", customer="t1:inv_1", reward="t1:inv_OTHER",
                       idempotency_key="k"))
    assert out["ok"] is False


def test_redeem_mints_a_token_then_creates_the_pay_link():
    p = _provider()
    calls: list[str] = []

    def _urlopen(req, timeout=0):
        calls.append(req.full_url)
        if "oauth/token" in req.full_url:
            return _Resp({"access_token": "bearer_1", "expires_in": 3600})
        assert req.headers.get("Authorization") == "Bearer bearer_1"
        assert "/invoices/inv_1/pay-link" in req.full_url    # the bare invoice id, tenant stripped
        return _Resp({"pay_url": "https://pay.raje3.sa/x", "checkout_url": "https://gw/x"})

    with patch("urllib.request.urlopen", _urlopen):
        out = run(p.redeem(tenant="_platform", customer="t1:inv_1", reward="t1:inv_1",
                          idempotency_key="k"))
    assert out == {"ok": True, "ref": "https://pay.raje3.sa/x"}
    assert any("oauth/token" in c for c in calls)
    assert any("pay-link" in c for c in calls)


def test_redeem_a_second_time_reuses_the_cached_token():
    p = _provider()
    mint_calls = {"n": 0}

    def _urlopen(req, timeout=0):
        if "oauth/token" in req.full_url:
            mint_calls["n"] += 1
            return _Resp({"access_token": "bearer_1", "expires_in": 3600})
        return _Resp({"pay_url": "https://pay.raje3.sa/x"})

    with patch("urllib.request.urlopen", _urlopen):
        run(p.redeem(tenant="_platform", customer="t1:inv_1", reward="t1:inv_1",
                    idempotency_key="k1"))
        run(p.redeem(tenant="_platform", customer="t1:inv_1", reward="t1:inv_1",
                    idempotency_key="k2"))
    assert mint_calls["n"] == 1


def test_redeem_an_already_settled_invoice_is_a_named_refusal():
    p = _provider()
    import urllib.error

    def _urlopen(req, timeout=0):
        if "oauth/token" in req.full_url:
            return _Resp({"access_token": "bearer_1", "expires_in": 3600})
        raise urllib.error.HTTPError("u", 409, "conflict", {}, None)

    with patch("urllib.request.urlopen", _urlopen):
        out = run(p.redeem(tenant="_platform", customer="t1:inv_1", reward="t1:inv_1",
                          idempotency_key="k"))
    assert out["ok"] is False
    assert "سُدِّدت" in out["reason"]


def test_redeem_on_a_malformed_customer_never_calls_billing():
    p = _provider()
    with patch("urllib.request.urlopen") as m:
        out = run(p.redeem(tenant="_platform", customer="bad", reward="bad",
                          idempotency_key="k"))
    assert out["ok"] is False
    m.assert_not_called()


def test_unreachable_billing_raises_renewal_unavailable_never_a_fake_answer():
    import urllib.error

    p = _provider()
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("down")):
        with pytest.raises(RenewalUnavailable):
            run(p.balance(tenant="_platform", customer="t1:inv_1"))


def test_null_provider_refuses_every_op():
    p = NullRenewalProvider()
    with pytest.raises(RenewalUnavailable):
        run(p.balance(tenant="_platform", customer="t1:inv_1"))
    with pytest.raises(RenewalUnavailable):
        run(p.rewards(tenant="_platform", customer="t1:inv_1"))
    with pytest.raises(RenewalUnavailable):
        run(p.redeem(tenant="_platform", customer="t1:inv_1", reward="t1:inv_1",
                    idempotency_key="k"))


def test_build_falls_back_to_null_when_unconfigured():
    class _S:
        BILLING_SERVICE_URL = ""
        IDENTITY_SERVICE_URL = ""
        INTERNAL_SERVICE_TOKEN = ""
        BILLING_CLIENT_ID = ""
        BILLING_CLIENT_SECRET = ""

    assert isinstance(build_renewal_provider(_S()), NullRenewalProvider)


def test_build_returns_the_real_provider_when_configured():
    class _S:
        BILLING_SERVICE_URL = "http://billing"
        IDENTITY_SERVICE_URL = "http://identity"
        INTERNAL_SERVICE_TOKEN = "itok"
        BILLING_CLIENT_ID = "cid"
        BILLING_CLIENT_SECRET = "csecret"

    assert isinstance(build_renewal_provider(_S()), RenewalProvider)
