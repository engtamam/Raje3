"""Mobile/on-the-go service requests — the engine only (core/mobile_requests.py). No network,
no whatsapp-assistant, no bookings — just the state machine and the real Operations instance
(built with a real MemoryDataStore) for record_visit()'s own side effects.
"""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.mobile_requests import (ACCEPTED, COMPLETED, NO_SHOW, PENDING, REJECTED,
                                      MobileRequestError, MobileRequestService, maps_link)
from app.core.models import Service
from app.core.operations import Operations
from app.core.stores import ServiceStore

CC = "966"
TENANT = "tnt_mobile_1"
PHONE = "0501234567"
# A real epoch instant — working_hours is None in the `svc` fixture (no BookingsDesk wired),
# so validate_requested_time() skips its check regardless of clock value; this only needs to
# be > 0 for every test below except the ones that deliberately test that floor.
REQUESTED_TIME = 1_800_000_000


def run(c):
    return asyncio.run(c)


@pytest.fixture()
def svc():
    store = MemoryDataStore()
    ops = Operations(store=store, pii_salt="s" * 32)
    return (MobileRequestService(store=store, operations=ops, default_cc=CC), store, ops)


async def _seed_service(store, service_id: str = "svc_wash") -> str:
    await ServiceStore(store).save(Service(id=service_id, tenant=TENANT, name="غسيل متنقل"))
    return service_id


# ── maps_link — the one genuinely missing utility ───────────────────────────────────────────────
def test_maps_link_is_a_real_clickable_google_maps_url():
    assert maps_link(24.7136, 46.6753) == "https://www.google.com/maps?q=24.7136,46.6753"


# ── creation ─────────────────────────────────────────────────────────────────────────────────
def test_a_new_request_starts_pending(svc):
    s, store, _ops = svc
    sid = run(_seed_service(store))
    req = run(s.create(tenant=TENANT, phone=PHONE, customer_name="أحمد",
                       service_ids=[sid], requested_time=REQUESTED_TIME,
                       lat=24.7136, lng=46.6753))
    assert req.status == PENDING
    assert req.public()["maps_url"] == "https://www.google.com/maps?q=24.7136,46.6753"


def test_creation_refuses_an_invalid_latitude(svc):
    s, store, _ops = svc
    sid = run(_seed_service(store))
    with pytest.raises(MobileRequestError):
        run(s.create(tenant=TENANT, phone=PHONE, customer_name="أحمد", service_ids=[sid],
                     requested_time=REQUESTED_TIME, lat=200, lng=46.6753))


def test_creation_refuses_with_no_services_chosen(svc):
    s, _store, _ops = svc
    with pytest.raises(MobileRequestError):
        run(s.create(tenant=TENANT, phone=PHONE, customer_name="أحمد", service_ids=[],
                     requested_time=REQUESTED_TIME, lat=24.7, lng=46.6))


def test_creation_refuses_a_zero_or_negative_time(svc):
    s, store, _ops = svc
    sid = run(_seed_service(store))
    with pytest.raises(MobileRequestError):
        run(s.create(tenant=TENANT, phone=PHONE, customer_name="أحمد", service_ids=[sid],
                     requested_time=0, lat=24.7, lng=46.6))
    with pytest.raises(MobileRequestError):
        run(s.create(tenant=TENANT, phone=PHONE, customer_name="أحمد", service_ids=[sid],
                     requested_time=-1, lat=24.7, lng=46.6))


# ── requested_time validated against the shop's REAL working hours ─────────────────────────────
class _FakeWorkingHours:
    """Same shape as BookingsDesk: `async working_hours(tenant) -> dict | None`."""

    def __init__(self, weekly: dict | None) -> None:
        self._weekly = weekly

    async def working_hours(self, tenant: str) -> dict | None:
        return self._weekly


def _riyadh_epoch(*, weekday: int, hour: int, minute: int = 0) -> int:
    """A real epoch instant that lands on the given Riyadh weekday/hour — 2026-09-14 is a
    Monday (weekday 0) in Riyadh time, so `days = weekday` walks forward from there."""
    import datetime as _dt

    from app.core.riyadh import RIYADH
    base = _dt.datetime(2026, 9, 14, tzinfo=RIYADH)
    d = base + _dt.timedelta(days=weekday)
    return int(d.replace(hour=hour, minute=minute).timestamp())


_OPEN_MON_TO_SAT = {
    str(d): {"closed": False, "start_minute": 9 * 60, "end_minute": 21 * 60} for d in range(6)
} | {"6": {"closed": True, "start_minute": 0, "end_minute": 0}}   # Sunday closed


def test_creation_accepts_a_real_time_inside_working_hours(svc):
    s, store, _ops = svc
    s._working_hours = _FakeWorkingHours(_OPEN_MON_TO_SAT)
    sid = run(_seed_service(store))
    t = _riyadh_epoch(weekday=0, hour=12)   # Monday, 12:00 — inside 09:00-21:00
    req = run(s.create(tenant=TENANT, phone=PHONE, customer_name="أحمد", service_ids=[sid],
                       requested_time=t, lat=24.7, lng=46.6))
    assert req.requested_time == t


def test_creation_refuses_a_time_outside_working_hours(svc):
    s, store, _ops = svc
    s._working_hours = _FakeWorkingHours(_OPEN_MON_TO_SAT)
    sid = run(_seed_service(store))
    t = _riyadh_epoch(weekday=0, hour=23)   # Monday, 23:00 — past the 21:00 close
    with pytest.raises(MobileRequestError):
        run(s.create(tenant=TENANT, phone=PHONE, customer_name="أحمد", service_ids=[sid],
                     requested_time=t, lat=24.7, lng=46.6))


def test_creation_refuses_a_time_on_a_closed_day(svc):
    s, store, _ops = svc
    s._working_hours = _FakeWorkingHours(_OPEN_MON_TO_SAT)
    sid = run(_seed_service(store))
    t = _riyadh_epoch(weekday=6, hour=12)   # Sunday, closed
    with pytest.raises(MobileRequestError):
        run(s.create(tenant=TENANT, phone=PHONE, customer_name="أحمد", service_ids=[sid],
                     requested_time=t, lat=24.7, lng=46.6))


def test_creation_with_no_working_hours_peer_wired_skips_the_check(svc):
    """None-safe fail-open, same posture BookingsDesk's own docstring documents for an
    unreachable/unconfigured peer — the `svc` fixture's own default."""
    s, store, _ops = svc
    sid = run(_seed_service(store))
    t = _riyadh_epoch(weekday=6, hour=3)   # would be refused if a real schedule were checked
    req = run(s.create(tenant=TENANT, phone=PHONE, customer_name="أحمد", service_ids=[sid],
                       requested_time=t, lat=24.7, lng=46.6))
    assert req.requested_time == t


def test_the_phone_is_stored_canonically(svc):
    """Two different spellings of the same number must resolve to the same stored phone, so the
    no-show risk lookup below actually finds them together. `canonical_phone` always prefixes
    `+` (core/signup.py's own module-wide convention) — this is the LOGIN identifier shape."""
    s, store, _ops = svc
    sid = run(_seed_service(store))
    a = run(s.create(tenant=TENANT, phone="0501234567", customer_name="أ", service_ids=[sid],
                     requested_time=REQUESTED_TIME, lat=1, lng=1))
    b = run(s.create(tenant=TENANT, phone="+966501234567", customer_name="ب", service_ids=[sid],
                     requested_time=REQUESTED_TIME, lat=1, lng=1))
    assert a.phone == b.phone == "+966501234567"


# ── review — accept/reject ──────────────────────────────────────────────────────────────────
def test_accepting_a_pending_request_works(svc):
    s, store, _ops = svc
    sid = run(_seed_service(store))
    req = run(s.create(tenant=TENANT, phone=PHONE, customer_name="أحمد", service_ids=[sid],
                       requested_time=REQUESTED_TIME, lat=1, lng=1))
    out = run(s.accept(TENANT, req.id, actor="owner1"))
    assert out.status == ACCEPTED
    assert out.decided_by == "owner1"
    assert out.decided_at > 0


def test_rejecting_a_pending_request_records_the_reason(svc):
    s, store, _ops = svc
    sid = run(_seed_service(store))
    req = run(s.create(tenant=TENANT, phone=PHONE, customer_name="أحمد", service_ids=[sid],
                       requested_time=REQUESTED_TIME, lat=1, lng=1))
    out = run(s.reject(TENANT, req.id, actor="owner1", reason="بعيد جداً"))
    assert out.status == REJECTED
    assert out.reject_reason == "بعيد جداً"


def test_a_request_cannot_be_reviewed_twice(svc):
    s, store, _ops = svc
    sid = run(_seed_service(store))
    req = run(s.create(tenant=TENANT, phone=PHONE, customer_name="أحمد", service_ids=[sid],
                       requested_time=REQUESTED_TIME, lat=1, lng=1))
    run(s.accept(TENANT, req.id, actor="owner1"))
    with pytest.raises(MobileRequestError):
        run(s.reject(TENANT, req.id, actor="owner1"))


def test_reviewing_an_unknown_request_is_refused_not_a_crash(svc):
    s, _store, _ops = svc
    with pytest.raises(MobileRequestError):
        run(s.accept(TENANT, "mreq_does_not_exist", actor="owner1"))


# ── assignment — optional, manual, never auto-routed ────────────────────────────────────────
def test_a_request_can_be_assigned_before_or_after_acceptance(svc):
    s, store, _ops = svc
    sid = run(_seed_service(store))
    req = run(s.create(tenant=TENANT, phone=PHONE, customer_name="أحمد", service_ids=[sid],
                       requested_time=REQUESTED_TIME, lat=1, lng=1))
    assigned = run(s.assign(TENANT, req.id, operator_id="op_1"))
    assert assigned.assigned_to == "op_1"
    run(s.accept(TENANT, req.id, actor="owner1"))
    reassigned = run(s.assign(TENANT, req.id, operator_id="op_2"))
    assert reassigned.assigned_to == "op_2"


def test_assignment_can_be_cleared(svc):
    s, store, _ops = svc
    sid = run(_seed_service(store))
    req = run(s.create(tenant=TENANT, phone=PHONE, customer_name="أحمد", service_ids=[sid],
                       requested_time=REQUESTED_TIME, lat=1, lng=1))
    run(s.assign(TENANT, req.id, operator_id="op_1"))
    cleared = run(s.assign(TENANT, req.id, operator_id=""))
    assert cleared.assigned_to == ""


def test_assigning_an_unknown_request_is_refused_not_a_crash(svc):
    s, _store, _ops = svc
    with pytest.raises(MobileRequestError):
        run(s.assign(TENANT, "mreq_does_not_exist", operator_id="op_1"))


def test_assigning_a_closed_request_is_refused(svc):
    s, store, _ops = svc
    sid = run(_seed_service(store))
    req = run(s.create(tenant=TENANT, phone=PHONE, customer_name="أحمد", service_ids=[sid],
                       requested_time=REQUESTED_TIME, lat=1, lng=1))
    run(s.reject(TENANT, req.id, actor="owner1"))
    with pytest.raises(MobileRequestError):
        run(s.assign(TENANT, req.id, operator_id="op_1"))


def test_listing_scoped_to_one_operator_only_shows_their_own(svc):
    s, store, _ops = svc
    sid = run(_seed_service(store))
    mine = run(s.create(tenant=TENANT, phone=PHONE, customer_name="أحمد", service_ids=[sid],
                        requested_time=REQUESTED_TIME, lat=1, lng=1))
    other = run(s.create(tenant=TENANT, phone="0509999999", customer_name="سارة",
                         service_ids=[sid], requested_time=REQUESTED_TIME, lat=1, lng=1))
    run(s.assign(TENANT, mine.id, operator_id="op_1"))
    run(s.assign(TENANT, other.id, operator_id="op_2"))
    rows = run(s.list(TENANT, assigned_to="op_1"))
    assert [r.id for r in rows] == [mine.id]


def test_completing_a_request_assigned_to_someone_else_is_refused(svc):
    s, store, _ops = svc
    sid = run(_seed_service(store))
    req = run(s.create(tenant=TENANT, phone=PHONE, customer_name="أحمد", service_ids=[sid],
                       requested_time=REQUESTED_TIME, lat=1, lng=1))
    run(s.assign(TENANT, req.id, operator_id="op_1"))
    run(s.accept(TENANT, req.id, actor="owner1"))
    with pytest.raises(MobileRequestError):
        run(s.complete(TENANT, req.id, expected_assignee="op_2"))


def test_completing_ones_own_assigned_request_succeeds(svc):
    s, store, _ops = svc
    sid = run(_seed_service(store))
    req = run(s.create(tenant=TENANT, phone=PHONE, customer_name="أحمد", service_ids=[sid],
                       requested_time=REQUESTED_TIME, lat=1, lng=1))
    run(s.assign(TENANT, req.id, operator_id="op_1"))
    run(s.accept(TENANT, req.id, actor="owner1"))
    out = run(s.complete(TENANT, req.id, expected_assignee="op_1"))
    assert out.status == COMPLETED


def test_a_manager_can_complete_regardless_of_assignment(svc):
    """`expected_assignee` empty (a manager's own route call never sets it) — no ownership
    check at all, same as before assignment existed."""
    s, store, _ops = svc
    sid = run(_seed_service(store))
    req = run(s.create(tenant=TENANT, phone=PHONE, customer_name="أحمد", service_ids=[sid],
                       requested_time=REQUESTED_TIME, lat=1, lng=1))
    run(s.assign(TENANT, req.id, operator_id="op_1"))
    run(s.accept(TENANT, req.id, actor="owner1"))
    out = run(s.complete(TENANT, req.id, expected_assignee=""))
    assert out.status == COMPLETED


def test_no_show_assigned_to_someone_else_is_refused(svc):
    s, store, _ops = svc
    sid = run(_seed_service(store))
    req = run(s.create(tenant=TENANT, phone=PHONE, customer_name="أحمد", service_ids=[sid],
                       requested_time=REQUESTED_TIME, lat=1, lng=1))
    run(s.assign(TENANT, req.id, operator_id="op_1"))
    run(s.accept(TENANT, req.id, actor="owner1"))
    with pytest.raises(MobileRequestError):
        run(s.no_show(TENANT, req.id, expected_assignee="op_2"))


def test_no_show_on_ones_own_assigned_request_succeeds(svc):
    s, store, _ops = svc
    sid = run(_seed_service(store))
    req = run(s.create(tenant=TENANT, phone=PHONE, customer_name="أحمد", service_ids=[sid],
                       requested_time=REQUESTED_TIME, lat=1, lng=1))
    run(s.assign(TENANT, req.id, operator_id="op_1"))
    run(s.accept(TENANT, req.id, actor="owner1"))
    out = run(s.no_show(TENANT, req.id, expected_assignee="op_1"))
    assert out.status == NO_SHOW


# ── completion — the bridge to a real visit ─────────────────────────────────────────────────
def test_completing_an_accepted_request_creates_a_real_visit(svc):
    s, store, _ops = svc
    sid = run(_seed_service(store))
    req = run(s.create(tenant=TENANT, phone=PHONE, customer_name="أحمد", service_ids=[sid],
                       requested_time=REQUESTED_TIME, lat=1, lng=1))
    run(s.accept(TENANT, req.id, actor="owner1"))
    out = run(s.complete(TENANT, req.id))
    assert out.status == COMPLETED
    assert out.visit_id, "a completed request must carry the real visit id it created"


class _FakeSeams:
    """Records what it was asked to seam — the test's substitute for reminders' own scheduling,
    proving only that `complete()` HANDS IT the right visit, not what reminders then does with it
    (that is reminders' own, already-tested, owner-configured-delay concern)."""

    def __init__(self) -> None:
        self.calls: list = []

    async def after_visit(self, result) -> None:
        self.calls.append(result)


def test_completing_runs_the_same_seams_every_other_visit_route_runs(svc):
    """The real gap this closes: record_visit() alone never told reminders/insights/search a
    thing happened — only seams.after_visit() does (core/seams.py::_emit_visit publishes
    `visit.recorded`, which is what reminders' own configured-delay rating-request scheduling
    reads from). Without this call, a mobile-service «تم» silently waited on the 5-minute reseam
    sweep (api/internal.py::_RESEAM_AFTER) to ever notice — correct eventually, never on the
    owner's own configured clock."""
    store = MemoryDataStore()
    ops = Operations(store=store, pii_salt="s" * 32)
    seams = _FakeSeams()
    s = MobileRequestService(store=store, operations=ops, default_cc=CC, seams=seams)
    sid = run(_seed_service(store))
    req = run(s.create(tenant=TENANT, phone=PHONE, customer_name="أحمد", service_ids=[sid],
                       requested_time=REQUESTED_TIME, lat=1, lng=1))
    run(s.accept(TENANT, req.id, actor="owner1"))
    out = run(s.complete(TENANT, req.id))

    assert len(seams.calls) == 1
    assert seams.calls[0].visit.id == out.visit_id


def test_a_request_completed_with_no_seams_peer_wired_still_completes(svc):
    """None-safe, same posture as every other optional peer in this codebase — a deployment or
    test that never wires `seams` (every pre-existing constructor call, including this file's own
    `svc` fixture) must keep working exactly as it always did."""
    s, store, _ops = svc
    sid = run(_seed_service(store))
    req = run(s.create(tenant=TENANT, phone=PHONE, customer_name="أحمد", service_ids=[sid],
                       requested_time=REQUESTED_TIME, lat=1, lng=1))
    run(s.accept(TENANT, req.id, actor="owner1"))
    out = run(s.complete(TENANT, req.id))
    assert out.status == COMPLETED
    assert out.visit_id


def test_completing_twice_does_not_double_record_the_visit(svc):
    """`record_visit()`'s own idempotency_key (mreq:{id}) is what protects this — a real,
    reused guarantee, not a second one built here."""
    s, store, _ops = svc
    sid = run(_seed_service(store))
    req = run(s.create(tenant=TENANT, phone=PHONE, customer_name="أحمد", service_ids=[sid],
                       requested_time=REQUESTED_TIME, lat=1, lng=1))
    run(s.accept(TENANT, req.id, actor="owner1"))
    first = run(s.complete(TENANT, req.id))
    # completing again should fail — it is no longer ACCEPTED, it is COMPLETED (terminal)
    with pytest.raises(MobileRequestError):
        run(s.complete(TENANT, req.id))
    assert first.visit_id


def test_completing_a_request_that_was_never_accepted_is_refused(svc):
    s, store, _ops = svc
    sid = run(_seed_service(store))
    req = run(s.create(tenant=TENANT, phone=PHONE, customer_name="أحمد", service_ids=[sid],
                       requested_time=REQUESTED_TIME, lat=1, lng=1))
    with pytest.raises(MobileRequestError):
        run(s.complete(TENANT, req.id))


def test_marking_no_show_never_creates_a_visit(svc):
    s, store, _ops = svc
    sid = run(_seed_service(store))
    req = run(s.create(tenant=TENANT, phone=PHONE, customer_name="أحمد", service_ids=[sid],
                       requested_time=REQUESTED_TIME, lat=1, lng=1))
    run(s.accept(TENANT, req.id, actor="owner1"))
    out = run(s.no_show(TENANT, req.id))
    assert out.status == NO_SHOW
    assert out.visit_id == ""


# ── no-show risk — a heads-up, never an enforcement ─────────────────────────────────────────
def test_a_new_customer_with_no_history_is_never_risky(svc):
    s, _store, _ops = svc
    risk = run(s.no_show_risk(TENANT, PHONE))
    assert risk.risky is False
    assert risk.considered == 0


def test_a_customer_who_always_shows_up_is_not_risky(svc):
    s, store, _ops = svc
    sid = run(_seed_service(store))
    for _ in range(5):
        req = run(s.create(tenant=TENANT, phone=PHONE, customer_name="أحمد", service_ids=[sid],
                           requested_time=REQUESTED_TIME, lat=1, lng=1))
        run(s.accept(TENANT, req.id, actor="owner1"))
        run(s.complete(TENANT, req.id))
    risk = run(s.no_show_risk(TENANT, PHONE))
    assert risk.risky is False
    assert risk.no_shows == 0


def test_a_customer_who_mostly_no_shows_is_flagged_risky(svc):
    """Same minimum-sample floor as bookings' own formula — a couple of no-shows must not flag
    someone forever, so this needs enough closed requests to actually clear it."""
    _default_s, store, ops = svc
    s = MobileRequestService(store=store, operations=ops, default_cc=CC,
                             risk_window=5, risk_threshold_percent=40)   # min_sample = 2
    sid = run(_seed_service(store))
    for _ in range(4):
        req = run(s.create(tenant=TENANT, phone=PHONE, customer_name="أحمد", service_ids=[sid],
                           requested_time=REQUESTED_TIME, lat=1, lng=1))
        run(s.accept(TENANT, req.id, actor="owner1"))
        run(s.no_show(TENANT, req.id))
    risk = run(s.no_show_risk(TENANT, PHONE))
    assert risk.risky is True
    assert risk.no_shows == 4


def test_pending_and_rejected_requests_never_count_toward_risk(svc):
    """Risk is about SHOWING UP once accepted, never about how many requests a customer sends or
    how many a shop happens to reject."""
    s, store, _ops = svc
    sid = run(_seed_service(store))
    for _ in range(6):
        req = run(s.create(tenant=TENANT, phone=PHONE, customer_name="أحمد", service_ids=[sid],
                           requested_time=REQUESTED_TIME, lat=1, lng=1))
        run(s.reject(TENANT, req.id, actor="owner1"))
    risk = run(s.no_show_risk(TENANT, PHONE))
    assert risk.considered == 0
    assert risk.risky is False


def test_risk_is_scoped_to_one_tenant_and_one_phone(svc):
    s, store, _ops = svc
    sid = run(_seed_service(store))
    other_tenant = "tnt_mobile_2"
    await_ = run
    for _ in range(4):
        req = await_(s.create(tenant=other_tenant, phone=PHONE, customer_name="أحمد",
                              service_ids=[sid], requested_time=REQUESTED_TIME, lat=1, lng=1))
        await_(s.accept(other_tenant, req.id, actor="owner2"))
        await_(s.no_show(other_tenant, req.id))
    risk = run(s.no_show_risk(TENANT, PHONE))
    assert risk.considered == 0, "another tenant's no-shows must never leak into this shop's view"


# ── listing ──────────────────────────────────────────────────────────────────────────────────
def test_list_filters_by_status(svc):
    s, store, _ops = svc
    sid = run(_seed_service(store))
    p1 = run(s.create(tenant=TENANT, phone=PHONE, customer_name="أ", service_ids=[sid],
                      requested_time=REQUESTED_TIME, lat=1, lng=1))
    p2 = run(s.create(tenant=TENANT, phone="0509999999", customer_name="ب", service_ids=[sid],
                      requested_time=REQUESTED_TIME, lat=1, lng=1))
    run(s.accept(TENANT, p2.id, actor="owner1"))

    pending = run(s.list(TENANT, status=PENDING))
    accepted = run(s.list(TENANT, status=ACCEPTED))
    assert [r.id for r in pending] == [p1.id]
    assert [r.id for r in accepted] == [p2.id]
