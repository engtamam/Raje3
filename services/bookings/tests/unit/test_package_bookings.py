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
                                 PackageOfferableCheck, PackageServicesLookup, SubjectRefLookup,
                                 VisitGateway)
from app.core.stores import BookingStore

TENANT = "t1"


class _FixedDurations:
    async def __call__(self, tenant: str, service_ids, quantities=None) -> int | None:
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


class _FixedPackageOfferable:
    """Defaults to "always offerable" — this file's own scheduling behaviour is covered in
    test_package_scheduling.py; these tests are about duration/eligibility/attend, and must not
    trip over the schedule gate by accident."""
    def __init__(self, offerable: bool = True) -> None:
        self._offerable = offerable

    async def __call__(self, tenant: str, package_id: str, at: int) -> bool:
        return self._offerable


class _RecordingVisits:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def __call__(self, **kwargs) -> dict | None:
        self.calls.append(kwargs)
        return {"visit_id": "vis_1"}


async def _subject_ref(tenant: str, customer_id: str) -> str:
    return "sub_" + customer_id


def _ops(*, package_durations=None, package_services=None, package_eligibility=None,
        package_offerable=None, visits=None) -> tuple[BookingOperations, _RecordingVisits]:
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
            lookup=package_eligibility or _FixedPackageEligibility()),
        package_offerable=PackageOfferableCheck(
            lookup=package_offerable or _FixedPackageOfferable()))
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


def test_a_package_booking_ignores_any_quantity_sent_for_it():
    """Packages have no per-component quantity concept (`Package.service_ids` in operations-
    service's own models.py: a bundle of DISTINCT services, never one repeated) — a caller
    sending `quantities` alongside a package must not have it silently accepted onto the row,
    and must not be refused for it either (the same way `meter`/`plate` are simply ignored by a
    shop that does not track vehicles, rather than validated against a field that has no meaning
    here)."""
    ops, _ = _ops()
    booking = _run(ops.create(tenant=TENANT, branch_id="b1", operator_id="op1", customer_id="c1",
                              service_ids=[], package_id="pkg1", starts_at=1786860000,
                              quantities={"svc1": 999_999_999}))   # would refuse if validated
    assert booking.quantities == {}


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


def test_nearest_slot_for_a_package_uses_the_package_duration_and_eligibility():
    ops, _ = _ops(package_durations=_FixedPackageDurations({"pkg1": 60}),
                 package_eligibility=_FixedPackageEligibility({"pkg1": ["op1"]}))
    starts_at = _run(ops.nearest_slot(tenant=TENANT, branch_id="b1", operator_id="op1",
                                      service_ids=[], package_id="pkg1", after=1786860000))
    assert starts_at is not None


def test_nearest_slot_refuses_an_ineligible_operator_for_a_package():
    ops, _ = _ops(package_eligibility=_FixedPackageEligibility({"pkg1": ["op9"]}))
    with pytest.raises(OperationError, match="لا يقدر"):
        _run(ops.nearest_slot(tenant=TENANT, branch_id="b1", operator_id="op1",
                              service_ids=[], package_id="pkg1", after=1786860000))


def test_a_package_off_its_own_schedule_refuses_the_requested_date():
    ops, _ = _ops(package_offerable=_FixedPackageOfferable(offerable=False))
    with pytest.raises(OperationError, match="غير متاحة في هذا التاريخ"):
        _run(ops.create(tenant=TENANT, branch_id="b1", operator_id="op1", customer_id="c1",
                        service_ids=[], package_id="pkg1", starts_at=1786860000))


def test_no_offerable_check_wired_refuses_a_package_booking():
    ops, _ = _ops(package_offerable=None)
    ops._package_offerable = None            # simulate a deployment with none wired at all
    with pytest.raises(OperationError, match="غير متاحة في هذا التاريخ"):
        _run(ops.create(tenant=TENANT, branch_id="b1", operator_id="op1", customer_id="c1",
                        service_ids=[], package_id="pkg1", starts_at=1786860000))


class _RecordingOfferable:
    """Records which (package_id, at) pairs it was actually asked about, and refuses everything
    except the one day named `only_ok_at` — the day-stepping test's stand-in for a weekly
    package that only runs on Saturdays."""
    def __init__(self, only_ok_day_start: int, only_ok_day_end: int) -> None:
        self.only_ok_day_start = only_ok_day_start
        self.only_ok_day_end = only_ok_day_end
        self.calls: list[tuple[str, int]] = []

    async def __call__(self, tenant: str, package_id: str, at: int) -> bool:
        self.calls.append((package_id, at))
        return self.only_ok_day_start <= at < self.only_ok_day_end


def test_nearest_slot_day_steps_past_days_the_package_does_not_run_on():
    """THE LOAD-BEARING GUARANTEE: a package that only runs on some days must never have
    nearest_slot hand back a time on a day it does not — even though the shop is open and the
    operator is free every day in the window."""
    # after = day 0 at 09:00; the package is only offerable from day 2 onward.
    after = 1786860000
    day = 86400
    offerable = _RecordingOfferable(only_ok_day_start=after + 2 * day, only_ok_day_end=after + 3 * day)
    ops, _ = _ops(package_offerable=offerable)
    starts_at = _run(ops.nearest_slot(tenant=TENANT, branch_id="b1", operator_id="op1",
                                      service_ids=[], package_id="pkg1", after=after))
    assert starts_at is not None
    assert starts_at >= after + 2 * day
    assert starts_at < after + 3 * day
    # MEMOISED PER DAY — several candidate slots fall on each rejected day (business hours give
    # more than one), and each must be asked about at most once.
    asked_days = [at for (_pid, at) in offerable.calls]
    from app.core.stores import day_bucket
    assert len(asked_days) == len(set(day_bucket(a) for a in asked_days))


def test_nearest_slot_finds_nothing_when_the_package_never_runs_in_the_whole_window():
    offerable = _FixedPackageOfferable(offerable=False)
    ops, _ = _ops(package_offerable=offerable)
    starts_at = _run(ops.nearest_slot(tenant=TENANT, branch_id="b1", operator_id="op1",
                                      service_ids=[], package_id="pkg1", after=1786860000))
    assert starts_at is None


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


# ── deep robustness pass (100-test confidence sweep) ─────────────────────────────────────────────

def test_a_second_create_with_the_same_idempotency_key_returns_the_first_package_booking():
    ops, _ = _ops()
    first = _run(ops.create(tenant=TENANT, branch_id="b1", operator_id="op1", customer_id="c1",
                            service_ids=[], package_id="pkg1", starts_at=1786860000,
                            idempotency_key="tap-pkg-1"))
    second = _run(ops.create(tenant=TENANT, branch_id="b1", operator_id="op1", customer_id="c1",
                             service_ids=[], package_id="pkg1", starts_at=1786860000,
                             idempotency_key="tap-pkg-1"))
    assert first.id == second.id


def test_a_lapsed_subscription_refuses_a_package_booking_too():
    from app.core.licence import LicenceError

    class _RefusingLicence:
        async def allowed(self, tenant: str) -> bool:
            return False

        async def require(self, tenant: str) -> None:
            raise LicenceError("تطبيق الحجوزات ليس في اشتراكك")

    ops, _ = _ops()
    ops._licence = _RefusingLicence()
    with pytest.raises(LicenceError):
        _run(ops.create(tenant=TENANT, branch_id="b1", operator_id="op1", customer_id="c1",
                        service_ids=[], package_id="pkg1", starts_at=1786860000))


def test_a_package_booking_without_a_branch_is_refused():
    ops, _ = _ops()
    with pytest.raises(OperationError, match="الفرع"):
        _run(ops.create(tenant=TENANT, branch_id="", operator_id="op1", customer_id="c1",
                        service_ids=[], package_id="pkg1", starts_at=1786860000))


def test_a_package_booking_without_starts_at_is_refused():
    ops, _ = _ops()
    with pytest.raises(OperationError, match="وقت الحجز"):
        _run(ops.create(tenant=TENANT, branch_id="b1", operator_id="op1", customer_id="c1",
                        service_ids=[], package_id="pkg1", starts_at=0))


def test_reschedule_of_a_package_booking_preserves_its_package_id():
    ops, visits = _ops()

    async def run():
        booking = await ops.create(tenant=TENANT, branch_id="b1", operator_id="op1",
                                   customer_id="c1", service_ids=[], package_id="pkg1",
                                   starts_at=1786860000)
        moved = await ops.reschedule(tenant=TENANT, booking_id=booking.id, starts_at=1786870000)
        return moved

    moved = _run(run())
    assert moved.package_id == "pkg1"
    assert moved.starts_at == 1786870000


def test_attend_is_idempotent_for_a_package_booking():
    ops, visits = _ops()

    async def run():
        booking = await ops.create(tenant=TENANT, branch_id="b1", operator_id="op1",
                                   customer_id="c1", service_ids=[], package_id="pkg1",
                                   starts_at=1786860000)
        first = await ops.attend(TENANT, booking.id)
        second = await ops.attend(TENANT, booking.id)
        return first, second

    first, second = _run(run())
    assert first.visit_id == second.visit_id
    assert len(visits.calls) == 1     # the second attend() is a no-op, no second peer call


def test_cancelling_a_package_booking_works_the_same_as_an_ordinary_one():
    ops, _ = _ops()

    async def run():
        booking = await ops.create(tenant=TENANT, branch_id="b1", operator_id="op1",
                                   customer_id="c1", service_ids=[], package_id="pkg1",
                                   starts_at=1786860000)
        return await ops.cancel(TENANT, booking.id, reason="غيّرت رأيها")

    cancelled = _run(run())
    assert cancelled.status == "cancelled"
    assert cancelled.package_id == "pkg1"


def test_package_services_lookup_returning_a_single_service_still_books():
    """The resolved component list is trusted as-is — operations' own PackageStore is the source
    of truth for "at least two services" (enforced at package CREATE time there); bookings does
    not re-derive that rule, it only asks what the components currently are."""
    ops, _ = _ops(package_services=_FixedPackageServices({"pkg1": ["svc_only_one"]}))
    booking = _run(ops.create(tenant=TENANT, branch_id="b1", operator_id="op1", customer_id="c1",
                              service_ids=[], package_id="pkg1", starts_at=1786860000))
    assert booking.service_ids == ("svc_only_one",)


def test_nearest_slot_day_steps_across_a_month_boundary():
    after = int(__import__("datetime").datetime(2026, 1, 30, 9, 0, tzinfo=__import__("datetime").timezone.utc).timestamp())
    day = 86400
    offerable = _RecordingOfferable(only_ok_day_start=after + 3 * day, only_ok_day_end=after + 4 * day)
    ops, _ = _ops(package_offerable=offerable)
    starts_at = _run(ops.nearest_slot(tenant=TENANT, branch_id="b1", operator_id="op1",
                                      service_ids=[], package_id="pkg1", after=after,
                                      search_days=14))
    assert starts_at is not None
    assert starts_at >= after + 3 * day


def test_nearest_slot_respects_search_days_and_finds_nothing_just_past_the_window():
    after = 1786860000
    day = 86400
    # Only offerable ONE second past the search window's own end.
    offerable = _RecordingOfferable(only_ok_day_start=after + 14 * day, only_ok_day_end=after + 15 * day)
    ops, _ = _ops(package_offerable=offerable)
    starts_at = _run(ops.nearest_slot(tenant=TENANT, branch_id="b1", operator_id="op1",
                                      service_ids=[], package_id="pkg1", after=after,
                                      search_days=14))
    assert starts_at is None


def test_an_eligible_operator_for_one_component_but_not_for_the_package_as_a_whole_is_refused():
    """The package's OWN eligibility answer is authoritative — bookings never re-derives it from
    individual components, it trusts whatever operations' package-eligibility route already
    computed (including its own disjoint-specialty degradation)."""
    ops, _ = _ops(package_eligibility=_FixedPackageEligibility({"pkg1": ["op_other"]}))
    with pytest.raises(OperationError, match="لا يقدر"):
        _run(ops.create(tenant=TENANT, branch_id="b1", operator_id="op1", customer_id="c1",
                        service_ids=[], package_id="pkg1", starts_at=1786860000))
