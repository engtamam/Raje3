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

import hmac
import time
import urllib.error
import urllib.parse
import urllib.request

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from typing import Any

from starlette.concurrency import run_in_threadpool

from app.api.auth import Principal
from app.api.authz import require_any_capability, require_capability
from app.api.ratelimit import rate_limit
from app.api.scope import branch_scope
from app.api import scope as SCOPE
from app.core.models import (ASSIGNMENT_MODES, PROCEDURE_STEP_SEVERITIES, Branch, Operator,
                             OperatorStepStat, Package, ProcedureStep, Service)
from app.core import branches as B
from app.core import operator_ticket as OT
from app.core import ai_notes as AN
from app.core import ai_toggle as AT
from app.core import msg_limits as ML
from app.core import scheduling as SCHED
from app.core import seats as S
from app.core import shop_mode as SM
from app.core import vehicles as V
from app.core import whatsapp_auto_register as WAR
from app.core.signup import SignupRefused
from app.core.stores import (BranchStore, OperatorStepStatStore, OperatorStore, PackageStore,
                             ProcedureStepStore, ServiceStore, TranslationStore, new_id)
from app.core.translations import TARGET_LOCALES, entry_id as translation_entry_id
from app.core.translations import resolve as resolve_translation
from app.api.subscribed import no_subscription_needed, subscribed_write

# The parent router in __init__ already carries /api/v1 — this prefix is appended to it.
router = APIRouter(prefix="/staff", tags=["staff"])

_MANAGE = require_capability("operations.manage")
_READ = require_capability("operations.read")
# A NARROWER DOOR, ONLY FOR THE CATALOGUE ("سوي للخدمات وحدة تهتم بالخدمات من
# تعديل وانشاء وغيرها") — `operations.manage` also creates staff and branches and renames the
# shop, which is why it stayed owner/manager-only. A role that should touch the SERVICE catalogue
# and nothing else now can, without inheriting the rest of what `operations.manage` grants. A
# SINGLE capability, not an OR of two — `ci/check_capability_truth.py` reads exactly one name per
# route, so owner/manager hold `operations.manage_services` explicitly too (roles.json), same
# shape as `bookings.manage` sitting beside `bookings.write`.
_MANAGE_SERVICES = require_capability("operations.manage_services")
# A plain field operator ("الموظف الميداني") holds `bookings.read`/
# `bookings.write` but not `operations.read` — so /staff/branches (this route's OWN body already
# narrows by branch_scope, exactly like every other scoped read) answered him 403, and the
# console's Bookings screen — which genuinely needs a branch_id, the server refuses `list_bookings`
# without one — could not learn even his own single branch. It read to him as «لا فروع بعد» (no
# branches EXIST), which was false: he simply could not list them.
#
# `require_any_capability`, not a role change: this narrowly reopens ONE already-self-narrowing
# read to whoever needs a branch to work with bookings, without touching `_READ`'s other routes
# (mode, vehicles — neither of which a field operator needs). Declared TWICE in user_actions.py
# under two ids/capabilities so BOTH audiences see it in their own catalogue; the route accepts
# either, which is why this binds `require_any_capability` and is deliberately outside
# ci/check_capability_truth.py's single-capability check (see that gate's own docstring — it only
# tracks bare `require_capability`).
_READ_BRANCHES = require_any_capability("operations.read", "bookings.read", "bookings.write")
# THE SAME BUG, ONE ROUTE OVER: the Bookings screen's day view needs the
# BRANCH'S TEAM to attribute a booking and to draw the week-view staff picker — it calls
# `/staff/operators` unconditionally on mount, same as it does `/staff/branches`. This comment
# above claimed "none of which a field operator needs" the day it was written; it was wrong about
# this one route, and a field operator saw «تعذّرت قراءة فريق العمل» for the same 403 reason his
# branch list used to fail for. `list_operators` already narrows by `branch_scope`/`SCOPE.visible`
# on its own — the gate was the only thing standing between a field operator and his own team.
_READ_OPERATORS_FOR_BOOKINGS = require_any_capability("operations.read", "bookings.read", "bookings.write")
# SHOP-TO-SHOP COUPONS — two doors, deliberately different widths (owner's own requirement):
# `_GRANT_COUPON` is what the visit-recording flow itself checks (field.py), open to any role
# that may record a visit — a grant riding on a real, logged act. `_GRANT_COUPON_DIRECT` gates
# THIS file's own standalone `/coupons/grant` — a grant with no visit behind it at all, so it
# stays owner/manager/supervisor only (roles.json). `_GRANT_COUPON_ANY` is only for the shared
# read screens (history/stats) below, where either door's holder may see what was granted.
_GRANT_COUPON = require_capability("operations.grant_coupon")
_GRANT_COUPON_DIRECT = require_capability("operations.grant_coupon_direct")
_GRANT_COUPON_ANY = require_any_capability(
    "operations.grant_coupon", "operations.grant_coupon_direct")
# STALE AS OF THE SAME DAY, same conversation, later: the seeded "operator"
# role above no longer HOLDS `bookings.read`/`bookings.write` at all — two operators sharing one
# schedule could edit or cancel each other's booking, and the fix was to take booking away from
# the role entirely (roles.seed.json / deploy/seed/roles.json), not to keep narrowing who can read
# around it. `_READ_BRANCHES` and `_READ_OPERATORS_FOR_BOOKINGS` stay — they are still the correct
# door for any principal who legitimately holds `bookings.*` without `operations.read` (a
# supervisor already carries both; a future or shop-defined role might not) — but neither one
# grants a plain field operator anything any more, because he does not reach this gate at all.


def _tenant(p: Principal) -> str:
    if not p.tenant:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "NO_TENANT")
    return p.tenant


# MOVED to core/operator_ticket.py (2026-09-14) as `pin_hash` — the till's own
# `POST /till/operators/verify-pin` needed the identical formula, and a second copy here is a
# second place for the two to drift apart. `OT.pin_hash` is this exact function, unchanged.
_pin_hash = OT.pin_hash


# ── operators ─────────────────────────────────────────────────────────────────────────────────
class OperatorIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    # Four digits, and no longer. A longer PIN is not meaningfully safer for what this protects,
    # and it IS meaningfully slower to type a hundred times a day — which is the cost that decides
    # whether the product gets used.
    pin: str = Field(min_length=4, max_length=4, pattern=r"^\d{4}$")
    role: str = Field(default="operator", max_length=32)
    # REQUIRED, NOT DESCRIPTIVE — every operator now names a real branch at
    # the moment he is added, the same way `till.py`'s own door already requires one on a sale.
    # No silent «كل الفروع» default: an owner with one branch still picks «الفرع الرئيسي»
    # explicitly, so the choice is a fact he made rather than one we guessed for him.
    branch_id: str = Field(min_length=1, max_length=64)


@router.post("/operators", status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(subscribed_write), Depends(rate_limit)])
async def create_operator(request: Request, body: OperatorIn,
                          principal: Principal = Depends(_MANAGE)) -> dict:
    tenant = _tenant(principal)
    store = OperatorStore(request.app.state.container.datastore)
    gauges = request.app.state.container.gauges

    # THE SHARED-TABLET EMPLOYEE IS SWITCHED OFF ON THIS DEPLOYMENT (config `PIN_OPERATORS_ENABLED`).
    #
    # The whole path is built and kept — the form, this route, `verify-pin`, the five-minute proof —
    # and it is simply not what the product is sold on today: every employee gets an account on his
    # own phone. Hiding the control in the console alone would leave the capability live to anybody
    # who kept a tab open or replayed a request, and a switch that only changes a screen is the
    # exact defect this codebase keeps finding. So the door answers too.
    if not getattr(request.app.state.container_settings, "PIN_OPERATORS_ENABLED", False):
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={
            "error": "PIN_OPERATORS_OFF",
            "message": "إضافة موظف برمز على الجهاز غير مفعّلة. أضِفه بحسابٍ يدخل به من جوّاله."})

    # AT THE DOOR, NOT IN A SWEEP. The sixteenth employee on a plan of fifteen is refused here, in
    # the screen where he is being added, with the limit named. A nightly job that finds sixteen
    # and does nothing is a limit that does not exist; one that deactivates somebody fires days
    # later at a person who did not make the mistake (core/seats.py).
    # LIVE ONES ONLY, and the same rule the update route reports by. Counting people who were
    # stopped months ago would make a shop buy seats for employees who no longer work there — and
    # the two counts disagreeing is worse still: whichever the owner is looking at is the wrong one.
    # THE COUNT AND THE INSERT ARE ONE ACT OR THE CAP IS DECORATION. Everything from the count to
    # the write happens inside the establishment's lane; two managers hiring in the same
    # millisecond are serialised rather than both told there is room (core/seats.py).
    # CHECKED BEFORE THE SEAT CLAIM AND THE AUDIT RECORD, not inside them — both are write-ahead
    # acts (a seat consumed, «operator.created» logged) that must never fire for an operator who
    # is then refused for lacking a real branch.
    try:
        branch_id = await B.resolve_required(
            BranchStore(request.app.state.container.datastore), tenant, body.branch_id)
    except B.BranchRequired:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={
            "error": "BRANCH_REQUIRED", "message": "اختر فرعاً حقيقياً لهذا الموظف."})

    try:
        async with S.claiming(request.app.state.container.datastore,
                              tenant=tenant, key=S.SEATS, now=time.time()):
            current = len([o for o in await store.list(tenant) if o.active])
            await S.guard_and_report(gauges, tenant=tenant, key=S.SEATS, current=current)

            await request.app.state.auditor.record(
                "operator.created", actor=principal.subject, tenant=tenant, resource="operator",
                ip=request.client.host if request.client else "")

            settings = request.app.state.container_settings
            op = Operator(id=new_id("opr"), tenant=tenant, name=body.name.strip(), role=body.role,
                          branch_id=branch_id, created=int(time.time()))
            op.pin_hash = _pin_hash(settings.PII_SALT, tenant, op.id, body.pin)
            await store.save(op)
            # REPORTED AFTER THE WRITE, and as the whole count rather than a delta. Before the
            # write it would be a lie for as long as the write takes, and a failed write would
            # leave billing believing in an employee who does not exist. Reporting the total means
            # a failed report heals itself on the next change.
            await gauges.report(tenant, S.SEATS, current + 1)
    except S.SeatClaimBusy as exc:
        return JSONResponse(status_code=status.HTTP_409_CONFLICT,
                            content={"error": "SEAT_BUSY", "message": str(exc)})
    except S.SeatLimitReached as exc:
        # RETURNED, NOT RAISED. The platform's error handler strips an HTTPException's detail, so
        # a raised refusal reaches the owner as a bare 403 and the sentence naming his limit —
        # the only part that tells him what to do — is thrown away.
        return JSONResponse(status_code=status.HTTP_402_PAYMENT_REQUIRED,
                            content={"error": "SEAT_LIMIT", "message": str(exc)})
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
    # REQUIRED — see OperatorIn's own note.
    branch_id: str = Field(min_length=1, max_length=64)


@router.post("/members", status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(subscribed_write), Depends(rate_limit)])
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

    # CHECKED BEFORE ANY OF IT — see create_operator's own note on why this cannot live inside the
    # seat/audit lane.
    try:
        branch_id = await B.resolve_required(
            BranchStore(request.app.state.container.datastore), tenant, body.branch_id)
    except B.BranchRequired:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={
            "error": "BRANCH_REQUIRED", "message": "اختر فرعاً حقيقياً لهذا الموظف."})

    # ONE LANE, AND IT COVERS THE MEMBERSHIP TOO. The seat is spent by the pair (identity account,
    # operator row), so the lane must not be released between them: two hires racing would both
    # count four, both create an account, and the second would find the first's row only after
    # paying for it (core/seats.py).
    try:
        async with S.claiming(request.app.state.container.datastore,
                              tenant=tenant, key=S.SEATS, now=time.time()):
            current = len([o for o in await store.list(tenant) if o.active])
            await S.guard_and_report(gauges, tenant=tenant, key=S.SEATS, current=current)

            # CRITICAL AND WRITE-AHEAD: this is a person being given access to an establishment's
            # data, which is the one family of acts that must be refused rather than performed
            # unrecorded.
            await request.app.state.auditor.record(
                "member.hired", actor=principal.subject, tenant=tenant, resource="member",
                ip=request.client.host if request.client else "")

            try:
                out = await request.app.state.container.signup.hire(
                    tenant, phone=body.phone, password=body.password, role=body.role)
            except SignupRefused as exc:
                # RETURNED, NEVER RAISED — the platform strips a raised detail, and «هذا الرقم
                # مسجّل في منشأة أخرى» is the only part of this answer the owner can act on.
                #
                # A SECOND, CORRECTIVE ENTRY — fixed 2026-09-12, a real gap a QA audit found: the
                # write-ahead record above claimed a hire for someone who was never actually given
                # access.
                await request.app.state.auditor.record(
                    "member.hired", actor=principal.subject, tenant=tenant, resource="member",
                    ip=request.client.host if request.client else "",
                    metadata={"outcome": "refused", "reason": str(exc)})
                return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST,
                                    content={"error": "NOT_HIRED", "message": str(exc)})

            return await _finish_hire(request, body=body, tenant=tenant, store=store,
                                      gauges=gauges, out=out, branch_id=branch_id,
                                      current=current)
    except S.SeatClaimBusy as exc:
        return JSONResponse(status_code=status.HTTP_409_CONFLICT,
                            content={"error": "SEAT_BUSY", "message": str(exc)})
    except S.SeatLimitReached as exc:
        return JSONResponse(status_code=status.HTTP_402_PAYMENT_REQUIRED,
                            content={"error": "SEAT_LIMIT", "message": str(exc)})


async def _finish_hire(request: Request, *, body: MemberIn, tenant: str, store: Any,
                       gauges: Any, out: dict, branch_id: str, current: int) -> dict:
    """The half of `hire_member` that runs after identity answered. Split out for depth only.

    IT RUNS INSIDE THE SEAT LANE and must stay there — the caller holds the claim across this
    call. Nothing here may be reused from outside it.
    """
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
    # WHAT HE MAY SEE, WHICH IS NOT WHERE HE WORKS. `branch_id` above is his station and decides
    # where his visits are counted; these two decide whose numbers, messages and customers he may
    # read. Separate fields because an owner grants them separately — a supervisor keeps working
    # out of one branch while watching four.
    #
    # `None` MEANS «LEAVE IT», as everywhere else in this model: an owner renaming somebody has not
    # asked to change what he can see.
    visible_branch_ids: list[str] | None = Field(default=None, max_length=64)
    visible_all: bool | None = None
    active: bool | None = None


@router.patch("/operators/{operator_id}", dependencies=[Depends(subscribed_write), Depends(rate_limit)])
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
        # `None` STILL MEANS «LEAVE IT» — an owner renaming somebody has not asked to move him.
        # An EXPLICIT VALUE MUST NOW BE A REAL BRANCH: «كل الفروع» is no longer a
        # state this route can put somebody back into, matching create's own rule. An id we do
        # not recognise is refused rather than silently resolved to «unassigned».
        try:
            branch_id = await B.resolve_required(
                BranchStore(request.app.state.container.datastore), tenant, body.branch_id)
        except B.BranchRequired:
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={
                "error": "BRANCH_REQUIRED", "message": "اختر فرعاً حقيقياً لهذا الموظف."})

    # EVERY BRANCH HE IS GRANTED IS CHECKED, one at a time, against his own shop's list. An id we
    # do not recognise is DROPPED rather than stored: a scope carrying a branch that does not exist
    # is a filter that matches nothing, and a screen that goes empty for a reason nobody can see.
    if body.visible_branch_ids is not None:
        branches = BranchStore(request.app.state.container.datastore)
        granted = []
        for wanted in body.visible_branch_ids:
            resolved = await B.resolve(branches, tenant, str(wanted))
            if resolved and resolved not in granted:
                granted.append(resolved)
        op.visible_branch_ids = granted
    if body.visible_all is not None:
        op.visible_all = bool(body.visible_all)

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


_WEEKDAY_NAMES_AR = ("الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد")


class OperatorHoursIn(BaseModel):
    # "0"-"6" as strings, Monday=0..Sunday=6 — `date.weekday()`'s own numbering, the SAME one
    # bookings-service's tenant-wide working-hours store already uses (models.py:17-18's own
    # comment on WORKING_HOURS), so the two never need translating into each other.
    weekly: dict[str, dict[str, Any]] = Field(default_factory=dict)


@router.put("/operators/{operator_id}/working-hours",
           dependencies=[Depends(subscribed_write), Depends(rate_limit)])
async def set_operator_working_hours(request: Request, operator_id: str, body: OperatorHoursIn,
                                     principal: Principal = Depends(_MANAGE)) -> dict:
    """An EXPLICIT override for one operator — a DEDICATED route rather than a nullable field on
    `OperatorPatch`, because `working_hours`'s own valid domain genuinely needs `None` to mean
    "inherits the shop's hours" (models.py's own docstring), which collides with `None` already
    meaning "leave this field alone" on every other patchable field. Two unambiguous routes (this
    one to SET, `DELETE` below to CLEAR) instead of one route with an ambiguous meaning for `null`.

    THE WHOLE WEEK, ALWAYS — same reasoning as bookings' own `set_working_hours`: a partial save
    is ambiguous (day 3 sent, day 5 not — keep it, or default it?), so the whole document is
    validated and written as one, never merged with what was there.

    NEVER WIDER THAN THE SHOP'S OWN HOURS — refused at write time when `bookings` can be asked
    (fail-OPEN when it cannot: an unreachable peer must not block every staff-hours edit on a
    check that simply cannot run right now — `bookings` still intersects defensively at read
    time regardless, so this is one of two independent guards, never the only one).
    """
    tenant = _tenant(principal)
    store = OperatorStore(request.app.state.container.datastore)
    op = await store.get(tenant, operator_id)
    if op is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND")

    out: dict[str, dict[str, Any]] = {}
    for d in range(7):
        entry = body.weekly.get(str(d)) or {}
        closed = bool(entry.get("closed", False))
        # A NON-NUMERIC start_minute/end_minute (Pydantic's own `dict[str, dict[str, Any]]`
        # constrains nothing about the VALUES) used to raise an uncaught ValueError here — a real
        # 500 a QA audit found, breaking this route's own "never raise, always return" discipline
        # that BAD_HOURS/EXCEEDS_SHOP_HOURS right below already follow. Same refusal, same shape.
        try:
            start = int(entry.get("start_minute", 0) or 0)
            end = int(entry.get("end_minute", 0) or 0)
        except (TypeError, ValueError):
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={
                "error": "BAD_HOURS",
                "message": f"وقت دوام يوم {_WEEKDAY_NAMES_AR[d]} غير صحيح"})
        # RETURNED, NOT RAISED — the platform's own error handler strips an HTTPException's
        # `detail` before it reaches the caller (see `create_operator`'s `SEAT_LIMIT` note above),
        # so a message meant to tell an owner exactly which day is wrong must not be raised.
        if not closed and not (0 <= start < end <= 24 * 60):
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={
                "error": "BAD_HOURS",
                "message": f"وقت دوام يوم {_WEEKDAY_NAMES_AR[d]} غير صحيح"})
        out[str(d)] = {"closed": closed, "start_minute": start, "end_minute": end}

    shop_hours = await request.app.state.container.bookings_desk.working_hours(tenant)
    if shop_hours is not None:
        for d in range(7):
            shop_entry = shop_hours.get(str(d)) or {}
            mine = out[str(d)]
            if mine["closed"] or shop_entry.get("closed"):
                continue
            if (mine["start_minute"] < int(shop_entry.get("start_minute", 0))
                    or mine["end_minute"] > int(shop_entry.get("end_minute", 24 * 60))):
                return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={
                    "error": "EXCEEDS_SHOP_HOURS",
                    "message": f"دوام {_WEEKDAY_NAMES_AR[d]} يتجاوز دوام المحل نفسه — عدّله ليقع ضمنه"})

    op.working_hours = out
    await store.save(op)
    await request.app.state.auditor.record(
        "staff_hours.changed", actor=principal.subject, tenant=tenant,
        resource=f"operator:{operator_id}", ip=request.client.host if request.client else "")
    return op.public()


@router.delete("/operators/{operator_id}/working-hours",
              dependencies=[Depends(subscribed_write), Depends(rate_limit)])
async def clear_operator_working_hours(request: Request, operator_id: str,
                                       principal: Principal = Depends(_MANAGE)) -> dict:
    """Back to inheriting the shop's own hours, in full — idempotent (clearing an
    already-inherited operator is a harmless no-op success, matching this codebase's usual
    idempotent-delete shape), never an error over a double click or a stale button."""
    tenant = _tenant(principal)
    store = OperatorStore(request.app.state.container.datastore)
    op = await store.get(tenant, operator_id)
    if op is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND")
    had = op.working_hours is not None
    op.working_hours = None
    await store.save(op)
    if had:
        await request.app.state.auditor.record(
            "staff_hours.changed", actor=principal.subject, tenant=tenant,
            resource=f"operator:{operator_id}", ip=request.client.host if request.client else "")
    return op.public()


@router.get("/operators", dependencies=[Depends(rate_limit)])
async def list_operators(request: Request, principal: Principal = Depends(_READ_OPERATORS_FOR_BOOKINGS)) -> dict:
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
    return {
        "operators": SCOPE.visible([o.public() for o in rows], scope),
        # WHETHER THE SHARED-TABLET EMPLOYEE EXISTS ON THIS DEPLOYMENT (config
        # `PIN_OPERATORS_ENABLED`). Carried on the read the screen already makes, so the form
        # offers one way of adding somebody rather than two, one of which the door refuses.
        #
        # ANSWERED HERE RATHER THAN ASSUMED THERE: a console that hard-coded «off» would have to be
        # rebuilt to turn it on, which is the opposite of a switch.
        "pin_operators_enabled": bool(
            getattr(request.app.state.container_settings, "PIN_OPERATORS_ENABLED", False)),
    }


# SUPERSEDED (2026-09-11) BY THE PLATFORM-WIDE `/api/v1/account/me/locale` (api/v1/__init__.py) —
# THIS ROUTE IS KEPT ONLY AS A ONE-TIME READ FALLBACK for whichever operator already had a value
# saved here before the switch (see that route's own carry-forward note), and is no longer written
# by the console. It structurally excludes the owner (see `get_my_operator_row` just above) — which
# is exactly the gap the new route exists to close: an operator has this row, the owner never will.
_VALID_OPERATOR_LOCALES = {"ar", "en", "ur", "ha", "fil", "bn"}


@router.get("/operators/me", dependencies=[Depends(rate_limit)])
async def get_my_operator_row(request: Request,
                              principal: Principal = Depends(_READ_OPERATORS_FOR_BOOKINGS)) -> dict:
    """His own operator row, or 404 — the owner himself has none (he is not an `Operator` row),
    and that is a real, expected answer, not a fault."""
    tenant = _tenant(principal)
    op = await OperatorStore(request.app.state.container.datastore).get_by_person(tenant, principal.subject)
    if op is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_AN_OPERATOR")
    return op.public()


class LocaleIn(BaseModel):
    locale: str = Field(min_length=2, max_length=8)


@router.patch("/operators/me/locale", dependencies=[Depends(subscribed_write), Depends(rate_limit)])
async def set_my_locale(request: Request, body: LocaleIn,
                        principal: Principal = Depends(_READ_OPERATORS_FOR_BOOKINGS)) -> dict:
    if body.locale not in _VALID_OPERATOR_LOCALES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "UNKNOWN_LOCALE")
    tenant = _tenant(principal)
    store = OperatorStore(request.app.state.container.datastore)
    op = await store.get_by_person(tenant, principal.subject)
    if op is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_AN_OPERATOR")
    op.locale = body.locale
    await store.save(op)
    return op.public()


_MAX_PINNED_NAV = 4  # the mobile bottom bar shows at most 4 icons — see nav_service.dart


class PinnedNavIn(BaseModel):
    pinned_nav_ids: list[str] = Field(max_length=_MAX_PINNED_NAV)


@router.patch("/operators/me/pinned-nav", dependencies=[Depends(subscribed_write), Depends(rate_limit)])
async def set_my_pinned_nav(request: Request, body: PinnedNavIn,
                            principal: Principal = Depends(_READ_OPERATORS_FOR_BOOKINGS)) -> dict:
    """The mobile app's own bottom-bar personalisation — which of THIS operator's own visible
    sections he wants pinned, and in what order. Same self-service shape as `/me/locale` right
    above: found by `sub`, never by an id in the path, so nobody can touch a colleague's row
    through this door.

    NOT VALIDATED AGAINST THE CATALOGUE HERE. A pin the caller can no longer reach (a capability
    since revoked) is filtered out client-side the same way a hidden `SECTIONS` row already is —
    this route only stores ids, the same "store the preference, let the read-side apply today's
    permissions" split `visible_branch_ids` already uses above.
    """
    tenant = _tenant(principal)
    store = OperatorStore(request.app.state.container.datastore)
    op = await store.get_by_person(tenant, principal.subject)
    if op is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_AN_OPERATOR")
    op.pinned_nav_ids = list(dict.fromkeys(body.pinned_nav_ids))  # de-duplicate, keep order
    await store.save(op)
    return op.public()


class PinVerifyIn(BaseModel):
    operator_id: str = Field(min_length=1, max_length=64)
    pin: str = Field(min_length=4, max_length=4, pattern=r"^\d{4}$")


@router.post("/operators/verify-pin", dependencies=[Depends(subscribed_write), Depends(rate_limit)])
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


@router.put("/mode", dependencies=[Depends(subscribed_write), Depends(rate_limit)])
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


class VehiclesIn(BaseModel):
    tracks_vehicle: bool


@router.get("/vehicles", dependencies=[Depends(rate_limit)])
async def read_vehicles(request: Request, principal: Principal = Depends(_READ)) -> dict:
    """Does this shop work on cars — the one question the plate page and the meter depend on."""
    tracks = await V.VehicleStore(request.app.state.container.datastore).tracks_vehicle(
        _tenant(principal))
    return {"tracks_vehicle": tracks}


@router.put("/vehicles", dependencies=[Depends(subscribed_write), Depends(rate_limit)])
async def set_vehicles(request: Request, body: VehiclesIn,
                       principal: Principal = Depends(_MANAGE)) -> dict:
    """Turn the plate page on or off for this establishment.

    BOTH DIRECTIONS, UNLIKE THE BRANCH MODE NEXT DOOR. Nothing outside our own database depends on
    the answer — no number is registered, no template is approved against it — so a shop that tried
    it and stopped doing cars simply says so, and the plate page goes away. A one-way switch here
    would be strictness with nothing behind it.

    AND IT IS EDITABLE AT ALL, which the trade it replaced was not: «نوع النشاط» was chosen once at
    sign-up and never again, so the tyre shop that added detailing, and the car wash that stopped,
    both lived with a screen that was wrong about them for ever.
    """
    tenant = _tenant(principal)
    row = await V.VehicleStore(request.app.state.container.datastore).set(
        tenant, body.tracks_vehicle)
    await request.app.state.auditor.record(
        "shop.vehicles_changed", actor=principal.subject, tenant=tenant, resource="shop_vehicles",
        ip=request.client.host if request.client else "")
    return row


@router.get("/whatsapp-auto-register", dependencies=[Depends(rate_limit)])
async def read_whatsapp_auto_register(
        request: Request, principal: Principal = Depends(_READ)) -> dict:
    """Has the owner switched on automatic contact registration over WhatsApp — every new number
    the shop's assistant hears from becomes a real جهات الاتصال row (`core/whatsapp_auto_register
    .py`'s own docstring has the full reasoning: OFF is the default for every shop, on purpose,
    until the owner opts in explicitly)."""
    enabled = await WAR.WhatsAppAutoRegisterFlagStore(request.app.state.container.datastore).enabled(
        _tenant(principal))
    return {"enabled": enabled}


class WhatsAppAutoRegisterIn(BaseModel):
    enabled: bool


@router.put("/whatsapp-auto-register",
           dependencies=[Depends(subscribed_write), Depends(rate_limit)])
async def set_whatsapp_auto_register(
        request: Request, body: WhatsAppAutoRegisterIn,
        principal: Principal = Depends(_MANAGE)) -> dict:
    """Turn automatic WhatsApp contact registration on or off — `_MANAGE`, not `_READ`: this is
    the owner's own data-collection decision (core/whatsapp_auto_register.py's own docstring),
    never a plain operator's to flip. Both directions, same as the visit-registration switch next
    door: a shop that turns it on and regrets it can turn it back off — no one-way ratchet."""
    tenant = _tenant(principal)
    row = await WAR.WhatsAppAutoRegisterFlagStore(request.app.state.container.datastore).set(
        tenant, body.enabled)
    await request.app.state.auditor.record(
        "shop.whatsapp_auto_register_changed", actor=principal.subject, tenant=tenant,
        resource="shop_whatsapp_auto_register_contacts",
        ip=request.client.host if request.client else "")
    return row


class ShopNameIn(BaseModel):
    name: str = Field(min_length=1, max_length=256)


@router.put("/shop-name", dependencies=[Depends(subscribed_write), Depends(rate_limit)])
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
    # ── ONLY A REFUSAL OF THE NAME MAY SAY «جرّب اسماً آخر» ────────────────────────────────────
    #
    # THIS LINE READ `if code >= 400` AND SAID THE SAME SENTENCE TO EVERY FAILURE. The registry
    # answers 400 INVALID_NAME for a name it will not take — and 404 when the tenant is unknown OR
    # when the route itself is absent, which is exactly what an older tenant-service returns
    # (#338: the cluster ran a digest predating this route). It answers 401/403 on a bad internal
    # token, and 5xx when it is simply down.
    #
    # Every one of those was rendered as «تعذّر حفظ الاسم. جرّب اسماً آخر.» — so an owner whose
    # shop name is perfectly fine retypes it, shortens it, drops the «مؤسسة», tries English, and
    # fails every time, because the thing that is broken is not his name and no name he can think
    # of will fix it. That is the worst shape a refusal can have: actionable-looking, and
    # impossible to act on.
    if code == status.HTTP_400_BAD_REQUEST:
        # THE REGISTRY'S REFUSAL IS THE REGISTRY'S. A name it rejects is one it can explain;
        # inventing a sentence of our own here would answer for a rule that is not ours.
        #
        # THE RAW BODY IS LOGGED, NEVER RETURNED (fixed 2026-09-12, a real gap a QA audit found).
        # `out` is the REGISTRY's own response — a peer's internals, its field names, whatever
        # detail it chose to include — and this route is reached over the owner's own token by an
        # external caller. Every other peer-error path in this service (connect.py's `_can_send`/
        # `whatsapp_register`, which maps a reason code to one of its own sentences and keeps the
        # peer's actual words server-side only) sends the clean sentence and nothing else; this
        # one alone forwarded `out` verbatim in `detail`.
        request.app.state.container.telemetry.event(
            "shop_rename_refused", tenant=tenant, status=code, body=str(out)[:400])
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST,
                            content={"error": "RENAME_REFUSED",
                                     "message": "تعذّر حفظ الاسم. جرّب اسماً آخر."})
    if code >= 400:
        # ANYTHING ELSE IS OURS, NOT HIS. He is told to wait rather than to invent — same
        # log-server-side-only fix as the 400 branch above; only the status code, never the
        # registry's own body, is a fact he or a browser network tab needs.
        request.app.state.container.telemetry.event(
            "shop_rename_unavailable", tenant=tenant, status=code, body=str(out)[:400])
        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            content={"error": "RENAME_UNAVAILABLE",
                                     "message": "تعذّر حفظ الاسم الآن — الخلل عندنا لا في الاسم. "
                                                "حاول بعد قليل."})
    await request.app.state.auditor.record(
        "shop.renamed", actor=principal.subject, tenant=tenant, resource="tenant",
        ip=request.client.host if request.client else "")
    return {"name": str(out.get("name") or body.name.strip())}


# ── the AI assistant's own notes ─────────────────────────────────────────────────────────────
class AiNotesIn(BaseModel):
    text: str = Field(default="", max_length=4000)  # the service's own 2000-char message is the
    # one the owner reads; this wider Pydantic cap only stops an oversized payload before it does
    # any work at all — belt, not the actual limit.


@router.get("/ai-notes", dependencies=[Depends(rate_limit)])
async def read_ai_notes(request: Request, principal: Principal = Depends(_MANAGE)) -> dict:
    """What the owner has told the WhatsApp AI assistant about his own shop.

    Reads back empty while `AI_NOTES_ENABLED` is off, regardless of what is stored — see that
    setting's own comment for why this is a behaviour switch, never a data-loss one.
    """
    s = request.app.state.container_settings
    if not getattr(s, "AI_NOTES_ENABLED", True):
        return {"text": ""}
    text = await AN.AiNotesStore(request.app.state.container.datastore).get(_tenant(principal))
    return {"text": text}


@router.put("/ai-notes", dependencies=[Depends(subscribed_write), Depends(rate_limit)])
async def set_ai_notes(request: Request, body: AiNotesIn,
                       principal: Principal = Depends(_MANAGE)) -> Any:
    """Set what the WhatsApp AI assistant knows about this shop beyond its catalogue — hours,
    policies, whatever a real receptionist would know and the platform does not.

    REDACTED BEFORE IT IS EVER STORED, never after. The text is merged into a prompt sent to a
    model that may be hosted outside the Kingdom (`whatsapp-assistant/core/conversation.py`), which
    redacts it AGAIN at merge time as a second, independent check — but the value written here is
    already safe even if that second check is ever bypassed.
    """
    s = request.app.state.container_settings
    if not getattr(s, "AI_NOTES_ENABLED", True):
        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            content={"error": "NOT_CONFIGURED",
                                     "message": "هذه الميزة غير مفعّلة حالياً."})
    tenant = _tenant(principal)
    try:
        cleaned = AN.sanitise(body.text)
    except AN.AiNotesError as exc:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST,
                            content={"error": "BAD_REQUEST", "message": str(exc)})
    await AN.AiNotesStore(request.app.state.container.datastore).set(tenant, cleaned.text)
    await request.app.state.auditor.record(
        "shop.ai_notes_changed", actor=principal.subject, tenant=tenant,
        resource="shop_ai_notes", ip=request.client.host if request.client else "")
    # `redacted` NAMES THE CATEGORIES, NEVER THE VALUE — same shape as assistant-service's own
    # `redacted` response field, so the owner learns a phone number was stripped without either of
    # us ever handling it a second time to tell him which one.
    return {"text": cleaned.text, "redacted": list(cleaned.hits)}


# ── the AI assistant's own kill switch ───────────────────────────────────────────────────────
@router.get("/ai-toggle", dependencies=[Depends(rate_limit)])
async def read_ai_toggle(request: Request, principal: Principal = Depends(_READ)) -> dict:
    """Is the WhatsApp AI assistant switched ON for this establishment right now — separate from
    whether the shop has bought `feature.whatsapp` at all (core/ai_toggle.py's own docstring: this
    is the owner's own runtime choice, never the entitlement). Absent means on, which is today's
    behaviour for every shop that has never touched this."""
    enabled = await AT.AiToggleStore(request.app.state.container.datastore).get(_tenant(principal))
    return {"enabled": enabled}


class AiToggleIn(BaseModel):
    enabled: bool


@router.put("/ai-toggle", dependencies=[Depends(subscribed_write), Depends(rate_limit)])
async def set_ai_toggle(request: Request, body: AiToggleIn, background: BackgroundTasks,
                        principal: Principal = Depends(_MANAGE)) -> dict:
    """Turn the WhatsApp AI assistant on or off for this establishment — `_MANAGE`, not `_READ`:
    this is the owner's own trust decision, never a plain operator's to flip. OFF closes it
    exactly as if `feature.whatsapp` had never been bought (whatsapp-assistant's own licence check
    reads this same row) — not a softer "paused" state, and reversible either direction.

    ALSO CUTS META'S OWN AI, THE INSTANT THIS FIRES — not this route's own reply engine (that gate
    already existed in whatsapp-assistant's `ToggleGatedLicence`); a number in Meta handover mode
    is never touched by that gate at all, so without this a shop could switch the assistant "off"
    here and still have Meta's AI answering its customers. OFF always disables Meta's rollout; ON
    only re-enables it when `feature.whatsapp` is still actually held — flipping the switch back on
    without ever having paid must not be a backdoor into Meta's AI. Fire-and-forget, same posture as
    `meta_agent_provision_trigger` — a shop with no Meta Business Agent on file costs one harmless,
    silently-reported no-op call."""
    tenant = _tenant(principal)
    c = request.app.state.container
    row = await AT.AiToggleStore(c.datastore).set(tenant, body.enabled)
    await request.app.state.auditor.record(
        "shop.ai_toggle_changed", actor=principal.subject, tenant=tenant,
        resource="shop_ai_toggle", ip=request.client.host if request.client else "")
    if body.enabled:
        if await c.whatsapp_licence.allowed(tenant):
            background.add_task(c.meta_agent_rollout_trigger.trigger, tenant=tenant, enabled=True)
    else:
        background.add_task(c.meta_agent_rollout_trigger.trigger, tenant=tenant, enabled=False)
    return row


# ── the customer-message word limit ──────────────────────────────────────────────────────────
class MsgWordLimitIn(BaseModel):
    limit: int = Field(ge=ML.MIN_MSG_WORD_LIMIT, le=ML.MAX_MSG_WORD_LIMIT)


@router.get("/msg-word-limit", dependencies=[Depends(rate_limit)])
async def read_msg_word_limit(request: Request, principal: Principal = Depends(_MANAGE)) -> dict:
    """How many words a customer's single WhatsApp message may be before the assistant refuses it
    outright, asking for something shorter, without ever calling the model.

    Reads back the default while `MSG_WORD_LIMIT_ENABLED` is off, regardless of what is stored —
    same behaviour-switch discipline as `AI_NOTES_ENABLED`.
    """
    s = request.app.state.container_settings
    if not getattr(s, "MSG_WORD_LIMIT_ENABLED", True):
        return {"limit": ML.DEFAULT_MSG_WORD_LIMIT}
    limit = await ML.MsgWordLimitStore(request.app.state.container.datastore).get(_tenant(principal))
    return {"limit": limit}


@router.put("/msg-word-limit", dependencies=[Depends(subscribed_write), Depends(rate_limit)])
async def set_msg_word_limit(request: Request, body: MsgWordLimitIn,
                             principal: Principal = Depends(_MANAGE)) -> Any:
    """Set this shop's own ceiling — bounded between `ML.MIN_MSG_WORD_LIMIT` and
    `ML.MAX_MSG_WORD_LIMIT` at the Pydantic layer already, `ML.sanitise` re-checks the same bound
    server-side rather than trusting the schema alone."""
    s = request.app.state.container_settings
    if not getattr(s, "MSG_WORD_LIMIT_ENABLED", True):
        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            content={"error": "NOT_CONFIGURED",
                                     "message": "هذه الميزة غير مفعّلة حالياً."})
    tenant = _tenant(principal)
    try:
        cleaned = ML.sanitise(body.limit)
    except ML.MsgWordLimitError as exc:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST,
                            content={"error": "BAD_REQUEST", "message": str(exc)})
    await ML.MsgWordLimitStore(request.app.state.container.datastore).set(tenant, cleaned)
    await request.app.state.auditor.record(
        "shop.msg_word_limit_changed", actor=principal.subject, tenant=tenant,
        resource="shop_msg_word_limits", ip=request.client.host if request.client else "")
    return {"limit": cleaned}


# ── branches ──────────────────────────────────────────────────────────────────────────────────
class BranchIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    #: Optional, set by the owner if he wants his branch on the admin panel's own map — never
    #: required to open a branch, same trade as every other optional field on this product.
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    city: str = Field(default="", max_length=80)


class BranchPatch(BaseModel):
    """Rename, close, reopen, or set/correct its location. NO DELETE — see `update_branch`."""

    name: str | None = Field(default=None, min_length=1, max_length=128)
    active: bool | None = None
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    city: str | None = Field(default=None, max_length=80)


def _live(rows: list[Branch]) -> int:
    return len([b for b in rows if b.active])


@router.post("/branches", status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(subscribed_write), Depends(rate_limit)])
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
    try:
        async with S.claiming(request.app.state.container.datastore,
                              tenant=tenant, key=S.BRANCHES, now=time.time()):
            current = _live(await store.list(tenant))
            # LOCATION IS OPTIONAL ON THE FIRST BRANCH, REQUIRED FROM THE SECOND ONE ON. A shop
            # with a single location has one obvious place — asking him to paste a map link to
            # open the account at all is friction with nothing to show for it (§ the docstring on
            # BranchIn.lat/lng above still holds for that case). The MOMENT a second branch
            # exists, "which one" stops being obvious to anyone reading this data later —
            # whatsapp-assistant's own branch-selection step (asking a customer for his city) has
            # nothing to match against for a branch nobody located, and the admin map silently
            # drops it (services/operations/app/api/v1/platform.py's own 0.0/0.0 filter). Refusing
            # here, once, is cheaper than a shop discovering the gap the day a customer's WhatsApp
            # conversation cannot find their second branch at all.
            if current >= 1 and (body.lat is None or body.lng is None):
                return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={
                    "error": "LOCATION_REQUIRED",
                    "message": "حدّد موقع الفرع على الخريطة — لازم من الفرع الثاني فأكثر."})
            await S.guard_and_report(gauges, tenant=tenant, key=S.BRANCHES, current=current)

            await request.app.state.auditor.record(
                "branch.created", actor=principal.subject, tenant=tenant, resource="branch",
                ip=request.client.host if request.client else "")
            b = Branch(id=new_id("brn"), tenant=tenant, name=body.name.strip(),
                       created=int(time.time()),
                       lat=body.lat or 0.0, lng=body.lng or 0.0, city=body.city.strip())
            await store.save(b)
            await gauges.report(tenant, S.BRANCHES, current + 1)
    except S.SeatClaimBusy as exc:
        return JSONResponse(status_code=status.HTTP_409_CONFLICT,
                            content={"error": "BRANCH_BUSY", "message": str(exc)})
    except S.SeatLimitReached as exc:
        return JSONResponse(status_code=status.HTTP_402_PAYMENT_REQUIRED,
                            content={"error": "BRANCH_LIMIT", "message": str(exc)})
    return b.public()


@router.patch("/branches/{branch_id}", dependencies=[Depends(subscribed_write), Depends(rate_limit)])
async def update_branch(request: Request, branch_id: str, body: BranchPatch,
                        principal: Principal = Depends(_MANAGE)) -> dict:
    """Rename a branch, close one, or set/correct its location — and NEVER delete one.

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

    # THE LANE IS TAKEN FOR EVERY EDIT, not only a reopen. Whether this request needs the guard
    # depends on `b.active`, which is read inside — deciding that outside the lane would mean
    # reading the state that decides, before holding the thing that keeps it still. A rename pays
    # a few microseconds of queueing for a rule with no exception in it (core/seats.py).
    try:
        async with S.claiming(request.app.state.container.datastore,
                              tenant=tenant, key=S.BRANCHES, now=time.time()):
            b = await store.get(tenant, branch_id)
            if b is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND")
            rows = await store.list(tenant)
            if body.active is True and not b.active:
                await S.guard_and_report(gauges, tenant=tenant, key=S.BRANCHES,
                                         current=_live(rows))

            # THE REAL DIFF, NOT JUST "SOMETHING CHANGED" — found by review: this event used to
            # carry no metadata at all, so a close, a reopen, a rename and a relocation were all
            # indistinguishable in the trail, one line reading "branch.updated" with nothing to
            # tell them apart. For a dispute over "was this branch open on date X" that is not a
            # log, it is a rumour. Computed BEFORE the mutation below, against the row this
            # request actually read, so it reflects what THIS call changes — never a stale diff
            # against a row a concurrent writer already moved past (the claim lane above already
            # protects the write itself; this only has to describe it honestly).
            changes: dict[str, Any] = {}
            if body.active is not None and body.active != b.active:
                changes["active"] = {"from": b.active, "to": body.active}
            if body.name is not None and body.name.strip() != b.name:
                changes["name"] = {"from": b.name, "to": body.name.strip()}
            if body.lat is not None and body.lat != b.lat:
                changes["lat"] = {"from": b.lat, "to": body.lat}
            if body.lng is not None and body.lng != b.lng:
                changes["lng"] = {"from": b.lng, "to": body.lng}
            if body.city is not None and body.city.strip() != b.city:
                changes["city"] = {"from": b.city, "to": body.city.strip()}

            await request.app.state.auditor.record(
                "branch.updated", actor=principal.subject, tenant=tenant,
                resource=f"branch:{branch_id}", ip=request.client.host if request.client else "",
                metadata=changes)

            if body.name is not None:
                b.name = body.name.strip()
            if body.active is not None:
                # THE CACHE `Branch.closed_at` SPLIT — see that field's own docstring. Set on
                # close, cleared on reopen; the real open/close TIMELINE is the audit event above.
                b.closed_at = int(time.time()) if body.active is False else 0
                b.active = body.active
            if body.lat is not None:
                b.lat = body.lat
            if body.lng is not None:
                b.lng = body.lng
            if body.city is not None:
                b.city = body.city.strip()
            await store.save(b)
            # THE WHOLE COUNT, RECOMPUTED — a gauge is reported, never incremented
            # (core/seats.py). The saved row is the one in `rows` by identity only if the store
            # returned the same object, so the live count is taken from the list with this row's
            # new state substituted in.
            await gauges.report(tenant, S.BRANCHES,
                                _live([b if r.id == b.id else r for r in rows]))
    except S.SeatClaimBusy as exc:
        return JSONResponse(status_code=status.HTTP_409_CONFLICT,
                            content={"error": "BRANCH_BUSY", "message": str(exc)})
    except S.SeatLimitReached as exc:
        return JSONResponse(status_code=status.HTTP_402_PAYMENT_REQUIRED,
                            content={"error": "BRANCH_LIMIT", "message": str(exc)})
    return b.public()


@router.get("/branches", dependencies=[Depends(rate_limit)])
async def list_branches(request: Request, principal: Principal = Depends(_READ_BRANCHES)) -> dict:
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

    # ── AND ONLY THE ONES HE MAY SEE (§12.4) ──────────────────────────────────────────────────
    # This read returned the whole chain to anybody holding `operations.list_branches`, while every
    # other read in this service — visits, customers, the dashboards — was already narrowed by
    # `branch_scope`. So a manager granted one branch could not read Jeddah's numbers and could
    # read Jeddah's NAME, its id, and how many places the chain has. «لا يرى موظف فرع أ بيانات
    # فرع ب» covers the names too: they are that shop's data.
    #
    # AND THE SWITCHER IS BUILT FROM THIS LIST. It moves to the sidebar, where the choice scopes
    # every screen, and its one non-negotiable rule is «يُضيِّق ولا يوسّع أبداً» — which can only
    # hold if the list it offers was narrowed first. Otherwise it offers him a branch the server
    # then refuses, and the product looks broken to a person who did nothing wrong.
    # `field="id"` AND NOT THE DEFAULT, which is the whole difference between a filter and a
    # no-op. `visible` keeps a row whose branch field is empty — right for a visit, because a
    # till records plenty with no branch and «غير محدَّد» belongs to everybody. A BRANCH row has
    # no `branch_id` at all: it IS the branch, and its key is `id`. Called with the default this
    # line would find the field missing on every row, keep every row, and read in review as
    # protection that was never applied.
    scope = await branch_scope(request.app.state.container.datastore, principal)
    kept = SCOPE.visible([b.public() for b in rows], scope, field="id")

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
    # THE GAUGE COUNTS THE SHOP'S REAL BRANCHES, not the ones this caller may see. The limit and
    # «may he open one more» are facts about the establishment's PLAN — computing them from a
    # narrowed list would tell a one-branch manager his chain of five has room for four more.
    return {"branches": kept, "branch_limit": int(limit), "may_add_branch": bool(may_add)}


_MAPS_SHORT_LINK_HOSTS = {"goo.gl", "maps.app.goo.gl"}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Declines to follow — `urlopen` then raises `HTTPError` on the redirect status, which is
    the only way urllib hands back the `Location` header without actually fetching the page it
    points to. We want the coordinate hiding in that URL, never the page itself."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        return None


def _resolve_maps_short_link(url: str) -> str:
    """Follows ONE redirect hop of a Google Maps short link and returns where it landed.

    A BROWSER CANNOT DO THIS ITSELF — reading a cross-origin redirect's destination is exactly
    what CORS exists to block, so apps/console's own googleMapsLink.ts deliberately never
    attempts it (see that file's own docstring). This route exists purely to do that one hop on
    the console's behalf, same-origin from its own point of view.

    RESTRICTED TO GOOGLE'S OWN SHORT-LINK HOSTS, NEVER AN ARBITRARY URL — an open "fetch whatever
    URL the caller names" route is a textbook SSRF door (a caller could point it at an internal
    service address). `goo.gl`/`maps.app.goo.gl` are the only two hosts Google actually issues
    these short links from.
    """
    parsed = urllib.parse.urlparse(url)
    host = (parsed.hostname or "").removeprefix("www.")
    if parsed.scheme != "https" or host not in _MAPS_SHORT_LINK_HOSTS:
        return ""
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        opener.open(url, timeout=5)
        # No redirect at all — nothing further to resolve.
        return ""
    except urllib.error.HTTPError as exc:
        if exc.code in (301, 302, 303, 307, 308):
            return exc.headers.get("Location") or ""
        return ""
    except OSError:
        return ""


@router.get("/resolve-maps-link", dependencies=[Depends(rate_limit)])
async def resolve_maps_link(request: Request, url: str,
                            principal: Principal = Depends(_READ)) -> dict:
    """`{"resolved_url": "..."}`, or `""` when the link was not one of ours to resolve or carried
    no redirect. Blocking I/O (urllib, matching signup.py's own `Http` — a second HTTP idiom in
    this codebase is a second set of timeout/error behaviour to keep in step), so it runs off the
    event loop via `run_in_threadpool` rather than stalling every other request on this worker.
    """
    resolved = await run_in_threadpool(_resolve_maps_short_link, url)
    return {"resolved_url": resolved}


# ── the service catalogue ─────────────────────────────────────────────────────────────────────
class ServiceIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    # 0 means "no natural cycle" — a one-off repair generates no reminder. Explicitly a valid
    # value rather than a missing one, because a default of 30 would schedule a reminder for a
    # puncture repair and teach a customer that our messages are noise.
    cycle_days: int = Field(default=0, ge=0, le=3650)
    # Minor units. No float ever touches an amount.
    price_minor: int = Field(default=0, ge=0)
    # 0 means NOT CONFIGURED, read by bookings to derive availability (docs/خطة-تنفيذ-الحجوزات.md
    # §2). Not defaulted to a guessed length here for the same reason `cycle_days` is not defaulted
    # to 30 above — an invented duration would let bookings compute a slot nobody actually set.
    # 720 = 12 hours, generous above any real salon/workshop service, still a real ceiling.
    duration_minutes: int = Field(default=0, ge=0, le=720)
    sort: int = Field(default=0, ge=0, le=9999)
    # A SHORT LINE THE OWNER WRITES — see Service.description's own docstring. Empty is the
    # common case; nothing here invents one.
    description: str = Field(default="", max_length=300)


def _localize_field(entries: dict[str, Any], entity_type: str, entity_id: str, field: str,
                    source: str, locale: str) -> str:
    return resolve_translation(entries.get(translation_entry_id(entity_type, entity_id, field)),
                               locale, source)


@router.get("/services", dependencies=[Depends(rate_limit)])
async def list_services(request: Request, include_retired: bool = False, locale: str = "ar",
                        principal: Principal = Depends(_MANAGE_SERVICES)) -> dict:
    """The OWNER's catalogue, which is not the field grid.

    /field/catalogue answers what an operator may record a visit against, and it is right that a
    retired service is absent from it. But the same list was the only one there was, so a service
    stopped from the management screen vanished from the management screen — and «تفعيل» had
    nothing left to act on. The same shape of bug as the rewards table, found the same way: by
    stopping something and looking for it.

    Gated on `operations.manage` OR `operations.manage_services` — not read:
    this is the list you edit, and an operator has no business seeing what the shop has retired.

    `locale`, WHEN NOT "ar" AND ONE OF `TARGET_LOCALES` — overrides `name`/`description` in each
    row with its own translation (see core/translations.py). Any other value (unset, "ar", junk)
    returns the shop's own Arabic untouched; there is no error path here, only the honest fallback
    `resolve()` itself already gives a locale with no answer yet.
    """
    tenant = _tenant(principal)
    ds = request.app.state.container.datastore
    rows = await ServiceStore(ds).list(tenant, active_only=not include_retired)
    if locale in TARGET_LOCALES:
        entries = await TranslationStore(ds).get_many(
            tenant, "service", [s.id for s in rows], ("name", "description"))
        out = []
        for s in rows:
            d = s.public()
            d["name"] = _localize_field(entries, "service", s.id, "name", s.name, locale)
            d["description"] = _localize_field(
                entries, "service", s.id, "description", s.description, locale)
            out.append(d)
        return {"services": out}
    return {"services": [s.public() for s in rows]}


@router.post("/services", status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(subscribed_write), Depends(rate_limit)])
async def create_service(request: Request, body: ServiceIn,
                         principal: Principal = Depends(_MANAGE_SERVICES)) -> dict:
    tenant = _tenant(principal)
    await request.app.state.auditor.record(
        "service.created", actor=principal.subject, tenant=tenant, resource="service",
        ip=request.client.host if request.client else "")
    s = Service(id=new_id("srv"), tenant=tenant, name=body.name.strip(),
                cycle_days=body.cycle_days, price_minor=body.price_minor,
                duration_minutes=body.duration_minutes, sort=body.sort,
                description=body.description.strip(), created=int(time.time()))
    await ServiceStore(request.app.state.container.datastore).save(s)
    return s.public()


class ServiceImportRow(BaseModel):
    """One line of an uploaded catalogue file — the console parses the spreadsheet client-side and
    sends structured rows, never a raw file; this service has no business knowing what a .csv or
    .xlsx looks like. Same field shape and same limits as `ServiceIn` on purpose: importing must
    not be a second, looser way to create a service than typing one in by hand."""
    name: str = Field(min_length=1, max_length=128)
    cycle_days: int = Field(default=0, ge=0, le=3650)
    price_minor: int = Field(default=0, ge=0)
    duration_minutes: int = Field(default=0, ge=0, le=720)
    # THE TILL'S OWN ID, OPTIONAL — Service.external_id's own docstring is the reason this exists:
    # matching by name alone forks a renamed product into two rows on the next re-upload. A row
    # carrying one matches an EXISTING service by it first (survives a rename in the file);
    # falls back to matching by name only when empty, same as a shop that never had a POS.
    external_id: str = Field(default="", max_length=128)
    # SAME "THE FILE WINS COMPLETELY" CONVENTION AS EVERY FIELD ABOVE — a blank column clears an
    # existing description the same way a blank price would zero one out. Not a partial edit.
    description: str = Field(default="", max_length=300)
    # AN IMAGE EMBEDDED IN THE ROW'S OWN CELL, EXTRACTED BY THE CONSOLE — see
    # services-images-board.md phase 2: an xlsx's picture is read client-side (this service still
    # has no business knowing what a .xlsx looks like) and arrives here as plain base64 bytes,
    # same shape as `CatalogueImageIn`. Blank means "leave whatever photo this service already
    # has" — UNLIKE description/price/etc. above, a re-import without a picture in every row must
    # not silently wipe photos uploaded one at a time from the edit screen.
    image_base64: str = Field(default="", max_length=8_000_000)  # ~6MB decoded, matches MAX_BYTES
    image_content_type: str = Field(default="", max_length=64)


class ServiceImportIn(BaseModel):
    rows: list[ServiceImportRow] = Field(min_length=1, max_length=200)
    # DEFAULT FALSE, AND NAMED WHAT IT DOES — an owner uploading a partial file by mistake must
    # never silently retire the rest of the catalogue. Explicit opt-in, asked again on every
    # import (the console never remembers a previous choice), because "everything not in this
    # file" is a different set on every upload.
    deactivate_missing: bool = False


@router.post("/services/bulk_import", dependencies=[Depends(subscribed_write), Depends(rate_limit)])
async def bulk_import_services(request: Request, body: ServiceImportIn,
                               principal: Principal = Depends(_MANAGE_SERVICES)) -> dict:
    """Create/update many services from an uploaded file, in one call.

    VALIDATION HAPPENS BEFORE ANY WRITE, ALWAYS — twice over. Pydantic's own field limits on
    `ServiceImportRow` (`name` non-empty, a price/duration/cycle in range) already refuse the
    WHOLE request with a 422 if even one row is malformed, before this function body ever runs —
    the same all-or-nothing guarantee `ServiceIn` already gives a single manual add, extended to a
    batch. The second check, below, is duplicate NAMES within the file itself: two rows meaning
    "the same service" is a file the owner needs to fix, not a coin flip about which row wins.

    MATCHED BY external_id FIRST, THEN NAME — see `ServiceImportRow.external_id`'s own note.
    A match UPDATES the existing row (and reactivates it if it was stopped); no match CREATES one.
    A previously-stopped service reappearing in a new upload is read as "bring it back", which is
    the only sane reading of an owner naming it in a file they are actively importing.

    `deactivate_missing` is the ONE destructive thing this route can do, and it is opt-in, per
    call, every time — see `ServiceImportIn.deactivate_missing`'s own note.
    """
    tenant = _tenant(principal)
    seen: dict[str, int] = {}
    dupes: set[str] = set()
    for row in body.rows:
        key = row.name.strip().lower()
        if key in seen:
            dupes.add(row.name.strip())
        seen[key] = 1
    if dupes:
        return JSONResponse(
            {"error": "DUPLICATE_NAMES", "names": sorted(dupes),
             "reason": "الملف فيه أكثر من صف بنفس الاسم — صحّح الملف وأعد الرفع."},
            status_code=status.HTTP_400_BAD_REQUEST)

    # IMAGES VALIDATED BEFORE ANY ROW IS WRITTEN, same "no partial import" discipline as the
    # duplicate-name check just above — decoding is cheap, and a file with one bad picture among
    # two hundred good rows must fail loud and name the row, not silently skip that one photo.
    import base64
    import binascii

    from app.core.catalogue_image import ALLOWED_TYPES, MAX_BYTES
    for row in body.rows:
        if not row.image_base64:
            continue
        ctype = row.image_content_type.lower().split(";")[0].strip()
        if ctype not in ALLOWED_TYPES:
            return JSONResponse(
                {"error": "INVALID_IMAGE", "name": row.name,
                 "reason": f"{row.name}: نوع الصورة غير مدعوم."},
                status_code=status.HTTP_400_BAD_REQUEST)
        try:
            decoded = base64.b64decode(row.image_base64, validate=True)
        except (ValueError, binascii.Error):
            return JSONResponse(
                {"error": "INVALID_IMAGE", "name": row.name,
                 "reason": f"{row.name}: تعذّرت قراءة الصورة."},
                status_code=status.HTTP_400_BAD_REQUEST)
        if not decoded or len(decoded) > MAX_BYTES:
            return JSONResponse(
                {"error": "INVALID_IMAGE", "name": row.name,
                 "reason": f"{row.name}: حجم الصورة غير صالح."},
                status_code=status.HTTP_400_BAD_REQUEST)

    store = ServiceStore(request.app.state.container.datastore)
    existing = await store.list(tenant, active_only=False)
    by_external_id = {s.external_id: s for s in existing if s.external_id}
    by_name = {s.name.strip().lower(): s for s in existing}

    created = updated = reactivated = 0
    touched_ids: set[str] = set()
    for row in body.rows:
        name = row.name.strip()
        target = by_external_id.get(row.external_id) if row.external_id else None
        if target is None:
            target = by_name.get(name.lower())

        if target is not None:
            was_stopped = target.active is False
            target.name = name
            target.cycle_days = row.cycle_days
            target.price_minor = row.price_minor
            target.duration_minutes = row.duration_minutes
            target.description = row.description.strip()
            target.active = True
            if row.external_id:
                target.external_id = row.external_id
            if row.image_base64:
                from app.core.catalogue_image import store_image
                stored = await store_image(
                    request.app.state.container.object_store, tenant=tenant, kind="service",
                    item_id=target.id, data=base64.b64decode(row.image_base64),
                    content_type=row.image_content_type, old_key=target.image_key)
                target.image_key = stored.key
            await store.save(target)
            touched_ids.add(target.id)
            if was_stopped:
                reactivated += 1
            else:
                updated += 1
        else:
            s = Service(id=new_id("srv"), tenant=tenant, name=name, cycle_days=row.cycle_days,
                       price_minor=row.price_minor, duration_minutes=row.duration_minutes,
                       external_id=row.external_id, description=row.description.strip(),
                       created=int(time.time()))
            if row.image_base64:
                from app.core.catalogue_image import store_image
                stored = await store_image(
                    request.app.state.container.object_store, tenant=tenant, kind="service",
                    item_id=s.id, data=base64.b64decode(row.image_base64),
                    content_type=row.image_content_type, old_key="")
                s.image_key = stored.key
            await store.save(s)
            touched_ids.add(s.id)
            created += 1

    deactivated = 0
    if body.deactivate_missing:
        for s in existing:
            if s.id not in touched_ids and s.active is not False:
                s.active = False
                await store.save(s)
                deactivated += 1

    await request.app.state.auditor.record(
        "service.bulk_imported", actor=principal.subject, tenant=tenant, resource="service",
        ip=request.client.host if request.client else "",
        metadata={"created": created, "updated": updated, "reactivated": reactivated,
                  "deactivated": deactivated, "rows": len(body.rows)})
    return {"created": created, "updated": updated, "reactivated": reactivated,
            "deactivated": deactivated}


class ServicePatch(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    cycle_days: int | None = Field(default=None, ge=0, le=3650)
    price_minor: int | None = Field(default=None, ge=0)
    duration_minutes: int | None = Field(default=None, ge=0, le=720)
    active: bool | None = None
    sort: int | None = Field(default=None, ge=0, le=9999)
    description: str | None = Field(default=None, max_length=300)
    # WHO CAN ACTUALLY DO THIS — `None` MEANS «LEAVE IT», same convention every other field on
    # this model already uses. An EXPLICIT empty list is a real value (models.py's own
    # `Service.eligible_staff_ids` docstring: "[] means every active operator"), not "leave it" —
    # so an owner can deliberately clear a restriction back to unrestricted from this same route.
    eligible_staff_ids: list[str] | None = Field(default=None, max_length=64)
    # NAMED vs AUTO — see Service.assignment_mode's own docstring (models.py). `None` means
    # "leave it", same convention as every field on this model; validated against
    # `ASSIGNMENT_MODES` here rather than trusted, since this is the one route that can set it.
    assignment_mode: str | None = Field(default=None, max_length=16)
    # THE PROTOCOL, ORDERED — see Service.procedure_step_ids's own docstring (models.py). `None`
    # means "leave it"; an explicit `[]` is a real value (clears the protocol back to none), same
    # "None vs empty list" convention `eligible_staff_ids` above already uses. ORDER IS LIST
    # ORDER — the console sends the ids in the sequence the owner dragged them into.
    procedure_step_ids: list[str] | None = Field(default=None, max_length=100)


@router.patch("/services/{service_id}", dependencies=[Depends(subscribed_write), Depends(rate_limit)])
async def update_service(request: Request, service_id: str, body: ServicePatch,
                         principal: Principal = Depends(_MANAGE_SERVICES)) -> dict:
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

    for fld in ("name", "cycle_days", "price_minor", "duration_minutes", "active", "sort",
                "description"):
        val = getattr(body, fld)
        if val is not None:
            setattr(s, fld, val.strip() if isinstance(val, str) else val)

    if body.assignment_mode is not None:
        if body.assignment_mode not in ASSIGNMENT_MODES:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                                f"assignment_mode must be one of {sorted(ASSIGNMENT_MODES)}")
        s.assignment_mode = body.assignment_mode

    # EVERY OPERATOR GRANTED IS CHECKED against this tenant's own roster, same discipline
    # `update_operator`'s `visible_branch_ids` already uses — an id we do not recognise is
    # DROPPED, not stored, so a stale/foreign id cannot silently narrow a service to nobody.
    if body.eligible_staff_ids is not None:
        operators = OperatorStore(request.app.state.container.datastore)
        real = {o.id for o in await operators.list(tenant)}
        s.eligible_staff_ids = [oid for oid in body.eligible_staff_ids if oid in real]

    # EVERY STEP ID IS CHECKED against this tenant's own live catalogue, same discipline as
    # `eligible_staff_ids` immediately above — a stale or foreign id (another tenant's step,
    # or one since retired) is DROPPED, never stored, so the checklist a field operator sees can
    # never silently point at text that no longer resolves. ORDER IS PRESERVED (a list
    # comprehension over the CALLER'S order, not the store's), which is the whole point of this
    # being a list rather than a set.
    if body.procedure_step_ids is not None:
        steps = ProcedureStepStore(request.app.state.container.datastore)
        real_steps = {st.id for st in await steps.list(tenant, active_only=True)}
        s.procedure_step_ids = [sid for sid in body.procedure_step_ids if sid in real_steps]

    await store.save(s)
    return s.public()


# ── الإجراءات والبروتوكول ([[task-service-procedure-checklists]], phase 1) ───────────────────────
# THE SHARED CATALOGUE — see `ProcedureStep`'s own docstring (models.py) for why this is a real,
# tenant-scoped collection rather than free text repeated on each service, and why a step is
# retired (`active=false`) rather than ever deleted.

class ProcedureStepIn(BaseModel):
    text: str = Field(min_length=1, max_length=300)
    severity: str = Field(default="normal", max_length=16)
    training_note: str = Field(default="", max_length=500)


@router.get("/procedure-steps", dependencies=[Depends(rate_limit)])
async def list_procedure_steps(request: Request, include_retired: bool = False, locale: str = "ar",
                               principal: Principal = Depends(_MANAGE_SERVICES)) -> dict:
    """The owner's own protocol catalogue — same shape as `list_services` above (owner's edit
    list includes what he retired, so a stopped step can be brought back), including the same
    `locale` override."""
    tenant = _tenant(principal)
    ds = request.app.state.container.datastore
    rows = await ProcedureStepStore(ds).list(tenant, active_only=not include_retired)
    if locale in TARGET_LOCALES:
        entries = await TranslationStore(ds).get_many(
            tenant, "procedure_step", [s.id for s in rows], ("text",))
        out = []
        for s in rows:
            d = s.public()
            d["text"] = _localize_field(entries, "procedure_step", s.id, "text", s.text, locale)
            out.append(d)
        return {"procedure_steps": out}
    return {"procedure_steps": [s.public() for s in rows]}


@router.post("/procedure-steps", status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(subscribed_write), Depends(rate_limit)])
async def create_procedure_step(request: Request, body: ProcedureStepIn,
                                principal: Principal = Depends(_MANAGE_SERVICES)) -> dict:
    if body.severity not in PROCEDURE_STEP_SEVERITIES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            f"severity must be one of {sorted(PROCEDURE_STEP_SEVERITIES)}")
    tenant = _tenant(principal)
    await request.app.state.auditor.record(
        "procedure_step.created", actor=principal.subject, tenant=tenant, resource="procedure_step",
        ip=request.client.host if request.client else "")
    s = ProcedureStep(id=new_id("step"), tenant=tenant, text=body.text.strip(),
                      severity=body.severity, training_note=body.training_note.strip(),
                      created=int(time.time()), created_by=principal.subject)
    await ProcedureStepStore(request.app.state.container.datastore).save(s)
    return s.public()


class ProcedureStepPatch(BaseModel):
    text: str | None = Field(default=None, min_length=1, max_length=300)
    severity: str | None = Field(default=None, max_length=16)
    training_note: str | None = Field(default=None, max_length=500)
    active: bool | None = None


@router.patch("/procedure-steps/{step_id}",
              dependencies=[Depends(subscribed_write), Depends(rate_limit)])
async def update_procedure_step(request: Request, step_id: str, body: ProcedureStepPatch,
                                principal: Principal = Depends(_MANAGE_SERVICES)) -> dict:
    """Edit a shared step — text/severity/training note change EVERYWHERE it is used, by design
    (see `Service.procedure_step_ids`'s own docstring: the whole reason this is a shared catalogue
    rather than per-service text).

    RETIRE rather than delete — `active: false`. A `Service.procedure_step_ids` entry pointing at
    a retired step is left in place (never silently pruned here): the SERVICE screen filters it out
    of what the field operator sees, while an OLD `Visit.rating_issue_step_ids`/`OperatorStepStat`
    row still resolves it back to real text — the exact same "never orphan a historical reference"
    reasoning `update_service`'s own docstring gives for services.
    """
    tenant = _tenant(principal)
    store = ProcedureStepStore(request.app.state.container.datastore)
    s = await store.get(tenant, step_id)
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND")

    if body.severity is not None and body.severity not in PROCEDURE_STEP_SEVERITIES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            f"severity must be one of {sorted(PROCEDURE_STEP_SEVERITIES)}")

    await request.app.state.auditor.record(
        "procedure_step.updated", actor=principal.subject, tenant=tenant,
        resource=f"procedure_step:{step_id}", ip=request.client.host if request.client else "")

    for fld in ("text", "severity", "training_note", "active"):
        val = getattr(body, fld)
        if val is not None:
            setattr(s, fld, val.strip() if isinstance(val, str) else val)
    s.updated_at = int(time.time())

    await store.save(s)
    return s.public()


class ProcedureChecklistExportIn(BaseModel):
    # ONE OR MORE SERVICES, ONE COMBINED CHECKLIST — the owner's own instruction (2026-09-16,
    # after the single-service version already shipped): select several services at once (e.g. a
    # customer booked غسيل خارجي AND تلميع together) and get back ONE document, not one per
    # service, with a step shared by more than one of them printed exactly ONCE.
    service_ids: list[str] = Field(min_length=1, max_length=20)
    file_format: str = Field(default="pdf", pattern="^(docx|pdf)$")
    # THE LANGUAGE TO PRINT IN — never the operator's own console locale implicitly, always
    # explicit at the moment of export (owner's own instruction: he may want a copy in a
    # technician's language while reading the console itself in Arabic). "ar" (default) skips
    # resolution entirely; anything else falls back to Arabic per field where no translation
    # exists yet (core/translations.py::resolve) — never a blank field or a 4xx.
    locale: str = Field(default="ar", max_length=8)


@router.post("/procedure-checklist/export", dependencies=[Depends(rate_limit)])
async def export_procedure_checklist(request: Request, body: ProcedureChecklistExportIn,
                                     principal: Principal = Depends(_MANAGE_SERVICES)) -> Any:
    """The same ordered protocol `ServiceDrawer` shows, as a branded document instead of a screen —
    hand this to a customer, or print it as a wall reference. Same capability the whole tab already
    sits behind; no separate gate needed.

    DEDUPED, FIRST OCCURRENCE WINS. A step referenced by more than one of the selected services
    (the exact "مستخدمة بـN خدمات" case the console's own shared-usage badge exists for) is printed
    once, at the position of the FIRST service (in the caller's own selection order) that carries
    it — never once per service, which would have a technician re-do (or re-read) the identical
    instruction for every service that happens to share it. Each such step carries a small "مشتركة
    مع: …" caption naming every OTHER selected service it also belongs to, so the merge is legible
    rather than silently lossy.

    RETIRED STEPS ARE SILENTLY SKIPPED, never printed — same convention `ServiceDrawer`'s own
    console-side rendering already follows for a `procedure_step_ids` entry whose step id no longer
    resolves to an active one (see `update_procedure_step`'s own docstring: never pruned from the
    list here, only filtered where it is shown).

    AN UNKNOWN SERVICE ID IS SILENTLY DROPPED FROM THE MERGE, never a 404 — the caller is a
    multi-select the console itself populated from the live catalogue, so a stale id (a service
    deleted between the picker rendering and the export click) is a timing gap, not a caller
    error; a 404 for the whole document would lose the N-1 services that are still perfectly real.
    Only when NONE of the given ids resolve is the request actually refused.
    """
    import asyncio
    import datetime as _dt
    import tempfile
    from pathlib import Path

    from fastapi import HTTPException
    from fastapi.responses import FileResponse

    from app.core.branches import MAIN as MAIN_BRANCH_ID
    from app.core.pdf_convert import PdfConversionUnavailable, convert_to_pdf
    from app.core.procedure_checklist_render import build_procedure_checklist_docx
    from app.core.stores import BranchStore
    from app.core.tenant_branding import fetch_branding

    tenant = _tenant(principal)
    ds = request.app.state.container.datastore
    found = await asyncio.gather(*(ServiceStore(ds).get(tenant, sid) for sid in body.service_ids))
    services = [s for s in found if s is not None]
    if not services:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND")

    all_step_ids = {sid for svc in services for sid in svc.procedure_step_ids}
    resolved = await ProcedureStepStore(ds).get_many(tenant, list(all_step_ids))

    # LOCALIZED ONCE, UP FRONT — `also_in`'s own captions and `service_names` below both read
    # from this same map, so a shop's service name is translated (or falls back to Arabic)
    # identically everywhere it appears on the document, never once translated and once not.
    svc_name: dict[str, str] = {s.id: s.name for s in services}
    step_text: dict[str, str] = {sid: st.text for sid, st in resolved.items()}
    if body.locale in TARGET_LOCALES:
        svc_entries = await TranslationStore(ds).get_many(
            tenant, "service", [s.id for s in services], ("name",))
        step_entries = await TranslationStore(ds).get_many(
            tenant, "procedure_step", list(all_step_ids), ("text",))
        svc_name = {s.id: _localize_field(svc_entries, "service", s.id, "name", s.name,
                                          body.locale) for s in services}
        step_text = {sid: _localize_field(step_entries, "procedure_step", sid, "text", st.text,
                                          body.locale) for sid, st in resolved.items()}

    # first_service: which selected service each step id resolves to FIRST, for the "مشتركة مع"
    # caption; `steps` keeps the FIRST-OCCURRENCE order across the whole selection.
    steps: list[dict[str, Any]] = []
    seen: set[str] = set()
    also_in: dict[str, list[str]] = {}
    for svc in services:
        for sid in svc.procedure_step_ids:
            step = resolved.get(sid)
            if step is None or not step.active:
                continue
            if sid not in seen:
                seen.add(sid)
                steps.append({"id": step.id, "text": step_text[sid], "severity": step.severity})
                also_in[sid] = []
            elif svc_name[svc.id] not in also_in[sid]:
                also_in[sid].append(svc_name[svc.id])
    for step in steps:
        step["also_in"] = also_in.get(step["id"], [])

    branch = await BranchStore(ds).get(tenant, MAIN_BRANCH_ID)
    shop_name = (branch.name or "").strip() if branch else ""
    branding = await fetch_branding(request.app.state.container_settings, tenant)

    await request.app.state.auditor.record(
        "procedure_checklist.exported", actor=principal.subject, tenant=tenant,
        resource="service:" + ",".join(s.id for s in services),
        ip=request.client.host if request.client else "",
        metadata={"format": body.file_format, "step_count": len(steps),
                  "service_count": len(services)})

    now = _dt.datetime.now(_dt.timezone(_dt.timedelta(hours=3)))
    tmp_dir = Path(tempfile.mkdtemp(prefix="procedure_checklist_"))
    docx_path = tmp_dir / f"procedure_checklist_{tenant}.docx"
    build_procedure_checklist_docx(
        shop_name=shop_name, service_names=[svc_name[s.id] for s in services],
        steps=steps, out_path=docx_path, logo_png=branding.logo_png,
        accent_color=branding.accent, generated_at_label=now.strftime("%Y-%m-%d %H:%M"),
        locale=body.locale)

    if body.file_format == "docx":
        return FileResponse(docx_path, media_type=
                           "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                           filename=docx_path.name)
    try:
        pdf_path = convert_to_pdf(docx_path)
    except PdfConversionUnavailable as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    return FileResponse(pdf_path, media_type="application/pdf", filename=pdf_path.name)


@router.get("/operators/{operator_id}/step-stats", dependencies=[Depends(rate_limit)])
async def list_operator_step_stats(request: Request, operator_id: str,
                                   principal: Principal = Depends(_MANAGE_SERVICES)) -> dict:
    """One operator's own training record — see `OperatorStepStat`'s own docstring (models.py):
    an incrementally-maintained count, never computed by scanning this tenant's visit history on
    every profile view.

    RESOLVED AGAINST THE STEP CATALOGUE HERE, so «فريقي» never has to make its own second call —
    a stat row for a step since retired still resolves (steps are never deleted, only retired;
    see `update_procedure_step`'s own note), so an old training entry does not silently vanish
    the day the owner tidies the catalogue.
    """
    tenant = _tenant(principal)
    stats = await OperatorStepStatStore(request.app.state.container.datastore).for_operator(
        tenant, operator_id)
    steps = await ProcedureStepStore(request.app.state.container.datastore).get_many(
        tenant, [st.step_id for st in stats])
    return {"step_stats": [
        {**st.public(), "step_text": steps[st.step_id].text if st.step_id in steps else "",
         "step_severity": steps[st.step_id].severity if st.step_id in steps else ""}
        for st in stats
    ]}


class CatalogueImageIn(BaseModel):
    """A product photo, sent as JSON — the same shape notification-service's own
    `WaMediaUploadIn` already uses for a media upload, kept consistent rather than adding a second
    (multipart) upload convention to this service for one route."""
    content_type: str = Field(min_length=1, max_length=64)   # image/jpeg|image/png|image/webp
    data_base64: str = Field(min_length=1)


@router.post("/services/{service_id}/image", dependencies=[Depends(subscribed_write), Depends(rate_limit)])
async def upload_service_image(request: Request, service_id: str, body: CatalogueImageIn,
                               principal: Principal = Depends(_MANAGE_SERVICES)) -> dict:
    """Replace this service's photo. See `catalogue_image.py`'s module docstring for why this is a
    real object, never a URL the console types in."""
    tenant = _tenant(principal)
    store = ServiceStore(request.app.state.container.datastore)
    s = await store.get(tenant, service_id)
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND")
    import base64
    import binascii

    from app.core.catalogue_image import CatalogueImageError, store_image
    try:
        data = base64.b64decode(body.data_base64, validate=True)
    except (ValueError, binascii.Error):
        # RETURNED, NEVER RAISED — the platform's global handler strips a raised `detail`, and
        # this reason is written for the person who submitted the file (ci/check_refusal_survives.py).
        return JSONResponse({"ok": False, "reason": "data_base64 is not valid base64"},
                           status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)
    try:
        stored = await store_image(
            request.app.state.container.object_store, tenant=tenant, kind="service",
            item_id=service_id, data=data, content_type=body.content_type, old_key=s.image_key)
    except CatalogueImageError as exc:
        return JSONResponse({"ok": False, "reason": str(exc)},
                           status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)
    s.image_key = stored.key
    await store.save(s)
    await request.app.state.auditor.record(
        "service.image_set", actor=principal.subject, tenant=tenant,
        resource=f"service:{service_id}", ip=request.client.host if request.client else "")
    return s.public()


@router.get("/services/{service_id}/image", dependencies=[Depends(rate_limit)])
async def get_service_image(request: Request, service_id: str,
                            principal: Principal = Depends(_MANAGE_SERVICES)):
    """The photo itself, streamed back — gated the same as the rest of this catalogue (`operations.
    manage`/`manage_services`) rather than left public, since a photo is still the shop's own
    content."""
    tenant = _tenant(principal)
    s = await ServiceStore(request.app.state.container.datastore).get(tenant, service_id)
    if s is None or not s.image_key:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND")
    from starlette.responses import Response

    from app.core.catalogue_image import read_image
    from app.ports.errors import NotFound
    try:
        data, ctype = await read_image(request.app.state.container.object_store, s.image_key)
    except NotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND")
    return Response(content=data, media_type=ctype)


# ── the package catalogue ─────────────────────────────────────────────────────────────────────
# A package is a named, priced GROUP of the owner's own services (see core/models.py::Package's
# own docstring for why price and points are never derived from the components). Same house style
# as the service routes just above — same capability gate (packages are "خدماتي ومنتجاتي" too),
# same subscribed_write, same rate limit, same audit-on-write, same deactivate-never-delete.
class PackageIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    # AT LEAST TWO, NO UPPER BOUND — a "package" of one service is just that service; how many
    # belong together past that is entirely the owner's call (packages feature decision).
    service_ids: list[str] = Field(min_length=2, max_length=64)
    # Minor units, OWNER-ENTERED, > 0 — a package at price 0 is an accidental free booking, never
    # a real state (see Package's own docstring: never derived from the components either way).
    price_minor: int = Field(gt=0)
    sort: int = Field(default=0, ge=0, le=9999)
    # Set by the console when a package is accepted straight from محلّي's "اجعلها باقة" suggestion
    # — see services/insights/app/core/bundles.py. Left at the default for anything typed by hand.
    source: str = Field(default="manual", pattern="^(manual|suggested)$")
    source_service_ids: list[str] = Field(default_factory=list, max_length=64)
    # ── scheduling (packages feature, phase 2) — see core/scheduling.py::is_offerable ──────────
    starts_at: int = Field(default=0, ge=0)
    ends_at: int = Field(default=0, ge=0)
    recurrence: str = Field(default="none", pattern="^(none|weekly|monthly|yearly)$")
    recurrence_weekdays: list[int] = Field(default_factory=list, max_length=7)
    recurrence_days_of_month: list[int] = Field(default_factory=list, max_length=31)
    recurrence_yearly_from: str = Field(default="", max_length=5)
    recurrence_yearly_to: str = Field(default="", max_length=5)
    # PURELY DESCRIPTIVE — see Package.person_count's own docstring. 1 = say nothing about it.
    person_count: int = Field(default=1, ge=1, le=50)
    description: str = Field(default="", max_length=300)


def _validate_package_services(tenant: str, service_ids: list[str],
                               live: dict[str, Service]) -> list[str] | None:
    """Every id must exist, belong to THIS tenant, and still be active — a package is a promise
    that everything inside it can actually be delivered today. Returns the cleaned, de-duplicated
    list, or None if any id fails (the caller turns that into a 400 naming the reason)."""
    seen: list[str] = []
    for sid in service_ids:
        if sid in seen:
            continue
        svc = live.get(sid)
        if svc is None or svc.tenant != tenant or not svc.active:
            return None
        seen.append(sid)
    return seen if len(seen) >= 2 else None


def _schedule_error(*, starts_at: int, ends_at: int, recurrence: str,
                    weekdays: list[int], days_of_month: list[int],
                    yearly_from: str, yearly_to: str) -> str:
    """One sentence naming what is wrong with a proposed schedule, or "" — checked at WRITE time
    so a malformed schedule is refused here, never discovered the first time a booking silently
    fails to validate against it (core/scheduling.py's own module docstring)."""
    if ends_at and starts_at and ends_at < starts_at:
        return "تاريخ النهاية قبل تاريخ البداية"
    return SCHED.validate_recurrence(
        recurrence=recurrence, weekdays=weekdays, days_of_month=days_of_month,
        yearly_from=yearly_from, yearly_to=yearly_to)


@router.get("/packages", dependencies=[Depends(rate_limit)])
async def list_packages(request: Request, include_retired: bool = False,
                        principal: Principal = Depends(_MANAGE_SERVICES)) -> dict:
    rows = await PackageStore(request.app.state.container.datastore).list(
        _tenant(principal), active_only=not include_retired)
    now = int(time.time())
    # `offerable_now` IS A CONVENIENCE, COMPUTED HERE FROM THE SAME FUNCTION EVERYTHING ELSE USES
    # — never a second rule. The console reads it to show "غير مفعّلة اليوم" beside a package
    # that is `active` but simply outside its own schedule right now (e.g. a Saturday-only
    # package viewed on a Tuesday) — a real, useful distinction from "the owner turned it off".
    return {"packages": [{**p.public(), "offerable_now": SCHED.is_offerable(p, now)} for p in rows]}


@router.post("/packages", status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(subscribed_write), Depends(rate_limit)])
async def create_package(request: Request, body: PackageIn,
                         principal: Principal = Depends(_MANAGE_SERVICES)) -> dict:
    tenant = _tenant(principal)
    svc_store = ServiceStore(request.app.state.container.datastore)
    live = {s.id: s for s in await svc_store.list(tenant, active_only=False)}
    cleaned = _validate_package_services(tenant, body.service_ids, live)
    if cleaned is None:
        return JSONResponse(
            {"error": "INVALID_SERVICES",
             "reason": "لازم خدمتين على الأقل، موجودتين وفعّالتين في قائمتك."},
            status_code=status.HTTP_400_BAD_REQUEST)

    sched_error = _schedule_error(
        starts_at=body.starts_at, ends_at=body.ends_at, recurrence=body.recurrence,
        weekdays=body.recurrence_weekdays, days_of_month=body.recurrence_days_of_month,
        yearly_from=body.recurrence_yearly_from, yearly_to=body.recurrence_yearly_to)
    if sched_error:
        return JSONResponse({"error": "INVALID_SCHEDULE", "reason": sched_error},
                            status_code=status.HTTP_400_BAD_REQUEST)

    await request.app.state.auditor.record(
        "package.created", actor=principal.subject, tenant=tenant, resource="package",
        ip=request.client.host if request.client else "")
    p = Package(id=new_id("pkg"), tenant=tenant, name=body.name.strip(),
               service_ids=cleaned, price_minor=body.price_minor, sort=body.sort,
               source=body.source, source_service_ids=list(body.source_service_ids),
               starts_at=body.starts_at, ends_at=body.ends_at, recurrence=body.recurrence,
               recurrence_weekdays=list(body.recurrence_weekdays),
               recurrence_days_of_month=list(body.recurrence_days_of_month),
               recurrence_yearly_from=body.recurrence_yearly_from,
               recurrence_yearly_to=body.recurrence_yearly_to,
               person_count=body.person_count, description=body.description.strip(),
               created=int(time.time()))
    await PackageStore(request.app.state.container.datastore).save(p)
    return {**p.public(), "offerable_now": SCHED.is_offerable(p, int(time.time()))}


class PackagePatch(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    service_ids: list[str] | None = Field(default=None, min_length=2, max_length=64)
    price_minor: int | None = Field(default=None, gt=0)
    active: bool | None = None
    sort: int | None = Field(default=None, ge=0, le=9999)
    # ── scheduling — `None` MEANS "LEAVE IT", same convention as every other field here. Editing
    # the schedule always sends the WHOLE shape (all recurrence-relevant fields together) rather
    # than one piece — a partial edit could otherwise leave e.g. `recurrence="weekly"` with the
    # PREVIOUS package's `recurrence_weekdays` silently still attached.
    starts_at: int | None = Field(default=None, ge=0)
    ends_at: int | None = Field(default=None, ge=0)
    recurrence: str | None = Field(default=None, pattern="^(none|weekly|monthly|yearly)$")
    recurrence_weekdays: list[int] | None = Field(default=None, max_length=7)
    recurrence_days_of_month: list[int] | None = Field(default=None, max_length=31)
    recurrence_yearly_from: str | None = Field(default=None, max_length=5)
    recurrence_yearly_to: str | None = Field(default=None, max_length=5)
    person_count: int | None = Field(default=None, ge=1, le=50)
    description: str | None = Field(default=None, max_length=300)


@router.patch("/packages/{package_id}",
              dependencies=[Depends(subscribed_write), Depends(rate_limit)])
async def update_package(request: Request, package_id: str, body: PackagePatch,
                         principal: Principal = Depends(_MANAGE_SERVICES)) -> dict:
    """Edit a package. DEACTIVATE rather than delete — same reasoning as `update_service`: a past
    visit that fulfilled this package must still make sense a year from now."""
    tenant = _tenant(principal)
    store = PackageStore(request.app.state.container.datastore)
    p = await store.get(tenant, package_id)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND")

    if body.service_ids is not None:
        svc_store = ServiceStore(request.app.state.container.datastore)
        live = {s.id: s for s in await svc_store.list(tenant, active_only=False)}
        cleaned = _validate_package_services(tenant, body.service_ids, live)
        if cleaned is None:
            return JSONResponse(
                {"error": "INVALID_SERVICES",
                 "reason": "لازم خدمتين على الأقل، موجودتين وفعّالتين في قائمتك."},
                status_code=status.HTTP_400_BAD_REQUEST)
        p.service_ids = cleaned

    # SCHEDULE FIELDS VALIDATED TOGETHER, AS THE SHAPE THEY WILL END UP AS — merging each patched
    # field over the package's CURRENT value first (the same "None = leave it" convention every
    # other field on this route uses), so an edit that only touches `recurrence` still gets
    # checked against whatever weekdays/dates the package already had, not against an empty patch.
    schedule_touched = any(
        getattr(body, f) is not None for f in
        ("starts_at", "ends_at", "recurrence", "recurrence_weekdays", "recurrence_days_of_month",
         "recurrence_yearly_from", "recurrence_yearly_to"))
    if schedule_touched:
        starts_at = body.starts_at if body.starts_at is not None else p.starts_at
        ends_at = body.ends_at if body.ends_at is not None else p.ends_at
        recurrence = body.recurrence if body.recurrence is not None else p.recurrence
        weekdays = (body.recurrence_weekdays if body.recurrence_weekdays is not None
                   else p.recurrence_weekdays)
        days_of_month = (body.recurrence_days_of_month if body.recurrence_days_of_month is not None
                         else p.recurrence_days_of_month)
        yearly_from = (body.recurrence_yearly_from if body.recurrence_yearly_from is not None
                      else p.recurrence_yearly_from)
        yearly_to = (body.recurrence_yearly_to if body.recurrence_yearly_to is not None
                    else p.recurrence_yearly_to)
        sched_error = _schedule_error(
            starts_at=starts_at, ends_at=ends_at, recurrence=recurrence, weekdays=weekdays,
            days_of_month=days_of_month, yearly_from=yearly_from, yearly_to=yearly_to)
        if sched_error:
            return JSONResponse({"error": "INVALID_SCHEDULE", "reason": sched_error},
                                status_code=status.HTTP_400_BAD_REQUEST)
        p.starts_at, p.ends_at, p.recurrence = starts_at, ends_at, recurrence
        p.recurrence_weekdays = list(weekdays)
        p.recurrence_days_of_month = list(days_of_month)
        p.recurrence_yearly_from, p.recurrence_yearly_to = yearly_from, yearly_to

    await request.app.state.auditor.record(
        "package.updated", actor=principal.subject, tenant=tenant,
        resource=f"package:{package_id}", ip=request.client.host if request.client else "")

    for fld in ("name", "price_minor", "active", "sort", "person_count", "description"):
        val = getattr(body, fld)
        if val is not None:
            setattr(p, fld, val.strip() if isinstance(val, str) else val)

    await store.save(p)
    return {**p.public(), "offerable_now": SCHED.is_offerable(p, int(time.time()))}


@router.post("/packages/{package_id}/image", dependencies=[Depends(subscribed_write), Depends(rate_limit)])
async def upload_package_image(request: Request, package_id: str, body: CatalogueImageIn,
                               principal: Principal = Depends(_MANAGE_SERVICES)) -> dict:
    """Replace this package's photo — same rules as `upload_service_image`."""
    tenant = _tenant(principal)
    store = PackageStore(request.app.state.container.datastore)
    p = await store.get(tenant, package_id)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND")
    import base64
    import binascii

    from app.core.catalogue_image import CatalogueImageError, store_image
    try:
        data = base64.b64decode(body.data_base64, validate=True)
    except (ValueError, binascii.Error):
        return JSONResponse({"ok": False, "reason": "data_base64 is not valid base64"},
                           status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)
    try:
        stored = await store_image(
            request.app.state.container.object_store, tenant=tenant, kind="package",
            item_id=package_id, data=data, content_type=body.content_type, old_key=p.image_key)
    except CatalogueImageError as exc:
        return JSONResponse({"ok": False, "reason": str(exc)},
                           status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)
    p.image_key = stored.key
    await store.save(p)
    await request.app.state.auditor.record(
        "package.image_set", actor=principal.subject, tenant=tenant,
        resource=f"package:{package_id}", ip=request.client.host if request.client else "")
    return {**p.public(), "offerable_now": SCHED.is_offerable(p, int(time.time()))}


@router.get("/packages/{package_id}/image", dependencies=[Depends(rate_limit)])
async def get_package_image(request: Request, package_id: str,
                            principal: Principal = Depends(_MANAGE_SERVICES)):
    tenant = _tenant(principal)
    p = await PackageStore(request.app.state.container.datastore).get(tenant, package_id)
    if p is None or not p.image_key:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND")
    from starlette.responses import Response

    from app.core.catalogue_image import read_image
    from app.ports.errors import NotFound
    try:
        data, ctype = await read_image(request.app.state.container.object_store, p.image_key)
    except NotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND")
    return Response(content=data, media_type=ctype)


# ── shop-to-shop coupons — the standalone tab's own grant, no visit involved ────────────────────
class GrantCouponIn(BaseModel):
    phone: str = Field(min_length=3, max_length=32)
    percent: int = Field(gt=0, le=100)
    general: bool = False
    app_keys: list[str] = Field(default_factory=list, max_length=16)


@router.post("/coupons/grant", dependencies=[Depends(rate_limit)])
async def grant_coupon(request: Request, body: GrantCouponIn,
                       principal: Principal = Depends(_GRANT_COUPON_DIRECT)):
    tenant = _tenant(principal)
    att = await request.app.state.container.coupons.grant(
        granter_tenant=tenant, granter_operator_id=principal.subject, phone=body.phone,
        percent=body.percent, general=body.general, app_keys=body.app_keys)
    await request.app.state.auditor.record(
        "coupon.grant_attempt", actor=principal.subject, tenant=tenant,
        resource=f"coupon_attempt:{att.id}", ip=request.client.host if request.client else "")
    return att.public()


@router.get("/coupons/history", dependencies=[Depends(rate_limit)])
async def coupon_history(request: Request, limit: int = 100,
                         principal: Principal = Depends(_GRANT_COUPON_ANY)):
    tenant = _tenant(principal)
    rows = await request.app.state.container.coupons.history(tenant, limit=min(limit, 200))
    return {"attempts": [r.public() for r in rows]}


@router.get("/coupons/stats", dependencies=[Depends(rate_limit)])
async def coupon_stats(request: Request, principal: Principal = Depends(_GRANT_COUPON_ANY)):
    tenant = _tenant(principal)
    return await request.app.state.container.coupons.stats(tenant)


@router.get("/coupons/check", dependencies=[Depends(rate_limit)])
async def coupon_check(request: Request, phone: str = "",
                       principal: Principal = Depends(_GRANT_COUPON_ANY)):
    """The grant form's own live hint, asked as the operator types — same `_lookup_beneficiary`
    the real grant uses, same minimal-disclosure answer (`CouponService.check`'s own docstring).
    Behind `_GRANT_COUPON_ANY` (not `_GRANT_COUPON_DIRECT`) because the visit-linked door needs
    this hint too, before it ever commits to a grant."""
    tenant = _tenant(principal)
    if not phone.strip():
        return {"registered": False, "already_granted_this_month": False}
    return await request.app.state.container.coupons.check(
        granter_tenant=tenant, phone=phone.strip())


@router.get("/coupons/preferences", dependencies=[Depends(rate_limit)])
async def coupon_preferences(request: Request, principal: Principal = Depends(_GRANT_COUPON_ANY)):
    """Whether THIS shop turned the visit-screen coupon checkbox on — read by Visit.tsx itself
    (any visit-recording role) once per screen load, never on the hot save path. `_GRANT_COUPON_ANY`
    on purpose: a plain operator must be able to read this to know whether to draw the checkbox,
    even though only `_GRANT_COUPON_DIRECT` may change it."""
    tenant = _tenant(principal)
    row = await request.app.state.container.coupons.preferences(tenant)
    return {"visit_grant_enabled": row.visit_grant_enabled}


class CouponPreferencesIn(BaseModel):
    visit_grant_enabled: bool


@router.patch("/coupons/preferences", dependencies=[Depends(rate_limit)])
async def set_coupon_preferences(request: Request, body: CouponPreferencesIn,
                                 principal: Principal = Depends(_GRANT_COUPON_DIRECT)):
    tenant = _tenant(principal)
    row = await request.app.state.container.coupons.set_preferences(
        tenant, visit_grant_enabled=body.visit_grant_enabled)
    await request.app.state.auditor.record(
        "coupon.preferences_set", actor=principal.subject, tenant=tenant,
        resource="coupon_preferences", ip=request.client.host if request.client else "")
    return {"visit_grant_enabled": row.visit_grant_enabled}


# ── referral partnership — NOT the same feature as coupons above, see core/mutual_benefit.py
# ── module docstring. TWO TIERS (owner's own explicit decision, 2026-09-21 — same split
# ── `operations.grant_coupon`/`operations.grant_coupon_direct` already draws for coupons):
# ── committing the shop to a partnership — propose/accept/reject/either cancel step — stays
# ── `operations.manage` (owner/manager only), matching the design doc's own "a commitment against
# ── another shop entirely" requirement, never a plain operator capability the way
# ── `operations.grant_coupon` (a routine, per-visit act) is. READING one — the list, its audit
# ── log, the performance KPIs — is `operations.read` instead, which `marketer` also holds
# ── (deploy/seed/roles.json's own row for that role): "وسّع قاعدة عملائك دون ريال إعلان واحد" is
# ── exactly a marketing metric this role should see, same reasoning `campaigns.read`/
# ── `insights.read` already grant it visibility elsewhere — seeing performance is not the same
# ── act as committing the shop's own services to a partner, and must not require the same key.
from app.core.mutual_benefit import MutualBenefitError

_REFERRAL_MANAGE = require_capability("operations.manage")
_REFERRAL_VIEW = require_capability("operations.read")


def _mutual_benefit_error(exc: MutualBenefitError) -> HTTPException:
    code = str(exc.args[0]) if exc.args else "error"
    status_map = {
        "not_found": status.HTTP_404_NOT_FOUND,
        "forbidden": status.HTTP_403_FORBIDDEN,
        "not_subscribed": status.HTTP_402_PAYMENT_REQUIRED,
        "self_partner": status.HTTP_400_BAD_REQUEST,
        "bad_condition": status.HTTP_400_BAD_REQUEST,
        "wrong_state": status.HTTP_409_CONFLICT,
        "billing_unavailable": status.HTTP_503_SERVICE_UNAVAILABLE,
        "over_concurrency_cap": status.HTTP_409_CONFLICT,
        "catalog_item_not_found": status.HTTP_404_NOT_FOUND,
        "catalog_group_not_found": status.HTTP_404_NOT_FOUND,
    }
    return HTTPException(status_map.get(code, status.HTTP_400_BAD_REQUEST), code.upper())


class ProposeMutualBenefitIn(BaseModel):
    shop_b_phone: str = Field(min_length=3, max_length=32)
    condition_type: str = Field(min_length=1, max_length=32)
    condition_value: str = Field(min_length=1, max_length=64)
    grant_validity_days: int = Field(gt=0, le=365)
    agreement_duration_days: int = Field(gt=0, le=3650)
    per_period_cap: int = Field(default=0, ge=0)
    idempotency_key: str = Field(default="", max_length=128)
    # NO FREE TEXT ANYWHERE — see core/mutual_benefit.py's own "GRANT TYPE" module-docstring
    # section for the full, decided-once-and-immutable shape: "gift" (gift_service_id, a real
    # service from shop_b's own catalogue) or "discount" with discount_scope "item"
    # (gift_service_id, same as a gift), "blanket" (nothing else), or "group" (discount_group_id,
    # a real Package from shop_b's own catalogue).
    grant_type: str = Field(default="discount", max_length=16)
    gift_service_id: str = Field(default="", max_length=64)
    discount_scope: str = Field(default="blanket", max_length=16)
    discount_group_id: str = Field(default="", max_length=64)


@router.post("/mutual-benefit/agreements", dependencies=[Depends(rate_limit)])
async def propose_mutual_benefit(request: Request, body: ProposeMutualBenefitIn,
                                       principal: Principal = Depends(_REFERRAL_MANAGE)):
    tenant = _tenant(principal)
    engine = request.app.state.container.mutual_benefit
    try:
        agreement = await engine.propose(
            shop_a=tenant, shop_b_phone=body.shop_b_phone, operator_id=principal.subject,
            condition_type=body.condition_type, condition_value=body.condition_value,
            grant_validity_days=body.grant_validity_days,
            agreement_duration_days=body.agreement_duration_days,
            per_period_cap=body.per_period_cap, idempotency_key=body.idempotency_key,
            grant_type=body.grant_type, gift_service_id=body.gift_service_id,
            discount_scope=body.discount_scope, discount_group_id=body.discount_group_id)
    except MutualBenefitError as exc:
        raise _mutual_benefit_error(exc) from exc
    await request.app.state.auditor.record(
        "mutual_benefit.propose", actor=principal.subject, tenant=tenant,
        resource=f"referral_agreement:{agreement.id}",
        ip=request.client.host if request.client else "")
    return agreement.public()


@router.get("/mutual-benefit/agreements", dependencies=[Depends(rate_limit)])
async def list_mutual_benefits(request: Request,
                                     principal: Principal = Depends(_REFERRAL_VIEW)):
    tenant = _tenant(principal)
    rows = await request.app.state.container.mutual_benefit.agreements_for(tenant)
    return {"agreements": [r.public() for r in rows]}


@router.get("/mutual-benefit/agreements/{agreement_id}", dependencies=[Depends(rate_limit)])
async def get_mutual_benefit(request: Request, agreement_id: str,
                                   principal: Principal = Depends(_REFERRAL_MANAGE)):
    tenant = _tenant(principal)
    try:
        agreement = await request.app.state.container.mutual_benefit.get(
            tenant, agreement_id)
    except MutualBenefitError as exc:
        raise _mutual_benefit_error(exc) from exc
    return agreement.public()


@router.post("/mutual-benefit/agreements/{agreement_id}/accept",
            dependencies=[Depends(rate_limit)])
async def accept_mutual_benefit(request: Request, agreement_id: str,
                                      principal: Principal = Depends(_REFERRAL_MANAGE)):
    tenant = _tenant(principal)
    try:
        agreement = await request.app.state.container.mutual_benefit.accept(
            tenant=tenant, agreement_id=agreement_id)
    except MutualBenefitError as exc:
        raise _mutual_benefit_error(exc) from exc
    await request.app.state.auditor.record(
        "mutual_benefit.accept", actor=principal.subject, tenant=tenant,
        resource=f"referral_agreement:{agreement_id}",
        ip=request.client.host if request.client else "")
    return agreement.public()


@router.post("/mutual-benefit/agreements/{agreement_id}/reject",
            dependencies=[Depends(rate_limit)])
async def reject_mutual_benefit(request: Request, agreement_id: str,
                                      principal: Principal = Depends(_REFERRAL_MANAGE)):
    tenant = _tenant(principal)
    try:
        agreement = await request.app.state.container.mutual_benefit.reject(
            tenant=tenant, agreement_id=agreement_id)
    except MutualBenefitError as exc:
        raise _mutual_benefit_error(exc) from exc
    await request.app.state.auditor.record(
        "mutual_benefit.reject", actor=principal.subject, tenant=tenant,
        resource=f"referral_agreement:{agreement_id}",
        ip=request.client.host if request.client else "")
    return agreement.public()


@router.post("/mutual-benefit/agreements/{agreement_id}/cancel-request",
            dependencies=[Depends(rate_limit)])
async def cancel_request_mutual_benefit(request: Request, agreement_id: str,
                                              principal: Principal = Depends(_REFERRAL_MANAGE)):
    tenant = _tenant(principal)
    try:
        agreement = await request.app.state.container.mutual_benefit.cancel_request(
            tenant=tenant, agreement_id=agreement_id)
    except MutualBenefitError as exc:
        raise _mutual_benefit_error(exc) from exc
    await request.app.state.auditor.record(
        "mutual_benefit.cancel_request", actor=principal.subject, tenant=tenant,
        resource=f"referral_agreement:{agreement_id}",
        ip=request.client.host if request.client else "")
    return agreement.public()


@router.post("/mutual-benefit/agreements/{agreement_id}/cancel-confirm",
            dependencies=[Depends(rate_limit)])
async def cancel_confirm_mutual_benefit(request: Request, agreement_id: str,
                                              principal: Principal = Depends(_REFERRAL_MANAGE)):
    tenant = _tenant(principal)
    try:
        agreement = await request.app.state.container.mutual_benefit.cancel_confirm(
            tenant=tenant, agreement_id=agreement_id)
    except MutualBenefitError as exc:
        raise _mutual_benefit_error(exc) from exc
    await request.app.state.auditor.record(
        "mutual_benefit.cancel_confirm", actor=principal.subject, tenant=tenant,
        resource=f"referral_agreement:{agreement_id}",
        ip=request.client.host if request.client else "")
    return agreement.public()


@router.get("/mutual-benefit/agreements/{agreement_id}/audit-log",
           dependencies=[Depends(rate_limit)])
async def mutual_benefit_audit_log(request: Request, agreement_id: str,
                                         principal: Principal = Depends(_REFERRAL_VIEW)):
    tenant = _tenant(principal)
    try:
        rows = await request.app.state.container.mutual_benefit.audit_log(
            tenant, agreement_id)
    except MutualBenefitError as exc:
        raise _mutual_benefit_error(exc) from exc
    return {"entries": [r.public() for r in rows]}


@router.get("/mutual-benefit/kpis", dependencies=[Depends(rate_limit)])
async def mutual_benefit_kpis(request: Request,
                                    principal: Principal = Depends(_REFERRAL_VIEW)):
    tenant = _tenant(principal)
    return await request.app.state.container.mutual_benefit.kpis(tenant)
