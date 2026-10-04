"""The unified "what is this phone entitled to, right now" read -- a STANDALONE function, called
explicitly by whichever app needs it, BEFORE its own payment/confirmation moment. Deliberately NOT
wired inside `record_visit()` itself: that function already has its own established, manual,
cashier-triggered offer flow (`Operations.apply_offer`/`core/entitlements.py::EntitlementGateway`,
a button the till presses AFTER a visit exists) -- embedding this here would either duplicate that
flow or silently race it. This module exists for the newer, automatic, pre-payment moment
WhatsApp Direct Ordering needs (and any future instant-checkout flow like it); the till's own
manual flow is untouched, on purpose.

MONEY ONLY, NEVER STACKED. Two money sources are compared here -- a live campaign discount
(reminders' `SendLog`) and a referral welcome discount (`referral_redemption.py::ReferralGrant`,
`new_customer_reward_type == "discount_percent"`) -- by real SAR value, and the higher one is
returned. A caller applies it automatically and silently; see `orders.py`'s own notes on WHEN the
winning offer is actually spent (never at the pricing moment, only once payment is confirmed).

LOYALTY POINTS ARE DELIBERATELY OUT OF THIS FUNCTION'S SCOPE for now -- a redeemable points reward
has no expiry the way a discount does, so it must only ever be the CUSTOMER's own choice, never
auto-applied, which needs a real "do you want to use your points?" conversational step a caller
does not yet have. Flagged here rather than silently half-built: adding it is a caller-side UX
project, not a change to this function's own contract.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.referral_redemption import NEW_CUSTOMER_DISCOUNT_PERCENT
from app.core.reward_value import scoped_value as _scoped_value


@dataclass(frozen=True)
class OfferDecision:
    discount_minor: int = 0
    # "" | "campaign:{send_log_id}" | "referral:{phone}" -- empty means no live money offer.
    discount_source: str = ""
    # What a later redeem call needs -- the send-log id for a campaign offer, the phone itself
    # for a referral grant (`ReferralRedemptionEngine.redeem` is keyed on phone, not a grant id).
    discount_ref: str = ""


async def best_offer_for(*, tenant: str, phone: str, subject_ref: str, invoice_minor: int,
                         line_minor: dict[str, int] | None = None,
                         discounts: Any = None, operations: Any = None) -> OfferDecision:
    """`discounts` is the `{find, redeem}` pair `adapters/discount_desk.py` builds (campaign
    source); `operations` is anything exposing `referral_discount_for(tenant, phone)` (the
    `Operations` class itself, see that method's own docstring -- a thin, read-only passthrough to
    `ReferralRedemptionEngine.eligibility`). Both are `None`-safe: a caller that wires neither
    simply never finds a discount, the same "nothing configured, no gap to explain" posture every
    optional peer in this fleet already holds.

    A PEER FAILURE MEANS "NO DISCOUNT THIS ATTEMPT", NEVER A REFUSAL -- an unreachable campaign or
    referral peer must not stop the caller's own transaction; it must simply not promise a
    discount we could not verify (same posture `adapters/discount_desk.py`'s own module docstring
    takes, mirrored here for the referral side too).
    """
    line_minor = line_minor or {}
    candidates: list[OfferDecision] = []

    if discounts is not None and subject_ref:
        try:
            discount = await discounts["find"](tenant=tenant, subject_ref=subject_ref)
        except Exception:                                                  # noqa: BLE001
            discount = None
        ref = str((discount or {}).get("ref") or "")
        if ref:
            minor = _scoped_value(
                kind=str(discount.get("reward_kind") or ""),
                amount=int(discount.get("reward_amount") or 0),
                scope_service_ids=discount.get("scope_service_ids"),
                invoice_minor=invoice_minor, line_minor=line_minor)
            if minor > 0:
                candidates.append(OfferDecision(minor, f"campaign:{ref}", ref))

    if operations is not None and phone:
        try:
            grant = await operations.referral_discount_for(tenant, phone)
        except Exception:                                                  # noqa: BLE001
            grant = None
        if grant and grant.get("eligible"):
            # WHOLE-INVOICE ONLY -- `ReferralGrant` carries no `scope_service_ids` at all (see
            # `referral_redemption.py`'s own model); a future per-service referral discount would
            # need that field added there first, not guessed at here.
            if grant.get("new_customer_reward_type") == NEW_CUSTOMER_DISCOUNT_PERCENT:
                percent = int((grant.get("new_customer_reward_params") or {}).get("percent") or 0)
                minor = max(0, min(invoice_minor * max(0, percent) // 100, invoice_minor))
                if minor > 0:
                    candidates.append(OfferDecision(minor, f"referral:{phone}", phone))

    if not candidates:
        return OfferDecision()
    return max(candidates, key=lambda o: o.discount_minor)
