"""ي-3 — a send log we could not read must not look like a shop that sent nothing.

THE PEER IS WHERE THE TWO STATES BECAME ONE. `HttpPeers.effect` answered
`{"sends": [], "sent_count": 0, "opt_outs": 0}` when reminders timed out — character for character
what a shop that has never sent a message looks like. Everything downstream then computed
confidently from it, and the dashboard printed «0 زيارة عادت بعد رسالة» through every outage.

THE REAL DRIVER, with the socket replaced and nothing else. A hand-written stub of `effect` would
pass whatever the driver did, which is how a chain defect survives a green suite.
"""
from __future__ import annotations

import asyncio
import json
import urllib.error


def _peers():
    from app.adapters.peers import HttpPeers

    return HttpPeers(operations_url="http://ops", visits_path="/v", catalogue_path="/c",
                     reminders_url="http://rem", consent_count_path="/n",
                     billing_url="http://bil", entitlement_path="/e",
                     token="k" * 40, timeout=1)


class _Body:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> bool:
        return False


def _with_urlopen(fake, fn):
    from app.adapters import peers

    real = peers.urllib.request.urlopen
    peers.urllib.request.urlopen = fake
    try:
        return fn()
    finally:
        peers.urllib.request.urlopen = real


def test_a_read_that_succeeded_says_so():
    answer = _with_urlopen(
        lambda *a, **k: _Body({"sends": [{"subject_ref": "a", "at": 10}], "sent_count": 1,
                               "opt_outs": 0, "truncated": False}),
        lambda: asyncio.run(_peers().effect("shop")))
    assert answer["ok"] is True
    assert answer["sent_count"] == 1


def test_a_read_that_failed_does_not():
    """AND IT IS THE ABSENCE OF THE CLAIM THAT MATTERS, not the empty list beside it. Every caller
    checks `ok`; nothing may infer «he sent nothing» from `sent_count == 0`."""
    def boom(*a, **k):
        raise urllib.error.URLError("reminders is restarting")

    answer = _with_urlopen(boom, lambda: asyncio.run(_peers().effect("shop")))
    assert answer["ok"] is False


def test_the_peers_own_ok_cannot_overwrite_ours():
    """`ok` is set LAST on a read that returned. A peer that one day sends its own `ok: false`
    must not make a read that plainly succeeded look like a failure — what arrived is what we
    read, and whether the READ worked is this adapter's fact to state."""
    answer = _with_urlopen(
        lambda *a, **k: _Body({"ok": False, "sends": [], "sent_count": 0, "opt_outs": 0}),
        lambda: asyncio.run(_peers().effect("shop")))
    assert answer["ok"] is True
