"""core/referral_reports.py — Phase 5a. Seeds grants/affiliates directly into the store (rather
than driving the full register()/redeem() engine) so each test controls exact timestamps and
shapes without depending on two other modules' own side effects."""
from __future__ import annotations

import asyncio

from app.adapters.datastore.memory import MemoryDataStore
from app.core.affiliates import AFFILIATES, Affiliate
from app.core.referral_redemption import GRANTS, ReferralGrant
from app.core.referral_reports import ReferralReportService

TENANT = "shop_a"
OTHER_TENANT = "shop_b"


def run(coro):
    return asyncio.run(coro)


def _grant(**over) -> dict:
    base = dict(
        id="g1", tenant=TENANT, code="AB123", referrer_phone="+966511111111",
        beneficiary_phone="+966522222222", campaign_id="camp_1", mode="once", created=1000,
        new_customer_reward_type="discount_percent", new_customer_reward_params={"percent": 10},
        referrer_reward_type="fixed_points", referrer_reward_params={"points": 50},
        invoice_minor=0, redeemed_at=0, redeemed_visit_id="", referrer_reward_credited=False,
        referrer_points_credited=0, source="referral", affiliate_id="",
    )
    base.update(over)
    return base


async def _seed_grant(store, **over) -> None:
    g = _grant(**over)
    await store.put(GRANTS, f"{g['tenant']}|{g['id']}", g)


async def _seed_affiliate(store, **over) -> Affiliate:
    base = dict(id="aff1", tenant=TENANT, phone="+966511111111", code="BLOGR",
               discount_percent=15, reward_type="fixed_points", reward_params={"points": 40},
               created_at=1000, active=True, unsettled_points=0, total_earned_points=0)
    base.update(over)
    a = Affiliate(**base)
    await store.put(AFFILIATES, f"{a.tenant}|{a.id}", a.to_dict())
    return a


def _svc(store=None) -> ReferralReportService:
    return ReferralReportService(store or MemoryDataStore())


# ── summary(): the headline numbers ─────────────────────────────────────────────────────────────
def test_summary_with_no_grants_is_all_zero_never_a_crash():
    out = run(_svc().summary(TENANT))
    assert out["registered_count"] == 0
    assert out["redeemed_count"] == 0
    assert out["conversion_rate"] == 0.0
    assert out["cost_ratio"] == 0.0
    assert out["revenue_minor"] == 0


def test_summary_counts_registered_and_redeemed_separately():
    store = MemoryDataStore()
    run(_seed_grant(store, id="g1", created=1000, redeemed_at=0))       # registered, not redeemed
    run(_seed_grant(store, id="g2", created=1000, redeemed_at=2000,
                    invoice_minor=10000, referrer_reward_credited=True,
                    referrer_points_credited=50))
    out = run(_svc(store).summary(TENANT))
    assert out["registered_count"] == 2
    assert out["redeemed_count"] == 1
    assert out["conversion_rate"] == 0.5


def test_summary_revenue_is_only_the_redeemed_invoice_amounts():
    store = MemoryDataStore()
    run(_seed_grant(store, id="g1", redeemed_at=2000, invoice_minor=5000))
    run(_seed_grant(store, id="g2", redeemed_at=0, invoice_minor=999999))  # pending, not counted
    out = run(_svc(store).summary(TENANT))
    assert out["revenue_minor"] == 5000


def test_summary_reward_cost_includes_both_referrer_credit_and_new_customer_discount():
    store = MemoryDataStore()
    run(_seed_grant(
        store, redeemed_at=2000, invoice_minor=10000,
        new_customer_reward_type="discount_percent", new_customer_reward_params={"percent": 10},
        referrer_reward_credited=True, referrer_points_credited=50))
    out = run(_svc(store).summary(TENANT))
    # 10% of 10000 = 1000 (new-customer discount) + 50 points * 1 halala = 50 (referrer credit)
    assert out["reward_cost_minor"] == 1050
    assert out["cost_ratio"] == 0.105


def test_summary_an_uncredited_referrer_reward_costs_nothing():
    store = MemoryDataStore()
    run(_seed_grant(store, redeemed_at=2000, invoice_minor=10000,
                    new_customer_reward_type="", new_customer_reward_params={},
                    referrer_reward_credited=False, referrer_points_credited=50))
    out = run(_svc(store).summary(TENANT))
    assert out["reward_cost_minor"] == 0    # no new-customer cost isolated here, and the
    # referrer's own credit never landed either — the whole redemption cost the shop nothing


def test_summary_welcome_points_reward_type_converts_at_the_reference_rate():
    store = MemoryDataStore()
    run(_seed_grant(store, redeemed_at=2000, invoice_minor=10000,
                    new_customer_reward_type="welcome_points",
                    new_customer_reward_params={"points": 30}))
    out = run(_svc(store).summary(TENANT))
    assert out["reward_cost_minor"] == 30


def test_summary_new_customers_acquired_counts_unique_beneficiaries_only():
    store = MemoryDataStore()
    run(_seed_grant(store, id="g1", redeemed_at=2000, beneficiary_phone="+9665A"))
    run(_seed_grant(store, id="g2", redeemed_at=2000, beneficiary_phone="+9665A"))  # same person
    run(_seed_grant(store, id="g3", redeemed_at=2000, beneficiary_phone="+9665B"))
    out = run(_svc(store).summary(TENANT))
    assert out["new_customers_acquired"] == 2


def test_summary_period_filters_registered_by_created_and_redeemed_by_redeemed_at_separately():
    # a grant CREATED before the window but REDEEMED inside it must count as redeemed-in-period,
    # never as registered-in-period — the two timestamps are independent filters (module docstring).
    store = MemoryDataStore()
    run(_seed_grant(store, created=500, redeemed_at=1500, invoice_minor=7000))
    out = run(_svc(store).summary(TENANT, since=1000, until=2000))
    assert out["registered_count"] == 0
    assert out["redeemed_count"] == 1
    assert out["revenue_minor"] == 7000


def test_summary_default_until_includes_a_grant_created_in_the_same_second_as_the_query():
    # A grant created THIS second and read back this same second must not fall through a
    # strict "< until" upper bound just because both timestamps landed on the same integer
    # second — this is exactly the bug a real end-to-end test caught (a hand-picked-timestamp
    # unit test alone never would have, since it never calls the default `until=None`).
    import time

    store = MemoryDataStore()
    now = int(time.time())
    run(_seed_grant(store, created=now, redeemed_at=0))
    out = run(_svc(store).summary(TENANT))
    assert out["registered_count"] == 1


def test_summary_never_leaks_another_tenants_grants():
    store = MemoryDataStore()
    run(_seed_grant(store, tenant=OTHER_TENANT, redeemed_at=2000, invoice_minor=99999))
    out = run(_svc(store).summary(TENANT))
    assert out["revenue_minor"] == 0
    assert out["redeemed_count"] == 0


# ── leaderboard(): ranked by revenue, never by count alone ───────────────────────────────────────
def test_leaderboard_ranks_by_revenue_not_by_redemption_count():
    store = MemoryDataStore()
    # referrer A: 5 tiny redemptions; referrer B: 1 big one — B must rank first.
    for i in range(5):
        run(_seed_grant(store, id=f"a{i}", referrer_phone="+966A", redeemed_at=2000,
                        invoice_minor=100, beneficiary_phone=f"+9665{i}"))
    run(_seed_grant(store, id="b1", referrer_phone="+966B", redeemed_at=2000, invoice_minor=100000,
                    beneficiary_phone="+9665Z"))
    rows = run(_svc(store).leaderboard(TENANT))
    assert rows[0]["referrer_phone"] == "+966B"
    assert rows[0]["revenue_minor"] == 100000
    assert rows[1]["referrer_phone"] == "+966A"
    assert rows[1]["redemptions"] == 5


def test_leaderboard_only_counts_redeemed_grants_never_pending_ones():
    store = MemoryDataStore()
    run(_seed_grant(store, redeemed_at=0))    # still pending
    rows = run(_svc(store).leaderboard(TENANT))
    assert rows == []


def test_leaderboard_separates_the_same_phones_referral_and_affiliate_history():
    # A phone that was an ordinary referrer at one point and an affiliate later must show as TWO
    # distinct rows, never merged — exactly Phase 4's own "history stays tagged separately" rule.
    store = MemoryDataStore()
    run(_seed_grant(store, id="g1", referrer_phone="+966X", source="referral", redeemed_at=1000,
                    invoice_minor=500))
    run(_seed_grant(store, id="g2", referrer_phone="+966X", source="affiliate", redeemed_at=2000,
                    invoice_minor=700, affiliate_id="aff1"))
    rows = run(_svc(store).leaderboard(TENANT))
    assert len(rows) == 2
    sources = {r["source"] for r in rows}
    assert sources == {"referral", "affiliate"}


def test_leaderboard_respects_the_limit_and_a_zero_or_negative_limit_returns_nothing():
    store = MemoryDataStore()
    for i in range(5):
        run(_seed_grant(store, id=f"g{i}", referrer_phone=f"+9665{i}", redeemed_at=2000,
                        beneficiary_phone=f"+9666{i}"))
    assert len(run(_svc(store).leaderboard(TENANT, limit=2))) == 2
    assert run(_svc(store).leaderboard(TENANT, limit=0)) == []
    assert run(_svc(store).leaderboard(TENANT, limit=-5)) == []


# ── campaign_breakdown(): ordinary campaigns only, never an affiliate's own code ─────────────────
def test_campaign_breakdown_excludes_affiliate_sourced_grants():
    store = MemoryDataStore()
    run(_seed_grant(store, id="g1", campaign_id="camp_1", created=1000, redeemed_at=2000,
                    invoice_minor=1000))
    run(_seed_grant(store, id="g2", campaign_id="", source="affiliate", created=1000,
                    redeemed_at=2000, invoice_minor=99999))
    rows = run(_svc(store).campaign_breakdown(TENANT))
    assert len(rows) == 1
    assert rows[0]["campaign_id"] == "camp_1"
    assert rows[0]["revenue_minor"] == 1000


def test_campaign_breakdown_conversion_rate_per_campaign():
    store = MemoryDataStore()
    run(_seed_grant(store, id="g1", campaign_id="camp_1", created=1000, redeemed_at=2000))
    run(_seed_grant(store, id="g2", campaign_id="camp_1", created=1000, redeemed_at=0,
                    beneficiary_phone="+9665X"))
    rows = run(_svc(store).campaign_breakdown(TENANT))
    assert rows[0]["registered"] == 2
    assert rows[0]["redeemed"] == 1
    assert rows[0]["conversion_rate"] == 0.5


# ── affiliate_breakdown(): every affiliate ever added, active or not ─────────────────────────────
def test_affiliate_breakdown_includes_a_paused_affiliate_with_its_real_balance():
    store = MemoryDataStore()
    run(_seed_affiliate(store, active=False, unsettled_points=120))
    rows = run(_svc(store).affiliate_breakdown(TENANT))
    assert len(rows) == 1
    assert rows[0]["active"] is False
    assert rows[0]["unsettled_points"] == 120


def test_affiliate_breakdown_aggregates_only_that_affiliates_own_redeemed_grants():
    store = MemoryDataStore()
    a = run(_seed_affiliate(store, id="aff1"))
    run(_seed_grant(store, id="g1", source="affiliate", affiliate_id=a.id, redeemed_at=2000,
                    invoice_minor=3000))
    run(_seed_grant(store, id="g2", source="referral", campaign_id="camp_1", redeemed_at=2000,
                    invoice_minor=99999))   # an ordinary grant — must never count toward affiliate
    rows = run(_svc(store).affiliate_breakdown(TENANT))
    assert rows[0]["redemptions"] == 1
    assert rows[0]["revenue_minor"] == 3000


def test_affiliate_breakdown_with_no_redemptions_yet_is_zeroed_not_missing():
    store = MemoryDataStore()
    run(_seed_affiliate(store))
    rows = run(_svc(store).affiliate_breakdown(TENANT))
    assert rows[0]["redemptions"] == 0
    assert rows[0]["revenue_minor"] == 0
    assert rows[0]["last_redeemed_at"] == 0


def test_affiliate_breakdown_never_leaks_another_tenant():
    store = MemoryDataStore()
    run(_seed_affiliate(store, tenant=OTHER_TENANT))
    assert run(_svc(store).affiliate_breakdown(TENANT)) == []
