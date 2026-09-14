"""A signed, short-lived `state` value for an OAuth authorize redirect.

WHY THE TENANT LIVES INSIDE THE TOKEN. A callback a few seconds later carries only what the
provider echoes back (`code`, `state`) — no auth header, no session cookie a cross-domain bounce
through the provider's own consent screen can be relied on to keep. So `state` is not a random
anti-CSRF nonce checked against a server-side session (there is no session here to check it
against); it is a SELF-CONTAINED signed claim — "this tenant started this install, this many
seconds ago" — the callback route decodes and verifies with nothing else to go on.

SAME SHAPE AS `operator_ticket.py`, DELIBERATELY — an HMAC over (purpose, tenant, nonce, expiry)
under the same `PII_SALT` every short-lived signed token in this service already uses, not a new
secret to provision. `purpose` (e.g. "salla") keeps one provider's state from being replayed as
another's if this pattern is ever reused for a second marketplace.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time

#: Five minutes — long enough for a slow OAuth consent screen, short enough that a leaked/logged
#: `state` (query strings end up in access logs and browser history) stops being useful quickly.
TTL_SECONDS = 300


def _b64(tenant: str) -> str:
    return base64.urlsafe_b64encode(tenant.encode("utf-8")).decode("ascii").rstrip("=")


def _unb64(value: str) -> str | None:
    try:
        pad = "=" * (-len(value) % 4)
        return base64.urlsafe_b64decode(value + pad).decode("utf-8")
    except Exception:                                                      # noqa: BLE001
        return None


def issue(salt: str, purpose: str, tenant: str, *, now: int | None = None) -> str:
    """A fresh state carrying THIS tenant, good for the next `TTL_SECONDS`."""
    opened = int(now if now is not None else time.time())
    expires = opened + TTL_SECONDS
    nonce = secrets.token_hex(8)
    tenant_part = _b64(tenant)
    mac = _sign(salt, purpose, tenant, nonce, opened, expires)
    return f"{tenant_part}.{opened}.{expires}.{nonce}.{mac}"


def tenant_for(salt: str, purpose: str, state: str, *, now: int | None = None) -> str | None:
    """The tenant this state was minted for, once verified — `None` if it is forged, expired, or
    malformed. Never raises: a callback carrying a garbage `state` (a stale bookmark, a replayed
    URL, a bot probing the endpoint) is an ordinary refusal, not a fault."""
    if not salt or not state:
        return None
    parts = state.split(".")
    if len(parts) != 5:
        return None
    tenant_part, opened_s, expires_s, nonce, mac = parts
    if not (opened_s.isdigit() and expires_s.isdigit()):
        return None
    tenant = _unb64(tenant_part)
    if not tenant:
        return None
    opened, expires = int(opened_s), int(expires_s)
    clock = int(now if now is not None else time.time())
    if not opened <= clock <= expires:
        return None
    if not hmac.compare_digest(_sign(salt, purpose, tenant, nonce, opened, expires), mac):
        return None
    return tenant


def _sign(salt: str, purpose: str, tenant: str, nonce: str, opened: int, expires: int) -> str:
    return hmac.new(salt.encode("utf-8"),
                    f"oauth_state|{purpose}|{tenant}|{nonce}|{opened}|{expires}".encode("utf-8"),
                    hashlib.sha256).hexdigest()
