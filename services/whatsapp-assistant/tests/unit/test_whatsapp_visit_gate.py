"""HttpWhatsAppVisitGate / NullWhatsAppVisitGate — read before the visit-registration Flow ever
opens for an identified staff sender. Defaults OFF for every tenant (services/operations' own
core/whatsapp_visit_flag.py has the full reasoning)."""
from __future__ import annotations

import asyncio
import json
import urllib.error
from unittest.mock import patch

from app.core.whatsapp_visit_gate import (HttpWhatsAppVisitGate, NullWhatsAppVisitGate, build)


def run(c):
    return asyncio.run(c)


def _gate():
    return HttpWhatsAppVisitGate(
        url="http://operations", path="/internal/operations/whatsapp-visit-registration",
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


def test_an_opted_in_tenant_reads_true():
    with patch("urllib.request.urlopen",
              return_value=_Resp({"tenant": "t1", "enabled": True})):
        assert run(_gate().enabled("t1")) is True


def test_a_tenant_that_never_opted_in_reads_false():
    with patch("urllib.request.urlopen",
              return_value=_Resp({"tenant": "t1", "enabled": False})):
        assert run(_gate().enabled("t1")) is False


def test_an_unreachable_peer_fails_toward_off():
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("down")):
        assert run(_gate().enabled("t1")) is False


def test_a_non_2xx_status_fails_toward_off():
    with patch("urllib.request.urlopen", return_value=_Resp({"enabled": True}, status=500)):
        assert run(_gate().enabled("t1")) is False


def test_an_empty_tenant_reads_false_without_a_call():
    with patch("urllib.request.urlopen") as m:
        assert run(_gate().enabled("")) is False
        m.assert_not_called()


def test_null_gate_always_reads_false():
    assert run(NullWhatsAppVisitGate().enabled("t1")) is False


def test_build_falls_back_to_null_when_unconfigured():
    class _S:
        OPERATIONS_SERVICE_URL = ""
        OPERATIONS_WHATSAPP_VISIT_REGISTRATION_PATH = "/internal/operations/whatsapp-visit-registration"
        INTERNAL_SERVICE_TOKEN = "itok"
        PEER_TIMEOUT_SECONDS = 8

    assert isinstance(build(_S()), NullWhatsAppVisitGate)


def test_build_returns_the_real_adapter_when_configured():
    class _S:
        OPERATIONS_SERVICE_URL = "http://operations"
        OPERATIONS_WHATSAPP_VISIT_REGISTRATION_PATH = "/internal/operations/whatsapp-visit-registration"
        INTERNAL_SERVICE_TOKEN = "itok"
        PEER_TIMEOUT_SECONDS = 8

    assert isinstance(build(_S()), HttpWhatsAppVisitGate)
