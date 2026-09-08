"""Stage 8 (docs/وصف-تطبيق-الحجوزات.md §2.6, §6.2): a number read at the moment it is useful, and
the "أقرب موعد" button.
"""
from __future__ import annotations

import asyncio

import pytest
from app.adapters.datastore.memory import MemoryDataStore
from app.core.licence import NullLicence
from app.core.operations import (BookingEvents, BookingOperations, DurationLookup,
                                 StaffEligibilityLookup, StaffHoursLookup, SubjectRefLookup,
                                 VisitGateway)
from app.core.stores import BookingStore

TENANT = "t1"


async def _duration(tenant, service_ids):
    return 30 if list(service_ids) == ["svc1"] else None


async def _subject_ref(tenant, customer_id):
    return "sub_" + customer_id


async def _no_visits(**kw):
    return {"visit_id": "vis_1"}


def _ops(*, risk_window=5, risk_threshold_percent=60, working_hours=None,
         eligible_staff_ids=None, staff_hours_by_operator=None) -> BookingOperations:
    store = MemoryDataStore()
    async def _eligibility(tenant, service_ids):
        if eligible_staff_ids is None:
            return {}
        return {sid: eligible_staff_ids.get(sid) for sid in service_ids if sid in eligible_staff_ids}
    async def _staff_hours(tenant, operator_ids):
        if staff_hours_by_operator is None:
            return {}
        return {oid: staff_hours_by_operator.get(oid) for oid in operator_ids
               if oid in staff_hours_by_operator}
    return BookingOperations(
        datastore=store, bookings=BookingStore(store),
        durations=DurationLookup(lookup=_duration), licence=NullLicence(),
        visits=VisitGateway(create=_no_visits),
        subject_refs=SubjectRefLookup(lookup=_subject_ref),
        events=BookingEvents(publish=None),
        risk_window=risk_window, risk_threshold_percent=risk_threshold_percent,
        working_hours=working_hours,
        staff_eligibility=StaffEligibilityLookup(lookup=_eligibility),
        staff_hours=StaffHoursLookup(lookup=_staff_hours))


def _run(c):
    return asyncio.run(c)


def _mk(ops, *, starts_at: int, customer_id: str = "c1"):
    return ops.create(tenant=TENANT, branch_id="b1", operator_id="op1", customer_id=customer_id,
                      service_ids=["svc1"], starts_at=starts_at)


# ── §2.6: the no-show risk number ────────────────────────────────────────────────────────────

def test_a_customer_with_no_closed_appointments_is_not_risky():
    ops = _ops()

    async def run():
        return await ops.no_show_risk(TENANT, "cus_new")

    risk = _run(run())
    assert risk == {"considered": 0, "no_shows": 0, "risky": False, "threshold_percent": 60}


def test_three_no_shows_of_the_last_five_marks_her_risky():
    ops = _ops()

    async def run():
        for i in range(5):
            b = await _mk(ops, starts_at=1786860000 + i * 86400)
            if i < 3:
                await ops.no_show(TENANT, b.id)
            else:
                await ops.attend(TENANT, b.id)
        return await ops.no_show_risk(TENANT, "c1")

    risk = _run(run())
    assert risk["considered"] == 5
    assert risk["no_shows"] == 3
    assert risk["risky"] is True


def test_two_no_shows_is_not_yet_risky():
    ops = _ops()

    async def run():
        for i in range(5):
            b = await _mk(ops, starts_at=1786860000 + i * 86400)
            if i < 2:
                await ops.no_show(TENANT, b.id)
            else:
                await ops.attend(TENANT, b.id)
        return await ops.no_show_risk(TENANT, "c1")

    risk = _run(run())
    assert risk["risky"] is False


def test_pending_and_cancelled_bookings_are_not_counted():
    """A number about CLOSED appointments — a future booking or a cancelled one says nothing
    about whether she shows up."""
    ops = _ops()

    async def run():
        b1 = await _mk(ops, starts_at=1786860000)
        await ops.no_show(TENANT, b1.id)
        b2 = await _mk(ops, starts_at=1786860000 + 86400)
        await ops.cancel(TENANT, b2.id)
        await _mk(ops, starts_at=1786860000 + 2 * 86400)   # still pending
        return await ops.no_show_risk(TENANT, "c1")

    risk = _run(run())
    assert risk["considered"] == 1
    assert risk["no_shows"] == 1
    assert risk["risky"] is False


def test_only_the_last_five_closed_appointments_count():
    ops = _ops()

    async def run():
        for i in range(4):
            b = await _mk(ops, starts_at=1786860000 + i * 86400)
            await ops.no_show(TENANT, b.id)
        for i in range(4, 7):
            b = await _mk(ops, starts_at=1786860000 + i * 86400)
            await ops.attend(TENANT, b.id)
        return await ops.no_show_risk(TENANT, "c1")

    risk = _run(run())
    assert risk["considered"] == 5
    # 7 closed total (4 no-shows + 3 attended); the most recent 5 are the 3 attended plus the
    # two most recent no-shows — the oldest two no-shows fall outside the window.
    assert risk["no_shows"] == 2
    assert risk["risky"] is False


def test_a_stricter_threshold_flags_her_from_fewer_no_shows():
    # 40% of a window of 5 -> a minimum sample of 2 (ceil(0.4*5)), not the default 3.
    ops = _ops(risk_threshold_percent=40)

    async def run():
        for i in range(5):
            b = await _mk(ops, starts_at=1786860000 + i * 86400)
            if i < 2:
                await ops.no_show(TENANT, b.id)
            else:
                await ops.attend(TENANT, b.id)
        return await ops.no_show_risk(TENANT, "c1")

    risk = _run(run())
    assert risk["considered"] == 5
    assert risk["no_shows"] == 2
    assert risk["risky"] is True
    assert risk["threshold_percent"] == 40


def test_a_single_no_show_is_never_risky_even_at_100_percent():
    # 100% of one closed appointment is not a pattern — the minimum-sample floor (ceil(1.0*5)=5)
    # refuses to call it risky no matter how strict the percentage is.
    ops = _ops(risk_threshold_percent=100)

    async def run():
        b = await _mk(ops, starts_at=1786860000)
        await ops.no_show(TENANT, b.id)
        return await ops.no_show_risk(TENANT, "c1")

    risk = _run(run())
    assert risk["considered"] == 1
    assert risk["no_shows"] == 1
    assert risk["risky"] is False


def test_a_smaller_window_judges_her_on_less_history():
    ops = _ops(risk_window=2, risk_threshold_percent=60)

    async def run():
        for i in range(2):
            b = await _mk(ops, starts_at=1786860000 + i * 86400)
            await ops.no_show(TENANT, b.id)
        return await ops.no_show_risk(TENANT, "c1")

    risk = _run(run())
    assert risk["considered"] == 2
    assert risk["no_shows"] == 2
    assert risk["risky"] is True


# ── §6.2: "أقرب موعد" ─────────────────────────────────────────────────────────────────────────

def test_nearest_slot_finds_the_first_real_opening():
    ops = _ops()

    async def run():
        found = await ops.nearest_slot(
            tenant=TENANT, branch_id="b1", operator_id="op1", service_ids=["svc1"],
            after=1786860000)
        return found

    starts_at = _run(run())
    assert starts_at == 1786860000


def test_nearest_slot_respects_the_shops_own_real_working_hours():
    # 1786860000 is Sunday 09:00 Riyadh (weekday()==6). Close Sunday entirely, open Monday
    # (weekday()==0) 10:00-18:00 — the search must skip past Sunday and land Monday at 10:00,
    # not offer 09:00 on a day the shop is closed.
    from app.adapters.datastore.memory import MemoryDataStore
    from app.core.stores import WorkingHoursStore

    ds = MemoryDataStore()
    whs = WorkingHoursStore(ds)

    async def seed():
        weekly = {str(d): {"closed": True, "start_minute": 0, "end_minute": 0} for d in range(7)}
        weekly["6"] = {"closed": True, "start_minute": 0, "end_minute": 0}
        weekly["0"] = {"closed": False, "start_minute": 600, "end_minute": 1080}
        await whs.save(TENANT, {"weekly": weekly})

    _run(seed())
    ops = _ops(working_hours=whs)

    async def run():
        return await ops.nearest_slot(
            tenant=TENANT, branch_id="b1", operator_id="op1", service_ids=["svc1"],
            after=1786860000)

    starts_at = _run(run())
    import datetime as _dt
    from app.core.riyadh import RIYADH
    when = _dt.datetime.fromtimestamp(starts_at, tz=RIYADH)
    assert when.weekday() == 0   # Monday
    assert (when.hour, when.minute) == (10, 0)


def test_nearest_slot_skips_a_conflict():
    ops = _ops()

    async def run():
        await _mk(ops, starts_at=1786860000)   # op1 busy 09:00-09:30
        return await ops.nearest_slot(
            tenant=TENANT, branch_id="b1", operator_id="op1", service_ids=["svc1"],
            after=1786860000)

    starts_at = _run(run())
    assert starts_at is not None
    assert starts_at >= 1786860000 + 30 * 60


def test_nearest_slot_refuses_on_unconfigured_duration():
    ops = _ops()

    async def run():
        await ops.nearest_slot(
            tenant=TENANT, branch_id="b1", operator_id="op1", service_ids=["svc_unknown"],
            after=1786860000)

    from app.core.operations import OperationError
    with pytest.raises(OperationError):
        _run(run())


# ── staff↔service eligibility and per-operator working hours (this feature) ──────────────────

def test_a_shop_that_never_restricted_anything_sees_no_change_at_all():
    """The graceful-degradation requirement, proven directly: an eligibility port that answers
    "no restriction found" (the default for every service nobody has ever touched) must not
    refuse create() or nearest_slot() for any operator."""
    ops = _ops(eligible_staff_ids={})

    async def run():
        b = await _mk(ops, starts_at=1786860000)
        found = await ops.nearest_slot(
            tenant=TENANT, branch_id="b1", operator_id="op1", service_ids=["svc1"],
            after=1786860000 + 3600)
        return b, found

    booking, found = _run(run())
    assert booking.operator_id == "op1"
    assert found is not None


def test_create_refuses_an_operator_not_eligible_for_the_service():
    ops = _ops(eligible_staff_ids={"svc1": ["op2"]})   # only op2 may do svc1

    async def run():
        return await _mk(ops, starts_at=1786860000)   # _mk always books op1

    from app.core.operations import OperationError
    with pytest.raises(OperationError):
        _run(run())


def test_create_succeeds_for_the_actually_eligible_operator():
    ops = _ops(eligible_staff_ids={"svc1": ["op1", "op2"]})

    async def run():
        return await _mk(ops, starts_at=1786860000)

    booking = _run(run())
    assert booking.operator_id == "op1"


def test_nearest_slot_refuses_a_probe_against_an_ineligible_operator():
    """A client cannot bypass eligibility by skipping create() and only ever calling "أقرب
    موعد" — the same restriction refuses the SEARCH too, so no open slot leaks for an operator
    who could never actually be booked into it."""
    ops = _ops(eligible_staff_ids={"svc1": ["op2"]})

    async def run():
        await ops.nearest_slot(
            tenant=TENANT, branch_id="b1", operator_id="op1", service_ids=["svc1"],
            after=1786860000)

    from app.core.operations import OperationError
    with pytest.raises(OperationError):
        _run(run())


def test_nearest_slot_narrows_to_an_operators_own_shorter_hours():
    """The shop is open 08:00-22:00 (the honest default with no working-hours store wired); an
    operator whose OWN hours only run 14:00-18:00 must never be offered a slot at 09:00, even
    though the shop itself would allow it."""
    ops = _ops(staff_hours_by_operator={
        "op1": {str(d): {"closed": False, "start_minute": 840, "end_minute": 1080} for d in range(7)},
    })

    async def run():
        return await ops.nearest_slot(
            tenant=TENANT, branch_id="b1", operator_id="op1", service_ids=["svc1"],
            after=1786860000)   # 09:00 — before this operator's own 14:00 start

    starts_at = _run(run())
    import datetime as _dt
    from app.core.riyadh import RIYADH
    when = _dt.datetime.fromtimestamp(starts_at, tz=RIYADH)
    assert (when.hour, when.minute) == (14, 0)


def test_an_operators_override_can_never_reach_wider_than_the_shops_own_hours():
    """Defence in depth: even if an override somehow claims hours OUTSIDE the shop's own (a
    write-time check bypassed, or the row edited directly), the shop's own hours still win —
    the intersection, never the operator's raw claim."""
    from app.adapters.datastore.memory import MemoryDataStore
    from app.core.stores import WorkingHoursStore

    ds = MemoryDataStore()
    whs = WorkingHoursStore(ds)

    async def seed():
        weekly = {str(d): {"closed": False, "start_minute": 600, "end_minute": 1080} for d in range(7)}   # 10:00-18:00
        await whs.save(TENANT, {"weekly": weekly})

    _run(seed())
    ops = _ops(working_hours=whs, staff_hours_by_operator={
        # Claims 06:00-23:00 — wider than the shop's 10:00-18:00 on every side.
        "op1": {str(d): {"closed": False, "start_minute": 0, "end_minute": 1380} for d in range(7)},
    })

    async def run():
        return await ops.nearest_slot(
            tenant=TENANT, branch_id="b1", operator_id="op1", service_ids=["svc1"],
            after=1786860000 - 3600)   # 08:00 — before the shop's own 10:00 start

    starts_at = _run(run())
    import datetime as _dt
    from app.core.riyadh import RIYADH
    when = _dt.datetime.fromtimestamp(starts_at, tz=RIYADH)
    assert (when.hour, when.minute) == (10, 0)   # the shop's own start, not the operator's wider claim
