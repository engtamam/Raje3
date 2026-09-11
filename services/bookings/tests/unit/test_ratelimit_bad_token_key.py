"""bookings-004 (QA audit, 2026-09-12): a rejected-but-present Bearer token used to fall back to
the SAME plain `None` a fully anonymous request gets, so every malformed/expired token behind one
NAT shared one IP-wide rate-limit bucket. `optional_principal` now keys a rejected token by its
own hash instead — proved here at the dependency level, no full app needed.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

from starlette.requests import Request

from app.api.ratelimit import optional_principal


class _RaisingVerifier:
    def verify(self, token: str):
        raise ValueError("bad token")


def _request(auth_header: str) -> Request:
    scope = {
        "type": "http", "method": "GET", "path": "/x", "headers": [
            (b"authorization", auth_header.encode()) if auth_header else (b"x-none", b"1"),
        ],
        "app": SimpleNamespace(state=SimpleNamespace(container=SimpleNamespace(
            token_verifier=_RaisingVerifier()))),
        "client": ("1.2.3.4", 1234),
    }
    return Request(scope)


def run(c):
    return asyncio.run(c)


def test_two_different_bad_tokens_get_two_different_keys():
    r1 = _request("Bearer garbage-one")
    r2 = _request("Bearer garbage-two")
    run(optional_principal(r1))
    run(optional_principal(r2))
    key1 = r1.state.rl_bad_token_key
    key2 = r2.state.rl_bad_token_key
    assert key1 and key2
    assert key1 != key2, "two different rejected tokens must not share one rate-limit key"


def test_the_same_bad_token_gets_the_same_key_every_time():
    """Stable, not random per request — two retries of the SAME malformed token must still count
    against the same budget, or the key would let an attacker reset their own counter for free by
    resending the identical token."""
    r1 = _request("Bearer garbage-one")
    r2 = _request("Bearer garbage-one")
    run(optional_principal(r1))
    run(optional_principal(r2))
    assert r1.state.rl_bad_token_key == r2.state.rl_bad_token_key


def test_a_fully_anonymous_request_sets_no_bad_token_key_at_all():
    r = _request("")
    principal = run(optional_principal(r))
    assert principal is None
    assert not hasattr(r.state, "rl_bad_token_key")
