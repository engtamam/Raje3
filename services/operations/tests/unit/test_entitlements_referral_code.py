"""core/entitlements.py's THIRD source — the global anonymous referral code
(core/referral_redemption.py). Mirrors test_entitlements.py's own style and coverage for the
existing two sources: the documented tie-break (mutual_benefit > referral_code > campaign), and
applying a referral_code-sourced entitlement really calling through to
`ReferralRedemptionEngine.redeem()` end to end via `Operations.apply_offer`."""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.entitlements import (SOURCE_CAMPAIGN, SOURCE_REFERRAL, SOURCE_REFERRAL_CODE,
                                   EntitlementGateway)
from app.core.models import Customer
from app.core.operations import Operations, _normalise_phone
from app.core.signup import canonical_phone
from app.core.referral_redemption import ReferralRedemptionEngine
from app.core.stores import CustomerStore, VisitStore, new_id

CC = "966"
TENANT = "tnt_refcode"
BENEFICIARY_PHONE = "0522222222"
CODE = "AB123"


def run(coro):
    return asyncio.run(coro)


class FakeReferralsDesk:
    def __init__(self, *, referrer_phone="0511111111", campaign=None) -> None:
        self._referrer_phone = referrer_phone
        self._campaign = campaign or {
            "id": "camp_1", "mode": "once", "min_spend_minor": 0,
            "usage_cap_period": "", "usage_cap_limit": 0, "x_times_limit": 0,
            "reward_type": "fixed_points", "reward_params": {"points": 50},
            "new_customer_reward_type": "discount_percent",
            "new_customer_reward_params": {"percent": 10},
        }
        self.configured = True

    async def lookup_code(self, code):
        return self._referrer_phone

    async def active_campaign(self, tenant):
        return self._campaign


class FakeLoyaltyDesk:
    def __init__(self) -> None:
        self.awards: list[dict] = []

    async def award(self, *, tenant, subject_ref, points, idempotency_key, reason, actor):
        self.awards.append({"points": points, "reason": reason})
        return {"earned": points}


async def _seed_customer(store, tenant: str, phone: str) -> None:
    """The referrer must already be an existing customer here (deep-review Phase 5c) — the
    default referrer phone below is seeded so these end-to-end tests keep exercising what they
    were written to test.

    SEEDED IN THE REAL STORAGE FORM (`_normalise_phone`, no leading "+") — every real writer of a
    Customer row uses it; `canonical_phone`'s "+966..." form is what `referral_redemption.py` uses
    for its OWN internal bookkeeping, never what `Customer.phone` is actually stored as (see that
    module's own import-time note)."""
    await CustomerStore(store).save(
        Customer(id=new_id("cus"), tenant=tenant, phone=_normalise_phone(phone),
                subject_ref="ref"))


def _referral_engine(*, store=None, **over) -> ReferralRedemptionEngine:
    store = store or MemoryDataStore()
    referrer_phone = over.get("referrer_phone", "0511111111")
    run(_seed_customer(store, TENANT, referrer_phone))
    return ReferralRedemptionEngine(
        store=store, referrals_desk=FakeReferralsDesk(**over),
        loyalty_desk=FakeLoyaltyDesk(), pii_salt="s" * 32, default_cc=CC)


# ── the gateway alone: tie-break against a campaign offer ───────────────────────────────────────
def test_referral_code_outranks_a_campaign_offer_when_both_are_live():
    engine = _referral_engine()
    run(engine.register(TENANT, code=CODE, beneficiary_phone=BENEFICIARY_PHONE))

    async def campaign_chooser(*, tenant, subject_ref, service_ids):
        return {"ref": "camp_1", "text": "عرض ترحيبي", "campaign_id": "camp"}

    gateway = EntitlementGateway(campaign_chooser=campaign_chooser, referral_code_engine=engine)
    chosen = run(gateway.choose(tenant=TENANT, subject_ref="sub_x", phone=BENEFICIARY_PHONE,
                                service_ids=[]))
    assert chosen is not None
    assert chosen.source == SOURCE_REFERRAL_CODE


def test_mutual_benefit_still_outranks_referral_code_when_both_are_live():
    from app.core.mutual_benefit import CONDITION_MIN_TOTAL, MutualBenefitEngine
    from app.core.signup import PHONE_INDEX, canonical_phone

    store = MemoryDataStore()

    class FakePlans:
        driver = "fake"

        async def subscriptions(self, tenant):
            return [{"id": "s", "plan": "p", "status": "active"}]

        async def plan_id_for_key(self, key):
            return "p"

        async def limits(self, plan_id):
            return {}

    class FakeAuthz:
        async def list_assignments(self, tenant):
            return []

        async def effective_capabilities(self, tenant, subject, roles):
            return set()

    class FakeNotifier:
        async def send(self, **kwargs):
            return True

    mb = MutualBenefitEngine(store=store, plans=FakePlans(), notifier=FakeNotifier(),
                             authz=FakeAuthz(), default_cc=CC)
    key = canonical_phone(BENEFICIARY_PHONE, default_cc=CC)
    run(store.put(PHONE_INDEX, key, {"id": key, "tenant": TENANT, "verified": True}))
    agreement = run(mb.propose(
        shop_a="tnt_other_shop", shop_b_phone=BENEFICIARY_PHONE, operator_id="op1",
        condition_type=CONDITION_MIN_TOTAL, condition_value="1000", grant_validity_days=3,
        agreement_duration_days=90, discount_kind="percent", discount_amount=10))
    run(mb.accept(tenant=TENANT, agreement_id=agreement.id))
    run(mb.on_visit_recorded(tenant="tnt_other_shop", customer_phone=BENEFICIARY_PHONE,
                             service_ids=[], total_minor=1500, visit_id="vis_trigger"))

    referral_engine = _referral_engine()
    run(referral_engine.register(TENANT, code=CODE, beneficiary_phone=BENEFICIARY_PHONE))

    gateway = EntitlementGateway(mutual_benefit_engine=mb, referral_code_engine=referral_engine)
    chosen = run(gateway.choose(tenant=TENANT, subject_ref="s", phone=BENEFICIARY_PHONE,
                                service_ids=[]))
    assert chosen.source == SOURCE_REFERRAL


# ── through Operations.apply_offer end to end ────────────────────────────────────────────────────
def test_applying_a_referral_code_entitlement_redeems_it_and_credits_the_referrer():
    engine = _referral_engine()
    grant = run(engine.register(TENANT, code=CODE, beneficiary_phone=BENEFICIARY_PHONE))

    store = engine._s  # the same MemoryDataStore the engine and Operations must share
    ops = Operations(store=store, pii_salt="s" * 32)

    async def campaign_chooser(*, tenant, subject_ref, service_ids):
        return None

    ops.with_entitlement_gateway(
        EntitlementGateway(campaign_chooser=campaign_chooser, referral_code_engine=engine))

    v = run(ops.record_visit(tenant=TENANT, phone=BENEFICIARY_PHONE, service_ids=["srv_1"]))
    applied = run(ops.apply_offer(tenant=TENANT, visit_id=v.visit.id, subject_ref="sub_ignored"))
    assert applied is not None
    assert "إحالة" in applied["text"]

    stored = run(VisitStore(store).get(TENANT, v.visit.id))
    assert stored.offer_ref == applied["ref"]

    assert engine._loyalty.awards == [{"points": 50, "reason": "referral"}]


def test_redeem_credits_the_referrers_real_existing_customer_never_a_duplicate():
    """REGRESSION (deep-review): `_customer_for_phone` used to look up/create against
    `canonical_phone`'s own "+966..." form, which never matches `Customer.phone`'s real storage
    form — so a referrer who was already a real customer here was never found, and every redeem
    silently created a SECOND Customer row for them with a mismatched phone and a brand-new,
    unconnected `subject_ref`, misdirecting their real loyalty points to a phantom account. This
    proves, end to end, that redeem() finds and credits the referrer's ONE real, pre-existing
    customer row — never a duplicate."""
    referrer_phone = "0511111111"
    store = MemoryDataStore()
    run(_seed_customer(store, TENANT, referrer_phone))
    real_referrer = run(CustomerStore(store).by_phone(TENANT, _normalise_phone(referrer_phone)))
    assert real_referrer is not None
    assert real_referrer.subject_ref == "ref"  # the REAL pre-existing pseudonym, seeded above

    loyalty = FakeLoyaltyDesk()
    engine = ReferralRedemptionEngine(
        store=store, referrals_desk=FakeReferralsDesk(referrer_phone=referrer_phone),
        loyalty_desk=loyalty, pii_salt="s" * 32, default_cc=CC)
    ops = Operations(store=store, pii_salt="s" * 32)

    class _CapturingLoyalty(FakeLoyaltyDesk):
        def __init__(self):
            super().__init__()
            self.credited_subject_refs: list[str] = []

        async def award(self, *, tenant, subject_ref, points, idempotency_key, reason, actor):
            self.credited_subject_refs.append(subject_ref)
            return await super().award(tenant=tenant, subject_ref=subject_ref, points=points,
                                       idempotency_key=idempotency_key, reason=reason, actor=actor)

    engine._loyalty = _CapturingLoyalty()

    async def campaign_chooser(*, tenant, subject_ref, service_ids):
        return None

    ops.with_entitlement_gateway(
        EntitlementGateway(campaign_chooser=campaign_chooser, referral_code_engine=engine))
    run(engine.register(TENANT, code=CODE, beneficiary_phone=BENEFICIARY_PHONE))
    v = run(ops.record_visit(tenant=TENANT, phone=BENEFICIARY_PHONE, service_ids=["srv_1"]))
    run(ops.apply_offer(tenant=TENANT, visit_id=v.visit.id, subject_ref="sub_ignored"))

    # THE CREDIT WENT TO THE REFERRER'S REAL, PRE-EXISTING SUBJECT_REF — never a fresh one.
    assert engine._loyalty.credited_subject_refs == ["ref"]

    # AND STILL EXACTLY ONE CUSTOMER ROW FOR THIS PHONE — no duplicate was ever created.
    rows, _ = run(store.find("customers", {"tenant": TENANT, "phone": _normalise_phone(referrer_phone)}))
    assert len(rows) == 1
    assert rows[0]["id"] == real_referrer.id


def test_a_second_tap_never_credits_the_referrer_twice():
    engine = _referral_engine()
    run(engine.register(TENANT, code=CODE, beneficiary_phone=BENEFICIARY_PHONE))

    store = engine._s
    ops = Operations(store=store, pii_salt="s" * 32)

    async def campaign_chooser(*, tenant, subject_ref, service_ids):
        return None

    ops.with_entitlement_gateway(
        EntitlementGateway(campaign_chooser=campaign_chooser, referral_code_engine=engine))

    v = run(ops.record_visit(tenant=TENANT, phone=BENEFICIARY_PHONE, service_ids=["srv_1"]))
    first = run(ops.apply_offer(tenant=TENANT, visit_id=v.visit.id, subject_ref="s"))
    second = run(ops.apply_offer(tenant=TENANT, visit_id=v.visit.id, subject_ref="s"))
    assert first == second
    assert len(engine._loyalty.awards) == 1
