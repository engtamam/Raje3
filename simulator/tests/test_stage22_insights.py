"""A sixth real, independent app wired into the simulator: services/insights (`apps/insights/`).
Real HTTP against a real, spawned services/insights; a fresh tenant has no real visit-event history
behind it (no real event bus wired into any of these newer apps), so every proof here is about the
honest EMPTY/ZERO state a brand-new establishment actually sees, not invented data.
"""
from __future__ import annotations

import asyncio

from simulator.apps.insights.actions import BranchesAction, DashboardAction, RefreshAction
from simulator.apps.insights.service import spawn as spawn_insights
from simulator.common.engine import run_one

TENANT = "sim-insights"


def run(coro):
    return asyncio.run(coro)


def test_a_fresh_tenants_dashboard_reads_cleanly_with_no_real_history_yet():
    async def _go():
        async with spawn_insights() as svc:
            return await run_one(DashboardAction(base_url=svc.base_url, tenant=TENANT))

    result = run(_go())
    assert result.ok, result


def test_a_fresh_tenant_has_no_branches_to_compare_yet():
    async def _go():
        async with spawn_insights() as svc:
            return await run_one(BranchesAction(base_url=svc.base_url, tenant=TENANT))

    result = run(_go())
    assert result.ok, result


def test_refreshing_a_fresh_tenants_snapshot_on_demand_works():
    async def _go():
        async with spawn_insights() as svc:
            refreshed = await run_one(RefreshAction(base_url=svc.base_url, tenant=TENANT))
            dashboard = await run_one(DashboardAction(base_url=svc.base_url, tenant=TENANT))
            return refreshed, dashboard

    refreshed, dashboard = run(_go())
    assert refreshed.ok, refreshed
    assert dashboard.ok, dashboard
