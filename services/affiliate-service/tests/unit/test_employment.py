"""«رشّح نفسك لوظيفة» (spec §8) — the properties worth a test:

  * "عميل مشترك" is a CONVERSION commission, never a referral count
  * eligible is not entitled: the platform decides
  * an already-approved marketer's second request is a no-op, not an error
  * a rejected request has no cooldown — trying again costs nothing
"""
from __future__ import annotations

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.employment import EmploymentError, EmploymentService
from app.core.models import ACTIVE, AFFILIATES, COMMISSIONS, CONFIRMED, CONVERSION, Affiliate, Commission


async def _seed_affiliate(store, affiliate_id="aff-1") -> None:
    row = Affiliate(id=affiliate_id, person_id="p1", phone="+966501234567", name="مسوّق",
                    role="affiliate_manager", status=ACTIVE)
    await store.put(AFFILIATES, affiliate_id, row.to_dict())


async def _seed_n_conversions(store, affiliate_id: str, n: int) -> None:
    for i in range(n):
        c = Commission(id=f"inv-{affiliate_id}-{i}", tenant=f"t-{affiliate_id}-{i}",
                       affiliate_id=affiliate_id, kind=CONVERSION, amount_halalas=4000,
                       status=CONFIRMED)
        await store.put(COMMISSIONS, c.id, c.to_dict())


def build(store, *, threshold=500) -> EmploymentService:
    return EmploymentService(store=store, commissions=DummyCommissions(store),
                             threshold_customers=threshold)


class DummyCommissions:
    """Just enough of CommissionEngine's surface — of_affiliate — to avoid wiring a whole
    CommissionEngine (billing HTTP, referrals) for a test that only needs the count."""

    def __init__(self, store) -> None:
        self._s = store

    async def of_affiliate(self, affiliate_id: str, *, limit: int = 200):
        rows, _ = await self._s.find(COMMISSIONS, {"affiliate_id": affiliate_id}, limit=limit)
        return [Commission.from_dict(r) for r in rows]


@pytest.mark.anyio
async def test_converted_customers_counts_commissions_never_referrals():
    store = MemoryDataStore()
    await _seed_affiliate(store)
    await _seed_n_conversions(store, "aff-1", 3)
    svc = build(store)
    assert await svc.converted_customers("aff-1") == 3


@pytest.mark.anyio
async def test_eligibility_preview_answers_how_close_without_ever_refusing():
    """request() refuses below threshold — a promoter could never see his own progress without
    triggering a refusal. This must succeed at any count, including zero."""
    store = MemoryDataStore()
    await _seed_affiliate(store)
    await _seed_n_conversions(store, "aff-1", 120)
    svc = build(store, threshold=500)

    out = await svc.eligibility_preview("aff-1")
    assert out["converted_customers"] == 120
    assert out["threshold"] == 500
    assert out["eligible"] is False
    assert out["customers_until_eligible"] == 380


@pytest.mark.anyio
async def test_eligibility_preview_at_threshold():
    store = MemoryDataStore()
    await _seed_affiliate(store)
    await _seed_n_conversions(store, "aff-1", 500)
    svc = build(store, threshold=500)

    out = await svc.eligibility_preview("aff-1")
    assert out["eligible"] is True
    assert out["customers_until_eligible"] == 0


@pytest.mark.anyio
async def test_below_threshold_is_refused():
    store = MemoryDataStore()
    await _seed_affiliate(store)
    await _seed_n_conversions(store, "aff-1", 499)
    svc = build(store, threshold=500)
    with pytest.raises(EmploymentError) as exc:
        await svc.request("aff-1")
    assert exc.value.reason == "below_threshold"


@pytest.mark.anyio
async def test_meeting_the_threshold_creates_a_locked_snapshot():
    store = MemoryDataStore()
    await _seed_affiliate(store)
    await _seed_n_conversions(store, "aff-1", 500)
    svc = build(store, threshold=500)
    out = await svc.request("aff-1")
    assert out["already_approved"] is False
    assert out["converted_customers"] == 500
    assert out["status"] == "requested"


@pytest.mark.anyio
async def test_a_second_request_while_one_is_pending_is_refused():
    store = MemoryDataStore()
    await _seed_affiliate(store)
    await _seed_n_conversions(store, "aff-1", 500)
    svc = build(store, threshold=500)
    await svc.request("aff-1")
    with pytest.raises(EmploymentError) as exc:
        await svc.request("aff-1")
    assert exc.value.reason == "already_pending"


@pytest.mark.anyio
async def test_admin_approves_then_a_further_request_is_a_no_op_not_an_error():
    store = MemoryDataStore()
    await _seed_affiliate(store)
    await _seed_n_conversions(store, "aff-1", 500)
    svc = build(store, threshold=500)
    req = await svc.request("aff-1")
    await svc.decide(req["id"], decision="approved", decided_by="admin-1")

    out = await svc.request("aff-1")
    assert out == {"already_approved": True}


@pytest.mark.anyio
async def test_a_rejected_request_has_no_cooldown_trying_again_costs_nothing():
    store = MemoryDataStore()
    await _seed_affiliate(store)
    await _seed_n_conversions(store, "aff-1", 500)
    svc = build(store, threshold=500)
    req = await svc.request("aff-1")
    await svc.decide(req["id"], decision="rejected", decided_by="admin-1")

    second = await svc.request("aff-1")
    assert second["id"] != req["id"]
    assert second["already_approved"] is False


@pytest.mark.anyio
async def test_deciding_an_already_decided_request_is_refused():
    store = MemoryDataStore()
    await _seed_affiliate(store)
    await _seed_n_conversions(store, "aff-1", 500)
    svc = build(store, threshold=500)
    req = await svc.request("aff-1")
    await svc.decide(req["id"], decision="approved", decided_by="admin-1")
    with pytest.raises(EmploymentError) as exc:
        await svc.decide(req["id"], decision="approved", decided_by="admin-1")
    assert exc.value.reason == "already_decided"


@pytest.mark.anyio
async def test_an_unknown_affiliate_is_refused_not_a_crash():
    store = MemoryDataStore()
    svc = build(store)
    with pytest.raises(EmploymentError) as exc:
        await svc.request("no-such-affiliate")
    assert exc.value.reason == "not_found"
