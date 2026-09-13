"""HttpAiToggle/NullAiToggle — asks operations' `/internal/operations/shop-name` (the SAME route
whatsapp-assistant's own shop_identity.py already calls) for one field: `ai_enabled`. Used by
Dispatcher._card_button_allowed to decide whether a carousel card's own button promises an action
something will actually answer (2026-09-13).
"""
from __future__ import annotations

import asyncio
import json
import urllib.error
from unittest.mock import patch

from app.adapters.peers import HttpAiToggle, NullAiToggle


def run(c):
    return asyncio.run(c)


def client():
    return HttpAiToggle(operations_url="http://operations",
                        path="/internal/operations/shop-name", token="t")


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


def test_a_shop_that_never_touched_it_reads_back_enabled():
    with patch("urllib.request.urlopen", _answer({"ai_enabled": True})):
        assert run(client().enabled("t1")) is True


def test_a_shop_that_switched_it_off_reads_back_disabled():
    with patch("urllib.request.urlopen", _answer({"ai_enabled": False})):
        assert run(client().enabled("t1")) is False


def test_the_field_missing_entirely_defaults_to_enabled():
    """An older operations build that has not shipped the field yet — absent reads as on, same
    fail-open posture the peer's own docstring states."""
    with patch("urllib.request.urlopen", _answer({})):
        assert run(client().enabled("t1")) is True


def test_a_peer_outage_fails_open_to_enabled():
    down = urllib.error.URLError("connection refused")
    with patch("urllib.request.urlopen", _answer(raise_with=down)):
        assert run(client().enabled("t1")) is True


def test_a_malformed_answer_fails_open_to_enabled():
    boom = urllib.error.HTTPError("u", 500, "boom", None, None)
    with patch("urllib.request.urlopen", _answer(raise_with=boom)):
        assert run(client().enabled("t1")) is True


def test_an_empty_tenant_never_reaches_operations():
    called = {"n": 0}

    def _urlopen(req, timeout=0):
        called["n"] += 1
        return _Resp({"ai_enabled": True})

    with patch("urllib.request.urlopen", _urlopen):
        assert run(client().enabled("")) is True
    assert called["n"] == 0


def test_null_ai_toggle_always_enabled():
    assert run(NullAiToggle().enabled("t1")) is True
