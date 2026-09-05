"""HttpReminders.grant_marketing — a real HTTP round trip, not a source-inspection test.

Found broken by ci/check_undefined_names.py: `urllib.request`/`json` were used directly in this
method but never imported anywhere in the file (every other client goes through `_post`/`_get`),
so any real invocation raised NameError. No existing test caught it because the only coverage
this method had was a fake stand-in class in an integration test and a source-string check on a
DIFFERENT method (`set_prefs`) in test_render.py — this file exercises the real class.
"""
from __future__ import annotations

import asyncio
import json
from unittest.mock import patch

from app.adapters.peers import HttpReminders


def run(c):
    return asyncio.run(c)


def peer():
    return HttpReminders(url="http://reminders", path="/internal/reminders/prefs", token="t" * 40)


class _Resp:
    def __init__(self, payload: dict) -> None:
        self._p = json.dumps(payload).encode()

    def read(self):
        return self._p

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_grants_marketing_and_keeps_existing_stops(monkeypatch):
    seen = {}

    def _urlopen(req, timeout=0):
        if req.get_method() == "GET" if hasattr(req, "get_method") else False:
            return _Resp({"preferences": []})
        seen["url"] = req.full_url
        seen["method"] = req.method
        seen["body"] = json.loads(req.data or b"{}")
        return _Resp({"saved": True})

    prefs_response = {"preferences": [
        {"class": "reminders", "enabled": False}, {"class": "marketing", "enabled": False},
    ]}

    async def _fake_prefs(self, tenant, subject_ref):
        return prefs_response

    with patch.object(HttpReminders, "prefs_for", _fake_prefs), \
         patch("urllib.request.urlopen", _urlopen):
        ok = run(peer().grant_marketing("t1", "sub_a"))

    assert ok is True
    assert seen["method"] == "PUT"
    # marketing itself is dropped from "stopped" (that's the whole point of granting it); every
    # OTHER stopped class survives untouched.
    assert seen["body"]["stopped"] == ["reminders"]


def test_a_read_that_fails_refuses_the_grant_rather_than_guessing():
    async def _fake_prefs(self, tenant, subject_ref):
        raise OSError("peer unreachable")

    with patch.object(HttpReminders, "prefs_for", _fake_prefs):
        ok = run(peer().grant_marketing("t1", "sub_a"))
    assert ok is False


def test_an_empty_preferences_answer_refuses_rather_than_granting_blind():
    async def _fake_prefs(self, tenant, subject_ref):
        return {"preferences": []}

    with patch.object(HttpReminders, "prefs_for", _fake_prefs):
        ok = run(peer().grant_marketing("t1", "sub_a"))
    assert ok is False


def test_the_peer_saying_it_did_not_save_is_reported_as_false():
    async def _fake_prefs(self, tenant, subject_ref):
        return {"preferences": [{"class": "reminders", "enabled": False}]}

    def _urlopen(req, timeout=0):
        return _Resp({"saved": False})

    with patch.object(HttpReminders, "prefs_for", _fake_prefs), \
         patch("urllib.request.urlopen", _urlopen):
        ok = run(peer().grant_marketing("t1", "sub_a"))
    assert ok is False


def test_a_peer_error_on_the_write_itself_is_caught_not_raised():
    import urllib.error

    async def _fake_prefs(self, tenant, subject_ref):
        return {"preferences": [{"class": "reminders", "enabled": False}]}

    def _urlopen(req, timeout=0):
        raise urllib.error.URLError("connection refused")

    with patch.object(HttpReminders, "prefs_for", _fake_prefs), \
         patch("urllib.request.urlopen", _urlopen):
        ok = run(peer().grant_marketing("t1", "sub_a"))
    assert ok is False
