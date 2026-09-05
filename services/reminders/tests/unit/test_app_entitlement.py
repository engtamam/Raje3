"""Does this establishment own one app key — the plain fact, reusable for any key."""
from __future__ import annotations

import asyncio
import json
from unittest.mock import patch

from app.core.app_entitlement import HttpAppEntitlement, NullAppEntitlement, build_app_entitlement


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


def _http():
    return HttpAppEntitlement(billing_url="http://billing", check_path="/internal/check", token="t")


def test_null_answers_true_for_a_key_it_was_given():
    e = NullAppEntitlement({"feature.rating"})
    assert run(e.allowed("t1", "feature.rating")) is True


def test_null_answers_false_for_a_key_it_was_not_given():
    e = NullAppEntitlement({"feature.rating"})
    assert run(e.allowed("t1", "feature.loyalty")) is False


def test_null_with_nothing_owns_nothing():
    e = NullAppEntitlement()
    assert run(e.allowed("t1", "feature.rating")) is False


def test_http_asks_with_the_given_key_in_the_query_string():
    seen = {}

    def _urlopen(req, timeout=0):
        seen["url"] = req.full_url
        return _Resp({"allowed": True})

    with patch("urllib.request.urlopen", _urlopen):
        result = run(_http().allowed("t1", "feature.rating"))
    assert result is True
    assert "key=feature.rating" in seen["url"]
    assert "tenant=t1" in seen["url"]


def test_http_answers_false_when_billing_says_not_allowed():
    with patch("urllib.request.urlopen", return_value=_Resp({"allowed": False})):
        assert run(_http().allowed("t1", "feature.rating")) is False


def test_http_answers_none_when_the_peer_is_unreachable():
    import urllib.error

    def _boom(req, timeout=0):
        raise urllib.error.URLError("refused")

    with patch("urllib.request.urlopen", _boom):
        assert run(_http().allowed("t1", "feature.rating")) is None


def test_http_answers_false_for_an_empty_tenant_without_asking():
    with patch("urllib.request.urlopen") as m:
        assert run(_http().allowed("", "feature.rating")) is False
        m.assert_not_called()


def test_two_different_keys_are_asked_independently():
    seen = []

    def _urlopen(req, timeout=0):
        seen.append(req.full_url)
        return _Resp({"allowed": True})

    with patch("urllib.request.urlopen", _urlopen):
        run(_http().allowed("t1", "feature.rating"))
        run(_http().allowed("t1", "feature.loyalty"))
    assert "key=feature.rating" in seen[0]
    assert "key=feature.loyalty" in seen[1]


def test_builder_returns_null_when_billing_is_not_configured():
    class _S:
        BILLING_SERVICE_URL = ""
        BILLING_CHECK_PATH = "/internal/check"
        INTERNAL_SERVICE_TOKEN = "t"
        PEER_TIMEOUT_SECONDS = 8

    e = build_app_entitlement(_S())
    assert e.driver == "null"


def test_builder_returns_http_when_billing_is_configured():
    class _S:
        BILLING_SERVICE_URL = "http://billing"
        BILLING_CHECK_PATH = "/internal/check"
        INTERNAL_SERVICE_TOKEN = "t"
        PEER_TIMEOUT_SECONDS = 8

    e = build_app_entitlement(_S())
    assert e.driver == "http"
