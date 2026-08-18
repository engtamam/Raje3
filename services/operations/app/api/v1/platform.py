"""The platform console surface — the message library, edited by US at runtime.

NOT AN ESTABLISHMENT'S SURFACE. Every route here is gated by `platform.operations`, which no
tenant token carries: a tyre shop must not be able to rename "بنشر" for every other tyre shop on
the product. This is our own operators curating the content the whole platform is built from.

WHY IT EXISTS AT ALL — the alternative was a JSON file read at boot, and it was wrong. Correcting
a sentence a thousand shops send would have meant editing a ConfigMap and restarting a service.
The library is content: somebody will want a word changed on a Tuesday afternoon because a customer
read it aloud and it sounded wrong. Content that needs a deploy is content that does not get edited.

IT USED TO CURATE MORE. A table of trades lived here, and every shop's catalogue and rewards were
seeded from whichever one its owner picked — a guess about a business we had never seen, wrong on
its first day for any shop that did two things. That is gone: a shop writes its own services, and
the only thing it is asked is whether it works on cars (core/vehicles.py).

EVERY MUTATION IS AUDITED. Changing a template changes what every establishment sends afterwards,
which makes it the highest-leverage edit anyone can make here — a wrong word propagated to a
thousand shops is not visible until their customers read it.
"""
from __future__ import annotations

from fastapi.responses import JSONResponse
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.api.auth import Principal
from app.api.authz import require_capability
from app.api.ratelimit import rate_limit
from app.core import evidence as EV
from app.core.stores import PrivacyRequestStore
from app.core.partners import PartnerError, PartnerRegistry
from app.core.templates import TemplateError, TemplateLibrary
from app.api.subscribed import no_subscription_needed, subscribed_write

# The parent router in __init__ already carries /api/v1 — this prefix is appended to it.
router = APIRouter(prefix="/platform", tags=["platform"])

_PLATFORM = require_capability("platform.operations")


def _lib(request: Request) -> TemplateLibrary:
    return TemplateLibrary(request.app.state.container.datastore)



def _refuse(reason: str) -> JSONResponse:
    """A refusal OUR OWN OPERATOR can read — returned, not raised.

    The platform's handler strips `detail` from every HTTPException (CWE-209 by design), which is
    right for a stack trace and wrong for these: `TemplateError` and `PartnerError`
    each name a rule the panel broke — a template body over the limit, a partner name already
    taken. Raised, they arrive as `{"error": "BAD_REQUEST"}` and the operator is told only that
    something is wrong with a form he has to guess at.

    THE STATUS IS KEPT, so every caller that checks `response.ok` behaves exactly as before.
    """
    return JSONResponse({"error": "BAD_REQUEST", "reason": reason}, status_code=400)


class TemplateIn(BaseModel):
    name: str = Field(min_length=3, max_length=512, pattern=r"^[a-z][a-z0-9_]*$")
    type: str = Field(default="", max_length=128)
    tone: str = Field(default="", pattern="^(brief|warm|formal|)$")
    label: str = Field(default="", max_length=200)
    # The five regulatory classes (spec §8.4.1). Validated, not accepted: the class decides the
    # rules, so a template filed under the wrong one carries the wrong constraints.
    cls: str = Field(alias="class", pattern="^(service|personal|awareness|warning|marketing)$")
    # Which kind of business this template is FOR (spec 16.6.5). Declared on the model, not only in
    # the core: pydantic drops an undeclared key silently and with a 200, which is exactly how the
    # `fills` rule was enforced in the core and bypassed at the door an hour after it was written.
    model: str = Field(default="both", pattern="^(cycle|loyalty|both)$")
    model_why: str = Field(default="", max_length=300)
    category: str = Field(pattern="^(UTILITY|MARKETING|AUTHENTICATION)$")
    language: str = Field(default="ar", max_length=8)
    body: str = Field(min_length=1, max_length=1024)
    header: str = Field(default="", max_length=60)
    button: str | None = Field(default=None, max_length=32)
    # Who fills each variable — "system", "catalogue", or "owner", one entry per variable. It MUST
    # be declared here: pydantic drops a field the model does not name, silently and with a 200.
    # A live call caught exactly that — a template declaring two owner fields was accepted because
    # `fills` never reached the library that refuses it, and the unit test passed because it called
    # the library directly, never crossing this model. The rule was real; the path to it was not.
    fills: list[str] = Field(default_factory=list, max_length=4)
    active: bool = True

    model_config = {"populate_by_name": True}


@router.get("/templates", dependencies=[Depends(rate_limit)])
async def list_templates(request: Request, cls: str = "", tone: str = "", model: str = "",
                         principal: Principal = Depends(_PLATFORM)) -> dict:
    """The whole library, filterable by class or tone.

    Inactive ones included: a console that shows only what is live cannot show an operator what
    they retired last month, which is the first thing they look for when asked why a message
    stopped going out.
    """
    lib = _lib(request)
    if model:
        # Filtered by model rather than by class: this is the query a console makes when it wants
        # "what should a cafe be offered?", and answering it with a class filter would return the
        # cycle templates a cafe has no use for.
        try:
            rows = await lib.for_model(model, active_only=False)
        except TemplateError as exc:
            return _refuse(str(exc))
        if cls:
            rows = [r for r in rows if r.get("class") == cls]
        if tone:
            rows = [r for r in rows if r.get("tone") == tone]
        return {"templates": rows}
    return {"templates": await lib.list(cls=cls, tone=tone, active_only=False)}


@router.put("/templates/{name}", dependencies=[Depends(no_subscription_needed), Depends(rate_limit)])
async def upsert_template(request: Request, name: str, body: TemplateIn,
                          principal: Principal = Depends(_PLATFORM)) -> dict:
    """Create or replace a template — at runtime, with no rebuild and no restart.

    Takes effect for establishments onboarded AFTERWARDS. It does not rewrite what a tenant
    already has registered with Meta: that copy is approved under its own name, and silently
    diverging from an approved text is how a send starts failing for a reason nobody can see.
    """
    if name != body.name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "the name in the path and the body must match")
    await request.app.state.auditor.record(
        "platform.template_changed", actor=principal.subject, tenant="",
        resource=f"template:{name}", ip=request.client.host if request.client else "")
    try:
        return await _lib(request).upsert(body.model_dump(by_alias=True))
    except TemplateError as exc:
        return _refuse(str(exc))


@router.delete("/templates/{name}", dependencies=[Depends(no_subscription_needed), Depends(rate_limit)])
async def deactivate_template(request: Request, name: str,
                              principal: Principal = Depends(_PLATFORM)) -> dict:
    """Deactivate, never delete. Establishments carry this name in their registry and Meta holds
    an approved copy under it — deleting our row leaves both pointing at nothing we can explain."""
    await request.app.state.auditor.record(
        "platform.template_deactivated", actor=principal.subject, tenant="",
        resource=f"template:{name}", ip=request.client.host if request.client else "")
    if not await _lib(request).deactivate(name):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND")
    return {"name": name, "active": False}

# ── partners: who resells us, and what we owe them ────────────────────────────────────────────
class PartnerIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    # A FRACTION, and the bound is why. 30 instead of 0.3 would pay a partner thirty times the
    # subscription — and the mistake is invisible until the first statement, by which time it has
    # been agreed in writing with somebody.
    commission_rate: float = Field(gt=0, lt=1)
    contact: str = Field(default="", max_length=200)


@router.get("/partners", dependencies=[Depends(rate_limit)])
async def list_partners(request: Request, principal: Principal = Depends(_PLATFORM)) -> dict:
    """Every partner. The key hash never appears — see core/partners.py."""
    from app.config import get_settings
    reg = PartnerRegistry(request.app.state.container.datastore, salt=get_settings().PII_SALT)
    return {"partners": await reg.list()}


@router.post("/partners", dependencies=[Depends(no_subscription_needed), Depends(rate_limit)])
async def create_partner(request: Request, body: PartnerIn,
                         principal: Principal = Depends(_PLATFORM)) -> dict:
    """Register a partner and mint its key.

    THE KEY IS RETURNED ONCE AND NEVER AGAIN. It is a bearer credential that directs money, and a
    console that can re-read it is a console whose screenshot is a payout.
    """
    from app.config import get_settings
    await request.app.state.auditor.record(
        "partner.created", actor=principal.subject, tenant="", resource="partner",
        ip=request.client.host if request.client else "")
    reg = PartnerRegistry(request.app.state.container.datastore, salt=get_settings().PII_SALT)
    try:
        row, key = await reg.create(name=body.name, commission_rate=body.commission_rate,
                                    contact=body.contact)
    except PartnerError as exc:
        return _refuse(str(exc))
    return {"partner": {k: v for k, v in row.items() if k != "key_hash"},
            "key": key,
            "note": "المفتاح يظهر مرة واحدة فقط. احفظه الآن — لا يمكن استرجاعه."}


class RotateIn(BaseModel):
    # DAYS, not seconds, because a human sets this and thinks in days. Bounded at 90: an overlap
    # longer than a quarter is not a migration window, it is two live credentials nobody is
    # tracking.
    #
    # THE CONSOLE DEFAULTS TO 14 WHILE THE LIBRARY DEFAULTS TO 0, and the difference is deliberate.
    # A caller that omits the argument in code has not decided anything, so it gets the safe
    # answer. A human pressing "rotate" in a panel is performing a planned migration and would
    # otherwise take a partner's whole fleet offline with one click — and 0 is still available to
    # them, which is what they should choose for a leak.
    overlap_days: int = Field(default=14, ge=0, le=90)


@router.post("/partners/{partner_id}/rotate", dependencies=[Depends(no_subscription_needed), Depends(rate_limit)])
async def rotate_partner(request: Request, partner_id: str, body: RotateIn,
                         principal: Principal = Depends(_PLATFORM)) -> dict:
    """Issue a new key while the old one keeps working for a window that closes itself."""
    from app.config import get_settings
    await request.app.state.auditor.record(
        "partner.key_rotated", actor=principal.subject, tenant="",
        resource=f"partner:{partner_id}", ip=request.client.host if request.client else "")
    reg = PartnerRegistry(request.app.state.container.datastore, salt=get_settings().PII_SALT)
    try:
        row, key = await reg.rotate(partner_id, overlap_seconds=body.overlap_days * 86400)
    except PartnerError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    return {"partner_id": partner_id, "key": key,
            "old_key_valid_until": row["prev_key_expires"],
            "note": "المفتاح القديم يعمل حتى التاريخ أعلاه ثم يتوقف تلقائياً."}


@router.delete("/partners/{partner_id}", dependencies=[Depends(no_subscription_needed), Depends(rate_limit)])
async def deactivate_partner(request: Request, partner_id: str,
                             principal: Principal = Depends(_PLATFORM)) -> dict:
    """Stop NEW attributions. Existing shops keep their stamp — they came through this partner
    once, and a falling-out does not rewrite history or stop what is already owed."""
    from app.config import get_settings
    await request.app.state.auditor.record(
        "partner.deactivated", actor=principal.subject, tenant="",
        resource=f"partner:{partner_id}", ip=request.client.host if request.client else "")
    reg = PartnerRegistry(request.app.state.container.datastore, salt=get_settings().PII_SALT)
    if not await reg.deactivate(partner_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND")
    return {"partner_id": partner_id, "active": False,
            "note": "المحلات المختومة به تبقى مختومة، ومستحقاته القائمة لا تسقط."}



# ── the statements, from OUR side (§7) ─────────────────────────────────────────────────────────
#
# The partner has always been able to read his own (api/v1/partner.py). We could not read anybody's
# — there was no route, and no state on the row either, so «هل دفعنا له عن يونيو؟» was a question
# the panel could not answer and the truth lived in a WhatsApp thread.


@router.get("/statements", dependencies=[Depends(rate_limit)])
async def list_statements(request: Request, status: str = "", limit: int = 200,
                          principal: Principal = Depends(_PLATFORM)) -> dict:
    """Every partner's statements, newest first, filterable by state.

    BY STATE BECAUSE THAT IS THE QUESTION. «أيّها لم يُدفع بعد؟» is what this screen is opened
    for; a list of everything ever issued stops answering anything in the second month.
    """
    from app.core.commission import StatementStore
    rows = await StatementStore(request.app.state.container.datastore).all_statements(
        limit=max(1, min(limit, 500)), status=status.strip().lower())
    return {"statements": rows, "count": len(rows)}


class StatementStateIn(BaseModel):
    """Mark a statement paid, or dispute it."""

    # A WIRE REFERENCE, REQUIRED FOR A PAYMENT — enforced in the route rather than the model,
    # because it is required for one state and meaningless for the other.
    reference: str = Field(default="", max_length=128)
    note: str = Field(default="", max_length=500)
    # The bank's value date, not our clicking time — the same rule §4.2 states for our own money.
    paid_at: int = Field(default=0, ge=0)


@router.post("/statements/{partner_id}/{period_start}/paid", dependencies=[Depends(no_subscription_needed), Depends(rate_limit)])
async def mark_statement_paid(request: Request, partner_id: str, period_start: int,
                              body: StatementStateIn,
                              principal: Principal = Depends(_PLATFORM)) -> dict:
    """We paid this. Recorded with the wire reference and the value date.

    «دفعنا» WITH NO REFERENCE IS A CLAIM. With one it is a fact two parties can check against a
    bank statement months later, which is exactly when the question gets asked — and the moment
    the person who pressed the button no longer remembers.
    """
    from app.core.commission import PAID, StatementStore
    if not body.reference.strip():
        return {"ok": False, "reason": "REFERENCE_REQUIRED",
                "message": "أدخل مرجع الحوالة — بلا مرجع لا يمكن إثبات الدفع لاحقاً."}
    await request.app.state.auditor.record(
        "partner.statement_paid", actor=principal.subject, tenant="",
        resource=f"statement:{partner_id}:{period_start}",
        ip=request.client.host if request.client else "")
    row = await StatementStore(request.app.state.container.datastore).set_state(
        partner_id, period_start, state=PAID, actor=principal.subject,
        reference=body.reference.strip(), note=body.note.strip(), at=body.paid_at)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND")
    return {"ok": True, "statement": row}


@router.post("/statements/{partner_id}/{period_start}/dispute",
             dependencies=[Depends(no_subscription_needed), Depends(rate_limit)])
async def dispute_statement(request: Request, partner_id: str, period_start: int,
                            body: StatementStateIn,
                            principal: Principal = Depends(_PLATFORM)) -> dict:
    """A partner disagrees with a figure. Recorded, with the reason, before anybody recomputes.

    THE FLAG SURVIVES A RECOMPUTE (core/commission.py). Re-running is exactly what a disputed
    month needs — and the dispute is the reason it was re-run, so clearing it would erase the
    record of why the number changed.
    """
    from app.core.commission import DISPUTED, StatementStore
    if not body.note.strip():
        return {"ok": False, "reason": "NOTE_REQUIRED",
                "message": "اكتب سبب الاعتراض — «متنازَع عليه» بلا سبب لا يقود إلى أي إجراء."}
    await request.app.state.auditor.record(
        "partner.statement_disputed", actor=principal.subject, tenant="",
        resource=f"statement:{partner_id}:{period_start}",
        ip=request.client.host if request.client else "")
    row = await StatementStore(request.app.state.container.datastore).set_state(
        partner_id, period_start, state=DISPUTED, actor=principal.subject,
        note=body.note.strip())
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND")
    return {"ok": True, "statement": row}


@router.get("/partners/{partner_id}/health", dependencies=[Depends(rate_limit)])
async def partner_health(request: Request, partner_id: str, quiet_days: int = 7,
                         principal: Principal = Depends(_PLATFORM)) -> dict:
    """Is this partner's link alive — shop by shop?

    THE THREE STATES ARE THREE DIFFERENT PHONE CALLS. «لم يبدأ» is the vendor's integration never
    finished; «توقّف» is a link that worked and stopped; «يرسل» needs nobody. A single health
    light would collapse all three into a shrug, and the first of them — a shop enrolled weeks ago
    that never sent anything — has no row of its own to be found by, which is why the list is
    built from the partner's SHOPS rather than from what arrived.
    """
    from app.config import get_settings
    from app.core.till_health import TillHealth

    c = request.app.state.container
    reg = PartnerRegistry(c.datastore, salt=get_settings().PII_SALT)
    tenants = await reg.tenants_of(partner_id)
    rows = await TillHealth(c.datastore).for_tenants(tenants,
                                                     quiet_days=max(1, min(quiet_days, 90)))
    counts = {"never": 0, "quiet": 0, "sending": 0}
    for row in rows:
        counts[row["state"]] = counts.get(row["state"], 0) + 1
    return {"partner_id": partner_id, "shops": len(rows), "counts": counts, "health": rows}


class SandboxIn(BaseModel):
    """Turn an establishment into a vendor's test shop."""

    tenant: str = Field(min_length=1, max_length=128)
    # DAYS, and bounded. A test shop with no end date is a demo tenant from a sales call two years
    # ago, still on the cluster, still holding somebody's phone number in a customer row.
    days: int = Field(default=30, ge=1, le=180)


@router.post("/sandbox", dependencies=[Depends(no_subscription_needed), Depends(rate_limit)])
async def mark_sandbox(request: Request, body: SandboxIn,
                       principal: Principal = Depends(_PLATFORM)) -> dict:
    """Label a shop as a sandbox — same routes, same rules, no money.

    A SANDBOX IS A REAL TENANT WITH A LABEL, never a second code path. Every «if this is the test
    system» branch is one nobody exercises against production, and then the integration a vendor
    proved in it is the one that fails on their first real shop. The label does exactly two
    things: it earns its partner no commission, and it is not a customer in our numbers.

    THE CREDENTIAL IS THE ORDINARY ONE. A till talks to a sandbox with the same machine account it
    would hold for a real shop (§16.6) — a special test key would prove a path production does not
    take.
    """
    import time as _time

    await request.app.state.auditor.record(
        "tenant.sandboxed", actor=principal.subject, tenant=body.tenant, resource="tenant",
        ip=request.client.host if request.client else "")
    from app.core.integration import mark_sandbox as _mark
    ok = await _mark(request.app.state.container.datastore, body.tenant,
                     expires_at=int(_time.time()) + body.days * 86_400)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND")
    return {"tenant": body.tenant, "sandbox": True, "days": body.days,
            "note": "لا عمولة على محل تجريبي، ولا يُحسب عميلاً."}


class EvidenceRequest(BaseModel):
    tenant: str = Field(min_length=1, max_length=128)
    # A WINDOW, NOT «EVERYTHING» — see core/evidence.py. Zero means "from the beginning" and
    # "until now", which is the honest default for the first question anybody asks.
    since: int = Field(default=0, ge=0)
    until: int = Field(default=0, ge=0)


@router.post("/evidence", dependencies=[Depends(no_subscription_needed), Depends(rate_limit)])
async def evidence_file(request: Request, body: EvidenceRequest,
                        principal: Principal = Depends(_PLATFORM)) -> dict:
    """One establishment's evidence file, for whoever is handling the complaint.

    THE PANEL'S DOOR, AND THE INTERNAL ROUTE STAYS SEPARATE. The panel is rendered from declared
    admin actions, and the contract is explicit that an internal-token route is never one of them —
    correctly: an operator surface must be gated by a capability that a person holds and an audit
    that names them, not by a shared service token.

    THE ACTOR IS THE TOKEN'S SUBJECT, never a field in the body. «Who took a copy of this» is the
    one fact this record exists for, and a self-declared name is not an answer.
    """
    c = request.app.state.container
    actor = getattr(principal, "subject", "") or ""
    await request.app.state.auditor.record(
        "compliance.evidence_exported", actor=actor, tenant=body.tenant,
        resource="evidence_file", ip=request.client.host if request.client else "",
        metadata={"since": body.since, "until": body.until, "asked_by": actor})
    file = EV.EvidenceFile(
        privacy_store=PrivacyRequestStore(c.datastore),
        consent_reader=getattr(c, "evidence_peer", None),
        legal_reader=getattr(c, "legal_acceptances", None))
    return await file.build(body.tenant, since=body.since, until=body.until, actor=actor)
