"""THE REAL BUG: `create()` enforces staff eligibility (`_refuse_if_ineligible`) but `reschedule()`
and `edit_services()` never did — a QA audit found both let a booking end up with an operator
assigned to a service they are not eligible for, silently, with no error at all.
"""
from __future__ import annotations

import asyncio

from app.adapters.datastore.memory import MemoryDataStore
from app.core.licence import NullLicence
from app.core.operations import (BookingEvents, BookingOperations, DurationLookup, OperationError,
                                 StaffEligibilityLookup, SubjectRefLookup, VisitGateway)
from app.core.stores import BookingStore

TENANT = "t1"


async def _duration(tenant, service_ids):
    return 30


async def _subject_ref(tenant, customer_id):
    return "sub_" + customer_id


async def _no_visits(**kw):
    return None


def _ops() -> BookingOperations:
    """svc1 is restricted to op1 ONLY — op2 is never eligible for it."""
    store = MemoryDataStore()

    async def _eligibility(tenant, service_ids):
        return {sid: ["op1"] for sid in service_ids if sid == "svc1"}

    return BookingOperations(
        datastore=store, bookings=BookingStore(store),
        durations=DurationLookup(lookup=_duration), licence=NullLicence(),
        visits=VisitGateway(create=_no_visits), subject_refs=SubjectRefLookup(lookup=_subject_ref),
        events=BookingEvents(publish=None),
        staff_eligibility=StaffEligibilityLookup(lookup=_eligibility))


def _run(c):
    return asyncio.run(c)


def test_reschedule_refuses_reassigning_to_an_ineligible_operator():
    ops = _ops()

    async def run():
        booking = await ops.create(tenant=TENANT, branch_id="b1", operator_id="op1",
                                   customer_id="c1", service_ids=["svc1"], starts_at=1_800_000_000)
        return await ops.reschedule(tenant=TENANT, booking_id=booking.id,
                                    starts_at=1_800_003_600, operator_id="op2")

    try:
        _run(run())
        assert False, "reschedule reassigned an ineligible operator without being refused"
    except OperationError as e:
        assert "لا يقدر" in str(e)


def test_edit_services_refuses_swapping_in_a_service_the_current_operator_cannot_do():
    ops = _ops()

    async def run():
        # op2's own first booking must be for something op2 IS eligible for (svc-open, unrestricted).
        booking = await ops.create(tenant=TENANT, branch_id="b1", operator_id="op2",
                                   customer_id="c1", service_ids=["svc-open"],
                                   starts_at=1_800_000_000)
        return await ops.edit_services(TENANT, booking.id, ["svc1"])   # op2 can't do svc1

    try:
        _run(run())
        assert False, "edit_services swapped in a service the current operator can't do, unrefused"
    except OperationError as e:
        assert "لا يقدر" in str(e)
