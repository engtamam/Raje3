"""The global, anonymous referral code — Phase 1 of
docs/خطة-تطبيق-الإحالة-والمسوقين-2026-09-27.md.

WHAT THIS IS, AND WHY IT LIVES HERE. Every phone number that ever passes through any shop's own
referral program gets exactly one short code, for the life of the platform. The code is a MASK for
the phone number, never the other way around: the whole point is that nobody — not a shop, not a
console screen, not this service's own admin — ever has to show, type, or store a phone number in
the open to run a referral program. `{phone -> code}` is the ONLY fact this module keeps; who
referred whom, what reward applies, and every real referral relationship live entirely inside each
tenant's own isolated collections elsewhere in this service, referencing the code as an opaque
string.

WHY NOT `identity-service` (the original design). That service lives in `platform/` — a vendored,
shared codebase this repo never edits directly; any change there needs a request to its own team.
There is no real technical reason the mapping had to live there: the phone normalizer is a plain,
already-duplicated-everywhere function (`app/core/phone.py`, copied from `services/coworking`, same
as `services/operations/app/core/signup.py::canonical_phone`), and this service already owns a full
datastore of its own from Phase 0. Keeping it here means zero cross-team dependency and zero risk
to the actual identity system — this module never touches an account, a session, or a login.

THE CODE'S OWN SHAPE (owner's own spec): 5 characters. The FIRST is always a letter — a quick visual
tell that this is a code, not a plain number, at a glance on a till screen or a WhatsApp message.
The alphabet excludes '0' and 'O' (visually near-identical in most fonts a phone or a receipt
printer renders) — 25 letters + 9 digits = 34 symbols per non-first slot, 25 for the first. That is
25 x 34^4 = 334,084,000 possible 5-character codes. The length grows to 6 (and beyond, the same
way) only once 5-character space genuinely starts running out — see `_LENGTH_ESCALATION_STREAK`'s
own note below for how that is detected without an expensive global count. A length change never
invalidates an existing shorter code: lookup is exact-string equality, never fixed-width, so codes
of different lengths coexist forever.

MINTING IS A TWO-PHASE CLAIM, NOT A READ-THEN-WRITE. `datastore.claim()` (added 2026-09-07,
originally for campaigns'/coworking's own double-booking/double-payout locks) is the one primitive
that makes "is this key already taken" and "take it" one atomic act instead of two round trips a
race can land between — see this service's own `tests/contracts/test_datastore_contract.py` for the
concurrency proof this file's own tests rely on. Two collections, two claims:

  1. Claim the PHONE key itself first (in `_BY_PHONE`) — this is what stops two concurrent
     mint-or-fetch calls for the SAME new phone from each generating and reserving a DIFFERENT
     code. The loser of this claim does not error: it retries a plain read a bounded number of
     times, because losing the claim means "someone else is minting this phone's code right now,
     wait for it," not "this phone is invalid."
  2. Only the winner of #1 then claims a randomly generated CODE in `_BY_CODE` (the reverse index)
     — this is what stops two DIFFERENT phones from ever ending up sharing one code. A collision
     here is expected and cheap: generate another candidate and try again.

Both claims use a TTL of "effectively forever" (`_PERMANENT_TTL_SECONDS`) rather than the short
transient window a booking lock uses — this is not a lock guarding one confirm, it is the record
itself, and `claim()` is simply the one atomic primitive this port already offers for "write only if
nobody has this key yet."
"""
from __future__ import annotations

import asyncio
import secrets
import time
from typing import Any

from app.core.phone import canonical_phone

#: `O` excluded (looks like `0`, which is excluded from the digit half for the same reason).
_LETTERS = "ABCDEFGHIJKLMNPQRSTUVWXYZ"
_DIGITS = "123456789"
_ALPHABET = _LETTERS + _DIGITS

_DEFAULT_LENGTH = 5

# THIS IS A RECORD, NOT A LOCK — the claim never expires in practice. A gigantic TTL (~317 years)
# is a deliberate choice over inventing a second, non-expiring primitive on the same port: `claim()`
# already IS "insert-if-absent-or-expired," and a TTL this size is expiry in name only.
_PERMANENT_TTL_SECONDS = 10_000_000_000.0

# HOW MANY TIMES A LOSER OF THE PHONE-CLAIM RE-READS BEFORE GIVING UP — same shape and same
# reasoning as campaigns' own `_MUTEX_RETRY_ATTEMPTS`/`_MUTEX_RETRY_DELAY_SECONDS`
# (services/campaigns/app/core/milestone.py): the winner's own write (claim, generate, claim again,
# then finalize) is a handful of awaits, never seconds — a short, tight retry window resolves the
# overwhelming majority of races well within it.
_PHONE_RETRY_ATTEMPTS = 150
_PHONE_RETRY_DELAY_SECONDS = 0.01

# HOW MANY COLLISIONS AT ONE LENGTH BEFORE GROWING TO THE NEXT — a cheap, self-adjusting substitute
# for an expensive exact count of every code ever minted (this port has no `count()`, and counting a
# collection that could hold hundreds of millions of rows on every mint would not be cheap even if
# it did). At any real fill level well short of exhaustion, a random draw collides on almost the
# first try; a run of this many CONSECUTIVE collisions is only plausible once the space is genuinely
# nearly full, and growing one character multiplies the space by 34x — comfortably ahead of demand.
_LENGTH_ESCALATION_STREAK = 20

BY_PHONE = "referral_codes_by_phone"
BY_CODE = "referral_phones_by_code"


class CodeMintFailed(Exception):
    """Fails closed: contention or exhaustion, never a silently wrong or duplicate code."""


def _generate_code(length: int) -> str:
    first = secrets.choice(_LETTERS)
    rest = "".join(secrets.choice(_ALPHABET) for _ in range(length - 1))
    return first + rest


async def code_for_phone(datastore: Any, raw_phone: str, *, now: float | None = None) -> str:
    """The one entry point — idempotent: the same phone always gets the same code back, minted
    fresh only the first time it is ever seen. Raises `CodeMintFailed` on an empty/unparseable
    phone or on genuine contention/exhaustion; never returns an empty or partial code."""
    phone = canonical_phone(raw_phone)
    if not phone:
        raise CodeMintFailed("رقم جوال غير صالح")

    existing = await datastore.get(BY_PHONE, phone)
    if existing and existing.get("code"):
        return existing["code"]

    now = time.time() if now is None else now
    won = await datastore.claim(BY_PHONE, phone, {"phone": phone, "code": ""},
                                ttl_seconds=_PERMANENT_TTL_SECONDS, now=now)
    if not won:
        # SOMEONE ELSE IS MINTING THIS PHONE'S CODE RIGHT NOW (or already did, and we simply read
        # before they finished) — wait for the winner, never invent a second code for this phone.
        for _ in range(_PHONE_RETRY_ATTEMPTS):
            row = await datastore.get(BY_PHONE, phone)
            if row and row.get("code"):
                return row["code"]
            await asyncio.sleep(_PHONE_RETRY_DELAY_SECONDS)
        raise CodeMintFailed("تعذّر إصدار الكود — حاول مرة أخرى")

    length = _DEFAULT_LENGTH
    streak = 0
    while True:
        candidate = _generate_code(length)
        code_won = await datastore.claim(BY_CODE, candidate, {"phone": phone, "code": candidate},
                                         ttl_seconds=_PERMANENT_TTL_SECONDS, now=now)
        if code_won:
            await datastore.put(BY_PHONE, phone, {"phone": phone, "code": candidate})
            return candidate
        streak += 1
        if streak >= _LENGTH_ESCALATION_STREAK:
            length += 1
            streak = 0


async def phone_for_code(datastore: Any, code: str) -> str | None:
    """The reverse lookup a till/redemption path needs (Phase 3) — the code alone is meaningless
    without it. Returns `None` for an unknown code, never raises: an invalid code typed at a till is
    an ordinary, expected refusal path for the caller to word, not this module's problem to phrase."""
    row = await datastore.get(BY_CODE, (code or "").strip().upper())
    return row["phone"] if row else None
