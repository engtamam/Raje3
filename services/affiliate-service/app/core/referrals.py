# =============================================================================
# affiliate-service — stamping WHICH establishment WHICH affiliate brought (spec §4)
# -----------------------------------------------------------------------------
# THE FACT THIS FILE OWNS, AND WHY IT LIVES HERE RATHER THAN IN OPERATIONS. operations already has
# an identical mechanism for till-company partners (core/partners.py) — first-key-wins, permanent,
# a DIRECT sentinel for a shop that signed up on its own. Reusing that module directly would
# conflate two different relationships under one row: a partner is a BEARER-KEY-authenticated
# company earning a PERCENTAGE of what a shop pays; an affiliate is an IDENTITY-authenticated
# person earning a FLAT amount per shop, with a manager/promoter hierarchy that has no partner
# equivalent at all. So operations calls this service once, at signup, with the raw fact (which
# affiliate id was on the link) — the same shape as the stamp it already writes for a partner key,
# just handed to the service that actually owns marketer commission.
#
# FIRST WINS, PERMANENT — copied deliberately from partners.py's own reasoning, word for word in
# spirit: a shop that read a marketer's WhatsApp message, signed up, and months later happens to
# click a DIFFERENT marketer's link (a review site, a forwarded message) must not silently move
# the commission to whoever's link was clicked most recently. The marketer who actually brought
# the shop is decided once, at signup, and never rewritten by a later touch.
# =============================================================================
from __future__ import annotations

import time
from typing import Any

from app.core.models import ACTIVE, AFFILIATES, LAPSED, REFERRALS, REFERRED, Affiliate, Referral
from app.core.phone import canonical_phone


class ReferralError(Exception):
    """A refusal the internal caller (operations) can log and move on from — never raised into
    a shop signup; see the module docstring and operations' own stamp_error precedent for why an
    attribution hiccup must not cost an owner his shop."""


_DAY = 24 * 60 * 60


class ReferralRegistry:
    def __init__(self, *, store, commission_amount_halalas: int = 0,
                 conversion_window_days: int = 90, default_cc: str = "966") -> None:
        self._s = store
        self._amount = commission_amount_halalas
        self._window = conversion_window_days
        self._cc = default_cc

    async def stamp(self, *, tenant: str, affiliate_id: str, shop_name: str = "",
                    shop_owner_phone: str = "") -> dict[str, Any]:
        if not tenant:
            raise ReferralError("cannot stamp without a tenant")
        if not affiliate_id:
            raise ReferralError("cannot stamp without an affiliate id")

        existing = await self.of_tenant(tenant)
        if existing is not None:
            # ALREADY DECIDED — see the module docstring. Returned as-is, whether the affiliate id
            # matches or not; a mismatch is not an error, it is exactly the scenario the rule
            # exists to resolve (a second marketer's link, touched after the first already won).
            return existing.to_dict()

        row = await self._s.get(AFFILIATES, affiliate_id)
        affiliate = Affiliate.from_dict(row) if row else None
        if affiliate is None or affiliate.status != ACTIVE:
            # AN UNKNOWN OR INACTIVE AFFILIATE ID IS REFUSED, never silently treated as "no
            # referral" — same reasoning as partners.py's own resolve(): a stale or mistyped link
            # must be visible as a fault, not swallowed into a shop that looks directly-acquired
            # when someone genuinely tried to refer it.
            raise ReferralError(f"unknown or inactive affiliate: {affiliate_id}")

        # SELF-REFERRAL, spec §2: "يُتحقق أن رقم جوال صاحب المحل ≠ رقم جوال المسوّق نفسه" — a
        # marketer opening a shop on his own number and crediting himself is a fabricated
        # commission, not a real referral. Both numbers folded the SAME way (app/core/phone.py)
        # before comparing, or two spellings of one number pass this check by accident. An empty
        # `shop_owner_phone` (an old caller that predates this field) is NOT a match — it cannot
        # prove self-referral, so it must not manufacture a false refusal either.
        if shop_owner_phone:
            owner = canonical_phone(shop_owner_phone, default_cc=self._cc)
            marketer = canonical_phone(affiliate.phone, default_cc=self._cc)
            if owner and marketer and owner == marketer:
                raise ReferralError("an affiliate cannot refer their own establishment")

        now = int(time.time())
        referral = Referral(
            id=tenant, tenant=tenant, affiliate_id=affiliate_id, shop_name=shop_name,
            commission_amount_halalas=self._amount, stamped_at=now,
            expires_at=now + self._window * _DAY,
        )
        await self._s.put(REFERRALS, referral.id, referral.to_dict())
        return referral.to_dict()

    async def lapse_if_expired(self, tenant: str, *, now: int | None = None) -> Referral | None:
        """Called by the COMMISSION ENGINE (a later slice) the moment a shop's subscription
        actually turns into real, paid revenue — never by a background sweep. Nothing needs to
        know a referral has lapsed until somebody is about to pay it, so there is nothing to sweep
        for; checking at that one moment is both simpler and correct.

        Flips REFERRED -> LAPSED past `expires_at` and returns the row either way (None only if
        no referral exists at all), so the caller has one place to read "may I pay this" from:
        `row.status == REFERRED`.
        """
        referral = await self.of_tenant(tenant)
        if referral is None or referral.status != REFERRED:
            return referral
        if (now if now is not None else int(time.time())) <= referral.expires_at:
            return referral
        referral.status = LAPSED
        await self._s.put(REFERRALS, referral.id, referral.to_dict())
        return referral

    async def of_tenant(self, tenant: str) -> Referral | None:
        row = await self._s.get(REFERRALS, tenant)
        return Referral.from_dict(row) if row else None

    async def all_referred(self, *, limit: int = 500) -> list[Referral]:
        """Every referral still eligible for a commission — the sweep's own worklist
        (core/commission.py's sync() is a no-op for LAPSED/REVOKED, so there is nothing to gain
        syncing those; excluding them here keeps the sweep's one bounded read from growing with
        the platform's whole referral history instead of just what is still live)."""
        rows, _ = await self._s.find(REFERRALS, {"status": REFERRED}, limit=limit,
                                     sort=("stamped_at", "asc"))
        return [Referral.from_dict(r) for r in rows]

    async def of_affiliate(self, affiliate_id: str, *, limit: int = 200) -> list[Referral]:
        """Every establishment THIS affiliate brought — the input to a dashboard/statement (a
        later slice). Scoped by `affiliate_id`, never by tenant: unlike a shop's own data, a
        Referral has no tenant of its own to isolate by — it belongs to the affiliate who earned
        it, and that is the only boundary that matters here."""
        rows, _ = await self._s.find(REFERRALS, {"affiliate_id": affiliate_id}, limit=limit,
                                     sort=("stamped_at", "asc"))
        return [Referral.from_dict(r) for r in rows]
