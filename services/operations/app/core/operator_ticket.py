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

AND IT IS A WINDOW, NOT A DEADLINE (أ-3). The screen this serves is the one that keeps working with
no network: a visit taken at noon in a workshop with no signal is queued on the device and drains
when the signal returns, sometimes hours later. Checking the ticket against the CLOCK AT ARRIVAL
would drop the operator off every one of those visits — silently, because dropping attribution is
not an error — so the shop with the worst connection is the one whose branch table stays empty.
What is checked instead is that THE MOMENT BEING ATTRIBUTED falls inside the window the PIN opened.
The window is still five minutes of work: a ticket cannot claim yesterday, and holding one for a
week buys nothing but those same five minutes, which have already passed.

AND IT IS NOT A CAPABILITY. The bearer token still decides what may be done at all; this only says
WHO among the shop's own staff is doing it. A forged ticket buys nothing a caller could not already
do — it buys attributing it to somebody else, which is the whole point.
"""
from __future__ import annotations

import hashlib
import hmac
import time

from app.core.digits import WESTERN

#: Long enough for a slow save on a bad connection, short enough that a tablet left unattended
#: stops being somebody else's signature.
TTL_SECONDS = 300

#: How long a queued visit may still carry the ticket it was taken under. It bounds the REPLAY, not
#: the work: whatever arrives with this ticket is still only attributable inside the five minutes
#: above. A device off the network for longer than this has a bigger problem than attribution, and
#: `_sane_occurred_at` refuses the backdating anyway.
GRACE_SECONDS = 7 * 24 * 3600


def issue(salt: str, tenant: str, operator_id: str, *, now: int | None = None,
          ttl: int = TTL_SECONDS) -> str:
    """A ticket for this operator, good for work done in the next `ttl` seconds."""
    opened = int(now if now is not None else time.time())
    expires = opened + int(ttl)
    return f"{opened}.{expires}.{_sign(salt, tenant, operator_id, opened, expires)}"


def _plain(part: str) -> bool:
    """Every character is 0-9 — the shape this module's own signer emits, and no other."""
    return bool(part) and all(c in WESTERN for c in part)


def verifies(salt: str, tenant: str, operator_id: str, ticket: str,
             *, at: int | None = None, now: int | None = None) -> bool:
    """Does this ticket prove this operator, in this establishment, for the work done at `at`?

    `at` is when the work HAPPENED — the device's own clock at the moment of saving. It defaults to
    arrival, which is right for a live save and wrong for a drained one; see the note on windows.
    """
    if not salt or not tenant or not operator_id or not ticket:
        return False
    parts = ticket.split(".")
    # 0-9 ONLY, EXPLICITLY. `str.isdigit()` is true for ARABIC-INDIC DIGIT FIVE, and `int()` of
    # carrying another script's digits parsed here. The MAC still refused it, which is why this is
    # a hardening and not a hole — but a parser that accepts what the signer never emits is one
    # surprise away from being one.
    if len(parts) != 3 or not _plain(parts[0]) or not _plain(parts[1]):
        return False
    opened, expires, mac = int(parts[0]), int(parts[1]), parts[2]
    clock = int(now if now is not None else time.time())
    moment = int(at) if at else clock
    if not opened <= moment <= expires:
        return False
    if clock > expires + GRACE_SECONDS:
        return False
    # compare_digest, because a naive `==` on a hex string leaks how much of a forgery was right.
    return hmac.compare_digest(_sign(salt, tenant, operator_id, opened, expires), mac)


def _sign(salt: str, tenant: str, operator_id: str, opened: int, expires: int) -> str:
    return hmac.new(salt.encode("utf-8"),
                    f"ticket|{tenant}|{operator_id}|{opened}|{expires}".encode("utf-8"),
                    hashlib.sha256).hexdigest()


def pin_hash(salt: str, tenant: str, operator_id: str, pin: str) -> str:
    """Salted and bound to the operator — moved here from `api/v1/staff.py` (2026-09-14) so a
    second caller (the till's own `POST /till/operators/verify-pin`) hashes a PIN exactly the same
    way instead of growing a second, independently-maintained copy of this formula.

    Bound to (tenant, operator_id) so the same four digits produce different hashes for different
    people — otherwise a leaked table would show at a glance which operators share a PIN, and
    "1234" would be identifiable across every establishment we host.
    """
    return hmac.new(salt.encode("utf-8"),
                    f"{tenant}|{operator_id}|{pin}".encode("utf-8"),
                    hashlib.sha256).hexdigest()
