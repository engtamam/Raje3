"""The real tie-break (owner's own correction, 2026-10-04): «العميل يهمه العرض الأفضل له، ما يهمه
مصدره» — whichever source is worth the most money wins outright, by real SAR value, never by a
fixed source priority. `test_entitlements.py` still covers the FALLBACK order for candidates that
cannot be priced at all (no invoice data supplied); this file is the real comparison, with real
invoice numbers.
"""
from __future__ import annotations

import asyncio

from app.adapters.datastore.memory import MemoryDataStore
from app.core.entitlements import SOURCE_CAMPAIGN, SOURCE_REFERRAL, SOURCE_REFERRAL_CODE, EntitlementGateway
from app.core.models import Package, Service
from app.core.mutual_benefit import (CONDITION_MIN_TOTAL, FEATURE_KEY, DISCOUNT_SCOPE_GROUP,
                                           GRANT_GIFT, MutualBenefitEngine)
from app.core.signup import PHONE_INDEX, canonical_phone
from app.core.stores import PackageStore, ServiceStore

CC = "966"
A = "tnt_val_a"
B = "tnt_val_b"
PHONE = "0522222222"
INVOICE = 10_000          # 100 SAR invoice, used across every test below


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


def _mutual_benefit_with(store, *, discount_kind: str, discount_amount: int,
                        grant_type: str = "discount", gift_service_id: str = "",
                        discount_scope: str = "blanket", discount_group_id: str = "") \
        -> MutualBenefitEngine:
    plans = FakePlans()
    _subscribe(plans, A)
    _subscribe(plans, B)
    engine = MutualBenefitEngine(store=store, plans=plans, notifier=FakeNotifier(),
                                       authz=FakeAuthz(), default_cc=CC)
    _register_phone(store, PHONE, B)
    kwargs = dict(shop_a=A, shop_b_phone=PHONE, operator_id="op1",
                 condition_type=CONDITION_MIN_TOTAL, condition_value="1000",
                 grant_validity_days=3, agreement_duration_days=90, grant_type=grant_type)
    if grant_type == GRANT_GIFT:
        kwargs["gift_service_id"] = gift_service_id
    else:
        kwargs.update(discount_kind=discount_kind, discount_amount=discount_amount,
                     discount_scope=discount_scope)
        if discount_scope == DISCOUNT_SCOPE_GROUP:
            kwargs["discount_group_id"] = discount_group_id
        elif discount_scope == "item":
            kwargs["gift_service_id"] = gift_service_id
    agreement = run(engine.propose(**kwargs))
    run(engine.accept(tenant=B, agreement_id=agreement.id))
    run(engine.on_visit_recorded(tenant=A, customer_phone=PHONE, service_ids=[],
                                total_minor=1500, visit_id="vis_trigger"))
    return engine


def _campaign_chooser(reward_kind: str, reward_amount: int, scope_service_ids=None):
    async def chooser(*, tenant, subject_ref, service_ids):
        return {"ref": "camp_1", "text": "عرض الحملة", "campaign_id": "camp",
               "reward_kind": reward_kind, "reward_amount": reward_amount,
               "scope_service_ids": scope_service_ids or []}
    return chooser


def test_a_bigger_campaign_discount_wins_over_a_smaller_mutual_benefit_discount():
    """10% off a 100 SAR invoice (mutual benefit) is 10 SAR; 30% (campaign) is 30 SAR — the
    campaign must win, even though the OLD fixed order always preferred the referral source."""
    store = MemoryDataStore()
    engine = _mutual_benefit_with(store, discount_kind="percent", discount_amount=10)
    gateway = EntitlementGateway(mutual_benefit_engine=engine,
                                campaign_chooser=_campaign_chooser("percent", 30))
    chosen = run(gateway.choose(tenant=B, subject_ref="s", phone=PHONE, service_ids=[],
                                invoice_minor=INVOICE))
    assert chosen is not None
    assert chosen.source == SOURCE_CAMPAIGN


def test_a_bigger_mutual_benefit_discount_wins_over_a_smaller_campaign_discount():
    """The reverse of the above — the OLD fixed order already got this one right, but for the
    wrong reason (priority, not value); this proves it is now value, by making the campaign the
    one that would have lost under the old rule too, for a DIFFERENT reason if the math were
    flipped."""
    store = MemoryDataStore()
    engine = _mutual_benefit_with(store, discount_kind="percent", discount_amount=30)
    gateway = EntitlementGateway(mutual_benefit_engine=engine,
                                campaign_chooser=_campaign_chooser("percent", 10))
    chosen = run(gateway.choose(tenant=B, subject_ref="s", phone=PHONE, service_ids=[],
                                invoice_minor=INVOICE))
    assert chosen is not None
    assert chosen.source == SOURCE_REFERRAL


def test_a_fixed_halalas_campaign_beats_a_percent_mutual_benefit_when_the_math_says_so():
    store = MemoryDataStore()
    engine = _mutual_benefit_with(store, discount_kind="percent", discount_amount=5)  # 5 SAR
    gateway = EntitlementGateway(mutual_benefit_engine=engine,
                                campaign_chooser=_campaign_chooser("fixed_halalas", 2000))  # 20 SAR
    chosen = run(gateway.choose(tenant=B, subject_ref="s", phone=PHONE, service_ids=[],
                                invoice_minor=INVOICE))
    assert chosen.source == SOURCE_CAMPAIGN


def test_a_gift_grant_is_priced_at_the_services_own_catalogue_price():
    """A free service worth 40 SAR must outrank a 10% (10 SAR) campaign discount on a 100 SAR
    invoice — the gift has no `discount_kind`/`discount_amount` at all, so its value can only come
    from the real catalogue price of the service being given away."""
    store = MemoryDataStore()
    run(ServiceStore(store).save(Service(id="svc_gift", tenant=B, name="فحص مجاني",
                                         price_minor=4000)))
    engine = _mutual_benefit_with(store, discount_kind="", discount_amount=0,
                                 grant_type=GRANT_GIFT, gift_service_id="svc_gift")
    gateway = EntitlementGateway(mutual_benefit_engine=engine,
                                campaign_chooser=_campaign_chooser("percent", 10),
                                store=store)
    chosen = run(gateway.choose(tenant=B, subject_ref="s", phone=PHONE, service_ids=[],
                                invoice_minor=INVOICE))
    assert chosen.source == SOURCE_REFERRAL


def test_a_gift_grant_with_no_store_wired_cannot_be_priced_and_loses_to_a_real_discount():
    """Without `store`, the gateway cannot look up the gift's own price — it must never guess a
    value, and must never crash; it simply loses to anything it CAN price."""
    store = MemoryDataStore()
    run(ServiceStore(store).save(Service(id="svc_gift2", tenant=B, name="فحص مجاني",
                                         price_minor=4000)))
    engine = _mutual_benefit_with(store, discount_kind="", discount_amount=0,
                                 grant_type=GRANT_GIFT, gift_service_id="svc_gift2")
    gateway = EntitlementGateway(mutual_benefit_engine=engine,
                                campaign_chooser=_campaign_chooser("percent", 10))  # no store=
    chosen = run(gateway.choose(tenant=B, subject_ref="s", phone=PHONE, service_ids=[],
                                invoice_minor=INVOICE))
    assert chosen.source == SOURCE_CAMPAIGN


def test_a_mutual_benefit_group_scope_discount_is_priced_against_only_its_own_packages_services():
    """A 50% discount scoped to a 2000-halalas package (1000 if only half is on this invoice) must
    be priced against exactly the package's member services actually on THIS invoice, the same
    scoping rule a campaign's own `scope_service_ids` already follows."""
    store = MemoryDataStore()
    run(ServiceStore(store).save(Service(id="svc_g1", tenant=B, name="خدمة 1", price_minor=3000)))
    run(ServiceStore(store).save(Service(id="svc_g2", tenant=B, name="خدمة 2", price_minor=3000)))
    run(PackageStore(store).save(Package(id="pkg_1", tenant=B, name="باقة",
                                        service_ids=["svc_g1", "svc_g2"])))
    engine = _mutual_benefit_with(store, discount_kind="percent", discount_amount=50,
                                 discount_scope=DISCOUNT_SCOPE_GROUP, discount_group_id="pkg_1")
    gateway = EntitlementGateway(mutual_benefit_engine=engine,
                                campaign_chooser=_campaign_chooser("percent", 5), store=store)
    # Only svc_g1 (3000) is actually on this invoice -- the group discount is 50% of 3000 = 1500,
    # not 50% of the whole 10000 invoice and not 50% of the whole package's 6000.
    line_minor = {"svc_g1": 3000, "svc_other": 7000}
    chosen = run(gateway.choose(tenant=B, subject_ref="s", phone=PHONE, service_ids=["svc_g1"],
                                invoice_minor=INVOICE, line_minor=line_minor))
    assert chosen.source == SOURCE_REFERRAL     # 1500 > campaign's 5% of 10000 = 500


def test_welcome_points_has_no_money_value_and_loses_to_any_real_discount():
    """A referral-code welcome-POINTS reward (not a discount) must never out-rank a real money
    discount just because it used to sit above campaigns in the fixed order."""
    class FakeReferralCode:
        async def eligibility(self, tenant, phone):
            return {"eligible": True, "new_customer_reward_type": "welcome_points",
                   "new_customer_reward_params": {"points": 50}}

    gateway = EntitlementGateway(referral_code_engine=FakeReferralCode(),
                                campaign_chooser=_campaign_chooser("percent", 10))
    chosen = run(gateway.choose(tenant=B, subject_ref="s", phone=PHONE, service_ids=[],
                                invoice_minor=INVOICE))
    assert chosen.source == SOURCE_CAMPAIGN


def test_welcome_points_is_still_offered_when_nothing_else_is_priceable():
    """The unpriceable candidate is never simply dropped -- with no competing priced offer, it is
    still returned (module docstring's "cannot be computed" tier)."""
    class FakeReferralCode:
        async def eligibility(self, tenant, phone):
            return {"eligible": True, "new_customer_reward_type": "welcome_points",
                   "new_customer_reward_params": {"points": 50}}

    gateway = EntitlementGateway(referral_code_engine=FakeReferralCode())
    chosen = run(gateway.choose(tenant=B, subject_ref="s", phone=PHONE, service_ids=[],
                                invoice_minor=INVOICE))
    assert chosen is not None
    assert chosen.source == SOURCE_REFERRAL_CODE


def test_a_referral_code_percent_discount_is_compared_by_real_value_too():
    store = MemoryDataStore()
    engine = _mutual_benefit_with(store, discount_kind="percent", discount_amount=5)  # 5 SAR

    class FakeReferralCode:
        async def eligibility(self, tenant, phone):
            return {"eligible": True, "new_customer_reward_type": "discount_percent",
                   "new_customer_reward_params": {"percent": 40}}             # 40 SAR

    gateway = EntitlementGateway(mutual_benefit_engine=engine,
                                referral_code_engine=FakeReferralCode())
    chosen = run(gateway.choose(tenant=B, subject_ref="s", phone=PHONE, service_ids=[],
                                invoice_minor=INVOICE))
    assert chosen.source == SOURCE_REFERRAL_CODE
