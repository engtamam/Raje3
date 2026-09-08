# =============================================================================
# bookings — Internal tier (service-to-service, X-Internal-Token)
# -----------------------------------------------------------------------------
# NOT user-facing. Guarded by a shared token compared in CONSTANT TIME
# (CWE-208: observable timing discrepancy). Never a user JWT.
# =============================================================================
from __future__ import annotations

import hmac

from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from app.config import Settings, get_settings
from app.core.erasure import TemplateErasure
from app.core import backup as _backup
from app.core.availability import (Busy, DayException, DurationNotConfigured, Schedule, Window,
                                   free_slots, nearest_slot)
from app.core.lock import SlotClaimBusy
from app.core.licence import LicenceError
from app.core.models import Booking
from app.core.operations import OperationError
from app.core.stores import ConcurrentEditError
from app.backup_manifest import BACKUP
from app.manifest import build_manifest

router = APIRouter(prefix="/internal", tags=["internal"])


def _now_iso() -> str:
    import datetime as _dt
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

_HEADER = "X-Internal-Token"


async def require_internal_token(
    x_internal_token: str | None = Header(default=None, alias=_HEADER),
    settings: Settings = Depends(get_settings),
) -> None:
    """Deny unless the caller presents the exact internal token (timing-safe)."""
    expected = settings.INTERNAL_SERVICE_TOKEN
    provided = x_internal_token or ""
    # hmac.compare_digest is constant-time and length-safe.
    if not hmac.compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="UNAUTHORIZED"
        )


@router.get("/health", dependencies=[Depends(require_internal_token)])
async def internal_health(settings: Settings = Depends(get_settings)) -> dict[str, str]:
    return {"status": "ok", "service": settings.SERVICE_NAME}


@router.get("/working-hours", dependencies=[Depends(require_internal_token)])
async def internal_working_hours(request: Request, tenant: str) -> dict:
    """The shop's own weekly policy — operations-service's read, so it can refuse a staff member's
    custom hours from ever exceeding the shop's own (`Operator.working_hours`'s write-time
    validation). The SAME derivation `GET /api/v1/bookings/working-hours` serves to the console
    (`c.booking_ops.working_hours`) — one source of truth, reached over two doors: a user token for
    the owner's own screen, this internal token for a peer service's validation.
    """
    c = request.app.state.container
    return {"weekly": await c.booking_ops.working_hours(tenant)}


@router.get("/manifest", dependencies=[Depends(require_internal_token)])
async def internal_manifest(
    request: Request, settings: Settings = Depends(get_settings)
) -> dict:
    container = getattr(request.app.state, "container", None)
    ports = container.describe() if container is not None else []
    manifest = build_manifest(settings, ports=ports)
    guard = getattr(request.app.state, "cwe_guard", None)
    if guard is not None:
        manifest["security"] = {"cwe_guard": guard.report()}
    return manifest


class EraseIn(BaseModel):
    tenant: str
    subject: str


@router.post("/privacy/erase", dependencies=[Depends(require_internal_token)])
async def erase_subject(request: Request, body: EraseIn) -> dict:
    """Erase a data subject. Called by compliance-service during a DSAR fan-out.

    Returns the ack: what was erased, and what was RETAINED with its legal basis. Idempotent — a
    DSAR retries, so erasing an already-erased subject must not fail. Wire this service into the
    fan-out by adding it to PRIVACY_TARGETS in compliance-service's values file; the
    safety:privacy-wiring gate fails if you implement this and forget.
    """
    c = request.app.state.container
    s = get_settings()
    eraser = TemplateErasure(store=c.datastore, pii_salt=s.PII_SALT,
                             max_scan=s.ERASURE_MAX_SCAN)
    return await eraser.erase(body.tenant, body.subject)


class BackupExportIn(BaseModel):
    # Empty tenant = the whole service; a value = just that customer's tenant-scoped rows.
    tenant: str = ""


class BackupImportIn(BaseModel):
    archive: dict
    # Off by default: a restore must not bulldoze rows written after the backup unless the operator
    # driving the restore says so.
    overwrite: bool = False
    # Empty = restore in place. A value REMAPS the restore into that tenant (restore-as-clone):
    # only rows that carry a tenant are reassigned; a global dataset is left alone.
    into_tenant: str = ""


def _sealer(settings: Settings):
    """The backup (seal, unseal) pair, or a 503 when no backup key is configured.

    Refused rather than defaulted: sealing with an empty key would write a plaintext-equivalent
    archive while every check reported it encrypted — the one outcome a backup must never have.
    """
    if not settings.BACKUP_KEK:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "BACKUP_KEK not configured — set this SHARED key (the SAME value backup-service holds) on this service, or its archives cannot be opened")
    return _backup.make_sealer(settings.BACKUP_KEK)


@router.post("/backup/export", dependencies=[Depends(require_internal_token)])
async def backup_export(request: Request, body: BackupExportIn,
                        settings: Settings = Depends(get_settings)) -> dict:
    """Produce a sealed, checksummed archive of this service's declared data.

    Called by backup-service, on a schedule, over the internal token. What this service holds is
    declared in app/backup_manifest.py; how it is read lives in core/backup.py. The orchestrator
    stores the archive and never sees the plaintext.
    """
    seal, _ = _sealer(settings)
    return await _backup.export(
        request.app.state.container.datastore, BACKUP,
        service=settings.SERVICE_NAME, version=settings.SERVICE_VERSION,
        taken_at=_now_iso(), seal=seal, tenant=body.tenant,
        scan_cap=settings.BACKUP_MAX_ROWS_PER_COLLECTION)


class BackupVerifyIn(BaseModel):
    archive: dict


@router.post("/backup/verify", dependencies=[Depends(require_internal_token)])
async def backup_verify(request: Request, body: BackupVerifyIn,
                        settings: Settings = Depends(get_settings)) -> dict:
    """Prove an archive restores, by test-restoring it into a throwaway namespace and comparing.

    backup-service calls this after it stores an archive (passing back the bytes it read FROM the
    store, so corruption at rest is caught too). This service is the only party that can unseal its
    own archive and knows its own schema, so verification lives here; the orchestrator only records
    the verdict. The throwaway namespace is torn down before this returns — nothing is left behind,
    and live data is never touched.
    """
    import secrets
    _, unseal = _sealer(settings)
    try:
        return await _backup.verify_restore(
            request.app.state.container.datastore, body.archive,
            unseal=unseal, token=secrets.token_hex(8))
    except _backup.BackupError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.post("/backup/import", dependencies=[Depends(require_internal_token)])
async def backup_import(request: Request, body: BackupImportIn,
                        settings: Settings = Depends(get_settings)) -> dict:
    """Restore an archive this service produced. Idempotent; leaves newer rows alone by default."""
    _, unseal = _sealer(settings)
    try:
        return await _backup.import_archive(
            request.app.state.container.datastore, body.archive,
            unseal=unseal, overwrite=body.overwrite, into_tenant=body.into_tenant)
    except _backup.BackupError as exc:
        # A bad archive is the caller's problem, not a 500: the checksum failed, the key did not
        # match, or a row had no identity. Say which, so an operator can act.
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


# ── availability: the query, and only the query (docs/خطة-تنفيذ-الحجوزات.md §2) ────────────
#
# NO STORE HERE YET, ON PURPOSE. Stage 2 is the derivation alone (app/core/availability.py) — pure,
# clock-free, store-free. This route is its first real caller: the schedule and the busy intervals
# arrive in the request body rather than being read from a booking store that does not exist until
# Stage 3. What changes when Stage 3 lands is WHERE `busy` comes from, never the derivation itself
# or this route's shape — the same interface a peer, the console, and eventually the portal all
# call (docs' §7, "a clean internal interface from day one").
class WindowIn(BaseModel):
    start_minute: int = Field(ge=0, le=24 * 60)
    end_minute: int = Field(ge=0, le=24 * 60)


class DayExceptionIn(BaseModel):
    closed: bool = True
    windows: list[WindowIn] = Field(default_factory=list)


class ScheduleIn(BaseModel):
    # "0"-"6" as strings — JSON object keys are always strings; Monday=0..Sunday=6, `date.weekday()`'s
    # own numbering, matching app/core/availability.py exactly rather than inventing a second one.
    weekly: dict[str, list[WindowIn]] = Field(default_factory=dict)
    exceptions: dict[str, DayExceptionIn] = Field(default_factory=dict)

    def to_schedule(self) -> Schedule:
        weekly = {int(k): tuple(Window(w.start_minute, w.end_minute) for w in v)
                  for k, v in self.weekly.items()}
        exceptions = {k: DayException(closed=v.closed,
                                      windows=tuple(Window(w.start_minute, w.end_minute)
                                                    for w in v.windows))
                     for k, v in self.exceptions.items()}
        return Schedule(weekly=weekly, exceptions=exceptions)


class BusyIn(BaseModel):
    starts_at: int
    ends_at: int


class AvailabilityCheckIn(BaseModel):
    schedule: ScheduleIn
    busy: list[BusyIn] = Field(default_factory=list)
    duration_minutes: int = Field(gt=0, le=720)
    window_start: int
    window_end: int


def _to_busy(rows: list[BusyIn]) -> list[Busy]:
    return [Busy(r.starts_at, r.ends_at) for r in rows]


@router.post("/availability/check", dependencies=[Depends(require_internal_token)])
async def availability_check(body: AvailabilityCheckIn) -> dict:
    """Every candidate start time in the window — the grid's own data source, and the "أقرب فتحة"
    button's underlying query. `duration_minutes` is a required, positive field at the API
    boundary already (`Field(gt=0)`), so `DurationNotConfigured` from the pure layer below is
    unreachable through this route by construction — the boundary enforces what the design doc
    calls "refuses rather than guesses" one layer earlier than the derivation itself has to.
    """
    slots = free_slots(body.schedule.to_schedule(), _to_busy(body.busy),
                       duration_minutes=body.duration_minutes,
                       window_start=body.window_start, window_end=body.window_end)
    return {"slots": [{"starts_at": s.starts_at, "ends_at": s.ends_at} for s in slots]}


class NearestSlotIn(BaseModel):
    schedule: ScheduleIn
    busy: list[BusyIn] = Field(default_factory=list)
    duration_minutes: int = Field(gt=0, le=720)
    after: int
    search_days: int = Field(default=14, ge=1, le=90)


@router.post("/availability/nearest", dependencies=[Depends(require_internal_token)])
async def availability_nearest(body: NearestSlotIn) -> dict:
    """The "أقرب فتحة" button (docs/وصف-تطبيق-الحجوزات.md §6.2): the first open candidate at or
    after `after`. `null` when nothing is free in `search_days` — the caller renders that as "لا
    فتحة قريبة", never as a silently empty grid."""
    found = nearest_slot(body.schedule.to_schedule(), _to_busy(body.busy),
                         duration_minutes=body.duration_minutes, after=body.after,
                         search_days=body.search_days)
    return {"slot": {"starts_at": found.starts_at, "ends_at": found.ends_at} if found else None}


# ── the REAL-store-backed counterpart to the pure query above, and REAL booking creation —
# whatsapp-assistant's own two questions (docs/خطة-تنفيذ-الحجوزات.md is silent on a chat peer
# because none existed until this feature; the shape below is the SAME `booking_ops` the console's
# own `/api/v1/bookings` route already calls — see that file's own `create_booking` — over the
# internal token instead of a user one, because whatsapp-assistant never holds a user token and
# must never be handed one). NEITHER ROUTE INVENTS AN OPERATOR OR A CUSTOMER: both ids arrive
# already resolved by the caller (whatsapp-assistant asks operations-service for both — see
# services/whatsapp-assistant/app/core/booking_assignment.py) and this service refuses exactly the
# way the console's own write path refuses one that turns out ineligible or unlicensed.
class InternalNearestRealSlotIn(BaseModel):
    tenant: str = Field(min_length=1, max_length=128)
    branch_id: str = Field(min_length=1, max_length=64)
    operator_id: str = Field(min_length=1, max_length=64)
    # EMPTY IS VALID — but only when `package_id` is set instead (packages feature, mutually
    # exclusive, same as the console's own POST /bookings body).
    service_ids: list[str] = Field(default_factory=list, max_length=20)
    package_id: str = Field(default="", max_length=64)
    after: int = Field(gt=0)
    search_days: int = Field(default=14, ge=1, le=90)
    # Booking-management-via-WhatsApp's own reschedule check (whatsapp-assistant's
    # propose_reschedule_booking): without this, a customer asking to move a booking to the SAME
    # time it already occupies — or any time still inside its own current window — reads as
    # "busy" against ITSELF, and the nearest-slot search jumps past to the next genuinely free
    # time instead. Same field/reasoning as the console's own `exclude_booking_id` on
    # GET /api/v1/bookings/nearest (app/api/v1/bookings.py) — the booking being moved is not a
    # conflict with itself. Empty (default) means "no exclusion", the pre-existing behaviour for
    # every other caller of this route (a brand-new booking has no id of its own yet to exclude).
    exclude_booking_id: str = Field(default="", max_length=64)


@router.post("/bookings/nearest-real-slot", dependencies=[Depends(require_internal_token)])
async def internal_nearest_real_slot(request: Request, body: InternalNearestRealSlotIn) -> dict:
    """Same question as `/availability/nearest` above, but fed from THIS service's own store — the
    operator's real existing bookings, the shop's real working hours, his own override if he has
    one (`BookingOperations.nearest_slot`/`_effective_schedule`) — rather than a schedule/busy list
    the caller has to assemble itself. Refuses (400) up front if `operator_id` cannot perform one
    of `service_ids`, the same "the write refuses, not only the suggestion" rule the create route
    below enforces — a probe against an ineligible operator must not return a false "free" slot.
    """
    c = request.app.state.container
    try:
        found = await c.booking_ops.nearest_slot(
            tenant=body.tenant, branch_id=body.branch_id, operator_id=body.operator_id,
            service_ids=body.service_ids, after=body.after, search_days=body.search_days,
            exclude_booking_id=body.exclude_booking_id, package_id=body.package_id)
    except OperationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return {"starts_at": found}


class InternalNearestAnyRealSlotIn(BaseModel):
    tenant: str = Field(min_length=1, max_length=128)
    branch_id: str = Field(min_length=1, max_length=64)
    # THE CALLER'S OWN ELIGIBLE POOL — same convention as the console's own GET .../nearest-any
    # (app/api/v1/bookings.py): this route does not itself decide who is eligible, only refuses
    # anyone in the list who turns out NOT to be (`_refuse_if_ineligible`, inside
    # `nearest_slots_any`) — never trusted blindly.
    operator_ids: list[str] = Field(min_length=1, max_length=64)
    service_ids: list[str] = Field(min_length=1, max_length=20)
    after: int = Field(gt=0)
    search_days: int = Field(default=14, ge=1, le=90)
    max_slots: int = Field(default=1, ge=1, le=20)
    exclude_booking_id: str = Field(default="", max_length=64)


@router.post("/bookings/nearest-any-real", dependencies=[Depends(require_internal_token)])
async def internal_nearest_any_real_slot(request: Request, body: InternalNearestAnyRealSlotIn) -> dict:
    """The «تلقائي» pick, for an internal caller (whatsapp-assistant's own booking_assignment.py,
    assignment-mode redesign phase 4) — the SAME merge + the shop's own algorithm the console's
    `nearest-any` route already applies (`BookingOperations.nearest_slots_any`, AssignmentSettingsStore),
    reached over the internal tier instead of a user JWT. One engine, three callers (console,
    WhatsApp Flow adapter once phase 5 exists, and this) — never a second, drifting copy of "who
    wins the slot" for the AI-led channel.
    """
    c = request.app.state.container
    window_end = body.after + body.search_days * 86400
    try:
        found = await c.booking_ops.nearest_slots_any(
            tenant=body.tenant, branch_id=body.branch_id, operator_ids=body.operator_ids,
            service_ids=body.service_ids, after=body.after, window_end=window_end,
            max_slots=body.max_slots, exclude_booking_id=body.exclude_booking_id,
            search_days=body.search_days)
    except OperationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return {"slots": [{"operator_id": s.operator_id, "starts_at": s.starts_at} for s in found]}


class InternalCreateBookingIn(BaseModel):
    tenant: str = Field(min_length=1, max_length=128)
    branch_id: str = Field(min_length=1, max_length=64)
    operator_id: str = Field(min_length=1, max_length=64)
    customer_id: str = Field(min_length=1, max_length=64)
    # EMPTY IS VALID — but only when `package_id` is set instead (packages feature).
    service_ids: list[str] = Field(default_factory=list, max_length=20)
    package_id: str = Field(default="", max_length=64)
    starts_at: int = Field(gt=0)
    note: str = Field(default="", max_length=500)
    idempotency_key: str = Field(default="", max_length=128)
    # WHATSAPP'S OWN VERSION OF THE CONSOLE'S "و+use my reward" CHECKBOX (CreateIn.intended_reward_id
    # in app/api/v1/bookings.py) — INTENT ONLY, never an immediate spend. `BookingOperations.create`
    # only ever STAMPS this on the row; the actual points spend happens exclusively inside
    # `attend()`, and `cancel()`/`no_show()` never touch it at all. This is the WHOLE reason a
    # WhatsApp-initiated redemption costs the shop nothing when a customer books, redeems, and then
    # never shows: nothing was ever spent to begin with. See
    # services/whatsapp-assistant/app/core/tools.py's `propose_booking` branch for the caller side.
    intended_reward_id: str | None = Field(default=None, max_length=128)
    # THE ATTRIBUTION FIX — whatsapp-assistant now sends its own actor constant
    # ("whatsapp-assistant", booking_assignment.py's `hold_and_confirm`/`hold_and_confirm_package`)
    # instead of leaving this at "". Anything else (blank, or a caller not yet updated) still lands
    # as "" — never guessed at — so an AI-made booking is honestly indistinguishable from a staff
    # one only for callers that have not been wired, not silently mislabelled either way.
    created_by: str = Field(default="", max_length=64)


@router.post("/bookings", dependencies=[Depends(require_internal_token)])
async def internal_create_booking(request: Request, body: InternalCreateBookingIn) -> dict:
    """THE one route that turns a customer's confirmed WhatsApp proposal into a real, persisted
    booking — `BookingOperations.create`, unchanged, over the internal token. Idempotent the same
    way the console's own create is (`idempotency_key`, checked first, before the licence check
    and before the lock): a redelivered `whatsapp.message` or a retried peer call must return the
    SAME booking, never a second one. `created_by` is forwarded from the caller (whatsapp-assistant
    stamps its own "whatsapp-assistant" actor constant here) so an AI-made booking can be told apart
    from a staff-made one downstream (reporting, attendance rate) — see `InternalCreateBookingIn`'s
    own note on why an unwired caller still lands at "" rather than a guessed value.
    """
    c = request.app.state.container
    try:
        booking = await c.booking_ops.create(
            tenant=body.tenant, branch_id=body.branch_id, operator_id=body.operator_id,
            customer_id=body.customer_id, service_ids=body.service_ids,
            package_id=body.package_id,
            starts_at=body.starts_at, note=body.note, idempotency_key=body.idempotency_key,
            intended_reward_id=body.intended_reward_id, created_by=body.created_by)
    except (SlotClaimBusy, ConcurrentEditError) as exc:
        # ConcurrentEditError is unreachable here in practice (a brand-new id has no stored row
        # to conflict with — see _claim_and_save's own note) but caught anyway for the same
        # defensive-consistency reason every write route in this file already does.
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except LicenceError as exc:
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, str(exc)) from exc
    except OperationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return booking.public()


# ── customer self-service, via whatsapp-assistant only (docs: booking-management-via-WhatsApp) ──
#
# Three routes let a WHATSAPP CUSTOMER view/cancel/reschedule HER OWN bookings, through the exact
# same proposal-then-real-button-confirm gate whatsapp-assistant already uses for a new booking —
# see that service's app/core/tools.py. What's genuinely NEW here (the staff routes in
# app/api/v1/bookings.py never needed it) is OWNERSHIP: a staff caller is authorized by BRANCH
# scope (_require_branch), which says nothing about who a given booking belongs to. A customer
# calling through the bot must be authorized by booking OWNERSHIP instead — `customer_id` arrives
# already resolved from her own WhatsApp number by whatsapp-assistant
# (booking_assignment.py::_resolve_customer_id), never typed free-form, but the route still
# verifies match on the STORED booking before doing anything: never trust the caller to have
# checked it. A mismatch and a nonexistent booking id return the IDENTICAL refusal, on purpose —
# distinguishing them would let a probing customer learn which random ids are real (an enumeration
# oracle), the same reasoning the product already applies elsewhere.
def _refusal(reason: str) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, reason)


async def _own_booking(request: Request, tenant: str, booking_id: str, customer_id: str,
                       branch_id: str = ""):
    """`branch_id`, WHEN THE CALLER PASSES ONE, IS PART OF OWNERSHIP TOO — not a second, looser
    check. A per_branch shop's WhatsApp number IS a branch (sending_identity.py on the caller's
    side), and a customer texting branch B's number must not be able to view/cancel/reschedule a
    booking that belongs to branch A just because both bookings are hers. Refused with the exact
    same sentence as "not hers at all" — same enumeration-oracle reasoning as the ownership check
    above: a customer must not learn "this id is real, just not at this branch" any more than she
    should learn "this id belongs to someone else"."""
    c = request.app.state.container
    booking = await c.bookings.get(tenant, booking_id)
    if (booking is None or booking.customer_id != customer_id
            or (branch_id and booking.branch_id != branch_id)):
        raise _refusal("الحجز غير موجود أو لا يخصّك")
    return booking


class InternalForCustomerIn(BaseModel):
    tenant: str = Field(min_length=1, max_length=128)
    customer_id: str = Field(min_length=1, max_length=64)
    # Empty (the default) means "every branch" — a central shop with no branch fixed on this
    # conversation yet must still see her whole history. Non-empty narrows to that one branch's
    # bookings only — see `_own_booking`'s own note on why this is ownership, not a filter.
    branch_id: str = Field(default="", max_length=64)


@router.post("/bookings/for-customer", dependencies=[Depends(require_internal_token)])
async def internal_bookings_for_customer(request: Request, body: InternalForCustomerIn) -> dict:
    """The bot's `list_my_bookings` — the SAME derivation the console's own customer page uses
    (`bookings_for_customer` in app/core/operations.py), over the internal token instead of a
    staff one. `customer_id` is caller-supplied but not caller-trusted with anyone else's rows:
    it is the resolved-from-phone-number id whatsapp-assistant already established, and the
    result is that customer's own history and nothing else — there is no parameter here that
    could name a different customer's data."""
    c = request.app.state.container
    rows = await c.booking_ops.bookings_for_customer(body.tenant, body.customer_id)
    if body.branch_id:
        rows = [b for b in rows if b.branch_id == body.branch_id]
    return {"bookings": [b.public() for b in rows]}


class InternalForSubjectIn(BaseModel):
    tenant: str = Field(min_length=1, max_length=128)
    subject_ref: str = Field(min_length=1, max_length=128)


@router.post("/bookings/for-subject", dependencies=[Depends(require_internal_token)])
async def internal_bookings_for_subject(request: Request, body: InternalForSubjectIn) -> dict:
    """SAME READ as `/bookings/for-customer` above, keyed by the pseudonym instead of the real
    `customer_id` — for a caller (an internal case-investigation tool, e.g.) that only ever
    resolves a phone number to `subject_ref` (operations' own read-only
    `/internal/operations/customer-by-phone`) and must never be handed — or made to mint, since
    the only route that hands out a real `customer_id` writes on every call — a real id just to
    look a history up. Read-only end to end: nothing on this path ever creates or touches a row."""
    c = request.app.state.container
    rows = await c.booking_ops.bookings_for_subject(body.tenant, body.subject_ref)
    return {"bookings": [b.public() for b in rows]}


class InternalByActorIn(BaseModel):
    tenant: str = Field(min_length=1, max_length=128)
    # REQUIRED, NEVER A WILDCARD — this route answers "bookings made by THIS actor", not "all
    # bookings this tenant has". A caller building a cross-service report (whatsapp-assistant's own
    # `upsell_report.py`, which named this exact gap as a documented follow-up) always knows its own
    # actor constant ("whatsapp-assistant"); there is no legitimate caller of this route that does
    # not, so an empty value is refused rather than silently read as "everyone".
    created_by: str = Field(min_length=1, max_length=64)
    branch_id: str = Field(default="", max_length=64)
    since: int | None = Field(default=None, ge=0)
    until: int | None = Field(default=None, ge=0)
    limit: int = Field(default=2000, ge=1, le=2000)


def _actor_public(b: Booking) -> dict:
    """A NARROWER PROJECTION than `Booking.public()` on purpose — this route serves a
    cross-service revenue report (whatsapp-assistant's own upsell/pricing stats), not a screen the
    booking's own customer or staff are looking at, and `.public()` carries `customer_id`, `note`,
    `idempotency_key` and other fields that report has no business seeing. Only what a price-and-
    volume aggregation actually needs."""
    return {
        "id": b.id, "branch_id": b.branch_id, "operator_id": b.operator_id,
        "service_ids": list(b.service_ids), "package_id": b.package_id,
        "starts_at": b.starts_at, "status": b.status,
        "price_override_minor": b.price_override_minor,
        "created": b.created, "created_by": b.created_by,
    }


@router.post("/bookings/by-actor", dependencies=[Depends(require_internal_token)])
async def internal_bookings_by_actor(request: Request, body: InternalByActorIn) -> dict:
    """Every booking a given ACTOR made — bookings-service's answer to the gap `upsell_report.py`
    (whatsapp-assistant) documented explicitly: no route existed to list bookings by who made them,
    only by whose customer they belong to (`for-customer`/`for-subject` above). `created_by` is
    required, never inferred or wildcarded (see `InternalByActorIn`'s own note) — this is
    "whatsapp-assistant's own bookings", never "this tenant's bookings". `since`/`until` (unix
    seconds, against `created` — when the AI made the booking, not the appointment time it booked)
    bound a real report window rather than an unbounded scan; `truncated` says honestly when the
    real cap (`BookingStore.by_actor`) was hit."""
    c = request.app.state.container
    rows, truncated = await c.booking_ops.bookings_by_actor(
        body.tenant, body.created_by, branch_id=body.branch_id, since=body.since,
        until=body.until, limit=body.limit)
    return {"bookings": [_actor_public(b) for b in rows], "truncated": truncated}


class InternalCancelIn(BaseModel):
    tenant: str = Field(min_length=1, max_length=128)
    customer_id: str = Field(min_length=1, max_length=64)
    reason: str = Field(default="", max_length=300)
    branch_id: str = Field(default="", max_length=64)


@router.post("/bookings/{booking_id}/cancel", dependencies=[Depends(require_internal_token)])
async def internal_cancel_booking(request: Request, booking_id: str, body: InternalCancelIn) -> dict:
    await _own_booking(request, body.tenant, booking_id, body.customer_id, body.branch_id)
    c = request.app.state.container
    try:
        booking = await c.booking_ops.cancel(body.tenant, booking_id, body.reason)
    except ConcurrentEditError as exc:
        # SAME shape as every route in app/api/v1/bookings.py's own `_handle` — a genuine, if
        # narrow, race (two near-simultaneous confirms on the same proposal, or a redelivered
        # webhook racing the first attempt) must read as a real, retryable conflict, not a raw 500.
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except OperationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return booking.public()


class InternalRescheduleIn(BaseModel):
    tenant: str = Field(min_length=1, max_length=128)
    customer_id: str = Field(min_length=1, max_length=64)
    starts_at: int = Field(gt=0)
    operator_id: str = Field(default="", max_length=64)
    branch_id: str = Field(default="", max_length=64)


@router.post("/bookings/{booking_id}/reschedule", dependencies=[Depends(require_internal_token)])
async def internal_reschedule_booking(request: Request, booking_id: str,
                                      body: InternalRescheduleIn) -> dict:
    await _own_booking(request, body.tenant, booking_id, body.customer_id, body.branch_id)
    c = request.app.state.container
    try:
        booking = await c.booking_ops.reschedule(
            tenant=body.tenant, booking_id=booking_id, starts_at=body.starts_at,
            operator_id=body.operator_id)
    except (SlotClaimBusy, ConcurrentEditError) as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except LicenceError as exc:
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, str(exc)) from exc
    except OperationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return booking.public()
