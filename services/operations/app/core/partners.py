"""Who brought this establishment to us — and the rule that decides where the money goes.

A POS company that puts our add-on in front of five hundred shops earns a share of what those shops
pay. That is the whole commercial model (spec §16.6.3), and it rests on one fact per establishment:
who brought it. Get that fact wrong and we pay the wrong company, or pay twice, or pay for a shop
nobody brought.

THE STAMP IS WRITTEN ONCE AND NEVER REWRITTEN. This is the only rule here that matters, and it is
the one that a normal `upsert` would quietly break.

Consider what last-write-wins would mean. A shop signs up through partner A. Six months later it
switches till software to partner B, which integrates and sends its own key. Under last-write-wins,
B now earns the commission on a customer it never brought — and A, which did bring it, stops being
paid. Nothing errors. Nothing is logged. Money simply starts flowing to whoever called most
recently, which is a rule nobody would ever write down but every naive implementation has.

So: the first partner key to arrive stamps the establishment permanently. Every later key is
recorded as a `seen_also` and changes nothing about attribution.

AND A SHOP THAT SIGNED UP DIRECTLY IS STAMPED TOO — with an empty partner. That is not the same as
being unstamped: "we brought this one ourselves" is a decided fact, and it is what stops a partner
who integrates a month later from claiming a shop our own marketing paid for.

DEACTIVATING A PARTNER DOES NOT UNSTAMP ITS SHOPS. They came through it once, and a falling-out
does not rewrite history. What deactivation stops is NEW stamps and, separately, whether we keep
paying — which is a billing decision, not a data one.

THE KEY IS A BEARER CREDENTIAL AND IS STORED HASHED. Anyone holding it can attribute an
establishment, which is anyone holding it can direct money. It is shown once, at creation, and
never again — the same treatment as any other secret, and for the same reason.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from typing import Any

PARTNERS = "partners"
STAMPS = "partner_stamps"
# One registry for the whole product, under the reserved tenant — the same pattern as sectors and
# templates. A partner is not owned by any establishment.
PLATFORM = "_platform"

# What a directly-acquired establishment is stamped with. A REAL VALUE, not an absent one: an empty
# stamp row and no stamp row must not look the same, because only one of them means "decided".
DIRECT = "_direct"


class PartnerError(Exception):
    """A refusal a console user can act on."""


def _hash_key(key: str, salt: str) -> str:
    """Hash a partner key for storage.

    HMAC with the platform salt rather than a bare digest: a bare SHA-256 of a key is offline-
    guessable if the key space is ever narrowed, and the salt is already a shared secret every
    service holds.
    """
    return hmac.new(salt.encode(), key.encode(), hashlib.sha256).hexdigest()


class PartnerRegistry:
    def __init__(self, store, *, salt: str) -> None:
        self._s = store
        self._salt = salt

    # ── the registry ──────────────────────────────────────────────────────────────────────────
    async def create(self, *, name: str, commission_rate: float,
                     contact: str = "") -> tuple[dict[str, Any], str]:
        """Register a partner. Returns the row and the PLAINTEXT key, which is shown once."""
        name = (name or "").strip()
        if not name:
            raise PartnerError("a partner needs a name — it appears on every statement")
        if not 0 < commission_rate < 1:
            raise PartnerError(
                f"commission_rate must be a fraction between 0 and 1, got {commission_rate}. "
                f"A rate of 30 rather than 0.3 would pay a partner thirty times the subscription.")

        partner_id = f"prt_{secrets.token_hex(8)}"
        # 32 bytes of urandom. Long enough that guessing is not a threat model, and the reason the
        # stamp can be trusted at all.
        key = f"rj3_{secrets.token_urlsafe(32)}"
        row = {
            "id": partner_id, "tenant": PLATFORM, "name": name, "contact": contact,
            "key_hash": _hash_key(key, self._salt),
            # A PREFIX, stored in the clear, so a console can show which key a partner is using
            # without being able to reconstruct it. Support needs to identify a key; nobody needs
            # to read one.
            "key_prefix": key[:12],
            "commission_rate": float(commission_rate),
            "active": True,
            "created": int(time.time()),
        }
        await self._s.put(PARTNERS, f"{PLATFORM}|{partner_id}", row)
        return row, key

    async def get(self, partner_id: str) -> dict[str, Any] | None:
        return await self._s.get(PARTNERS, f"{PLATFORM}|{partner_id}")

    async def list(self) -> list[dict[str, Any]]:
        rows, _ = await self._s.find(PARTNERS, {"tenant": PLATFORM}, limit=500,
                                     sort=("created", "desc"))
        # The hash never leaves this module. A console that can display it can leak it into a log,
        # a screenshot, or a support ticket.
        return [{k: v for k, v in r.items() if k != "key_hash"} for r in rows]

    async def deactivate(self, partner_id: str) -> bool:
        """Stop NEW stamps. Existing ones are untouched — see the module docstring."""
        row = await self.get(partner_id)
        if row is None:
            return False
        row["active"] = False
        row["deactivated"] = int(time.time())
        await self._s.put(PARTNERS, f"{PLATFORM}|{partner_id}", row)
        return True

    async def resolve(self, key: str) -> dict[str, Any] | None:
        """Find the partner a key belongs to, or None.

        Scans the registry and compares hashes in constant time. A scan is acceptable here and
        nowhere else: partners are counted in dozens, not millions, and this runs once per
        establishment rather than once per request.
        """
        if not key:
            return None
        wanted = _hash_key(key, self._salt)
        rows, _ = await self._s.find(PARTNERS, {"tenant": PLATFORM}, limit=500)
        for row in rows:
            # compare_digest, not ==. A short-circuiting comparison on a credential hash leaks its
            # prefix through timing, and the cost of doing it right is nothing.
            if hmac.compare_digest(row.get("key_hash", ""), wanted):
                return row
        return None

    # ── the stamp ─────────────────────────────────────────────────────────────────────────────
    async def stamp(self, tenant: str, *, key: str = "") -> dict[str, Any]:
        """Attribute an establishment. IDEMPOTENT, AND FIRST WINS.

        Called on tenant creation and on the first integration call. Passing no key stamps the
        establishment as directly acquired, which is a decision rather than an absence.
        """
        if not tenant:
            raise PartnerError("cannot stamp without a tenant")

        existing = await self.stamp_of(tenant)
        partner = await self.resolve(key) if key else None

        if existing is not None:
            # ALREADY DECIDED. A different key arriving later is recorded so support can answer
            # "why is this shop attributed to A when B integrated it?", and it changes nothing.
            if partner and partner["id"] != existing.get("partner_id"):
                seen = list(existing.get("seen_also") or [])
                if partner["id"] not in seen:
                    seen.append(partner["id"])
                    existing["seen_also"] = seen
                    existing["updated"] = int(time.time())
                    await self._s.put(STAMPS, f"{tenant}|stamp", existing)
            return existing

        if key and partner is None:
            # An unknown key is REFUSED rather than silently treated as a direct signup. Silently
            # downgrading it would mean a partner whose key was mistyped in a deployment sees its
            # shops attributed to us, and would have no way to discover why.
            raise PartnerError("unknown partner key")
        if partner is not None and not partner.get("active", True):
            raise PartnerError(f"partner {partner['name']} is not active — its key cannot be used "
                               f"to onboard new establishments")

        row = {
            "id": f"{tenant}|stamp", "tenant": tenant,
            "partner_id": partner["id"] if partner else DIRECT,
            "partner_name": partner["name"] if partner else "",
            "commission_rate": float(partner["commission_rate"]) if partner else 0.0,
            "seen_also": [],
            "stamped_at": int(time.time()),
        }
        await self._s.put(STAMPS, f"{tenant}|stamp", row)
        return row

    async def stamp_of(self, tenant: str) -> dict[str, Any] | None:
        return await self._s.get(STAMPS, f"{tenant}|stamp")

    async def tenants_of(self, partner_id: str) -> list[str]:
        """Which establishments a partner brought — the input to its statement.

        Reads stamps rather than a list kept on the partner: a denormalised list is a second place
        the truth lives, and the day it disagrees with the stamps is the day somebody is paid for a
        shop they did not bring.
        """
        rows, _ = await self._s.find(STAMPS, {"partner_id": partner_id}, limit=5000,
                                     sort=("stamped_at", "asc"))
        return [r.get("tenant", "") for r in rows if r.get("tenant")]
