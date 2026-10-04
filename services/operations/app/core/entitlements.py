"""ONE aggregation point for "does this customer currently hold ANY single-use entitlement" —
a discount, a gift, an offer, a referral grant, anything shaped like "granted once, redeemed once,
then gone/expired". The same "one real chokepoint" discipline `Operations.record_visit()` already
established for WRITES (see `core/mutual_benefit.py`'s own module docstring), now for this
one specific kind of READ, and consumed by exactly one place: `Operations.apply_offer()`.

WHY THIS EXISTS NOW, NOT BEFORE. `apply_offer` (§5.6.2) already had a real, working, one-per-visit,
idempotent mechanism — but it asked exactly ONE source (`reminders`' own campaign offers, via the
pluggable `_choose_offer` callback `with_offer_chooser` installs). Adding referral partnership's own
`MutualBenefitEngine.eligibility()` as a SECOND source directly into `apply_offer` would have
meant `apply_offer` itself growing a second special case, and a THIRD future source (a coupon-like
thing, anything else shaped the same way) growing a third — the same drift `record_visit()`'s own
module docstring warns against for writes. This module is the fix: `apply_offer` asks ONE question
of ONE thing, and every real source registers into it instead.

THE TIE-BREAK RULE, DECIDED AND DOCUMENTED (never "whichever happened to be checked first" as an
accident of code order — the caller here has NO room to be arbitrary, because only one entitlement
can EVER be applied per visit, by `apply_offer`'s own long-standing invariant: "خصمان على فاتورة
واحدة قرارٌ لم يتخذه المالك"):

    REFERRAL PARTNERSHIP WINS OVER A REMINDERS CAMPAIGN OFFER, WHEN BOTH ARE LIVE AT ONCE.

    A referral grant is a promise made TO ANOTHER BUSINESS, with its own hard, short expiry per
    customer (`MutualBenefitEngine`'s own `grant_validity_days`) and real reputational stakes
    if it silently lapses unused — the partner shop is watching its own KPI screen for exactly this
    ("redeemed vs expired unused"). A reminders campaign offer is entirely this tenant's OWN
    marketing tool: it can be resent, re-targeted, or re-scheduled at will, with no third party
    depending on it. Letting an internal promotion silently eat a cross-tenant commitment this shop
    entered into by agreement would be the worse failure of the two, so the referral grant is
    checked first and, if live, wins outright — the campaign offer is never even applied to (or
    consumed from) THIS visit, and stays available for the customer's next one.

A FAILURE TO READ EITHER SOURCE REFUSES, IT DOES NOT ANSWER «none» — the exact posture
`adapters/offer_choice.py`'s own module docstring already states for the campaign side; applied
here uniformly to both sources, for the same reason: applying nothing costs a customer an
entitlement he still holds, while applying one we could not verify is a discount nobody agreed to.

A FUTURE SOURCE (a coupon system, anything else single-grant/single-redeem) joins by handing its own
async `(tenant, subject_ref, phone, service_ids) -> dict | None` chooser (or, for something already
shaped like `MutualBenefitEngine`, a small adapter the same shape as `_referral_entitlement`
below) into `EntitlementGateway.__init__` and adding one line to `choose()`'s own priority list —
never a change to `Operations.apply_offer` itself.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

SOURCE_REFERRAL = "mutual_benefit"
SOURCE_REFERRAL_CODE = "referral_code"
SOURCE_CAMPAIGN = "reminders_campaign"

# The priority list `choose()` walks, top to bottom — see the module docstring for WHY referral
# outranks a campaign offer. `referral_code` (services/referrals' own global anonymous code,
# core/referral_redemption.py) is a SECOND cross-party promise, same reasoning as the mutual-
# benefit one above it: a referrer trusts this code to pay out, and a shop's own reminders
# campaign is entirely internal marketing that can be resent at will — so `referral_code` outranks
# `reminders_campaign` too, but sits BELOW `mutual_benefit` (an existing, already-decided
# partnership between two specific shops is a narrower, more deliberate commitment than a
# platform-wide anonymous code either shop could have joined at any time).
_PRIORITY = (SOURCE_REFERRAL, SOURCE_REFERRAL_CODE, SOURCE_CAMPAIGN)


class EntitlementPeerUnavailable(RuntimeError):
    """We could not ask ONE of the registered sources. NOT «he holds nothing» — see
    `adapters/offer_choice.py::OfferPeerUnavailable`'s own docstring; this is that same distinction,
    generalised to every source this gateway asks, not only the campaign one."""


@dataclass
class Entitlement:
    source: str                    # SOURCE_REFERRAL or SOURCE_CAMPAIGN (or a future source's own)
    ref: str
    text: str
    campaign_id: str = ""
    # Opaque to `apply_offer` — only `finalize()` below reads it, and only for the source that
    # produced it (a referral grant needs the phone to redeem; a campaign offer needs nothing more,
    # `ref` alone is already what reminders itself tracks).
    finalize_key: str = ""

    def as_offer_fields(self) -> dict[str, Any]:
        """The exact shape `Operations.apply_offer` has always stamped onto a `Visit` — unchanged,
        so nothing downstream of it (the receipt screen, the till, the console) has to learn a new
        one just because the offer's SOURCE is now one of two things instead of always reminders."""
        return {"ref": self.ref, "text": self.text, "campaign_id": self.campaign_id}


CampaignChooser = Callable[..., Awaitable[dict[str, Any] | None]]


class EntitlementGateway:
    """`mutual_benefit_engine` and `campaign_chooser` are both optional — a deployment or a test may wire
    either, both, or neither (mirroring `_choose_offer`'s own long-standing `None`-is-a-real-state
    posture). `campaign_chooser` is the SAME callable shape `with_offer_chooser` always took
    (`adapters/offer_choice.py::http_chooser`'s own return value) — nothing about that peer's own
    contract changed, only who calls it."""

    def __init__(self, *, mutual_benefit_engine: Any = None,
                campaign_chooser: CampaignChooser | None = None,
                referral_code_engine: Any = None) -> None:
        self._referral = mutual_benefit_engine
        self._campaign_chooser = campaign_chooser
        self._referral_code = referral_code_engine

    async def choose(self, *, tenant: str, subject_ref: str, phone: str,
                     service_ids: list[str]) -> Entitlement | None:
        referral: Entitlement | None = None
        if self._referral is not None and phone:
            try:
                elig = await self._referral.eligibility(tenant, phone)
            except Exception as exc:                                          # noqa: BLE001
                raise EntitlementPeerUnavailable(str(exc)) from exc
            if elig and elig.get("eligible"):
                # NEVER the referring shop's name — same privacy rule
                # `MutualBenefitGrant.public_for_beneficiary` already enforces at its own source; this
                # text is ALWAYS DERIVED from the real catalogue fact backing the grant, never
                # authored/typed/stored text (owner's own correction — see
                # `core/mutual_benefit.py`'s own "GRANT TYPE" module-docstring section).
                # Every kind/scope resolves to one opaque `Entitlement` shape — `apply_offer`
                # never learns which one it got.
                from app.core.mutual_benefit import (DISCOUNT_SCOPE_BLANKET,
                                                            DISCOUNT_SCOPE_GROUP, GRANT_GIFT)

                if elig.get("grant_type") == GRANT_GIFT:
                    text = f"هدية شراكة إحالة نشطة لهذا العميل: {elig.get('gift_service_name', '')}"
                elif elig.get("discount_scope") == DISCOUNT_SCOPE_GROUP:
                    text = f"خصم شراكة إحالة نشط على مجموعة: {elig.get('discount_group_name', '')}"
                elif elig.get("discount_scope") == DISCOUNT_SCOPE_BLANKET:
                    text = "خصم شراكة إحالة نشط — خصم شامل"
                else:                                                   # discount, scope "item"
                    text = f"خصم شراكة إحالة نشط على: {elig.get('gift_service_name', '')}"
                referral = Entitlement(source=SOURCE_REFERRAL, ref=f"referral:{phone}",
                                       text=text, finalize_key=phone)

        referral_code: Entitlement | None = None
        if self._referral_code is not None and phone:
            try:
                elig = await self._referral_code.eligibility(tenant, phone)
            except Exception as exc:                                          # noqa: BLE001
                raise EntitlementPeerUnavailable(str(exc)) from exc
            if elig and elig.get("eligible"):
                from app.core.referral_redemption import (
                    NEW_CUSTOMER_DISCOUNT_PERCENT, NEW_CUSTOMER_WELCOME_POINTS)

                reward_type = elig.get("new_customer_reward_type")
                params = elig.get("new_customer_reward_params") or {}
                if reward_type == NEW_CUSTOMER_DISCOUNT_PERCENT:
                    text = f"خصم عميل جديد بالإحالة: {params.get('percent', 0)}%"
                elif reward_type == NEW_CUSTOMER_WELCOME_POINTS:
                    text = f"نقاط ترحيب بالإحالة: {params.get('points', 0)} نقطة"
                else:
                    text = "مكافأة إحالة نشطة"
                referral_code = Entitlement(source=SOURCE_REFERRAL_CODE,
                                            ref=f"referral_code:{phone}", text=text,
                                            finalize_key=phone)

        campaign: Entitlement | None = None
        if self._campaign_chooser is not None:
            try:
                chosen = await self._campaign_chooser(
                    tenant=tenant, subject_ref=subject_ref, service_ids=service_ids)
            except Exception as exc:                                          # noqa: BLE001
                raise EntitlementPeerUnavailable(str(exc)) from exc
            if chosen and chosen.get("ref"):
                campaign = Entitlement(
                    source=SOURCE_CAMPAIGN, ref=str(chosen.get("ref") or ""),
                    text=str(chosen.get("text") or ""),
                    campaign_id=str(chosen.get("campaign_id") or ""))

        by_source = {SOURCE_REFERRAL: referral, SOURCE_REFERRAL_CODE: referral_code,
                    SOURCE_CAMPAIGN: campaign}
        for source in _PRIORITY:
            if by_source.get(source) is not None:
                return by_source[source]
        return None

    async def finalize(self, entitlement: Entitlement, *, tenant: str, visit_id: str) -> None:
        """Called ONCE, by `apply_offer`, ONLY for a freshly-chosen entitlement (never on a replay
        that returns an already-stamped visit) — see that method's own note on ordering: this runs
        BEFORE the visit is stamped, so a failure here refuses the whole apply and a retry asks
        `choose()` again from a clean slate, rather than a visit that claims an offer nothing ever
        actually redeemed."""
        if entitlement.source == SOURCE_REFERRAL and self._referral is not None:
            await self._referral.redeem(tenant, entitlement.finalize_key, visit_id=visit_id)
        elif entitlement.source == SOURCE_REFERRAL_CODE and self._referral_code is not None:
            await self._referral_code.redeem(tenant, entitlement.finalize_key, visit_id=visit_id)
        # SOURCE_CAMPAIGN needs no finalize call of its own — reminders tracks nothing further to
        # confirm; `apply_offer` stamping the visit IS the whole record, exactly as it always was.
