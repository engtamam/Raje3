"""«برنامج دعم الوفاء» (spec §8) — the properties worth a test:

  * the tier is floor(active_shops / 50) * 500 SAR, computed fresh, never cached
  * eligible is not entitled: a human decides, the system only recommends
  * the manager's call is advisory; the admin's is binding, either direction
  * the cooldown anchors to the REQUEST, never the decision — a slow admin costs nothing
  * a rejected request never sets that anchor at all
"""
from __future__ import annotations

import time

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.models import ACTIVE, AFFILIATES, COMMISSIONS, CONFIRMED, CONVERSION, Affiliate, Commission
from app.core.referrals import ReferralRegistry
from app.core.wafa import WafaError, WafaService

DAY = 24 * 60 * 60


async def _seed_manager(store, affiliate_id="mgr-1") -> None:
    row = Affiliate(id=affiliate_id, person_id="p1", phone="+966501234567", name="مسوّق",
                    role="affiliate_manager", status=ACTIVE)
    await store.put(AFFILIATES, affiliate_id, row.to_dict())


async def _stamp_n_shops(referrals: ReferralRegistry, affiliate_id: str, n: int,
                         start: int = 0) -> None:
    for i in range(start, start + n):
        await referrals.stamp(tenant=f"t-{i}", affiliate_id=affiliate_id)


async def _seed_recent_conversion(store, affiliate_id: str, tenant: str = "t-0",
                                  days_ago: int = 1) -> None:
    """A real CONVERSION commission (commission.py's own shape) inside the activity window —
    the exact event `wafa.request()` now requires at least one of, per its own module note.
    Written directly, not through CommissionEngine, because these tests are about wafa.py's own
    gate reading the row, not about how the row gets created."""
    now = int(time.time())
    row = Commission(id=f"inv-{tenant}", tenant=tenant, affiliate_id=affiliate_id,
                     kind=CONVERSION, amount_halalas=1000, status=CONFIRMED,
                     earned_at="", confirms_at=now, created_at=now - days_ago * DAY)
    await store.put(COMMISSIONS, row.id, row.to_dict())


def build(store, *, tier_shops=50, tier_amount=50000, cooldown_days=30,
         retention_min=0.70, refund_max=0.15, min_recent_conversions=1,
         tickets=None) -> tuple[WafaService, ReferralRegistry]:
    referrals = ReferralRegistry(store=store, commission_amount_halalas=1000)
    wafa = WafaService(store=store, referrals=referrals, tier_shops=tier_shops,
                       tier_amount_halalas=tier_amount, cooldown_days=cooldown_days,
                       retention_min=retention_min, refund_max=refund_max,
                       min_recent_conversions=min_recent_conversions, tickets=tickets)
    return wafa, referrals


@pytest.mark.anyio
async def test_tier_amount_is_a_pure_multiplier():
    store = MemoryDataStore()
    wafa, _ = build(store)
    assert wafa.tier_amount(0) == 0
    assert wafa.tier_amount(49) == 0
    assert wafa.tier_amount(50) == 50000
    assert wafa.tier_amount(100) == 100000
    assert wafa.tier_amount(400) == 400000


@pytest.mark.anyio
async def test_eligibility_preview_answers_how_close_without_ever_refusing():
    """The whole point of this method: request() refuses below threshold, so a promoter could
    never see his own progress without triggering a refusal. This must succeed at any count."""
    store = MemoryDataStore()
    await _seed_manager(store)
    wafa, referrals = build(store)
    await _stamp_n_shops(referrals, "mgr-1", 30)

    out = await wafa.eligibility_preview("mgr-1")
    assert out["active_shops"] == 30
    assert out["tier_shops"] == 50
    assert out["shops_until_next_tier"] == 20
    assert out["eligible"] is False
    assert out["current_tier_amount_halalas"] == 0


@pytest.mark.anyio
async def test_eligibility_preview_at_and_past_a_tier_boundary():
    store = MemoryDataStore()
    await _seed_manager(store)
    wafa, referrals = build(store)
    await _stamp_n_shops(referrals, "mgr-1", 50)
    await _seed_recent_conversion(store, "mgr-1")

    out = await wafa.eligibility_preview("mgr-1")
    assert out["eligible"] is True
    assert out["current_tier_amount_halalas"] == 50000
    # sitting exactly on a boundary — the NEXT one is a full tier away, not zero
    assert out["shops_until_next_tier"] == 50


@pytest.mark.anyio
async def test_eligibility_preview_with_zero_shops():
    store = MemoryDataStore()
    await _seed_manager(store)
    wafa, _ = build(store)
    out = await wafa.eligibility_preview("mgr-1")
    assert out["active_shops"] == 0
    assert out["shops_until_next_tier"] == 50
    assert out["eligible"] is False


@pytest.mark.anyio
async def test_eligibility_preview_now_carries_support_kpis_for_himself():
    """"مدير التسويق يعتبر مسوّي، عنده نفس المؤشرات لنفسه" — `performance_for`
    already computed `support_kpis`; `eligibility_preview` dropped it before this fix, so a
    marketer's own home/earnings screen had no way to show it, even though `GET /me/team` showed
    the SAME numbers about his team members all along."""
    store = MemoryDataStore()
    await _seed_manager(store)
    wafa, _ = build(store)   # no TicketReader configured in this test's build()
    out = await wafa.eligibility_preview("mgr-1")
    assert out["support_kpis"] == {"available": False, "reason": "tickets_not_configured"}


@pytest.mark.anyio
async def test_below_threshold_is_refused_before_any_recommendation_is_computed():
    store = MemoryDataStore()
    await _seed_manager(store)
    wafa, referrals = build(store)
    await _stamp_n_shops(referrals, "mgr-1", 49)
    with pytest.raises(WafaError) as exc:
        await wafa.request("mgr-1")
    assert exc.value.reason == "below_threshold"


@pytest.mark.anyio
async def test_request_refused_with_enough_shops_but_no_recent_conversion():
    store = MemoryDataStore()
    await _seed_manager(store)
    wafa, referrals = build(store)
    await _stamp_n_shops(referrals, "mgr-1", 50)   # shops alone are not enough anymore
    with pytest.raises(WafaError) as exc:
        await wafa.request("mgr-1")
    assert exc.value.reason == "no_recent_conversion"


@pytest.mark.anyio
async def test_activity_window_follows_cooldown_days_not_a_fixed_30():
    """"خلال مدة الطلب نفسها" — the lookback is `cooldown_days` itself, not an independent
    setting; a conversion 45 days ago must count once cooldown_days is raised to 60."""
    store = MemoryDataStore()
    await _seed_manager(store)
    wafa, referrals = build(store, cooldown_days=60)
    await _stamp_n_shops(referrals, "mgr-1", 50)
    await _seed_recent_conversion(store, "mgr-1", days_ago=45)   # outside 30, inside 60
    out = await wafa.request("mgr-1")
    assert out["active_shops"] == 50


@pytest.mark.anyio
async def test_activity_window_shrinks_with_cooldown_days_too():
    store = MemoryDataStore()
    await _seed_manager(store)
    wafa, referrals = build(store, cooldown_days=10)
    await _stamp_n_shops(referrals, "mgr-1", 50)
    await _seed_recent_conversion(store, "mgr-1", days_ago=20)   # outside a 10-day window
    with pytest.raises(WafaError) as exc:
        await wafa.request("mgr-1")
    assert exc.value.reason == "no_recent_conversion"


@pytest.mark.anyio
async def test_min_recent_conversions_can_require_more_than_one():
    """"عدد العملاء الجدد... يكون ايضا متغير" — a separate knob from the window itself: one
    qualifying conversion is not enough once the requirement is raised to 3."""
    store = MemoryDataStore()
    await _seed_manager(store)
    wafa, referrals = build(store, min_recent_conversions=3)
    await _stamp_n_shops(referrals, "mgr-1", 50)
    await _seed_recent_conversion(store, "mgr-1", tenant="t-0")
    await _seed_recent_conversion(store, "mgr-1", tenant="t-1")
    with pytest.raises(WafaError) as exc:
        await wafa.request("mgr-1")   # only 2 of the required 3
    assert exc.value.reason == "no_recent_conversion"

    await _seed_recent_conversion(store, "mgr-1", tenant="t-2")
    out = await wafa.request("mgr-1")   # the 3rd makes it eligible
    assert out["active_shops"] == 50


@pytest.mark.anyio
async def test_request_locks_the_shop_count_and_tier_amount_and_recommends_approve():
    store = MemoryDataStore()
    await _seed_manager(store)
    wafa, referrals = build(store)
    await _stamp_n_shops(referrals, "mgr-1", 50)   # all REFERRED, nothing lapsed/refunded
    await _seed_recent_conversion(store, "mgr-1")
    out = await wafa.request("mgr-1")
    assert out["active_shops"] == 50
    assert out["tier_amount_halalas"] == 50000
    assert out["system_recommendation"] == "approve"
    assert out["system_retention_rate"] == 1.0
    assert out["system_refund_rate"] == 0.0


@pytest.mark.anyio
async def test_a_second_request_while_one_is_pending_is_refused():
    store = MemoryDataStore()
    await _seed_manager(store)
    wafa, referrals = build(store)
    await _stamp_n_shops(referrals, "mgr-1", 50)
    await _seed_recent_conversion(store, "mgr-1")
    await wafa.request("mgr-1")
    with pytest.raises(WafaError) as exc:
        await wafa.request("mgr-1")
    assert exc.value.reason == "already_pending"


@pytest.mark.anyio
async def test_the_system_recommends_reject_on_poor_retention():
    store = MemoryDataStore()
    await _seed_manager(store)
    wafa, referrals = build(store)
    await _stamp_n_shops(referrals, "mgr-1", 90)
    # Lapse 40 of them — 50 stay active (still eligible), retention (50/90) is under the 0.70 floor.
    for i in range(40):
        row = await store.get("affiliate_referrals", f"t-{i}")
        row["status"] = "lapsed"
        await store.put("affiliate_referrals", f"t-{i}", row)
    await _seed_recent_conversion(store, "mgr-1")
    out = await wafa.request("mgr-1")
    assert out["system_recommendation"] == "reject"


@pytest.mark.anyio
async def test_manager_decision_is_advisory_and_recorded_but_never_changes_status():
    store = MemoryDataStore()
    await _seed_manager(store)
    wafa, referrals = build(store)
    await _stamp_n_shops(referrals, "mgr-1", 50)
    await _seed_recent_conversion(store, "mgr-1")
    req = await wafa.request("mgr-1")

    out = await wafa.manager_decide(req["id"], decision="reject", decided_by="mgr-2",
                                    reason="ما يجاوب على عملائه")
    assert out.status == "requested"   # STILL pending — advisory only
    assert out.manager_decision == "reject"
    assert out.manager_reason == "ما يجاوب على عملائه"


@pytest.mark.anyio
async def test_admin_can_grant_despite_a_manager_rejection():
    store = MemoryDataStore()
    await _seed_manager(store)
    wafa, referrals = build(store)
    await _stamp_n_shops(referrals, "mgr-1", 50)
    await _seed_recent_conversion(store, "mgr-1")
    req = await wafa.request("mgr-1")
    await wafa.manager_decide(req["id"], decision="reject", decided_by="mgr-2")

    out = await wafa.admin_decide(req["id"], decision="approve", decided_by="admin-1")
    assert out.status == "granted"
    assert out.manager_decision == "reject"   # untouched — a documented input, not overwritten


@pytest.mark.anyio
async def test_admin_can_refuse_despite_a_manager_approval():
    store = MemoryDataStore()
    await _seed_manager(store)
    wafa, referrals = build(store)
    await _stamp_n_shops(referrals, "mgr-1", 50)
    await _seed_recent_conversion(store, "mgr-1")
    req = await wafa.request("mgr-1")
    await wafa.manager_decide(req["id"], decision="approve", decided_by="mgr-2")

    out = await wafa.admin_decide(req["id"], decision="reject", decided_by="admin-1",
                                  reason="نمط إحالات مريب")
    assert out.status == "rejected"
    assert out.reason == "نمط إحالات مريب"


@pytest.mark.anyio
async def test_deciding_an_already_decided_request_is_refused():
    store = MemoryDataStore()
    await _seed_manager(store)
    wafa, referrals = build(store)
    await _stamp_n_shops(referrals, "mgr-1", 50)
    await _seed_recent_conversion(store, "mgr-1")
    req = await wafa.request("mgr-1")
    await wafa.admin_decide(req["id"], decision="approve", decided_by="admin-1")

    with pytest.raises(WafaError) as exc:
        await wafa.admin_decide(req["id"], decision="approve", decided_by="admin-1")
    assert exc.value.reason == "already_decided"


# ── the cooldown: anchored to the REQUEST, never the decision ──────────────────────────────────

@pytest.mark.anyio
async def test_cooldown_blocks_a_second_request_inside_30_days_of_the_last_grant():
    store = MemoryDataStore()
    await _seed_manager(store)
    wafa, referrals = build(store)
    await _stamp_n_shops(referrals, "mgr-1", 50)
    await _seed_recent_conversion(store, "mgr-1")
    req = await wafa.request("mgr-1")
    await wafa.admin_decide(req["id"], decision="approve", decided_by="admin-1")

    with pytest.raises(WafaError) as exc:
        await wafa.request("mgr-1")
    assert exc.value.reason == "cooldown"


@pytest.mark.anyio
async def test_a_slow_admin_decision_does_not_push_the_next_cycle_later():
    """THE central guarantee: the cooldown anchors to `requested_at`, not `decided_at` — an admin
    who takes a week to decide must not cost the marketer a week of his next cycle."""
    store = MemoryDataStore()
    await _seed_manager(store)
    wafa, referrals = build(store, cooldown_days=30)
    await _stamp_n_shops(referrals, "mgr-1", 50)
    await _seed_recent_conversion(store, "mgr-1")
    req = await wafa.request("mgr-1")
    requested_at = req["requested_at"]

    # Simulate the admin deciding a week LATE by hand-editing decided_at forward — admin_decide()
    # itself always writes `granted_at = requested_at`, so this proves the anchor rather than
    # merely asserting the implementation detail.
    granted = await wafa.admin_decide(req["id"], decision="approve", decided_by="admin-1")
    assert granted.granted_at == requested_at   # NOT `now`, whatever `now` was at decision time


@pytest.mark.anyio
async def test_a_rejected_request_never_sets_the_cooldown_anchor():
    store = MemoryDataStore()
    await _seed_manager(store)
    wafa, referrals = build(store)
    await _stamp_n_shops(referrals, "mgr-1", 50)
    await _seed_recent_conversion(store, "mgr-1")
    req = await wafa.request("mgr-1")
    await wafa.admin_decide(req["id"], decision="reject", decided_by="admin-1")

    # No cooldown — a wrongly-refused request costs nothing once he asks again (still eligible).
    second = await wafa.request("mgr-1")
    assert second["id"] != req["id"]


@pytest.mark.anyio
async def test_an_unknown_affiliate_is_refused_not_a_crash():
    store = MemoryDataStore()
    wafa, _referrals = build(store)
    with pytest.raises(WafaError) as exc:
        await wafa.request("no-such-affiliate")
    assert exc.value.reason == "not_found"


@pytest.mark.anyio
async def test_performance_for_reports_full_retention_and_zero_refund_with_no_history():
    store = MemoryDataStore()
    await _seed_manager(store)
    wafa, _referrals = build(store)
    out = await wafa.performance_for("mgr-1")
    assert out == {"active_shops": 0, "retention_rate": 1.0, "refund_rate": 0.0,
                   "support_kpis": {"available": False, "reason": "tickets_not_configured"},
                   "recent_conversions": 0,
                   "total_referrals": 0, "total_commissions": 0}
    # THE POINT OF THIS TEST'S OWN NAME, made explicit: retention_rate/refund_rate are formula
    # DEFAULTS with no referral or commission behind them — a caller must read total_referrals/
    # total_commissions to tell "no evidence yet" from "a real 100%/0%" ("كيف
    # كذا وهو صفر اساس! في غلط في المعادلة").
    assert out["total_referrals"] == 0 and out["total_commissions"] == 0


@pytest.mark.anyio
async def test_performance_for_counts_every_referral_and_commission_past_a_single_page():
    """Regression: `performance_for` used to read both referrals and commissions with
    `limit=2000` and throw the cursor away — past that count (or past the internal page size)
    the read silently stopped and every figure computed from it (active_shops, retention_rate,
    total_referrals) was confidently wrong. Seeds well past one internal page (500) of both and
    asserts every count reflects ALL of them."""
    store = MemoryDataStore()
    await _seed_manager(store)
    wafa, referrals = build(store)
    shop_count = 650
    await _stamp_n_shops(referrals, "mgr-1", shop_count)

    out = await wafa.performance_for("mgr-1")
    assert out["active_shops"] == shop_count
    assert out["total_referrals"] == shop_count
    assert out["retention_rate"] == 1.0

    # Now push commissions past one page too — one CONFIRMED commission per referred shop.
    from app.core.models import COMMISSIONS, CONFIRMED, CONVERSION, Commission
    for i in range(shop_count):
        c = Commission(id=f"c-{i:05d}", tenant=f"t-{i}", affiliate_id="mgr-1", kind=CONVERSION,
                       amount_halalas=100, status=CONFIRMED)
        await store.put(COMMISSIONS, c.id, c.to_dict())

    out = await wafa.performance_for("mgr-1")
    assert out["total_commissions"] == shop_count
    assert out["refund_rate"] == 0.0


# ── §١٣: real support KPIs, additive and best-effort ────────────────────────────────────────────

class FakeTickets:
    """Answers by tenant — same "scripted by key" idiom as the platform's other fakes."""

    def __init__(self, by_tenant: dict) -> None:
        self._by_tenant = by_tenant

    async def support_kpis(self, *, tenant: str, grantee: str) -> dict:
        return self._by_tenant.get(tenant, {"available": False, "reason": "no_active_grant"})


@pytest.mark.anyio
async def test_support_kpis_average_across_every_shop_that_actually_shared():
    store = MemoryDataStore()
    await _seed_manager(store)
    referrals = ReferralRegistry(store=store, commission_amount_halalas=1000)
    await _stamp_n_shops(referrals, "mgr-1", 2)   # tenants t-0, t-1
    tickets = FakeTickets({
        "t-0": {"available": True, "ticket_count": 4, "avg_first_response_seconds": 100.0,
               "avg_resolution_seconds": 1000.0, "escalation_rate": 0.5},
        "t-1": {"available": False, "reason": "no_active_grant"},   # shop never consented
    })
    wafa = WafaService(store=store, referrals=referrals, tickets=tickets)
    out = await wafa.performance_for("mgr-1")
    support = out["support_kpis"]
    assert support["available"] is True
    assert support["shops_with_shared_tickets"] == 1   # only t-0 counted, t-1 skipped honestly
    assert support["ticket_count"] == 4
    assert support["avg_first_response_seconds"] == 100.0
    assert support["escalation_rate"] == 0.5


@pytest.mark.anyio
async def test_support_kpis_reports_unavailable_when_no_shop_ever_shared():
    store = MemoryDataStore()
    await _seed_manager(store)
    referrals = ReferralRegistry(store=store, commission_amount_halalas=1000)
    await _stamp_n_shops(referrals, "mgr-1", 1)
    tickets = FakeTickets({})   # every tenant falls through to no_active_grant
    wafa = WafaService(store=store, referrals=referrals, tickets=tickets)
    out = await wafa.performance_for("mgr-1")
    assert out["support_kpis"] == {"available": False, "reason": "no_shared_tickets"}
