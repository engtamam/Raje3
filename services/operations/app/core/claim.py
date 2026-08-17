"""The shop that arrives through its till — invited by the partner, opened by its owner.

WHY THE PARTNER CANNOT SIMPLY CREATE THE ACCOUNT, which is the obvious design and the wrong one.

Somebody has to choose a password. If it is not the owner, it is the till company — and whoever
holds it holds the shop: they can connect its WhatsApp, subscribe it, message its customers in its
name, and read every number in it. That is not a partnership, it is a set of keys handed to a
supplier because it was convenient at signup.

So the partner's call creates NO ACCOUNT. It records an invitation and sends the owner a message.
He proves his number, chooses his own password, and the ordinary signup saga runs from there —
the same one a shop that found us on its own goes through, with two differences it does not choose:

    catalogue   built from his own invoices (§4.2) rather than typed, and asking a
                till company to pick a trade on its customer's behalf is a guess written into
                somebody else's data
    stamp       the partner key, which is what decides the commission — and it is written ONCE
                and never rewritten (core/partners.py)

────────────────────────────────────────────────────────────────────────────────────────────────
THE INVITATION EXPIRES

Seven days. An invitation that never expires is a way into a shop that nobody remembers issuing:
the till company changes staff, the record survives, and a claim arrives a year later for a shop
that has since signed up on its own. The window is long enough for an owner who pressed a button
on a Thursday and read his messages on Sunday.

AND IT IS SINGLE USE. Claiming consumes it — an invitation that worked twice would be a password
reset for anybody who ever saw the message.

────────────────────────────────────────────────────────────────────────────────────────────────
AND IT ANSWERS THE SAME WAY WHETHER OR NOT THE NUMBER IS KNOWN

The partner's route is internal-tier, so it may say plainly that a shop already exists. The
OWNER's route may not: it is public, and telling one caller "no invitation for this number" and
another "wrong code" is an answer to "which numbers has a till company registered", one request at
a time.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

CLAIMS = "partner_claims"

# SEVEN DAYS. See the module note — long enough for a Thursday button and a Sunday reading, short
# enough that a forgotten invitation is not a permanent way in.
TTL_SECONDS = 7 * 86400


class ClaimError(Exception):
    """A refusal, in the sentence its reader can act on."""


@dataclass(frozen=True)
class Invitation:
    phone: str
    shop_name: str
    # THE RESOLVED PARTNER ID, NEVER THE RAW KEY (ك-5). See `Claims.invite` below.
    partner_id: str
    created: int
    expires: int

    def alive(self, now: int) -> bool:
        return now < self.expires


class Claims:
    """The pending invitations. One row per canonical phone — a second invitation for the same
    number REPLACES the first rather than queueing behind it, because two live invitations for one
    shop is a state nobody can reason about."""

    def __init__(self, store) -> None:
        self._s = store

    async def invite(self, *, phone: str, shop_name: str, partner_id: str,
                     now: int, ttl: int = TTL_SECONDS) -> Invitation:
        """Record the invitation with the partner ALREADY RESOLVED, never the bearer key itself.

        `partners.py` states its own rule plainly: a partner key is «shown once, stored hashed».
        This row used to hold the raw key for up to seven days — the invitation's whole TTL — in a
        collection with none of that module's hashing, because resolving it happened at CLAIM time,
        days later. `core/signup.py.invite_partner_shop` now resolves it the moment the till company
        calls, and only the id — worthless to steal, since attributing a shop needs no secret once
        it is your own partner id in your own row — lives here for the week the invitation is open.
        """
        inv = Invitation(phone=phone, shop_name=shop_name, partner_id=partner_id,
                         created=now, expires=now + ttl)
        await self._s.put(CLAIMS, phone, {
            "id": phone, "phone": phone, "shop_name": shop_name,
            "partner_id": partner_id, "created": inv.created, "expires": inv.expires,
        })
        return inv

    async def get(self, phone: str) -> Invitation | None:
        row = await self._s.get(CLAIMS, phone)
        if not row:
            return None
        return Invitation(phone=str(row.get("phone") or ""),
                          shop_name=str(row.get("shop_name") or ""),
                          partner_id=str(row.get("partner_id") or ""),
                          created=int(row.get("created") or 0),
                          expires=int(row.get("expires") or 0))

    async def consume(self, phone: str) -> None:
        """Single use — see the module note."""
        await self._s.delete(CLAIMS, phone)


def check(inv: Invitation | None, *, now: int) -> Invitation:
    """The invitation, or one refusal for every way it can be absent.

    UNKNOWN, EXPIRED AND ALREADY-CLAIMED COLLAPSE INTO ONE ANSWER, and the sentence names neither.
    Told apart, they answer "has a till company registered this number" to anyone who asks — and
    the person who legitimately holds an invitation is not helped by learning which of the three
    happened, because in all three his next step is the same: ask the till company again.
    """
    if inv is None or not inv.alive(now):
        raise ClaimError("لا توجد دعوة صالحة لهذا الرقم. تواصل مع مزوّد نظام الكاشير.")
    return inv
