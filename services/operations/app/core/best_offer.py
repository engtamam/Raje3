"""ONE decision: given several live discount CANDIDATES for the same customer, which one is
actually worth the most — by real SAR value, never by which source happened to be checked first,
and never by which caller is asking.

THIS IS DELIBERATELY JUST THE DECISION, NOT THE FETCHING. `core/entitlements.py::EntitlementGateway`
(the manual visit/till flow) and `core/discount_consultation.py::best_offer_for` (WhatsApp Direct
Ordering's auto-apply flow) each reach their own peers differently — entitlements talks to
in-process engine objects (`MutualBenefitEngine`, `ReferralRedemptionEngine`) because everything it
asks lives in this same service; discount_consultation talks to `reminders` over HTTP because that
service is a separate process. Making them share a peer-fetching layer would mean inventing a
lowest-common-denominator interface neither caller actually needs. What they SHOULD share — and,
before this module existed, did not — is the actual arithmetic: "given these priced candidates,
which one wins", which was two near-identical `max(..., key=...)` + fallback-order blocks that
could silently drift apart exactly the way the campaigns free-text bug did. This module is that one
shared piece.

MUTUAL-BENEFIT IS NOT A CANDIDATE EVERY CALLER MAY OFFER. A mutual-benefit discount is, by design,
NEVER applied by us — the granting shop's own till applies it by hand (see `core/mutual_benefit.py`'s
own module docstring). The manual visit flow can surface it as the winner because a human is
standing there to act on it; an automated flow like WhatsApp order payment, which charges a real
payment link with no human in the loop, must never let it win, because nothing would ever actually
apply it. Each caller decides which sources it is allowed to offer by which candidates it builds —
this module never assumes a fixed set.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OfferCandidate:
    source: str
    # `None` — never priced at all (an unresolvable gift, a points-type reward with no SAR value).
    # `0` — priced, and worth nothing (e.g. a scope that matched nothing on this invoice). Both
    # lose to any positively-priced candidate; see `rank`'s own docstring.
    value_minor: int | None
    ref: str
    text: str
    finalize_key: str = ""
    campaign_id: str = ""


def rank(candidates: list[OfferCandidate], *,
        fallback_order: tuple[str, ...] = ()) -> OfferCandidate | None:
    """The highest REAL, POSITIVE value wins outright. If nothing priced above zero, fall back to
    `fallback_order` (first source in that tuple that has a candidate at all) so a genuinely
    unpriceable candidate (module docstring's own examples) is still offered rather than silently
    dropped — never confused with "nothing live at all", which is a plain `None`."""
    priced = [c for c in candidates if c.value_minor is not None and c.value_minor > 0]
    if priced:
        return max(priced, key=lambda c: c.value_minor)
    by_source = {c.source: c for c in candidates}
    for source in fallback_order:
        if source in by_source:
            return by_source[source]
    return None
