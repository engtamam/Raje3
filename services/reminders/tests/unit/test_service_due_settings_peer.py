"""HttpServiceDueSettings/NullServiceDueSettings — «حان وقت الخدمة»'s campaigns-side on/off
setting, read at every send of `svc_service_reminder` (2026-09-13). Mirrors
services/campaigns/tests/unit/test_loyalty_peer.py's own shape exactly.
"""
from __future__ import annotations

import asyncio
import json
import urllib.error
from unittest.mock import patch

from app.core.service_due_settings import HttpServiceDueSettings, NullServiceDueSettings


def run(c):
    return asyncio.run(c)


def client(ttl_seconds: int = 300):
    return HttpServiceDueSettings(
        url="http://campaigns", path="/internal/campaigns/service-due-settings",
        token="t", ttl_seconds=ttl_seconds)


class _Resp:
    def __init__(self, payload):
        self._p = json.dumps(payload).encode()

    def read(self):
        return self._p

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _answer(payload=None, raise_with=None):
    def _urlopen(req, timeout=0):
        if raise_with is not None:
            raise raise_with
        return _Resp(payload or {})
    return _urlopen


def test_a_real_answer_is_passed_through():
    with patch("urllib.request.urlopen", _answer({"active": False})):
        out = run(client().load("t1"))
    assert out.active is False


def test_a_tenant_that_never_touched_this_gets_the_untouched_default():
    with patch("urllib.request.urlopen", _answer({"active": True})):
        out = run(client().load("t1"))
    assert out.active is True


def test_a_peer_outage_answers_the_safe_default_rather_than_raising():
    down = urllib.error.URLError("connection refused")
    with patch("urllib.request.urlopen", _answer(raise_with=down)):
        out = run(client().load("t1"))
    assert out.active is True


def test_a_malformed_answer_answers_the_safe_default_rather_than_raising():
    boom = urllib.error.HTTPError("u", 500, "boom", None, None)
    with patch("urllib.request.urlopen", _answer(raise_with=boom)):
        out = run(client().load("t1"))
    assert out.active is True


def test_the_answer_is_cached_within_the_ttl():
    calls = {"n": 0}

    def _urlopen(req, timeout=0):
        calls["n"] += 1
        return _Resp({"active": True})

    c = client(ttl_seconds=300)
    with patch("urllib.request.urlopen", _urlopen):
        run(c.load("t1"))
        run(c.load("t1"))
    assert calls["n"] == 1


def test_null_service_due_settings_always_answers_the_safe_default():
    out = run(NullServiceDueSettings().load("t1"))
    assert out.active is True
