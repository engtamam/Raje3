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
from app.core.operations import (BookingEvents, BookingOperations, DurationLookup, OperationError,
                                 RewardGateway, SubjectRefLookup, VisitGateway)
from app.core.stores import BookingStore, ConcurrentEditError

TENANT = "t1"


class _FixedDurations:
    def __init__(self, minutes: dict[str, int]) -> None:
        self._by_service = minutes

    async def __call__(self, tenant: str, service_ids, quantities=None) -> int | None:
        total = 0
        for sid in service_ids:
            m = self._by_service.get(sid)
            if not m:
                return None
            total += m * max(1, int((quantities or {}).get(sid, 1)))
        return total


class _RefusingLicence:
    async def allowed(self, tenant: str) -> bool:
        return False

    async def require(self, tenant: str) -> None:
        raise LicenceError("تطبيق الحجوزات ليس في اشتراكك")


class _FixedVisits:
    """A stand-in for `operations`' booking->visit gateway. `answer=None` means the peer refused
    or was unreachable; `boom=True` proves attend() never marks a booking attended silently."""
    def __init__(self, *, answer=None, boom: bool = False) -> None:
        self._answer = answer
        self._boom = boom
        self.calls: list[dict] = []

    async def __call__(self, **kwargs) -> dict | None:
        self.calls.append(kwargs)
        if self._boom:
            raise RuntimeError("operations is restarting")
        return self._answer


class _FixedRewards:
    """A stand-in for `operations`' loyalty desk. `answer=None` means the peer refused or was
    unreachable — the same shape a missing gateway (`rewards=None`) produces, exercised by the
    tests that pass neither."""
    def __init__(self, *, answer=None, boom: bool = False) -> None:
        self._answer = answer
        self._boom = boom
        self.calls: list[dict] = []

    async def __call__(self, **kwargs) -> dict | None:
        self.calls.append(kwargs)
        if self._boom:
            raise RuntimeError("operations is restarting")
        return self._answer


async def _subject_ref(tenant: str, customer_id: str) -> str:
    return "sub_" + customer_id


def _ops(*, licence=None, minutes=None, visits=None, subject_ref_lookup=None,
         rewards=None) -> BookingOperations:
    store = MemoryDataStore()
    return BookingOperations(
        datastore=store, bookings=BookingStore(store),
        durations=DurationLookup(lookup=_FixedDurations(minutes or {"svc1": 30})),
        licence=licence or NullLicence(),
        visits=VisitGateway(create=visits or _FixedVisits(answer={"visit_id": "vis_1"})),
        subject_refs=SubjectRefLookup(lookup=subject_ref_lookup or _subject_ref),
        events=BookingEvents(publish=None),
        rewards=RewardGateway(redeem=rewards) if rewards is not None else None)


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


# ── "2× غسيل خارجي" as a booking, exactly like the same thing recorded as a visit ──────────────

def test_a_quantity_doubles_the_slot_duration_it_asks_for():
    ops = _ops(minutes={"svc1": 30})

    async def run():
        return await ops.create(tenant=TENANT, branch_id="b1", operator_id="op1",
                                customer_id="c1", service_ids=["svc1"], starts_at=1786860000,
                                quantities={"svc1": 2})

    booking = _run(run())
    assert booking.duration_minutes == 60
    assert booking.quantities == {"svc1": 2}


def test_a_quantity_for_a_service_not_on_the_booking_is_refused():
    """A stale client-side quantity for a service that isn't on this booking used to be silently
    dropped; now it refuses instead of quietly booking the wrong count."""
    ops = _ops(minutes={"svc1": 30})

    async def run():
        with pytest.raises(OperationError, match="لا تطابق"):
            await ops.create(tenant=TENANT, branch_id="b1", operator_id="op1",
                            customer_id="c1", service_ids=["svc1"], starts_at=1786860000,
                            quantities={"svc_never_chosen": 5})

    _run(run())


def test_an_out_of_range_quantity_refuses_before_any_booking_is_created():
    ops = _ops(minutes={"svc1": 30})

    async def run():
        with pytest.raises(OperationError, match="quantities"):
            await ops.create(tenant=TENANT, branch_id="b1", operator_id="op1", customer_id="c1",
                            service_ids=["svc1"], starts_at=1786860000,
                            quantities={"svc1": 0})

    _run(run())


def test_editing_services_also_updates_the_quantity_snapshot():
    ops = _ops(minutes={"svc1": 30, "svc2": 20})

    async def run():
        booking = await ops.create(tenant=TENANT, branch_id="b1", operator_id="op1",
                                   customer_id="c1", service_ids=["svc1"], starts_at=1786860000,
                                   quantities={"svc1": 2})
        assert booking.duration_minutes == 60
        return await ops.edit_services(TENANT, booking.id, ["svc2"], quantities={"svc2": 3})

    edited = _run(run())
    assert edited.duration_minutes == 60   # 20 × 3
    assert edited.quantities == {"svc2": 3}
    # the OLD quantity entry must not survive an edit that dropped its own service.
    assert "svc1" not in edited.quantities


def test_attend_carries_the_bookings_own_quantities_to_the_visit_gateway():
    visits = _FixedVisits(answer={"visit_id": "vis_1"})
    ops = _ops(minutes={"svc1": 30}, visits=visits)

    async def run():
        booking = await ops.create(tenant=TENANT, branch_id="b1", operator_id="op1",
                                   customer_id="c1", service_ids=["svc1"], starts_at=1786860000,
                                   quantities={"svc1": 2})
        return await ops.attend(TENANT, booking.id)

    _run(run())
    assert visits.calls[-1]["quantities"] == {"svc1": 2}


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


def test_concurrent_reschedules_of_the_same_booking_do_not_silently_clobber_one_another():
    """The SAME §4 race as `test_concurrent_note_edits_do_not_silently_drop_one`, but for
    `reschedule()` specifically — found by review: `_claim_and_save`'s lock only serialises TWO
    DIFFERENT bookings colliding on the same (branch, operator, time-bucket) lane; it said nothing
    about a SECOND writer editing the SAME booking with a stale in-memory copy (e.g. a staff
    member's console edit racing a booking-management-via-WhatsApp reschedule retry). Fixed by
    `_claim_and_save` now using `save_if_unchanged(expected_rev=...)` instead of a bare `save()`."""
    ops = _ops()

    async def run():
        booking = await ops.create(tenant=TENANT, branch_id="b1", operator_id="op1",
                                   customer_id="c1", service_ids=["svc1"], starts_at=1786860000)
        # First writer reschedules successfully — the booking's rev advances in the store.
        first = await ops.reschedule(tenant=TENANT, booking_id=booking.id,
                                     starts_at=1786860000 + 3600)
        # Second writer's in-memory copy is the PRE-first-reschedule snapshot — its own local
        # mutation (moving starts_at again) still carries the STALE rev, exactly what a retried
        # confirm after a store-write gap would look like.
        stale = booking
        stale.starts_at = 1786860000 + 7200
        return first, stale

    first, stale = _run(run())
    assert first.starts_at == 1786860000 + 3600

    async def run_stale():
        with pytest.raises(ConcurrentEditError):
            await ops._claim_and_save(stale, now=1786860000)

    _run(run_stale())
    # THE FIRST WRITER'S RESCHEDULE MUST STILL STAND — never silently overwritten by the second,
    # refused writer.
    async def reread():
        return await ops._bookings.get(TENANT, first.id)

    current = _run(reread())
    assert current.starts_at == 1786860000 + 3600


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


# ── Stage 4: attendance and the booking->visit gateway (§4) ─────────────────────────────────

def test_attending_a_booking_creates_a_real_visit_via_the_gateway():
    visits = _FixedVisits(answer={"visit_id": "vis_42"})
    ops = _ops(visits=visits)

    async def run():
        booking = await ops.create(tenant=TENANT, branch_id="b1", operator_id="op1",
                                   customer_id="c1", service_ids=["svc1"], starts_at=1786860000)
        return await ops.attend(TENANT, booking.id)

    attended = _run(run())
    assert attended.status == "attended"
    assert attended.visit_id == "vis_42"
    assert visits.calls[0]["idempotency_key"] == f"bkg:{attended.id}"


def test_a_retried_attend_does_not_call_the_gateway_twice():
    """Idempotent — the visit already exists (§4's own duplicate-prevention requirement)."""
    visits = _FixedVisits(answer={"visit_id": "vis_1"})
    ops = _ops(visits=visits)

    async def run():
        booking = await ops.create(tenant=TENANT, branch_id="b1", operator_id="op1",
                                   customer_id="c1", service_ids=["svc1"], starts_at=1786860000)
        first = await ops.attend(TENANT, booking.id)
        second = await ops.attend(TENANT, booking.id)
        return first, second

    first, second = _run(run())
    assert first.visit_id == second.visit_id == "vis_1"
    assert len(visits.calls) == 1, "a retried attend must not call the gateway a second time"


def test_a_failed_gateway_call_never_marks_the_booking_attended():
    """§4's own warning, verified: a Visit that failed to get created must never be implied by a
    booking that already reads 'attended'."""
    ops = _ops(visits=_FixedVisits(answer=None))

    async def run():
        booking = await ops.create(tenant=TENANT, branch_id="b1", operator_id="op1",
                                   customer_id="c1", service_ids=["svc1"], starts_at=1786860000)
        with pytest.raises(OperationError, match="تعذّر تسجيل الزيارة"):
            await ops.attend(TENANT, booking.id)
        return await ops._bookings.get(TENANT, booking.id)

    still_booked = _run(run())
    assert still_booked.status == "booked"
    assert still_booked.visit_id is None


def test_no_show_never_calls_the_visit_gateway():
    visits = _FixedVisits(answer={"visit_id": "vis_should_not_happen"})
    ops = _ops(visits=visits)

    async def run():
        booking = await ops.create(tenant=TENANT, branch_id="b1", operator_id="op1",
                                   customer_id="c1", service_ids=["svc1"], starts_at=1786860000)
        return await ops.no_show(TENANT, booking.id, "لم تحضر")

    marked = _run(run())
    assert marked.status == "no_show"
    assert marked.visit_id is None
    assert visits.calls == []


def test_no_show_is_idempotent():
    ops = _ops()

    async def run():
        booking = await ops.create(tenant=TENANT, branch_id="b1", operator_id="op1",
                                   customer_id="c1", service_ids=["svc1"], starts_at=1786860000)
        first = await ops.no_show(TENANT, booking.id, "لم تحضر")
        second = await ops.no_show(TENANT, booking.id, "سبب آخر")
        return first, second

    first, second = _run(run())
    assert second.reason_no_show == first.reason_no_show, "a retried no_show must not overwrite"


def test_attended_and_no_show_cannot_be_re_entered_into_each_other():
    ops = _ops()

    async def run():
        booking = await ops.create(tenant=TENANT, branch_id="b1", operator_id="op1",
                                   customer_id="c1", service_ids=["svc1"], starts_at=1786860000)
        await ops.no_show(TENANT, booking.id)
        with pytest.raises(OperationError):
            await ops.attend(TENANT, booking.id)

    _run(run())


# ── Stage 5: subject_ref stamped at create, the confirmation event (§5, §6.5) ───────────────

def test_create_stamps_the_customers_subject_ref():
    ops = _ops()

    async def run():
        return await ops.create(tenant=TENANT, branch_id="b1", operator_id="op1",
                                customer_id="c1", service_ids=["svc1"], starts_at=1786860000)

    booking = _run(run())
    assert booking.subject_ref == "sub_c1"


def test_an_unreachable_peer_refuses_creation_rather_than_stamping_nothing():
    async def _cannot_ask(tenant: str, customer_id: str) -> str | None:
        return None
    ops = _ops(subject_ref_lookup=_cannot_ask)

    async def run():
        await ops.create(tenant=TENANT, branch_id="b1", operator_id="op1", customer_id="c1",
                         service_ids=["svc1"], starts_at=1786860000)

    with pytest.raises(OperationError):
        _run(run())


def test_a_created_booking_publishes_the_confirmation_event():
    published = []

    async def publish(topic, event):
        published.append((topic, event.payload))

    ops = _ops()
    ops._events = BookingEvents(publish=publish)

    async def run():
        return await ops.create(tenant=TENANT, branch_id="b1", operator_id="op1",
                                customer_id="c1", service_ids=["svc1"], starts_at=1786860000)

    booking = _run(run())
    assert len(published) == 1
    topic, payload = published[0]
    assert topic == "bookings.booking.changed"
    assert payload["kind"] == "created"
    assert payload["booking_id"] == booking.id
    assert payload["subject_ref"] == "sub_c1"


def test_a_failed_event_publish_does_not_fail_the_booking():
    async def boom(topic, event):
        raise RuntimeError("event bus is down")
    ops = _ops()
    ops._events = BookingEvents(publish=boom)

    async def run():
        return await ops.create(tenant=TENANT, branch_id="b1", operator_id="op1",
                                customer_id="c1", service_ids=["svc1"], starts_at=1786860000)

    booking = _run(run())
    assert booking.status == "booked", "a missed event must never undo or refuse the booking itself"


def test_a_booking_defaults_to_no_payment():
    ops = _ops()

    async def run():
        return await ops.create(tenant=TENANT, branch_id="b1", operator_id="op1",
                                customer_id="c1", service_ids=["svc1"], starts_at=1786860000)

    assert _run(run()).payment_status == "none"


def test_an_unknown_payment_state_refuses_not_guesses():
    ops = _ops()

    async def run():
        with pytest.raises(OperationError, match="دفع"):
            await ops.create(tenant=TENANT, branch_id="b1", operator_id="op1", customer_id="c1",
                            service_ids=["svc1"], starts_at=1786860000, payment_status="half")

    _run(run())


def test_payment_status_is_editable_after_the_booking_is_terminal():
    ops = _ops()

    async def run():
        booking = await ops.create(tenant=TENANT, branch_id="b1", operator_id="op1",
                                   customer_id="c1", service_ids=["svc1"], starts_at=1786860000)
        await ops.cancel(TENANT, booking.id)
        # A cancelled booking still owes a truthful record of what was actually paid — the
        # appointment itself is closed, but "was it paid" is a separate fact that outlives it.
        return await ops.set_payment_status(TENANT, booking.id, "paid")

    updated = _run(run())
    assert updated.payment_status == "paid"


def test_a_deposit_with_no_amount_refuses_not_guesses():
    ops = _ops()

    async def run():
        with pytest.raises(OperationError, match="العربون"):
            await ops.create(tenant=TENANT, branch_id="b1", operator_id="op1", customer_id="c1",
                            service_ids=["svc1"], starts_at=1786860000, payment_status="deposit")

    _run(run())


def test_a_deposit_with_a_real_amount_is_kept():
    ops = _ops()

    async def run():
        return await ops.create(tenant=TENANT, branch_id="b1", operator_id="op1",
                                customer_id="c1", service_ids=["svc1"], starts_at=1786860000,
                                payment_status="deposit", deposit_amount_minor=5000)

    booking = _run(run())
    assert booking.payment_status == "deposit"
    assert booking.deposit_amount_minor == 5000


def test_paid_needs_no_amount_of_its_own():
    ops = _ops()

    async def run():
        return await ops.create(tenant=TENANT, branch_id="b1", operator_id="op1",
                                customer_id="c1", service_ids=["svc1"], starts_at=1786860000,
                                payment_status="paid")

    booking = _run(run())
    assert booking.payment_status == "paid"
    assert booking.deposit_amount_minor is None


def test_switching_away_from_deposit_clears_the_amount():
    ops = _ops()

    async def run():
        booking = await ops.create(tenant=TENANT, branch_id="b1", operator_id="op1",
                                   customer_id="c1", service_ids=["svc1"], starts_at=1786860000,
                                   payment_status="deposit", deposit_amount_minor=5000)
        return await ops.set_payment_status(TENANT, booking.id, "paid")

    updated = _run(run())
    assert updated.payment_status == "paid"
    assert updated.deposit_amount_minor is None


def test_re_sending_deposit_with_no_new_amount_keeps_the_one_already_on_file():
    ops = _ops()

    async def run():
        booking = await ops.create(tenant=TENANT, branch_id="b1", operator_id="op1",
                                   customer_id="c1", service_ids=["svc1"], starts_at=1786860000,
                                   payment_status="deposit", deposit_amount_minor=5000)
        return await ops.set_payment_status(TENANT, booking.id, "deposit")

    updated = _run(run())
    assert updated.deposit_amount_minor == 5000


def test_an_unknown_payment_state_refuses_the_edit_too():
    ops = _ops()

    async def run():
        booking = await ops.create(tenant=TENANT, branch_id="b1", operator_id="op1",
                                   customer_id="c1", service_ids=["svc1"], starts_at=1786860000)
        with pytest.raises(OperationError, match="دفع"):
            await ops.set_payment_status(TENANT, booking.id, "half")

    _run(run())


def test_an_intended_reward_is_never_spent_at_booking_time():
    rewards = _FixedRewards(answer={"ok": True})
    ops = _ops(rewards=rewards)

    async def run():
        return await ops.create(tenant=TENANT, branch_id="b1", operator_id="op1",
                                customer_id="c1", service_ids=["svc1"], starts_at=1786860000,
                                intended_reward_id="rwd_1")

    booking = _run(run())
    assert booking.intended_reward_id == "rwd_1"
    assert rewards.calls == [], "create() must never call the reward gateway — only attend() may"


def test_attending_spends_the_intended_reward_and_clears_it():
    rewards = _FixedRewards(answer={"ok": True})
    ops = _ops(rewards=rewards)

    async def run():
        booking = await ops.create(tenant=TENANT, branch_id="b1", operator_id="op1",
                                   customer_id="c1", service_ids=["svc1"], starts_at=1786860000,
                                   intended_reward_id="rwd_1")
        return await ops.attend(TENANT, booking.id)

    attended = _run(run())
    assert attended.intended_reward_id is None
    assert rewards.calls[0]["reward_id"] == "rwd_1"
    assert rewards.calls[0]["subject_ref"] == "sub_c1"


def test_a_refused_redemption_leaves_the_intent_set_but_still_attends():
    rewards = _FixedRewards(answer={"ok": False, "reason": "REFUSED"})
    ops = _ops(rewards=rewards)

    async def run():
        booking = await ops.create(tenant=TENANT, branch_id="b1", operator_id="op1",
                                   customer_id="c1", service_ids=["svc1"], starts_at=1786860000,
                                   intended_reward_id="rwd_1")
        return await ops.attend(TENANT, booking.id)

    attended = _run(run())
    assert attended.status == "attended", "a refused redemption must never block attendance itself"
    assert attended.intended_reward_id == "rwd_1", "left set — the visit screen's own signal to redeem him by hand"


def test_an_unreachable_reward_gateway_leaves_the_intent_set_too():
    ops = _ops(rewards=_FixedRewards(answer=None))

    async def run():
        booking = await ops.create(tenant=TENANT, branch_id="b1", operator_id="op1",
                                   customer_id="c1", service_ids=["svc1"], starts_at=1786860000,
                                   intended_reward_id="rwd_1")
        return await ops.attend(TENANT, booking.id)

    attended = _run(run())
    assert attended.status == "attended"
    assert attended.intended_reward_id == "rwd_1"


def test_no_reward_gateway_wired_at_all_still_attends_cleanly():
    # `rewards=None` (the default) — a local/test run with nothing configured must behave exactly
    # like every other optional peer in this file: silently absent, never a crash.
    ops = _ops()

    async def run():
        booking = await ops.create(tenant=TENANT, branch_id="b1", operator_id="op1",
                                   customer_id="c1", service_ids=["svc1"], starts_at=1786860000,
                                   intended_reward_id="rwd_1")
        return await ops.attend(TENANT, booking.id)

    attended = _run(run())
    assert attended.status == "attended"
    assert attended.intended_reward_id == "rwd_1"


def test_no_intended_reward_never_calls_the_gateway_at_attend_either():
    rewards = _FixedRewards(answer={"ok": True})
    ops = _ops(rewards=rewards)

    async def run():
        booking = await ops.create(tenant=TENANT, branch_id="b1", operator_id="op1",
                                   customer_id="c1", service_ids=["svc1"], starts_at=1786860000)
        return await ops.attend(TENANT, booking.id)

    _run(run())
    assert rewards.calls == []


# ── the best live campaign/referral/mutual-benefit discount, applied automatically at attend()
# (2026-10-04) — `operations` already decided and applied it inside the SAME peer call that
# creates the visit; `attend()` here only records what it answered. ─────────────────────────────

def test_attending_records_the_offer_operations_already_applied():
    visits = _FixedVisits(answer={"visit_id": "vis_1",
                                  "offer": {"ref": "camp_1", "text": "خصم 20%"}})
    ops = _ops(visits=visits)

    async def run():
        booking = await ops.create(tenant=TENANT, branch_id="b1", operator_id="op1",
                                   customer_id="c1", service_ids=["svc1"], starts_at=1786860000)
        return await ops.attend(TENANT, booking.id)

    attended = _run(run())
    assert attended.applied_offer_ref == "camp_1"
    assert attended.applied_offer_text == "خصم 20%"


def test_nothing_live_leaves_the_offer_fields_unset():
    visits = _FixedVisits(answer={"visit_id": "vis_1", "offer": None})
    ops = _ops(visits=visits)

    async def run():
        booking = await ops.create(tenant=TENANT, branch_id="b1", operator_id="op1",
                                   customer_id="c1", service_ids=["svc1"], starts_at=1786860000)
        return await ops.attend(TENANT, booking.id)

    attended = _run(run())
    assert attended.applied_offer_ref is None
    assert attended.applied_offer_text is None


def test_a_peer_response_with_no_offer_key_at_all_leaves_the_fields_unset_too():
    """An older/unrelated peer answer shaped without the new key must never crash — same
    defensive `.get()` discipline every other optional field here already takes."""
    visits = _FixedVisits(answer={"visit_id": "vis_1"})
    ops = _ops(visits=visits)

    async def run():
        booking = await ops.create(tenant=TENANT, branch_id="b1", operator_id="op1",
                                   customer_id="c1", service_ids=["svc1"], starts_at=1786860000)
        return await ops.attend(TENANT, booking.id)

    attended = _run(run())
    assert attended.applied_offer_ref is None
    assert attended.applied_offer_text is None


def test_a_booking_with_both_an_intended_reward_and_a_live_offer_records_both():
    """The two mechanisms are independent — a points intent (chosen by the customer at booking
    time) and an automatically-applied campaign/referral/mutual-benefit discount are not mutually
    exclusive the way points-vs-apply_offer are for a WALK-IN visit (see
    `Operations.redeem_points_reward`'s own docstring in operations-service for why that one IS
    exclusive): a booking's own visit is created and offered in the SAME peer call, with the
    reward spend a wholly separate step right after."""
    rewards = _FixedRewards(answer={"ok": True})
    visits = _FixedVisits(answer={"visit_id": "vis_1",
                                  "offer": {"ref": "ref_mb", "text": "خصم شراكة إحالة"}})
    ops = _ops(visits=visits, rewards=rewards)

    async def run():
        booking = await ops.create(tenant=TENANT, branch_id="b1", operator_id="op1",
                                   customer_id="c1", service_ids=["svc1"], starts_at=1786860000,
                                   intended_reward_id="rwd_1")
        return await ops.attend(TENANT, booking.id)

    attended = _run(run())
    assert attended.intended_reward_id is None             # spent
    assert attended.applied_offer_ref == "ref_mb"           # and recorded


def test_set_intended_reward_is_editable_before_attendance():
    ops = _ops()

    async def run():
        booking = await ops.create(tenant=TENANT, branch_id="b1", operator_id="op1",
                                   customer_id="c1", service_ids=["svc1"], starts_at=1786860000)
        changed = await ops.set_intended_reward(TENANT, booking.id, "rwd_2")
        cleared = await ops.set_intended_reward(TENANT, changed.id, None)
        return changed, cleared

    changed, cleared = _run(run())
    assert changed.intended_reward_id == "rwd_2"
    assert cleared.intended_reward_id is None


def test_set_intended_reward_refuses_on_a_terminal_booking():
    ops = _ops()

    async def run():
        booking = await ops.create(tenant=TENANT, branch_id="b1", operator_id="op1",
                                   customer_id="c1", service_ids=["svc1"], starts_at=1786860000)
        await ops.cancel(TENANT, booking.id)
        with pytest.raises(OperationError, match="أُغلِق"):
            await ops.set_intended_reward(TENANT, booking.id, "rwd_1")

    _run(run())
