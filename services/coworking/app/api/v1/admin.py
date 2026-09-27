"""The shop's own admin surface (spec §7) — everything an owner does to run this app.

TIER "user", CAPABILITY "coworking.manage" — same shape as every other per-shop admin route in
this fleet (`campaigns.manage`, `bookings.manage`, …): a token belonging to a person at THIS shop,
never a platform operator. `principal.tenant` is what scopes every read and write here to that
one shop; nothing in this file ever accepts a tenant from the request body.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field
from starlette.responses import JSONResponse

from app.api.auth import Principal, require_user
from app.api.authz import require_capability
from app.api.ratelimit import rate_limit
from app.config import get_settings
from app.core.bookings import BookingRefused
from app.core.joins import JoinError
from app.core.phone import canonical_phone
from app.core.resources import ResourceError

router = APIRouter(prefix="/api/v1/coworking", tags=["coworking-admin"])

_MANAGE = require_capability("coworking.manage")


def _tenant(principal: Principal) -> str:
    return principal.tenant or ""


def _phone(raw: str) -> str:
    # SAME NORMALIZER `public.py` USES — an owner typing a number by hand ("0501234567") must
    # resolve to the exact same key a freelancer's own booking attempt does ("+966501234567"), or
    # `block()` silently blocks a row nobody ever books under while the real identity stays free.
    return canonical_phone(raw, default_cc=get_settings().COWORKING_PHONE_DEFAULT_CC)


def _refuse(reason: str, *, status_code: int = status.HTTP_400_BAD_REQUEST) -> JSONResponse:
    return JSONResponse({"error": "BAD_REQUEST", "reason": reason}, status_code=status_code)


# ── resources (spec §7) ─────────────────────────────────────────────────────────────────────────
class ResourceIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)


@router.post("/resources", dependencies=[Depends(rate_limit)])
async def create_resource(request: Request, body: ResourceIn,
                          principal: Principal = Depends(_MANAGE)) -> dict:
    c = request.app.state.container
    try:
        resource = await c.resources.create(_tenant(principal), name=body.name)
    except ResourceError as exc:
        return _refuse(str(exc))
    return resource.to_dict()


@router.get("/resources", dependencies=[Depends(rate_limit)])
async def list_resources(request: Request, principal: Principal = Depends(_MANAGE)) -> dict:
    c = request.app.state.container
    resources = await c.resources.list(_tenant(principal))
    return {"resources": [r.to_dict() for r in resources]}


class ResourceUpdateIn(BaseModel):
    name: str | None = None
    active: bool | None = None


@router.patch("/resources/{resource_id}", dependencies=[Depends(rate_limit)])
async def update_resource(request: Request, resource_id: str, body: ResourceUpdateIn,
                          principal: Principal = Depends(_MANAGE)) -> dict:
    c = request.app.state.container
    try:
        resource = await c.resources.update(_tenant(principal), resource_id,
                                            name=body.name, active=body.active)
    except ResourceError as exc:
        return _refuse(str(exc), status_code=status.HTTP_404_NOT_FOUND)
    return resource.to_dict()


class WindowIn(BaseModel):
    start_minute: int = Field(..., ge=0, le=24 * 60)
    end_minute: int = Field(..., ge=0, le=24 * 60)


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
    return resource.to_dict()


# ── join requests (spec §6/§7) ──────────────────────────────────────────────────────────────────
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
    await c.joins.unblock(_tenant(principal), phone)
    return {"unblocked": True}


# ── bookings (spec §7) ───────────────────────────────────────────────────────────────────────────
@router.get("/bookings", dependencies=[Depends(rate_limit)])
async def list_bookings(request: Request, resource_id: str | None = None,
                        status: str | None = None,
                        principal: Principal = Depends(_MANAGE)) -> dict:
    c = request.app.state.container
    rows = await c.bookings.list_for_tenant(_tenant(principal), resource_id=resource_id,
                                            status=status)
    return {"bookings": rows}


@router.post("/bookings/{booking_id}/cancel", dependencies=[Depends(rate_limit)])
async def cancel_booking(request: Request, booking_id: str,
                         principal: Principal = Depends(_MANAGE)) -> dict:
    c = request.app.state.container
    try:
        return await c.bookings.cancel(_tenant(principal), booking_id)
    except BookingRefused as exc:
        return _refuse(str(exc), status_code=status.HTTP_404_NOT_FOUND)


# ── tenant-level pause (spec §5) ─────────────────────────────────────────────────────────────────
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
