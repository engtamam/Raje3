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
from pydantic import BaseModel, Field, field_validator

from app.api.auth import Principal
from app.api.authz import require_capability
from app.api.ratelimit import rate_limit
from app.config import get_settings
from app.core import evidence as EV
from app.core import wallet_topup_reconcile as wallet_topup_core
from app.core.seats import BRANCHES, SEATS
from app.core.stores import BranchStore, OperatorStore, PrivacyRequestStore
from app.core.partners import PartnerError, PartnerRegistry, validate_commission_rate
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
    tone: str = Field(default="", pattern="^(masculine|feminine|)$")
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
        # A SECOND, CORRECTIVE ENTRY — fixed 2026-09-12, a real gap a QA audit found.
        await request.app.state.auditor.record(
            "platform.template_changed", actor=principal.subject, tenant="",
            resource=f"template:{name}", ip=request.client.host if request.client else "",
            metadata={"outcome": "refused", "reason": str(exc)})
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
    # NO BOUND WRITTEN HERE — see the field_validator below. `0` and `1` used to be re-typed as a
    # Field(ge=..., lt=...) at this exact spot, and PartnerRegistry.create() re-typed them a
    # second time as its own domain guard; the two drifted the day one was widened to allow a 0%
    # rate and nobody remembered the other copy existed. core/partners.py::validate_commission_rate
    # is now the one place the bound lives — this model calls it rather than restating it.
    commission_rate: float
    contact: str = Field(default="", max_length=200)

    @field_validator("commission_rate")
    @classmethod
    def _valid_commission_rate(cls, v: float) -> float:
        try:
            validate_commission_rate(v)
        except PartnerError as exc:
            raise ValueError(str(exc)) from exc
        return v


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
        # A SECOND, CORRECTIVE ENTRY — fixed 2026-09-12, a real gap a QA audit found.
        await request.app.state.auditor.record(
            "partner.created", actor=principal.subject, tenant="", resource="partner",
            ip=request.client.host if request.client else "",
            metadata={"outcome": "refused", "reason": str(exc)})
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
        # A SECOND, CORRECTIVE ENTRY — fixed 2026-09-12, a real gap a QA audit found.
        await request.app.state.auditor.record(
            "partner.key_rotated", actor=principal.subject, tenant="",
            resource=f"partner:{partner_id}", ip=request.client.host if request.client else "",
            metadata={"outcome": "refused", "reason": str(exc)})
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
    from app.core.commission import PAID, StatementBusy, StatementStore
    if not body.reference.strip():
        return {"ok": False, "reason": "REFERENCE_REQUIRED",
                "message": "أدخل مرجع الحوالة — بلا مرجع لا يمكن إثبات الدفع لاحقاً."}
    await request.app.state.auditor.record(
        "partner.statement_paid", actor=principal.subject, tenant="",
        resource=f"statement:{partner_id}:{period_start}",
        ip=request.client.host if request.client else "")
    try:
        row = await StatementStore(request.app.state.container.datastore).set_state(
            partner_id, period_start, state=PAID, actor=principal.subject,
            reference=body.reference.strip(), note=body.note.strip(), at=body.paid_at)
    except StatementBusy:
        return {"ok": False, "reason": "BUSY",
                "message": "يجري تحديث هذا الكشف الآن — أعد المحاولة بعد لحظة."}
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
    from app.core.commission import DISPUTED, StatementBusy, StatementStore
    if not body.note.strip():
        return {"ok": False, "reason": "NOTE_REQUIRED",
                "message": "اكتب سبب الاعتراض — «متنازَع عليه» بلا سبب لا يقود إلى أي إجراء."}
    await request.app.state.auditor.record(
        "partner.statement_disputed", actor=principal.subject, tenant="",
        resource=f"statement:{partner_id}:{period_start}",
        ip=request.client.host if request.client else "")
    try:
        row = await StatementStore(request.app.state.container.datastore).set_state(
            partner_id, period_start, state=DISPUTED, actor=principal.subject,
            note=body.note.strip())
    except StatementBusy:
        return {"ok": False, "reason": "BUSY",
                "message": "يجري تحديث هذا الكشف الآن — أعد المحاولة بعد لحظة."}
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


@router.post("/wallet-topups/reconcile-now",
             dependencies=[Depends(no_subscription_needed), Depends(rate_limit)])
async def wallet_topups_reconcile_now(request: Request,
                                      principal: Principal = Depends(_PLATFORM)) -> dict:
    """The same sweep the CronJob runs every 5 minutes (see
    app/core/wallet_topup_reconcile.py's own header) — for the one moment somebody is staring at a
    stuck top-up and does not want to wait for the next scheduled pass.

    THE INTERNAL-TOKEN ROUTE STAYS SEPARATE (`/internal/operations/wallet-topups/reconcile`),
    exactly as the evidence file's own note above explains: a person-facing trigger is gated by a
    capability a person holds and an audit that names them, never by the shared internal token.
    """
    s = get_settings()
    actor = getattr(principal, "subject", "") or ""
    topups = wallet_topup_core.HttpWalletTopups(
        billing_url=s.BILLING_SERVICE_URL, identity_url=s.IDENTITY_SERVICE_URL,
        client_id=s.BILLING_CLIENT_ID, client_secret=s.BILLING_CLIENT_SECRET,
        pending_path=s.BILLING_WALLET_TOPUPS_PENDING_PATH,
        reconcile_path=s.BILLING_WALLET_TOPUP_RECONCILE_PATH,
        timeout=s.PEER_TIMEOUT_SECONDS, limit=s.WALLET_TOPUP_RECONCILE_LIMIT,
        older_than_seconds=s.WALLET_TOPUP_RECONCILE_OLDER_THAN_SECONDS)
    out = await wallet_topup_core.WalletTopupReconciler(topups=topups).run()
    await request.app.state.auditor.record(
        "billing.wallet_topups_reconciled", actor=actor, tenant="", resource="wallet-topups",
        ip=request.client.host if request.client else "")
    return out.to_dict()


@router.get("/branches/locations", dependencies=[Depends(rate_limit)])
async def branch_locations(request: Request, limit: int = 200, after: str = "",
                           principal: Principal = Depends(_PLATFORM)) -> dict:
    """Every ACTIVE branch across every tenant that has actually located itself — for the admin
    panel's own map. Crosses the tenancy wall this service's own
    `core/stores.py` header note exists to enforce everywhere else, so it is fenced the same way
    `BranchStore.browse_platform` documents: capability-gated (`platform.operations`), a bounded
    page, and audited here — never a raw unfiltered scan reachable from a route.

    ROWS WITH NO LOCATION SET ARE DROPPED, not shown at (0, 0) — an owner who never opened
    «فريقي» and set a location said nothing, and (0, 0) is a real point in the Gulf of Guinea, not
    a null island convention this response invents on his behalf.
    """
    await request.app.state.auditor.record(
        "platform.branch_locations_viewed", actor=getattr(principal, "subject", "") or "",
        tenant="", resource="branches:all-tenants",
        ip=request.client.host if request.client else "")
    store = BranchStore(request.app.state.container.datastore)
    rows, nxt = await store.browse_platform(limit=limit, after=after or None)
    located = [b.public() for b in rows if b.lat != 0.0 or b.lng != 0.0]
    return {"branches": located, "next_cursor": nxt}


@router.get("/tenants/{tenant_id}/capacity", dependencies=[Depends(rate_limit)])
async def tenant_capacity(request: Request, tenant_id: str,
                          principal: Principal = Depends(_PLATFORM)) -> dict:
    """How many branches and staff (operators) ONE establishment actually has, AND the entitled
    limit (how many it is paid for) next to each — for the admin console's «العملاء والدعم»
    screen. Counts are a plain read (`BranchStore.list`/`OperatorStore.list`, tenant-scoped,
    already used by the shop's own «فريقي» screen — this route just reads them for a tenant the
    caller NAMES rather than the caller's own).

    THE LIMIT WAS WRONGLY THOUGHT UNREACHABLE HERE, and it never was: `core/seats.py`'s own
    `HttpGauges.allows_one_more` — the SAME call `guard_and_report` makes on every hire/branch-add
    to enforce the cap — already returns `(allowed, limit)`. The limit is not a new number to ask
    billing-service for; it is the second half of a call this service makes constantly. Calling it
    here for DISPLAY, with the CURRENT true count, asks nothing billing-service cannot already
    answer and mutates nothing (`allows_one_more` is a read).

    `-1` means unlimited or unreachable (billing down, or an unlimited plan) — `guard_and_report`
    treats both as "allow", and the console shows no ceiling rather than inventing one.
    """
    await request.app.state.auditor.record(
        "platform.tenant_capacity_viewed", actor=getattr(principal, "subject", "") or "",
        tenant=tenant_id, resource=f"tenant:{tenant_id}",
        ip=request.client.host if request.client else "")
    ds = request.app.state.container.datastore
    branches = await BranchStore(ds).list(tenant_id)
    operators = await OperatorStore(ds).list(tenant_id)
    branch_n, operator_n = len(branches), len(operators)
    gauges = request.app.state.container.gauges
    _, branches_limit = await gauges.allows_one_more(tenant_id, BRANCHES, branch_n)
    _, operators_limit = await gauges.allows_one_more(tenant_id, SEATS, operator_n)
    return {"branches": branch_n, "operators": operator_n,
            "branches_limit": branches_limit, "operators_limit": operators_limit}


@router.get("/whatsapp/diagnostics", dependencies=[Depends(rate_limit)])
async def whatsapp_diagnostics(request: Request, tenant: str = "", phone_number_id: str = "",
                               principal: Principal = Depends(_PLATFORM)) -> dict:
    """«ليش واتساب هذا المحل معطّل؟» — one shop's own delivery history, read by tenant id or by
    Meta's phone_number_id (an operator usually has the number first, not our internal id).

    THE PANEL'S DOOR, THE INTERNAL ROUTE STAYS SEPARATE — same rule as `evidence_file` above:
    `notification-service`'s own `/internal/whatsapp/deliveries` is guarded by a shared service
    token, never a declared admin action there. This route is the operator surface: gated by
    `platform.operations`, audited here by the actual person asking, and the peer call happens
    through `container.whatsapp_diagnostics` so the browser's token never has to carry the
    internal one.
    """
    if not tenant and not phone_number_id:
        return _refuse("مرّر tenant أو phone_number_id — لا بحث بلا أحدهما.")
    await request.app.state.auditor.record(
        "platform.whatsapp_diagnostics_viewed", actor=getattr(principal, "subject", "") or "",
        tenant=tenant, resource=f"whatsapp:{tenant or phone_number_id}",
        ip=request.client.host if request.client else "")
    desk = request.app.state.container.whatsapp_diagnostics
    out = (await desk.by_tenant(tenant)) if tenant else (await desk.by_phone_number_id(phone_number_id))
    if out is None:
        return JSONResponse(
            {"error": "UNAVAILABLE", "reason": "تعذّر الاتصال بخدمة الإشعارات الآن."},
            status_code=502)
    return out


@router.get("/whatsapp/flow-json", dependencies=[Depends(rate_limit)])
async def whatsapp_flow_json(request: Request, name: str,
                             principal: Principal = Depends(_PLATFORM)) -> Any:
    """The REAL generated screens JSON for one Flow — what `AdminWhatsAppTemplates.tsx`'s preview
    renders, the exact document Meta itself would show, never a hand-modeled stand-in. See
    `WhatsAppDiagnostics.flow_json`'s own docstring for why a bad name is a 404, not a 502.
    """
    await request.app.state.auditor.record(
        "platform.whatsapp_flow_json_viewed", actor=getattr(principal, "subject", "") or "",
        tenant="", resource=f"whatsapp-flow:{name}",
        ip=request.client.host if request.client else "")
    desk = request.app.state.container.whatsapp_diagnostics
    status, out = await desk.flow_json(name)
    if status != 200:
        return JSONResponse(out, status_code=status)
    return out


@router.get("/customers/by-phone", dependencies=[Depends(rate_limit)])
async def platform_customer_by_phone(request: Request, tenant: str, phone: str,
                                     principal: Principal = Depends(_PLATFORM)) -> dict:
    """The «الامتثال» support screen's own door: a support/compliance operator already knows which
    ESTABLISHMENT they are helping (they pick it explicitly — never guessed, never every shop
    searched at once) and needs that one customer's profile to act on.

    SAME CORE LOOKUP AS THE SHOP'S OWN SCREEN (`field.py::customer_by_phone`), under the SAME
    weak-role search discipline (`Operations.customer_by_phone_searched` — see its own docstring:
    two steps, the risky "match an arbitrary string against every phone number" half runs under a
    role that can see nothing else). The only difference here is WHO is asking and WHICH tenant:
    an explicit `tenant` param, gated by `platform.operations` rather than the caller's own tenant
    claim — this is the cross-shop admin surface `field.py`'s route deliberately is not.

    AUDITED THE SAME WAY, hit or miss, resource carrying only the last 4 digits — never the full
    number, never a name — for the exact reason `customer.searched_by_phone` already states: an
    audit trail that stored the full number would recreate the exact problem it exists to catch.
    A DISTINCT action (`platform.customer_searched_by_phone`, not that same action) because this is
    a cross-shop admin read under `platform.operations`, not the shop's own `operations.read` — the
    two must stay separately answerable, same as every other `platform.*` action in this file.

    CARRIES `subject_ref` ON TOP OF `public()`, UNLIKE THE SHOP'S OWN SCREEN. `public()` withholds
    it deliberately (a shop owner has no use for the pseudonym other services key rows by), but the
    admin panel does: the «سجل الأخطاء» screen's own customer search resolves phone → subject_ref
    HERE, once, then asks error-collector for that pseudonym's signals — the same two-step shape as
    every other cross-service admin lookup on this platform (never a raw phone number sent onward).
    Safe to expose here specifically because this whole route already sits behind
    `platform.operations`, the same capability that already lets an operator read this customer's
    full profile.
    """
    await request.app.state.auditor.record(
        "platform.customer_searched_by_phone", actor=getattr(principal, "subject", "") or "",
        tenant=tenant, resource=f"phone-suffix:{phone[-4:]}",
        ip=request.client.host if request.client else "")
    c = await request.app.state.container.operations.customer_by_phone_searched(tenant, phone)
    if c is None:
        return {"customer": None}
    return {"customer": {**c.public(), "subject_ref": c.subject_ref}}


@router.get("/whatsapp/platform-status", dependencies=[Depends(rate_limit)])
async def whatsapp_platform_status(request: Request,
                                   principal: Principal = Depends(_PLATFORM)) -> dict:
    """The Meta category's "Status" tab (Raje3 Meta-panel Phase 1, cheapest slice — nothing here is
    a new call to Meta, only data this platform already holds).

    THE PLATFORM'S OWN NUMBERS, NEVER A SHOP'S. `AdminProviderSecrets.tsx`'s Meta secrets
    (META_APP_ID, WHATSAPP_ACCESS_TOKEN, …) are OUR sending identity — the same one that sends a
    signup OTP — not any one establishment's connected WhatsApp. So this answers four things about
    the platform as a whole:

      1. per-number CONNECTION state — read in-process from `ConnectionStore.all()`, this service's
         own table, with no peer call at all;
      2. real WhatsApp delivery counts over the most recent rows — `notification-service`'s
         `DeliveryStore`, asked through `container.platform_status` (never this service's own copy
         of that data, which does not exist);
      3. how many WhatsApp numbers are currently bound — `notification-service`'s
         `WhatsAppNumberIndex`, same call;
      4. how many customers have opted out of marketing — `notification-service`'s
         `PreferenceStore`, same call.

    TWO INDEPENDENT READS, EACH ANSWERED HONESTLY ON ITS OWN. A `notification-service` outage must
    not blank the connection states this service already knows, and a slow `ConnectionStore` scan
    must not block the delivery figures — so both are fetched, and the peer's own unavailability is
    reported IN the response (`peer_unavailable`) rather than failing the whole request.

    THE PEER'S FIGURES ARE CAPPED COUNTS, NOT A TIME WINDOW (platform v0.19.6): each is exact over
    the most-recent `cap` rows (`notification-service`'s own `NOTIFY_PLATFORM_STATUS_CAP`, default
    5000) and marked `capped` past it — there is no `window_hours` any more, and the peer's own
    nested shape ({"deliveries": {...}, "bound_numbers": {"count","capped"}, ...}) is reshaped here
    into the flat fields the console already renders, so the console never has to know the peer's
    internal envelope.
    """
    from app.core.connect import ConnectionStore

    await request.app.state.auditor.record(
        "platform.whatsapp_status_viewed", actor=getattr(principal, "subject", "") or "",
        tenant="", resource="whatsapp:platform-status",
        ip=request.client.host if request.client else "")
    ds = request.app.state.container.datastore
    rows = await ConnectionStore(ds).all()
    counts: dict[str, int] = {}
    for r in rows:
        counts[r.state] = counts.get(r.state, 0) + 1
    connections = {
        "total": len(rows), "by_state": counts,
        # Newest first, and capped — this is a status glance, never a full export of every number
        # this platform has ever connected.
        "numbers": [r.to_dict() for r in sorted(rows, key=lambda r: -r.at)[:200]],
    }
    peer = request.app.state.container.platform_status
    remote = await peer.read()
    if remote is None:
        return {"connections": connections, "peer_unavailable": True,
                "deliveries": None, "numbers_bound": None, "marketing_opt_outs": None}
    deliveries = remote.get("deliveries") or {}
    bound = remote.get("bound_numbers") or {}
    opt_outs = remote.get("marketing_opt_outs") or {}
    return {
        "connections": connections, "peer_unavailable": False,
        "deliveries": {
            "sent": deliveries.get("sent", 0), "failed": deliveries.get("failed", 0),
            "delivered": deliveries.get("delivered", 0), "read": deliveries.get("read", 0),
            # how many of the most-recent messages this figure was actually computed over, and
            # whether that hit the cap — the console shows "آخر N رسالة" instead of a false "24 ساعة".
            "sampled": deliveries.get("sampled", 0), "capped": bool(deliveries.get("capped")),
        },
        "numbers_bound": bound.get("count"), "numbers_bound_capped": bool(bound.get("capped")),
        "marketing_opt_outs": opt_outs.get("count"),
        "marketing_opt_outs_capped": bool(opt_outs.get("capped")),
    }


# ── ONE SHOP'S OWN CONNECTED WHATSAPP NUMBER (platform v0.19.9) — sits next to `whatsapp_diagnostics`
# above, same per-shop scope: `tenant`'s OWN number, never the platform's own Meta identity. All four
# peer through `container.whatsapp_admin` (see that adapter's own header). ─────────────────────────

@router.get("/whatsapp/messaging-limit", dependencies=[Depends(rate_limit)])
async def whatsapp_messaging_limit(request: Request, tenant: str,
                                   principal: Principal = Depends(_PLATFORM)) -> dict:
    """This shop's WhatsApp messaging-limit tier + quality rating — a real gap this closes: the
    peer route existed before this batch (platform v0.19.x) but was never wired to any admin
    screen. Placed alongside diagnostics: "why is this shop's WhatsApp broken" often IS a spent
    daily limit, not a delivery failure."""
    if not tenant:
        return _refuse("مرّر tenant.")
    await request.app.state.auditor.record(
        "platform.whatsapp_messaging_limit_viewed", actor=getattr(principal, "subject", "") or "",
        tenant=tenant, resource=f"whatsapp:{tenant}",
        ip=request.client.host if request.client else "")
    out = await request.app.state.container.whatsapp_admin.messaging_limit(tenant)
    if out is None or "_status" in out:
        return JSONResponse({"error": "UNAVAILABLE", "reason": "تعذّر الاتصال بخدمة الإشعارات الآن."},
                            status_code=502)
    return out


@router.get("/whatsapp/subscribed-fields", dependencies=[Depends(rate_limit)])
async def whatsapp_subscribed_fields(request: Request, tenant: str,
                                     principal: Principal = Depends(_PLATFORM)) -> dict:
    """Which apps (and webhook fields) Meta is ACTUALLY sending for this shop's WABA — read-only,
    always: Meta configures subscribed fields at the APP level (App Dashboard), never per-WABA, so
    there is no write route to mirror here and none should ever be added — this exists only to
    CONFIRM what is really wired, which an operator otherwise cannot see at all."""
    if not tenant:
        return _refuse("مرّر tenant.")
    await request.app.state.auditor.record(
        "platform.whatsapp_subscribed_fields_viewed", actor=getattr(principal, "subject", "") or "",
        tenant=tenant, resource=f"whatsapp:{tenant}",
        ip=request.client.host if request.client else "")
    out = await request.app.state.container.whatsapp_admin.subscribed_fields(tenant)
    if out is None:
        return JSONResponse({"error": "UNAVAILABLE", "reason": "تعذّر الاتصال بخدمة الإشعارات الآن."},
                            status_code=502)
    if "_status" in out:
        code = out["_status"]
        reason = "NOT_CONNECTED" if code == 409 else out.get("detail", "META_ERROR")
        return JSONResponse({"error": "PEER_REFUSED", "reason": reason}, status_code=code)
    return {"apps": out.get("apps", [])}


@router.get("/whatsapp/business-verification", dependencies=[Depends(rate_limit)])
async def whatsapp_business_verification(request: Request, tenant: str,
                                         principal: Principal = Depends(_PLATFORM)) -> dict:
    """The WABA's business_verification_status + overall status — gates template-review speed and
    throughput upgrades, so an operator should be able to see it rather than guess it from symptoms."""
    if not tenant:
        return _refuse("مرّر tenant.")
    await request.app.state.auditor.record(
        "platform.whatsapp_business_verification_viewed", actor=getattr(principal, "subject", "") or "",
        tenant=tenant, resource=f"whatsapp:{tenant}",
        ip=request.client.host if request.client else "")
    out = await request.app.state.container.whatsapp_admin.business_verification(tenant)
    if out is None:
        return JSONResponse({"error": "UNAVAILABLE", "reason": "تعذّر الاتصال بخدمة الإشعارات الآن."},
                            status_code=502)
    if "_status" in out:
        code = out["_status"]
        reason = "NOT_CONNECTED" if code == 409 else out.get("detail", "META_ERROR")
        return JSONResponse({"error": "PEER_REFUSED", "reason": reason}, status_code=code)
    return {"business_verification_status": out.get("business_verification_status", ""),
            "status": out.get("status", "")}


class TwoStepPinIn(BaseModel):
    tenant: str = Field(min_length=1, max_length=128)
    phone_number_id: str = Field(default="", max_length=128)
    # Client-side courtesy only — the peer validates the same 6-digit shape server-side regardless
    # (notification-service's own `TwoStepPinIn`), so a raw API call cannot bypass this.
    pin: str = Field(pattern=r"^[0-9]{6}$")


@router.post("/whatsapp/two-step-pin", dependencies=[Depends(rate_limit)])
async def whatsapp_set_two_step_pin(request: Request, body: TwoStepPinIn,
                                    principal: Principal = Depends(_PLATFORM)) -> dict:
    """Set/rotate a shop's own WhatsApp two-step-verification PIN — a credential-changing write, so
    it is audited BEFORE the call (write-ahead, same discipline as `secrets.update`), and the PIN
    itself never appears in that audit row or in this route's response: `{ok: True}` on success,
    never an echo of what was just set — matching the peer's own write-only guarantee."""
    actor = getattr(principal, "subject", "") or ""
    await request.app.state.auditor.record(
        "platform.whatsapp_two_step_pin_set", actor=actor, tenant=body.tenant,
        resource=f"whatsapp:{body.tenant}", ip=request.client.host if request.client else "")
    out = await request.app.state.container.whatsapp_admin.set_two_step_pin(
        tenant=body.tenant, phone_number_id=body.phone_number_id, pin=body.pin)
    if out is None:
        return JSONResponse({"ok": False, "reason": "UNAVAILABLE"}, status_code=502)
    if "_status" in out:
        code = out["_status"]
        reason = "NOT_CONNECTED" if code == 409 else out.get("reason", "META_ERROR")
        return JSONResponse({"ok": False, "reason": reason}, status_code=code)
    if not out.get("ok"):
        return JSONResponse({"ok": False, "reason": out.get("reason", "META_ERROR")}, status_code=400)
    return {"ok": True}


class CustomerSuccessTenantIn(BaseModel):
    id: str = Field(min_length=1, max_length=128)
    name: str = Field(default="", max_length=256)
    # ISO 8601, exactly the shape tenant-service's own tenant.list already answers with
    # (`Tenant.created_at`) — the console already holds this list, this route never calls
    # tenant-service itself.
    created_at: str = Field(default="")


class CustomerSuccessIn(BaseModel):
    tenants: list[CustomerSuccessTenantIn]
    # Days with no service added before a fresh signup counts as "stalled". A plain number, not a
    # hardcoded constant, because base-services-9f/تمام may want to tune it without a redeploy —
    # but it IS bounded (1-30) so a typo cannot turn this into a 0-day or year-long window.
    stall_days: int = Field(default=3, ge=1, le=30)


@router.post("/customers/success-scan", dependencies=[Depends(rate_limit)])
async def customer_success_scan(request: Request, body: CustomerSuccessIn,
                                principal: Principal = Depends(_PLATFORM)) -> dict:
    """«نجاح العملاء» — which shops may be stalling, computed for real from this service's own
    visit/service records, never guessed.

    THE CALLER SUPPLIES THE TENANT LIST (id + created_at), because tenant-service — not this
    service — owns it, and the console already holds it (the same `tenant.list` call
    `CustomerList.tsx` makes). This route does not call tenant-service itself; it only asks its OWN
    data two bounded questions per tenant (`Operations.customer_success_flags`) — no scan, no N+1
    against a peer, cost bounded by however many tenants the caller sent (capped the same way
    `CustomerList.tsx`'s own TENANT_LIST_LIMIT already caps that list).

    A tenant with an unparsable/missing `created_at` is skipped for the stall check (never treated
    as "just signed up", which would false-negative it forever, nor as "ancient", which would
    false-positive it immediately) but still checked for the no-visits signal.
    """
    import datetime as _dt

    svc = request.app.state.container.operations
    now = _dt.datetime.now(_dt.timezone.utc).timestamp()
    out: list[dict] = []
    for t in body.tenants[:200]:      # same order-of-magnitude cap as tenant.list's own ceiling
        try:
            created = _dt.datetime.fromisoformat(t.created_at.replace("Z", "+00:00")).timestamp()
        except (ValueError, AttributeError):
            created = now      # unparsable -> never flagged as "stalled since signup" (see docstring)
        flags = await svc.customer_success_flags(
            t.id, created_at=created, now=now, stall_seconds=body.stall_days * 86400)
        if flags["no_services_after_stall"] or flags["has_services_no_visits"]:
            out.append({"tenant": t.id, "name": t.name, **flags})
    await request.app.state.auditor.record(
        "platform.customer_success_scanned", actor=getattr(principal, "subject", "") or "",
        tenant="", resource=f"tenants:{len(body.tenants)}",
        ip=request.client.host if request.client else "")
    return {"stalling": out, "scanned": len(body.tenants)}


@router.post("/flows/subscription-renewal/seed", dependencies=[Depends(rate_limit)])
async def seed_subscription_renewal_flow(request: Request,
                                         principal: Principal = Depends(_PLATFORM)) -> dict:
    """Author the subscription-renewal Flow on `PLATFORM` ("_platform"), ONCE — a manual admin
    action, never a connect-time or install-time automatic step (owner's decision, 2026-09-10:
    nothing reaches Meta on a fresh install with no WhatsApp connection yet, and this Flow is
    platform-owned exactly like the `auth_otp` template, never per-shop like rating/report/
    booking's own clone-at-connect Flows — see core/flows.py's own module comments).

    IDEMPOTENT: the second call (a re-run, a retry) finds the id already stored in RuntimeConfig
    and does nothing further, same "already done" posture the three bootstrap scripts hold for
    their own master Flows."""
    from app.config import Settings
    from app.core.flows import (PLATFORM, SUBSCRIPTION_RENEWAL_FLOW_CATEGORIES,
                                SUBSCRIPTION_RENEWAL_FLOW_JSON, SUBSCRIPTION_RENEWAL_FLOW_NAME,
                                provision_shop_flow_encryption)
    from app.core.runtime_config import RuntimeConfig
    from app.runtime_policy import RUNTIME_POLICY

    s = get_settings()
    c = request.app.state.container
    rc = RuntimeConfig(c.datastore, Settings, policy=RUNTIME_POLICY)
    existing = await rc.get(tenant="", key="MASTER_SUBSCRIPTION_RENEWAL_FLOW_ID",
                            default=s.MASTER_SUBSCRIPTION_RENEWAL_FLOW_ID)
    if existing:
        return {"ok": True, "flow_id": existing, "already_seeded": True}

    endpoint_uri = (f"{s.PUBLIC_BASE_URL}/webhooks/whatsapp/flow/{PLATFORM}/"
                    f"{SUBSCRIPTION_RENEWAL_FLOW_NAME}" if s.PUBLIC_BASE_URL else "")
    out = await c.flows.author_master(
        name=SUBSCRIPTION_RENEWAL_FLOW_NAME, categories=SUBSCRIPTION_RENEWAL_FLOW_CATEGORIES,
        flow_json=SUBSCRIPTION_RENEWAL_FLOW_JSON, endpoint_uri=endpoint_uri)
    if not out.get("ok") or not out.get("flow_id"):
        # RETURNED, NEVER RAISED — the platform's global error handler strips a raised
        # HTTPException's own `detail`, and this reason is the one thing the admin who pressed
        # the button needs to actually see (ci/check_refusal_survives.py).
        return JSONResponse({"ok": False, "reason": out.get("reason") or "flow authoring failed"},
                            status_code=status.HTTP_502_BAD_GATEWAY)
    await rc.set(tenant="", key="MASTER_SUBSCRIPTION_RENEWAL_FLOW_ID", value=out["flow_id"],
                actor_ref=getattr(principal, "subject", "") or "")
    # THE FLOW'S OTHER HALF — same call the three clone-per-shop Flows make at connect time, here
    # made once, for PLATFORM's own number rather than a shop's.
    enc = await provision_shop_flow_encryption(c.flows, PLATFORM)
    await request.app.state.auditor.record(
        "platform.subscription_renewal_flow_seeded", actor=getattr(principal, "subject", "") or "",
        tenant="", resource=f"flow:{out['flow_id']}",
        ip=request.client.host if request.client else "")
    return {"ok": True, "flow_id": out["flow_id"], "already_seeded": False,
            "encryption": enc.get("ok", False)}
