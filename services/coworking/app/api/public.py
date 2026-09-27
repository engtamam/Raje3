"""The freelancer's own door — public, no-auth (spec §6).

MOUNTED AT `/p/coworking/{tenant}`, SERVED DIRECTLY BY THIS SERVICE — a deliberate departure from
how `/p/*` is documented today (`deploy/edge/edge.json` routes the whole prefix to `portal`, which
serves the WhatsApp-opened customer page over a per-CUSTOMER HMAC reference). That model does not
fit here: portal's reference protects a single person's own link; this app gives a SHOP one
shareable link it hands to whichever freelancers it already works with (spec §4 — no directory, no
per-person secret to protect at all). Building this inside portal would mean portal calling into
this service over HTTP for every read and write for no benefit — the domain logic already lives
here, next to its own datastore, exactly like every admin API in this fleet. So `edge.json` gets a
new, MORE SPECIFIC route (`/p/coworking/*` -> this service) placed alongside the existing `/p/*` ->
portal route; the renderer's own "longest prefix wins" rule (its header comment) means this one
route is never shadowed by the other, and every other `/p/*` link keeps working exactly as before.

NO TOKEN, EVER — the phone the caller types IS their identity (see `core/phone.py`'s own module
doc for why that is a deliberate, new pattern here). Every read and write below is scoped to BOTH
the URL's own `{tenant}` and the caller's own phone — never one alone — so a stranger who knows one
shop's link and one phone number can still never see another shop's resources, prices or bookings,
and never another freelancer's bookings at the SAME shop either.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel, Field
from starlette.responses import JSONResponse

from app.api.ratelimit import rate_limit
from app.config import get_settings
from app.core.bookings import BookingRefused, JoinRequired
from app.core.phone import canonical_phone

router = APIRouter(prefix="/p/coworking", tags=["coworking-public"])

# Never cached anywhere between here and the freelancer's own browser — a shared/cached response
# to "what is free right now" or "what are my bookings" is stale the instant anyone else acts,
# and a cache is one more place a phone number and a price would sit at rest for no reason.
NO_STORE = {"Cache-Control": "no-store, no-cache, must-revalidate, private",
           "Pragma": "no-cache"}


def _phone(raw: str) -> str:
    return canonical_phone(raw, default_cc=get_settings().COWORKING_PHONE_DEFAULT_CC)


def _refuse(reason: str, message: str, *,
           status_code: int = status.HTTP_400_BAD_REQUEST) -> JSONResponse:
    return JSONResponse({"error": reason, "reason": message}, status_code=status_code,
                        headers=NO_STORE)


@router.get("/{tenant}/resources", dependencies=[Depends(rate_limit)])
async def list_resources(request: Request, tenant: str) -> JSONResponse:
    """Active resources only, and only the fields a freelancer choosing one needs — never the
    weekly schedule's raw shape (that is what `/slots` computes FROM it, deliberately not exposed
    verbatim, the same "derived, never a second source of truth" discipline
    `core/availability.py`'s own module doc holds for a booking screen)."""
    c = request.app.state.container
    resources = await c.resources.list(tenant, include_inactive=False)
    body = {"resources": [{"id": r.id, "name": r.name, "hourly_price_minor": r.hourly_price_minor}
                          for r in resources]}
    return JSONResponse(body, headers=NO_STORE)


@router.get("/{tenant}/slots", dependencies=[Depends(rate_limit)])
async def free_slots(request: Request, tenant: str, resource_id: str,
                     window_start: int = Query(..., description="epoch seconds"),
                     window_end: int = Query(..., description="epoch seconds"),
                     duration_minutes: int = Query(..., gt=0, le=24 * 60)) -> JSONResponse:
    c = request.app.state.container
    if window_end <= window_start:
        return _refuse("BAD_WINDOW", "نطاق التاريخ غير صالح")
    # BOUNDED — an open-ended search window is an unbounded scan of every confirmed booking on
    # this resource forever; 90 days is generously past any realistic "pick a slot" horizon.
    if window_end - window_start > 90 * 86400:
        return _refuse("BAD_WINDOW", "نطاق البحث طويل جداً — 90 يوماً كحد أقصى")
    slots = await c.bookings.free_slots(tenant, resource_id, window_start=window_start,
                                        window_end=window_end, duration_minutes=duration_minutes)
    body = {"slots": [{"starts_at": s.starts_at, "ends_at": s.ends_at} for s in slots]}
    return JSONResponse(body, headers=NO_STORE)


class JoinIn(BaseModel):
    phone: str = Field(..., min_length=3, max_length=32)


@router.get("/{tenant}/status", dependencies=[Depends(rate_limit)])
async def join_status(request: Request, tenant: str, phone: str) -> JSONResponse:
    phone = _phone(phone)
    if not phone:
        return _refuse("BAD_PHONE", "رقم الجوال غير صالح")
    c = request.app.state.container
    status_ = await c.joins.status(tenant, phone)
    return JSONResponse({"status": status_}, headers=NO_STORE)


@router.post("/{tenant}/join", dependencies=[Depends(rate_limit)])
async def join(request: Request, tenant: str, body: JoinIn) -> JSONResponse:
    """Submit a join request by hand, without first failing a booking attempt over it — a
    friendlier door onto the same `ensure_pending` a first booking attempt would otherwise trigger
    automatically (spec §6)."""
    phone = _phone(body.phone)
    if not phone:
        return _refuse("BAD_PHONE", "رقم الجوال غير صالح")
    c = request.app.state.container
    existing = await c.joins.status(tenant, phone)
    if existing is not None:
        return JSONResponse({"status": existing}, headers=NO_STORE)
    row = await c.joins.ensure_pending(tenant, phone)
    return JSONResponse({"status": row["status"]}, headers=NO_STORE)


class BookingIn(BaseModel):
    phone: str = Field(..., min_length=3, max_length=32)
    resource_id: str = Field(..., min_length=1, max_length=200)
    starts_at: int = Field(..., description="epoch seconds")
    ends_at: int = Field(..., description="epoch seconds")


@router.post("/{tenant}/bookings", dependencies=[Depends(rate_limit)])
async def create_booking(request: Request, tenant: str, body: BookingIn) -> JSONResponse:
    phone = _phone(body.phone)
    if not phone:
        return _refuse("BAD_PHONE", "رقم الجوال غير صالح")
    c = request.app.state.container
    try:
        booking = await c.bookings.create(tenant, resource_id=body.resource_id, phone=phone,
                                          starts_at=body.starts_at, ends_at=body.ends_at)
    except JoinRequired as exc:
        # NOT AN ERROR STATUS — a join request was created, which is the expected first step for
        # a phone this shop has never seen (spec §6). 202: accepted, not yet actionable.
        return JSONResponse({"status": "join_required", "reason": str(exc)},
                            status_code=status.HTTP_202_ACCEPTED, headers=NO_STORE)
    except BookingRefused as exc:
        return _refuse(exc.reason, str(exc))
    return JSONResponse(booking, headers=NO_STORE)


@router.get("/{tenant}/my-bookings", dependencies=[Depends(rate_limit)])
async def my_bookings(request: Request, tenant: str, phone: str) -> JSONResponse:
    phone = _phone(phone)
    if not phone:
        return _refuse("BAD_PHONE", "رقم الجوال غير صالح")
    c = request.app.state.container
    rows = await c.bookings.list_for_phone(tenant, phone)
    return JSONResponse({"bookings": rows}, headers=NO_STORE)
