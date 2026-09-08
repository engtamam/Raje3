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

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, status
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from app.api.auth import Principal
from app.api.authz import require_capability
from app.api.ratelimit import rate_limit
from app.api import scope as SCOPE
from app.api.scope import branch_scope
from app.config import get_settings
from app.core import erase_customer as E
from app.core import operator_ticket as OT
from app.core import plate as P
from app.core import vehicles as V
from app.core.operations import OperationError, Operations
from app.api.subscribed import (no_subscription_needed, subscribed_write,
                                subscribed_write_or_customer_creating_app,
                                subscribed_write_or_visit)

# The parent router in __init__ already carries /api/v1 — this prefix is appended to it.
router = APIRouter(prefix="/field", tags=["field"])

# Two capabilities, not one. Recording a visit is what every operator does all day; reading the
# customer book is a different privilege, and a shop that hires seasonal help should be able to
# grant the first without the second.
_RECORD = require_capability("operations.record")
_READ = require_capability("operations.read")
# The third: what only the owner or a manager may do. Erasing a customer is irreversible by
# design — the whole point of an erasure is that nothing is left to restore.
_MANAGE = require_capability("operations.manage")


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
    # Shops that work on cars only. A salon never sends it, and the screen never shows the field.
    plate: str = Field(default="", max_length=32)
    operator_id: str = Field(default="", max_length=64)
    # THE PROOF THAT `operator_id` IS HIS TO CLAIM (و-4). `verify-pin` establishes who is saving
    # and used to hand back only a name, so this field was a free string: a device could file its
    # work against any operator in the shop — and `_branch_for` reads exactly this field to decide
    # which BRANCH the visit belongs to, so the branch numbers moved with it. That is the same hole
    # `_branch_for`'s own note describes closing, one field to the left.
    #
    # Empty is allowed and means «no person» — the till sends none, and a shop that never set PINs
    # records visits with no operator at all. What is refused is a NAME WITHOUT A TICKET.
    operator_ticket: str = Field(default="", max_length=200)
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
    # WHEN HE PRESSED SAVE, on his clock (أ-3). The queue on the device holds a visit through an
    # outage and drains it when the signal returns — and it sent only the draft, so nine visits
    # taken through a morning with no coverage were all recorded at the moment the network came
    # back. `_sane_occurred_at` then read 0 and answered «now», which is a defensible default for
    # a value nobody sent and a lie for one that was known and dropped. Peak-hours reports the
    # busiest hour as whenever the shop last reconnected, and the visit confirmation reaches the
    # customer seven hours after he left.
    #
    # The till door has accepted this since it existed; only the field door was missing it, and
    # only the field door has a queue. `_sane_occurred_at` bounds what a device clock may claim.
    occurred_at: int = Field(default=0, ge=0)


@router.post("/visits", status_code=status.HTTP_201_CREATED, dependencies=[Depends(subscribed_write_or_visit), Depends(rate_limit)])
async def record_visit(request: Request, body: VisitIn, background: BackgroundTasks,
                       principal: Principal = Depends(_RECORD)) -> dict:
    """Record a visit. This endpoint is the product, as far as the shop floor is concerned."""
    tenant = _tenant(principal)

    # ── THE SAME GATE THE TILL DOOR HOLDS, ON THE ACT AND NOT THE ROUTE (ك-1) ─────────────────
    # `operations.record` is the identical capability a till's own credential carries, and this
    # route asked nothing more of it — so the licence a shop must buy to point a till at us, and
    # the stable idempotency key a batched retry needs, could both be skipped by calling THIS door
    # with THAT credential instead. `is_machine_subject` answers False for every human operator,
    # so nothing here changes for the field screen's ordinary traffic.
    from app.core.licence import NOT_INCLUDED as _API_NOT_INCLUDED
    from app.core.licence import is_machine_subject, refuses_machine_write

    if is_machine_subject(principal.subject):
        if await refuses_machine_write(
                getattr(request.app.state.container, "api_licence", None),
                tenant, principal.subject):
            return {"recorded": False, "reason": _API_NOT_INCLUDED}
        if not body.idempotency_key:
            # THE KEY ITSELF, AND NOTHING ELSE — this door is not the till door.
            #
            # `till.py` accepts `idempotency_key` OR `invoice_id` OR `occurred_at`, and it may:
            # `_key_for` DERIVES a stable key from whichever it was given. Here nothing derives
            # anything — `record_visit` deduplicates on `idempotency_key` and on nothing else
            # (core/operations.py) — so accepting `occurred_at` would refuse the machine that
            # sends neither and wave through the machine whose retry doubles the visit anyway,
            # while telling it in writing that its retry was safe.
            #
            # A HUMAN IS NOT ASKED FOR ONE, and that is not an oversight: an operator retyping
            # the same visit twice is recording a second real visit.
            return {"recorded": False,
                   "reason": "send idempotency_key — without it a retry cannot be told "
                             "from a second sale"}

    # ── THE PLATE IS REQUIRED WHERE THE VEHICLE IS THE ASSET ──────────────────────────────────
    # A tyre shop could record a visit with the plate box empty, and the row was then unfindable
    # by the one thing that counter searches by: the car. Its cycle is the car's, its reminder says
    # «سيارتك», and its screen looks the customer up by plate before phone — so a plateless visit
    # is half a visit, and nobody notices until a returning customer cannot be found months later.
    #
    # CHECKED HERE, NOT IN core/operations.py, because «does this shop work on cars» is a fact the
    # core does not hold and should not fetch — it takes what it is given and stays pure.
    #
    # AND THE RULE IS ONE LETTER AND ONE DIGIT, NOT THE SAUDI FORMAT (see core/plate.py): a format
    # check refuses temporary, transit, Gulf and diplomatic plates, and the man with a customer
    # waiting types «1» and moves on — which leaves the field required AND meaningless.
    # ONE FLAG, ASKED OF THIS SHOP. It used to be «which trade did he pick at sign-up, and is that
    # trade one of the ones we listed as having vehicles» — an answer chosen once, never editable,
    # and wrong for every shop that started doing cars later.
    tracks_vehicle = await V.VehicleStore(request.app.state.container.datastore).tracks_vehicle(tenant)
    if tracks_vehicle and not P.is_plausible(body.plate):
        # RETURNED, NOT RAISED — the platform strips a refusal's detail, and this refusal is the
        # entire value of the answer to the person holding the phone.
        return {"recorded": False, "reason": P.REFUSAL, "field": "plate"}

    # ── A NAME ON THE VISIT MUST BE A NAME SOMEBODY PROVED (و-4) ──────────────────────────────
    # `verify-pin` now issues a short-lived signed ticket for the operator it confirmed, and this
    # is where the two halves finally meet. An unproven name is dropped rather than refused: the
    # visit is the product and losing it costs the shop a customer, while losing the attribution
    # costs it a column. What must never happen is the attribution being WRONG — «من سجّل هذه
    # الزيارة» and «في أي فرع» are both read off this field.
    operator_id = body.operator_id.strip()
    if operator_id and not OT.verifies(
            request.app.state.container_settings.PII_SALT, tenant, operator_id,
            body.operator_ticket, at=body.occurred_at):
        operator_id = ""

    # Write-ahead. Critical: a visit the log cannot witness must not happen.
    await request.app.state.auditor.record(
        "visit.recorded", actor=principal.subject, tenant=tenant, resource="visit",
        ip=request.client.host if request.client else "")

    try:
        result = await _svc(request).record_visit(
            tenant=tenant, phone=body.phone, service_ids=body.service_ids, name=body.name,
            plate=body.plate, operator_id=operator_id, branch_id=body.branch_id,
            meter=body.meter, note=body.note, custom_service=body.custom_service,
            idempotency_key=body.idempotency_key, occurred_at=body.occurred_at)
    except OperationError as exc:
        # RETURNED, NOT RAISED — the third time this file says it, and the one place it was not
        # done. The plate refusal above and the offer refusal below both return; this raised, and
        # the platform's handler strips `detail` (CWE-209 by design), so the operator with a
        # customer in front of him saw `{"error": "BAD_REQUEST"}`: no field named, no reason. He
        # retries the same input, fails again, and either abandons the visit — the customer leaves
        # the product entirely, no reminder and no points — or registers him a second way.
        #
        # AND THE SENTENCES THEMSELVES WERE ENGLISH. «a phone number is required» is not a refusal
        # an operator in a workshop can act on even when it does arrive; the five reachable ones in
        # core/operations.py are Arabic now.
        return {"recorded": False, "reason": str(exc)}

    # A repeat of the same key is a SUCCESS, not a conflict: the operator's intent was satisfied,
    # and a 409 on a double tap teaches them the screen is unreliable. `duplicate` is reported so
    # a client can tell the difference without being punished for it.
    # THE QUESTION IS «HAVE THE SEAMS RUN?», NOT «IS THIS THE FIRST ATTEMPT?» (ز-7).
    #
    # This read `if not result.duplicate`, which is the wrong question by exactly the case that
    # matters. The seams run after the response: indexing the customer, and emitting the visit that
    # reminders schedules from and insights counts. A pod evicted in that window left the visit
    # saved and none of it done — and then the retry, seeing a duplicate, skipped the seams
    # ALTOGETHER. So the one attempt that could have repaired it was the one guaranteed not to.
    # The customer was never reminded, never indexed, and nothing anywhere said so.
    if not result.visit.seamed_at:
        seams = request.app.state.container.seams
        background.add_task(seams.after_visit, result)

    return {"visit": result.visit.public(), "customer": result.customer.public(),
            "created_customer": result.created_customer, "duplicate": result.duplicate}


@router.get("/customers/recent", dependencies=[Depends(rate_limit)])
async def recent_customers(request: Request, limit: int = 10, branch_id: str = "",
                           principal: Principal = Depends(_READ)) -> dict:
    """The strip along the top of the field screen — today's customers, one tap away."""
    limit = max(1, min(limit, 50))
    rows = await _svc(request).recent_customers(_tenant(principal), limit=limit)
    # HIS BRANCH ONLY — the strip was the one read on this screen that never narrowed. `public()`
    # carries the name, the phone and `last_branch_id`, so a manager scoped to Jeddah opened the
    # field screen and read Riyadh's customers by name and number, ten at a time, without asking
    # for anything. The branch gate did not see it either: it exempts `branch_id`, and the field
    # here is called `last_branch_id`.
    #
    # Unbranched customers stay visible, as everywhere else: a till records no branch, and hiding
    # those would leave a manager looking at a shop that appears to have no customers at all.
    scope = await branch_scope(request.app.state.container.datastore, principal)
    # AND THE BRANCH HE IS CURRENTLY LOOKING AT, from the switcher in the rail. `narrow` can
    # only tighten: an owner filtering to Jeddah sees Jeddah, and a manager asking for a branch
    # he was never granted is answered with his own scope rather than an accusation.
    kept = SCOPE.visible([c.public() for c in rows], SCOPE.narrow(scope, branch_id),
                         field="last_branch_id")
    return {"customers": kept}


@router.get("/ratings", dependencies=[Depends(rate_limit)])
async def ratings(request: Request, stars: int = 0, handled: str = "", branch_id: str = "",
                  limit: int = 50, after: str = "",
                  principal: Principal = Depends(_READ)) -> dict:
    """The console's «التقييمات» tab (rating-app-feature.md phase 5) — every visit a customer
    actually rated, one filterable list.

    `stars` (1-5, 0 = every rank), `handled` ("true"/"false", "" = both) — plain query strings
    rather than a real bool/optional-int, matching this file's own convention of never asking
    FastAPI to coerce a query param that a browser can send as an empty string. See
    VisitStore.ratings' own docstring for `handled=true`'s one known pagination limitation.
    """
    if stars not in (0, 1, 2, 3, 4, 5):
        return {"error": "BAD_REQUEST", "message": "التقييم يجب أن يكون بين 1 و5، أو صفر لكل التقييمات."}
    handled_filter = {"true": True, "false": False, "": None}.get(handled.lower())
    if handled and handled_filter is None:
        return {"error": "BAD_REQUEST", "message": "handled يجب أن تكون true أو false."}
    limit = max(1, min(limit, 100))
    rows, cursor = await _svc(request).ratings(
        _tenant(principal), stars=stars or None, handled=handled_filter,
        branch_id=branch_id, limit=limit, after=after or None)
    # SAME BRANCH DISCIPLINE AS /customers/recent ABOVE — a manager scoped to one branch must not
    # read another branch's ratings by passing a different `branch_id` query param himself.
    scope = await branch_scope(request.app.state.container.datastore, principal)
    kept = SCOPE.visible([v.public() for v in rows], SCOPE.narrow(scope, branch_id),
                         field="branch_id")
    return {"ratings": kept, "next_cursor": cursor}


class RatingHandledIn(BaseModel):
    note: str = Field(default="", max_length=500)


@router.patch("/ratings/{visit_id}/handled",
              dependencies=[Depends(subscribed_write), Depends(rate_limit)])
async def mark_rating_handled(request: Request, visit_id: str, body: RatingHandledIn,
                              principal: Principal = Depends(_RECORD)) -> dict:
    """«تمت المعالجة» — a human read this rating and did something about it. Never automatic; see
    Visit.rating_handled_at's own docstring."""
    try:
        v = await _svc(request).mark_rating_handled(_tenant(principal), visit_id, body.note)
    except OperationError as exc:
        # RETURNED, NEVER RAISED — see record_visit's own comment above on why.
        return {"handled": False, "reason": str(exc)}
    await request.app.state.auditor.record(
        "visit.rating_handled", actor=principal.subject, tenant=_tenant(principal),
        resource=f"visit:{visit_id}", ip=request.client.host if request.client else "")
    return {"handled": True, "visit": v.public()}


@router.get("/customers/by-phone", dependencies=[Depends(rate_limit)])
async def customer_by_phone(request: Request, phone: str,
                            principal: Principal = Depends(_READ)) -> dict:
    """Exact lookup, for the moment the full number has been typed.

    PREFIX lookup is NOT here and must not be added here. It is served by search-service's
    /search/suggest, because a prefix scan over the datastore is a table scan and this sits inside
    a five-second budget. Measured, not assumed: POST /search matches whole tokens, so `96650`
    finds nothing against a stored `966501234567` — the keypad must call suggest.

    AUDITED ON EVERY CALL, HIT OR MISS — the one read in this service that turns an arbitrary
    string an operator typed into "does this customer exist and who is he", which is exactly the
    read an insider abuses (checking a specific number out of curiosity, or probing whether
    someone is a customer here at all). A miss is still worth a row: it is what a numbers-guessing
    probe looks like before it ever finds a hit. The resource carries only the searched number's
    LAST 4 DIGITS, never the number itself — an audit trail that stored the full phone would just
    recreate the exact problem (PII sitting in the clear somewhere new) it exists to catch abuse of.
    """
    await request.app.state.auditor.record(
        "customer.searched_by_phone", actor=principal.subject, tenant=_tenant(principal),
        resource=f"phone-suffix:{phone[-4:]}", ip=request.client.host if request.client else "")
    c = await _svc(request).customer_by_phone_searched(_tenant(principal), phone)
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


class EnsureCustomerIn(BaseModel):
    phone: str = Field(min_length=1, max_length=32)
    name: str = Field(default="", max_length=128)


@router.post("/customers/ensure", dependencies=[Depends(subscribed_write_or_customer_creating_app), Depends(rate_limit)])
async def ensure_customer(request: Request, body: EnsureCustomerIn, background: BackgroundTasks,
                          principal: Principal = Depends(_RECORD)) -> dict:
    """Resolve or create a customer by phone, with no visit attached — `bookings`' console dialog
    needs a `customer_id` before it can create a booking, and this is the SAME resolve-or-create
    act `record_visit` already makes (docs/خطة-تنفيذ-الحجوزات.md §6.2: "نفس الفعل الخلفي الذي
    يستعمله VisitIn, لا إعادة تنفيذ") — `Operations.ensure_customer` is the same code, just
    without a visit riding along.

    SAME CAPABILITY AS RECORDING A VISIT (`operations.record`), because it is the same act minus
    the visit: an operator who may register a customer while recording one may register a customer
    on his own.

    INDEXED HERE TOO, NOT ONLY AFTER A VISIT (a customer booked but not yet
    attended could not be FOUND by his own phone number — `seams.index_customer_row` used to run
    only from `after_visit`, so a fresh customer stayed invisible to the keypad's own search until
    his first visit was confirmed, weeks after the booking that created him). `Seams` already
    names this exact shape "TWO CALLERS, ONE SHAPE" in its own docstring, anticipating a second
    caller — this is it. Backgrounded, same as `record_visit`'s own seam below: the operator is
    not waiting on a search index write to get his `customer_id` back.
    """
    try:
        c = await _svc(request).ensure_customer(_tenant(principal), body.phone, body.name)
    except OperationError as exc:
        # RETURNED, NOT RAISED — same rule as `record_visit` above: the platform strips
        # HTTPException detail on the way out (CWE-209 by design), and the console dialog calling
        # this needs the actual reason to show the operator, not a bare `{"error": "BAD_REQUEST"}`.
        return {"customer": None, "reason": str(exc)}
    seams = request.app.state.container.seams
    background.add_task(seams.index_customer_row, tenant=_tenant(principal), customer_id=c.id,
                        phone=c.phone, name=c.name, plates=[])
    return {"customer": {**c.public(), "subject_ref": c.subject_ref}}


class ResolveIn(BaseModel):
    """Pseudonyms in, customers out. NO TENANT FIELD — see the route."""

    refs: list[str] = Field(default_factory=list, max_length=200)


@router.post("/customers/resolve", dependencies=[Depends(no_subscription_needed), Depends(rate_limit)])
async def resolve_customers(request: Request, body: ResolveIn, branch_id: str = "",
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
    # HIS BRANCH ONLY — the same rule as the strip along the top of the field screen (و-8),
    # and this route is the twin nobody looked at. It answers «من تأخّر»: a LIST, browsed, not
    # one person standing at the counter. `public()` carries the name, the phone and
    # `last_branch_id`, so a manager scoped to Jeddah read Riyadh's overdue customers by name
    # and number — two hundred at a time, which is the page size.
    #
    # A TARGETED LOOKUP IS DIFFERENT and stays open: `by-phone` and the record are one person
    # the operator already has in front of him, and the customer is shared across the chain
    # (§12.4). What narrows is the BROWSE and the HISTORY.
    #
    # Unbranched customers stay visible, as everywhere else: a till records no branch.
    scope = await branch_scope(request.app.state.container.datastore, principal)
    # THE REF IS ECHOED BACK BESIDE EACH CUSTOMER, and it tells the caller nothing he did not
    # send: he asked with these pseudonyms. Without it the answer cannot be PAIRED with the
    # question — unknown refs are simply absent, so position proves nothing — and a caller holding
    # one pseudonym per row (the privacy-request panel holds one per request) could not say which
    # customer belonged to which. `public()` still omits it: this is the route whose job is the join.
    kept = SCOPE.visible([{**c.public(), "subject_ref": c.subject_ref} for c in rows],
                         SCOPE.narrow(scope, branch_id), field="last_branch_id")
    return {"customers": kept}


@router.get("/customers/suggest", dependencies=[Depends(rate_limit)])
async def suggest_customers(request: Request, prefix: str = "", branch_id: str = "",
                            principal: Principal = Depends(_READ)) -> dict:
    """The keypad's suggestion list, narrowed to the reader's branch (ط-3).

    WHY THIS ROUTE EXISTS AT ALL. The console called search-service directly — `/suggest` for the
    terms and `POST /search` for the people. Neither route knows what a branch is, so a supervisor
    scoped to Jeddah typed four digits and read Riyadh's customers by name, phone and plate. It
    walked around the whole of `overdue` and `customers_by_refs` above, because the keypad never
    asked operations anything: the narrowing was in a service the browser talked past.

    AND A FILTER THE BROWSER CHOOSES IS NOT A GUARD. Sending `filters: {branch_id: …}` from the
    console would read the same in a screenshot and mean nothing — the next caller sends whatever
    it likes. The scope is resolved HERE, from the token, by the same `branch_scope` the browse
    routes use.

    A BROWSE, NOT A TARGETED LOOKUP, and the rule at `customers_by_refs` decides which this is: a
    list of candidates from four typed digits is browsing. `by-phone` stays open because a whole
    number is one person the operator already has in front of him.

    TWO CALLS, BECAUSE THE PEER ANSWERS TWO QUESTIONS. `suggest` matches a prefix and returns
    TERMS; `search` matches whole tokens and returns PEOPLE. The typed text is added to the terms
    because an autocomplete deliberately omits the word you have finished typing — without it the
    list vanished at the keystroke that completed the number.

    `null` MEANS «I COULD NOT ASK», and it is not an empty shop. The screen has to say «تعذّر
    البحث»; «لا يوجد عميل» to a man standing at the counter is the one wrong answer here.
    """
    prefix = (prefix or "").strip()
    if not prefix:
        return {"customers": [], "ok": True}
    tenant = _tenant(principal)
    c = request.app.state.container
    index = get_settings().SEARCH_INDEX_NAME
    terms = await c.search.suggest(index=index, tenant=tenant, prefix=prefix)
    if terms is None:
        return {"customers": [], "ok": False}
    words = list(dict.fromkeys([*terms, *prefix.split()]))
    if not words:
        return {"customers": [], "ok": True}
    hits = await c.search.query(index=index, tenant=tenant, text=" ".join(words[:8]), size=8)
    if hits is None:
        return {"customers": [], "ok": False}
    rows = []
    for h in hits:
        f = h.get("fields") or {}
        rows.append({"id": str(h.get("id") or ""),
                     "phone": str(f.get("phone") or ""),
                     "name": str(f.get("name") or "") or None,
                     "plate": str(f.get("plate") or "") or None,
                     # The scope field, and it is dropped from the answer below: the caller has no
                     # use for it and it is what a scoped reader must not be able to enumerate.
                     "branch_id": str(f.get("branch_id") or "")})
    scope = await branch_scope(c.datastore, principal)
    # THE SAME ONE CHOICE, on the visit list too — the switcher governs every screen or it
    # governs none of them, and «one screen narrowed, the one beside it not» is the split it
    # was moved to the rail to close.
    kept = SCOPE.visible(rows, SCOPE.narrow(scope, branch_id), field="branch_id")
    return {"customers": [{k: v for k, v in r.items() if k != "branch_id"} for r in kept],
            "ok": True}


class RenameIn(BaseModel):
    name: str = Field(default="", max_length=120)


@router.patch("/customers/{customer_id}", dependencies=[Depends(subscribed_write), Depends(rate_limit)])
async def rename_customer(request: Request, customer_id: str, body: RenameIn,
                          principal: Principal = Depends(_RECORD)) -> dict:
    """Name a customer who arrived without one (§4.3).

    THE OPERATOR MAY DO IT, not only the owner: he is the one standing in front of the man whose
    name it is, and a correction that has to wait for a manager is a correction that never happens.
    It is the same capability that records the visit — writing a name is smaller than writing a
    visit, and the visit is already his to write.
    """
    c = await _svc(request).rename_customer(_tenant(principal), customer_id, body.name)
    if c is None:
        return {"ok": False, "reason": "لا يوجد عميل بهذا المعرّف"}
    return {"ok": True, "customer": {"id": c.id, "name": c.name}}


@router.post("/customers/{customer_id}/erase", dependencies=[Depends(no_subscription_needed), Depends(rate_limit)])
async def erase_customer(request: Request, customer_id: str, authorization: str = Header(""),
                         principal: Principal = Depends(_MANAGE)) -> dict:
    """«امسح بياناتي» — honoured by the shop that was asked, in the shop's own screen.

    THE ESTABLISHMENT IS THE CONTROLLER. Its customer asks IT, not us, and the PDPL gives him an
    answer within thirty days from the establishment. The erasure engine has been complete for
    months — compliance opens the request, fans it out to every service that holds anything of his,
    and keeps each acknowledgement — and the person who receives the request had no way to start
    it. See core/erase_customer.py for why we start it there rather than deleting anything here.

    NOT THE OPERATOR'S. `operations.manage`, not `operations.record`: recording a visit is what
    the man at the counter does all day, and erasing a customer is the one act on this screen that
    cannot be undone by anybody, including us.

    THE CALLER'S OWN AUTHORIZATION IS FORWARDED. compliance re-checks the capability and re-scopes
    to his tenant, so the erasure is his act under his name — and this service never gains the
    power to erase a customer of an establishment that did not ask.
    """
    c = await _svc(request).customer_for_erasure(_tenant(principal), customer_id)
    if c is None or not c.subject_ref:
        # NOT A 404. The screen renders the same either way, and a distinct status here answers
        # "does this establishment hold this id?" for anyone who can guess one.
        return {"ok": False, "reason": "لا يوجد عميل بهذا المعرّف"}

    # WRITE-AHEAD, like every other irreversible act in this service: an erasure the log cannot
    # witness must not happen, and recording it afterwards would leave the one action a regulator
    # asks about as the one action with no record.
    await request.app.state.auditor.record(
        "customer.erasure_requested", actor=principal.subject, tenant=_tenant(principal),
        resource=f"customer:{customer_id}",
        ip=request.client.host if request.client else "")

    # THE MAP IS RE-ASSERTED BEFORE THE FAN-OUT, AND IT IS A RECONCILING READ, NOT BELT AND BRACES.
    #
    # An erasure reaches exactly the data targets compliance holds for this tenant. The owner's own
    # role carries `compliance.manage` — it has to, because this very button travels on HIS token
    # so the erasure is his act — and the same capability also grants DELETE on those targets. So
    # the shop can narrow its own map, by accident or otherwise, and every erasure afterwards fans
    # out to what is left, every one of those acknowledges, and the request closes COMPLETED. The
    # customer is told his data is gone while a whole service still holds it. Nothing fails.
    #
    # Registration is idempotent by the store's own rule, so re-asserting costs one round trip and
    # restores anything missing. A failure here is REPORTED, never swallowed: an erasure over a map
    # we know to be incomplete is the false «تم» this whole path exists to avoid.
    incomplete = await request.app.state.container.signup.reassert_data_map(_tenant(principal))
    if incomplete:
        return {"ok": False,
                "reason": "تعذّر التأكد من اكتمال خريطة بياناتك، والحذف لم يبدأ. أعد المحاولة."}

    try:
        result = await run_in_threadpool(
            E.erase_subject,
            compliance_url=get_settings().COMPLIANCE_SERVICE_URL,
            authorization=authorization, subject_ref=c.subject_ref)
    except E.EraseFailed as exc:
        # RETURNED, NOT RAISED. The platform strips a refusal's detail on the way out, and «تعذّر»
        # with no reason is what sends an owner to support with a legal deadline running.
        return {"ok": False, "reason": str(exc)}
    return {"ok": True, **result}


@router.get("/privacy-requests", dependencies=[Depends(rate_limit)])
async def privacy_requests(request: Request, principal: Principal = Depends(_MANAGE)) -> dict:
    """What his customers have asked him for, and not yet been answered.

    A RIGHT NOBODY IS TOLD ABOUT IS NOT A RIGHT. The customer taps «احذف بياناتي» on his own page
    and the request lands here; without this list the only way the establishment would learn of it
    is if he also telephoned — which is the situation the page exists to replace.
    """
    rows = await _svc(request).open_privacy_requests(_tenant(principal))
    return {"requests": [r.public() for r in rows]}


@router.post("/privacy-requests/{request_id}/close", dependencies=[Depends(no_subscription_needed), Depends(rate_limit)])
async def close_privacy_request(request: Request, request_id: str,
                                principal: Principal = Depends(_MANAGE)) -> dict:
    """Answered. WHO closed it is kept — «we answered him» is a claim that needs a name on it.

    AND IT IS AUDITED, because the row alone cannot support the claim. The ASK is audited
    (`privacy.requested`, the hour PDPL's thirty-day clock starts) and the ANSWER was not — so the
    two halves of the one thing a regulator asks about lived in different places, and only the
    half that accuses us was in the ledger. Write-ahead, like every other act on this path: a
    closure the log could not witness is a closure we cannot later prove we made.
    """
    tenant = _tenant(principal)
    await request.app.state.auditor.record(
        "privacy.answered", actor=principal.subject, tenant=tenant, resource="privacy_request",
        ip=request.client.host if request.client else "")
    ok = await _svc(request).close_privacy_request(tenant, request_id, principal.subject)
    return {"ok": ok}


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
    if rec is not None:
        # HIS BRANCH ONLY, WHEN HE HAS ONE (§12.4). The customer is shared across the chain — one
        # person, one balance — so the record itself is never hidden; what narrows is the HISTORY,
        # which is where another branch's work would otherwise be readable line by line.
        #
        # Unbranched visits stay visible to everyone: a till sends none, and hiding them would
        # leave a branch manager reading a customer who appears never to have come in.
        scope = await branch_scope(request.app.state.container.datastore, principal)
        rec = {**rec, "visits": SCOPE.visible(list(rec.get("visits") or []), scope)}
    if rec is None:
        # 404 for "not in THIS establishment", which is also the answer when the id belongs to
        # another tenant. Deliberately indistinguishable: a 403 would confirm the id exists
        # somewhere, which is an enumeration oracle across establishments.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND")
    return rec


@router.get("/catalogue", dependencies=[Depends(rate_limit)])
async def catalogue(request: Request, principal: Principal = Depends(_READ)) -> dict:
    """The service grid, and the extra inputs this shop's work needs."""
    tenant = _tenant(principal)
    store = request.app.state.container.datastore
    # THE FIELDS COME WITH THE GRID, and this is the point of answering them here at all.
    #
    # `fields` is a list of descriptors rather than a boolean, so the screen asks «is `plate` among
    # my fields» and never carries its own idea of which shops have plates. A shop that does not
    # work on cars answers an empty list — honest, and it renders the phone and nothing else,
    # which is always valid.
    return {"services": await _svc(request).catalogue(tenant),
            "tracks_vehicle": await V.VehicleStore(store).tracks_vehicle(tenant),
            "fields": await V.fields_for(store, tenant)}

class ApplyOfferIn(BaseModel):
    subject_ref: str = Field(min_length=8, max_length=128)


@router.post("/visits/{visit_id}/offer", dependencies=[Depends(subscribed_write_or_visit), Depends(rate_limit)])
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
        # `_tenant`, NEVER `principal.tenant` — the only line in this module that read the claim
        # raw. It is the same value on every good request, which is why it survived; on a token
        # with no tenant it is "" and this call goes on with an empty establishment instead of the
        # 403 every sibling route answers.
        applied = await ops.apply_offer(tenant=_tenant(principal), visit_id=visit_id,
                                        subject_ref=body.subject_ref)
    except OperationError as e:
        # RETURNED, NEVER RAISED. The platform strips HTTPException detail on the way out, so a
        # raise here reaches the owner as an empty 400 — the refusal he needs to read is the whole
        # value of the answer.
        return {"applied": False, "reason": str(e)}

    if applied is None:
        return {"applied": False, "reason": "لا يوجد عرضٌ ساري يشمل هذه الزيارة"}
    return {"applied": True, "offer": applied}
