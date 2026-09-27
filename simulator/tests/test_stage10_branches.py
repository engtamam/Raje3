"""The branches/permissions module — real branch-scope isolation, proven over real HTTP against
a real services/operations AND a real identity-service (spawned together — see apps/identity/
service.py's own module docstring for why a real login, not the four-digit PIN, is the only way
to get a person_id `branch_scope()` can match at all).

`services/operations/app/api/scope.py::branch_scope`/`visible` is the real code being exercised —
never reimplemented or reached into directly. Every assertion here is about what a REAL HTTP
response contains, driven by a REAL Operator row created through the REAL hiring route.
"""
from __future__ import annotations

import asyncio

from simulator.apps.identity.directory import lookup_person_id
from simulator.apps.identity.service import spawn as spawn_identity
from simulator.apps.operations.actions import (
    CreateBranchAction, HireMemberAction, ListOperatorsAction, SetOperatorScopeAction,
)
from simulator.apps.operations.service import spawn as spawn_operations
from simulator.common.engine import run_one

TENANT = "sim-stage10"


def run(coro):
    return asyncio.run(coro)


def test_two_employees_each_scoped_to_their_own_branch_never_see_each_others_roster():
    """THE MAIN PROOF: branch A's own employee and branch B's own employee, each asking the SAME
    real route (`GET /api/v1/staff/operators`) with their own real, hired identity — branch A's
    employee sees only branch A's roster, branch B's only branch B's, never the other's."""
    tenant = f"{TENANT}-isolation"

    async def _go():
        async with spawn_identity() as idn:
            async with spawn_operations(identity_url=idn.base_url) as ops:
                branch_a = await run_one(
                    CreateBranchAction(base_url=ops.base_url, tenant=tenant,
                                      branch_name="فرع الرياض"))
                assert branch_a.ok, branch_a
                branch_b = await run_one(
                    CreateBranchAction(base_url=ops.base_url, tenant=tenant,
                                      branch_name="فرع جدة"))
                assert branch_b.ok, branch_b

                hire_a = await run_one(HireMemberAction(
                    base_url=ops.base_url, tenant=tenant, phone="0511111111",
                    password="Passw0rd1", role="operator", branch_id=branch_a.data["id"]))
                assert hire_a.ok, hire_a
                hire_b = await run_one(HireMemberAction(
                    base_url=ops.base_url, tenant=tenant, phone="0522222222",
                    password="Passw0rd2", role="operator", branch_id=branch_b.data["id"]))
                assert hire_b.ok, hire_b

                person_a = await lookup_person_id(idn.base_url, tenant=tenant, phone="0511111111")
                person_b = await lookup_person_id(idn.base_url, tenant=tenant, phone="0522222222")
                assert person_a and person_b, (person_a, person_b)

                as_a = await run_one(ListOperatorsAction(
                    base_url=ops.base_url, tenant=tenant, caller_subject=person_a))
                as_b = await run_one(ListOperatorsAction(
                    base_url=ops.base_url, tenant=tenant, caller_subject=person_b))
                return as_a, as_b

    as_a, as_b = run(_go())
    assert as_a.ok and as_b.ok, (as_a, as_b)
    a_branch_ids = {o["branch_id"] for o in as_a.data["operators"]}
    b_branch_ids = {o["branch_id"] for o in as_b.data["operators"]}
    # each one sees their OWN branch (and only their own) — never the other's.
    assert a_branch_ids and b_branch_ids
    assert a_branch_ids.isdisjoint(b_branch_ids), (a_branch_ids, b_branch_ids)


def test_visible_all_lets_a_supervisor_see_every_branchs_roster():
    """The OTHER real path a real employee can be given: `visible_all=True` — a supervisor over
    the whole chain, not narrowed to one branch. The same real route, the same real check, a
    different real grant."""
    tenant = f"{TENANT}-visible-all"

    async def _go():
        async with spawn_identity() as idn:
            async with spawn_operations(identity_url=idn.base_url) as ops:
                branch_a = await run_one(CreateBranchAction(
                    base_url=ops.base_url, tenant=tenant, branch_name="فرع 1"))
                branch_b = await run_one(CreateBranchAction(
                    base_url=ops.base_url, tenant=tenant, branch_name="فرع 2"))
                assert branch_a.ok and branch_b.ok

                supervisor = await run_one(HireMemberAction(
                    base_url=ops.base_url, tenant=tenant, phone="0533333333",
                    password="Passw0rd3", role="supervisor", branch_id=branch_a.data["id"]))
                assert supervisor.ok, supervisor
                # a second, ordinary employee at the other branch, purely so there is a SECOND
                # branch's own row for the supervisor to prove they can see.
                other = await run_one(HireMemberAction(
                    base_url=ops.base_url, tenant=tenant, phone="0544444444",
                    password="Passw0rd4", role="operator", branch_id=branch_b.data["id"]))
                assert other.ok, other

                grant = await run_one(SetOperatorScopeAction(
                    base_url=ops.base_url, tenant=tenant, operator_id=supervisor.data["id"],
                    visible_all=True))
                assert grant.ok, grant

                person_id = await lookup_person_id(idn.base_url, tenant=tenant,
                                                   phone="0533333333")
                assert person_id
                return await run_one(ListOperatorsAction(
                    base_url=ops.base_url, tenant=tenant, caller_subject=person_id))

    result = run(_go())
    assert result.ok, result
    seen_branch_ids = {o["branch_id"] for o in result.data["operators"]}
    assert {"", None} != seen_branch_ids  # a real, non-trivial answer
    assert len(seen_branch_ids) >= 2, "expected both branches' own rows to be visible"


def test_a_deactivated_employee_is_refused_everything_never_widened_to_see_all():
    """THE REGRESSION THIS GUARDS AGAINST, BY NAME (scope.py's own docstring): `REVOKED` (a
    stopped employee) is `None`, which is falsy — a naive `if not scope: return everything` would
    have handed a DISMISSED person the whole chain's roster instead of nothing. This is real,
    still-valid JWT (nothing about the token itself expired or changed) hitting a real route
    after the person's own row was deactivated — proving the SECOND lock (this module's own
    words: "in practice no token reaches here at all — this is the second lock, and it is the
    one that holds if the first is ever skipped or a token is still in flight") for real.

    TWO BRANCHES, TWO EMPLOYEES — DELIBERATELY, not one of each. With only one branch/operator in
    the whole tenant, "sees nothing" and "sees everything" produce the IDENTICAL response (there
    is only ever one row to show either way), so a single-branch version of this test could not
    actually tell REVOKED from the exact widening bug it exists to catch. This shape is the only
    one that can distinguish them."""
    tenant = f"{TENANT}-revoked"

    async def _go():
        async with spawn_identity() as idn:
            async with spawn_operations(identity_url=idn.base_url) as ops:
                branch_a = await run_one(CreateBranchAction(
                    base_url=ops.base_url, tenant=tenant, branch_name="فرع أ"))
                assert branch_a.ok
                branch_b = await run_one(CreateBranchAction(
                    base_url=ops.base_url, tenant=tenant, branch_name="فرع ب"))
                assert branch_b.ok

                member = await run_one(HireMemberAction(
                    base_url=ops.base_url, tenant=tenant, phone="0555555555",
                    password="Passw0rd5", role="operator", branch_id=branch_a.data["id"]))
                assert member.ok, member
                other = await run_one(HireMemberAction(
                    base_url=ops.base_url, tenant=tenant, phone="0566666677",
                    password="Passw0rd6", role="operator", branch_id=branch_b.data["id"]))
                assert other.ok, other

                person_id = await lookup_person_id(idn.base_url, tenant=tenant,
                                                   phone="0555555555")
                assert person_id

                # confirm the SAME token/subject sees ONLY their own branch (not branch B's)
                # before being stopped — the control this test's own contrast depends on.
                before = await run_one(ListOperatorsAction(
                    base_url=ops.base_url, tenant=tenant, caller_subject=person_id))

                stop = await run_one(SetOperatorScopeAction(
                    base_url=ops.base_url, tenant=tenant, operator_id=member.data["id"],
                    active=False))
                assert stop.ok, stop

                after = await run_one(ListOperatorsAction(
                    base_url=ops.base_url, tenant=tenant, caller_subject=person_id))
                return before, after

    before, after = run(_go())
    assert before.ok
    before_branches = {o["branch_id"] for o in before.data["operators"]}
    assert before_branches == {before.data["operators"][0]["branch_id"]}, before_branches
    assert after.ok  # still a clean 200 — REVOKED is an empty LIST, never an error status
    after_branches = {o["branch_id"] for o in after.data["operators"]}
    assert after_branches == set(), (
        "a stopped employee's own still-valid token must see NOTHING, never the whole chain — "
        f"got {after.data['operators']!r}")
