"""core/referral_redemption.py — Phase 3's own till-side redemption engine for the global
anonymous referral code. Fakes `ReferralsDesk` and the loyalty award call so this file proves the
engine's OWN logic (validation, usage caps, idempotent redeem, reward crediting) without a real
services/referrals or services/loyalty running."""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.models import Customer
from app.core.operations import _normalise_phone
from app.core.signup import canonical_phone
from app.core.referral_redemption import (
    MODE_ONCE, MODE_X_TIMES, NEW_CUSTOMER_DISCOUNT_PERCENT, REWARD_CASHBACK_POINTS,
    REWARD_FIXED_POINTS, REWARD_MYSTERY_BOX, ReferralRedemptionEngine, ReferralRedemptionError,
)
from app.core.stores import CustomerStore, new_id

CC = "966"
TENANT = "shop_a"
REFERRER_PHONE = "0511111111"
BENEFICIARY_PHONE = "0522222222"
CODE = "AB123"


def run(coro):
    return asyncio.run(coro)


class FakeReferralsDesk:
    def __init__(self, *, code_to_phone: dict | None = None,
                campaign: dict | None = None) -> None:
        self._codes = code_to_phone or {}
        self._campaign = campaign
        self.configured = True

    async def lookup_code(self, code):
        return self._codes.get(code)

    async def active_campaign(self, tenant):
        return self._campaign


class FakeLoyaltyDesk:
    def __init__(self) -> None:
        self.awards: list[dict] = []

    async def award(self, *, tenant, subject_ref, points, idempotency_key, reason, actor):
        self.awards.append({"tenant": tenant, "subject_ref": subject_ref, "points": points,
                            "idempotency_key": idempotency_key, "reason": reason})
        return {"earned": points, "balance": points, "entry_id": "e1"}


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


_UNSET = object()


async def _seed_customer(store, tenant: str, phone: str) -> None:
    """Deep-review Phase 5c added a real requirement to register(): the ordinary global-code
    referrer must already be an existing Customer at this tenant (see referral_redemption.py's
    own comment on that check). Every test in this file that expects register() to SUCCEED for
    REFERRER_PHONE needs that phone seeded as a customer first — this is that seed, reused by
    the default `_engine()` factory below so existing happy-path tests keep testing what they
    were written to test, not this newer, separate guard (which has its own dedicated tests)."""
    await CustomerStore(store).save(
        Customer(id=new_id("cus"), tenant=tenant, phone=_normalise_phone(phone),
                subject_ref="ref"))


def _engine(*, code_to_phone=_UNSET, campaign=_UNSET, loyalty=None,
           seed_referrer: bool = True) -> ReferralRedemptionEngine:
    if code_to_phone is _UNSET:
        code_to_phone = {CODE: REFERRER_PHONE}
    if campaign is _UNSET:
        campaign = _campaign()
    store = MemoryDataStore()
    if seed_referrer:
        run(_seed_customer(store, TENANT, REFERRER_PHONE))
    return ReferralRedemptionEngine(
        store=store,
        referrals_desk=FakeReferralsDesk(code_to_phone=code_to_phone, campaign=campaign),
        loyalty_desk=loyalty or FakeLoyaltyDesk(), pii_salt="s" * 32, default_cc=CC)


# ── register(): every refusal ────────────────────────────────────────────────────────────────────
def test_unknown_code_is_refused():
    engine = _engine(code_to_phone={})
    with pytest.raises(ReferralRedemptionError):
        run(engine.register(TENANT, code=CODE, beneficiary_phone=BENEFICIARY_PHONE))


def test_self_referral_is_refused():
    engine = _engine(code_to_phone={CODE: BENEFICIARY_PHONE})
    with pytest.raises(ReferralRedemptionError):
        run(engine.register(TENANT, code=CODE, beneficiary_phone=BENEFICIARY_PHONE))


def test_no_active_campaign_is_refused():
    engine = _engine(campaign=None)
    with pytest.raises(ReferralRedemptionError):
        run(engine.register(TENANT, code=CODE, beneficiary_phone=BENEFICIARY_PHONE))


def test_below_min_spend_is_refused():
    engine = _engine(campaign=_campaign(min_spend_minor=5000))
    with pytest.raises(ReferralRedemptionError):
        run(engine.register(TENANT, code=CODE, beneficiary_phone=BENEFICIARY_PHONE,
                           invoice_minor=1000))


def test_at_or_above_min_spend_is_accepted():
    engine = _engine(campaign=_campaign(min_spend_minor=5000))
    grant = run(engine.register(TENANT, code=CODE, beneficiary_phone=BENEFICIARY_PHONE,
                                invoice_minor=5000))
    assert grant.beneficiary_phone


def test_a_blank_code_is_refused_not_crashed():
    engine = _engine()
    with pytest.raises(ReferralRedemptionError):
        run(engine.register(TENANT, code="", beneficiary_phone=BENEFICIARY_PHONE))


def test_a_blank_phone_is_refused_not_crashed():
    engine = _engine()
    with pytest.raises(ReferralRedemptionError):
        run(engine.register(TENANT, code=CODE, beneficiary_phone=""))


# ── register(): idempotency ─────────────────────────────────────────────────────────────────────
def test_registering_twice_for_the_same_beneficiary_returns_the_same_pending_grant():
    engine = _engine()
    first = run(engine.register(TENANT, code=CODE, beneficiary_phone=BENEFICIARY_PHONE))
    second = run(engine.register(TENANT, code=CODE, beneficiary_phone=BENEFICIARY_PHONE))
    assert first.id == second.id


# ── usage caps, enforced at register() ──────────────────────────────────────────────────────────
def test_mode_once_refuses_a_second_referrer_after_one_redeemed_grant():
    engine = _engine(campaign=_campaign(mode=MODE_ONCE))
    g1 = run(engine.register(TENANT, code=CODE, beneficiary_phone="0533333333"))
    run(engine.redeem(TENANT, "0533333333", visit_id="v1"))

    with pytest.raises(ReferralRedemptionError):
        run(engine.register(TENANT, code=CODE, beneficiary_phone="0544444444"))


def test_mode_x_times_allows_exactly_the_configured_limit():
    engine = _engine(campaign=_campaign(mode=MODE_X_TIMES, x_times_limit=2))
    run(engine.register(TENANT, code=CODE, beneficiary_phone="0533333333"))
    run(engine.redeem(TENANT, "0533333333", visit_id="v1"))
    run(engine.register(TENANT, code=CODE, beneficiary_phone="0544444444"))
    run(engine.redeem(TENANT, "0544444444", visit_id="v2"))

    with pytest.raises(ReferralRedemptionError):
        run(engine.register(TENANT, code=CODE, beneficiary_phone="0555555555"))


def test_mode_lifetime_never_caps():
    engine = _engine(campaign=_campaign(mode="lifetime"))
    for i in range(5):
        phone = f"05{i:09d}"
        run(engine.register(TENANT, code=CODE, beneficiary_phone=phone))
        run(engine.redeem(TENANT, phone, visit_id=f"v{i}"))
    # no exception raised for a 6th
    run(engine.register(TENANT, code=CODE, beneficiary_phone="0566666666"))


def test_usage_cap_period_and_limit_are_enforced_independently_of_mode():
    engine = _engine(campaign=_campaign(mode="lifetime", usage_cap_period="day", usage_cap_limit=1))
    run(engine.register(TENANT, code=CODE, beneficiary_phone="0533333333"))
    run(engine.redeem(TENANT, "0533333333", visit_id="v1"))

    with pytest.raises(ReferralRedemptionError):
        run(engine.register(TENANT, code=CODE, beneficiary_phone="0544444444"))


# ── cap_scope — owner-approved design change (deep-review Phase 5c) ──────────────────────────────
def test_cap_scope_lifetime_blocks_a_referrer_across_a_brand_new_campaign():
    engine = _engine(campaign=_campaign(mode=MODE_ONCE, cap_scope="lifetime"))
    run(engine.register(TENANT, code=CODE, beneficiary_phone="0533333333"))
    run(engine.redeem(TENANT, "0533333333", visit_id="v1"))
    # a BRAND-NEW campaign (different id) — with cap_scope=lifetime the referrer's earlier grant
    # under camp_1 must still block them here, even though campaign_id differs.
    engine._referrals._campaign = _campaign(mode=MODE_ONCE, cap_scope="lifetime", id="camp_2")
    with pytest.raises(ReferralRedemptionError):
        run(engine.register(TENANT, code=CODE, beneficiary_phone="0544444444"))


def test_cap_scope_campaign_default_lets_a_brand_new_campaign_reset_the_count():
    engine = _engine(campaign=_campaign(mode=MODE_ONCE))  # cap_scope omitted -> "campaign" default
    run(engine.register(TENANT, code=CODE, beneficiary_phone="0533333333"))
    run(engine.redeem(TENANT, "0533333333", visit_id="v1"))
    # a brand-new campaign (different id) resets the count — today's exact behaviour, unchanged.
    engine._referrals._campaign = _campaign(mode=MODE_ONCE, id="camp_2")
    run(engine.register(TENANT, code=CODE, beneficiary_phone="0544444444"))  # must succeed


# ── eligibility() / redeem(): the EntitlementGateway shape ──────────────────────────────────────
def test_eligibility_is_none_with_no_pending_grant():
    engine = _engine()
    assert run(engine.eligibility(TENANT, "0599999999")) is None


def test_eligibility_reflects_the_pending_grants_new_customer_reward():
    engine = _engine()
    run(engine.register(TENANT, code=CODE, beneficiary_phone=BENEFICIARY_PHONE))
    elig = run(engine.eligibility(TENANT, BENEFICIARY_PHONE))
    assert elig["eligible"] is True
    assert elig["new_customer_reward_type"] == NEW_CUSTOMER_DISCOUNT_PERCENT


def test_redeem_is_idempotent_on_visit_id():
    engine = _engine()
    run(engine.register(TENANT, code=CODE, beneficiary_phone=BENEFICIARY_PHONE))
    first = run(engine.redeem(TENANT, BENEFICIARY_PHONE, visit_id="v1"))
    second = run(engine.redeem(TENANT, BENEFICIARY_PHONE, visit_id="v1"))
    assert first is True and second is True
    # no longer eligible — a THIRD, different visit finds nothing pending
    assert run(engine.eligibility(TENANT, BENEFICIARY_PHONE)) is None


def test_redeem_with_no_pending_grant_returns_false():
    engine = _engine()
    assert run(engine.redeem(TENANT, "0599999999", visit_id="v1")) is False


# ── the referrer's own reward is credited exactly once, at redeem ───────────────────────────────
def test_redeem_credits_the_referrers_own_fixed_points():
    loyalty = FakeLoyaltyDesk()
    engine = _engine(campaign=_campaign(reward_type=REWARD_FIXED_POINTS,
                                        reward_params={"points": 40}), loyalty=loyalty)
    run(engine.register(TENANT, code=CODE, beneficiary_phone=BENEFICIARY_PHONE))
    run(engine.redeem(TENANT, BENEFICIARY_PHONE, visit_id="v1"))
    assert len(loyalty.awards) == 1
    assert loyalty.awards[0]["points"] == 40
    assert loyalty.awards[0]["reason"] == "referral"


def test_redeem_is_never_double_credited_on_a_retried_finalize():
    loyalty = FakeLoyaltyDesk()
    engine = _engine(loyalty=loyalty)
    run(engine.register(TENANT, code=CODE, beneficiary_phone=BENEFICIARY_PHONE))
    run(engine.redeem(TENANT, BENEFICIARY_PHONE, visit_id="v1"))
    run(engine.redeem(TENANT, BENEFICIARY_PHONE, visit_id="v1"))
    assert len(loyalty.awards) == 1


def test_cashback_points_credits_the_same_way_as_fixed_points():
    loyalty = FakeLoyaltyDesk()
    engine = _engine(campaign=_campaign(reward_type=REWARD_CASHBACK_POINTS,
                                        reward_params={"points": 15}), loyalty=loyalty)
    run(engine.register(TENANT, code=CODE, beneficiary_phone=BENEFICIARY_PHONE))
    run(engine.redeem(TENANT, BENEFICIARY_PHONE, visit_id="v1"))
    assert loyalty.awards[0]["points"] == 15


def test_invoice_percentage_computes_off_the_invoice_amount():
    loyalty = FakeLoyaltyDesk()
    engine = _engine(campaign=_campaign(reward_type="invoice_percentage",
                                        reward_params={"percent": 10}), loyalty=loyalty)
    run(engine.register(TENANT, code=CODE, beneficiary_phone=BENEFICIARY_PHONE,
                       invoice_minor=10000))
    run(engine.redeem(TENANT, BENEFICIARY_PHONE, visit_id="v1"))
    assert loyalty.awards[0]["points"] == 1000       # 10% of 10000


def test_mystery_box_credits_one_of_its_own_outcomes():
    loyalty = FakeLoyaltyDesk()
    engine = _engine(campaign=_campaign(
        reward_type=REWARD_MYSTERY_BOX,
        reward_params={"outcomes": [{"points": 5, "weight": 1}, {"points": 500, "weight": 1}]}),
        loyalty=loyalty)
    run(engine.register(TENANT, code=CODE, beneficiary_phone=BENEFICIARY_PHONE))
    run(engine.redeem(TENANT, BENEFICIARY_PHONE, visit_id="v1"))
    assert loyalty.awards[0]["points"] in (5, 500)


# ── the global code is honoured only where the referrer is ALREADY a customer (deep-review) ─────
def test_referrer_who_is_an_existing_customer_here_may_be_referred_from():
    engine = _engine()  # default _engine() already seeds REFERRER_PHONE as a customer
    grant = run(engine.register(TENANT, code=CODE, beneficiary_phone=BENEFICIARY_PHONE))
    assert grant.referrer_phone == canonical_phone(REFERRER_PHONE, default_cc=CC)


def test_referrer_who_is_not_a_customer_here_at_all_is_refused_like_an_unknown_code():
    # THE FIX: a shop must not be able to resolve ANY phone's global code and import a stranger's
    # real number into its own database with zero consent — the referrer must already be a
    # customer HERE, by any means, before their code is honoured at all.
    engine = _engine(seed_referrer=False)
    with pytest.raises(ReferralRedemptionError) as unknown_referrer:
        run(engine.register(TENANT, code=CODE, beneficiary_phone=BENEFICIARY_PHONE))
    # a SEPARATE beneficiary — the first call's own `_REGISTER_LOCK` claim is still held (register()
    # never explicitly releases it; it only expires by TTL), so reusing the same beneficiary phone
    # here would hit "registration already in progress", not the refusal this test means to compare.
    with pytest.raises(ReferralRedemptionError) as unknown_code:
        run(engine.register(TENANT, code="NOSUCHCODE", beneficiary_phone="0577777777"))
    # SAME REFUSAL SHAPE AS AN UNKNOWN CODE — never revealing WHY (the phone exists but isn't a
    # customer here, vs. the code simply not existing), since that difference is itself a minor
    # information disclosure worth avoiding.
    assert str(unknown_referrer.value) == str(unknown_code.value)


# ── a phone with ANY existing Customer row here is not a "new customer" (deep-review) ───────────
def test_a_genuinely_new_beneficiary_phone_may_register_normally():
    engine = _engine()
    grant = run(engine.register(TENANT, code=CODE, beneficiary_phone=BENEFICIARY_PHONE))
    assert grant.beneficiary_phone == canonical_phone(BENEFICIARY_PHONE, default_cc=CC)


def test_a_beneficiary_who_already_has_a_customer_row_here_is_refused_even_with_a_fresh_code():
    # Owner decision: "new customer" means no existing Customer row at this shop AT ALL — not
    # through a referral, not through a walk-in visit, not through anything — even if the exact
    # CODE being entered is one this phone has never used before.
    engine = _engine()
    run(_seed_customer(engine._s, TENANT, BENEFICIARY_PHONE))  # e.g. a prior walk-in visit
    with pytest.raises(ReferralRedemptionError):
        run(engine.register(TENANT, code=CODE, beneficiary_phone=BENEFICIARY_PHONE))


def test_status_multiplier_is_recorded_but_not_credited_this_phase():
    """A deliberate Phase 3 boundary — see the module docstring. Must not raise, must not credit
    points nobody defined a value for."""
    loyalty = FakeLoyaltyDesk()
    engine = _engine(campaign=_campaign(
        reward_type="status_multiplier",
        reward_params={"referrals_required": 3, "multiplier": 2.0}), loyalty=loyalty)
    run(engine.register(TENANT, code=CODE, beneficiary_phone=BENEFICIARY_PHONE))
    result = run(engine.redeem(TENANT, BENEFICIARY_PHONE, visit_id="v1"))
    assert result is True
    assert loyalty.awards == []
