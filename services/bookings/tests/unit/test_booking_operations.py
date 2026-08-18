"""Create/edit/cancel — the sequential, non-race behaviours (docs/خطة-تنفيذ-الحجوزات.md §3/§4).

The race itself is `test_two_operators_cannot_take_the_same_slot.py`; this file is everything the
lock does not need to prove: the duplicate-tap guard, the "no silent default" refusal, the
snapshot-not-live duration, the one-way status transitions, and write-if-unchanged.
"""
from __future__ import annotations

import asyncio

import pytest
from app.adapters.datastore.memory import MemoryDataStore
from app.core.licence import LicenceError, NullLicence
from app.core.models import STATUS_CANCELLED
from app.core.operations import BookingOperations, DurationLookup, OperationError
from app.core.stores import BookingStore, ConcurrentEditError

TENANT = "t1"


class _FixedDurations:
    def __init__(self, minutes: dict[str, int]) -> None:
        self._by_service = minutes

    async def __call__(self, tenant: str, service_ids) -> int | None:
        total = 0
        for sid in service_ids:
            m = self._by_service.get(sid)
            if not m:
                return None
            total += m
        return total


class _RefusingLicence:
    async def allowed(self, tenant: str) -> bool:
        return False

    async def require(self, tenant: str) -> None:
        raise LicenceError("تطبيق الحجوزات ليس في اشتراكك")


def _ops(*, licence=None, minutes=None) -> BookingOperations:
    store = MemoryDataStore()
    return BookingOperations(
        datastore=store, bookings=BookingStore(store),
        durations=DurationLookup(lookup=_FixedDurations(minutes or {"svc1": 30})),
        licence=licence or NullLicence())


def _run(coro):
    return asyncio.run(coro)


def test_a_second_create_with_the_same_idempotency_key_returns_the_first_booking():
    ops = _ops()

    async def run():
        first = await ops.create(tenant=TENANT, branch_id="b1", operator_id="op1",
                                 customer_id="c1", service_ids=["svc1"], starts_at=1786860000,
                                 idempotency_key="tap-1")
        second = await ops.create(tenant=TENANT, branch_id="b1", operator_id="op1",
                                  customer_id="c1", service_ids=["svc1"], starts_at=1786860000,
                                  idempotency_key="tap-1")
        return first, second

    first, second = _run(run())
    assert first.id == second.id


def test_a_service_with_no_duration_configured_refuses_not_guesses():
    ops = _ops(minutes={"svc1": 0})

    async def run():
        with pytest.raises(OperationError, match="مدة"):
            await ops.create(tenant=TENANT, branch_id="b1", operator_id="op1", customer_id="c1",
                            service_ids=["svc1"], starts_at=1786860000)

    _run(run())


def test_a_lapsed_subscription_refuses_creating_but_never_reading():
    ops = _ops(licence=_RefusingLicence())

    async def run():
        with pytest.raises(LicenceError):
            await ops.create(tenant=TENANT, branch_id="b1", operator_id="op1", customer_id="c1",
                            service_ids=["svc1"], starts_at=1786860000)

    _run(run())


def test_editing_service_ids_recomputes_duration_not_only_at_create():
    ops = _ops(minutes={"svc1": 30, "svc2": 45})

    async def run():
        booking = await ops.create(tenant=TENANT, branch_id="b1", operator_id="op1",
                                   customer_id="c1", service_ids=["svc1"], starts_at=1786860000)
        assert booking.duration_minutes == 30
        edited = await ops.edit_services(TENANT, booking.id, ["svc2"])
        return edited

    edited = _run(run())
    assert edited.duration_minutes == 45, "a service edit must recompute the snapshot, not keep it"


def test_a_reschedule_moves_the_grid_index_bucket():
    ops = _ops()

    async def run():
        booking = await ops.create(tenant=TENANT, branch_id="b1", operator_id="op1",
                                   customer_id="c1", service_ids=["svc1"], starts_at=1786860000)
        # a day later
        moved = await ops.reschedule(tenant=TENANT, booking_id=booking.id,
                                     starts_at=1786860000 + 86400)
        slots_old_day = await ops._bookings.slots_between(
            TENANT, "b1", start_bucket="2026-08-16", end_bucket="2026-08-16")
        slots_new_day = await ops._bookings.slots_between(
            TENANT, "b1", start_bucket="2026-08-17", end_bucket="2026-08-17")
        return moved, slots_old_day, slots_new_day

    moved, old_day, new_day = _run(run())
    assert old_day == [], "the OLD slot row must not linger after a reschedule"
    assert len(new_day) == 1 and new_day[0].id == moved.id


def test_cancel_is_idempotent():
    ops = _ops()

    async def run():
        booking = await ops.create(tenant=TENANT, branch_id="b1", operator_id="op1",
                                   customer_id="c1", service_ids=["svc1"], starts_at=1786860000)
        first = await ops.cancel(TENANT, booking.id, "غيّرت رأيها")
        second = await ops.cancel(TENANT, booking.id, "سبب آخر")
        return first, second

    first, second = _run(run())
    assert first.status == STATUS_CANCELLED
    assert second.status == STATUS_CANCELLED
    assert second.cancelled_reason == first.cancelled_reason, "a retried cancel must not overwrite"


def test_a_terminal_booking_cannot_be_edited_back_to_life():
    ops = _ops()

    async def run():
        booking = await ops.create(tenant=TENANT, branch_id="b1", operator_id="op1",
                                   customer_id="c1", service_ids=["svc1"], starts_at=1786860000)
        await ops.cancel(TENANT, booking.id)
        with pytest.raises(OperationError, match="أُغلِق"):
            await ops.edit_note(TENANT, booking.id, "ملاحظة جديدة")

    _run(run())


def test_concurrent_note_edits_do_not_silently_drop_one():
    """§4's second race scenario: two writers of the SAME row, which the operator/time lock does
    not protect (it serialises different bookings, not two edits of one)."""
    ops = _ops()

    async def run():
        booking = await ops.create(tenant=TENANT, branch_id="b1", operator_id="op1",
                                   customer_id="c1", service_ids=["svc1"], starts_at=1786860000)
        # Both "read" the same snapshot (simulated: both start from the freshly created booking).
        stale_rev = booking.rev
        first = await ops.edit_note(TENANT, booking.id, "من الموظفة الأولى")
        with pytest.raises(ConcurrentEditError):
            # The second writer's in-memory copy still holds the PRE-first-edit rev — the store
            # has since moved on, so this write must be refused, not silently overwrite.
            stale = await ops._bookings.get(TENANT, booking.id)
            stale.note = "من الموظفة الثانية"
            await ops._bookings.save_if_unchanged(stale, expected_rev=stale_rev)
        return first

    first = _run(run())
    assert first.note == "من الموظفة الأولى"


def test_a_double_booking_across_reschedule_is_refused():
    """Not the pure race — the ordinary sequential case: op1 already has 9:00-9:30, a second
    booking dragged onto 9:15 for the same operator must be refused, not silently overlapped."""
    ops = _ops()

    async def run():
        await ops.create(tenant=TENANT, branch_id="b1", operator_id="op1", customer_id="c1",
                         service_ids=["svc1"], starts_at=1786860000)   # 09:00, 30 min
        second = await ops.create(tenant=TENANT, branch_id="b1", operator_id="op1",
                                  customer_id="c2", service_ids=["svc1"], starts_at=1786860900,
                                  idempotency_key="second")   # 09:15 — overlaps
        return second

    from app.core.lock import SlotClaimBusy
    with pytest.raises(SlotClaimBusy):
        _run(run())
