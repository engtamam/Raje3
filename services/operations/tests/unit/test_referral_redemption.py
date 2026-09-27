"""core/referral_redemption.py — Phase 3's own till-side redemption engine for the global
anonymous referral code. Fakes `ReferralsDesk` and the loyalty award call so this file proves the
engine's OWN logic (validation, usage caps, idempotent redeem, reward crediting) without a real
services/referrals or services/loyalty running."""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.referral_redemption import (
    MODE_ONCE, MODE_X_TIMES, NEW_CUSTOMER_DISCOUNT_PERCENT, REWARD_CASHBACK_POINTS,
    REWARD_FIXED_POINTS, REWARD_MYSTERY_BOX, ReferralRedemptionEngine, ReferralRedemptionError,
)

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


def _engine(*, code_to_phone=_UNSET, campaign=_UNSET, loyalty=None) -> ReferralRedemptionEngine:
    if code_to_phone is _UNSET:
        code_to_phone = {CODE: REFERRER_PHONE}
    if campaign is _UNSET:
        campaign = _campaign()
    return ReferralRedemptionEngine(
        store=MemoryDataStore(),
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
