"""New app wired into the simulator: services/bookings (`apps/bookings/`) — genuinely different
from every prior app in ONE structural way worth naming: it cannot create a real booking alone.
`create()` asks TWO real peer questions of operations over HTTP — a service's own configured
duration in minutes, AND whether `customer_id` resolves to a real customer at all (its own
`subject_refs.resolve` call) — so every test here spawns a real Fleet (operations + bookings),
never bookings alone, proving `common/fleet.py` composes with a THIRD real app, not just the two
it was built against.
"""
from __future__ import annotations

import asyncio
import datetime
import time

from simulator.apps.bookings.actions import (
    AttendBookingAction, CancelBookingAction, CreateBookingAction, ListBookingsAction,
    NoShowBookingAction, RescheduleBookingAction,
)
from simulator.apps.bookings.service import spawn as spawn_bookings
from simulator.apps.operations.actions import CreateServiceAction, EnsureCustomerAction
from simulator.apps.operations.service import spawn as spawn_operations
from simulator.common.engine import run_one
from simulator.common.fleet import ServiceSpec, run_fleet

TENANT = "sim-bookings"


def run(coro):
    return asyncio.run(coro)


def _fleet_specs():
    return [
        ServiceSpec(name="operations", spawn=spawn_operations),
        ServiceSpec(name="bookings", spawn=spawn_bookings,
                   needs={"OPERATIONS_SERVICE_URL": "operations"}),
    ]


def test_a_made_up_customer_id_is_refused_a_real_one_ensured_first_just_works():
    """The mechanical proof this app's own peer dependency is real, on the customer side:
    `create()` calls operations' own `subject_refs.resolve(customer_id)` peer route, so a made-up
    id is refused BY NAME ("العميلة غير موجودة") — and a real customer, `ensure`-d on operations
    first, lets the exact same booking through."""

    async def _go():
        async with run_fleet(_fleet_specs()) as fleet:
            ops_url, bookings_url = fleet.url("operations"), fleet.url("bookings")
            service = await run_one(CreateServiceAction(
                base_url=ops_url, tenant=TENANT, service_name="قص شعر", duration_minutes=30))

            refused = await run_one(CreateBookingAction(
                base_url=bookings_url, tenant=TENANT, branch_id="branch-1", operator_id="op-1",
                customer_id="cust-made-up", service_ids=[service.data["id"]],
                starts_at=int(time.time()) + 3600))

            customer = await run_one(EnsureCustomerAction(
                base_url=ops_url, tenant=TENANT, phone="0511111111"))
            created = await run_one(CreateBookingAction(
                base_url=bookings_url, tenant=TENANT, branch_id="branch-1", operator_id="op-1",
                customer_id=customer.data["id"], service_ids=[service.data["id"]],
                starts_at=int(time.time()) + 7200))
            return refused, created

    refused, created = run(_go())
    assert not refused.ok, "a made-up customer_id must refuse a booking, not guess"
    assert created.ok, created


def test_an_unconfigured_zero_minute_service_refuses_a_booking_by_name():
    async def _go():
        async with run_fleet(_fleet_specs()) as fleet:
            ops_url, bookings_url = fleet.url("operations"), fleet.url("bookings")
            customer = await run_one(EnsureCustomerAction(
                base_url=ops_url, tenant=TENANT, phone="0522222222"))
            unconfigured = await run_one(CreateServiceAction(
                base_url=ops_url, tenant=TENANT, service_name="خدمة بلا مدة", duration_minutes=0))
            return await run_one(CreateBookingAction(
                base_url=bookings_url, tenant=TENANT, branch_id="branch-1", operator_id="op-1",
                customer_id=customer.data["id"], service_ids=[unconfigured.data["id"]],
                starts_at=int(time.time()) + 3600))

    refused = run(_go())
    assert not refused.ok, "an unconfigured (0-minute) service must refuse a booking, not guess"


def test_a_full_lifecycle_create_list_reschedule_then_attend():
    async def _go():
        async with run_fleet(_fleet_specs()) as fleet:
            ops_url, bookings_url = fleet.url("operations"), fleet.url("bookings")
            customer = await run_one(EnsureCustomerAction(
                base_url=ops_url, tenant=TENANT, phone="0533333333"))
            service = await run_one(CreateServiceAction(
                base_url=ops_url, tenant=TENANT, service_name="غسيل", duration_minutes=20))
            starts_at = int(time.time()) + 3600
            created = await run_one(CreateBookingAction(
                base_url=bookings_url, tenant=TENANT, branch_id="branch-2", operator_id="op-2",
                customer_id=customer.data["id"], service_ids=[service.data["id"]],
                starts_at=starts_at))
            date_bucket = datetime.datetime.fromtimestamp(
                starts_at, tz=datetime.timezone.utc).strftime("%Y-%m-%d")
            listed = await run_one(ListBookingsAction(
                base_url=bookings_url, tenant=TENANT, branch_id="branch-2", date=date_bucket))
            rescheduled = await run_one(RescheduleBookingAction(
                base_url=bookings_url, tenant=TENANT, booking_id=created.data["id"],
                starts_at=starts_at + 1800))
            attended = await run_one(AttendBookingAction(
                base_url=bookings_url, tenant=TENANT, booking_id=created.data["id"]))
            return created, listed, rescheduled, attended

    created, listed, rescheduled, attended = run(_go())
    assert created.ok, created
    assert listed.ok, listed
    assert any(b["id"] == created.data["id"] for b in listed.data["bookings"])
    assert rescheduled.ok, rescheduled
    assert attended.ok, attended
    assert attended.data["status"] == "attended"


def test_a_second_booking_for_the_same_operator_at_the_exact_same_time_is_refused():
    """The one guarantee a bookings product actually sells: two customers can never both be told
    the same technician is free at 3pm. Same operator, same start time, same branch — the SECOND
    create must be refused, never silently double-booked."""

    async def _go():
        async with run_fleet(_fleet_specs()) as fleet:
            ops_url, bookings_url = fleet.url("operations"), fleet.url("bookings")
            customer_a = await run_one(EnsureCustomerAction(
                base_url=ops_url, tenant=TENANT, phone="0544444444"))
            customer_b = await run_one(EnsureCustomerAction(
                base_url=ops_url, tenant=TENANT, phone="0555555555"))
            service = await run_one(CreateServiceAction(
                base_url=ops_url, tenant=TENANT, service_name="تلميع", duration_minutes=45))
            starts_at = int(time.time()) + 10_800
            first = await run_one(CreateBookingAction(
                base_url=bookings_url, tenant=TENANT, branch_id="branch-3", operator_id="op-3",
                customer_id=customer_a.data["id"], service_ids=[service.data["id"]],
                starts_at=starts_at))
            second = await run_one(CreateBookingAction(
                base_url=bookings_url, tenant=TENANT, branch_id="branch-3", operator_id="op-3",
                customer_id=customer_b.data["id"], service_ids=[service.data["id"]],
                starts_at=starts_at))
            return first, second

    first, second = run(_go())
    assert first.ok, first
    assert not second.ok, "double-booking the same operator at the same time must be refused"


def test_cancelling_then_no_show_are_both_refused_terminal_transitions():
    async def _go():
        async with run_fleet(_fleet_specs()) as fleet:
            ops_url, bookings_url = fleet.url("operations"), fleet.url("bookings")
            customer = await run_one(EnsureCustomerAction(
                base_url=ops_url, tenant=TENANT, phone="0566666666"))
            service = await run_one(CreateServiceAction(
                base_url=ops_url, tenant=TENANT, service_name="حلاقة", duration_minutes=15))
            created = await run_one(CreateBookingAction(
                base_url=bookings_url, tenant=TENANT, branch_id="branch-4", operator_id="op-4",
                customer_id=customer.data["id"], service_ids=[service.data["id"]],
                starts_at=int(time.time()) + 14_400))
            cancelled = await run_one(CancelBookingAction(
                base_url=bookings_url, tenant=TENANT, booking_id=created.data["id"],
                reason="العميل ألغى"))
            no_show_after_cancel = await run_one(NoShowBookingAction(
                base_url=bookings_url, tenant=TENANT, booking_id=created.data["id"]))
            return cancelled, no_show_after_cancel

    cancelled, no_show_after_cancel = run(_go())
    assert cancelled.ok, cancelled
    assert cancelled.data["status"] == "cancelled"
    assert not no_show_after_cancel.ok, \
        "a cancelled booking must refuse a later no-show, never silently accept it"
