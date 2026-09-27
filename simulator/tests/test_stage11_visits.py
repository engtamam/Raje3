"""New app wired into the simulator: services/operations' own field/visit door
(`POST /api/v1/field/visits`) — "this endpoint is the product, as far as the shop floor is
concerned" in that route's own words. Real HTTP against a real, spawned services/operations.
"""
from __future__ import annotations

import asyncio

from simulator.apps.operations.actions import RecordUniqueVisitAction, RecordVisitAction
from simulator.apps.operations.service import spawn as spawn_operations
from simulator.common.engine import run_one
from simulator.common.execution import run_concurrent
from simulator.common.load import run_load
from simulator.common.report import summarize

TENANT = "sim-visits"


def run(coro):
    return asyncio.run(coro)


def test_recording_a_visit_for_real_creates_a_customer_and_a_visit():
    async def _go():
        async with spawn_operations() as svc:
            return await run_one(RecordVisitAction(
                base_url=svc.base_url, tenant=TENANT, phone="0511111111"))

    result = run(_go())
    assert result.ok, result
    assert result.data["visit"]["service_ids"] == ["svc-simulated"]
    # normalised to E.164 by `Operations._normalise_phone` — the same value in, a canonical form
    # back, never the raw digits echoed unchanged.
    assert result.data["customer"]["phone"] == "966511111111"


def test_recording_with_no_service_ids_is_refused_not_a_crash():
    """`service_ids` carries `min_length=1` on `VisitIn` itself (field.py), so an empty list never
    even reaches `record_visit`'s own business-rule refusal — it is caught at request validation,
    HTTP 422, before the route body runs at all. Proves this action still surfaces a clean `ok=False`
    for that case, never a crash or an unexamined non-201."""

    async def _go():
        async with spawn_operations() as svc:
            return await run_one(RecordVisitAction(
                base_url=svc.base_url, tenant=TENANT, phone="0522222222", service_ids=[]))

    result = run(_go())
    assert not result.ok
    assert "422" in result.detail


def test_the_same_idempotency_key_recorded_concurrently_is_never_double_counted():
    """The exact shape this project's own referral race-fix proved matters elsewhere: N concurrent
    callers sending the SAME idempotency_key for the SAME sale must produce exactly one real visit
    — `record_visit`'s own double-tap guard (core/operations.py), never N counted visits for one
    customer who tapped save once under a slow network."""
    N = 12

    async def _go():
        async with spawn_operations() as svc:
            action = RecordVisitAction(base_url=svc.base_url, tenant=TENANT, phone="0533333333",
                                       idempotency_key="fixed-key-race-proof")
            results = await run_concurrent(action, N)
            listed = await run_one(RecordVisitAction(
                base_url=svc.base_url, tenant=TENANT, phone="0533333333",
                idempotency_key="fixed-key-race-proof"))
            return results, listed

    results, listed = run(_go())
    assert all(r.ok for r in results), results
    visit_ids = {r.data["visit"]["id"] for r in results}
    assert len(visit_ids) == 1, "every concurrent caller with the same key must get the SAME visit"
    assert listed.data["duplicate"] is True


def test_load_of_independent_visits_reports_a_clean_success_rate():
    COUNT = 40

    async def _go():
        async with spawn_operations() as svc:
            action = RecordUniqueVisitAction(base_url=svc.base_url, tenant=TENANT)
            return await run_load(action, COUNT, concurrency=10)

    results, durations = run(_go())
    report = summarize(results, durations=durations)
    assert report.count == COUNT
    assert report.error_rate == 0.0, report
