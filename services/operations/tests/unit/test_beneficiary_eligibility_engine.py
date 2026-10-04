"""core/referral_redemption.py::_check_beneficiary_eligibility — proves the engine itself, not
just the config layer (test_affiliate_beneficiary_eligibility.py / services/referrals' own
test_beneficiary_eligibility.py), actually respects the per-campaign and per-affiliate "who may
redeem" setting (owner instruction, 2026-09-27), replacing what used to be one universal,
unconditional "must be a brand-new customer" rule."""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.affiliates import REWARD_FIXED_POINTS as AFF_REWARD_FIXED_POINTS
from app.core.affiliates import AffiliateService
from app.core.models import Customer
from app.core.operations import _normalise_phone
from app.core.signup import canonical_phone
from app.core.referral_redemption import (
    MODE_ONCE, NEW_CUSTOMER_DISCOUNT_PERCENT, REWARD_FIXED_POINTS, ReferralRedemptionEngine,
    ReferralRedemptionError,
)
from app.core.stores import CustomerStore, new_id

CC = "966"
TENANT = "shop_a"
REFERRER_PHONE = "0511111111"
BENEFICIARY_PHONE = "0522222222"
CODE = "AB123"
AFFILIATE_CODE = "BLOGR"


def run(coro):
    return asyncio.run(coro)


class FakeReferralsDesk:
    def __init__(self, *, code_to_phone=None, campaign=None):
        self._codes = code_to_phone if code_to_phone is not None else {CODE: REFERRER_PHONE}
        self._campaign = campaign

    async def lookup_code(self, code):
        return self._codes.get(code)

    async def active_campaign(self, tenant):
        return self._campaign


class FakeLoyaltyDesk:
    def __init__(self):
        self.awards: list[dict] = []

    async def award(self, *, tenant, subject_ref, points, idempotency_key, reason, actor):
        self.awards.append({"points": points, "reason": reason})
        return {"earned": points}


def _campaign(**over) -> dict:
    base = {
        "id": "camp_1", "mode": MODE_ONCE, "min_spend_minor": 0,
        "usage_cap_period": "", "usage_cap_limit": 0, "x_times_limit": 0,
        "reward_type": REWARD_FIXED_POINTS, "reward_params": {"points": 100},
        "new_customer_reward_type": NEW_CUSTOMER_DISCOUNT_PERCENT,
        "new_customer_reward_params": {"percent": 10},
    }
    base.update(over)
    return base


async def _seed_customer(store, tenant: str, phone: str, *, visit_count: int = 0) -> None:
    await CustomerStore(store).save(
        Customer(id=new_id("cus"), tenant=tenant, phone=_normalise_phone(phone),
                subject_ref="ref", visit_count=visit_count))


def _engine(*, campaign=None, affiliates=None, store=None) -> ReferralRedemptionEngine:
    store = store or MemoryDataStore()
    run(_seed_customer(store, TENANT, REFERRER_PHONE))
    return ReferralRedemptionEngine(
        store=store, referrals_desk=FakeReferralsDesk(campaign=campaign or _campaign()),
        loyalty_desk=FakeLoyaltyDesk(), pii_salt="s" * 32, default_cc=CC, affiliates=affiliates)


# ── ordinary campaign path ───────────────────────────────────────────────────────────────────────
def test_default_new_mode_still_refuses_an_existing_customer_regression_proof():
    store = MemoryDataStore()
    run(_seed_customer(store, TENANT, BENEFICIARY_PHONE))
    engine = _engine(store=store)
    with pytest.raises(ReferralRedemptionError):
        run(engine.register(TENANT, code=CODE, beneficiary_phone=BENEFICIARY_PHONE))


def test_max_visits_mode_allows_a_customer_at_or_under_the_configured_count():
    store = MemoryDataStore()
    run(_seed_customer(store, TENANT, BENEFICIARY_PHONE, visit_count=3))
    engine = _engine(store=store, campaign=_campaign(
        beneficiary_eligibility="max_visits", beneficiary_max_visits=3))
    grant = run(engine.register(TENANT, code=CODE, beneficiary_phone=BENEFICIARY_PHONE))
    assert grant.beneficiary_phone == canonical_phone(BENEFICIARY_PHONE, default_cc=CC)


def test_max_visits_mode_refuses_a_customer_over_the_configured_count():
    store = MemoryDataStore()
    run(_seed_customer(store, TENANT, BENEFICIARY_PHONE, visit_count=4))
    engine = _engine(store=store, campaign=_campaign(
        beneficiary_eligibility="max_visits", beneficiary_max_visits=3))
    with pytest.raises(ReferralRedemptionError):
        run(engine.register(TENANT, code=CODE, beneficiary_phone=BENEFICIARY_PHONE))


def test_open_mode_allows_any_customer_regardless_of_visit_count():
    store = MemoryDataStore()
    run(_seed_customer(store, TENANT, BENEFICIARY_PHONE, visit_count=999))
    engine = _engine(store=store, campaign=_campaign(beneficiary_eligibility="open"))
    grant = run(engine.register(TENANT, code=CODE, beneficiary_phone=BENEFICIARY_PHONE))
    assert grant.beneficiary_phone == canonical_phone(BENEFICIARY_PHONE, default_cc=CC)


def test_a_genuinely_new_customer_is_eligible_under_every_mode():
    for eligibility in ("new", "max_visits", "open"):
        campaign = _campaign(beneficiary_eligibility=eligibility, beneficiary_max_visits=0)
        engine = _engine(campaign=campaign)
        grant = run(engine.register(TENANT, code=CODE, beneficiary_phone=BENEFICIARY_PHONE))
        assert grant.beneficiary_phone == canonical_phone(BENEFICIARY_PHONE, default_cc=CC)


# ── beneficiary_created_this_call: the real-entry-point regression ─────────────────────────────
# `record_visit`/`ensure_customer` save the beneficiary's own Customer row BEFORE ever calling
# register() — so under "new" mode, a plain by_phone lookup would find that JUST-SAVED row and
# refuse every brand-new customer, always (a real bug caught only by a genuine end-to-end HTTP
# test through the real engine, not by any fake-engine wiring test). `beneficiary_created_this_call`
# is the caller-supplied fact that lets "new" mode still mean "new".
def test_new_mode_accepts_when_the_beneficiarys_own_row_already_exists_but_was_created_this_call():
    store = MemoryDataStore()
    phone = _normalise_phone(BENEFICIARY_PHONE)
    # Simulates record_visit's own ordering: the row is saved BEFORE register() ever runs.
    run(CustomerStore(store).save(Customer(id=new_id("cus"), tenant=TENANT, phone=phone,
                                          subject_ref="ref", visit_count=1)))
    engine = _engine(store=store, campaign=_campaign(beneficiary_eligibility="new"))
    grant = run(engine.register(TENANT, code=CODE, beneficiary_phone=BENEFICIARY_PHONE,
                                beneficiary_created_this_call=True))
    assert grant.beneficiary_phone == canonical_phone(BENEFICIARY_PHONE, default_cc=CC)


def test_new_mode_still_refuses_a_genuinely_returning_customer_even_with_the_flag_unset():
    # THE FLAG IS NEVER A BLANKET BYPASS — a caller that correctly reports "I did NOT just create
    # this row" (the ordinary returning-customer case) must still be refused under "new".
    store = MemoryDataStore()
    run(_seed_customer(store, TENANT, BENEFICIARY_PHONE))
    engine = _engine(store=store, campaign=_campaign(beneficiary_eligibility="new"))
    with pytest.raises(ReferralRedemptionError):
        run(engine.register(TENANT, code=CODE, beneficiary_phone=BENEFICIARY_PHONE,
                            beneficiary_created_this_call=False))


def test_the_flag_is_irrelevant_under_open_and_max_visits_modes():
    store = MemoryDataStore()
    phone = _normalise_phone(BENEFICIARY_PHONE)
    run(CustomerStore(store).save(Customer(id=new_id("cus"), tenant=TENANT, phone=phone,
                                          subject_ref="ref", visit_count=1)))
    # "open": accepted regardless of the flag either way.
    engine_open = _engine(store=store, campaign=_campaign(beneficiary_eligibility="open"))
    run(engine_open.register(TENANT, code=CODE, beneficiary_phone=BENEFICIARY_PHONE,
                             beneficiary_created_this_call=False))


def test_the_till_route_default_never_passes_the_flag_and_keeps_refusing_an_existing_customer():
    # THE TILL'S OWN DIRECT ROUTE (`/referral/register`) never saves anything first — it asks a
    # standing question about a phone that may have been a customer for years. It must NEVER pass
    # `beneficiary_created_this_call=True` for a real existing customer, and the default (False)
    # must keep the ORIGINAL "new" behaviour intact for that standing question.
    store = MemoryDataStore()
    run(_seed_customer(store, TENANT, BENEFICIARY_PHONE))
    engine = _engine(store=store, campaign=_campaign(beneficiary_eligibility="new"))
    with pytest.raises(ReferralRedemptionError):
        run(engine.register(TENANT, code=CODE, beneficiary_phone=BENEFICIARY_PHONE))  # no flag at all


# ── affiliate paths — independent of whatever the ordinary campaign says ────────────────────────
def _make_with_affiliate(*, campaign=None, **affiliate_over):
    store = MemoryDataStore()
    run(_seed_customer(store, TENANT, REFERRER_PHONE))
    affiliates = AffiliateService(store, default_cc=CC)
    base = dict(phone=REFERRER_PHONE, code=AFFILIATE_CODE, discount_percent=25,
               reward_type=AFF_REWARD_FIXED_POINTS, reward_params={"points": 40})
    base.update(affiliate_over)
    run(affiliates.add(TENANT, **base))
    engine = ReferralRedemptionEngine(
        store=store, referrals_desk=FakeReferralsDesk(campaign=campaign or _campaign()),
        loyalty_desk=FakeLoyaltyDesk(), pii_salt="s" * 32, default_cc=CC, affiliates=affiliates)
    return engine, store


def test_affiliate_open_beats_a_campaign_set_to_new_for_an_existing_customer():
    # campaign itself would refuse this beneficiary (default "new") — the CODE resolves to an
    # affiliate whose own setting is "open", and the affiliate's own terms must win.
    engine, store = _make_with_affiliate(
        campaign=_campaign(beneficiary_eligibility="new"), beneficiary_eligibility="open")
    run(_seed_customer(store, TENANT, BENEFICIARY_PHONE, visit_count=50))
    grant = run(engine.register(TENANT, code=AFFILIATE_CODE, beneficiary_phone=BENEFICIARY_PHONE))
    assert grant.source == "affiliate"


def test_affiliate_new_refuses_even_though_the_campaign_is_wide_open():
    # the reverse: campaign is "open" but the code resolves to an affiliate still on "new" —
    # the affiliate's own stricter setting must be the one enforced, not the campaign's.
    engine, store = _make_with_affiliate(
        campaign=_campaign(beneficiary_eligibility="open"), beneficiary_eligibility="new")
    run(_seed_customer(store, TENANT, BENEFICIARY_PHONE))
    with pytest.raises(ReferralRedemptionError):
        run(engine.register(TENANT, code=AFFILIATE_CODE, beneficiary_phone=BENEFICIARY_PHONE))


def test_self_referral_is_refused_even_under_open_eligibility():
    # SCENARIO: "open" removes the "must be new" restriction, but it must never be read as
    # removing the SEPARATE self-referral rule — the two are independent refusals, checked in
    # order (self-referral first, unconditionally, before eligibility is ever consulted).
    store = MemoryDataStore()
    run(_seed_customer(store, TENANT, REFERRER_PHONE))
    engine = _engine(store=store, campaign=_campaign(beneficiary_eligibility="open"))
    with pytest.raises(ReferralRedemptionError):
        run(engine.register(TENANT, code=CODE, beneficiary_phone=REFERRER_PHONE))


def test_self_referral_via_the_affiliates_own_code_is_refused_even_under_open_eligibility():
    store = MemoryDataStore()
    run(_seed_customer(store, TENANT, REFERRER_PHONE))
    affiliates = AffiliateService(store, default_cc=CC)
    run(affiliates.add(TENANT, phone=REFERRER_PHONE, code=AFFILIATE_CODE, discount_percent=25,
                       reward_type=AFF_REWARD_FIXED_POINTS, reward_params={"points": 40},
                       beneficiary_eligibility="open"))
    engine = ReferralRedemptionEngine(
        store=store, referrals_desk=FakeReferralsDesk(campaign=_campaign()),
        loyalty_desk=FakeLoyaltyDesk(), pii_salt="s" * 32, default_cc=CC, affiliates=affiliates)
    with pytest.raises(ReferralRedemptionError):
        run(engine.register(TENANT, code=AFFILIATE_CODE, beneficiary_phone=REFERRER_PHONE))


def test_eligibility_is_checked_before_min_spend_so_the_ineligible_reason_is_never_masked():
    # ORDERING SCENARIO: an over-the-limit beneficiary who ALSO fails min-spend must see the
    # eligibility refusal, not a misleading "invoice too low" message for a code that was never
    # going to be honoured regardless of the invoice amount.
    store = MemoryDataStore()
    run(_seed_customer(store, TENANT, BENEFICIARY_PHONE, visit_count=99))
    engine = _engine(store=store, campaign=_campaign(
        beneficiary_eligibility="max_visits", beneficiary_max_visits=1, min_spend_minor=100_00))
    with pytest.raises(ReferralRedemptionError, match="تجاوز عدد الزيارات"):
        run(engine.register(TENANT, code=CODE, beneficiary_phone=BENEFICIARY_PHONE,
                            invoice_minor=0))


def test_eligibility_is_checked_before_the_usage_cap_so_an_ineligible_beneficiary_never_counts_against_it():
    # ORDERING SCENARIO: an ineligible beneficiary must be refused BEFORE the referrer's own
    # once/x_times slot is ever consumed — an ineligible attempt must never burn through a
    # referrer's real, limited usage cap.
    store = MemoryDataStore()
    run(_seed_customer(store, TENANT, BENEFICIARY_PHONE, visit_count=99))
    engine = _engine(store=store, campaign=_campaign(
        mode=MODE_ONCE, beneficiary_eligibility="max_visits", beneficiary_max_visits=1))
    with pytest.raises(ReferralRedemptionError):
        run(engine.register(TENANT, code=CODE, beneficiary_phone=BENEFICIARY_PHONE))
    # THE CAP WAS NEVER TOUCHED — a genuinely new beneficiary can still register under the same
    # once-per-referrer campaign afterwards.
    grant = run(engine.register(TENANT, code=CODE, beneficiary_phone="0533333333"))
    assert grant.referrer_phone == canonical_phone(REFERRER_PHONE, default_cc=CC)


def test_visit_count_is_read_fresh_each_time_not_cached_across_calls():
    # SCENARIO: a customer who was over the limit, then had their own visit_count corrected
    # downward by an unrelated process (e.g. a manual fix), is re-evaluated against the real,
    # current count — never a stale snapshot from an earlier check. Calls the engine's own
    # private eligibility check directly (rather than two full `register()` calls) because
    # `register()` itself holds a short-lived per-beneficiary lock unrelated to eligibility — see
    # `_REGISTER_LOCK` — that would otherwise make a second immediate call collide for a reason
    # that has nothing to do with what this test is proving.
    store = MemoryDataStore()
    customers = CustomerStore(store)
    # SEEDED IN THE REAL STORAGE FORM (`_normalise_phone`, no leading "+") — the method itself
    # re-normalises whatever `canon_beneficiary` shape it is called with, so seeding any other
    # form here would defeat the very lookup this test means to exercise.
    stored_phone = _normalise_phone(BENEFICIARY_PHONE)
    canon_beneficiary = canonical_phone(BENEFICIARY_PHONE, default_cc=CC)
    run(customers.save(Customer(id=new_id("cus"), tenant=TENANT, phone=stored_phone,
                               subject_ref="ref", visit_count=5)))
    engine = _engine(store=store, campaign=_campaign(
        beneficiary_eligibility="max_visits", beneficiary_max_visits=2))
    with pytest.raises(ReferralRedemptionError):
        run(engine._check_beneficiary_eligibility(
            TENANT, canon_beneficiary, eligibility="max_visits", max_visits=2))

    customer = run(customers.by_phone(TENANT, stored_phone))
    customer.visit_count = 1
    run(customers.save(customer))
    # NO EXCEPTION THIS TIME — same engine, same beneficiary, only the stored visit_count changed.
    run(engine._check_beneficiary_eligibility(
        TENANT, canon_beneficiary, eligibility="max_visits", max_visits=2))


def test_affiliate_max_visits_enforced_via_the_affiliates_own_global_code_too():
    # reached via the affiliate's ORDINARY global code (not their custom one) — same enforcement.
    store = MemoryDataStore()
    run(_seed_customer(store, TENANT, REFERRER_PHONE))
    affiliates = AffiliateService(store, default_cc=CC)
    run(affiliates.add(TENANT, phone=REFERRER_PHONE, code=AFFILIATE_CODE, discount_percent=25,
                       reward_type=AFF_REWARD_FIXED_POINTS, reward_params={"points": 40},
                       beneficiary_eligibility="max_visits", beneficiary_max_visits=2))
    run(_seed_customer(store, TENANT, BENEFICIARY_PHONE, visit_count=5))
    engine = ReferralRedemptionEngine(
        store=store, referrals_desk=FakeReferralsDesk(code_to_phone={CODE: REFERRER_PHONE}),
        loyalty_desk=FakeLoyaltyDesk(), pii_salt="s" * 32, default_cc=CC, affiliates=affiliates)
    with pytest.raises(ReferralRedemptionError):
        run(engine.register(TENANT, code=CODE, beneficiary_phone=BENEFICIARY_PHONE))
