"""app/core/push_verify.py — verifying a job-service push dispatch signature. Mirrors platform's
own core/push_signing test coverage and whatsapp-assistant's own copy (the first migration) so
this copy never silently drifts from what job-service actually sends."""
from __future__ import annotations

import hashlib
import hmac

from app.core.push_verify import verify

SECRET = "s" * 40


def _sign(secret: str, ts: int, body: bytes) -> str:
    signed = f"{ts}.".encode("utf-8") + body
    return hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()


def test_a_genuine_signature_within_the_window_verifies():
    body = b'{"job":{"id":"j1"}}'
    ts = 1_800_000_000
    sig = _sign(SECRET, ts, body)
    assert verify(SECRET, ts, body, sig, now=ts + 10, max_skew_seconds=300) is True


def test_a_tampered_body_never_verifies():
    body = b'{"job":{"id":"j1"}}'
    ts = 1_800_000_000
    sig = _sign(SECRET, ts, body)
    assert verify(SECRET, ts, body + b"x", sig, now=ts, max_skew_seconds=300) is False


def test_an_old_timestamp_outside_the_window_is_refused_even_with_a_valid_signature():
    body = b'{"job":{"id":"j1"}}'
    ts = 1_800_000_000
    sig = _sign(SECRET, ts, body)
    assert verify(SECRET, ts, body, sig, now=ts + 301, max_skew_seconds=300) is False


def test_no_secret_configured_refuses_never_crashes():
    assert verify("", 1000, b"x", "deadbeef", now=1000, max_skew_seconds=300) is False


def test_a_garbage_non_numeric_timestamp_refuses_never_raises():
    assert verify(SECRET, "not-a-number", b"x", "deadbeef", now=1000, max_skew_seconds=300) is False
