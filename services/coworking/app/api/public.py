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

import re
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel, Field
from starlette.responses import HTMLResponse, JSONResponse

from app.api.ratelimit import rate_limit
from app.config import get_settings
from app.core.bookings import BookingRefused, JoinRequired
from app.core.memberships import MembershipError, MembershipRefused
from app.core.phone import canonical_phone
from app.core.shop_info import fetch_shop_info

router = APIRouter(prefix="/p/coworking", tags=["coworking-public"])

# Read once at import time, not per request — the page is one static file, shared by every tenant
# (the tenant is read from the URL client-side, see the script's own `location.pathname` parse).
_PORTAL_HTML = (Path(__file__).resolve().parent.parent / "static" / "portal.html").read_text(
    encoding="utf-8")

# Never cached anywhere between here and the freelancer's own browser — a shared/cached response
# to "what is free right now" or "what are my bookings" is stale the instant anyone else acts,
# and a cache is one more place a phone number and a price would sit at rest for no reason.
NO_STORE = {"Cache-Control": "no-store, no-cache, must-revalidate, private",
           "Pragma": "no-cache"}


_PHONE_SHAPE_RE = re.compile(r"^[0-9+()\- ]{3,32}$")  # phone punctuation only — no digits buried in junk


def _phone(raw: str) -> str:
    if not _PHONE_SHAPE_RE.match(raw or ""):
        return ""
    return canonical_phone(raw, default_cc=get_settings().COWORKING_PHONE_DEFAULT_CC)


def _refuse(reason: str, message: str, *,
           status_code: int = status.HTTP_400_BAD_REQUEST) -> JSONResponse:
    return JSONResponse({"error": reason, "reason": message}, status_code=status_code,
                        headers=NO_STORE)


@router.get("/{tenant}", dependencies=[Depends(rate_limit)])
async def portal_page(tenant: str) -> HTMLResponse:
    """The freelancer's own landing page — the shareable link a shop hands out (console/mobile's
    own `ShareLinkCard`). ONE static page for every tenant; it reads `{tenant}` from its own URL
    and calls the JSON routes below exactly like any other client of this file would.

    ITS OWN CSP, NOT THE SERVICE'S GLOBAL `default-src 'none'` — this is the one HTML page in the
    service, with real inline <script>/<style> and same-origin <img>/fetch calls the global JSON-
    API policy would otherwise block outright."""
    headers = {**NO_STORE, "Content-Security-Policy": (
        "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'self'; "
        "frame-ancestors 'none'")}
    return HTMLResponse(_PORTAL_HTML, headers=headers)


@router.get("/{tenant}/resources", dependencies=[Depends(rate_limit)])
async def list_resources(request: Request, tenant: str) -> JSONResponse:
    """Active resources only, and only the fields a freelancer choosing one needs — never the
    weekly schedule's raw shape (that is what `/slots` computes FROM it, deliberately not exposed
    verbatim, the same "derived, never a second source of truth" discipline
    `core/availability.py`'s own module doc holds for a booking screen). `description`/`has_image`
    are exactly what he needs to pick one — never `branch_id` (which branch a resource sits at is
    the SHOP's own scoping concern, not a fact the freelancer's booking screen has any use for)."""
    c = request.app.state.container
    resources = await c.resources.list(tenant, include_inactive=False)
    body = {"resources": [
        {"id": r.id, "name": r.name, "hourly_price_minor": r.hourly_price_minor,
         "description": r.description, "has_image": bool(r.image_key),
         # «hourly» (free_slots/bookings below) vs «month»/«year» (memberships below) — the
         # freelancer's own portal reads this to decide which door a resource's card opens.
         "rental_period": r.rental_period, "quantity": r.quantity,
         "period_price_minor": r.period_price_minor}
        for r in resources]}
    return JSONResponse(body, headers=NO_STORE)


@router.get("/{tenant}/shop", dependencies=[Depends(rate_limit)])
async def shop_info(request: Request, tenant: str) -> JSONResponse:
    """What the portal's own header needs — the shop's name/logo/accent (see `core/shop_info.py`'s
    own module doc for why this is a peer call) and whether it is paused right now (spec §5) so a
    freelancer sees that BEFORE trying to book, not only as a refusal after picking a slot."""
    c = request.app.state.container
    info = await fetch_shop_info(get_settings(), tenant)
    paused = await c.pause.is_paused(tenant)
    body = {"name": info.name, "logo_url": info.logo_url, "accent": info.accent, "paused": paused}
    return JSONResponse(body, headers=NO_STORE)


@router.get("/{tenant}/resources/{resource_id}/image", dependencies=[Depends(rate_limit)])
async def resource_image(request: Request, tenant: str, resource_id: str):
    """The photo itself, streamed back — PUBLIC, no auth, same door every other read on this
    file already is: a freelancer choosing a resource needs to see it before booking, and a photo
    a shop uploaded to its own public link is not the sensitive content operations' own catalogue
    photo (gated behind a login) is."""
    from starlette.responses import Response

    from app.core.catalogue_image import read_image
    from app.ports.errors import NotFound
    c = request.app.state.container
    resource = await c.resources.get(tenant, resource_id)
    if resource is None or not resource.active or not resource.image_key:
        return JSONResponse({"error": "NOT_FOUND"}, status_code=status.HTTP_404_NOT_FOUND,
                            headers=NO_STORE)
    try:
        data, ctype = await read_image(c.object_store, resource.image_key)
    except NotFound:
        return JSONResponse({"error": "NOT_FOUND"}, status_code=status.HTTP_404_NOT_FOUND,
                            headers=NO_STORE)
    return Response(content=data, media_type=ctype, headers=NO_STORE)


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


# ── memberships (owner decision, 2026-10-06) — the «month»/«year» seat door ──────────────────────
class MembershipJoinIn(BaseModel):
    phone: str = Field(..., min_length=3, max_length=32)
    resource_id: str = Field(..., min_length=1, max_length=200)


@router.post("/{tenant}/memberships", dependencies=[Depends(rate_limit)])
async def join_membership(request: Request, tenant: str, body: MembershipJoinIn) -> JSONResponse:
    phone = _phone(body.phone)
    if not phone:
        return _refuse("BAD_PHONE", "رقم الجوال غير صالح")
    c = request.app.state.container
    try:
        membership = await c.memberships.join(tenant, resource_id=body.resource_id, phone=phone)
    except MembershipRefused as exc:
        if exc.reason == "JOIN_REQUIRED":
            # SAME SHAPE `create_booking` ABOVE GIVES A FIRST-EVER PHONE — 202, not an error: a
            # join request now exists, which is the expected first step (spec §6, reused as-is).
            return JSONResponse({"status": "join_required", "reason": str(exc)},
                                status_code=status.HTTP_202_ACCEPTED, headers=NO_STORE)
        return _refuse(exc.reason, str(exc))
    return JSONResponse(membership, headers=NO_STORE)


@router.get("/{tenant}/my-memberships", dependencies=[Depends(rate_limit)])
async def my_memberships(request: Request, tenant: str, phone: str) -> JSONResponse:
    phone = _phone(phone)
    if not phone:
        return _refuse("BAD_PHONE", "رقم الجوال غير صالح")
    c = request.app.state.container
    rows = await c.memberships.list_for_phone(tenant, phone)
    return JSONResponse({"memberships": rows}, headers=NO_STORE)


def _owns_membership(row: dict | None, phone: str) -> bool:
    return row is not None and row.get("freelancer_phone") == phone


@router.post("/{tenant}/memberships/{membership_id}/stop-renewal",
            dependencies=[Depends(rate_limit)])
async def stop_own_membership_renewal(request: Request, tenant: str, membership_id: str,
                                      phone: str) -> JSONResponse:
    """THE MEMBER'S OWN DOOR — "لو خرج يقدر يوقف التجديد" (owner's own words). Scoped to BOTH the
    membership id and the caller's own phone, the same two-fact discipline every other route in
    this file holds — a stranger who knows one membership id can never touch another member's
    row even by accident."""
    phone = _phone(phone)
    if not phone:
        return _refuse("BAD_PHONE", "رقم الجوال غير صالح")
    c = request.app.state.container
    row = await c.memberships.get(tenant, membership_id)
    if not _owns_membership(row, phone):
        return _refuse("NOT_FOUND", "العضوية غير موجودة", status_code=status.HTTP_404_NOT_FOUND)
    try:
        updated = await c.memberships.stop_renewal(tenant, membership_id)
    except MembershipError as exc:
        return _refuse("NOT_FOUND", str(exc), status_code=status.HTTP_404_NOT_FOUND)
    return JSONResponse(updated, headers=NO_STORE)


@router.post("/{tenant}/memberships/{membership_id}/resume-renewal",
            dependencies=[Depends(rate_limit)])
async def resume_own_membership_renewal(request: Request, tenant: str, membership_id: str,
                                        phone: str) -> JSONResponse:
    phone = _phone(phone)
    if not phone:
        return _refuse("BAD_PHONE", "رقم الجوال غير صالح")
    c = request.app.state.container
    row = await c.memberships.get(tenant, membership_id)
    if not _owns_membership(row, phone):
        return _refuse("NOT_FOUND", "العضوية غير موجودة", status_code=status.HTTP_404_NOT_FOUND)
    try:
        updated = await c.memberships.resume_renewal(tenant, membership_id)
    except MembershipError as exc:
        return _refuse("NOT_FOUND", str(exc), status_code=status.HTTP_404_NOT_FOUND)
    return JSONResponse(updated, headers=NO_STORE)


class MembershipForceEndIn(BaseModel):
    phone: str = Field(..., min_length=3, max_length=32)
    # NO DEFAULT, SAME AS THE ADMIN ROUTE — a member ending his own membership early must also
    # type `true` explicitly; see core/memberships.py's own module doc.
    acknowledged: bool
    note: str = Field(default="", max_length=2000)


@router.post("/{tenant}/memberships/{membership_id}/force-end",
            dependencies=[Depends(rate_limit)])
async def force_end_own_membership(request: Request, tenant: str, membership_id: str,
                                   body: MembershipForceEndIn) -> JSONResponse:
    """«يقدر يجبر إيقاف الاشتراك» — the member's own immediate-exit door, same acknowledgment
    requirement and same audit trail as the shop's own `force-end` admin route."""
    phone = _phone(body.phone)
    if not phone:
        return _refuse("BAD_PHONE", "رقم الجوال غير صالح")
    c = request.app.state.container
    row = await c.memberships.get(tenant, membership_id)
    if not _owns_membership(row, phone):
        return _refuse("NOT_FOUND", "العضوية غير موجودة", status_code=status.HTTP_404_NOT_FOUND)
    try:
        updated = await c.memberships.force_end(
            tenant, membership_id, acknowledged=body.acknowledged, ack_by=phone, note=body.note)
    except MembershipError as exc:
        return _refuse("NOT_FOUND", str(exc), status_code=status.HTTP_404_NOT_FOUND)
    await request.app.state.auditor.record(
        "coworking.membership_force_ended", actor=phone, tenant=tenant,
        resource=f"membership:{membership_id}", ip=request.client.host if request.client else "",
        metadata={"note": body.note, "by": "member"})
    return JSONResponse(updated, headers=NO_STORE)
