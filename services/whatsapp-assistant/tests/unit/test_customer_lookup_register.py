"""HttpCustomerLookup.register() — auto-registering a stranger's number as a real جهات الاتصال row,
ONLY once the tenant's own owner has opted in (services/operations' own core/
whatsapp_auto_register.py). A feature the conversation triggers deterministically, never a tool the
model must remember to call — see conversation.py's own call site.
"""
from __future__ import annotations

import asyncio
import json
from unittest.mock import patch

from app.core.customer_lookup import HttpCustomerLookup, NullCustomerLookup


def run(coro):
    return asyncio.run(coro)


def client(**overrides):
    kwargs = dict(
        url="http://operations:8000", path="/internal/operations/customer-by-phone",
        token="t", timeout=8,
        auto_register_flag_path="/internal/operations/whatsapp-auto-register",
        customer_id_by_phone_path="/internal/operations/customer-id-by-phone")
    kwargs.update(overrides)
    return HttpCustomerLookup(**kwargs)


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


def test_never_registers_when_the_owner_has_not_opted_in():
    calls = []

    def _urlopen(req, timeout=None):
        calls.append(req.full_url)
        return _Resp({"enabled": False})

    with patch("urllib.request.urlopen", _urlopen):
        ok = run(client().register("t1", "+9665..."))

    assert ok is False
    # ONE CALL ONLY — the flag read. A stranger's number must never be turned into a real
    # customer_id when the flag comes back off, so the second call must never fire at all.
    assert len(calls) == 1
    assert "whatsapp-auto-register" in calls[0]


def test_registers_once_the_owner_has_opted_in():
    calls = []

    def _urlopen(req, timeout=None):
        calls.append(req.full_url)
        if "whatsapp-auto-register" in req.full_url:
            return _Resp({"enabled": True})
        return _Resp({"customer_id": "cus_1", "subject_ref": "ref_1"})

    with patch("urllib.request.urlopen", _urlopen):
        ok = run(client().register("t1", "+9665..."))

    assert ok is True
    assert len(calls) == 2
    assert "customer-id-by-phone" in calls[1]


def test_a_failed_flag_read_never_registers():
    def _urlopen(req, timeout=None):
        return _Resp({}, status=503)

    with patch("urllib.request.urlopen", _urlopen):
        assert run(client().register("t1", "+9665...")) is False


def test_a_failed_create_call_reports_false_even_with_the_flag_on():
    def _urlopen(req, timeout=None):
        if "whatsapp-auto-register" in req.full_url:
            return _Resp({"enabled": True})
        return _Resp({}, status=503)

    with patch("urllib.request.urlopen", _urlopen):
        assert run(client().register("t1", "+9665...")) is False


def test_neither_peer_path_configured_never_calls_out_at_all():
    """A deployment that never set the two extra paths auto-registers nobody — same "opt in,
    never silently upgrade" default every other optional peer in this service already holds."""
    calls = []

    def _urlopen(req, timeout=None):
        calls.append(req.full_url)
        return _Resp({"enabled": True})

    with patch("urllib.request.urlopen", _urlopen):
        ok = run(client(auto_register_flag_path="", customer_id_by_phone_path="").register("t1", "+9665..."))

    assert ok is False
    assert calls == []


def test_null_customer_lookup_never_registers():
    assert run(NullCustomerLookup().register("t1", "+9665...")) is False
