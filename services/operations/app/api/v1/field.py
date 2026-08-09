"""The field surface — the screen an operator uses all day.

THE TENANT COMES OFF THE TOKEN, NEVER OFF THE BODY. Every route below scopes to
`principal.tenant`, and there is no field anywhere in this module through which a caller can name
an establishment. A tenant a caller can send is a tenant a caller can change, and cross-tenant
access here means one workshop reading another's customer list.

THE SEAMS RUN AFTER THE RESPONSE. Search indexing, the analytics event and the reminder schedule
are handed to a background task once the operator has been answered — see core/seams.py. A slow
peer must never become a slow screen, and the five-second budget belongs to the operator, not to
our fan-out.

THE AUDIT IS THE EXCEPTION, and it runs BEFORE the write. A visit the log cannot witness must not
happen, and recording afterwards would tell an operator "saved" about something the record does
not hold.
"""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.api.auth import Principal
from app.api.authz import require_capability
from app.api.ratelimit import rate_limit
from app.core.operations import OperationError, Operations

# The parent router in __init__ already carries /api/v1 — this prefix is appended to it.
router = APIRouter(prefix="/field", tags=["field"])

# Two capabilities, not one. Recording a visit is what every operator does all day; reading the
# customer book is a different privilege, and a shop that hires seasonal help should be able to
# grant the first without the second.
_RECORD = require_capability("operations.record")
_READ = require_capability("operations.read")


def _svc(request: Request) -> Operations:
    return request.app.state.container.operations


def _tenant(p: Principal) -> str:
    if not p.tenant:
        # A user token with no tenant is a platform-level token being used on a tenant surface.
        # Refused rather than defaulted: defaulting here would silently pick somebody's data.
        raise HTTPException(status.HTTP_403_FORBIDDEN, "NO_TENANT")
    return p.tenant


class VisitIn(BaseModel):
    phone: str = Field(min_length=3, max_length=32)
    service_ids: list[str] = Field(min_length=1, max_length=20)
    # OPTIONAL, and blank is a real value — a required name produces "عميل" and "." and "ااا",
    # which are worse than blank because an invented name becomes a greeting in a real message.
    name: str = Field(default="", max_length=128)
    # Vehicle sectors only. A salon never sends it, and the screen never shows the field.
    plate: str = Field(default="", max_length=32)
    operator_id: str = Field(default="", max_length=64)
    branch_id: str = Field(default="", max_length=64)
    meter: int = Field(default=0, ge=0, le=10_000_000)
    note: str = Field(default="", max_length=1000)
    # Only meaningful with the catch-all: what the technician actually did. Optional, because a
    # required box here would be one more thing to type with a customer waiting — and "خدمة أخرى"
    # with no label still records the visit, which is the point.
    custom_service: str = Field(default="", max_length=200)
    # CLIENT-generated, one per entry on the screen. See core/operations.py for why this cannot be
    # server-side: a server cannot tell a double tap from a customer who genuinely came back.
    idempotency_key: str = Field(default="", max_length=128)


@router.post("/visits", status_code=status.HTTP_201_CREATED, dependencies=[Depends(rate_limit)])
async def record_visit(request: Request, body: VisitIn, background: BackgroundTasks,
                       principal: Principal = Depends(_RECORD)) -> dict:
    """Record a visit. This endpoint is the product, as far as the shop floor is concerned."""
    tenant = _tenant(principal)

    # Write-ahead. Critical: a visit the log cannot witness must not happen.
    await request.app.state.auditor.record(
        "visit.recorded", actor=principal.subject, tenant=tenant, resource="visit",
        ip=request.client.host if request.client else "")

    try:
        result = await _svc(request).record_visit(
            tenant=tenant, phone=body.phone, service_ids=body.service_ids, name=body.name,
            plate=body.plate, operator_id=body.operator_id, branch_id=body.branch_id,
            meter=body.meter, note=body.note, custom_service=body.custom_service,
            idempotency_key=body.idempotency_key)
    except OperationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))

    # A repeat of the same key is a SUCCESS, not a conflict: the operator's intent was satisfied,
    # and a 409 on a double tap teaches them the screen is unreliable. `duplicate` is reported so
    # a client can tell the difference without being punished for it.
    if not result.duplicate:
        seams = request.app.state.container.seams
        background.add_task(seams.after_visit, result)

    return {"visit": result.visit.public(), "customer": result.customer.public(),
            "created_customer": result.created_customer, "duplicate": result.duplicate}


@router.get("/customers/recent", dependencies=[Depends(rate_limit)])
async def recent_customers(request: Request, limit: int = 10,
                           principal: Principal = Depends(_READ)) -> dict:
    """The strip along the top of the field screen — today's customers, one tap away."""
    limit = max(1, min(limit, 50))
    rows = await _svc(request).recent_customers(_tenant(principal), limit=limit)
    return {"customers": [c.public() for c in rows]}


@router.get("/customers/by-phone", dependencies=[Depends(rate_limit)])
async def customer_by_phone(request: Request, phone: str,
                            principal: Principal = Depends(_READ)) -> dict:
    """Exact lookup, for the moment the full number has been typed.

    PREFIX lookup is NOT here and must not be added here. It is served by search-service's
    /search/suggest, because a prefix scan over the datastore is a table scan and this sits inside
    a five-second budget. Measured, not assumed: POST /search matches whole tokens, so `96650`
    finds nothing against a stored `966501234567` — the keypad must call suggest.
    """
    c = await _svc(request).customer_by_phone(_tenant(principal), phone)
    return {"customer": c.public() if c else None}


@router.get("/customers/{customer_id}", dependencies=[Depends(rate_limit)])
async def customer_record(request: Request, customer_id: str,
                          principal: Principal = Depends(_READ)) -> dict:
    """The customer's record: their vehicles and their recent visits."""
    rec = await _svc(request).customer_record(_tenant(principal), customer_id)
    if rec is None:
        # 404 for "not in THIS establishment", which is also the answer when the id belongs to
        # another tenant. Deliberately indistinguishable: a 403 would confirm the id exists
        # somewhere, which is an enumeration oracle across establishments.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND")
    return rec


@router.get("/catalogue", dependencies=[Depends(rate_limit)])
async def catalogue(request: Request, principal: Principal = Depends(_READ)) -> dict:
    """The service grid. Seeded full from the sector defaults at tenant creation — an
    establishment that must build its own list before recording a first visit will not record a
    first visit."""
    return {"services": await _svc(request).catalogue(_tenant(principal))}
