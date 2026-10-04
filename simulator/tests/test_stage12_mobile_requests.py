"""New app wired into the simulator: services/operations' own mobile/on-the-go service-request
queue (`app/api/v1/mobile_requests.py`) — the shop's own review queue for a technician sent to a
customer rather than the customer coming to the shop. Real HTTP against a real, spawned
services/operations, proving the full lifecycle AND the two-capability manager/execute split that
route file's own docstring describes.
"""
from __future__ import annotations

import asyncio

from simulator.apps.operations.mobile_requests_actions import (
    _EXECUTE_CAP, _MANAGE_CAP, AcceptMobileRequestAction, AssignMobileRequestAction,
    CompleteMobileRequestAction, CreateMobileRequestAction, ListMobileRequestsAction,
    NoShowMobileRequestAction, RejectMobileRequestAction,
)
from simulator.apps.operations.service import spawn as spawn_operations
from simulator.common.engine import run_one

TENANT = "sim-mobile-requests"


def run(coro):
    return asyncio.run(coro)


def test_full_lifecycle_create_accept_complete_records_a_real_visit():
    async def _go():
        async with spawn_operations() as svc:
            created = await run_one(CreateMobileRequestAction(
                base_url=svc.base_url, tenant=TENANT, phone="0511111111"))
            request_id = created.data["id"]
            accepted = await run_one(AcceptMobileRequestAction(
                base_url=svc.base_url, tenant=TENANT, request_id=request_id))
            completed = await run_one(CompleteMobileRequestAction(
                base_url=svc.base_url, tenant=TENANT, request_id=request_id))
            return created, accepted, completed

    created, accepted, completed = run(_go())
    assert created.ok, created
    assert created.data["status"] == "pending"
    assert accepted.ok, accepted
    assert accepted.data["status"] == "accepted"
    assert completed.ok, completed
    assert completed.data["status"] == "completed"
    assert completed.data["visit_id"], "completing must record a real visit and keep its id"


def test_rejecting_a_pending_request_never_reaches_accepted():
    async def _go():
        async with spawn_operations() as svc:
            created = await run_one(CreateMobileRequestAction(
                base_url=svc.base_url, tenant=TENANT, phone="0522222222"))
            rejected = await run_one(RejectMobileRequestAction(
                base_url=svc.base_url, tenant=TENANT, request_id=created.data["id"],
                reason="بعيد عن نطاق الخدمة"))
            accept_after_reject = await run_one(AcceptMobileRequestAction(
                base_url=svc.base_url, tenant=TENANT, request_id=created.data["id"]))
            return rejected, accept_after_reject

    rejected, accept_after_reject = run(_go())
    assert rejected.ok, rejected
    assert rejected.data["status"] == "rejected"
    assert not accept_after_reject.ok, "a rejected request must refuse a later accept, not allow it"


def test_no_show_never_records_a_visit():
    async def _go():
        async with spawn_operations() as svc:
            created = await run_one(CreateMobileRequestAction(
                base_url=svc.base_url, tenant=TENANT, phone="0533333333"))
            await run_one(AcceptMobileRequestAction(
                base_url=svc.base_url, tenant=TENANT, request_id=created.data["id"]))
            no_show = await run_one(NoShowMobileRequestAction(
                base_url=svc.base_url, tenant=TENANT, request_id=created.data["id"]))
            return no_show

    no_show = run(_go())
    assert no_show.ok, no_show
    assert no_show.data["status"] == "no_show"
    assert not no_show.data.get("visit_id"), "a no-show must never carry a recorded visit id"


def test_an_execute_tier_operator_cannot_complete_a_request_assigned_to_someone_else():
    """The exact ownership check `expected_assignee` exists for (core/mobile_requests.py::
    complete's own docstring): an execute-tier caller may mark تم only on THEIR OWN assigned
    request, server-enforced, never trusted from the caller's own claimed identity."""

    async def _go():
        async with spawn_operations() as svc:
            created = await run_one(CreateMobileRequestAction(
                base_url=svc.base_url, tenant=TENANT, phone="0544444444"))
            request_id = created.data["id"]
            await run_one(AssignMobileRequestAction(
                base_url=svc.base_url, tenant=TENANT, request_id=request_id,
                operator_id="op-assigned-real"))
            await run_one(AcceptMobileRequestAction(
                base_url=svc.base_url, tenant=TENANT, request_id=request_id))
            wrong_operator_complete = await run_one(CompleteMobileRequestAction(
                base_url=svc.base_url, tenant=TENANT, request_id=request_id,
                caller_subject="op-someone-else", caller_caps=(_EXECUTE_CAP,)))
            right_operator_complete = await run_one(CompleteMobileRequestAction(
                base_url=svc.base_url, tenant=TENANT, request_id=request_id,
                caller_subject="op-assigned-real", caller_caps=(_EXECUTE_CAP,)))
            return wrong_operator_complete, right_operator_complete

    wrong_operator_complete, right_operator_complete = run(_go())
    assert not wrong_operator_complete.ok, \
        "an operator must never complete a request assigned to somebody else"
    assert right_operator_complete.ok, right_operator_complete


def test_an_execute_tier_operator_sees_only_their_own_assigned_queue():
    """`list_mobile_requests` forces an execute-tier caller server-side to their own assigned_to —
    never trusted from a query param (module docstring). Two requests, assigned to two different
    operators: each operator's own list must show exactly one, never the other's."""

    async def _go():
        async with spawn_operations() as svc:
            req_a = await run_one(CreateMobileRequestAction(
                base_url=svc.base_url, tenant=TENANT, phone="0555555555"))
            req_b = await run_one(CreateMobileRequestAction(
                base_url=svc.base_url, tenant=TENANT, phone="0566666666"))
            await run_one(AssignMobileRequestAction(
                base_url=svc.base_url, tenant=TENANT, request_id=req_a.data["id"],
                operator_id="op-a"))
            await run_one(AssignMobileRequestAction(
                base_url=svc.base_url, tenant=TENANT, request_id=req_b.data["id"],
                operator_id="op-b"))
            list_a = await run_one(ListMobileRequestsAction(
                base_url=svc.base_url, tenant=TENANT, caller_subject="op-a",
                caller_caps=(_EXECUTE_CAP,)))
            list_b = await run_one(ListMobileRequestsAction(
                base_url=svc.base_url, tenant=TENANT, caller_subject="op-b",
                caller_caps=(_EXECUTE_CAP,)))
            return req_a, req_b, list_a, list_b

    req_a, req_b, list_a, list_b = run(_go())
    ids_a = {r["id"] for r in list_a.data["requests"]}
    ids_b = {r["id"] for r in list_b.data["requests"]}
    assert ids_a == {req_a.data["id"]}
    assert ids_b == {req_b.data["id"]}


def test_a_manager_sees_everything_an_execute_tier_operator_would_never_see_alone():
    async def _go():
        async with spawn_operations() as svc:
            req = await run_one(CreateMobileRequestAction(
                base_url=svc.base_url, tenant=TENANT, phone="0577777777"))
            await run_one(AssignMobileRequestAction(
                base_url=svc.base_url, tenant=TENANT, request_id=req.data["id"],
                operator_id="op-c"))
            manager_list = await run_one(ListMobileRequestsAction(
                base_url=svc.base_url, tenant=TENANT, caller_subject="owner",
                caller_caps=(_MANAGE_CAP,)))
            return req, manager_list

    req, manager_list = run(_go())
    ids = {r["id"] for r in manager_list.data["requests"]}
    assert req.data["id"] in ids
