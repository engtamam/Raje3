"""Platform-scale infrastructure, piece 3 proof: `common/background.py::run_background_noise`
keeps a real, independent stream of traffic hitting a real spawned service WHILE a scenario's own
deliberate action runs concurrently — proving the noise is genuinely concurrent (not just
"scheduled and forgotten"), stops immediately when told to, and never interferes with the
scenario's own real result.
"""
from __future__ import annotations

import asyncio
import random

from simulator.apps.operations.actions import CreateBranchAction, ListOperatorsAction
from simulator.apps.operations.service import spawn as spawn_operations
from simulator.common.background import run_background_noise
from simulator.common.engine import run_one
from simulator.common.population import populate


def run(coro):
    return asyncio.run(coro)


def test_noise_keeps_ticking_concurrently_with_a_real_scenario_action_then_stops_on_exit():
    async def _go():
        async with spawn_operations() as svc:
            def make_tenant_action(tenant_id: str):
                return CreateBranchAction(base_url=svc.base_url, tenant=tenant_id,
                                          branch_name="الفرع الرئيسي")
            tenants = [r.tenant_id for r in await populate(make_tenant_action, 5, concurrency=5)]

            def make_noise():
                tenant = random.choice(tenants)
                return CreateBranchAction(
                    base_url=svc.base_url, tenant=tenant,
                    branch_name=f"فرع ضوضاء {random.randint(1, 1_000_000)}")

            async with run_background_noise(make_noise, rate_per_second=20.0) as report:
                # the scenario's own real, deliberate action — a fresh tenant, unrelated to noise.
                scenario = await run_one(CreateBranchAction(
                    base_url=svc.base_url, tenant="sim-scenario-tenant",
                    branch_name="الفرع الرئيسي"))
                await asyncio.sleep(0.5)  # let noise tick several times alongside it
                mid_run_count = report.count
            return scenario, report, mid_run_count

    scenario, report, mid_run_count = run(_go())
    assert scenario.ok, scenario
    assert mid_run_count > 0, "noise must have ticked at least once while the scenario action ran"
    assert report.count == report.ok_count + report.fail_count
    assert report.ok_count > 0, "noise itself must be real, successful traffic, not just attempts"


def test_stopping_is_immediate_not_waiting_out_whatever_tick_is_mid_sleep():
    """A slow rate (long interval) must still stop the instant the `with` block exits — proves the
    stop is event-gated, not a sleep the caller has to wait out."""

    async def _go():
        async with spawn_operations() as svc:
            def make_noise():
                return ListOperatorsAction(base_url=svc.base_url, tenant="sim-noise-solo",
                                           caller_subject="owner")
            started = asyncio.get_event_loop().time()
            async with run_background_noise(make_noise, rate_per_second=0.5):
                await asyncio.sleep(0.05)
            elapsed = asyncio.get_event_loop().time() - started
            return elapsed

    elapsed = run(_go())
    # the tick interval here is 2 seconds; exiting must not block anywhere near that long.
    assert elapsed < 1.0, f"exit took {elapsed}s — stop is not immediate"
