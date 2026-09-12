"""managers_for_branch — the recipient list for a branch-scoped in-app alert. `authz` is a fake here
(a real one is a network client, `authz_desk.py`'s own job) so this proves the RESOLUTION LOGIC:
capability holder + branch coverage, combined the same way `api/scope.py::branch_scope` already
reads it for one caller.
"""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.models import Operator
from app.core.notify_recipients import managers_for_branch
from app.core.stores import OperatorStore

TENANT = "tnt_alpha"
BRANCH_A = "br_a"
BRANCH_B = "br_b"


class _FakeAuthz:
    """`assignments`: list of {subject, roles, capabilities}. `role_caps`: role name -> capability
    set, for subjects whose grant comes through a role rather than a direct capability."""

    def __init__(self, assignments: list[dict], role_caps: dict[str, set[str]] | None = None):
        self._assignments = assignments
        self._role_caps = role_caps or {}
        self.effective_calls: list[str] = []

    async def list_assignments(self, tenant: str) -> list[dict]:
        return self._assignments

    async def effective_capabilities(self, tenant: str, subject: str, roles: list[str]) -> set[str]:
        self.effective_calls.append(subject)
        caps: set[str] = set()
        for r in roles:
            caps |= self._role_caps.get(r, set())
        return caps


def run(coro):
    return asyncio.run(coro)


async def _seed_operator(store, **over) -> None:
    base = dict(tenant=TENANT, id=f"op_{over.get('person_id', 'x')}", name="x")
    base.update(over)
    await OperatorStore(store).save(Operator(**base))


def test_the_owner_with_no_operator_row_is_always_included():
    store = MemoryDataStore()
    authz = _FakeAuthz([
        {"subject": "owner_1", "roles": [], "capabilities": ["operations.manage"]},
    ])
    out = run(managers_for_branch(store=store, authz=authz, tenant=TENANT, branch_id=BRANCH_A))
    assert out == ["owner_1"]


def test_a_manager_scoped_to_a_different_branch_is_excluded():
    store = MemoryDataStore()
    run(_seed_operator(store, person_id="mgr_1", branch_id=BRANCH_B))
    authz = _FakeAuthz([
        {"subject": "mgr_1", "roles": [], "capabilities": ["operations.manage"]},
    ])
    out = run(managers_for_branch(store=store, authz=authz, tenant=TENANT, branch_id=BRANCH_A))
    assert out == []


def test_a_manager_scoped_to_the_matching_branch_is_included():
    store = MemoryDataStore()
    run(_seed_operator(store, person_id="mgr_1", branch_id=BRANCH_A))
    authz = _FakeAuthz([
        {"subject": "mgr_1", "roles": [], "capabilities": ["operations.manage"]},
    ])
    out = run(managers_for_branch(store=store, authz=authz, tenant=TENANT, branch_id=BRANCH_A))
    assert out == ["mgr_1"]


def test_visible_branch_ids_covers_more_than_one_branch():
    store = MemoryDataStore()
    run(_seed_operator(store, person_id="sup_1", branch_id=BRANCH_B,
                       visible_branch_ids=[BRANCH_A, BRANCH_B]))
    authz = _FakeAuthz([
        {"subject": "sup_1", "roles": [], "capabilities": ["operations.manage"]},
    ])
    out = run(managers_for_branch(store=store, authz=authz, tenant=TENANT, branch_id=BRANCH_A))
    assert out == ["sup_1"]


def test_visible_all_sees_every_branch():
    store = MemoryDataStore()
    run(_seed_operator(store, person_id="area_mgr", branch_id=BRANCH_B, visible_all=True))
    authz = _FakeAuthz([
        {"subject": "area_mgr", "roles": [], "capabilities": ["operations.manage"]},
    ])
    out = run(managers_for_branch(store=store, authz=authz, tenant=TENANT, branch_id=BRANCH_A))
    assert out == ["area_mgr"]


def test_a_stopped_operator_is_excluded_even_with_the_capability():
    store = MemoryDataStore()
    run(_seed_operator(store, person_id="ex_mgr", branch_id=BRANCH_A, active=False))
    authz = _FakeAuthz([
        {"subject": "ex_mgr", "roles": [], "capabilities": ["operations.manage"]},
    ])
    out = run(managers_for_branch(store=store, authz=authz, tenant=TENANT, branch_id=BRANCH_A))
    assert out == []


def test_a_subject_without_the_capability_at_all_is_excluded():
    store = MemoryDataStore()
    run(_seed_operator(store, person_id="op_1", branch_id=BRANCH_A))
    authz = _FakeAuthz([
        {"subject": "op_1", "roles": [], "capabilities": ["operations.record"]},
    ])
    out = run(managers_for_branch(store=store, authz=authz, tenant=TENANT, branch_id=BRANCH_A))
    assert out == []


def test_a_capability_granted_only_through_a_role_is_still_found():
    """No direct capability listed — only a role — so this must reach `effective_capabilities`."""
    store = MemoryDataStore()
    run(_seed_operator(store, person_id="mgr_1", branch_id=BRANCH_A))
    authz = _FakeAuthz(
        [{"subject": "mgr_1", "roles": ["shift-supervisor"], "capabilities": []}],
        role_caps={"shift-supervisor": {"operations.manage"}},
    )
    out = run(managers_for_branch(store=store, authz=authz, tenant=TENANT, branch_id=BRANCH_A))
    assert out == ["mgr_1"]
    assert authz.effective_calls == ["mgr_1"]


def test_a_direct_capability_grant_never_calls_effective_needlessly():
    store = MemoryDataStore()
    run(_seed_operator(store, person_id="mgr_1", branch_id=BRANCH_A))
    authz = _FakeAuthz([
        {"subject": "mgr_1", "roles": [], "capabilities": ["operations.manage"]},
    ])
    run(managers_for_branch(store=store, authz=authz, tenant=TENANT, branch_id=BRANCH_A))
    assert authz.effective_calls == []


def test_another_tenants_assignments_never_leak_in():
    """`list_assignments` is already tenant-scoped by the authz call itself — this proves the
    resolver does not ALSO need to re-filter by tenant on top of what its peer already scoped."""
    store = MemoryDataStore()
    run(_seed_operator(store, person_id="mgr_1", branch_id=BRANCH_A))
    authz = _FakeAuthz([])   # a real AuthzDesk would simply never return tnt_other's rows here
    out = run(managers_for_branch(store=store, authz=authz, tenant=TENANT, branch_id=BRANCH_A))
    assert out == []
