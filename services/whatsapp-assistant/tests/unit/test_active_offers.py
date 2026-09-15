"""core/active_offers.py — the peer client over reminders' own send-log read
(GET /internal/reminders/portal/offers), reused as-is for check_active_offers (core/tools.py).
Mirrors test_rhythm_provider.py's own shape (the reference this file was copied from)."""
from __future__ import annotations

import asyncio
import json
from unittest.mock import patch

from app.core.active_offers import ActiveOffer, HttpActiveOffers, NullActiveOffers, build


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
    kwargs = dict(url="http://reminders", path="/internal/reminders/portal/offers", token="t" * 40)
    kwargs.update(over)
    return HttpActiveOffers(**kwargs)


def test_null_provider_always_answers_empty():
    p = NullActiveOffers()
    assert run(p.for_subject(tenant="t1", subject_ref="s1")) == []


def test_a_real_offer_row_is_parsed_into_an_active_offer():
    p = _client()
    payload = {"offers": [{"text": "خصم 20% على الغسيل", "expires_at": 1_800_000_000,
                          "sent_at": 1_799_000_000, "services": ["svc_wash"], "scoped": True,
                          "value": "20%"}]}
    with patch("urllib.request.urlopen", return_value=_Resp(payload)):
        out = run(p.for_subject(tenant="t1", subject_ref="s1"))
    assert out == [ActiveOffer(text="خصم 20% على الغسيل", expires_at=1_800_000_000,
                               sent_at=1_799_000_000, services=["svc_wash"], scoped=True,
                               value="20%")]


def test_the_query_carries_tenant_and_subject_ref_never_guessed():
    p = _client()
    seen = {}

    def _urlopen(req, timeout=0):
        seen["url"] = req.full_url
        return _Resp({"offers": []})

    with patch("urllib.request.urlopen", _urlopen):
        run(p.for_subject(tenant="t1", subject_ref="s1"))
    assert "tenant=t1" in seen["url"] and "subject_ref=s1" in seen["url"]


def test_an_empty_offers_list_is_a_clean_empty_result():
    p = _client()
    with patch("urllib.request.urlopen", return_value=_Resp({"offers": []})):
        assert run(p.for_subject(tenant="t1", subject_ref="s1")) == []


def test_a_row_missing_text_is_skipped_never_crashes():
    p = _client()
    payload = {"offers": [{"expires_at": 1, "services": []}, {"text": "ok", "expires_at": 2}]}
    with patch("urllib.request.urlopen", return_value=_Resp(payload)):
        out = run(p.for_subject(tenant="t1", subject_ref="s1"))
    assert len(out) == 1 and out[0].text == "ok"


def test_an_unreachable_peer_degrades_to_empty_never_raises():
    import urllib.error

    p = _client()
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("down")):
        assert run(p.for_subject(tenant="t1", subject_ref="s1")) == []


def test_a_non_2xx_status_degrades_to_empty():
    p = _client()
    with patch("urllib.request.urlopen", return_value=_Resp({"offers": [{"text": "x"}]}, status=500)):
        assert run(p.for_subject(tenant="t1", subject_ref="s1")) == []


def test_build_falls_back_to_null_when_unconfigured():
    class _S:
        REMINDERS_SERVICE_URL = ""
        REMINDERS_PORTAL_OFFERS_PATH = "/internal/reminders/portal/offers"
        INTERNAL_SERVICE_TOKEN = "t" * 40
        PEER_TIMEOUT_SECONDS = 8

    assert isinstance(build(_S()), NullActiveOffers)


def test_build_returns_the_real_client_when_configured():
    class _S:
        REMINDERS_SERVICE_URL = "http://reminders"
        REMINDERS_PORTAL_OFFERS_PATH = "/internal/reminders/portal/offers"
        INTERNAL_SERVICE_TOKEN = "t" * 40
        PEER_TIMEOUT_SECONDS = 8

    assert isinstance(build(_S()), HttpActiveOffers)
