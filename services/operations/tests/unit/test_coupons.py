"""Shop-to-shop coupons — the engine only (core/coupons.py). billing-service itself is faked
here (`FakePlans`), matching exactly the contract base-services v0.23.0/v0.23.1 shipped: create
one coupon row, attach a code to an EXISTING subscription, and the specific 400 reason codes on a
refused attach. Nothing here talks to a real socket.
"""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.coupons import (ALREADY_HAS_BETTER, BILLING_UNAVAILABLE, COUPONS_KEY, GRANTED,
                              INVALID_PERCENT, INVALID_SCOPE, NOT_SUBSCRIBED, NO_ACCOUNT,
                              OVER_CAP, CouponError, CouponService, PLATFORM)
from app.core.signup import PHONE_INDEX, canonical_phone

CC = "966"
A = "tnt_alpha"    # the granter
B = "tnt_beta"     # the beneficiary
PHONE = "0501234567"


def run(coro):
    return asyncio.run(coro)


class FakePlans:
    driver = "fake"

    def __init__(self) -> None:
        self.subs: dict[str, list[dict]] = {}
        self.limits_by_plan: dict[str, dict] = {}
        self.plan_for_key: dict[str, str] = {}
        self.created: dict[str, dict] = {}
        self.attached: dict[str, str] = {}
        self.attach_status = 200
        self.attach_reason = ""
        self.create_status = 201

    async def subscriptions(self, tenant: str):
        return self.subs.get(tenant)

    async def limits(self, plan_id: str):
        return self.limits_by_plan.get(plan_id)

    async def plan_id_for_key(self, key: str) -> str:
        return self.plan_for_key.get(key, "")

    async def create_coupon(self, *, code, plan_id, percent, expires_at, note=""):
        if self.create_status >= 400:
            return self.create_status, {"error": "BAD_REQUEST"}
        self.created[code] = {"plan_id": plan_id, "percent": percent}
        return self.create_status, {"code": code, "plan_id": plan_id}

    async def attach_coupon(self, *, tenant, sub_id, coupon_code):
        if self.attach_status == 200:
            self.attached[sub_id] = coupon_code
            return 200, {"subscription_id": sub_id, "coupon_code": coupon_code,
                        "status": "attached"}
        if self.attach_status == 404:
            return 404, {"error": "NOT_FOUND", "reason": "SUBSCRIPTION_NOT_FOUND"}
        return self.attach_status, {"error": "BAD_REQUEST", "reason": self.attach_reason}


def _register(store, phone: str, tenant: str) -> None:
    key = canonical_phone(phone, default_cc=CC)
    run(store.put(PHONE_INDEX, key, {"id": key, "tenant": tenant, "verified": True}))


def _hold_one_app(plans: FakePlans, tenant: str, *, key: str, plan_id: str, sub_id: str,
                  status: str = "active") -> None:
    plans.subs.setdefault(tenant, []).append({"id": sub_id, "plan": plan_id, "status": status})
    plans.limits_by_plan[plan_id] = {key: {"kind": "boolean", "limit": 1}}
    plans.plan_for_key[key] = plan_id


@pytest.fixture()
def svc():
    store = MemoryDataStore()
    plans = FakePlans()
    return CouponService(store=store, plans=plans, default_cc=CC), store, plans


# ── the basic refusals, each with its own real reason ──────────────────────────────────────────
def test_a_non_positive_percent_is_refused_before_anything_else(svc):
    s, _store, _plans = svc
    att = run(s.grant(granter_tenant=A, granter_operator_id="op1", phone=PHONE, percent=0,
                      general=True))
    assert att.outcome == INVALID_PERCENT


def test_an_unknown_app_key_is_an_invalid_scope(svc):
    s, _store, _plans = svc
    att = run(s.grant(granter_tenant=A, granter_operator_id="op1", phone=PHONE, percent=10,
                      app_keys=["feature.does_not_exist"]))
    assert att.outcome == INVALID_SCOPE


def test_targeting_the_coupons_app_itself_is_always_refused(svc):
    """The one app a grant must never be able to discount — see module docstring."""
    s, _store, _plans = svc
    att = run(s.grant(granter_tenant=A, granter_operator_id="op1", phone=PHONE, percent=10,
                      app_keys=[COUPONS_KEY]))
    assert att.outcome == INVALID_SCOPE


def test_a_percent_above_the_effective_cap_is_refused(svc):
    s, _store, plans = svc
    _register(_store, PHONE, B)
    _hold_one_app(plans, B, key="feature.bookings", plan_id="plan_bookings", sub_id="sub_1")
    # default base_percent is 10 — 11 must exceed it
    att = run(s.grant(granter_tenant=A, granter_operator_id="op1", phone=PHONE, percent=11,
                      app_keys=["feature.bookings"]))
    assert att.outcome == OVER_CAP


def test_an_unregistered_phone_is_no_account(svc):
    s, _store, _plans = svc
    att = run(s.grant(granter_tenant=A, granter_operator_id="op1", phone=PHONE, percent=5,
                      app_keys=["feature.bookings"]))
    assert att.outcome == NO_ACCOUNT
    # NEVER LEAKS WHICH TENANT — public() carries no beneficiary identity at all, and this
    # outcome in particular must not even hint at "found but refused for another reason".
    assert "beneficiary" not in att.public()


def test_a_registered_tenant_holding_none_of_the_requested_apps_is_not_subscribed(svc):
    s, _store, plans = svc
    _register(_store, PHONE, B)
    plans.subs[B] = []  # billing answered: holds nothing
    att = run(s.grant(granter_tenant=A, granter_operator_id="op1", phone=PHONE, percent=5,
                      app_keys=["feature.bookings"]))
    assert att.outcome == NOT_SUBSCRIBED


def test_billing_being_unreadable_is_a_distinct_outcome_from_not_subscribed(svc):
    s, _store, plans = svc
    _register(_store, PHONE, B)
    plans.subs[B] = None  # None, not []: "could not read", never "holds nothing"
    att = run(s.grant(granter_tenant=A, granter_operator_id="op1", phone=PHONE, percent=5,
                      app_keys=["feature.bookings"]))
    assert att.outcome == BILLING_UNAVAILABLE


# ── the real, successful path ───────────────────────────────────────────────────────────────────
def test_a_specific_app_grant_creates_and_attaches_one_coupon(svc):
    s, store, plans = svc
    _register(store, PHONE, B)
    _hold_one_app(plans, B, key="feature.bookings", plan_id="plan_bookings", sub_id="sub_1")
    att = run(s.grant(granter_tenant=A, granter_operator_id="op1", phone=PHONE, percent=10,
                      app_keys=["feature.bookings"]))
    assert att.outcome == GRANTED
    assert att.per_app == {"feature.bookings": "attached"}
    assert len(att.grant_ids) == 1
    assert plans.attached["sub_1"] in plans.created


def test_a_general_grant_covers_every_eligible_held_app_except_coupons_itself(svc):
    s, store, plans = svc
    _register(store, PHONE, B)
    _hold_one_app(plans, B, key="feature.bookings", plan_id="plan_bookings", sub_id="sub_1")
    _hold_one_app(plans, B, key="feature.loyalty", plan_id="plan_loyalty", sub_id="sub_2")
    _hold_one_app(plans, B, key=COUPONS_KEY, plan_id="plan_coupons", sub_id="sub_3")
    att = run(s.grant(granter_tenant=A, granter_operator_id="op1", phone=PHONE, percent=10,
                      general=True))
    assert att.outcome == GRANTED
    assert set(att.per_app) == {"feature.bookings", "feature.loyalty"}
    assert "sub_3" not in plans.attached


def test_a_general_grant_ignores_a_cancelled_subscription(svc):
    s, store, plans = svc
    _register(store, PHONE, B)
    _hold_one_app(plans, B, key="feature.bookings", plan_id="plan_bookings", sub_id="sub_1",
                 status="canceled")
    att = run(s.grant(granter_tenant=A, granter_operator_id="op1", phone=PHONE, percent=10,
                      general=True))
    assert att.outcome == NOT_SUBSCRIBED


# ── the attach-refusal reason codes, mapped from base-services v0.23.1's own contract ──────────
@pytest.mark.parametrize("reason,expected", [
    ("COUPON_EXPIRED", "coupon_expired"),
    ("COUPON_EXHAUSTED", "coupon_exhausted"),
    ("COUPON_MAX_REDEMPTIONS", "coupon_exhausted"),
    ("COUPON_UNKNOWN", "coupon_unknown"),
    ("COUPON_PLAN_MISMATCH", "plan_mismatch"),
    ("COUPON_DISABLED", "coupon_disabled"),
    ("COUPON_SCHEDULED", "coupon_scheduled"),
    ("SOMETHING_NEW_WE_DO_NOT_KNOW_YET", BILLING_UNAVAILABLE),
])
def test_attach_refusal_reasons_map_to_a_legible_per_app_outcome(svc, reason, expected):
    s, store, plans = svc
    _register(store, PHONE, B)
    _hold_one_app(plans, B, key="feature.bookings", plan_id="plan_bookings", sub_id="sub_1")
    plans.attach_status = 400
    plans.attach_reason = reason
    att = run(s.grant(granter_tenant=A, granter_operator_id="op1", phone=PHONE, percent=10,
                      app_keys=["feature.bookings"]))
    # nothing attached, so the overall outcome falls back to billing_unavailable — the per-app
    # detail is where the real reason lives
    assert att.outcome == BILLING_UNAVAILABLE
    assert att.per_app == {"feature.bookings": expected}


def test_a_vanished_subscription_at_attach_time_is_reported_as_not_subscribed(svc):
    s, store, plans = svc
    _register(store, PHONE, B)
    _hold_one_app(plans, B, key="feature.bookings", plan_id="plan_bookings", sub_id="sub_1")
    plans.attach_status = 404
    att = run(s.grant(granter_tenant=A, granter_operator_id="op1", phone=PHONE, percent=10,
                      app_keys=["feature.bookings"]))
    assert att.per_app == {"feature.bookings": NOT_SUBSCRIBED}


# ── the ceiling is the last word ─────────────────────────────────────────────────────────────
def test_the_ceiling_clamps_a_tenant_override_that_asks_above_it(svc):
    s, _store, _plans = svc
    run(s.update_settings(ceiling_percent=20, base_percent=10))
    with pytest.raises(CouponError):
        run(s.set_tenant_override(A, percent=25))


def test_a_tier_percent_at_the_ceiling_is_honoured_but_never_exceeded(svc):
    s, _store, _plans = svc
    # A TIER AT THE CEILING ITSELF is the strictest legal case — `update_settings` already
    # refuses anything ABOVE it (see the test right below), so this proves the clamp is a no-op
    # rather than a silent truncation when the tier is exactly correct.
    run(s.update_settings(ceiling_percent=25, base_percent=5,
                          tiers=[{"max_grants": 0, "percent": 25}]))
    assert run(s.effective_cap(A)) == 25


def test_an_override_wins_over_the_automatic_tier(svc):
    s, _store, _plans = svc
    run(s.update_settings(ceiling_percent=35, base_percent=10,
                          tiers=[{"max_grants": 0, "percent": 30}]))
    run(s.set_tenant_override(A, percent=15))
    assert run(s.effective_cap(A)) == 15


def test_settings_reject_a_tier_percent_above_the_ceiling(svc):
    s, _store, _plans = svc
    with pytest.raises(CouponError):
        run(s.update_settings(ceiling_percent=20, base_percent=10,
                              tiers=[{"max_grants": 10, "percent": 25}]))


# ── monthly activity tiers — the count that decides NEXT month's cap ───────────────────────────
def test_monthly_grant_count_only_counts_this_tenants_own_successful_grants(svc):
    s, store, plans = svc
    _register(store, PHONE, B)
    _hold_one_app(plans, B, key="feature.bookings", plan_id="plan_bookings", sub_id="sub_1")
    run(s.grant(granter_tenant=A, granter_operator_id="op1", phone=PHONE, percent=5,
               app_keys=["feature.bookings"]))
    # a refused attempt from a DIFFERENT tenant must not count against A
    run(s.grant(granter_tenant="tnt_other", granter_operator_id="op9", phone="0509999999",
               percent=5, app_keys=["feature.bookings"]))
    from app.core.coupons import _month_key, _now
    assert run(s.monthly_grant_count(A, _month_key(_now()))) == 1
    assert run(s.monthly_grant_count("tnt_other", _month_key(_now()))) == 0


# ── history and stats read back what grant() actually wrote ────────────────────────────────────
def test_history_and_stats_reflect_real_grants(svc):
    s, store, plans = svc
    _register(store, PHONE, B)
    _hold_one_app(plans, B, key="feature.bookings", plan_id="plan_bookings", sub_id="sub_1")
    run(s.grant(granter_tenant=A, granter_operator_id="op1", phone=PHONE, percent=5,
               app_keys=["feature.bookings"]))
    rows = run(s.history(A))
    assert len(rows) == 1 and rows[0].outcome == GRANTED

    stats = run(s.stats(A))
    # THIS month's own count — the grant just made counts toward it immediately (display only;
    # `effective_cap`'s own tier lookup deliberately reads LAST month instead, so activity this
    # month can never raise this month's own cap — see that function's docstring).
    assert stats["grants_this_month"] == 1
    assert stats["ceiling_percent"] >= stats["current_cap_percent"]


# ── protection against layering a weaker coupon on top of a stronger one ───────────────────────
def test_a_weaker_or_equal_coupon_is_refused_when_a_better_one_is_already_active(svc):
    s, store, plans = svc
    _register(store, PHONE, B)
    _hold_one_app(plans, B, key="feature.bookings", plan_id="plan_bookings", sub_id="sub_1")
    first = run(s.grant(granter_tenant=A, granter_operator_id="op1", phone=PHONE, percent=10,
                        app_keys=["feature.bookings"]))
    assert first.outcome == GRANTED

    # A DIFFERENT shop tries to grant the SAME beneficiary a coupon that is no stronger — refused
    # outright, before billing is ever asked, so nothing is wasted and nothing overwrites the
    # stronger one already attached.
    weaker = run(s.grant(granter_tenant="tnt_other", granter_operator_id="op9", phone=PHONE,
                        percent=5, app_keys=["feature.bookings"]))
    assert weaker.outcome == ALREADY_HAS_BETTER
    assert weaker.per_app == {"feature.bookings": ALREADY_HAS_BETTER}

    equal = run(s.grant(granter_tenant="tnt_other", granter_operator_id="op9", phone=PHONE,
                       percent=10, app_keys=["feature.bookings"]))
    assert equal.outcome == ALREADY_HAS_BETTER


def test_a_genuinely_stronger_coupon_is_allowed_to_replace_the_active_one(svc):
    s, store, plans = svc
    _register(store, PHONE, B)
    _hold_one_app(plans, B, key="feature.bookings", plan_id="plan_bookings", sub_id="sub_1")
    run(s.grant(granter_tenant=A, granter_operator_id="op1", phone=PHONE, percent=10,
               app_keys=["feature.bookings"]))

    run(s.update_settings(ceiling_percent=35, base_percent=10))
    run(s.set_tenant_override("tnt_other", percent=20))
    stronger = run(s.grant(granter_tenant="tnt_other", granter_operator_id="op9", phone=PHONE,
                          percent=15, app_keys=["feature.bookings"]))
    assert stronger.outcome == GRANTED
    assert stronger.per_app == {"feature.bookings": "attached"}


def test_the_check_is_per_app_and_per_beneficiary_not_global(svc):
    """A stronger coupon already active for a DIFFERENT app, or a DIFFERENT beneficiary, must
    never block a fresh grant that has nothing to do with it."""
    s, store, plans = svc
    _register(store, PHONE, B)
    _hold_one_app(plans, B, key="feature.bookings", plan_id="plan_bookings", sub_id="sub_1")
    _hold_one_app(plans, B, key="feature.loyalty", plan_id="plan_loyalty", sub_id="sub_2")
    run(s.grant(granter_tenant=A, granter_operator_id="op1", phone=PHONE, percent=10,
               app_keys=["feature.bookings"]))
    other_app = run(s.grant(granter_tenant="tnt_other", granter_operator_id="op9", phone=PHONE,
                           percent=5, app_keys=["feature.loyalty"]))
    assert other_app.outcome == GRANTED


def test_a_general_grant_still_wins_every_app_where_it_is_not_beaten(svc):
    """The exact case the owner asked about: one shop already gave a STRONGER coupon on ONE
    specific app; a second shop's WEAKER general grant covers several apps including that one.
    The weaker app-line is refused (ALREADY_HAS_BETTER, no billing call wasted on it) while every
    OTHER app it targets still succeeds — a general grant is N independent per-app decisions, never
    one all-or-nothing unit."""
    s, store, plans = svc
    _register(store, PHONE, B)
    _hold_one_app(plans, B, key="feature.bookings", plan_id="plan_bookings", sub_id="sub_1")
    _hold_one_app(plans, B, key="feature.loyalty", plan_id="plan_loyalty", sub_id="sub_2")

    # Shop A already gave 20% on بooking specifically.
    run(s.update_settings(ceiling_percent=35, base_percent=10))
    run(s.set_tenant_override(A, percent=20))
    strong_one_app = run(s.grant(granter_tenant=A, granter_operator_id="op1", phone=PHONE,
                                percent=20, app_keys=["feature.bookings"]))
    assert strong_one_app.outcome == GRANTED

    # Shop C offers 10% general — weaker than the 20% already on bookings, but loyalty has
    # nothing yet.
    general_weaker = run(s.grant(granter_tenant="tnt_other", granter_operator_id="op9",
                                phone=PHONE, percent=10, general=True))
    assert general_weaker.outcome == GRANTED             # overall: it DID land somewhere
    assert general_weaker.per_app == {
        "feature.bookings": ALREADY_HAS_BETTER,           # refused, real reason — no billing call
        "feature.loyalty": "attached",                    # succeeded, nothing to beat here
    }

    # THE EARLIER SUCCESS IS NEVER RETROACTIVELY FLIPPED — a later, better-or-worse offer changes
    # nothing about a `CouponAttempt` row already written; only the NEW attempt's own outcome
    # reflects today's comparison.
    history = run(s.history(A))
    assert history[0].outcome == GRANTED


# ── the live "check before granting" hint ───────────────────────────────────────────────────────
def test_check_reports_unregistered_when_the_phone_is_unknown(svc):
    s, _store, _plans = svc
    out = run(s.check(granter_tenant=A, phone=PHONE))
    assert out == {"registered": False, "already_granted_this_month": False}


def test_check_reports_registered_but_not_yet_granted(svc):
    s, store, plans = svc
    _register(store, PHONE, B)
    out = run(s.check(granter_tenant=A, phone=PHONE))
    assert out == {"registered": True, "already_granted_this_month": False}


def test_check_reports_already_granted_this_month_by_the_same_granter(svc):
    s, store, plans = svc
    _register(store, PHONE, B)
    _hold_one_app(plans, B, key="feature.bookings", plan_id="plan_bookings", sub_id="sub_1")
    run(s.grant(granter_tenant=A, granter_operator_id="op1", phone=PHONE, percent=5,
               app_keys=["feature.bookings"]))
    out = run(s.check(granter_tenant=A, phone=PHONE))
    assert out == {"registered": True, "already_granted_this_month": True}


def test_check_never_leaks_a_grant_made_by_a_different_granter(svc):
    s, store, plans = svc
    _register(store, PHONE, B)
    _hold_one_app(plans, B, key="feature.bookings", plan_id="plan_bookings", sub_id="sub_1")
    run(s.grant(granter_tenant=A, granter_operator_id="op1", phone=PHONE, percent=5,
               app_keys=["feature.bookings"]))
    out = run(s.check(granter_tenant="tnt_other", phone=PHONE))
    assert out == {"registered": True, "already_granted_this_month": False}
