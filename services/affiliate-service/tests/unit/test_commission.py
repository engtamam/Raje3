"""Turning a REAL payment into a commission — the properties worth a test:

  * a commission is created from billing's own durable invoice history, never invented locally
  * the SAME invoice synced twice produces the SAME one row, never two
  * a conversion outside its referral's window lapses the referral instead of paying it
  * a refund voids a still-pending commission, never a confirmed one
  * the hold actually holds, and lifts on its own clock, not the caller's
"""
from __future__ import annotations

import time

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.commission import CommissionEngine
from app.core.models import (
    ACTIVE, AFFILIATES, CONFIRMED, CONVERSION, LAPSED, PENDING, REFERRED, VOIDED, Affiliate,
)
from app.core.referrals import ReferralRegistry

TENANT = "t-1"
DAY = 24 * 60 * 60


class FakeBillingHttp:
    """Answers GET /internal/billing/invoices with a fixed list, regardless of query string —
    this test drives ONE tenant per engine instance, so the querystring is not worth parsing."""

    def __init__(self, invoices=None, status=200):
        self.invoices = invoices or []
        self.status = status
        self.calls = []

    def call(self, url, *, method, body=None, internal=False):
        self.calls.append((method, url))
        if "/internal/billing/invoices" in url:
            return self.status, {"invoices": self.invoices}
        return 500, {}


def _iso(epoch: int) -> str:
    import datetime as _dt
    return _dt.datetime.fromtimestamp(epoch, _dt.timezone.utc).isoformat()


async def _seed(store, *, affiliate_id="aff-1", commission_amount=4000, window_days=90) -> ReferralRegistry:
    row = Affiliate(id=affiliate_id, person_id="p1", phone="+966501234567", name="مسوّق",
                    role="affiliate_manager", status=ACTIVE)
    await store.put(AFFILIATES, affiliate_id, row.to_dict())
    referrals = ReferralRegistry(store=store, commission_amount_halalas=commission_amount,
                                 conversion_window_days=window_days)
    await referrals.stamp(tenant=TENANT, affiliate_id=affiliate_id)
    return referrals


def build(invoices, *, referrals, hold_days=7,
         billing_url="http://billing:8000", status=200) -> CommissionEngine:
    return CommissionEngine(
        store=referrals._s, http=FakeBillingHttp(invoices, status=status),
        billing_url=billing_url, referrals=referrals, hold_days=hold_days)


@pytest.mark.anyio
async def test_no_referral_means_nothing_to_sync():
    store = MemoryDataStore()
    referrals = ReferralRegistry(store=store)
    engine = build([], referrals=referrals)
    out = await engine.sync("no-such-tenant")
    assert out == {"synced": False, "reason": "no_referral"}


@pytest.mark.anyio
async def test_billing_not_configured_is_reported_not_raised():
    store = MemoryDataStore()
    referrals = await _seed(store)
    engine = build([], referrals=referrals, billing_url="")
    out = await engine.sync(TENANT)
    assert out == {"synced": False, "reason": "billing_not_configured"}


@pytest.mark.anyio
async def test_a_conversion_inside_the_window_creates_a_pending_commission():
    store = MemoryDataStore()
    referrals = await _seed(store, commission_amount=4000)
    now = int(time.time())
    engine = build([{"id": "inv-1", "subscription_id": "sub-a", "paid_sequence": 1,
                     "subscription_paid_sequence": 1, "amount_minor": 9900, "refunded_minor": 0,
                     "paid_at": _iso(now)}], referrals=referrals, hold_days=7)
    out = await engine.sync(TENANT)
    assert out["created"] == ["inv-1"]

    rows = await engine.of_affiliate("aff-1")
    assert len(rows) == 1
    assert rows[0].kind == CONVERSION
    assert rows[0].amount_halalas == 4000
    assert rows[0].status == PENDING
    assert rows[0].confirms_at - now in range(7 * DAY - 2, 7 * DAY + 2)


@pytest.mark.anyio
async def test_syncing_the_same_invoice_twice_never_creates_a_second_row():
    store = MemoryDataStore()
    referrals = await _seed(store)
    invoices = [{"id": "inv-1", "subscription_id": "sub-a", "paid_sequence": 1,
                "subscription_paid_sequence": 1, "amount_minor": 9900, "refunded_minor": 0,
                "paid_at": _iso(int(time.time()))}]
    engine = build(invoices, referrals=referrals)
    await engine.sync(TENANT)
    second = await engine.sync(TENANT)
    assert second["created"] == []          # nothing NEW the second time
    assert len(await engine.of_affiliate("aff-1")) == 1


@pytest.mark.anyio
async def test_a_conversion_after_the_window_lapses_the_referral_and_pays_nothing():
    store = MemoryDataStore()
    referrals = await _seed(store, window_days=90)
    late = int(time.time()) + 400 * DAY
    engine = build([{"id": "inv-1", "subscription_id": "sub-a", "paid_sequence": 1,
                     "subscription_paid_sequence": 1, "amount_minor": 9900, "refunded_minor": 0,
                     "paid_at": _iso(late)}], referrals=referrals)
    out = await engine.sync(TENANT)
    assert out["created"] == []
    assert len(await engine.of_affiliate("aff-1")) == 0

    referral = await referrals.of_tenant(TENANT)
    assert referral.status == LAPSED


@pytest.mark.anyio
async def test_a_fully_refunded_invoice_never_earns_a_commission_at_all():
    store = MemoryDataStore()
    referrals = await _seed(store)
    engine = build([{"id": "inv-1", "subscription_id": "sub-a", "paid_sequence": 1,
                     "subscription_paid_sequence": 1, "amount_minor": 9900, "refunded_minor": 9900,
                     "paid_at": _iso(int(time.time()))}], referrals=referrals)
    out = await engine.sync(TENANT)
    assert out["created"] == []
    assert len(await engine.of_affiliate("aff-1")) == 0


@pytest.mark.anyio
async def test_a_refund_that_lands_after_creation_voids_a_still_pending_commission():
    store = MemoryDataStore()
    referrals = await _seed(store)
    paid_at = _iso(int(time.time()))
    # First sync: paid, no refund yet.
    engine = build([{"id": "inv-1", "subscription_id": "sub-a", "paid_sequence": 1,
                     "subscription_paid_sequence": 1, "amount_minor": 9900, "refunded_minor": 0,
                     "paid_at": paid_at}], referrals=referrals)
    await engine.sync(TENANT)

    # Second sync: the SAME invoice now shows fully refunded.
    engine2 = build([{"id": "inv-1", "subscription_id": "sub-a", "paid_sequence": 1,
                      "subscription_paid_sequence": 1, "amount_minor": 9900, "refunded_minor": 9900,
                      "paid_at": paid_at}], referrals=referrals)
    out = await engine2.sync(TENANT)
    assert out["voided"] == ["inv-1"]

    rows = await engine2.of_affiliate("aff-1")
    assert rows[0].status == VOIDED


@pytest.mark.anyio
async def test_a_refund_never_reverses_an_already_confirmed_commission():
    store = MemoryDataStore()
    referrals = await _seed(store)
    paid_at_epoch = int(time.time()) - 30 * DAY   # long past any hold
    engine = build([{"id": "inv-1", "subscription_id": "sub-a", "paid_sequence": 1,
                     "subscription_paid_sequence": 1, "amount_minor": 9900, "refunded_minor": 0,
                     "paid_at": _iso(paid_at_epoch)}], referrals=referrals, hold_days=7)
    await engine.sync(TENANT)
    confirmed = await engine.confirm_if_due("inv-1")
    assert confirmed.status == CONFIRMED

    engine2 = build([{"id": "inv-1", "subscription_id": "sub-a", "paid_sequence": 1,
                      "subscription_paid_sequence": 1, "amount_minor": 9900, "refunded_minor": 9900,
                      "paid_at": _iso(paid_at_epoch)}], referrals=referrals)
    await engine2.sync(TENANT)
    rows = await engine2.of_affiliate("aff-1")
    assert rows[0].status == CONFIRMED     # untouched — a dispute for an admin, not auto-reversed


@pytest.mark.anyio
async def test_confirm_if_due_waits_out_the_hold():
    store = MemoryDataStore()
    referrals = await _seed(store)
    now = int(time.time())
    engine = build([{"id": "inv-1", "subscription_id": "sub-a", "paid_sequence": 1,
                     "subscription_paid_sequence": 1, "amount_minor": 9900, "refunded_minor": 0,
                     "paid_at": _iso(now)}], referrals=referrals, hold_days=7)
    await engine.sync(TENANT)

    too_early = await engine.confirm_if_due("inv-1", now=now + 2 * DAY)
    assert too_early.status == PENDING

    due = await engine.confirm_if_due("inv-1", now=now + 8 * DAY)
    assert due.status == CONFIRMED


@pytest.mark.anyio
async def test_confirming_twice_is_idempotent():
    store = MemoryDataStore()
    referrals = await _seed(store)
    now = int(time.time()) - 30 * DAY
    engine = build([{"id": "inv-1", "subscription_id": "sub-a", "paid_sequence": 1,
                     "subscription_paid_sequence": 1, "amount_minor": 9900, "refunded_minor": 0,
                     "paid_at": _iso(now)}], referrals=referrals, hold_days=7)
    await engine.sync(TENANT)
    first = await engine.confirm_if_due("inv-1")
    second = await engine.confirm_if_due("inv-1")
    assert first.status == second.status == CONFIRMED


@pytest.mark.anyio
async def test_renewals_earn_nothing_retired_2026_08_20():
    store = MemoryDataStore()
    referrals = await _seed(store)
    now = int(time.time())
    invoices = [
        {"id": "inv-1", "subscription_id": "sub-a", "paid_sequence": 1,
         "subscription_paid_sequence": 1, "amount_minor": 9900, "refunded_minor": 0,
         "paid_at": _iso(now)},
        {"id": "inv-2", "subscription_id": "sub-a", "paid_sequence": 2,
         "subscription_paid_sequence": 2, "amount_minor": 9900, "refunded_minor": 0,
         "paid_at": _iso(now + 30 * DAY)},
        {"id": "inv-3", "subscription_id": "sub-a", "paid_sequence": 3,
         "subscription_paid_sequence": 3, "amount_minor": 9900, "refunded_minor": 0,
         "paid_at": _iso(now + 60 * DAY)},
    ]
    engine = build(invoices, referrals=referrals)
    out = await engine.sync(TENANT)
    assert out["created"] == ["inv-1"]   # only the conversion — no renewal ever fires anymore


@pytest.mark.anyio
async def test_a_revoked_referral_earns_nothing_even_with_real_payments():
    store = MemoryDataStore()
    referrals = await _seed(store)
    # Simulate an admin revoking the referral directly on the row (no public API for it yet —
    # REVOKED is reachable today only by hand-editing the store, same as the platform's own
    # not-yet-built admin tooling for it).
    row = await store.get("affiliate_referrals", TENANT)
    row["status"] = "revoked"
    await store.put("affiliate_referrals", TENANT, row)

    engine = build([{"id": "inv-1", "subscription_id": "sub-a", "paid_sequence": 1,
                     "subscription_paid_sequence": 1, "amount_minor": 9900, "refunded_minor": 0,
                     "paid_at": _iso(int(time.time()))}], referrals=referrals)
    out = await engine.sync(TENANT)
    assert out == {"synced": False, "reason": "referral_revoked"}


# ── spec §10: a manager's real revenue transparency ────────────────────────────────────────────

@pytest.mark.anyio
async def test_totals_for_splits_confirmed_from_pending_and_never_touches_the_hold():
    store = MemoryDataStore()
    referrals = await _seed(store, commission_amount=4000)
    now = int(time.time())
    engine = build([{"id": "inv-1", "subscription_id": "sub-a", "paid_sequence": 1,
                     "subscription_paid_sequence": 1, "amount_minor": 9900, "refunded_minor": 0,
                     "paid_at": _iso(now)}], referrals=referrals, hold_days=7)
    await engine.sync(TENANT)

    totals = await engine.totals_for("aff-1")
    assert totals == {"confirmed_halalas": 0, "pending_halalas": 4000, "commission_count": 1}
    # totals_for must not itself confirm a due commission — of_affiliate() (the promoter's own
    # dashboard read) is the one place a hold advances.
    rows = await engine.of_affiliate("aff-1")
    assert rows[0].status == PENDING


@pytest.mark.anyio
async def test_revenue_for_reads_billings_own_net_paid_history_per_referred_shop():
    store = MemoryDataStore()
    referrals = await _seed(store)   # stamps ONE referral: TENANT -> aff-1
    engine = build([{"id": "inv-1", "subscription_id": "sub-a", "paid_sequence": 1,
                     "subscription_paid_sequence": 1, "amount_minor": 9900, "refunded_minor": 1900,
                     "paid_at": _iso(int(time.time()))}], referrals=referrals)
    out = await engine.revenue_for("aff-1")
    assert out == {"shops": [{"tenant": TENANT, "shop_name": "", "net_revenue_minor": 8000}],
                   "total_net_revenue_minor": 8000, "revenue_partial": False}


@pytest.mark.anyio
async def test_revenue_for_reports_partial_rather_than_hiding_the_whole_team_on_one_billing_hiccup():
    store = MemoryDataStore()
    referrals = await _seed(store)
    engine = build([], referrals=referrals, status=503)   # billing unreachable
    out = await engine.revenue_for("aff-1")
    assert out["shops"] == [{"tenant": TENANT, "shop_name": "", "net_revenue_minor": None}]
    assert out["total_net_revenue_minor"] == 0
    assert out["revenue_partial"] is True


@pytest.mark.anyio
async def test_platform_revenue_sums_every_referral_ever_regardless_of_status_or_tree():
    store = MemoryDataStore()
    referrals = await _seed(store, affiliate_id="aff-1")   # stamps TENANT ("t-1") -> aff-1
    # A SECOND, unrelated affiliate + referral, no relation to aff-1's tree.
    other = Affiliate(id="aff-other", person_id="p2", phone="+966509999999", name="آخر",
                      role="affiliate_manager", status=ACTIVE)
    await store.put(AFFILIATES, "aff-other", other.to_dict())
    await referrals.stamp(tenant="t-2", affiliate_id="aff-other")
    # Revoke the second one — platform_revenue must still count its real revenue.
    row = await store.get("affiliate_referrals", "t-2")
    row["status"] = "revoked"
    await store.put("affiliate_referrals", "t-2", row)

    class TwoTenantHttp:
        def call(self, url, *, method, body=None, internal=False):
            if "tenant=t-1" in url:
                return 200, {"invoices": [{"amount_minor": 9900, "refunded_minor": 0}]}
            if "tenant=t-2" in url:
                return 200, {"invoices": [{"amount_minor": 5000, "refunded_minor": 0}]}
            return 500, {}

    engine = CommissionEngine(store=store, http=TwoTenantHttp(), billing_url="http://billing:8000",
                              referrals=referrals)
    out = await engine.platform_revenue()
    assert out["total_net_revenue_minor"] == 14900
    assert {s["tenant"] for s in out["shops"]} == {"t-1", "t-2"}


@pytest.mark.anyio
async def test_team_summary_sums_across_members_and_never_counts_the_manager_himself():
    store = MemoryDataStore()
    referrals = await _seed(store, affiliate_id="aff-promoter-1", commission_amount=4000)
    now = int(time.time())
    engine = build([{"id": "inv-1", "subscription_id": "sub-a", "paid_sequence": 1,
                     "subscription_paid_sequence": 1, "amount_minor": 9900, "refunded_minor": 0,
                     "paid_at": _iso(now)}], referrals=referrals, hold_days=0)
    await engine.sync(TENANT)
    await engine.confirm_if_due("inv-1")

    summary = await engine.team_summary(["aff-promoter-1", "aff-promoter-2"])
    assert summary["team_confirmed_halalas"] == 4000
    assert summary["team_pending_halalas"] == 0
    assert {m["affiliate_id"] for m in summary["members"]} == {"aff-promoter-1", "aff-promoter-2"}
    empty = next(m for m in summary["members"] if m["affiliate_id"] == "aff-promoter-2")
    assert empty == {"affiliate_id": "aff-promoter-2", "confirmed_halalas": 0,
                     "pending_halalas": 0, "commission_count": 0, "shops": [],
                     "total_net_revenue_minor": 0, "revenue_partial": False}
