"""Booking a PACKAGE instead of individual services — mutually exclusive `package_id`/`service_ids`
(packages feature). Mirrors test_booking_operations.py's fixture shape.
"""
from __future__ import annotations

import asyncio

import pytest
from app.adapters.datastore.memory import MemoryDataStore
from app.core.licence import NullLicence
from app.core.operations import (BookingEvents, BookingOperations, DurationLookup, OperationError,
                                 PackageDurationLookup, PackageEligibilityLookup,
                                 PackageServicesLookup, SubjectRefLookup, VisitGateway)
from app.core.stores import BookingStore

TENANT = "t1"


class _FixedDurations:
    async def __call__(self, tenant: str, service_ids) -> int | None:
        return 30 * len(service_ids) if service_ids else None


class _FixedPackageDurations:
    def __init__(self, by_package: dict[str, int] | None = None) -> None:
        self._by_package = by_package or {}

    async def __call__(self, tenant: str, package_id: str) -> int | None:
        return self._by_package.get(package_id)


class _FixedPackageServices:
    def __init__(self, by_package: dict[str, list[str]] | None = None) -> None:
        self._by_package = by_package or {"pkg1": ["svc1", "svc2"]}

    async def __call__(self, tenant: str, package_id: str) -> list[str] | None:
        return self._by_package.get(package_id)


class _FixedPackageEligibility:
    def __init__(self, by_package: dict[str, list[str]] | None = None) -> None:
        self._by_package = by_package or {}

    async def __call__(self, tenant: str, package_id: str) -> list[str] | None:
        return self._by_package.get(package_id)


class _RecordingVisits:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def __call__(self, **kwargs) -> dict | None:
        self.calls.append(kwargs)
        return {"visit_id": "vis_1"}


async def _subject_ref(tenant: str, customer_id: str) -> str:
    return "sub_" + customer_id


def _ops(*, package_durations=None, package_services=None, package_eligibility=None,
        visits=None) -> tuple[BookingOperations, _RecordingVisits]:
    store = MemoryDataStore()
    visits = visits or _RecordingVisits()
    ops = BookingOperations(
        datastore=store, bookings=BookingStore(store),
        durations=DurationLookup(lookup=_FixedDurations()), licence=NullLicence(),
        visits=VisitGateway(create=visits),
        subject_refs=SubjectRefLookup(lookup=_subject_ref),
        events=BookingEvents(publish=None),
        package_durations=PackageDurationLookup(
            lookup=package_durations or _FixedPackageDurations({"pkg1": 60})),
        package_services=PackageServicesLookup(
            lookup=package_services or _FixedPackageServices()),
        package_eligibility=PackageEligibilityLookup(
            lookup=package_eligibility or _FixedPackageEligibility()))
    return ops, visits


def _run(coro):
    return asyncio.run(coro)


def test_creating_a_package_booking_resolves_its_components_and_duration():
    ops, _ = _ops()
    booking = _run(ops.create(tenant=TENANT, branch_id="b1", operator_id="op1", customer_id="c1",
                              service_ids=[], package_id="pkg1", starts_at=1786860000))
    assert booking.package_id == "pkg1"
    assert set(booking.service_ids) == {"svc1", "svc2"}
    assert booking.duration_minutes == 60          # from the package's own duration lookup


def test_service_ids_and_package_id_together_is_refused():
    ops, _ = _ops()
    with pytest.raises(OperationError, match="لا الاثنين"):
        _run(ops.create(tenant=TENANT, branch_id="b1", operator_id="op1", customer_id="c1",
                        service_ids=["svc1"], package_id="pkg1", starts_at=1786860000))


def test_neither_service_ids_nor_package_id_is_refused():
    ops, _ = _ops()
    with pytest.raises(OperationError, match="اختر خدمة"):
        _run(ops.create(tenant=TENANT, branch_id="b1", operator_id="op1", customer_id="c1",
                        service_ids=[], package_id="", starts_at=1786860000))


def test_an_unknown_package_is_refused():
    ops, _ = _ops(package_services=_FixedPackageServices({}))
    with pytest.raises(OperationError, match="غير موجودة"):
        _run(ops.create(tenant=TENANT, branch_id="b1", operator_id="op1", customer_id="c1",
                        service_ids=[], package_id="does_not_exist", starts_at=1786860000))


def test_a_package_with_no_duration_configured_refuses_not_guesses():
    ops, _ = _ops(package_durations=_FixedPackageDurations({}))
    with pytest.raises(OperationError, match="مدة"):
        _run(ops.create(tenant=TENANT, branch_id="b1", operator_id="op1", customer_id="c1",
                        service_ids=[], package_id="pkg1", starts_at=1786860000))


def test_an_ineligible_operator_is_refused_for_a_package():
    ops, _ = _ops(package_eligibility=_FixedPackageEligibility({"pkg1": ["op9"]}))
    with pytest.raises(OperationError, match="لا يقدر"):
        _run(ops.create(tenant=TENANT, branch_id="b1", operator_id="op1", customer_id="c1",
                        service_ids=[], package_id="pkg1", starts_at=1786860000))


def test_an_eligible_operator_is_allowed_for_a_package():
    ops, _ = _ops(package_eligibility=_FixedPackageEligibility({"pkg1": ["op1", "op2"]}))
    booking = _run(ops.create(tenant=TENANT, branch_id="b1", operator_id="op1", customer_id="c1",
                              service_ids=[], package_id="pkg1", starts_at=1786860000))
    assert booking.package_id == "pkg1"


def test_attending_a_package_booking_carries_its_package_id_to_the_visit_gateway():
    ops, visits = _ops()

    async def run():
        booking = await ops.create(tenant=TENANT, branch_id="b1", operator_id="op1",
                                   customer_id="c1", service_ids=[], package_id="pkg1",
                                   starts_at=1786860000)
        return await ops.attend(TENANT, booking.id)

    attended = _run(run())
    assert attended.visit_id == "vis_1"
    assert visits.calls[-1]["package_id"] == "pkg1"
    assert set(visits.calls[-1]["service_ids"]) == {"svc1", "svc2"}


def test_no_package_ports_wired_refuses_a_package_booking_explicitly():
    store = MemoryDataStore()
    ops = BookingOperations(
        datastore=store, bookings=BookingStore(store),
        durations=DurationLookup(lookup=_FixedDurations()), licence=NullLicence(),
        visits=VisitGateway(create=_RecordingVisits()),
        subject_refs=SubjectRefLookup(lookup=_subject_ref),
        events=BookingEvents(publish=None))
    with pytest.raises(OperationError, match="غير متاح"):
        _run(ops.create(tenant=TENANT, branch_id="b1", operator_id="op1", customer_id="c1",
                        service_ids=[], package_id="pkg1", starts_at=1786860000))
