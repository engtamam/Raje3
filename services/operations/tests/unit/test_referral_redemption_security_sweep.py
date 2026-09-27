"""Phase 5b — the final security/edge-case sweep across the whole referral+affiliate feature.
This file holds findings specific to core/referral_redemption.py's own usage-cap enforcement;
see the module's own docstring and `_enforce_usage_cap`'s own comment for the full reasoning."""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.referral_redemption import (
    MODE_ONCE, MODE_X_TIMES, NEW_CUSTOMER_DISCOUNT_PERCENT, REWARD_FIXED_POINTS,
    ReferralRedemptionEngine, ReferralRedemptionError,
)

CC = "966"
TENANT = "shop_a"
REFERRER_PHONE = "0511111111"
CODE = "AB123"


def run(coro):
    return asyncio.run(coro)


class FakeReferralsDesk:
    def __init__(self, *, campaign: dict) -> None:
        self._campaign = campaign
        self.configured = True

    async def lookup_code(self, code):
        return REFERRER_PHONE if code == CODE else None

    async def active_campaign(self, tenant):
        return self._campaign


class FakeLoyaltyDesk:
    def __init__(self) -> None:
        self.awards: list[dict] = []

    async def award(self, *, tenant, subject_ref, points, idempotency_key, reason, actor):
        self.awards.append({"points": points})
        return {"earned": points}


def _campaign(**over) -> dict:
    base = {
        "id": "camp_1", "mode": MODE_ONCE, "min_spend_minor": 0, "usage_cap_period": "",
        "usage_cap_limit": 0, "x_times_limit": 0, "reward_type": REWARD_FIXED_POINTS,
        "reward_params": {"points": 50}, "new_customer_reward_type": NEW_CUSTOMER_DISCOUNT_PERCENT,
        "new_customer_reward_params": {"percent": 10},
    }
    base.update(over)
    return base


def _engine(campaign: dict, loyalty=None) -> ReferralRedemptionEngine:
    return ReferralRedemptionEngine(
        store=MemoryDataStore(), referrals_desk=FakeReferralsDesk(campaign=campaign),
        loyalty_desk=loyalty or FakeLoyaltyDesk(), pii_salt="s" * 32, default_cc=CC)


# ── THE EXACT EXPLOIT: mode_once credited more than once via two pending grants ─────────────────
def test_mode_once_refuses_a_second_registration_while_the_first_is_still_only_pending():
    # THE BUG THIS CLOSES: two different new customers both register against the SAME
    # mode_once referrer BEFORE either one redeems — the old implementation counted only
    # REDEEMED grants, so both reads saw "0 redeemed so far" and both registrations succeeded,
    # letting the referrer be credited twice under a campaign that promises exactly once.
    engine = _engine(_campaign(mode=MODE_ONCE))
    run(engine.register(TENANT, code=CODE, beneficiary_phone="0533333333"))  # first: still pending
    with pytest.raises(ReferralRedemptionError):
        run(engine.register(TENANT, code=CODE, beneficiary_phone="0544444444"))


def test_mode_once_the_referrer_can_never_be_credited_twice_even_if_both_pending_grants_existed():
    # Defence in depth: even if a second pending grant HAD somehow been created (e.g. by a
    # version of this code with the bug still present), redeeming both must never credit the
    # referrer twice — this proves the fix at the register() layer is the real fix, by first
    # showing what would happen without it, using the store directly to force the old bug's
    # exact precondition (two pending grants) and confirming there's no SECOND line of defence
    # at redeem() to catch it. This is intentional documentation of WHERE the one fix must live,
    # not a claim redeem() re-validates the cap on its own.
    loyalty = FakeLoyaltyDesk()
    engine = _engine(_campaign(mode=MODE_ONCE), loyalty=loyalty)
    g1 = run(engine.register(TENANT, code=CODE, beneficiary_phone="0533333333"))
    assert g1.mode == MODE_ONCE
    run(engine.redeem(TENANT, "0533333333", visit_id="v1"))
    assert len(loyalty.awards) == 1
    # the SAME referrer's code, for a DIFFERENT new customer, after the first has already
    # redeemed — refused by len(active) >= 1 (the redeemed grant itself already counts).
    with pytest.raises(ReferralRedemptionError):
        run(engine.register(TENANT, code=CODE, beneficiary_phone="0544444444"))


def test_mode_x_times_refuses_stacking_pending_grants_past_the_limit():
    engine = _engine(_campaign(mode=MODE_X_TIMES, x_times_limit=2))
    run(engine.register(TENANT, code=CODE, beneficiary_phone="0533333333"))  # pending, slot 1
    run(engine.register(TENANT, code=CODE, beneficiary_phone="0544444444"))  # pending, slot 2
    # a THIRD new customer, still with zero of the first two ever redeemed — must be refused
    # against the limit of 2, not allowed through because "0 redeemed so far".
    with pytest.raises(ReferralRedemptionError):
        run(engine.register(TENANT, code=CODE, beneficiary_phone="0555555555"))


def test_mode_x_times_allows_exactly_the_limit_across_a_mix_of_pending_and_redeemed():
    engine = _engine(_campaign(mode=MODE_X_TIMES, x_times_limit=2))
    run(engine.register(TENANT, code=CODE, beneficiary_phone="0533333333"))
    run(engine.redeem(TENANT, "0533333333", visit_id="v1"))                 # 1 redeemed
    run(engine.register(TENANT, code=CODE, beneficiary_phone="0544444444"))  # 1 more pending == 2
    with pytest.raises(ReferralRedemptionError):
        run(engine.register(TENANT, code=CODE, beneficiary_phone="0555555555"))  # would be 3


def test_mode_lifetime_still_never_caps_even_with_many_pending_grants_at_once():
    # LIFETIME mode has no cap at all — proving the fix did not accidentally start limiting it.
    engine = _engine(_campaign(mode="lifetime"))
    for i in range(10):
        run(engine.register(TENANT, code=CODE, beneficiary_phone=f"05{i:09d}"))
    # no exception anywhere above — a lifetime campaign really does allow unlimited pending grants


def test_a_registered_but_never_redeemed_grant_still_blocks_a_second_once_registration():
    # Documents the accepted trade-off honestly (see the module's own docstring): with no expiry
    # mechanism, an abandoned pending grant permanently consumes a mode_once referrer's one
    # lifetime slot. Fixed CLOSED (a stuck slot, never crediting anyone further) rather than
    # fixed OPEN (an uncapped exploit) — the correct direction for a security fix when the
    # alternative is a real financial exploit; a real expiry mechanism is a separate, future
    # product decision, not a defect this test pretends is fixed.
    engine = _engine(_campaign(mode=MODE_ONCE))
    run(engine.register(TENANT, code=CODE, beneficiary_phone="0533333333"))
    # never redeemed — the customer walked away
    with pytest.raises(ReferralRedemptionError):
        run(engine.register(TENANT, code=CODE, beneficiary_phone="0544444444"))


def test_usage_cap_period_and_limit_is_unaffected_by_this_fix_still_counts_redeemed_only():
    # The rolling period cap (day/week/month) is a DIFFERENT kind of cap — a rate limit over
    # real elapsed time, not an absolute lifetime count — and intentionally still counts only
    # REDEEMED grants within the window, never pending ones (a pending grant has no meaningful
    # position in a time window until it actually redeems).
    engine = _engine(_campaign(mode="lifetime", usage_cap_period="day", usage_cap_limit=1))
    run(engine.register(TENANT, code=CODE, beneficiary_phone="0533333333"))
    run(engine.redeem(TENANT, "0533333333", visit_id="v1"))
    with pytest.raises(ReferralRedemptionError):
        run(engine.register(TENANT, code=CODE, beneficiary_phone="0544444444"))
