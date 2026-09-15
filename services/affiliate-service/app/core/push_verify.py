"""Verify a job-service PUSH dispatch — copied from platform/services/job-service's own
`core/push_signing.verify` (base-services-62's reference implementation, v0.24.0/v0.24.1), the
same "copied deliberately rather than shared" convention every other peer client in this codebase
already follows: our services never import platform's Python packages directly, so the small,
stable piece of logic is copied once per receiving service instead. See
services/whatsapp-assistant's own copy of this file (the first migration, 2026-09-15) for the
full design rationale.

Scheme (Stripe-webhook style): job-service signs `f"{timestamp}.{body}"` (body = the exact request
bytes) with HMAC-SHA256 under a shared secret, and sends the hex digest + the timestamp as two
headers. The receiver recomputes and compares in constant time, AND rejects a timestamp outside a
small replay window — both checks fail CLOSED (missing/garbage input -> False, never an exception).

THE SECRET: job-service signs with `PUSH_SIGNING_SECRET` if that is configured on ITS side, else
falls back to the shared fleet `INTERNAL_SERVICE_TOKEN` every service already holds identically —
so a receiver with no dedicated `PUSH_SIGNING_SECRET` of its own verifies correctly against
`INTERNAL_SERVICE_TOKEN` by default too, matching that same fallback."""
from __future__ import annotations

import hashlib
import hmac

SIGNATURE_HEADER = "X-Job-Signature"
TIMESTAMP_HEADER = "X-Job-Signature-Timestamp"


def verify(secret: str, timestamp: str | int, body: bytes, signature: str, *,
          now: float, max_skew_seconds: int) -> bool:
    """True iff `signature` matches `body`+`timestamp` under `secret` AND the timestamp is within
    `max_skew_seconds` of `now`. Constant-time compare (CWE-208). Any missing/garbage input ->
    False, never an exception — fail closed, never crash."""
    if not secret or not signature:
        return False
    try:
        ts = int(timestamp)
    except (TypeError, ValueError):
        return False
    # Replay window FIRST: an old (or far-future) timestamp is refused even if the HMAC is valid,
    # so a captured genuine push cannot be re-sent later.
    if abs(float(now) - ts) > int(max_skew_seconds):
        return False
    signed = f"{ts}.".encode("utf-8") + (body or b"")
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, str(signature))
