"""The shop's own admin surface (spec §7) — everything an owner does to run this app.

TIER "user", CAPABILITY "coworking.manage" — same shape as every other per-shop admin route in
this fleet (`campaigns.manage`, `bookings.manage`, …): a token belonging to a person at THIS shop,
never a platform operator. `principal.tenant` is what scopes every read and write here to that
one shop; nothing in this file ever accepts a tenant from the request body.

BRANCH SCOPE (owner decision, 2026-09-27): a resource belongs to one physical branch, and a manager
scoped to one branch must not create, edit or read resources/bookings at another — same discipline
`app/adapters/branch_scope.py`'s own module doc describes, reused rather than reinvented.
UNASSIGNED (`branch_id == ""`) IS ALWAYS VISIBLE TO EVERYONE, the same "a row with no branch is
kept for everyone" rule every other branch-scoped domain in this fleet already holds — a resource
nobody has assigned to a branch yet is not a resource hidden from its own manager.

JOIN REQUESTS ARE DELIBERATELY EXCLUDED — see `core/joins.py`'s own module doc: that gate is
shop-wide by design (a freelancer approved once may book any resource at that shop), and
branch-scoping it would be a real behaviour change nobody asked for, not a gap this file closes.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field, model_validator
from starlette.responses import JSONResponse

from app.adapters.branch_scope import DENIED, visible
from app.api.auth import Principal, require_user
from app.api.authz import require_capability_scoped
from app.api.ratelimit import rate_limit
from app.config import get_settings
from app.core.bookings import BookingRefused
from app.core.joins import JoinError
from app.core.models import BOOKINGS
from app.core.phone import canonical_phone
from app.core.resources import ResourceError

router = APIRouter(prefix="/api/v1/coworking", tags=["coworking-admin"])

_MANAGE = require_capability_scoped("coworking.manage")


def _tenant(principal: Principal) -> str:
    return principal.tenant or ""


def _phone(raw: str) -> str:
    # SAME NORMALIZER `public.py` USES — an owner typing a number by hand ("0501234567") must
    # resolve to the exact same key a freelancer's own booking attempt does ("+966501234567"), or
    # `block()` silently blocks a row nobody ever books under while the real identity stays free.
    return canonical_phone(raw, default_cc=get_settings().COWORKING_PHONE_DEFAULT_CC)


def _refuse(reason: str, *, status_code: int = status.HTTP_400_BAD_REQUEST) -> JSONResponse:
    return JSONResponse({"error": "BAD_REQUEST", "reason": reason}, status_code=status_code)


async def _scope(container, principal: Principal) -> Any:
    """The branches this caller may act on — `""` for unscoped (everything), a `frozenset`/single
    id for narrowed, or a DENIED sentinel when we could not ask or the person was stopped. Not
    wired anywhere (`container.branch_scope` absent, or its own URL unconfigured) reads the same
    as unscoped — a from-scratch install with no operations peer has no branches to isolate."""
    resolver = getattr(container, "branch_scope", None)
    if resolver is None:
        return ""
    return await resolver.scope(_tenant(principal), principal.subject or "")


def _branch_allowed(scope: Any, branch_id: str) -> bool:
    """UNASSIGNED IS ALWAYS ALLOWED — see this module's own docstring. Every OTHER branch_id asks
    the adapter's own `visible()`."""
    if not branch_id:
        return True
    return visible(scope, branch_id)


async def _require_branch(container, principal: Principal, branch_id: str) -> JSONResponse | None:
    """`None` means proceed; anything else is the refusal to return verbatim. Checked for BOTH the
    resource/booking's CURRENT branch (may he touch it at all) and, when the caller is assigning
    one, the REQUESTED branch (may he assign INTO it) — the same two-sided check
    `mobile_requests.py`'s own `assign_mobile_request` already holds for the identical reason."""
    if not branch_id:
        return None
    scope = await _scope(container, principal)
    if scope in DENIED:
        return _refuse("BRANCH_SCOPE_UNAVAILABLE", status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
    if not visible(scope, branch_id):
        return _refuse("OUTSIDE_YOUR_BRANCH", status_code=status.HTTP_403_FORBIDDEN)
    return None


def _in_scope(branch_id: str, scope: Any) -> bool:
    """Whether one row's own `branch_id` belongs to a branch this caller may read — the LIST-side
    twin of `_require_branch` above, applied per row rather than refusing the whole call."""
    return _branch_allowed(scope, branch_id)


# ── resources (spec §7) ─────────────────────────────────────────────────────────────────────────
class ResourceIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    # "" IS A REAL, VALID ANSWER — unassigned, visible to every branch's manager until somebody
    # picks one (see this module's own docstring).
    branch_id: str = Field(default="", max_length=64)
    # The shop's own words on what a freelancer is booking — empty is real and common.
    description: str = Field(default="", max_length=2000)


@router.post("/resources", dependencies=[Depends(rate_limit)])
async def create_resource(request: Request, body: ResourceIn,
                          principal: Principal = Depends(_MANAGE)) -> dict:
    c = request.app.state.container
    refusal = await _require_branch(c, principal, body.branch_id)
    if refusal is not None:
        return refusal
    try:
        resource = await c.resources.create(_tenant(principal), name=body.name,
                                            branch_id=body.branch_id,
                                            description=body.description)
    except ResourceError as exc:
        return _refuse(str(exc))
    return resource.public()


@router.get("/resources", dependencies=[Depends(rate_limit)])
async def list_resources(request: Request, principal: Principal = Depends(_MANAGE)) -> dict:
    c = request.app.state.container
    scope = await _scope(c, principal)
    if scope in DENIED:
        return {"resources": []}
    resources = await c.resources.list(_tenant(principal))
    kept = [r for r in resources if _in_scope(r.branch_id, scope)]
    return {"resources": [r.public() for r in kept]}


class ResourceUpdateIn(BaseModel):
    name: str | None = None
    active: bool | None = None
    branch_id: str | None = None
    description: str | None = None


@router.patch("/resources/{resource_id}", dependencies=[Depends(rate_limit)])
async def update_resource(request: Request, resource_id: str, body: ResourceUpdateIn,
                          principal: Principal = Depends(_MANAGE)) -> dict:
    c = request.app.state.container
    existing = await c.resources.get(_tenant(principal), resource_id)
    if existing is not None:
        refusal = await _require_branch(c, principal, existing.branch_id)
        if refusal is not None:
            return refusal
        if body.branch_id is not None:
            # REASSIGNING — the DESTINATION branch must also be inside his own scope, the same
            # two-sided check `assign_mobile_request` already holds.
            refusal = await _require_branch(c, principal, body.branch_id)
            if refusal is not None:
                return refusal
    try:
        resource = await c.resources.update(_tenant(principal), resource_id,
                                            name=body.name, active=body.active,
                                            branch_id=body.branch_id,
                                            description=body.description)
    except ResourceError as exc:
        return _refuse(str(exc), status_code=status.HTTP_404_NOT_FOUND)
    return resource.public()


class CatalogueImageIn(BaseModel):
    """A product photo, sent as JSON — the same shape operations' own catalogue upload already
    uses (`services/operations/app/api/v1/staff.py::CatalogueImageIn`), kept consistent rather
    than adding a second (multipart) upload convention to this fleet for one route."""
    content_type: str = Field(min_length=1, max_length=64)   # image/jpeg|image/png|image/webp
    data_base64: str = Field(min_length=1)


@router.post("/resources/{resource_id}/image", dependencies=[Depends(rate_limit)])
async def upload_resource_image(request: Request, resource_id: str, body: CatalogueImageIn,
                                principal: Principal = Depends(_MANAGE)) -> dict:
    """Replace this resource's ONE photo — see `core/catalogue_image.py`'s own module doc for why
    this is a real object, never a URL typed in, and never more than one."""
    c = request.app.state.container
    tenant = _tenant(principal)
    resource = await c.resources.get(tenant, resource_id)
    if resource is None:
        return _refuse("NOT_FOUND", status_code=status.HTTP_404_NOT_FOUND)
    refusal = await _require_branch(c, principal, resource.branch_id)
    if refusal is not None:
        return refusal
    import base64
    import binascii

    from app.core.catalogue_image import CatalogueImageError, store_image
    try:
        data = base64.b64decode(body.data_base64, validate=True)
    except (ValueError, binascii.Error):
        return _refuse("data_base64 is not valid base64",
                      status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)
    try:
        stored = await store_image(
            c.object_store, tenant=tenant, kind="resource", item_id=resource_id,
            data=data, content_type=body.content_type, old_key=resource.image_key)
    except CatalogueImageError as exc:
        return _refuse(str(exc), status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)
    updated = await c.resources.set_image(tenant, resource_id, image_key=stored.key)
    await request.app.state.auditor.record(
        "coworking.resource_image_set", actor=principal.subject, tenant=tenant,
        resource=f"resource:{resource_id}", ip=request.client.host if request.client else "")
    return updated.public()


@router.get("/resources/{resource_id}/image", dependencies=[Depends(rate_limit)])
async def get_resource_image(request: Request, resource_id: str,
                             principal: Principal = Depends(_MANAGE)):
    """The photo itself, streamed back — gated the same as the rest of this catalogue."""
    from starlette.responses import Response

    from app.core.catalogue_image import read_image
    from app.ports.errors import NotFound
    c = request.app.state.container
    resource = await c.resources.get(_tenant(principal), resource_id)
    if resource is not None:
        refusal = await _require_branch(c, principal, resource.branch_id)
        if refusal is not None:
            return refusal
    if resource is None or not resource.image_key:
        return JSONResponse({"error": "NOT_FOUND"}, status_code=status.HTTP_404_NOT_FOUND)
    try:
        data, ctype = await read_image(c.object_store, resource.image_key)
    except NotFound:
        return JSONResponse({"error": "NOT_FOUND"}, status_code=status.HTTP_404_NOT_FOUND)
    return Response(content=data, media_type=ctype)


class WindowIn(BaseModel):
    start_minute: int = Field(..., ge=0, le=24 * 60)
    end_minute: int = Field(..., ge=0, le=24 * 60)

    @model_validator(mode="after")
    def _ordered(self) -> "WindowIn":
        if self.end_minute <= self.start_minute:
            raise ValueError("end_minute must be after start_minute")
        return self


class DayExceptionIn(BaseModel):
    closed: bool = True
    windows: list[WindowIn] = Field(default_factory=list)


class AvailabilityIn(BaseModel):
    # Weekday 0=Monday..6=Sunday (Python's own `date.weekday()`), same convention
    # `core/availability.py`'s own `Schedule` already documents.
    weekly: dict[int, list[WindowIn]] = Field(default_factory=dict)
    exceptions: dict[str, DayExceptionIn] = Field(default_factory=dict)
    hourly_price_minor: int = Field(..., ge=0)


@router.put("/resources/{resource_id}/availability", dependencies=[Depends(rate_limit)])
async def set_availability(request: Request, resource_id: str, body: AvailabilityIn,
                           principal: Principal = Depends(_MANAGE)) -> dict:
    c = request.app.state.container
    existing = await c.resources.get(_tenant(principal), resource_id)
    if existing is not None:
        refusal = await _require_branch(c, principal, existing.branch_id)
        if refusal is not None:
            return refusal
    weekly = {day: [(w.start_minute, w.end_minute) for w in windows]
             for day, windows in body.weekly.items()}
    exceptions = {date: {"closed": exc.closed,
                        "windows": [(w.start_minute, w.end_minute) for w in exc.windows]}
                 for date, exc in body.exceptions.items()}
    try:
        resource = await c.resources.set_availability(
            _tenant(principal), resource_id, weekly=weekly, exceptions=exceptions,
            hourly_price_minor=body.hourly_price_minor)
    except ResourceError as exc:
        return _refuse(str(exc))
    return resource.public()


# ── join requests (spec §6/§7) — SHOP-WIDE, NEVER BRANCH-SCOPED, see this module's own docstring
@router.get("/joins", dependencies=[Depends(rate_limit)])
async def list_joins(request: Request, status: str | None = None,
                     principal: Principal = Depends(_MANAGE)) -> dict:
    c = request.app.state.container
    rows = await c.joins.list(_tenant(principal), status=status)
    return {"joins": rows}


@router.post("/joins/{phone}/approve", dependencies=[Depends(rate_limit)])
async def approve_join(request: Request, phone: str,
                       principal: Principal = Depends(_MANAGE)) -> dict:
    c = request.app.state.container
    phone = _phone(phone)
    try:
        return await c.joins.approve(_tenant(principal), phone)
    except JoinError as exc:
        return _refuse(str(exc), status_code=status.HTTP_404_NOT_FOUND)


@router.post("/joins/{phone}/reject", dependencies=[Depends(rate_limit)])
async def reject_join(request: Request, phone: str,
                      principal: Principal = Depends(_MANAGE)) -> dict:
    c = request.app.state.container
    phone = _phone(phone)
    try:
        await c.joins.reject(_tenant(principal), phone)
    except JoinError as exc:
        return _refuse(str(exc), status_code=status.HTTP_404_NOT_FOUND)
    return {"rejected": True}


@router.post("/joins/{phone}/block", dependencies=[Depends(rate_limit)])
async def block_phone(request: Request, phone: str,
                      principal: Principal = Depends(_MANAGE)) -> dict:
    """Answerable even with no prior join request at all — see `core/joins.py`'s own module doc."""
    c = request.app.state.container
    phone = _phone(phone)
    return await c.joins.block(_tenant(principal), phone)


@router.post("/joins/{phone}/unblock", dependencies=[Depends(rate_limit)])
async def unblock_phone(request: Request, phone: str,
                        principal: Principal = Depends(_MANAGE)) -> dict:
    c = request.app.state.container
    phone = _phone(phone)
    try:
        await c.joins.unblock(_tenant(principal), phone)
    except JoinError as exc:
        return _refuse(str(exc), status_code=status.HTTP_404_NOT_FOUND)
    return {"unblocked": True}


# ── bookings (spec §7) ───────────────────────────────────────────────────────────────────────────
@router.get("/bookings", dependencies=[Depends(rate_limit)])
async def list_bookings(request: Request, resource_id: str | None = None,
                        status: str | None = None,
                        principal: Principal = Depends(_MANAGE)) -> dict:
    c = request.app.state.container
    scope = await _scope(c, principal)
    if scope in DENIED:
        return {"bookings": []}
    rows = await c.bookings.list_for_tenant(_tenant(principal), resource_id=resource_id,
                                            status=status)
    kept = [r for r in rows if _in_scope(str(r.get("branch_id") or ""), scope)]
    return {"bookings": kept}


@router.post("/bookings/{booking_id}/cancel", dependencies=[Depends(rate_limit)])
async def cancel_booking(request: Request, booking_id: str,
                         principal: Principal = Depends(_MANAGE)) -> dict:
    c = request.app.state.container
    # A plain read of record, once, only to learn the branch before deciding whether this caller
    # may act on it at all — `bookings.cancel` below is the actual, tenant-scoped write.
    row = await c.datastore.get(BOOKINGS, booking_id)
    if row is not None and row.get("tenant") == _tenant(principal):
        refusal = await _require_branch(c, principal, str(row.get("branch_id") or ""))
        if refusal is not None:
            return refusal
    try:
        return await c.bookings.cancel(_tenant(principal), booking_id)
    except BookingRefused as exc:
        return _refuse(str(exc), status_code=status.HTTP_404_NOT_FOUND)


# ── tenant-level pause (spec §5) — SHOP-WIDE, NEVER BRANCH-SCOPED: "this establishment stops
# taking new bookings" is a single switch by design, not a per-branch one ─────────────────────────
@router.get("/pause", dependencies=[Depends(rate_limit)])
async def get_pause(request: Request, principal: Principal = Depends(_MANAGE)) -> dict:
    c = request.app.state.container
    return {"paused": await c.pause.is_paused(_tenant(principal))}


class PauseIn(BaseModel):
    paused: bool


@router.put("/pause", dependencies=[Depends(rate_limit)])
async def set_pause(request: Request, body: PauseIn,
                    principal: Principal = Depends(_MANAGE)) -> dict:
    c = request.app.state.container
    paused = await c.pause.set_paused(_tenant(principal), body.paused)
    await request.app.state.auditor.record(
        "coworking.pause_changed", actor=principal.subject, tenant=_tenant(principal),
        resource="tenant", ip=request.client.host if request.client else "",
        metadata={"paused": paused})
    return {"paused": paused}
