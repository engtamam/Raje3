"""A code per customer per offer — the only thing that measures whether an offer WORKED.

WHAT WE COULD MEASURE BEFORE THIS, AND WHAT WE COULD NOT. The run report counts what went out:
«وصلت 47 عميلاً». Nobody has ever asked a shop owner to be impressed by that. What he pays to know
is how many of the 47 came back and spent it — and an offer with no handle on it cannot be counted
at the till, because nothing at the counter distinguishes «عرض وصلني» from «سمعت عنه».

WHY IT IS DERIVED AND NOT STORED. The code is a function of the send's own idempotency key, so:

  · a retry after a timeout produces the SAME code — the customer does not receive two;
  · nothing has to be written, reconciled, or cleaned up when a message is never sent;
  · and the code cannot drift from the row it belongs to, because it IS the row, hashed.

THE ALPHABET IS THE POINT. A code is read aloud across a counter by somebody who is not looking at
the screen, and typed back by somebody who is. So: no O against 0, no I or L against 1, no letters
that are a hand's slip apart in Arabic-keyboard Latin. Twenty-eight symbols, six characters, in two
groups of three — one of the shapes a person can hold in their head long enough to say it.
"""
from __future__ import annotations

import hashlib

# Crockford-ish, minus the pairs a person confuses when reading aloud: 0/O, 1/I/L, and the
# vowels that turn a random code into an accidental word.
ALPHABET = "23456789BCDFGHJKMNPQRSTVWXYZ"
PREFIX = "RJ"
LENGTH = 6


def code_for(idempotency_key: str) -> str:
    """The coupon this send carries. Same key, same code, for ever.

    NOT RANDOM, DELIBERATELY. A random code needs a store, and a store needs a write on the send
    path — one more thing that can fail between deciding to send and sending. This needs neither.
    """
    if not idempotency_key:
        return ""
    digest = hashlib.sha256(idempotency_key.encode("utf-8")).digest()
    out = []
    for byte in digest[:LENGTH]:
        out.append(ALPHABET[byte % len(ALPHABET)])
    body = "".join(out)
    return f"{PREFIX}-{body}"


def looks_like_code(value: str) -> bool:
    """Whether a string a person typed at a till is one of ours — checked before a lookup.

    A CHEAP REFUSAL BEFORE AN EXPENSIVE READ. The till screen accepts free text, and «خصم» typed
    into it must not become a scan of the send log.
    """
    v = (value or "").strip().upper()
    if not v.startswith(PREFIX + "-"):
        return False
    body = v[len(PREFIX) + 1:]
    return len(body) == LENGTH and all(c in ALPHABET for c in body)


def normalise(value: str) -> str:
    """What the customer said, as the code we issued.

    He reads it off his phone and the operator types it: lowercase, spaces around the dash, a
    missing dash. All of those are the same code, and refusing them would be refusing a customer
    holding a valid offer over our own formatting.
    """
    v = (value or "").strip().upper().replace(" ", "")
    if v.startswith(PREFIX) and not v.startswith(PREFIX + "-"):
        v = f"{PREFIX}-{v[len(PREFIX):]}"
    return v
