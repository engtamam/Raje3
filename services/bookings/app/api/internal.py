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
