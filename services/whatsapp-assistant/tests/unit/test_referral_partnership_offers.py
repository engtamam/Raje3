"""core/referral_partnership_offers.py — the peer client over operations' own unified
entitlement gateway (GET /internal/operations/referral-and-partnership-offers), the other half of
"what offers does he hold" alongside active_offers.py (campaign-only). Mirrors
test_active_offers.py's own shape (the reference this file was copied from).
"""
from __future__ import annotations

import asyncio
import json
from unittest.mock import patch

from app.core.referral_partnership_offers import (HttpReferralPartnershipOffers,
                                                   NullReferralPartnershipOffers,
                                                   ReferralPartnershipOffer, build)


def run(c):
    return asyncio.run(c)


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


def _client(**over):
    kwargs = dict(url="http://operations",
                 path="/internal/operations/referral-and-partnership-offers", token="t" * 40)
    kwargs.update(over)
    return HttpReferralPartnershipOffers(**kwargs)


def test_null_provider_always_answers_empty():
    p = NullReferralPartnershipOffers()
    assert run(p.for_phone(tenant="t1", phone="0500000001")) == []


def test_a_real_offer_row_is_parsed():
    p = _client()
    payload = {"offers": [{"text": "خصم شراكة إحالة نشط — خصم شامل"}]}
    with patch("urllib.request.urlopen", return_value=_Resp(payload)):
        out = run(p.for_phone(tenant="t1", phone="0500000001"))
    assert out == [ReferralPartnershipOffer(text="خصم شراكة إحالة نشط — خصم شامل")]


def test_the_query_carries_tenant_and_phone_never_guessed():
    p = _client()
    seen = {}

    def _urlopen(req, timeout=0):
        seen["url"] = req.full_url
        return _Resp({"offers": []})

    with patch("urllib.request.urlopen", _urlopen):
        run(p.for_phone(tenant="t1", phone="0500000001"))
    assert "tenant=t1" in seen["url"] and "phone=0500000001" in seen["url"]


def test_an_empty_offers_list_is_a_clean_empty_result():
    p = _client()
    with patch("urllib.request.urlopen", return_value=_Resp({"offers": []})):
        assert run(p.for_phone(tenant="t1", phone="0500000001")) == []


def test_a_row_missing_text_is_skipped_never_crashes():
    p = _client()
    payload = {"offers": [{}, {"text": "ok"}]}
    with patch("urllib.request.urlopen", return_value=_Resp(payload)):
        out = run(p.for_phone(tenant="t1", phone="0500000001"))
    assert len(out) == 1 and out[0].text == "ok"


def test_an_unreachable_peer_degrades_to_empty_never_raises():
    """Same posture `active_offers.py`'s own HttpActiveOffers takes — including the real 503 the
    internal route answers when operations' own EntitlementGateway source is unreachable: a
    conversation must still run, just with nothing to mention this turn."""
    import urllib.error

    p = _client()
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("down")):
        assert run(p.for_phone(tenant="t1", phone="0500000001")) == []


def test_a_non_2xx_status_degrades_to_empty():
    p = _client()
    with patch("urllib.request.urlopen",
              return_value=_Resp({"offers": [{"text": "x"}]}, status=503)):
        assert run(p.for_phone(tenant="t1", phone="0500000001")) == []


def test_build_falls_back_to_null_when_unconfigured():
    class _S:
        OPERATIONS_SERVICE_URL = ""
        INTERNAL_SERVICE_TOKEN = "t" * 40

    assert isinstance(build(_S()), NullReferralPartnershipOffers)


def test_build_uses_http_when_configured():
    class _S:
        OPERATIONS_SERVICE_URL = "http://operations"
        INTERNAL_SERVICE_TOKEN = "t" * 40

    assert isinstance(build(_S()), HttpReferralPartnershipOffers)
