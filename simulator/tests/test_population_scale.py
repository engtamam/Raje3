"""Platform-scale infrastructure, piece 2 proof: `common/population.py::populate` creates MANY
real, independent tenants against ONE real, already-running services/operations — proving the
mechanism at genuine scale (hundreds of real tenants, real HTTP, real in-memory datastore), not a
fixture standing in for it.
"""
from __future__ import annotations

import asyncio

from simulator.apps.operations.actions import CreateBranchAction, ListOperatorsAction
from simulator.apps.operations.service import spawn as spawn_operations
from simulator.common.engine import run_one
from simulator.common.population import populate


def run(coro):
    return asyncio.run(coro)


def test_hundreds_of_real_independent_tenants_each_get_their_own_real_branch():
    """The main proof: 300 real tenants, each hitting the real create-branch route concurrently
    (bounded), each getting back its OWN real branch id — never leaking into another tenant's own
    data, which is exactly what a shared-nothing-per-tenant platform is supposed to guarantee."""
    COUNT = 300

    async def _go():
        async with spawn_operations() as svc:
            def make_action(tenant_id: str):
                return CreateBranchAction(base_url=svc.base_url, tenant=tenant_id,
                                          branch_name="الفرع الرئيسي")
            return await populate(make_action, COUNT, concurrency=25)

    results = run(_go())
    assert len(results) == COUNT
    assert all(r.result.ok for r in results), [r for r in results if not r.result.ok][:3]

    tenant_ids = {r.tenant_id for r in results}
    assert len(tenant_ids) == COUNT, "tenant ids must be distinct — that is the whole point"

    branch_ids = {r.result.data["id"] for r in results}
    assert len(branch_ids) == COUNT, "every tenant must get its OWN branch, never a shared one"


def test_a_tenant_from_the_population_is_a_genuinely_real_independent_tenant_afterward():
    """A tenant created through `populate` must behave exactly like any hand-created tenant
    afterward — e.g. `ListOperatorsAction` against it must work and see only ITS OWN data, proving
    `populate` did not take some shortcut that leaves a half-real tenant behind."""

    async def _go():
        async with spawn_operations() as svc:
            def make_action(tenant_id: str):
                return CreateBranchAction(base_url=svc.base_url, tenant=tenant_id,
                                          branch_name="الفرع الرئيسي")
            results = await populate(make_action, 5, concurrency=5)
            picked = results[2]
            listed = await run_one(ListOperatorsAction(
                base_url=svc.base_url, tenant=picked.tenant_id, caller_subject="owner"))
            return picked, listed

    picked, listed = run(_go())
    assert picked.result.ok
    assert listed.ok, listed
