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
    if c is None:
        return {"customer": None}
    # THE PSEUDONYM COMES WITH THE EXACT MATCH, and only with it — never with the prefix
    # suggestions, which are a list of people the operator has not chosen yet.
    #
    # It is here so the field screen can ask reminders one question: is this customer holding an
    # offer (§5.6.2)? An offer the man at the counter cannot see becomes a discount argued over
    # while the customer holds the message that promised it. The alternative was operations asking
    # reminders on the hot path of a five-second screen, which puts another service's latency
    # inside the one budget this product actually has.
    return {"customer": {**c.public(), "subject_ref": c.subject_ref}}


class ResolveIn(BaseModel):
    """Pseudonyms in, customers out. NO TENANT FIELD — see the route."""

    refs: list[str] = Field(default_factory=list, max_length=200)


@router.post("/customers/resolve", dependencies=[Depends(rate_limit)])
async def resolve_customers(request: Request, body: ResolveIn,
                            principal: Principal = Depends(_READ)) -> dict:
    """Turn a list of `subject_ref` pseudonyms into this establishment's customers.

    WHY THIS EXISTS. «عملائي» promises three things and delivered two: how many do I have, find
    this one, and WHO IS OVERDUE. The third could not be built, because the overdue list lives in
    reminders — and reminders holds no names at all. It answers with the pseudonym, deliberately:
    a service that does not need a customer's name must not be able to read one.

    So the join happens where the names already are, which is here. The alternative was giving
    reminders a copy of the customer table, and a second copy of a name is a second thing that goes
    stale and a second place PII can leak from.

    THE TENANT IS NOT A FIELD ON THE BODY. It comes from the token, exactly as the till route
    learned to do: a caller who can name the tenant can name somebody else's, and a pseudonym is
    only meaningful within one — so a request that carried its own tenant would be a customer
    lookup across establishments wearing an internal-looking name.

    UNKNOWN REFS ARE SIMPLY ABSENT from the answer rather than being reported. A pseudonym this
    establishment does not hold is not an error to explain: it is an erased customer, or another
    shop's, and confirming which would answer a question nobody should be able to ask.
    """
    wanted = {r for r in body.refs if r}
    if not wanted:
        return {"customers": []}
    rows = await _svc(request).customers_by_refs(_tenant(principal), wanted)
    return {"customers": [c.public() for c in rows]}


@router.get("/customers/by-plate", dependencies=[Depends(rate_limit)])
async def customer_by_plate(request: Request, plate: str,
                            principal: Principal = Depends(_READ)) -> dict:
    """Whose car this is — so a vehicle shop never asks for a number it already holds.

    DECLARED BEFORE /customers/{customer_id} ON PURPOSE. FastAPI matches in declaration order, and
    a path parameter registered first would swallow «by-plate» as a customer id — the same trap
    that «by-phone» sits above, for the same reason.

    Answers `null` for an unknown plate rather than 404: the screen renders the same either way,
    and a distinct status here is an oracle for which cars a shop has seen.
    """
    c = await _svc(request).customer_by_plate(_tenant(principal), plate)
    if c is None:
        return {"customer": None}
    # The pseudonym travels with an exact match, exactly as it does for by-phone — it is what lets
    # the screen ask about his offers without a second round trip.
    return {"customer": {"id": c.id, "phone": c.phone, "name": c.name,
                         "subject_ref": c.subject_ref}}


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
    tenant = _tenant(principal)
    sectors = request.app.state.container.sectors
    key = await sectors.sector_of(tenant)
    # THE FIELDS COME WITH THE GRID, and this is the point of answering them here at all.
    #
    # Which inputs a screen renders is a property of the SECTOR (spec 13.2): the plate exists in a
    # tyre shop and does not exist in a salon - not disabled, not empty, absent. The front end
    # cannot work that out for itself without carrying its own list of sector keys, which is a
    # copy of our data living where we cannot change it: our console adds a fifth sector at
    # runtime and the screen keeps rendering the four it was built with.
    #
    # `fields` is the full descriptor rather than names, so the screen never needs its own idea of
    # what "meter" means either. An establishment provisioned before we recorded sectors answers
    # an empty list - honest, and it renders the phone and nothing else, which is always valid.
    return {"services": await _svc(request).catalogue(tenant),
            "sector": key,
            "fields": await sectors.fields_for(key) if key else []}

class ApplyOfferIn(BaseModel):
    subject_ref: str = Field(min_length=8, max_length=128)


@router.post("/visits/{visit_id}/offer", dependencies=[Depends(rate_limit)])
async def apply_offer(request: Request, visit_id: str, body: ApplyOfferIn,
                      principal: Principal = Depends(_RECORD)) -> dict:
    """Record that an offer was applied to this visit — the tap that proves it (§5.6.2).

    IT LIVES HERE AND NOT IN reminders, and that is the whole correction. «ويُسجَّل على الزيارة،
    لا على العرض»: the send log is append-only and every cap in 5.8 is counted against it, so the
    used-mark cannot be written into it. The visit is also simply what happened at the counter.

    A TAP, NEVER AN INFERENCE. Nothing spends an offer because a visit arrived — a customer who
    came for something else and was quietly charged an offer he was saving is a customer we took
    something from. The discount is money; a system that spends it with nobody deciding produces
    an invoice the shop cannot explain.

    ONE PER VISIT, ENFORCED HERE because here is where the visit is. A second tap returns the SAME
    offer and spends nothing more — a double tap at a counter is one intention, and a screen that
    punished it is a screen people stop trusting.

    AND reminders CHOOSES WHICH ONE, because only it knows what was sent, with what scope and what
    expiry. We record; it judges. Neither reads the other's tables.
    """
    ops: Operations = request.app.state.container.operations
    try:
        applied = await ops.apply_offer(tenant=principal.tenant, visit_id=visit_id,
                                        subject_ref=body.subject_ref)
    except OperationError as e:
        # RETURNED, NEVER RAISED. The platform strips HTTPException detail on the way out, so a
        # raise here reaches the owner as an empty 400 — the refusal he needs to read is the whole
        # value of the answer.
        return {"applied": False, "reason": str(e)}

    if applied is None:
        return {"applied": False, "reason": "لا يوجد عرضٌ ساري يشمل هذه الزيارة"}
    return {"applied": True, "offer": applied}
