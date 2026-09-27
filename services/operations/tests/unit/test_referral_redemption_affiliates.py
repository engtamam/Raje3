"""Phase 4 — the affiliate tier's own integration into core/referral_redemption.py: a custom
code entered directly, the SAME referrer phone reached via their ordinary global code, and the
"never both roles" rule holding at redemption time."""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.adapters.referrals_desk import ReferralsPeerUnavailable
from app.core.affiliates import REWARD_FIXED_POINTS, REWARD_INVOICE_PERCENTAGE, AffiliateService
from app.core.models import Customer
from app.core.operations import _normalise_phone
from app.core.signup import canonical_phone
from app.core.referral_redemption import (
    MODE_ONCE, NEW_CUSTOMER_DISCOUNT_PERCENT, ReferralRedemptionEngine, ReferralRedemptionError,
)
from app.core.stores import CustomerStore, new_id

CC = "966"
TENANT = "shop_a"
AFFILIATE_PHONE = "0511111111"
BENEFICIARY_PHONE = "0522222222"
GLOBAL_CODE = "AB123"        # the affiliate's own ordinary, global anonymous code
AFFILIATE_CODE = "BLOGR"     # the affiliate's separate, shop-chosen custom code


def run(coro):
    return asyncio.run(coro)


class FakeReferralsDesk:
    """The GLOBAL lookup — an affiliate integration must never call this for their OWN custom
    code (see the assertion on `lookup_calls` below); it is only ever consulted for a genuinely
    ordinary global code."""

    def __init__(self, *, code_to_phone=None, campaign=None):
        self._codes = code_to_phone if code_to_phone is not None else {GLOBAL_CODE: AFFILIATE_PHONE}
        self._campaign = campaign
        self.configured = True
        self.lookup_calls = 0
        self.active_campaign_calls = 0

    async def lookup_code(self, code):
        self.lookup_calls += 1
        return self._codes.get(code)

    async def active_campaign(self, tenant):
        self.active_campaign_calls += 1
        return self._campaign


class FakeLoyaltyDesk:
    def __init__(self):
        self.awards: list[dict] = []

    async def award(self, *, tenant, subject_ref, points, idempotency_key, reason, actor):
        self.awards.append({"points": points, "reason": reason})
        return {"earned": points}


async def _seed_customer(store, tenant: str, phone: str) -> None:
    """When an affiliate's code falls through to the ORDINARY campaign path (inactive affiliate,
    or no affiliates wired), the referrer must already be an existing customer here (deep-review
    Phase 5c) — AFFILIATE_PHONE is seeded by default below so those fallthrough tests keep
    exercising what they were written to test."""
    await CustomerStore(store).save(
        Customer(id=new_id("cus"), tenant=tenant, phone=_normalise_phone(phone),
                subject_ref="ref"))


def _make(*, referrals=None, loyalty=None, affiliates=None, store=None):
    store = store or MemoryDataStore()
    run(_seed_customer(store, TENANT, AFFILIATE_PHONE))
    affiliates = affiliates or AffiliateService(store, default_cc=CC)
    engine = ReferralRedemptionEngine(
        store=store, referrals_desk=referrals or FakeReferralsDesk(),
        loyalty_desk=loyalty or FakeLoyaltyDesk(), pii_salt="s" * 32, default_cc=CC,
        affiliates=affiliates)
    return engine, affiliates


def _add_affiliate(affiliates, **over):
    base = dict(phone=AFFILIATE_PHONE, code=AFFILIATE_CODE, discount_percent=25,
               reward_type=REWARD_FIXED_POINTS, reward_params={"points": 40})
    base.update(over)
    return run(affiliates.add(TENANT, **base))


# ── entering the affiliate's own custom code directly ───────────────────────────────────────────
def test_the_custom_code_never_calls_the_global_referrals_service_at_all():
    referrals = FakeReferralsDesk()
    engine, affiliates = _make(referrals=referrals)
    _add_affiliate(affiliates)
    run(engine.register(TENANT, code=AFFILIATE_CODE, beneficiary_phone=BENEFICIARY_PHONE))
    assert referrals.lookup_calls == 0
    assert referrals.active_campaign_calls == 0


def test_the_custom_code_uses_the_affiliates_own_discount_and_reward_not_any_campaign():
    engine, affiliates = _make()
    _add_affiliate(affiliates, discount_percent=25, reward_type=REWARD_FIXED_POINTS,
                   reward_params={"points": 40})
    grant = run(engine.register(TENANT, code=AFFILIATE_CODE, beneficiary_phone=BENEFICIARY_PHONE))
    assert grant.new_customer_reward_type == NEW_CUSTOMER_DISCOUNT_PERCENT
    assert grant.new_customer_reward_params == {"percent": 25}
    assert grant.referrer_reward_type == REWARD_FIXED_POINTS
    assert grant.referrer_reward_params == {"points": 40}
    assert grant.source == "affiliate"
    assert grant.campaign_id == ""


def test_the_custom_code_has_no_campaign_so_it_never_enforces_min_spend_or_usage_caps():
    # No active_campaign is even wired here (None) — proving the affiliate path truly never
    # touches campaign machinery, unlike the ordinary path which would refuse with no campaign.
    engine, affiliates = _make(referrals=FakeReferralsDesk(campaign=None))
    _add_affiliate(affiliates)
    grant = run(engine.register(TENANT, code=AFFILIATE_CODE, beneficiary_phone=BENEFICIARY_PHONE,
                                invoice_minor=0))
    assert grant.source == "affiliate"


def test_the_custom_code_self_referral_is_still_refused():
    engine, affiliates = _make()
    _add_affiliate(affiliates)
    with pytest.raises(ReferralRedemptionError):
        run(engine.register(TENANT, code=AFFILIATE_CODE, beneficiary_phone=AFFILIATE_PHONE))


def test_an_inactive_affiliates_custom_code_falls_through_to_the_ordinary_global_lookup():
    referrals = FakeReferralsDesk(code_to_phone={AFFILIATE_CODE: "0533333333"},
                                  campaign={
                                      "id": "camp_1", "mode": MODE_ONCE, "min_spend_minor": 0,
                                      "usage_cap_period": "", "usage_cap_limit": 0,
                                      "x_times_limit": 0, "reward_type": REWARD_FIXED_POINTS,
                                      "reward_params": {"points": 5},
                                      "new_customer_reward_type": NEW_CUSTOMER_DISCOUNT_PERCENT,
                                      "new_customer_reward_params": {"percent": 5},
                                  })
    engine, affiliates = _make(referrals=referrals)
    a = _add_affiliate(affiliates)
    run(affiliates.set_active(TENANT, a.id, active=False))
    run(_seed_customer(engine._s, TENANT, "0533333333"))  # the OTHER referrer this code now maps to
    # the (now-inactive) affiliate's OWN former code happens to also be a real global code held
    # by someone else — the deactivated affiliate row must never shadow it.
    grant = run(engine.register(TENANT, code=AFFILIATE_CODE, beneficiary_phone=BENEFICIARY_PHONE))
    assert grant.source == "referral"
    assert referrals.lookup_calls == 1


# ── entering the affiliate's ORDINARY global code — "never both roles" holds either way ────────
def test_the_affiliates_ordinary_global_code_also_uses_affiliate_terms_not_the_campaign():
    referrals = FakeReferralsDesk(code_to_phone={GLOBAL_CODE: AFFILIATE_PHONE}, campaign={
        "id": "camp_1", "mode": MODE_ONCE, "min_spend_minor": 0, "usage_cap_period": "",
        "usage_cap_limit": 0, "x_times_limit": 0, "reward_type": "invoice_percentage",
        "reward_params": {"percent": 99},
        "new_customer_reward_type": NEW_CUSTOMER_DISCOUNT_PERCENT,
        "new_customer_reward_params": {"percent": 1},
    })
    engine, affiliates = _make(referrals=referrals)
    _add_affiliate(affiliates, discount_percent=25, reward_type=REWARD_FIXED_POINTS,
                   reward_params={"points": 40})

    grant = run(engine.register(TENANT, code=GLOBAL_CODE, beneficiary_phone=BENEFICIARY_PHONE))
    # AFFILIATE terms won, never the ordinary campaign's (99%/1% above would be a dead giveaway
    # if the campaign path had been used instead).
    assert grant.source == "affiliate"
    assert grant.new_customer_reward_params == {"percent": 25}
    assert grant.referrer_reward_params == {"points": 40}
    # the campaign was never even read, since the affiliate check short-circuits before it.
    assert referrals.active_campaign_calls == 0


def test_a_deactivated_affiliate_reached_via_their_global_code_uses_the_ordinary_campaign():
    referrals = FakeReferralsDesk(code_to_phone={GLOBAL_CODE: AFFILIATE_PHONE}, campaign={
        "id": "camp_1", "mode": MODE_ONCE, "min_spend_minor": 0, "usage_cap_period": "",
        "usage_cap_limit": 0, "x_times_limit": 0, "reward_type": REWARD_FIXED_POINTS,
        "reward_params": {"points": 7},
        "new_customer_reward_type": NEW_CUSTOMER_DISCOUNT_PERCENT,
        "new_customer_reward_params": {"percent": 8},
    })
    engine, affiliates = _make(referrals=referrals)
    a = _add_affiliate(affiliates)
    run(affiliates.set_active(TENANT, a.id, active=False))

    grant = run(engine.register(TENANT, code=GLOBAL_CODE, beneficiary_phone=BENEFICIARY_PHONE))
    assert grant.source == "referral"
    assert grant.referrer_reward_params == {"points": 7}


# ── redeem(): affiliate crediting is tagged differently and feeds the settlement balance ────────
def test_redeem_credits_loyalty_tagged_affiliate_and_updates_the_settlement_balance():
    loyalty = FakeLoyaltyDesk()
    engine, affiliates = _make(loyalty=loyalty)
    a = _add_affiliate(affiliates, reward_type=REWARD_FIXED_POINTS, reward_params={"points": 40})
    run(engine.register(TENANT, code=AFFILIATE_CODE, beneficiary_phone=BENEFICIARY_PHONE))
    result = run(engine.redeem(TENANT, BENEFICIARY_PHONE, visit_id="v1"))

    assert result is True
    assert loyalty.awards == [{"points": 40, "reason": "affiliate"}]
    updated = run(affiliates.get(TENANT, a.id))
    assert updated.unsettled_points == 40
    assert updated.total_earned_points == 40


def test_redeem_of_an_ordinary_grant_never_touches_any_affiliate_balance():
    loyalty = FakeLoyaltyDesk()
    referrals = FakeReferralsDesk(campaign={
        "id": "camp_1", "mode": MODE_ONCE, "min_spend_minor": 0, "usage_cap_period": "",
        "usage_cap_limit": 0, "x_times_limit": 0, "reward_type": REWARD_FIXED_POINTS,
        "reward_params": {"points": 10},
        "new_customer_reward_type": NEW_CUSTOMER_DISCOUNT_PERCENT,
        "new_customer_reward_params": {"percent": 10},
    })
    engine, affiliates = _make(referrals=referrals, loyalty=loyalty)
    run(engine.register(TENANT, code=GLOBAL_CODE, beneficiary_phone=BENEFICIARY_PHONE))
    run(engine.redeem(TENANT, BENEFICIARY_PHONE, visit_id="v1"))
    assert loyalty.awards == [{"points": 10, "reason": "referral"}]


def test_a_retried_redeem_never_double_credits_the_affiliate_balance():
    engine, affiliates = _make()
    a = _add_affiliate(affiliates)
    run(engine.register(TENANT, code=AFFILIATE_CODE, beneficiary_phone=BENEFICIARY_PHONE))
    run(engine.redeem(TENANT, BENEFICIARY_PHONE, visit_id="v1"))
    run(engine.redeem(TENANT, BENEFICIARY_PHONE, visit_id="v1"))
    assert run(affiliates.get(TENANT, a.id)).unsettled_points == 40


def test_invoice_percentage_affiliate_reward_scales_off_the_registered_invoice():
    engine, affiliates = _make()
    a = _add_affiliate(affiliates, reward_type=REWARD_INVOICE_PERCENTAGE,
                       reward_params={"percent": 10})
    run(engine.register(TENANT, code=AFFILIATE_CODE, beneficiary_phone=BENEFICIARY_PHONE,
                        invoice_minor=20000))
    run(engine.redeem(TENANT, BENEFICIARY_PHONE, visit_id="v1"))
    assert run(affiliates.get(TENANT, a.id)).unsettled_points == 2000  # 10% of 20000


# ── an unreachable affiliates dependency must never crash a redemption that has nothing to do
# with any affiliate ─────────────────────────────────────────────────────────────────────────────
def test_engine_with_no_affiliates_wired_behaves_exactly_like_phase_3():
    referrals = FakeReferralsDesk(campaign={
        "id": "camp_1", "mode": MODE_ONCE, "min_spend_minor": 0, "usage_cap_period": "",
        "usage_cap_limit": 0, "x_times_limit": 0, "reward_type": REWARD_FIXED_POINTS,
        "reward_params": {"points": 10},
        "new_customer_reward_type": NEW_CUSTOMER_DISCOUNT_PERCENT,
        "new_customer_reward_params": {"percent": 10},
    })
    store = MemoryDataStore()
    run(_seed_customer(store, TENANT, AFFILIATE_PHONE))
    engine = ReferralRedemptionEngine(
        store=store, referrals_desk=referrals, loyalty_desk=FakeLoyaltyDesk(),
        pii_salt="s" * 32, default_cc=CC)  # affiliates=None, the default
    grant = run(engine.register(TENANT, code=GLOBAL_CODE, beneficiary_phone=BENEFICIARY_PHONE))
    assert grant.source == "referral"
