"""Stage 8 (docs/وصف-تطبيق-الحجوزات.md §2.6, §6.2): a number read at the moment it is useful, and
the "أقرب فتحة" button.
"""
from __future__ import annotations

import asyncio

import pytest
from app.adapters.datastore.memory import MemoryDataStore
from app.core.licence import NullLicence
from app.core.operations import BookingEvents, BookingOperations, DurationLookup, SubjectRefLookup, VisitGateway
from app.core.stores import BookingStore

TENANT = "t1"


async def _duration(tenant, service_ids):
    return 30 if list(service_ids) == ["svc1"] else None


async def _subject_ref(tenant, customer_id):
    return "sub_" + customer_id


async def _no_visits(**kw):
    return {"visit_id": "vis_1"}


def _ops() -> BookingOperations:
    store = MemoryDataStore()
    return BookingOperations(
        datastore=store, bookings=BookingStore(store),
        durations=DurationLookup(lookup=_duration), licence=NullLicence(),
        visits=VisitGateway(create=_no_visits),
        subject_refs=SubjectRefLookup(lookup=_subject_ref),
        events=BookingEvents(publish=None))


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
    assert risk == {"considered": 0, "no_shows": 0, "risky": False}


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


# ── §6.2: "أقرب فتحة" ─────────────────────────────────────────────────────────────────────────

def test_nearest_slot_finds_the_first_real_opening():
    ops = _ops()

    async def run():
        found = await ops.nearest_slot(
            tenant=TENANT, branch_id="b1", operator_id="op1", service_ids=["svc1"],
            after=1786860000)
        return found

    starts_at = _run(run())
    assert starts_at == 1786860000


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
