"""The booking surface (docs/خطة-تنفيذ-الحجوزات.md §6, Stage 6) — the grid's own read, and every
write `app/core/operations.py::BookingOperations` exposes.

TWO CAPABILITIES, NOT ONE, MATCHING `app/core/licence.py`'s OWN READ/WRITE ASYMMETRY. `bookings.read`
opens the grid; `bookings.write` is everything that grows or changes a commitment. A shop whose
subscription lapsed still keeps `bookings.write` at the RBAC layer (a role is not a subscription) —
`BookingOperations` itself is what refuses the growing half, at the licence layer, one level below
this one. The two must not be confused: RBAC answers "is this person allowed to try", licence
answers "has the shop paid for what they are trying".

BRANCH SCOPE IS ENFORCED HERE, NOT TRUSTED FROM THE BODY — same defect family loyalty's own
redemption path closed (`app/adapters/branch_scope.py`'s own docstring): a caller-supplied branch
id, unchecked, is a write filed for a branch nobody there expects.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.adapters.branch_scope import DENIED, visible
from app.api.auth import Principal, require_user
from app.api.authz import require_capability
from app.api.ratelimit import rate_limit
from app.core.lock import SlotClaimBusy
from app.core.licence import LicenceError
from app.core.models import Booking
from app.core.operations import OperationError
from app.core.stores import ConcurrentEditError, day_bucket

router = APIRouter(prefix="/api/v1/bookings", tags=["bookings"])

_READ = require_capability("bookings.read")
_WRITE = require_capability("bookings.write")
# A THIRD CAPABILITY, NOT bookings.write ("مو اي موظف يقدر يعدل لازم صلاحيات
# معينة") — working hours are a POLICY every branch and every operator's own schedule reads from,
# the same distance `operations.manage` keeps from `operations.record`: an operator who may take
# a booking must not thereby be able to redefine when the shop is open. Owner and manager hold it
# by default (deploy/seed/roles.json), supervisor and operator do not — same split as
# operations.manage/operations.record already draws for the catalogue and the team.
_MANAGE = require_capability("bookings.manage")


def _refuse(reason: str, status_code: int = status.HTTP_400_BAD_REQUEST) -> JSONResponse:
    """Same shape as every other service's own `_refuse` (operator.py, loyalty's own) — a
    sentence WE wrote, never anything the caller sent back verbatim."""
    return JSONResponse({"error": "BAD_REQUEST", "reason": reason}, status_code=status_code)


def _tenant(principal: Principal) -> str:
    # NEVER from the body — the tenant comes off the token and only off the token.
    t = getattr(principal, "tenant", "") or ""
    if not t:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "no establishment on this token")
    return t


async def _require_branch(request: Request, principal: Principal, branch_id: str) -> None:
    """Refuses unless this caller's own scope includes `branch_id`. Fails closed on an unreadable
    scope, exactly as loyalty's redeem path does."""
    if not branch_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "الفرع مطلوب")
    resolver = getattr(request.app.state.container, "branch_scope", None)
    if resolver is None:
        return   # not wired (local/dev) — same lenient default loyalty's own path takes
    scope = await resolver.scope(_tenant(principal), principal.subject)
    if scope in DENIED:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "تعذّر التحقق من فرعك الآن. أعد المحاولة بعد قليل.")
    if not visible(scope, branch_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "هذا الفرع خارج صلاحيتك")


def _public(b: Booking) -> dict:
    return b.public()


def _handle(exc: Exception) -> JSONResponse:
    if isinstance(exc, SlotClaimBusy):
        return _refuse(str(exc), status.HTTP_409_CONFLICT)
    if isinstance(exc, ConcurrentEditError):
        return _refuse(str(exc), status.HTTP_409_CONFLICT)
    if isinstance(exc, LicenceError):
        return _refuse(str(exc), status.HTTP_402_PAYMENT_REQUIRED)
    if isinstance(exc, OperationError):
        return _refuse(str(exc))
    raise exc


# ── the grid's own read ──────────────────────────────────────────────────────────────────────
@router.get("", dependencies=[Depends(_READ), Depends(rate_limit)])
async def list_bookings(request: Request, branch_id: str, date: str,
                        principal: Principal = Depends(require_user)) -> dict:
    """Every booking for one branch, one business day (§2's `booking_slots` index — never a scan
    of every booking this establishment has ever made). `date` is `YYYY-MM-DD`, the shop's own
    business day (app/core/riyadh.py), matching exactly what `day_bucket()` produces."""
    tenant = _tenant(principal)
    await _require_branch(request, principal, branch_id)
    c = request.app.state.container
    rows = await c.bookings.slots_between(tenant, branch_id, start_bucket=date, end_bucket=date)
    return {"bookings": [_public(b) for b in rows]}


@router.get("/counts", dependencies=[Depends(_READ), Depends(rate_limit)])
async def booking_counts(request: Request, branch_id: str, start: str, end: str,
                         principal: Principal = Depends(require_user)) -> dict:
    """The month/year view's own read (docs/خطة-تصميم-تقويم-الحجوزات.md §1) — how many bookings
    land on each day of the range, NEVER the bookings themselves: no name, no phone, nothing
    `Booking.public()` would carry. `start`/`end` are `YYYY-MM-DD`, same business-day buckets
    `day_bucket()` produces. Deliberately no row cap here — see `counts_between`'s own docstring."""
    tenant = _tenant(principal)
    await _require_branch(request, principal, branch_id)
    c = request.app.state.container
    counts = await c.bookings.counts_between(
        tenant, branch_id, start_bucket=start, end_bucket=end)
    return {"counts": counts}


@router.get("/risk", dependencies=[Depends(_READ), Depends(rate_limit)])
async def no_show_risk(request: Request, customer_id: str,
                       principal: Principal = Depends(require_user)) -> dict:
    """A number beside her name at the moment the dialog opens, not a verdict (§2.6) — how many
    of her last five CLOSED appointments she did not attend. Never refuses, never blocks; the
    staff member reads it and decides."""
    tenant = _tenant(principal)
    c = request.app.state.container
    return await c.booking_ops.no_show_risk(tenant, customer_id)


@router.get("/for-customer", dependencies=[Depends(_READ), Depends(rate_limit)])
async def bookings_for_customer(request: Request, customer_id: str,
                                principal: Principal = Depends(require_user)) -> dict:
    """His own booking history — the customer page's own section (docs/وصف-تطبيق-الحجوزات.md
    §3: "مواعيده القادمة والسابقة، ونسبة حضوره"). Not branch-scoped: a customer's OWN history is
    his across every branch he was ever served at, the same reasoning `no_show_risk` above
    already applies."""
    tenant = _tenant(principal)
    c = request.app.state.container
    rows = await c.booking_ops.bookings_for_customer(tenant, customer_id)
    return {"bookings": [_public(b) for b in rows]}


@router.get("/working-hours", dependencies=[Depends(_READ), Depends(rate_limit)])
async def read_working_hours(request: Request,
                             principal: Principal = Depends(require_user)) -> dict:
    """The shop's own weekly policy — every branch shares it. Anyone who can
    read the grid may read this; only `bookings.manage` may change it (see `_MANAGE` above)."""
    tenant = _tenant(principal)
    c = request.app.state.container
    return {"weekly": await c.booking_ops.working_hours(tenant)}


class DayHoursIn(BaseModel):
    closed: bool = False
    start_minute: int = Field(default=0, ge=0, le=24 * 60)
    end_minute: int = Field(default=0, ge=0, le=24 * 60)


class WorkingHoursIn(BaseModel):
    # KEYED BY STRING, NOT INT — JSON object keys are always strings on the wire; Pydantic would
    # coerce int keys back on the way in, but the console sends "0".."6" and this names that
    # explicitly rather than relying on coercion nobody reading this route would expect.
    weekly: dict[str, DayHoursIn]


@router.patch("/working-hours", dependencies=[Depends(_MANAGE), Depends(rate_limit)])
async def write_working_hours(request: Request, body: WorkingHoursIn,
                              principal: Principal = Depends(require_user)) -> dict:
    tenant = _tenant(principal)
    c = request.app.state.container
    try:
        weekly = await c.booking_ops.set_working_hours(
            tenant, {k: v.model_dump() for k, v in body.weekly.items()})
    except OperationError as exc:
        return _handle(exc)
    return {"weekly": weekly}


@router.get("/nearest", dependencies=[Depends(_READ), Depends(rate_limit)])
async def nearest_slot(request: Request, branch_id: str, operator_id: str,
                       service_ids: str, after: int, exclude_booking_id: str = "",
                       principal: Principal = Depends(require_user)) -> dict:
    """The "أقرب فتحة" button (§6.2) — `service_ids` is a comma-separated list, since query
    params carry no arrays cleanly. `null` when nothing is free in the search window.

    `exclude_booking_id` IS FOR RESCHEDULING ONE THAT ALREADY EXISTS. Without it, an edit of a
    booking asks "when is this operator free?" while that operator's own diary still contains the
    very appointment being moved — so its current hour reads as taken and, for a long service on a
    busy day, the answer comes back "لا فتحة فاضية هذا اليوم" for a booking that is sitting in a
    perfectly good slot right now. The one booking being edited is not a conflict with itself.
    """
    tenant = _tenant(principal)
    await _require_branch(request, principal, branch_id)
    c = request.app.state.container
    ids = [s for s in service_ids.split(",") if s]
    try:
        found = await c.booking_ops.nearest_slot(
            tenant=tenant, branch_id=branch_id, operator_id=operator_id,
            service_ids=ids, after=after, exclude_booking_id=exclude_booking_id)
    except OperationError as exc:
        return _handle(exc)
    return {"starts_at": found}


@router.get("/nearest-any", dependencies=[Depends(_READ), Depends(rate_limit)])
async def nearest_slots_any(request: Request, branch_id: str, operator_ids: str,
                            service_ids: str, after: int, window_end: int,
                            max_slots: int = 6, exclude_booking_id: str = "",
                            principal: Principal = Depends(require_user)) -> dict:
    """The «أي متاح» merge (app/core/assignment.py, Phase 0) — ONE call instead of the console's
    old sequential per-candidate loop against `/nearest` above. `operator_ids` is the caller's own
    eligible set (comma-separated, same convention `service_ids` already uses on this route) —
    each is still refused individually if ineligible, same as `/nearest` always has been; this
    endpoint does not itself decide who is eligible."""
    tenant = _tenant(principal)
    await _require_branch(request, principal, branch_id)
    c = request.app.state.container
    op_ids = [s for s in operator_ids.split(",") if s]
    svc_ids = [s for s in service_ids.split(",") if s]
    try:
        found = await c.booking_ops.nearest_slots_any(
            tenant=tenant, branch_id=branch_id, operator_ids=op_ids, service_ids=svc_ids,
            after=after, window_end=window_end, max_slots=max_slots,
            exclude_booking_id=exclude_booking_id)
    except OperationError as exc:
        return _handle(exc)
    return {"slots": [{"operator_id": s.operator_id, "starts_at": s.starts_at} for s in found]}


class CreateIn(BaseModel):
    branch_id: str = Field(min_length=1, max_length=64)
    operator_id: str = Field(min_length=1, max_length=64)
    customer_id: str = Field(min_length=1, max_length=64)
    # EMPTY IS VALID — but only when `package_id` is set instead. Bookings' own `create()` refuses
    # the "both" and "neither" cases with a clear Arabic reason; pydantic only bounds the shape.
    service_ids: list[str] = Field(default_factory=list, max_length=20)
    # MUTUALLY EXCLUSIVE WITH `service_ids` — a booking is one or the other (packages feature).
    package_id: str = Field(default="", max_length=64)
    starts_at: int = Field(gt=0)
    note: str = Field(default="", max_length=500)
    idempotency_key: str = Field(default="", max_length=128)
    series_id: str | None = None
    series_seq: int | None = None
    # "بدون عربون بعربون او مدفوع" — one of PAYMENT_STATES.
    payment_status: str = Field(default="none", pattern=r"^(none|deposit|paid)$")
    # Required by operations.py when payment_status is "deposit"; ignored otherwise.
    deposit_amount_minor: int | None = Field(default=None, ge=0)
    # THIS BOOKING ONLY — never the catalogue. See models.py's own note on the field.
    price_override_minor: int | None = Field(default=None, ge=0)
    # INTENT ONLY — never spent here. See models.py's own note on the field and RewardGateway's
    # in core/operations.py for why the actual redeem waits for attend().
    intended_reward_id: str | None = Field(default=None, max_length=128)


@router.post("", dependencies=[Depends(_WRITE), Depends(rate_limit)])
async def create_booking(request: Request, body: CreateIn,
                         principal: Principal = Depends(require_user)) -> dict:
    tenant = _tenant(principal)
    await _require_branch(request, principal, body.branch_id)
    c = request.app.state.container
    try:
        booking = await c.booking_ops.create(
            tenant=tenant, branch_id=body.branch_id, operator_id=body.operator_id,
            customer_id=body.customer_id, service_ids=body.service_ids,
            package_id=body.package_id,
            starts_at=body.starts_at, note=body.note, idempotency_key=body.idempotency_key,
            created_by=principal.subject, series_id=body.series_id, series_seq=body.series_seq,
            payment_status=body.payment_status, deposit_amount_minor=body.deposit_amount_minor,
            price_override_minor=body.price_override_minor,
            intended_reward_id=body.intended_reward_id)
    except (OperationError, SlotClaimBusy, LicenceError, ConcurrentEditError) as exc:
        # ConcurrentEditError is unreachable here in practice (a brand-new id has no stored row
        # to conflict with — see _claim_and_save's own note) but caught anyway for the same
        # defensive-consistency reason every other write route in this file already does.
        return _handle(exc)
    return _public(booking)


async def _get_own(request: Request, principal: Principal, booking_id: str) -> Booking:
    """Fetches the booking and validates the CALLER'S scope against ITS branch — the id in the
    URL, never a branch the client could name in the body."""
    tenant = _tenant(principal)
    c = request.app.state.container
    booking = await c.bookings.get(tenant, booking_id)
    if booking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "الحجز غير موجود")
    await _require_branch(request, principal, booking.branch_id)
    return booking


class RescheduleIn(BaseModel):
    starts_at: int = Field(gt=0)
    operator_id: str = Field(default="", max_length=64)


@router.patch("/{booking_id}/reschedule", dependencies=[Depends(_WRITE), Depends(rate_limit)])
async def reschedule_booking(request: Request, booking_id: str, body: RescheduleIn,
                             principal: Principal = Depends(require_user)) -> dict:
    tenant = _tenant(principal)
    await _get_own(request, principal, booking_id)
    c = request.app.state.container
    try:
        booking = await c.booking_ops.reschedule(
            tenant=tenant, booking_id=booking_id, starts_at=body.starts_at,
            operator_id=body.operator_id)
    except (OperationError, SlotClaimBusy, LicenceError, ConcurrentEditError) as exc:
        return _handle(exc)
    return _public(booking)


class ServicesIn(BaseModel):
    service_ids: list[str] = Field(min_length=1, max_length=20)


@router.patch("/{booking_id}/services", dependencies=[Depends(_WRITE), Depends(rate_limit)])
async def edit_booking_services(request: Request, booking_id: str, body: ServicesIn,
                                principal: Principal = Depends(require_user)) -> dict:
    tenant = _tenant(principal)
    await _get_own(request, principal, booking_id)
    c = request.app.state.container
    try:
        booking = await c.booking_ops.edit_services(tenant, booking_id, body.service_ids)
    except (OperationError, SlotClaimBusy, LicenceError, ConcurrentEditError) as exc:
        return _handle(exc)
    return _public(booking)


class NoteIn(BaseModel):
    note: str = Field(default="", max_length=500)


@router.patch("/{booking_id}/note", dependencies=[Depends(_WRITE), Depends(rate_limit)])
async def edit_booking_note(request: Request, booking_id: str, body: NoteIn,
                            principal: Principal = Depends(require_user)) -> dict:
    tenant = _tenant(principal)
    await _get_own(request, principal, booking_id)
    c = request.app.state.container
    try:
        booking = await c.booking_ops.edit_note(tenant, booking_id, body.note)
    except (OperationError, ConcurrentEditError) as exc:
        return _handle(exc)
    return _public(booking)


class PaymentIn(BaseModel):
    payment_status: str = Field(pattern=r"^(none|deposit|paid)$")
    deposit_amount_minor: int | None = Field(default=None, ge=0)


@router.patch("/{booking_id}/payment", dependencies=[Depends(_WRITE), Depends(rate_limit)])
async def edit_booking_payment(request: Request, booking_id: str, body: PaymentIn,
                               principal: Principal = Depends(require_user)) -> dict:
    tenant = _tenant(principal)
    await _get_own(request, principal, booking_id)
    c = request.app.state.container
    try:
        booking = await c.booking_ops.set_payment_status(
            tenant, booking_id, body.payment_status, deposit_amount_minor=body.deposit_amount_minor)
    except (OperationError, ConcurrentEditError) as exc:
        return _handle(exc)
    return _public(booking)


class RewardIn(BaseModel):
    reward_id: str | None = Field(default=None, max_length=128)


@router.patch("/{booking_id}/reward", dependencies=[Depends(_WRITE), Depends(rate_limit)])
async def edit_booking_reward(request: Request, booking_id: str, body: RewardIn,
                              principal: Principal = Depends(require_user)) -> dict:
    tenant = _tenant(principal)
    await _get_own(request, principal, booking_id)
    c = request.app.state.container
    try:
        booking = await c.booking_ops.set_intended_reward(tenant, booking_id, body.reward_id)
    except (OperationError, ConcurrentEditError) as exc:
        return _handle(exc)
    return _public(booking)


class ReasonIn(BaseModel):
    reason: str = Field(default="", max_length=300)


@router.patch("/{booking_id}/cancel", dependencies=[Depends(_WRITE), Depends(rate_limit)])
async def cancel_booking(request: Request, booking_id: str, body: ReasonIn,
                         principal: Principal = Depends(require_user)) -> dict:
    tenant = _tenant(principal)
    await _get_own(request, principal, booking_id)
    c = request.app.state.container
    try:
        booking = await c.booking_ops.cancel(tenant, booking_id, body.reason)
    except (OperationError, ConcurrentEditError) as exc:
        return _handle(exc)
    return _public(booking)


class AttendIn(BaseModel):
    occurred_at: int = Field(default=0, ge=0)


@router.patch("/{booking_id}/attend", dependencies=[Depends(_WRITE), Depends(rate_limit)])
async def attend_booking(request: Request, booking_id: str, body: AttendIn,
                         principal: Principal = Depends(require_user)) -> dict:
    """ALLOWED even on a lapsed subscription — see `app/core/licence.py`'s own line: closing an
    existing booking's status is never the growing half."""
    tenant = _tenant(principal)
    await _get_own(request, principal, booking_id)
    c = request.app.state.container
    try:
        booking = await c.booking_ops.attend(tenant, booking_id, body.occurred_at)
    except (OperationError, ConcurrentEditError) as exc:
        return _handle(exc)
    return _public(booking)


@router.patch("/{booking_id}/no-show", dependencies=[Depends(_WRITE), Depends(rate_limit)])
async def no_show_booking(request: Request, booking_id: str, body: ReasonIn,
                          principal: Principal = Depends(require_user)) -> dict:
    tenant = _tenant(principal)
    await _get_own(request, principal, booking_id)
    c = request.app.state.container
    try:
        booking = await c.booking_ops.no_show(tenant, booking_id, body.reason)
    except (OperationError, ConcurrentEditError) as exc:
        return _handle(exc)
    return _public(booking)
