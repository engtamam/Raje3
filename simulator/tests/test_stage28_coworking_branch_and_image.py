"""Stage 28: coworking's own real branch-scoping (owner decision, 2026-09-27) and its new
description/single-photo support (owner decision, same day) — proven for real, not merely wired.
"""
from __future__ import annotations

import asyncio
import base64

from simulator.apps.coworking.actions import (
    CreateResourceAction, GetResourceImageAction, ListResourcesAction, UploadResourceImageAction,
)
from simulator.apps.coworking.service import spawn as spawn_coworking
from simulator.apps.operations.service import spawn as spawn_operations
from simulator.common.engine import run_one
from simulator.common.fleet import ServiceSpec, run_fleet

TENANT = "sim-coworking-branch"

# The smallest possible valid PNG (1x1, transparent) — real bytes, not a placeholder string.
_TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")


def run(coro):
    return asyncio.run(coro)


def _fleet_specs():
    return [
        ServiceSpec(name="operations", spawn=spawn_operations),
        ServiceSpec(name="coworking", spawn=spawn_coworking,
                   needs={"OPERATIONS_SERVICE_URL": "operations"}),
    ]


def test_a_resource_created_with_description_reads_back_publicly_never_leaking_the_image_key():
    async def _go():
        async with spawn_coworking() as svc:
            created = await run_one(CreateResourceAction(
                base_url=svc.base_url, tenant=TENANT, resource_name="غرفة اجتماعات",
                description="غرفة هادئة تتسع لأربعة أشخاص، بإطلالة على الحديقة"))
            listed = await run_one(ListResourcesAction(base_url=svc.base_url, tenant=TENANT))
            return created, listed

    created, listed = run(_go())
    assert created.ok, created
    assert created.data["description"] == "غرفة هادئة تتسع لأربعة أشخاص، بإطلالة على الحديقة"
    assert created.data["has_image"] is False
    assert "image_key" not in created.data, "the internal object-store key must never leave this service"
    assert any(r["id"] == created.data["id"] for r in listed.data["resources"])


def test_uploading_and_reading_back_a_real_photo_round_trips_the_exact_bytes():
    async def _go():
        async with spawn_coworking() as svc:
            created = await run_one(CreateResourceAction(
                base_url=svc.base_url, tenant=TENANT, resource_name="مكتب فردي"))
            uploaded = await run_one(UploadResourceImageAction(
                base_url=svc.base_url, tenant=TENANT, resource_id=created.data["id"],
                data_base64=base64.b64encode(_TINY_PNG).decode(), content_type="image/png"))
            fetched = await run_one(GetResourceImageAction(
                base_url=svc.base_url, tenant=TENANT, resource_id=created.data["id"]))
            return created, uploaded, fetched

    created, uploaded, fetched = run(_go())
    assert created.ok, created
    assert uploaded.ok, uploaded
    assert uploaded.data["has_image"] is True
    assert fetched.ok, fetched
    assert fetched.data["bytes"] == _TINY_PNG
    assert fetched.data["content_type"] == "image/png"


def test_a_manager_scoped_to_one_branch_never_sees_a_resource_at_another_branch():
    """The main branch-scoping proof — a real 3-service Fleet (identity+operations+coworking), a
    real hired manager scoped to branch A via operations' own real branch-scope peer, proving
    coworking's own resource list actually narrows, not merely accepts the field — same proof
    shape as `test_stage14_integration.py`'s own mobile-requests branch-scope test."""
    from simulator.apps.identity.directory import lookup_person_id
    from simulator.apps.identity.service import spawn as spawn_identity
    from simulator.apps.operations.actions import CreateBranchAction, HireMemberAction

    specs = [
        ServiceSpec(name="identity", spawn=spawn_identity),
        ServiceSpec(name="operations", spawn=spawn_operations,
                   needs={"IDENTITY_SERVICE_URL": "identity"}),
        ServiceSpec(name="coworking", spawn=spawn_coworking,
                   needs={"OPERATIONS_SERVICE_URL": "operations"}),
    ]

    async def _real_go():
        async with run_fleet(specs) as fleet:
            idn_url = fleet.url("identity")
            ops_url = fleet.url("operations")
            coworking_url = fleet.url("coworking")
            tenant = f"{TENANT}-fleet"

            branch_a = await run_one(CreateBranchAction(
                base_url=ops_url, tenant=tenant, branch_name="فرع أ"))
            branch_b = await run_one(CreateBranchAction(
                base_url=ops_url, tenant=tenant, branch_name="فرع ب"))
            assert branch_a.ok and branch_b.ok

            manager_a = await run_one(HireMemberAction(
                base_url=ops_url, tenant=tenant, phone="0511110003",
                password="Passw0rd1", role="manager", branch_id=branch_a.data["id"]))
            assert manager_a.ok, manager_a
            manager_a_person = await lookup_person_id(idn_url, tenant=tenant, phone="0511110003")
            assert manager_a_person

            resource_a = await run_one(CreateResourceAction(
                base_url=coworking_url, tenant=tenant, resource_name="غرفة الفرع أ",
                branch_id=branch_a.data["id"]))
            resource_b = await run_one(CreateResourceAction(
                base_url=coworking_url, tenant=tenant, resource_name="غرفة الفرع ب",
                branch_id=branch_b.data["id"]))
            assert resource_a.ok and resource_b.ok

            scoped_list = await run_one(ListResourcesAction(
                base_url=coworking_url, tenant=tenant, caller_subject=manager_a_person))
            unscoped_list = await run_one(ListResourcesAction(
                base_url=coworking_url, tenant=tenant, caller_subject="owner"))
            return resource_a, resource_b, scoped_list, unscoped_list

    resource_a, resource_b, scoped_list, unscoped_list = run(_real_go())
    scoped_ids = {r["id"] for r in scoped_list.data["resources"]}
    unscoped_ids = {r["id"] for r in unscoped_list.data["resources"]}
    assert resource_a.data["id"] in scoped_ids
    assert resource_b.data["id"] not in scoped_ids, \
        "a manager scoped to branch A must never see a resource assigned to branch B"
    assert resource_a.data["id"] in unscoped_ids and resource_b.data["id"] in unscoped_ids, \
        "the owner (unnarrowed) must still see both"
