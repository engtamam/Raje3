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

THE TIE-BREAK RULE (owner's own correction, 2026-10-04 — replacing a FIXED priority order this
module used to hold): "العميل يهمه العرض الأفضل له، ما يهمه مصدره" — whichever source is actually
worth the most to the customer wins, by REAL SAR value, never by which source happened to be
checked first. Every money-shaped source (a reminders campaign offer, a referral-code welcome
discount, a mutual-benefit discount grant) is reduced to "how many halalas off THIS invoice" via
`core/reward_value.py::scoped_value` and the highest wins outright.

A GIFT GRANT (mutual-benefit `GRANT_GIFT`) IS VALUED AT THE GIFTED SERVICE'S OWN CATALOGUE PRICE —
a free service is worth exactly what the shop would otherwise have charged for it, looked up from
shop_b's own `ServiceStore` at comparison time (never scoped against the invoice — it is an ADDED
free item, not a percentage off what is already there).

A SOURCE WHOSE VALUE CANNOT BE COMPUTED (an unresolvable gift service, a referral reward type that
is not a money discount at all — e.g. `welcome_points`) is never silently dropped: it is still
offered, at the BOTTOM of the ranking, so a customer never loses an entitlement just because this
gateway could not price it — it only loses the TIE-BREAK against something it could price.

A FAILURE TO READ A SOURCE REFUSES, IT DOES NOT ANSWER «none» — the exact posture
`adapters/offer_choice.py`'s own module docstring already states for the campaign side; applied
here uniformly to every source, for the same reason: applying nothing costs a customer an
entitlement he still holds, while applying one we could not verify is a discount nobody agreed to.

A FUTURE SOURCE (a coupon system, anything else single-grant/single-redeem) joins by handing its own
async `(tenant, subject_ref, phone, service_ids) -> dict | None` chooser (or, for something already
shaped like `MutualBenefitEngine`, a small adapter the same shape as `_referral_entitlement`
below) into `EntitlementGateway.__init__`, and giving `choose()` a way to price it — never a change
to `Operations.apply_offer` itself.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from app.core.best_offer import OfferCandidate, rank
from app.core.reward_value import scoped_value

SOURCE_REFERRAL = "mutual_benefit"
SOURCE_REFERRAL_CODE = "referral_code"
SOURCE_CAMPAIGN = "reminders_campaign"

# Used only as the LAST-RESORT tie-break order, for candidates whose real value could not be
# computed at all (see module docstring's "cannot be computed" section) — every priced candidate
# is still compared by `scoped_value` first.
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
                referral_code_engine: Any = None, store: Any = None) -> None:
        self._referral = mutual_benefit_engine
        self._campaign_chooser = campaign_chooser
        self._referral_code = referral_code_engine
        # ONLY FOR PRICING A GIFT GRANT (see module docstring) — the one candidate this gateway
        # cannot value from its own eligibility payload alone, since a gift's worth is whatever
        # the granting shop's OWN catalogue already charges for that service. `None`-safe like
        # every other optional peer here: without it, a gift simply falls to the value-less
        # tie-break tier instead of being priced.
        self._store = store

    async def choose(self, *, tenant: str, subject_ref: str, phone: str,
                     service_ids: list[str], invoice_minor: int = 0,
                     line_minor: dict[str, int] | None = None) -> Entitlement | None:
        line_minor = line_minor or {}
        referral: Entitlement | None = None
        referral_value: int | None = None
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
                    referral_value = await self._gift_value(
                        tenant, str(elig.get("gift_service_id") or ""))
                elif elig.get("discount_scope") == DISCOUNT_SCOPE_GROUP:
                    text = f"خصم شراكة إحالة نشط على مجموعة: {elig.get('discount_group_name', '')}"
                    group_scope = await self._group_scope_ids(
                        tenant, str(elig.get("discount_group_id") or ""))
                    referral_value = scoped_value(
                        kind=str(elig.get("discount_kind") or ""),
                        amount=int(elig.get("discount_amount") or 0),
                        scope_service_ids=group_scope, invoice_minor=invoice_minor,
                        line_minor=line_minor)
                elif elig.get("discount_scope") == DISCOUNT_SCOPE_BLANKET:
                    text = "خصم شراكة إحالة نشط — خصم شامل"
                    referral_value = scoped_value(
                        kind=str(elig.get("discount_kind") or ""),
                        amount=int(elig.get("discount_amount") or 0),
                        scope_service_ids=None, invoice_minor=invoice_minor,
                        line_minor=line_minor)
                else:                                                   # discount, scope "item"
                    text = f"خصم شراكة إحالة نشط على: {elig.get('gift_service_name', '')}"
                    referral_value = scoped_value(
                        kind=str(elig.get("discount_kind") or ""),
                        amount=int(elig.get("discount_amount") or 0),
                        scope_service_ids=[str(elig.get("gift_service_id") or "")],
                        invoice_minor=invoice_minor, line_minor=line_minor)
                referral = Entitlement(source=SOURCE_REFERRAL, ref=f"referral:{phone}",
                                       text=text, finalize_key=phone)

        referral_code: Entitlement | None = None
        referral_code_value: int | None = None
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
                    percent = int(params.get("percent") or 0)
                    text = f"خصم عميل جديد بالإحالة: {percent}%"
                    referral_code_value = scoped_value(
                        kind="percent", amount=percent, scope_service_ids=None,
                        invoice_minor=invoice_minor, line_minor=line_minor)
                elif reward_type == NEW_CUSTOMER_WELCOME_POINTS:
                    # POINTS, NOT MONEY — nothing here reduces THIS invoice, so it has no SAR
                    # value to compare with; see module docstring's "cannot be computed" tier.
                    text = f"نقاط ترحيب بالإحالة: {params.get('points', 0)} نقطة"
                else:
                    text = "مكافأة إحالة نشطة"
                referral_code = Entitlement(source=SOURCE_REFERRAL_CODE,
                                            ref=f"referral_code:{phone}", text=text,
                                            finalize_key=phone)

        campaign: Entitlement | None = None
        campaign_value: int | None = None
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
                reward_kind = str(chosen.get("reward_kind") or "")
                if reward_kind:
                    campaign_value = scoped_value(
                        kind=reward_kind, amount=int(chosen.get("reward_amount") or 0),
                        scope_service_ids=chosen.get("scope_service_ids"),
                        invoice_minor=invoice_minor, line_minor=line_minor)

        by_source = {SOURCE_REFERRAL: referral, SOURCE_REFERRAL_CODE: referral_code,
                    SOURCE_CAMPAIGN: campaign}
        values = {SOURCE_REFERRAL: referral_value, SOURCE_REFERRAL_CODE: referral_code_value,
                 SOURCE_CAMPAIGN: campaign_value}

        # THE REAL COMPARISON, SHARED WITH `discount_consultation.py::best_offer_for` — see
        # `core/best_offer.py`'s own module docstring for why the DECISION is shared while each
        # caller still fetches its own candidates its own way.
        candidates = [OfferCandidate(source=source, value_minor=values[source],
                                    ref=entitlement.ref, text=entitlement.text,
                                    finalize_key=entitlement.finalize_key,
                                    campaign_id=entitlement.campaign_id)
                     for source, entitlement in by_source.items() if entitlement is not None]
        winner = rank(candidates, fallback_order=_PRIORITY)
        return by_source[winner.source] if winner is not None else None

    async def _gift_value(self, tenant: str, service_id: str) -> int | None:
        if self._store is None or not service_id:
            return None
        try:
            from app.core.stores import ServiceStore

            service = await ServiceStore(self._store).get(tenant, service_id)
        except Exception:                                                  # noqa: BLE001
            return None
        return service.price_minor if service is not None else None

    async def _group_scope_ids(self, tenant: str, group_id: str) -> list[str] | None:
        if self._store is None or not group_id:
            return None
        try:
            from app.core.stores import PackageStore

            package = await PackageStore(self._store).get(tenant, group_id)
        except Exception:                                                  # noqa: BLE001
            return None
        return list(package.service_ids) if package is not None else None

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
