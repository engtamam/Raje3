"""HttpLoyalty/NullLoyalty — a points credit with no visit behind it, calling loyalty's own
`/internal/loyalty/award` (2026-09-13). Built ahead of any goal that calls it: the capability
exists so a future template design does not wait on a backend that does not.
"""
from __future__ import annotations

import asyncio
import json
import urllib.error
from unittest.mock import patch

from app.adapters.peers import HttpLoyalty, NullLoyalty


def run(c):
    return asyncio.run(c)


def client():
    return HttpLoyalty(loyalty_url="http://loyalty", award_path="/internal/loyalty/award",
                       token="t")


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


def test_a_real_credit_reports_what_loyalty_reports():
    with patch("urllib.request.urlopen", _answer({"earned": 20, "balance": 20})):
        out = run(client().award(tenant="t1", subject_ref="ref_1", points=20,
                                 idempotency_key="cmp_1:ref_1"))
    assert out == {"earned": 20, "balance": 20}


def test_a_duplicate_key_is_passed_through_unchanged():
    dup = {"earned": 0, "duplicate": True, "reason": "already credited for this key"}
    with patch("urllib.request.urlopen", _answer(dup)):
        out = run(client().award(tenant="t1", subject_ref="ref_1", points=20,
                                 idempotency_key="cmp_1:ref_1"))
    assert out == dup


def test_a_peer_outage_answers_not_credited_rather_than_raising():
    down = urllib.error.URLError("connection refused")
    with patch("urllib.request.urlopen", _answer(raise_with=down)):
        out = run(client().award(tenant="t1", subject_ref="ref_1", points=20,
                                 idempotency_key="cmp_1:ref_1"))
    assert out["earned"] == 0
    assert "UNREACHABLE" in out["reason"]


def test_a_malformed_answer_answers_not_credited_rather_than_raising():
    boom = urllib.error.HTTPError("u", 500, "boom", None, None)
    with patch("urllib.request.urlopen", _answer(raise_with=boom)):
        out = run(client().award(tenant="t1", subject_ref="ref_1", points=20,
                                 idempotency_key="cmp_1:ref_1"))
    assert out["earned"] == 0


def test_null_loyalty_never_credits_and_says_why():
    out = run(NullLoyalty().award(tenant="t1", subject_ref="ref_1", points=20,
                                  idempotency_key="cmp_1:ref_1"))
    assert out == {"earned": 0, "reason": "NOT_CONFIGURED"}
