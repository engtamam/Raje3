"""Two real gaps closed together: (1) the mobile-requests app's own BRANCH dimension
(mobile_requests.py's own docstring: assigned indirectly, through whoever a request is currently
assigned to) proven with REAL hired operators — `test_stage12_mobile_requests.py` only ever
proved the manager/execute CAPABILITY split with made-up operator ids that resolve to no real
branch at all; and (2) the new apps (visit recording) proven running ALONGSIDE the platform-scale
pieces (Fleet + population + background noise), not just alone.
"""
from __future__ import annotations

import asyncio

from simulator.apps.identity.directory import lookup_person_id
from simulator.apps.identity.service import spawn as spawn_identity
from simulator.apps.operations.actions import (
    CreateBranchAction, HireMemberAction, RecordUniqueVisitAction, SetOperatorScopeAction,
)
from simulator.apps.operations.mobile_requests_actions import (
    _MANAGE_CAP, AssignMobileRequestAction, CreateMobileRequestAction, ListMobileRequestsAction,
)
from simulator.apps.operations.service import spawn as spawn_operations
from simulator.common.background import run_background_noise
from simulator.common.engine import run_one
from simulator.common.fleet import Fleet, ServiceSpec, run_fleet
from simulator.common.population import populate

TENANT = "sim-stage14"


def run(coro):
    return asyncio.run(coro)


def test_a_manager_scoped_to_one_branch_never_sees_a_mobile_request_assigned_to_another_branch():
    """The real branch dimension `test_stage12_mobile_requests.py` never actually exercised —
    that file's own `operator_id`s (`"op-a"`, `"op-b"`, ...) resolve to no real Operator row at
    all, so `_operator_branch` always answered `""` (unassigned, always visible) regardless of
    scope. Here the assigned operator is a REAL hired member with a REAL branch, and a manager
    genuinely scoped away from that branch (`visible_branch_ids`) must never see the request."""
    tenant = f"{TENANT}-branch-scope"

    async def _go():
        async with spawn_identity() as idn:
            async with spawn_operations(identity_url=idn.base_url) as ops:
                branch_a = await run_one(CreateBranchAction(
                    base_url=ops.base_url, tenant=tenant, branch_name="فرع أ"))
                branch_b = await run_one(CreateBranchAction(
                    base_url=ops.base_url, tenant=tenant, branch_name="فرع ب"))
                assert branch_a.ok and branch_b.ok

                manager_a = await run_one(HireMemberAction(
                    base_url=ops.base_url, tenant=tenant, phone="0511110001",
                    password="Passw0rd1", role="manager", branch_id=branch_a.data["id"]))
                assert manager_a.ok, manager_a
                await run_one(SetOperatorScopeAction(
                    base_url=ops.base_url, tenant=tenant, operator_id=manager_a.data["id"],
                    visible_branch_ids=[branch_a.data["id"]]))

                technician_b = await run_one(HireMemberAction(
                    base_url=ops.base_url, tenant=tenant, phone="0511110002",
                    password="Passw0rd2", role="operator", branch_id=branch_b.data["id"]))
                assert technician_b.ok, technician_b

                created = await run_one(CreateMobileRequestAction(
                    base_url=ops.base_url, tenant=tenant, phone="0500000001"))
                assert created.ok, created
                assigned = await run_one(AssignMobileRequestAction(
                    base_url=ops.base_url, tenant=tenant, request_id=created.data["id"],
                    operator_id=technician_b.data["id"]))
                assert assigned.ok, assigned

                manager_a_person = await lookup_person_id(
                    idn.base_url, tenant=tenant, phone="0511110001")
                assert manager_a_person

                scoped_list = await run_one(ListMobileRequestsAction(
                    base_url=ops.base_url, tenant=tenant, caller_subject=manager_a_person,
                    caller_caps=(_MANAGE_CAP,)))
                unscoped_list = await run_one(ListMobileRequestsAction(
                    base_url=ops.base_url, tenant=tenant, caller_subject="owner",
                    caller_caps=(_MANAGE_CAP,)))
                return created, scoped_list, unscoped_list

    created, scoped_list, unscoped_list = run(_go())
    assert scoped_list.ok and unscoped_list.ok
    scoped_ids = {r["id"] for r in scoped_list.data["requests"]}
    unscoped_ids = {r["id"] for r in unscoped_list.data["requests"]}
    assert created.data["id"] not in scoped_ids, \
        "a manager scoped to branch A must never see a request assigned to branch B's technician"
    assert created.data["id"] in unscoped_ids, \
        "the owner (unnarrowed) must still see it — proves this is scoping, not a broken route"


def test_visit_recording_survives_real_background_noise_across_a_populated_fleet():
    """Everything built this session running TOGETHER, once: a real Fleet (identity+operations),
    a real population of tenants, real background noise ticking against that pool, and the visit-
    recording app's own load path proven concurrently with all of it — not each piece proven only
    in isolation."""

    async def _go():
        specs = [
            ServiceSpec(name="identity", spawn=spawn_identity),
            ServiceSpec(name="operations", spawn=spawn_operations,
                       needs={"IDENTITY_SERVICE_URL": "identity"}),
        ]
        async with run_fleet(specs) as fleet:
            assert isinstance(fleet, Fleet)
            ops_url = fleet.url("operations")

            def make_tenant_action(tenant_id: str):
                return CreateBranchAction(base_url=ops_url, tenant=tenant_id,
                                          branch_name="الفرع الرئيسي")
            tenants = [r.tenant_id for r in await populate(
                make_tenant_action, 10, concurrency=5, tenant_prefix="sim-stage14-pool")]

            import random

            def make_noise():
                tenant = random.choice(tenants)
                return RecordUniqueVisitAction(base_url=ops_url, tenant=tenant)

            async with run_background_noise(make_noise, rate_per_second=10.0) as report:
                scenario = await run_one(RecordUniqueVisitAction(
                    base_url=ops_url, tenant="sim-stage14-scenario-tenant"))
                await asyncio.sleep(0.4)
                mid_run_count = report.count
            return scenario, report, mid_run_count

    scenario, report, mid_run_count = run(_go())
    assert scenario.ok, scenario
    assert mid_run_count > 0
    assert report.ok_count > 0
    assert report.fail_count == 0, report
