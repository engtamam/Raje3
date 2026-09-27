"""Deeper adversarial coverage for core/referral_redemption.py — security-relevant edge cases the
happy-path tests in test_referral_redemption.py don't reach: an unresolvable referrer identity, a
genuine registration race, malformed/hostile campaign data from the referrals peer, an unreachable
loyalty peer at redeem time, and an unreachable referrals peer at register time."""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.adapters.referrals_desk import ReferralsPeerUnavailable
from app.core.models import Customer
from app.core.signup import canonical_phone
from app.core.referral_redemption import (
    MODE_ONCE, NEW_CUSTOMER_DISCOUNT_PERCENT, ReferralRedemptionEngine, ReferralRedemptionError,
)
from app.core.stores import CustomerStore, new_id

CC = "966"
TENANT = "shop_a"
REFERRER_PHONE = "0511111111"
BENEFICIARY_PHONE = "0522222222"
CODE = "AB123"


def run(coro):
    return asyncio.run(coro)


def _campaign(**over) -> dict:
    base = {
        "id": "camp_1", "mode": MODE_ONCE, "min_spend_minor": 0,
        "usage_cap_period": "", "usage_cap_limit": 0, "x_times_limit": 0,
        "reward_type": "fixed_points", "reward_params": {"points": 100},
        "new_customer_reward_type": NEW_CUSTOMER_DISCOUNT_PERCENT,
        "new_customer_reward_params": {"percent": 10},
    }
    base.update(over)
    return base


class FakeReferralsDesk:
    def __init__(self, *, code_to_phone=None, campaign=_campaign(), unavailable=False,
                unavailable_campaign=False):
        self._codes = code_to_phone if code_to_phone is not None else {CODE: REFERRER_PHONE}
        self._campaign = campaign
        self._unavailable = unavailable
        self._unavailable_campaign = unavailable_campaign
        self.configured = True
        self.lookup_calls = 0

    async def lookup_code(self, code):
        self.lookup_calls += 1
        if self._unavailable:
            raise ReferralsPeerUnavailable("boom")
        return self._codes.get(code)

    async def active_campaign(self, tenant):
        if self._unavailable_campaign:
            raise ReferralsPeerUnavailable("boom")
        return self._campaign


class FakeLoyaltyDesk:
    def __init__(self, *, unavailable=False):
        self.awards: list[dict] = []
        self._unavailable = unavailable

    async def award(self, *, tenant, subject_ref, points, idempotency_key, reason, actor):
        if self._unavailable:
            return None                     # exactly what LoyaltyDesk.award() returns on failure
        self.awards.append({"points": points, "reason": reason})
        return {"earned": points}


async def _seed_customer(store, tenant: str, phone: str) -> None:
    """The referrer must already be an existing customer here (deep-review Phase 5c) — every
    test below that expects register() to SUCCEED for REFERRER_PHONE needs it seeded first."""
    await CustomerStore(store).save(
        Customer(id=new_id("cus"), tenant=tenant, phone=canonical_phone(phone, default_cc=CC),
                subject_ref="ref"))


def _engine(*, referrals=None, loyalty=None, store=None,
           seed_referrer: bool = True) -> ReferralRedemptionEngine:
    store = store or MemoryDataStore()
    if seed_referrer:
        run(_seed_customer(store, TENANT, REFERRER_PHONE))
    return ReferralRedemptionEngine(
        store=store, referrals_desk=referrals or FakeReferralsDesk(),
        loyalty_desk=loyalty or FakeLoyaltyDesk(), pii_salt="s" * 32, default_cc=CC)


# ── an unresolvable referrer identity must never become an uncapped, anonymous discount mill ────
def test_a_referrer_phone_that_fails_to_canonicalize_refuses_registration():
    # "not-a-phone" cannot canonicalize to anything real — canonical_phone returns "" for it,
    # and the engine must refuse outright rather than let an empty referrer_phone slip through
    # (which would skip _enforce_usage_cap's own check entirely — an uncapped free-discount path).
    referrals = FakeReferralsDesk(code_to_phone={CODE: "not-a-phone"})
    engine = _engine(referrals=referrals)
    with pytest.raises(ReferralRedemptionError):
        run(engine.register(TENANT, code=CODE, beneficiary_phone=BENEFICIARY_PHONE))


def test_self_referral_with_a_differently_formatted_phone_is_still_caught():
    # The referrer's own phone, stored with a leading zero; the beneficiary presents the SAME
    # person's number with the country code instead — canonical_phone must normalize both to the
    # same value for the self-referral check to catch it.
    referrals = FakeReferralsDesk(code_to_phone={CODE: "0501234567"})
    engine = _engine(referrals=referrals)
    with pytest.raises(ReferralRedemptionError):
        run(engine.register(TENANT, code=CODE, beneficiary_phone="+966501234567"))


# ── register(): a genuine concurrency race must never create two pending grants ─────────────────
#
# MemoryDataStore's own claim() is atomic BECAUSE it never awaits between its read and its write
# (see ports/datastore.py's own docstring) — so under this test harness's single, cooperative
# event loop, two `asyncio.gather`-ed register() calls for a brand-new beneficiary never actually
# interleave at all (no genuine suspension point exists between them): the first runs to
# completion before the second is ever scheduled, and the second then simply finds the first's
# grant via the ordinary idempotency check. That is a REAL, correct outcome — not a race at all —
# and asserting "one wins, one is refused" against it would be asserting behaviour this event loop
# cannot produce, not a real guarantee. What genuinely needs proving is register()'s own REACTION
# to losing the claim, which requires manufacturing the race directly rather than hoping
# `asyncio.gather` happens to interleave two non-suspending coroutines.
def test_a_beneficiary_already_claimed_by_a_concurrent_registration_is_refused_not_duplicated():
    import time as _time

    from app.core.referral_redemption import _REGISTER_LOCK

    store = MemoryDataStore()
    engine = _engine(store=store)
    canon_beneficiary = "+966522222222"

    # Simulate the OTHER racer having just won the claim, mid-flight, before this call starts.
    won = run(store.claim(_REGISTER_LOCK, f"{TENANT}|{canon_beneficiary}", {"actor": "other"},
                          ttl_seconds=5, now=_time.time()))
    assert won is True

    with pytest.raises(ReferralRedemptionError):
        run(engine.register(TENANT, code=CODE, beneficiary_phone=BENEFICIARY_PHONE))

    # No grant was created by the losing caller — the other racer's own write (not simulated here)
    # is the only one that may ever land.
    rows, _ = run(store.find("referral_redemption_grants", {"tenant": TENANT}, limit=100))
    assert rows == []


def test_the_claim_expiring_lets_a_later_call_through_normally():
    import time as _time

    store = MemoryDataStore()
    engine = _engine(store=store)
    canon_beneficiary = "+966522222222"

    from app.core.referral_redemption import _REGISTER_LOCK
    run(store.claim(_REGISTER_LOCK, f"{TENANT}|{canon_beneficiary}", {"actor": "other"},
                    ttl_seconds=1, now=1000.0))

    # register() reads its own current time — advancing the store's notion of "now" far enough
    # is what a real several-second-later retry looks like; here we just prove a fresh claim
    # attempt against an EXPIRED lock succeeds, matching claim()'s own documented contract.
    later_won = run(store.claim(_REGISTER_LOCK, f"{TENANT}|{canon_beneficiary}", {"actor": "us"},
                                ttl_seconds=5, now=1010.0))
    assert later_won is True


def test_a_retry_after_the_lock_expires_is_still_idempotent():
    # Not a real race — just confirms the lock does not permanently wedge a legitimate retry: once
    # the first call has actually written its grant, a second call (lock or no lock) finds it via
    # the ordinary pending-grant check and returns the SAME grant, never a refusal.
    engine = _engine()
    first = run(engine.register(TENANT, code=CODE, beneficiary_phone=BENEFICIARY_PHONE))
    second = run(engine.register(TENANT, code=CODE, beneficiary_phone=BENEFICIARY_PHONE))
    assert first.id == second.id


# ── an unreachable referrals peer must refuse cleanly, never crash or silently pass ─────────────
def test_referrals_peer_unavailable_during_lookup_is_a_clean_refusal():
    engine = _engine(referrals=FakeReferralsDesk(unavailable=True))
    with pytest.raises(ReferralRedemptionError):
        run(engine.register(TENANT, code=CODE, beneficiary_phone=BENEFICIARY_PHONE))


def test_referrals_peer_unavailable_during_active_campaign_read_is_a_clean_refusal():
    engine = _engine(referrals=FakeReferralsDesk(unavailable_campaign=True))
    with pytest.raises(ReferralRedemptionError):
        run(engine.register(TENANT, code=CODE, beneficiary_phone=BENEFICIARY_PHONE))


# ── an unreachable loyalty peer at redeem time must never block the customer's own discount ─────
def test_loyalty_peer_unavailable_at_redeem_still_redeems_the_visit_side():
    loyalty = FakeLoyaltyDesk(unavailable=True)
    engine = _engine(loyalty=loyalty)
    run(engine.register(TENANT, code=CODE, beneficiary_phone=BENEFICIARY_PHONE))
    # The customer's own discount must apply even though the referrer's credit failed — the two
    # are not the same promise, and a lost credit must never cost the NEW customer their reward.
    redeemed = run(engine.redeem(TENANT, BENEFICIARY_PHONE, visit_id="v1"))
    assert redeemed is True
    assert loyalty.awards == []


# ── malformed / hostile campaign data from the referrals peer must never crash the engine ───────
def test_a_negative_invoice_minor_never_produces_negative_credited_points():
    engine = _engine(referrals=FakeReferralsDesk(
        campaign=_campaign(reward_type="invoice_percentage", reward_params={"percent": 10})))
    grant = run(engine.register(TENANT, code=CODE, beneficiary_phone=BENEFICIARY_PHONE,
                                invoice_minor=-5000))
    assert grant.invoice_minor == -5000          # stored honestly, not silently clamped
    loyalty = engine._loyalty
    run(engine.redeem(TENANT, BENEFICIARY_PHONE, visit_id="v1"))
    assert loyalty.awards == []                  # points > 0 check refuses a negative credit


def test_an_unknown_referrer_reward_type_never_crashes_redeem():
    engine = _engine(referrals=FakeReferralsDesk(
        campaign=_campaign(reward_type="a_future_reward_type_this_build_does_not_know",
                          reward_params={"anything": 1})))
    run(engine.register(TENANT, code=CODE, beneficiary_phone=BENEFICIARY_PHONE))
    result = run(engine.redeem(TENANT, BENEFICIARY_PHONE, visit_id="v1"))
    assert result is True
    assert engine._loyalty.awards == []


def test_a_mystery_box_with_no_outcomes_key_at_all_never_crashes_redeem():
    engine = _engine(referrals=FakeReferralsDesk(
        campaign=_campaign(reward_type="mystery_box", reward_params={})))
    run(engine.register(TENANT, code=CODE, beneficiary_phone=BENEFICIARY_PHONE))
    result = run(engine.redeem(TENANT, BENEFICIARY_PHONE, visit_id="v1"))
    assert result is True
    assert engine._loyalty.awards == []


def test_a_campaign_missing_reward_params_entirely_never_crashes_registration_or_redeem():
    engine = _engine(referrals=FakeReferralsDesk(
        campaign=_campaign(reward_type="fixed_points", reward_params=None)))
    run(engine.register(TENANT, code=CODE, beneficiary_phone=BENEFICIARY_PHONE))
    result = run(engine.redeem(TENANT, BENEFICIARY_PHONE, visit_id="v1"))
    assert result is True
    assert engine._loyalty.awards == []


# ── an out-of-range percent from the peer must never produce a reward larger than the invoice ────
def test_an_out_of_range_invoice_percentage_from_a_faked_peer_is_clamped_not_trusted():
    # services/referrals' own rewards.py already validates 0 < percent <= 99 at campaign-creation
    # time — this is defense in depth for a malformed/hostile value the peer forwards anyway (a
    # future schema change, a bug on that side, a compromised peer), never independently
    # exploitable through any reviewed path today.
    engine = _engine(referrals=FakeReferralsDesk(
        campaign=_campaign(reward_type="invoice_percentage", reward_params={"percent": 5000})))
    run(engine.register(TENANT, code=CODE, beneficiary_phone=BENEFICIARY_PHONE, invoice_minor=1000))
    run(engine.redeem(TENANT, BENEFICIARY_PHONE, visit_id="v1"))
    assert engine._loyalty.awards[0]["points"] <= 1000  # never more than the invoice itself


def test_a_negative_percent_from_a_faked_peer_is_clamped_to_zero_not_negative():
    engine = _engine(referrals=FakeReferralsDesk(
        campaign=_campaign(reward_type="points_match", reward_params={"percent": -50})))
    run(engine.register(TENANT, code=CODE, beneficiary_phone=BENEFICIARY_PHONE, invoice_minor=1000))
    run(engine.redeem(TENANT, BENEFICIARY_PHONE, visit_id="v1"))
    assert engine._loyalty.awards == []  # points <= 0 never credited at all
