"""HttpOwnerPhone / NullOwnerPhone — the subscription-renewal trigger's ONE read: a tenant's
founding owner's own phone, from identity-service (platform v0.19.13)."""
from __future__ import annotations

import asyncio
import json
import urllib.error
from unittest.mock import patch

from app.core.owner_phone import HttpOwnerPhone, NullOwnerPhone, build


def run(c):
    return asyncio.run(c)


def _owner():
    return HttpOwnerPhone(url="http://identity", path="/internal/tenancy/owner-phone",
                          token="itok", timeout=8)


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


def test_a_phone_identifier_resolves_to_the_number():
    o = _owner()
    with patch("urllib.request.urlopen",
              return_value=_Resp({"tenant": "t1", "person_id": "p1",
                                  "identifier": "+966500000000", "is_phone": True})):
        assert run(o.resolve("t1")) == "+966500000000"


def test_an_email_identifier_resolves_to_empty_never_sent_by_whatsapp():
    o = _owner()
    with patch("urllib.request.urlopen",
              return_value=_Resp({"tenant": "t1", "person_id": "p1",
                                  "identifier": "owner@shop.com", "is_phone": False})):
        assert run(o.resolve("t1")) == ""


def test_a_404_not_found_owner_resolves_to_empty():
    o = _owner()
    with patch("urllib.request.urlopen",
              side_effect=urllib.error.HTTPError("u", 404, "not found", {}, None)):
        assert run(o.resolve("t1")) == ""


def test_an_unreachable_peer_resolves_to_empty_never_raises():
    o = _owner()
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("down")):
        assert run(o.resolve("t1")) == ""


def test_an_empty_tenant_resolves_to_empty_without_a_call():
    o = _owner()
    with patch("urllib.request.urlopen") as m:
        assert run(o.resolve("")) == ""
        m.assert_not_called()


def test_null_owner_phone_always_resolves_to_empty():
    assert run(NullOwnerPhone().resolve("t1")) == ""


def test_build_falls_back_to_null_when_unconfigured():
    class _S:
        IDENTITY_SERVICE_URL = ""
        IDENTITY_OWNER_PHONE_PATH = "/internal/tenancy/owner-phone"
        INTERNAL_SERVICE_TOKEN = "itok"
        PEER_TIMEOUT_SECONDS = 8

    assert isinstance(build(_S()), NullOwnerPhone)


def test_build_returns_the_real_adapter_when_configured():
    class _S:
        IDENTITY_SERVICE_URL = "http://identity"
        IDENTITY_OWNER_PHONE_PATH = "/internal/tenancy/owner-phone"
        INTERNAL_SERVICE_TOKEN = "itok"
        PEER_TIMEOUT_SECONDS = 8

    assert isinstance(build(_S()), HttpOwnerPhone)
