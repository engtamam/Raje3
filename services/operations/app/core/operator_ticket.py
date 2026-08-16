"""Proof that the person named on a visit is the person who typed a PIN.

THE HOLE THIS CLOSES (و-4). `verify-pin` confirms an operator at the moment of saving, and then
issued nothing. The visit that followed carried `operator_id` as a free string in the request body,
so the two facts were never joined: a device in Riyadh could name Jeddah's operator, and the visit
would be filed against him — and `_branch_for` reads exactly that field to decide WHERE the work
happened, so the branch numbers move with it. The comment on `_branch_for` says it closes the hole
of a body-supplied branch; it does, and this was the same hole one field to the left.

SIGNED, NOT STORED. A ticket is an HMAC over (tenant, operator_id, expiry) under the same salt the
PIN hash already uses. No new collection, nothing to expire on a schedule, and a restart does not
invalidate a tablet mid-shift. What it proves is narrow and exact: somebody knew this operator's
PIN, in this establishment, within the last few minutes.

SHORT-LIVED, because it is not a session. It exists to carry one confirmation from the PIN prompt
to the save a few seconds later. An hour would let a tablet left on a counter file work all evening
under a name whose owner went home.

AND IT IS NOT A CAPABILITY. The bearer token still decides what may be done at all; this only says
WHO among the shop's own staff is doing it. A forged ticket buys nothing a caller could not already
do — it buys attributing it to somebody else, which is the whole point.
"""
from __future__ import annotations

import hashlib
import hmac
import time

#: Long enough for a slow save on a bad connection, short enough that a tablet left unattended
#: stops being somebody else's signature.
TTL_SECONDS = 300


def issue(salt: str, tenant: str, operator_id: str, *, now: int | None = None,
          ttl: int = TTL_SECONDS) -> str:
    """A ticket for this operator, good for `ttl` seconds."""
    expires = int(now if now is not None else time.time()) + int(ttl)
    return f"{expires}.{_sign(salt, tenant, operator_id, expires)}"


def verifies(salt: str, tenant: str, operator_id: str, ticket: str,
             *, now: int | None = None) -> bool:
    """Does this ticket prove this operator, in this establishment, right now?"""
    if not salt or not tenant or not operator_id or not ticket:
        return False
    head, _, mac = ticket.partition(".")
    if not mac or not head.isdigit():
        return False
    expires = int(head)
    if expires < int(now if now is not None else time.time()):
        return False
    # compare_digest, because a naive `==` on a hex string leaks how much of a forgery was right.
    return hmac.compare_digest(_sign(salt, tenant, operator_id, expires), mac)


def _sign(salt: str, tenant: str, operator_id: str, expires: int) -> str:
    return hmac.new(salt.encode("utf-8"),
                    f"ticket|{tenant}|{operator_id}|{expires}".encode("utf-8"),
                    hashlib.sha256).hexdigest()
