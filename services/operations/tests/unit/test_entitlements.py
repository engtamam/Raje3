"""core/entitlements.py — the one aggregation point `Operations.apply_offer` consults instead of
calling reminders' campaign chooser directly. Two things this file must prove that no other test
does: the documented tie-break rule (referral wins over a campaign offer, when both are live for
the same visit) actually holds, and applying a referral-sourced entitlement really calls through to
`ReferralPartnershipEngine.redeem()` so its own KPIs become real — the exact gap a real review
found (propose/accept/detect worked; nothing ever consumed a grant)."""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.entitlements import (SOURCE_CAMPAIGN, SOURCE_REFERRAL, EntitlementGateway,
                                   EntitlementPeerUnavailable)
from app.core.operations import Operations
from app.core.referral_partnership import (CONDITION_MIN_TOTAL, FEATURE_KEY,
                                           ReferralPartnershipEngine)
from app.core.signup import PHONE_INDEX, canonical_phone
from app.core.stores import VisitStore

CC = "966"
A = "tnt_ref_a"       # the referring shop
B = "tnt_ref_b"       # the beneficiary shop, where the entitlement is applied
PHONE = "0511111111"


def run(coro):
    return asyncio.run(coro)


class FakePlans:
    driver = "fake"

    def __init__(self) -> None:
        self.subs: dict[str, list[dict]] = {}
        self.plan_for_key = {FEATURE_KEY: "plan_referral"}

    async def subscriptions(self, tenant):
        return self.subs.get(tenant, [])

    async def plan_id_for_key(self, key):
        return self.plan_for_key.get(key, "")

    async def limits(self, plan_id):
        return {}


def _subscribe(plans: FakePlans, tenant: str) -> None:
    plans.subs.setdefault(tenant, []).append(
        {"id": f"sub_{tenant}", "plan": "plan_referral", "status": "active"})


class FakeAuthz:
    async def list_assignments(self, tenant: str):
        return []

    async def effective_capabilities(self, tenant, subject, roles):
        return set()


class FakeNotifier:
    async def send(self, **kwargs):
        return True


def _register_phone(store, phone: str, tenant: str) -> None:
    key = canonical_phone(phone, default_cc=CC)
    run(store.put(PHONE_INDEX, key, {"id": key, "tenant": tenant, "verified": True}))


def _referral_grant(store) -> ReferralPartnershipEngine:
    """A live, redeemable referral grant for `PHONE` at shop B, created the real way (propose ->
    accept -> record_visit at A over the min-total threshold) rather than poked in directly — so
    this test also exercises the real detection path, not just a fixture shortcut."""
    plans = FakePlans()
    _subscribe(plans, A)
    _subscribe(plans, B)
    engine = ReferralPartnershipEngine(store=store, plans=plans, notifier=FakeNotifier(),
                                       authz=FakeAuthz(), default_cc=CC)
    _register_phone(store, PHONE, B)
    agreement = run(engine.propose(
        shop_a=A, shop_b_phone=PHONE, operator_id="op1", condition_type=CONDITION_MIN_TOTAL,
        condition_value="1000", discount_note="10%", grant_validity_days=3,
        agreement_duration_days=90))
    run(engine.accept(tenant=B, agreement_id=agreement.id))
    run(engine.on_visit_recorded(tenant=A, customer_phone=PHONE, service_ids=[],
                                total_minor=1500, visit_id="vis_trigger"))
    return engine


# ── the gateway alone: the documented tie-break, and unreadable-source refusal ──────────────────
def test_referral_outranks_a_campaign_offer_when_both_are_live():
    store = MemoryDataStore()
    engine = _referral_grant(store)

    async def campaign_chooser(*, tenant, subject_ref, service_ids):
        return {"ref": "camp_1", "text": "عرض ترحيبي", "campaign_id": "camp"}

    gateway = EntitlementGateway(referral_engine=engine, campaign_chooser=campaign_chooser)
    chosen = run(gateway.choose(tenant=B, subject_ref="sub_x", phone=PHONE, service_ids=[]))
    assert chosen is not None
    assert chosen.source == SOURCE_REFERRAL


def test_a_campaign_offer_alone_is_still_chosen_when_no_referral_is_live():
    store = MemoryDataStore()

    async def campaign_chooser(*, tenant, subject_ref, service_ids):
        return {"ref": "camp_1", "text": "عرض", "campaign_id": ""}

    # No referral engine wired at all — the campaign source is still respected.
    gateway = EntitlementGateway(referral_engine=None, campaign_chooser=campaign_chooser)
    chosen = run(gateway.choose(tenant=B, subject_ref="sub_x", phone="0500000000",
                                service_ids=[]))
    assert chosen is not None and chosen.source == SOURCE_CAMPAIGN


def test_neither_source_live_returns_nothing_not_a_refusal():
    async def campaign_chooser(*, tenant, subject_ref, service_ids):
        return None

    gateway = EntitlementGateway(referral_engine=None, campaign_chooser=campaign_chooser)
    assert run(gateway.choose(tenant=B, subject_ref="s", phone="0500000000",
                              service_ids=[])) is None


def test_an_unreadable_source_refuses_it_never_silently_answers_none():
    async def broken_chooser(*, tenant, subject_ref, service_ids):
        raise RuntimeError("peer down")

    gateway = EntitlementGateway(referral_engine=None, campaign_chooser=broken_chooser)
    with pytest.raises(EntitlementPeerUnavailable):
        run(gateway.choose(tenant=B, subject_ref="s", phone="0500000000", service_ids=[]))


# ── through `Operations.apply_offer` end to end: the gap a real review found ────────────────────
def test_applying_a_referral_entitlement_actually_redeems_it_and_kpis_update():
    store = MemoryDataStore()
    engine = _referral_grant(store)
    ops = Operations(store=store, pii_salt="s" * 32)
    ops.with_referral_engine(engine)

    async def campaign_chooser(*, tenant, subject_ref, service_ids):
        return None                                                     # nothing from reminders

    from app.core.entitlements import EntitlementGateway

    ops.with_entitlement_gateway(
        EntitlementGateway(referral_engine=engine, campaign_chooser=campaign_chooser))

    v = run(ops.record_visit(tenant=B, phone=PHONE, service_ids=["srv_1"]))
    applied = run(ops.apply_offer(tenant=B, visit_id=v.visit.id, subject_ref="sub_ignored"))
    assert applied is not None
    assert "شراكة" in applied["text"]

    # THE VISIT IS STAMPED, EXACTLY THE EXISTING SHAPE — untouched by which source won.
    stored = run(VisitStore(store).get(B, v.visit.id))
    assert stored.offer_ref == applied["ref"]

    # AND THE GAP IS CLOSED: `redeem()` really ran, so the KPI screen's numbers are real.
    kpis = run(engine.kpis(A))
    assert kpis["as_referrer"]["redeemed"] == 1
    assert kpis["as_referrer"]["redemption_rate"] == 1.0


def test_a_second_tap_never_redeems_a_second_grant():
    """`apply_offer`'s own «عرضٌ واحد لكل زيارة» invariant, now proven to hold even with a peer
    (referral redeem) in the loop — a second tap must not spend a SECOND grant."""
    store = MemoryDataStore()
    engine = _referral_grant(store)
    # A second, later grant for the same customer/agreement — proves a second tap could otherwise
    # have picked a fresh one instead of just replaying.
    run(engine.on_visit_recorded(tenant=A, customer_phone=PHONE, service_ids=[],
                                total_minor=2000, visit_id="vis_trigger_2"))

    ops = Operations(store=store, pii_salt="s" * 32)
    ops.with_referral_engine(engine)
    from app.core.entitlements import EntitlementGateway

    async def campaign_chooser(*, tenant, subject_ref, service_ids):
        return None

    ops.with_entitlement_gateway(
        EntitlementGateway(referral_engine=engine, campaign_chooser=campaign_chooser))

    v = run(ops.record_visit(tenant=B, phone=PHONE, service_ids=["srv_1"]))
    first = run(ops.apply_offer(tenant=B, visit_id=v.visit.id, subject_ref="s"))
    second = run(ops.apply_offer(tenant=B, visit_id=v.visit.id, subject_ref="s"))
    assert first == second

    kpis = run(engine.kpis(A))
    assert kpis["as_referrer"]["redeemed"] == 1          # not 2


def test_a_referral_redeem_failure_refuses_the_whole_apply_and_never_stamps_the_visit():
    """Ordering guarantee from `apply_offer`'s own docstring: finalize before stamp."""
    store = MemoryDataStore()
    engine = _referral_grant(store)

    class BreakingEngine:
        async def eligibility(self, tenant, phone):
            return await engine.eligibility(tenant, phone)

        async def redeem(self, tenant, phone, *, visit_id):
            raise RuntimeError("boom")

    ops = Operations(store=store, pii_salt="s" * 32)
    from app.core.entitlements import EntitlementGateway

    async def campaign_chooser(*, tenant, subject_ref, service_ids):
        return None

    ops.with_entitlement_gateway(
        EntitlementGateway(referral_engine=BreakingEngine(), campaign_chooser=campaign_chooser))

    v = run(ops.record_visit(tenant=B, phone=PHONE, service_ids=["srv_1"]))
    from app.core.operations import OperationError

    with pytest.raises(OperationError):
        run(ops.apply_offer(tenant=B, visit_id=v.visit.id, subject_ref="s"))

    stored = run(VisitStore(store).get(B, v.visit.id))
    assert stored.offer_ref == ""                                  # never stamped
