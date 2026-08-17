"""The back office — operators, branches and the service catalogue.

A DIFFERENT PRIVILEGE FROM THE FIELD SCREEN, and separated on purpose. Recording a visit is what
everyone does all day; adding an operator, changing a price or deactivating a service is the
owner's. A shop that hires seasonal help must be able to grant the first without the second.

THE PIN IS ATTRIBUTION, NOT AUTHENTICATION — and the distinction decides the whole design.

A four-digit PIN is guessable by construction: ten thousand possibilities, and a colleague standing
beside you can watch it being typed. It is not, and cannot be, what protects an establishment's
data. That is the establishment's session, which is a real token behind a real login.

What the PIN answers is a narrower and genuinely useful question: WHICH of the three people sharing
this tablet recorded that visit. It is asked at SAVE, not at the start of a shift, because the
screen stays open all day and a login per visit would destroy the five-second rule — and the
predictable result of that is one device signed in as one person recording everybody's work, which
is worse than no attribution because it is attribution that lies.

So it is hashed (never stored readable), it is rate-limited (guessing four digits is otherwise
trivial), a wrong one is audited (a pattern of failures is the signal worth having), and it is
never returned by any read.
"""
from __future__ import annotations

import hashlib
import hmac
import time

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from typing import Any

from starlette.concurrency import run_in_threadpool

from app.api.auth import Principal
from app.api.authz import require_capability
from app.api.ratelimit import rate_limit
from app.api.scope import branch_scope
from app.api import scope as SCOPE
from app.core.models import Branch, Operator, Service
from app.core import branches as B
from app.core import operator_ticket as OT
from app.core import seats as S
from app.core import shop_mode as SM
from app.core.signup import SignupRefused
from app.core.stores import BranchStore, OperatorStore, ServiceStore, new_id

# The parent router in __init__ already carries /api/v1 — this prefix is appended to it.
router = APIRouter(prefix="/staff", tags=["staff"])

_MANAGE = require_capability("operations.manage")
_READ = require_capability("operations.read")


def _tenant(p: Principal) -> str:
    if not p.tenant:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "NO_TENANT")
    return p.tenant


def _pin_hash(salt: str, tenant: str, operator_id: str, pin: str) -> str:
    """Salted and bound to the operator.

    Bound to (tenant, operator_id) so the same four digits produce different hashes for different
    people — otherwise a leaked table would show at a glance which operators share a PIN, and
    "1234" would be identifiable across every establishment we host.
    """
    return hmac.new(salt.encode("utf-8"),
                    f"{tenant}|{operator_id}|{pin}".encode("utf-8"),
                    hashlib.sha256).hexdigest()


# ── operators ─────────────────────────────────────────────────────────────────────────────────
class OperatorIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    # Four digits, and no longer. A longer PIN is not meaningfully safer for what this protects,
    # and it IS meaningfully slower to type a hundred times a day — which is the cost that decides
    # whether the product gets used.
    pin: str = Field(min_length=4, max_length=4, pattern=r"^\d{4}$")
    role: str = Field(default="operator", max_length=32)
    branch_id: str = Field(default="", max_length=64)


@router.post("/operators", status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(rate_limit)])
async def create_operator(request: Request, body: OperatorIn,
                          principal: Principal = Depends(_MANAGE)) -> dict:
    tenant = _tenant(principal)
    store = OperatorStore(request.app.state.container.datastore)
    gauges = request.app.state.container.gauges

    # AT THE DOOR, NOT IN A SWEEP. The sixteenth employee on a plan of fifteen is refused here, in
    # the screen where he is being added, with the limit named. A nightly job that finds sixteen
    # and does nothing is a limit that does not exist; one that deactivates somebody fires days
    # later at a person who did not make the mistake (core/seats.py).
    # LIVE ONES ONLY, and the same rule the update route reports by. Counting people who were
    # stopped months ago would make a shop buy seats for employees who no longer work there — and
    # the two counts disagreeing is worse still: whichever the owner is looking at is the wrong one.
    current = len([o for o in await store.list(tenant) if o.active])
    try:
        await S.guard_and_report(gauges, tenant=tenant, key=S.SEATS, current=current)
    except S.SeatLimitReached as exc:
        # RETURNED, NOT RAISED. The platform's error handler strips an HTTPException's detail, so
        # a raised refusal reaches the owner as a bare 403 and the sentence naming his limit —
        # the only part that tells him what to do — is thrown away.
        return JSONResponse(status_code=status.HTTP_402_PAYMENT_REQUIRED,
                            content={"error": "SEAT_LIMIT", "message": str(exc)})

    await request.app.state.auditor.record(
        "operator.created", actor=principal.subject, tenant=tenant, resource="operator",
        ip=request.client.host if request.client else "")

    settings = request.app.state.container_settings
    # HIS BRANCH, IF THE SHOP HAS ONE BY THAT ID. Unlike a visit this is a field on a form we
    # serve, so a bad value here is our bug rather than a till's — but the same rule applies: an
    # employee is not refused over a label, he is recorded without one.
    branch_id = ""
    if body.branch_id.strip():
        branch_id = await B.resolve(BranchStore(request.app.state.container.datastore),
                                    tenant, body.branch_id)
    op = Operator(id=new_id("opr"), tenant=tenant, name=body.name.strip(), role=body.role,
                  branch_id=branch_id, created=int(time.time()))
    op.pin_hash = _pin_hash(settings.PII_SALT, tenant, op.id, body.pin)
    await store.save(op)
    # REPORTED AFTER THE WRITE, and as the whole count rather than a delta. Before the write it
    # would be a lie for as long as the write takes, and a failed write would leave billing
    # believing in an employee who does not exist. Reporting the total means a failed report
    # heals itself on the next change.
    await gauges.report(tenant, S.SEATS, current + 1)
    # public() omits pin_hash — a hash that is never returned cannot be attacked offline by
    # somebody who reached a read endpoint.
    return op.public()


class MemberIn(BaseModel):
    """An employee who gets his own login — not a PIN on a shared tablet."""

    name: str = Field(min_length=1, max_length=128)
    phone: str = Field(min_length=6, max_length=32)
    # LONG ENOUGH TO BE REAL. This account can read a shop's customer list; identity refuses a
    # short one anyway, and refusing here means he is told before the round trip.
    password: str = Field(min_length=8, max_length=256)
    role: str = Field(min_length=1, max_length=32)
    branch_id: str = Field(default="", max_length=64)


@router.post("/members", status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(rate_limit)])
async def hire_member(request: Request, body: MemberIn,
                      principal: Principal = Depends(_MANAGE)) -> dict:
    """Hire somebody: an account he signs in with, a role, and the branch he works at.

    TWO THINGS ARE CREATED AND THEY ARE ONE ACT. The membership lives at identity — that is what a
    token is minted from — and the operator row lives here, which is what the seat gauge counts,
    what a visit is attributed to, and where his branch is written. Creating either alone gives a
    shop half an employee: a login nobody can attribute work to, or a name on a list who cannot
    open anything.

    THE ORDER IS THE MEMBERSHIP FIRST, and it is the recoverable order. If the account is created
    and our row is not, he can sign in and sees a shop that does not know him — visible, and
    repairable by hiring him again (the membership add is idempotent). The reverse leaves a seat
    consumed by somebody who cannot log in at all, and nothing on any screen says why.

    THE SEAT IS CHECKED BEFORE EITHER, because an establishment at its limit must be refused
    before an account exists at identity that we would then have to unwind.
    """
    tenant = _tenant(principal)
    store = OperatorStore(request.app.state.container.datastore)
    gauges = request.app.state.container.gauges

    current = len([o for o in await store.list(tenant) if o.active])
    try:
        await S.guard_and_report(gauges, tenant=tenant, key=S.SEATS, current=current)
    except S.SeatLimitReached as exc:
        return JSONResponse(status_code=status.HTTP_402_PAYMENT_REQUIRED,
                            content={"error": "SEAT_LIMIT", "message": str(exc)})

    branch_id = ""
    if body.branch_id.strip():
        branch_id = await B.resolve(BranchStore(request.app.state.container.datastore),
                                    tenant, body.branch_id)

    # CRITICAL AND WRITE-AHEAD: this is a person being given access to an establishment's data,
    # which is the one family of acts that must be refused rather than performed unrecorded.
    await request.app.state.auditor.record(
        "member.hired", actor=principal.subject, tenant=tenant, resource="member",
        ip=request.client.host if request.client else "")

    try:
        out = await request.app.state.container.signup.hire(
            tenant, phone=body.phone, password=body.password, role=body.role)
    except SignupRefused as exc:
        # RETURNED, NEVER RAISED — the platform strips a raised detail, and «هذا الرقم مسجّل في
        # منشأة أخرى» is the only part of this answer the owner can act on.
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST,
                            content={"error": "NOT_HIRED", "message": str(exc)})

    person_id = out.get("person_id", "")

    # ONE PERSON IS ONE ROW, AND THE PRESS IS NOT THE ACT (ز-10). The id used to be `new_id("opr")`
    # — new on every call — while the membership behind it is keyed by phone at identity and is
    # idempotent. So a double press, or a retry on a slow reply, created a SECOND operator row for
    # the same human: two seats consumed by one employee on a plan the owner is paying per seat
    # for, a name listed twice on his team screen, and `verify-pin` picking whichever row it found
    # first — so the same person's work is attributed to one row today and the other tomorrow.
    #
    # `person_id` is the key identity already deduped for us. Reusing it means the second press
    # overwrites the first row rather than adding one, and the count stays what the owner sees.
    existing = None
    if person_id:
        for row in await store.list(tenant):
            if row.person_id == person_id:
                existing = row
                break

    op = Operator(id=existing.id if existing else new_id("opr"),
                  tenant=tenant, name=body.name.strip(), role=body.role,
                  branch_id=branch_id,
                  created=existing.created if existing else int(time.time()))
    # HIS OWN LOGIN IS HIS IDENTITY, so there is no PIN on this row. `verify-pin` compares against
    # an empty hash and refuses — which is correct: a man with an account does not also need four
    # digits, and giving him one would be a second credential to leak.
    op.person_id = person_id
    await store.save(op)
    # THE COUNT DOES NOT MOVE WHEN NOBODY WAS ADDED. Reporting `current + 1` after re-saving a row
    # that already existed would tell billing the shop grew by an employee it did not hire.
    await gauges.report(tenant, S.SEATS, current if existing else current + 1)
    return op.public()


class OperatorPatch(BaseModel):
    """What an owner changes about somebody after adding them. NOT the PIN — see below."""

    name: str | None = Field(default=None, min_length=1, max_length=128)
    role: str | None = Field(default=None, max_length=32)
    branch_id: str | None = Field(default=None, max_length=64)
    active: bool | None = None


@router.patch("/operators/{operator_id}", dependencies=[Depends(rate_limit)])
async def update_operator(request: Request, operator_id: str, body: OperatorPatch,
                          principal: Principal = Depends(_MANAGE)) -> dict:
    """Move somebody to a branch, rename him, or stop him.

    THE BRANCH IS THE POINT OF THIS ROUTE. `branch_id` was settable at creation and changeable
    nowhere, so an owner who hired somebody before opening his second branch could never say where
    that person now works — and the visit path reads exactly this field to decide where the work
    happened (core/operations.py). A field that decides something and cannot be corrected is worse
    than one that decides nothing.

    DEACTIVATE, NEVER DELETE: `verify-pin` refuses an inactive operator, and old visits still name
    him. An employee who left is history, not a gap.

    AND THE PIN IS NOT HERE. Changing somebody's four digits from the same form that renames him
    invites it to be done casually and read aloud; it is a separate act, and this route not having
    it is the design rather than an omission.
    """
    tenant = _tenant(principal)
    store = OperatorStore(request.app.state.container.datastore)
    op = await store.get(tenant, operator_id)
    if op is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND")

    branch_id = op.branch_id
    if body.branch_id is not None:
        # CHECKED AGAINST HIS OWN SHOP'S BRANCHES, and an empty string means «كل الفروع» — the
        # state every shop starts in. An id we do not recognise resolves to that same state rather
        # than pinning him to a place that does not exist.
        branch_id = await B.resolve(BranchStore(request.app.state.container.datastore),
                                    tenant, body.branch_id)

    await request.app.state.auditor.record(
        "operator.updated", actor=principal.subject, tenant=tenant,
        resource=f"operator:{operator_id}", ip=request.client.host if request.client else "")

    # ── STOPPING HIM MUST STOP HIM ────────────────────────────────────────────────────────────
    #
    # This row is not his access. `hire` created two things — the membership at identity, which is
    # what a token is minted from, and this row — and until now `active=False` wrote only the row.
    # He signed in the same evening with the same password. Worse, an inactive row narrows nobody,
    # and a person nothing narrows reads the WHOLE establishment: being dismissed promoted him
    # from his own branch to every branch.
    #
    # THE MEMBERSHIP GOES FIRST AND A FAILURE REFUSES. Writing "stopped" on a screen while the
    # login still works is precisely the lie being fixed; a row still marked active after a failed
    # revoke is at least true.
    stopping = body.active is False and op.active
    if stopping and op.person_id:
        try:
            await request.app.state.container.signup.revoke(tenant, op.person_id)
        except SignupRefused as exc:
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST,
                                content={"error": "NOT_STOPPED", "message": str(exc)})

    # AND HE IS NOT BROUGHT BACK BY A TOGGLE. His membership is gone, and only a password nobody
    # here has can mint another; flipping this flag would return a name to «فريقي» that consumes a
    # seat and cannot open the app — the half-employee `hire` refuses to create.
    if body.active is True and not op.active and not op.person_id:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "REHIRE_REQUIRED",
                     "message": "تم إلغاء دخوله عند إيقافه. أضِفه من جديد ليعمل حسابه."})

    op.name = body.name.strip() if body.name is not None else op.name
    op.role = body.role if body.role is not None else op.role
    op.branch_id = branch_id
    op.active = body.active if body.active is not None else op.active
    # HIS ROW STAYS, HIS LOGIN DOES NOT. Old visits still name him — an employee who left is
    # history, not a gap — but the link to a membership that no longer exists is cleared, so
    # nothing later mistakes it for a live account.
    if stopping:
        op.person_id = ""
    await store.save(op)
    # SEATS ARE REPORTED AGAIN, because stopping somebody frees his seat — a gauge is the CURRENT
    # value, and an owner who deactivated two people must not be refused his next hire.
    await request.app.state.container.gauges.report(
        tenant, S.SEATS, len([o for o in await store.list(tenant) if o.active]))
    return op.public()


@router.get("/operators", dependencies=[Depends(rate_limit)])
async def list_operators(request: Request, principal: Principal = Depends(_READ)) -> dict:
    """«فريقي» — and HIS branch's team, not the chain's.

    FOUND BY THE GATE, not by the audit. `Operator.public()` carries the name, the role and the
    branch, and this route handed every branch's staff to anyone who could read — so a manager
    scoped to Jeddah read the whole chain's roster, which is the same widening as the customer
    strip (و-8) wearing different rows.

    Unbranched operators stay visible to everyone, exactly as unbranched visits do: a shop in
    the default central mode gives nobody a branch, and hiding those would empty the screen.
    """
    tenant = _tenant(principal)
    rows = await OperatorStore(request.app.state.container.datastore).list(tenant)
    scope = await branch_scope(request.app.state.container.datastore, principal)
    return {"operators": SCOPE.visible([o.public() for o in rows], scope)}


class PinVerifyIn(BaseModel):
    operator_id: str = Field(min_length=1, max_length=64)
    pin: str = Field(min_length=4, max_length=4, pattern=r"^\d{4}$")


@router.post("/operators/verify-pin", dependencies=[Depends(rate_limit)])
async def verify_pin(request: Request, body: PinVerifyIn,
                     principal: Principal = Depends(_READ)) -> dict:
    """Confirm which operator is saving. Called by the field screen at the moment of saving.

    Rate-limited like every route here, and that is what makes a four-digit secret defensible at
    all: ten thousand possibilities fall in minutes to an unthrottled endpoint.
    """
    tenant = _tenant(principal)
    settings = request.app.state.container_settings
    op = await OperatorStore(request.app.state.container.datastore).get(tenant, body.operator_id)

    expected = op.pin_hash if op else ""
    candidate = _pin_hash(settings.PII_SALT, tenant, body.operator_id, body.pin)
    # compare_digest on both paths, and an unknown operator takes the same path as a wrong PIN:
    # one answer for "no such operator", "wrong PIN" and "deactivated" (CWE-203/208). Anything
    # else lets a caller enumerate who works here.
    ok = bool(op) and op.active and hmac.compare_digest(expected, candidate)

    if not ok:
        # Audited. One failure is a fat finger; a pattern of them is the signal worth having, and
        # it cannot be seen if failures are not recorded.
        await request.app.state.auditor.record(
            "operator.pin_rejected", actor=principal.subject, tenant=tenant,
            resource=f"operator:{body.operator_id}",
            ip=request.client.host if request.client else "")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "PIN_REJECTED")

    # AND IT ISSUES THE PROOF, which it never used to. Confirming an operator and then handing back
    # only his name left the visit that followed to name whoever it liked in `operator_id` — and
    # that field decides which BRANCH the work is filed under. See core/operator_ticket.py.
    return {"operator": op.public(),
            "ticket": OT.issue(settings.PII_SALT, tenant, body.operator_id),
            "ticket_ttl": OT.TTL_SECONDS}


# ── how this establishment runs its branches ──────────────────────────────────────────────────
class ModeIn(BaseModel):
    mode: str = Field(min_length=1, max_length=32)


def _modes_available(request: Request) -> set[str]:
    """Which modes this deployment can actually honour.

    PER-BRANCH NEEDS A SENDING IDENTITY PER NUMBER, and until that exists every message resolves
    one credential per establishment — so a shop switched into it would keep sending from the one
    number while its screens promised otherwise. Configuration rather than a constant, so the day
    it ships is a values change and not a release.
    """
    modes = {SM.CENTRAL}
    if getattr(request.app.state.container_settings, "BRANCH_MODE_PER_BRANCH_READY", False):
        modes.add(SM.PER_BRANCH)
    return modes


@router.get("/mode", dependencies=[Depends(rate_limit)])
async def read_mode(request: Request, principal: Principal = Depends(_READ)) -> dict:
    """Central or per-branch — and whether the second is offered at all.

    `available` IS PART OF THE ANSWER, not a fact the screen may assume. A choice rendered as
    selectable while its plumbing is half-built is the defect this product keeps finding: a control
    with nothing behind it. The screen shows both, explains both, and offers what is real.
    """
    c = request.app.state.container
    row = await SM.ModeStore(c.datastore).get(_tenant(principal))
    return {**row, "available": SM.PER_BRANCH in _modes_available(request)}


@router.put("/mode", dependencies=[Depends(rate_limit)])
async def set_mode(request: Request, body: ModeIn,
                   principal: Principal = Depends(_MANAGE)) -> dict:
    """Move to per-branch. One way, and never back from this screen — see core/shop_mode.py."""
    tenant = _tenant(principal)
    store = SM.ModeStore(request.app.state.container.datastore)
    try:
        row = await store.set(tenant, body.mode,
                              available=SM.PER_BRANCH in _modes_available(request))
    except SM.ModeError as exc:
        # RETURNED, NEVER RAISED. The three refusals differ for the owner — an unknown value, a
        # mode not yet live, and the one-way rule — and the platform strips a raised detail.
        return JSONResponse(status_code=status.HTTP_409_CONFLICT,
                            content={"error": "MODE_REFUSED", "message": str(exc)})
    # RECORDED AFTER IT HAPPENED, not before it was allowed. An audit line written on the way in
    # says a shop changed its mode on the day it was refused — and the one question this record
    # exists to answer, months later, is when the change was actually made.
    await request.app.state.auditor.record(
        "shop.mode_changed", actor=principal.subject, tenant=tenant, resource="shop_mode",
        ip=request.client.host if request.client else "")
    return row


class ShopNameIn(BaseModel):
    name: str = Field(min_length=1, max_length=256)


@router.put("/shop-name", dependencies=[Depends(rate_limit)])
async def set_shop_name(request: Request, body: ShopNameIn,
                        principal: Principal = Depends(_MANAGE)) -> Any:
    """The shop's name — ONE name, and the owner can change it.

    IT IS CAPTURED ONCE AT SIGNUP AND WAS PERMANENT — a browser autofilling a password into that
    box left an owner reading garbage at the top of his own account screen for good. This route
    is the one place the name is written, and `ci/check_a_shop_has_one_name.py` keeps it the only
    name there is.

    WHY WE PROXY IT. The registry's rename is INTERNAL — service-to-service, on the internal
    token — because a tenant renaming itself directly is a user-tier surface the platform does
    not offer. So the owner's edit arrives here, on his own token and his own capability, and
    this service makes the internal call with the tenant taken from the TOKEN and never from the
    body: a caller who can name the tenant can name somebody else's.
    """
    tenant = _tenant(principal)
    s = request.app.state.container_settings
    base = (getattr(s, "TENANT_SERVICE_URL", "") or "").rstrip("/")
    if not base:
        # NOT CONFIGURED IS SAID OUT LOUD, never rendered as success — the owner would retype
        # his name, read «تم», and find the old one still there on the next screen.
        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            content={"error": "NOT_CONFIGURED",
                                     "message": "تعذّر حفظ الاسم — سجلّ المنشآت غير مُهيّأ لدينا."})
    from app.core.signup import Http

    http = Http(timeout=getattr(s, "SIGNUP_TIMEOUT_SECONDS", 10),
                internal_token=s.INTERNAL_SERVICE_TOKEN)
    code, out = await run_in_threadpool(
        http.call, f"{base}/internal/tenants/{tenant}",
        method="PATCH", body={"name": body.name.strip()}, internal=True)
    if code >= 400:
        # THE REGISTRY'S REFUSAL IS THE REGISTRY'S. A name it rejects is one it can explain;
        # inventing a sentence of our own here would answer for a rule that is not ours.
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST,
                            content={"error": "RENAME_REFUSED",
                                     "message": "تعذّر حفظ الاسم. جرّب اسماً آخر.",
                                     "detail": out})
    await request.app.state.auditor.record(
        "shop.renamed", actor=principal.subject, tenant=tenant, resource="tenant",
        ip=request.client.host if request.client else "")
    return {"name": str(out.get("name") or body.name.strip())}


# ── branches ──────────────────────────────────────────────────────────────────────────────────
class BranchIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)


class BranchPatch(BaseModel):
    """Rename, close, reopen. NO DELETE — see `update_branch`."""

    name: str | None = Field(default=None, min_length=1, max_length=128)
    active: bool | None = None


def _live(rows: list[Branch]) -> int:
    return len([b for b in rows if b.active])


@router.post("/branches", status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(rate_limit)])
async def create_branch(request: Request, body: BranchIn,
                        principal: Principal = Depends(_MANAGE)) -> dict:
    tenant = _tenant(principal)
    store = BranchStore(request.app.state.container.datastore)
    gauges = request.app.state.container.gauges

    # HIS MAIN BRANCH IS ONE OF THEM, and this is where the base plan's single branch is spent.
    # An establishment that has never opened «فريقي» has no row yet, so it is created before the
    # count — otherwise his first added branch would be counted as one while he owns two.
    await B.ensure_main(store, tenant=tenant)
    # LIVE ONES ONLY. A branch he closed is history on old visits, not capacity he keeps paying
    # for — counting it would make «فرع إضافي» a purchase that buys back a place he shut down.
    current = _live(await store.list(tenant))
    try:
        await S.guard_and_report(gauges, tenant=tenant, key=S.BRANCHES, current=current)
    except S.SeatLimitReached as exc:
        return JSONResponse(status_code=status.HTTP_402_PAYMENT_REQUIRED,
                            content={"error": "BRANCH_LIMIT", "message": str(exc)})

    await request.app.state.auditor.record(
        "branch.created", actor=principal.subject, tenant=tenant, resource="branch",
        ip=request.client.host if request.client else "")
    b = Branch(id=new_id("brn"), tenant=tenant, name=body.name.strip(), created=int(time.time()))
    await store.save(b)
    await gauges.report(tenant, S.BRANCHES, current + 1)
    return b.public()


@router.patch("/branches/{branch_id}", dependencies=[Depends(rate_limit)])
async def update_branch(request: Request, branch_id: str, body: BranchPatch,
                        principal: Principal = Depends(_MANAGE)) -> dict:
    """Rename a branch, or close one — and NEVER delete one.

    DEACTIVATE RATHER THAN DELETE, the same rule the service catalogue follows above and for a
    harder reason: visits, points movements and schedules all carry a `branch_id` as a plain
    string, so deleting the row would leave a year of records pointing at a place with no name —
    and the branch table would report those visits under an id nobody recognises.

    THE MAIN BRANCH CANNOT BE CLOSED. It is what an unrecognised branch falls back to and the one
    place a shop with no others has; closing it would leave the establishment with nowhere to
    record a visit. Renaming it is his — «الفرع الرئيسي» is our word, not his shop's.

    REOPENING IS GUARDED LIKE AN ADDITION, because it is one: it puts a place back into service
    and a plan that allows one branch must not be passed by closing and reopening.
    """
    tenant = _tenant(principal)
    store = BranchStore(request.app.state.container.datastore)
    gauges = request.app.state.container.gauges

    b = await store.get(tenant, branch_id)
    if b is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND")

    if body.active is False and B.is_main(branch_id):
        # RETURNED, NEVER RAISED — the platform's handler strips a raised detail, and the sentence
        # naming the rule is the only useful part of this answer.
        return JSONResponse(status_code=status.HTTP_409_CONFLICT,
                            content={"error": "MAIN_BRANCH",
                                     "message": "الفرع الرئيسي لا يُغلق. غيّر اسمه إن أردت."})

    rows = await store.list(tenant)
    if body.active is True and not b.active:
        try:
            await S.guard_and_report(gauges, tenant=tenant, key=S.BRANCHES, current=_live(rows))
        except S.SeatLimitReached as exc:
            return JSONResponse(status_code=status.HTTP_402_PAYMENT_REQUIRED,
                                content={"error": "BRANCH_LIMIT", "message": str(exc)})

    await request.app.state.auditor.record(
        "branch.updated", actor=principal.subject, tenant=tenant,
        resource=f"branch:{branch_id}", ip=request.client.host if request.client else "")

    if body.name is not None:
        b.name = body.name.strip()
    if body.active is not None:
        b.active = body.active
    await store.save(b)
    # THE WHOLE COUNT, RECOMPUTED — a gauge is reported, never incremented (core/seats.py). The
    # saved row is the one in `rows` by identity only if the store returned the same object, so
    # the live count is taken from the list with this row's new state substituted in.
    await gauges.report(tenant, S.BRANCHES,
                        _live([b if r.id == b.id else r for r in rows]))
    return b.public()


@router.get("/branches", dependencies=[Depends(rate_limit)])
async def list_branches(request: Request, principal: Principal = Depends(_READ)) -> dict:
    """His places — and the main one is created here if it is somehow missing.

    A WRITE ON A READ, AND IT EARNS ITS PLACE. Signup creates the main branch (core/signup.py),
    but every establishment that existed before that step did not get one, and there is no
    migration to run — the rule is that a repair belongs in the code that needs the row, not in a
    script somebody has to remember. `ensure_main` is keyed on a fixed id, so this is one write the
    first time a shop opens the screen and none ever after.
    """
    store = BranchStore(request.app.state.container.datastore)
    tenant = _tenant(principal)
    await B.ensure_main(store, tenant=tenant)
    rows = await store.list(tenant)

    # ── HOW MANY HE MAY HAVE, BECAUSE THE SCREEN CANNOT GUESS IT (هـ-3) ────────────────────────
    # «فريقي» locked its branches tab on whether the caller holds `operations.list_branches` —
    # a ROLE fact — and wrote a PLAN sentence on the lock. Both halves were wrong at once: an
    # owner whose plan allows one branch holds the capability, saw no lock at all, and met the
    # refusal only after typing a name; and a supervisor without the capability was told
    # «الفروع متاحة في باقة أعلى» about a plan his shop may well already be paying for.
    #
    # So the entitlement travels with the read, exactly as `shop_mode.available` does.
    #
    # -1 IS «NO KNOWN CEILING» AND IT COVERS TWO CASES: an unlimited plan, and a billing we could
    # not reach — `allows_one_more` fails open by design (core/seats.py). Neither may draw a lock:
    # telling a paying shop it has not paid is the worst sentence in the product, and an outage
    # must never be the thing that says it.
    #
    # AND THE FIRST HALF OF THE SAME ANSWER TRAVELS TOO — «may he open ONE MORE, right now». The
    # limit alone only closes the tab for a shop whose plan allows exactly one branch. A shop
    # allowed three and holding three sees an open tab and a live «إضافة فرع», types a name, and
    # meets the refusal at the end — the same journey this finding is about, reached at a
    # different number. The gauge already computes both; taking only `[1]` threw away the half
    # that answers the button.
    may_add, limit = await request.app.state.container.gauges.allows_one_more(
        tenant, S.BRANCHES, _live(rows))
    return {"branches": [b.public() for b in rows], "branch_limit": int(limit),
            "may_add_branch": bool(may_add)}


# ── the service catalogue ─────────────────────────────────────────────────────────────────────
class ServiceIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    # 0 means "no natural cycle" — a one-off repair generates no reminder. Explicitly a valid
    # value rather than a missing one, because a default of 30 would schedule a reminder for a
    # puncture repair and teach a customer that our messages are noise.
    cycle_days: int = Field(default=0, ge=0, le=3650)
    # Minor units. No float ever touches an amount.
    price_minor: int = Field(default=0, ge=0)
    sort: int = Field(default=0, ge=0, le=9999)


@router.get("/services", dependencies=[Depends(rate_limit)])
async def list_services(request: Request, include_retired: bool = False,
                        principal: Principal = Depends(_MANAGE)) -> dict:
    """The OWNER's catalogue, which is not the field grid.

    /field/catalogue answers what an operator may record a visit against, and it is right that a
    retired service is absent from it. But the same list was the only one there was, so a service
    stopped from the management screen vanished from the management screen — and «تفعيل» had
    nothing left to act on. The same shape of bug as the rewards table, found the same way: by
    stopping something and looking for it.

    Gated on `operations.manage`, not read: this is the list you edit, and an operator has no
    business seeing what the shop has retired.
    """
    rows = await ServiceStore(request.app.state.container.datastore).list(
        _tenant(principal), active_only=not include_retired)
    return {"services": [s.public() for s in rows]}


@router.post("/services", status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(rate_limit)])
async def create_service(request: Request, body: ServiceIn,
                         principal: Principal = Depends(_MANAGE)) -> dict:
    tenant = _tenant(principal)
    await request.app.state.auditor.record(
        "service.created", actor=principal.subject, tenant=tenant, resource="service",
        ip=request.client.host if request.client else "")
    s = Service(id=new_id("srv"), tenant=tenant, name=body.name.strip(),
                cycle_days=body.cycle_days, price_minor=body.price_minor, sort=body.sort,
                created=int(time.time()))
    await ServiceStore(request.app.state.container.datastore).save(s)
    return s.public()


class ServicePatch(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    cycle_days: int | None = Field(default=None, ge=0, le=3650)
    price_minor: int | None = Field(default=None, ge=0)
    active: bool | None = None
    sort: int | None = Field(default=None, ge=0, le=9999)


@router.patch("/services/{service_id}", dependencies=[Depends(rate_limit)])
async def update_service(request: Request, service_id: str, body: ServicePatch,
                         principal: Principal = Depends(_MANAGE)) -> dict:
    """Edit a catalogue entry.

    DEACTIVATE rather than delete — `active: false`. Deleting a service would orphan every visit
    that references it, and a shop that stops offering something still needs last year's records
    to make sense.
    """
    tenant = _tenant(principal)
    store = ServiceStore(request.app.state.container.datastore)
    s = await store.get(tenant, service_id)
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND")

    await request.app.state.auditor.record(
        "service.updated", actor=principal.subject, tenant=tenant,
        resource=f"service:{service_id}", ip=request.client.host if request.client else "")

    for fld in ("name", "cycle_days", "price_minor", "active", "sort"):
        val = getattr(body, fld)
        if val is not None:
            setattr(s, fld, val.strip() if isinstance(val, str) else val)
    await store.save(s)
    return s.public()
