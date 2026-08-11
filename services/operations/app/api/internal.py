# =============================================================================
# operations — Internal tier (service-to-service, X-Internal-Token)
# -----------------------------------------------------------------------------
# NOT user-facing. Guarded by a shared token compared in CONSTANT TIME
# (CWE-208: observable timing discrepancy). Never a user JWT.
# =============================================================================
from __future__ import annotations

import hmac
import time

from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from app.config import Settings, get_settings
from app.core.erasure import OperationsErasure
from app.core import retention as retention_core
from app.core.models import CUSTOMERS, VISITS
from app.core import invoices as _invoices
from app.core.integration import Integration
from app.core.partners import PartnerError, PartnerRegistry
from app.core.stores import ServiceStore, VisitStore, new_id
from app.core.operations import OperationError
from app.core.sectors import SectorError
from app.core import backup as _backup
from app.backup_manifest import BACKUP
from app.manifest import build_manifest

router = APIRouter(prefix="/internal", tags=["internal"])


def _now_iso() -> str:
    import datetime as _dt
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

_HEADER = "X-Internal-Token"


async def require_internal_token(
    x_internal_token: str | None = Header(default=None, alias=_HEADER),
    settings: Settings = Depends(get_settings),
) -> None:
    """Deny unless the caller presents the exact internal token (timing-safe)."""
    expected = settings.INTERNAL_SERVICE_TOKEN
    provided = x_internal_token or ""
    # hmac.compare_digest is constant-time and length-safe.
    if not hmac.compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="UNAUTHORIZED"
        )


@router.get("/health", dependencies=[Depends(require_internal_token)])
async def internal_health(settings: Settings = Depends(get_settings)) -> dict[str, str]:
    return {"status": "ok", "service": settings.SERVICE_NAME}


@router.get("/manifest", dependencies=[Depends(require_internal_token)])
async def internal_manifest(
    request: Request, settings: Settings = Depends(get_settings)
) -> dict:
    container = getattr(request.app.state, "container", None)
    ports = container.describe() if container is not None else []
    manifest = build_manifest(settings, ports=ports)
    guard = getattr(request.app.state, "cwe_guard", None)
    if guard is not None:
        manifest["security"] = {"cwe_guard": guard.report()}
    return manifest


class EraseIn(BaseModel):
    tenant: str
    subject: str


@router.post("/privacy/erase", dependencies=[Depends(require_internal_token)])
async def erase_subject(request: Request, body: EraseIn) -> dict:
    """Erase a data subject. Called by compliance-service during a DSAR fan-out.

    Returns the ack: what was erased, and what was RETAINED with its legal basis. Idempotent — a
    DSAR retries, so erasing an already-erased subject must not fail. Wire this service into the
    fan-out by adding it to PRIVACY_TARGETS in compliance-service's values file; the
    safety:privacy-wiring gate fails if you implement this and forget.
    """
    c = request.app.state.container
    s = get_settings()
    # Write-ahead, and CRITICAL. Erasure is irreversible and this service holds the phone number
    # itself — after it runs, nothing else can show that it did. Recording afterwards would leave
    # the one case that matters unrecorded: the erasure that half-succeeded.
    await request.app.state.auditor.record(
        "subject.erased", actor="", tenant=body.tenant, resource="subject",
        ip=request.client.host if request.client else "")
    eraser = OperationsErasure(store=c.datastore, pii_salt=s.PII_SALT,
                               max_scan=s.ERASURE_MAX_SCAN)
    return await eraser.erase(body.tenant, body.subject)


class BatchVisitIn(BaseModel):
    """One visit inside a drained batch, as an integration SDK sends it."""
    # PERMISSIVE ON PURPOSE, and this is the whole point of the endpoint rather than a relaxation
    # of it. The interactive route validates hard, because a person is looking at the response and
    # can fix it. Here nobody is looking: a drained queue may contain an entry that was valid when
    # the till recorded it and is not valid now.
    #
    # If the MODEL rejects that entry, pydantic fails the whole request — and the all-or-nothing
    # batch is back, one layer above the per-item results that were built to prevent it. The item
    # would be retried, fail identically, and block everything behind it forever. So the shape is
    # accepted here and the BUSINESS rule decides, per item, in the loop below, where a rejection
    # is reported rather than fatal.
    #
    # Found by calling the endpoint. Reading the code, both layers looked correct.
    tenant: str = Field(default="", max_length=128)
    phone: str = Field(default="", max_length=32)
    service_ids: list[str] = Field(default_factory=list, max_length=20)
    name: str = Field(default="", max_length=128)
    plate: str = Field(default="", max_length=32)
    operator_id: str = Field(default="", max_length=64)
    branch_id: str = Field(default="", max_length=64)
    meter: int = Field(default=0, ge=0, le=10_000_000)
    note: str = Field(default="", max_length=1000)
    # What the till called it, when the service is not in our catalogue. Preserved on the visit so
    # the owner can read it — and a name that keeps recurring is the signal to add it properly.
    custom_service: str = Field(default="", max_length=200)
    # ── the POS path (spec §16.6.4) ────────────────────────────────────────────────────────────
    # Invoice lines, as the till holds them. Present INSTEAD of service_ids for an integrated
    # establishment: the caller does not know our service ids and must not have to.
    #
    # Permissive like everything else on this model — a malformed line becomes a free-text line
    # rather than failing the item, because the till has already taken the customer's money.
    lines: list[dict] = Field(default_factory=list, max_length=50)
    # THEIR invoice number. The idempotency key is derived from it when present, because the till
    # is the only party that knows whether two calls are the same sale — our own generated key
    # would be new on every retry, which is exactly the doubling this prevents.
    invoice_id: str = Field(default="", max_length=128)
    # REQUIRED here, unlike the interactive route. A batch is by definition a replay, and a replay
    # without a stable key is how one lost reply becomes two visits, two reminders and doubled
    # revenue. The device cannot know whether we saved the first attempt — only we can.
    idempotency_key: str = Field(default="", max_length=128)
    # The device's clock, which may be days out. Kept ALONGSIDE our own receive time rather than
    # instead of it: reminders schedule from the visit time, so a device running two days fast
    # would otherwise produce a reminder that arrives before it should.
    occurred_at: int = Field(default=0, ge=0)


class BatchIn(BaseModel):
    # Small on purpose. The SDK drains oldest-first in modest batches with a randomised gap, so a
    # city's network returning does not put a thousand devices on us in the same second.
    visits: list[BatchVisitIn] = Field(min_length=1, max_length=50)


@router.post("/operations/visits/batch", dependencies=[Depends(require_internal_token)])
async def record_visits_batch(request: Request, body: BatchIn) -> dict:
    """Accept a drained batch from an integration, and report the outcome PER ITEM.

    THE FAILURE THIS EXISTS TO PREVENT — and it is the one everybody who writes an offline queue by
    hand walks into. An all-or-nothing batch containing a single permanently-invalid visit (a
    service id that was deleted, say) fails, is retried, fails again, forever. Everything behind it
    stops moving, and the shop believes its data is syncing while the queue has not advanced in a
    week. Nothing errors anywhere a human is looking.

    So each element gets its own verdict: `accepted`, `duplicate`, or `rejected` with a reason the
    SDK can act on. A rejected item is the client's to dead-letter locally after a bounded number
    of attempts; it must never block the queue behind it.

    THE TENANT IS ON EACH ITEM here, unlike the user-tier route where it comes off the token. This
    is the internal tier, called by a service that already authenticated the establishment, and one
    batch could in principle carry more than one — so it is per item rather than per request, and
    every item is scoped to its own.
    """
    c = request.app.state.container
    svc = c.operations
    results: list[dict] = []
    accepted = 0

    for item in body.visits:
        # ── invoice lines become services BEFORE the visit is recorded ────────────────────────
        # Resolved per item rather than per batch: two items may belong to different tenants, and
        # a catalogue write scoped to the wrong one is the worst bug this endpoint could have.
        extra_custom = ""
        if item.lines:
            try:
                res = await _invoices.resolve(
                    _invoices.parse_lines(item.lines), tenant=item.tenant,
                    service_store=ServiceStore(c.datastore), new_id=new_id,
                    now=int(time.time()))
                item.service_ids = list(dict.fromkeys(list(item.service_ids) + res.service_ids))
                # THE SHOP HAS JUST TOLD US IT IS INTEGRATED, by doing the one thing only an
                # integrated shop does. Nobody could answer this at signup — the till company
                # often connects weeks later, sometimes without the owner — so it is read from
                # evidence instead of asked. Runs once; every invoice after this is a single read.
                await Integration(store=c.datastore,
                                  sectors=c.sectors).note_invoice(item.tenant)
                # Free-text lines ride along as the custom label so the owner can read what was
                # actually sold. Joined rather than dropped: a recurring label is the signal to
                # offer it as a real service.
                extra_custom = "، ".join(res.free_text[:5])
            except (NameError, AttributeError, TypeError, ImportError):
                # A PROGRAMMING ERROR, NOT A PEER FAILURE — and it must not be swallowed.
                #
                # The first version caught bare Exception here so a catalogue problem could never
                # cost a recorded sale. It then swallowed `name 'time' is not defined` — a missing
                # import — and the item came back "rejected: select at least one service". The
                # catch protected the sale and lied about the cause, and the caller was told to fix
                # something that was not wrong. Found on the cluster; no test saw it, because a
                # test importing the module would have failed at import.
                raise
            except Exception as exc:                                        # noqa: BLE001
                # Anything else — a datastore hiccup, a peer timeout — and the visit still lands.
                # A catalogue failure must never cost a recorded sale.
                c.telemetry.event("invoice_resolve_failed", tenant=item.tenant,
                                  error=str(exc)[:200])
        if extra_custom and not item.custom_service:
            item.custom_service = extra_custom
        if item.invoice_id and not item.idempotency_key:
            # Namespaced, so a till whose invoice numbers restart at 1 each day cannot collide with
            # a key some other integration chose.
            item.idempotency_key = f"inv:{item.tenant}:{item.invoice_id}"

        # The tenant is per item and must be present. Checked here rather than by the model, so a
        # single item missing it is REJECTED while the rest of the batch still lands.
        if not item.tenant or not item.idempotency_key:
            results.append({"idempotency_key": item.idempotency_key, "status": "rejected",
                            "reason": "tenant and idempotency_key are required on a batch item"})
            continue
        # Audited per item, write-ahead, exactly as the interactive route is. A visit arriving
        # through an integration is not a lesser visit — the same reminders, points and revenue
        # derive from it.
        await request.app.state.auditor.record(
            "visit.recorded", actor="integration", tenant=item.tenant, resource="visit",
            ip=request.client.host if request.client else "")
        try:
            res = await svc.record_visit(
                tenant=item.tenant, phone=item.phone, service_ids=item.service_ids,
                name=item.name, plate=item.plate, operator_id=item.operator_id,
                branch_id=item.branch_id, meter=item.meter, note=item.note,
                custom_service=item.custom_service,
                idempotency_key=item.idempotency_key, occurred_at=item.occurred_at,
                # ONLY on this path. A till cannot know our catalogue, and refusing a service it
                # sent would lose the visit — which loses the customer from the product. On the
                # field screen the operator picks from the grid, so an unknown id there is a bug
                # and must fail loudly.
                allow_unknown_services=True)
        except OperationError as exc:
            # REJECTED, not retryable. The reason travels back so the SDK can dead-letter it with
            # something a support engineer can read, instead of retrying it into eternity.
            results.append({"idempotency_key": item.idempotency_key, "status": "rejected",
                            "reason": str(exc)})
            continue

        if res.duplicate:
            results.append({"idempotency_key": item.idempotency_key, "status": "duplicate",
                            "visit_id": res.visit.id})
            continue

        entry = {"idempotency_key": item.idempotency_key, "status": "accepted",
                 "visit_id": res.visit.id}
        if res.unknown_services:
            # Accepted AND flagged. The visit is safe; the integration still learns that it sent
            # something we do not have, which is how a vendor finds their mapping bug instead of
            # discovering months later that a third of their visits say "خدمة أخرى".
            entry["unknown_services"] = res.unknown_services
        results.append(entry)
        accepted += 1
        # The seams run per accepted visit, after it is durable — same rule as the interactive
        # path. Inline here rather than as a background task: a batch is not on anybody's screen,
        # so there is no five-second budget to protect, and doing it inline means the caller's
        # 200 genuinely reflects the work being done.
        await request.app.state.container.seams.after_visit(res)

    return {"accepted": accepted, "total": len(body.visits), "results": results}


class SeedTenantIn(BaseModel):
    tenant: str = Field(min_length=1, max_length=128)
    sector: str = Field(min_length=1, max_length=64)
    # The till will send this establishment's catalogue, so we seed only the catch-all. NOT a
    # sixth sector: an integrated tyre shop is still a tyre shop with the same services and the
    # same cycles, and duplicating every sector would double the table to express one flag.
    integrated: bool = False
    # Who brought it. Stamped here, at creation, so attribution exists before the first invoice —
    # and stamped ONCE, so a later key cannot rewrite it (core/partners.py).
    partner_key: str = Field(default="", max_length=128)


@router.post("/operations/seed-tenant", dependencies=[Depends(require_internal_token)])
async def seed_tenant(request: Request, body: SeedTenantIn) -> dict:
    """Give a new establishment its service catalogue.

    Called once, by the provisioning path, at the moment a tenant is created. Internal tier because
    it is service-to-service by nature — the establishment is not signed in yet, so there is no
    user token to carry, and minting a platform-capable one for this would put a very powerful
    credential in the signup flow.

    IDEMPOTENT: seeding twice adds nothing. A retried provisioning step must not produce a
    catalogue with every service listed twice, which is a mess the owner has to clean by hand on
    their first day.
    """
    sectors = request.app.state.container.sectors
    try:
        created = await sectors.seed_tenant(tenant=body.tenant, sector_key=body.sector,
                                            integrated=body.integrated)
    except SectorError as exc:
        # 400 and the list of valid sectors: a caller that sent a typo can fix it from the
        # response, without reading our source.
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    # ATTRIBUTION BEFORE THE FIRST INVOICE. Failing the whole provisioning because a partner key
    # was mistyped would be worse than an unattributed shop, so a bad key is reported in the
    # response rather than raised — the shop exists, and the stamp can be applied by hand.
    stamp_error = ""
    try:
        await PartnerRegistry(request.app.state.container.datastore,
                              salt=get_settings().PII_SALT).stamp(body.tenant,
                                                                  key=body.partner_key)
    except PartnerError as exc:
        stamp_error = str(exc)

    return {"tenant": body.tenant, "sector": body.sector, "services_created": created,
            "integrated": body.integrated, "stamp_error": stamp_error,
            "fields": await sectors.fields_for(body.sector),
            "tracks_vehicle": await sectors.tracks_vehicle(body.sector)}


class PartnerInviteIn(BaseModel):
    """What a till company tells us when a shop presses «تفعيل» inside its software."""

    phone: str = Field(min_length=6, max_length=32)
    shop_name: str = Field(min_length=1, max_length=200)
    # THE KEY IS THE ATTRIBUTION, and it arrives here rather than on the owner's claim for a
    # reason: a value the OWNER could send is a value anyone could send, and commission would
    # follow whoever typed the most convincing body.
    partner_key: str = Field(min_length=1, max_length=128)


@router.post("/signup/partner-invite", dependencies=[Depends(require_internal_token)])
async def partner_invite(request: Request, body: PartnerInviteIn) -> dict:
    """Invite a shop whose till company just enrolled it — and create NO ACCOUNT.

    THE ACCOUNT IS NOT CREATED HERE, and that is the whole design (core/claim.py). Somebody has to
    choose a password; if it is not the owner, it is the till company — and whoever holds it can
    connect his WhatsApp, subscribe him, and message his customers in his name.

    So this records an invitation and sends him a message. He proves his number, picks his own
    password, and the ordinary saga runs from there.
    """
    try:
        return await request.app.state.container.signup.invite_partner_shop(
            phone=body.phone, shop_name=body.shop_name, partner_key=body.partner_key)
    except Exception as exc:                                                # noqa: BLE001
        # INTERNAL TIER, SO IT MAY SAY WHAT IT MEANS. The caller is a service we contracted with,
        # not a stranger — and a partner integration that fails silently is a shop nobody follows
        # up on.
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)[:200])


class CustomerVisitsIn(BaseModel):
    tenant: str = Field(min_length=1, max_length=128)
    subject_ref: str = Field(min_length=8, max_length=128)
    # TEN by default and capped at 25. A customer's page is not a statement of account, and a
    # public page that can ask for a thousand rows is a public page that can be made expensive.
    limit: int = Field(default=10, ge=1, le=25)


@router.post("/operations/offers-spent", dependencies=[Depends(require_internal_token)])
async def offers_spent(request: Request, body: CustomerVisitsIn) -> dict:
    """Which offers this customer has already spent — asked by reminders, answered by us.

    THE DIRECTION IS THE WHOLE POINT (§5.6.2). `reminders` issues an offer and can say which one a
    visit would apply; only `operations` may say that one WAS applied, because the visit is the
    thing that happened and the send log is append-only. Reminders used to stamp its own log, and
    every cap in 5.8 is counted against that log.

    BY PSEUDONYM, and it answers with send-log row ids and nothing else. No visit, no service, no
    date — the caller needs a set to subtract, and anything more would be this service volunteering
    a history nobody asked for.
    """
    c = request.app.state.container
    crows, _ = await c.datastore.find(
        CUSTOMERS, {"tenant": body.tenant, "subject_ref": body.subject_ref}, limit=1)
    if not crows:
        # An unknown subject has spent nothing. Not a 404: same reason as customer-visits — a
        # distinct answer here is an oracle for whether a pseudonym exists.
        return {"refs": []}
    refs = await VisitStore(c.datastore).offers_spent(body.tenant, str(crows[0].get("id") or ""))
    return {"refs": refs}


@router.post("/operations/customer-visits", dependencies=[Depends(require_internal_token)])
async def customer_visits(request: Request, body: CustomerVisitsIn) -> dict:
    """One customer's own visit history, for their page.

    SHAPED FOR DISPLAY, NOT FOR EXPORT. It returns the service names and a formatted date and
    nothing else — no operator, no branch, no note, no amount. Everything omitted here is
    something the portal would otherwise be able to show to whoever holds a forwarded link, and a
    field is far easier not to send than to remember to hide.

    NO PHONE AND NO NAME even though this service holds both: the caller identifies the customer
    by pseudonym and gets back only what happened, never who it happened to.

    Returns an empty list for an unknown subject rather than 404 — the portal renders the same
    page either way, and a 404 here would travel through it as an oracle.
    """
    c = request.app.state.container
    rows, _ = await c.datastore.find(
        VISITS, {"tenant": body.tenant}, limit=200, sort=("created", "desc"))
    cust = None
    crows, _ = await c.datastore.find(
        CUSTOMERS, {"tenant": body.tenant, "subject_ref": body.subject_ref}, limit=1)
    cust = crows[0] if crows else None
    if cust is None:
        return {"visits": [], "count": 0}

    names = {s.id: s.name for s in await ServiceStore(c.datastore).list(body.tenant,
                                                                       active_only=False)}
    out = []
    for r in rows:
        if r.get("customer_id") != cust.get("id"):
            continue
        labels = [names.get(sid, "") for sid in (r.get("service_ids") or [])]
        labels = [x for x in labels if x] or [r.get("custom_service") or "زيارة"]
        out.append({"services": "، ".join(labels[:3]),
                    "date": _arabic_date(int(r.get("occurred_at") or r.get("created") or 0))})
        if len(out) >= body.limit:
            break
    return {"visits": out, "count": len(out)}


_AR_MONTHS = ("يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
              "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر")


def _arabic_date(epoch: int) -> str:
    """A date a person reads, formatted HERE rather than in the portal.

    Formatted on this side because this is where the timezone belongs: the visit happened in
    Riyadh, and a page rendering a UTC epoch would show a late-evening visit on the wrong day.
    Western digits throughout — Arabic-Indic numerals are not what a Saudi phone keyboard types.
    """
    if not epoch:
        return ""
    from datetime import datetime, timedelta, timezone
    d = datetime.fromtimestamp(epoch, timezone(timedelta(hours=3)))
    return f"{d.day} {_AR_MONTHS[d.month - 1]}"


class StampIn(BaseModel):
    tenant: str = Field(min_length=1, max_length=128)
    # Empty = a direct signup, which is a DECISION and not an absence. See core/partners.py.
    partner_key: str = Field(default="", max_length=128)


@router.post("/operations/partner-stamp", dependencies=[Depends(require_internal_token)])
async def partner_stamp(request: Request, body: StampIn) -> dict:
    """Attribute an establishment to whoever brought it. FIRST WINS, ALWAYS.

    Called by the provisioning path at tenant creation, and again by the first integration call
    that carries a partner key. Both are safe: the second one cannot change the answer.

    Internal-tier because the key is a bearer credential that directs money — a route that accepts
    it must not be reachable with a user token, and must never appear in a URL where a proxy would
    log it. Hence POST with a body rather than a query parameter.
    """
    c = request.app.state.container
    s = get_settings()
    await request.app.state.auditor.record(
        "partner.stamped", actor="", tenant=body.tenant, resource="partner_stamp",
        ip=request.client.host if request.client else "")
    reg = PartnerRegistry(c.datastore, salt=s.PII_SALT)
    try:
        row = await reg.stamp(body.tenant, key=body.partner_key)
    except PartnerError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    # The key never comes back, not even a prefix of it. A response that echoes a credential is a
    # credential in whatever logged the response.
    return {"tenant": row["tenant"], "partner_id": row["partner_id"],
            "partner_name": row["partner_name"], "stamped_at": row["stamped_at"]}


@router.get("/operations/partner-stamp/{tenant}", dependencies=[Depends(require_internal_token)])
async def read_stamp(request: Request, tenant: str) -> dict:
    """Who brought this establishment — the input to a commission statement."""
    c = request.app.state.container
    s = get_settings()
    row = await PartnerRegistry(c.datastore, salt=s.PII_SALT).stamp_of(tenant)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND")
    return row


@router.get("/operations/templates", dependencies=[Depends(require_internal_token)])
async def internal_templates(request: Request) -> dict:
    """The platform template library, for a peer that needs to know what it may send.

    THE SAME LIBRARY THE CONSOLE EDITS, read-only and internal. `campaigns` needs to know which
    template a goal maps to and whether it is active — and a peer that had to hold its own copy
    would be a second place the wording lives, which is always the stale one.

    Returns the whole library rather than one type: it is 66 rows, it is cached on the other side,
    and one call per campaign creation beats one call per goal card.
    """
    lib = await request.app.state.container.templates.list()
    return {"templates": lib, "count": len(lib)}


class CustomersIn(BaseModel):
    tenant: str = Field(min_length=1, max_length=128)
    # Bounded, and the ceiling is a product decision: an establishment with more customers than
    # this in one campaign is a case we want to look at before it goes out.
    limit: int = Field(default=5000, ge=1, le=5000)


@router.post("/operations/customers", dependencies=[Depends(require_internal_token)])
async def internal_customers(request: Request, body: CustomersIn) -> dict:
    """Every customer of one establishment, as PSEUDONYMS — for building a campaign audience.

    NO PHONE AND NO NAME. The caller decides who receives a message; it never needs to know who
    they are, and a field not sent is a field that cannot leak from a service that had no business
    holding it.

    What it does carry is what an audience rule reasons about: when they last visited, and how many
    times. `campaigns` joins the learned interval from reminders — this service does not hold it.
    """
    c = request.app.state.container
    rows, _ = await c.datastore.find(CUSTOMERS, {"tenant": body.tenant},
                                     limit=body.limit, sort=("last_visit", "desc"))
    return {"customers": [{"subject_ref": r.get("subject_ref", ""),
                           "last_visit": int(r.get("last_visit") or 0),
                           "visit_count": int(r.get("visit_count") or 0)}
                          for r in rows if r.get("subject_ref")],
            "count": len(rows)}


class VisitsSinceIn(BaseModel):
    # EMPTY MEANS EVERY TENANT, and that is not a convenience — it is what makes the catch-up able
    # to BOOTSTRAP. A consumer that can only ask about tenants it already knows can never learn
    # about the one whose very first event it missed, which is precisely the case the catch-up
    # exists to repair. Found by running the tick on a live cluster and getting "tenants: 0".
    tenant: str = Field(default="", max_length=128)
    # Exclusive watermark. The caller stores the highest `created` it has processed and asks for
    # what came after — a cursor it owns, not a subscription we owe it.
    since: int = Field(ge=0)
    limit: int = Field(default=200, ge=1, le=1000)


@router.post("/operations/visits/since", dependencies=[Depends(require_internal_token)])
async def visits_since(request: Request, body: VisitsSinceIn) -> dict:
    """Visits recorded after a watermark — the READ that makes the visit event self-healing.

    THIS EXISTS BECAUSE THE EVENT BUS IS AT-MOST-ONCE, and its port says so in capitals: a
    subscriber that is restarting, disconnected, or not yet deployed does not receive the event,
    and nothing anywhere records that it missed one. For `reminders` that is not a delay, it is a
    customer who never gets a reminder — for ever, because nothing will ever mention that visit
    again.

    The rule the port imposes on every consumer is that an event may be a HINT that makes
    reconciliation faster, and never the only way a fact can be learned. So this is the other way:
    a bounded, ordered read that a consumer can catch up from after any outage, restart, or
    deployment gap.

    ORDERED BY `created`, NOT `occurred_at`. The watermark must advance monotonically, and
    `occurred_at` is the DEVICE clock — an offline till draining a week of records emits visits
    whose occurred_at is in the past, and a cursor on it would skip everything drained after the
    reader had moved on. `created` is ours and only ever increases.
    """
    c = request.app.state.container
    if body.tenant:
        rows, _ = await c.datastore.find(VISITS, {"tenant": body.tenant},
                                         limit=body.limit, sort=("created", "asc"))
    else:
        # sweeper: reading EVERY tenant's visits IS the operation here, not a forgotten filter.
        # This is the bootstrap path — a consumer that can only ask about tenants it already knows
        # can never learn about the one whose first event it missed, and the event bus is
        # at-most-once. `find` correctly refuses an empty `where`; this says out loud that the
        # absence of a filter is the point.
        #
        # It is internal-token only, bounded by `limit`, and driven by a five-minute cron, so the
        # cost is a bounded read every five minutes rather than anything on a request path.
        rows = await c.datastore.scan_all(VISITS, limit=body.limit)
    fresh = [r for r in rows if int(r.get("created") or 0) > body.since]
    # scan_all does not sort. The watermark depends on `created` ascending, and a page returned in
    # storage order would advance the cursor past visits it never returned.
    fresh.sort(key=lambda r: int(r.get("created") or 0))
    # The same payload shape as the event, so a consumer has ONE code path for both. Two shapes
    # would mean the recovery path is the one nobody exercises and therefore the one that is
    # broken when it is finally needed.
    out = []
    for r in fresh:
        tenant = r.get("tenant") or body.tenant
        cust = await c.datastore.get(CUSTOMERS, f"{tenant}|{r.get('customer_id','')}")
        out.append({
            "tenant": tenant,
            "visit_id": r.get("id", ""),
            "customer_id": r.get("customer_id", ""),
            "subject_ref": (cust or {}).get("subject_ref", ""),
            "service_ids": list(r.get("service_ids") or []),
            "asset_id": r.get("asset_id", ""),
            "operator_id": r.get("operator_id", ""),
            "branch_id": r.get("branch_id", ""),
            "visit_count": (cust or {}).get("visit_count", 0),
            "occurred_at": r.get("occurred_at") or r.get("created"),
            "created": r.get("created"),
        })
    return {"visits": out, "count": len(out),
            # The next watermark, computed here rather than by the caller: deriving it from the
            # last row is a one-line mistake that either replays everything or skips a visit.
            "watermark": max([int(v["created"]) for v in out] + [body.since]),
            "more": len(fresh) == body.limit}


class RecipientIn(BaseModel):
    tenant: str = Field(min_length=1, max_length=128)
    # The pseudonym we published on the visit event. Peers hold this and nothing else.
    subject_ref: str = Field(min_length=8, max_length=128)


@router.post("/operations/recipient", dependencies=[Depends(require_internal_token)])
async def resolve_recipient(request: Request, body: RecipientIn) -> dict:
    """Turn a subject_ref back into a destination, for a peer that is about to send.

    THIS ROUTE EXISTS BECAUSE THE ALTERNATIVE WAS WORSE. `reminders` decides whether and when to
    message a customer, and it deliberately holds no phone number — what it holds is a prediction
    of when each person next needs a service, across every shop they use, and attached to a phone
    number that is a marketing list. But notification-service takes a real recipient. Something has
    to bridge the two.

    Three ways to bridge it, and this is the least bad:

      Store the number in reminders     — undoes the whole reason it holds a pseudonym.
      Have notification-service resolve — it would need our salt and our customer table, which is
                                          a bigger blast radius than this route.
      Resolve here, at send time        — the number never rests anywhere new. It exists in this
                                          response, in the peer's memory for the length of one
                                          call, and nowhere else.

    So: internal-token only, one subject at a time, no listing, and NOTHING LOGGED. A route that
    turns a pseudonym into a phone number is the single most sensitive surface this service has,
    and a bulk version of it would be a customer list export wearing a different name.

    Returns an EMPTY recipient rather than 404 for an unknown or erased subject. A 404 here is an
    oracle: it answers "does this establishment have a customer with this pseudonym?" to anyone
    holding the internal token, and the caller's behaviour is identical either way — it cannot
    send, and it must not retry.
    """
    c = request.app.state.container
    rows, _ = await c.datastore.find(
        CUSTOMERS, {"tenant": body.tenant, "subject_ref": body.subject_ref}, limit=1)
    row = rows[0] if rows else None
    phone = (row or {}).get("phone") or ""
    return {
        "tenant": body.tenant,
        "subject_ref": body.subject_ref,
        # Empty after an erasure: the row survives with its phone blanked (see core/erasure.py),
        # which is exactly right — the peer learns "cannot send" without learning "never existed".
        "recipient": phone,
        "name": (row or {}).get("name") or "",
        "found": bool(phone),
    }


class FreeVisitIn(BaseModel):
    tenant: str = Field(min_length=1, max_length=128)
    # THE PSEUDONYM, because the caller is `loyalty`, which holds no phone number and must not.
    # Every other write path here takes a phone; this one exists precisely so that one does not
    # have to be handed to a service that was built to not have it.
    subject_ref: str = Field(min_length=8, max_length=128)
    service_id: str = Field(min_length=1, max_length=64)
    actor: str = Field(default="", max_length=128)
    # The redemption's id. Also the idempotency key, because the redemption is the only thing that
    # knows whether two calls are the same free wash.
    source: str = Field(min_length=1, max_length=128)


@router.post("/operations/visits/by-ref", dependencies=[Depends(require_internal_token)])
async def record_visit_by_ref(request: Request, body: FreeVisitIn) -> dict:
    """Record a visit for a customer identified by pseudonym — the free service a reward bought.

    WHY THIS ROUTE EXISTS. A reward of type `service` (spec §9.4) is a real wash performed for no
    money. If it is not recorded as a visit, two things go wrong and neither shows up as an error:
    the reminder cycle is never restarted, so the customer is reminded to come in for the service
    he just received; and the shop's own history says he did not come.

    AND WHY NOT `visits/batch`. That route identifies the customer by phone. `loyalty` deliberately
    holds only the pseudonym, and handing it a phone number to make one call would undo the reason
    it was built that way. The mapping lives here, where the number already is.

    Returns `recorded: false` for an unknown or erased subject rather than 404 — the caller has
    already handed the customer his reward and must not treat this as a failure, and a 404 here
    would answer "does this establishment have this customer?" to anyone holding the token.
    """
    c = request.app.state.container
    rows, _ = await c.datastore.find(
        CUSTOMERS, {"tenant": body.tenant, "subject_ref": body.subject_ref}, limit=1)
    phone = (rows[0] if rows else {}).get("phone") or ""
    if not phone:
        return {"recorded": False, "reason": "unknown or erased subject"}

    await request.app.state.auditor.record(
        "visit.recorded", actor=body.actor or "loyalty", tenant=body.tenant, resource="visit",
        ip=request.client.host if request.client else "")
    try:
        res = await c.operations.record_visit(
            tenant=body.tenant, phone=phone, service_ids=[body.service_id],
            operator_id=body.actor,
            # Namespaced on the redemption, so a retry of the same redemption records one visit.
            idempotency_key=f"loyalty:{body.source}",
            note="مكافأة ولاء")
    except OperationError as exc:
        return {"recorded": False, "reason": str(exc)}
    return {"recorded": True, "visit_id": res.visit.id, "duplicate": res.duplicate}


class CatalogueIn(BaseModel):
    tenant: str = Field(min_length=1, max_length=128)


@router.post("/operations/catalogue", dependencies=[Depends(require_internal_token)])
async def read_catalogue(request: Request, body: CatalogueIn) -> dict:
    """One establishment's services — id, name, and cycle.

    FOR `insights`, which needs three things this service already holds: the NAME, so a bundle
    card says "غيار زيت" rather than `svc_9f2a` and is therefore pressable; the CYCLE, because
    cycle completion is computed from it and asking the owner for it a second time would be asking
    for something he already gave us; and the FULL LIST INCLUDING RETIRED SERVICES, because an
    indicator over the last ninety days covers visits to services that have since been switched
    off, and dropping them would silently shrink every denominator.

    No prices. `insights` does not price anything (spec §10.6.2.1) and a field sent for no reason
    is a field that ends up used for one.
    """
    c = request.app.state.container
    rows = await ServiceStore(c.datastore).list(body.tenant, active_only=False)
    return {"services": [{"id": s.id, "name": s.name, "cycle_days": s.cycle_days,
                          "active": s.active} for s in rows],
            "count": len(rows)}


@router.get("/operations/sectors", dependencies=[Depends(require_internal_token)])
async def list_sectors(request: Request) -> dict:
    """The sectors this deployment knows, with the fields each one renders.

    The signup screen reads this instead of carrying its own copy — a second list is a second thing
    to keep in step, and it will not be kept in step.
    """
    sectors = request.app.state.container.sectors
    out = []
    for row in await sectors.list():
        # ACTIVE ONLY on this route. It feeds the signup screen, and offering a sector we have
        # retired would let an establishment choose something that will not seed a catalogue.
        if not row.get("active", True):
            continue
        key = row.get("key", "")
        out.append({"key": key, "name": row.get("name", key),
                    "fields": await sectors.fields_for(key),
                    "tracks_vehicle": row.get("asset") == "vehicle"})
    return {"sectors": out}


class BackupExportIn(BaseModel):
    # Empty tenant = the whole service; a value = just that customer's tenant-scoped rows.
    tenant: str = ""


class BackupImportIn(BaseModel):
    archive: dict
    # Off by default: a restore must not bulldoze rows written after the backup unless the operator
    # driving the restore says so.
    overwrite: bool = False
    # Empty = restore in place. A value REMAPS the restore into that tenant (restore-as-clone):
    # only rows that carry a tenant are reassigned; a global dataset is left alone.
    into_tenant: str = ""


def _sealer(settings: Settings):
    """The backup (seal, unseal) pair, or a 503 when no backup key is configured.

    Refused rather than defaulted: sealing with an empty key would write a plaintext-equivalent
    archive while every check reported it encrypted — the one outcome a backup must never have.
    """
    if not settings.BACKUP_KEK:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "BACKUP_KEK not configured — set this SHARED key (the SAME value backup-service holds) on this service, or its archives cannot be opened")
    return _backup.make_sealer(settings.BACKUP_KEK)


@router.post("/backup/export", dependencies=[Depends(require_internal_token)])
async def backup_export(request: Request, body: BackupExportIn,
                        settings: Settings = Depends(get_settings)) -> dict:
    """Produce a sealed, checksummed archive of this service's declared data.

    Called by backup-service, on a schedule, over the internal token. What this service holds is
    declared in app/backup_manifest.py; how it is read lives in core/backup.py. The orchestrator
    stores the archive and never sees the plaintext.
    """
    seal, _ = _sealer(settings)
    return await _backup.export(
        request.app.state.container.datastore, BACKUP,
        service=settings.SERVICE_NAME, version=settings.SERVICE_VERSION,
        taken_at=_now_iso(), seal=seal, tenant=body.tenant,
        scan_cap=settings.BACKUP_MAX_ROWS_PER_COLLECTION)


class BackupVerifyIn(BaseModel):
    archive: dict


@router.post("/backup/verify", dependencies=[Depends(require_internal_token)])
async def backup_verify(request: Request, body: BackupVerifyIn,
                        settings: Settings = Depends(get_settings)) -> dict:
    """Prove an archive restores, by test-restoring it into a throwaway namespace and comparing.

    backup-service calls this after it stores an archive (passing back the bytes it read FROM the
    store, so corruption at rest is caught too). This service is the only party that can unseal its
    own archive and knows its own schema, so verification lives here; the orchestrator only records
    the verdict. The throwaway namespace is torn down before this returns — nothing is left behind,
    and live data is never touched.
    """
    import secrets
    _, unseal = _sealer(settings)
    try:
        return await _backup.verify_restore(
            request.app.state.container.datastore, body.archive,
            unseal=unseal, token=secrets.token_hex(8))
    except _backup.BackupError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.post("/backup/import", dependencies=[Depends(require_internal_token)])
async def backup_import(request: Request, body: BackupImportIn,
                        settings: Settings = Depends(get_settings)) -> dict:
    """Restore an archive this service produced. Idempotent; leaves newer rows alone by default."""
    _, unseal = _sealer(settings)
    try:
        return await _backup.import_archive(
            request.app.state.container.datastore, body.archive,
            unseal=unseal, overwrite=body.overwrite, into_tenant=body.into_tenant)
    except _backup.BackupError as exc:
        # A bad archive is the caller's problem, not a 500: the checksum failed, the key did not
        # match, or a row had no identity. Say which, so an operator can act.
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.post("/operations/retention/sweep", dependencies=[Depends(require_internal_token)])
async def retention_sweep(request: Request) -> dict:
    """The nightly retention pass (§14.5). Driven by a CronJob, never by a person.

    NO BODY AND NO TENANT ARGUMENT, deliberately. A sweep that took a tenant would be a deletion
    endpoint with a filter on it, and the internal token is held by every service in the mesh.
    This one only ever does what the clock already decided.

    It decides WHO is past the line; core/erasure.py decides what erasing means — the same code a
    DSAR runs, so there is exactly one definition of "erased" in this service.
    """
    from app.core.runtime_config import RuntimeConfig
    from app.runtime_policy import RUNTIME_POLICY

    c = request.app.state.container
    s = get_settings()
    default = retention_core.Policy(customer_years=s.RETENTION_CUSTOMER_YEARS,
                                    lapsed_years=s.RETENTION_LAPSED_YEARS)
    # NAMED KEY OR NO CLOCK. Without the entitlement key we cannot tell "left" from "here", and
    # guessing would start a two-year countdown on establishments that never went anywhere.
    subs: object = retention_core.NullSubscriptions()
    if s.RETENTION_ENTITLEMENT_KEY and s.BILLING_SERVICE_URL:
        subs = retention_core.HttpSubscriptions(
            billing_url=s.BILLING_SERVICE_URL, check_path=s.BILLING_CHECK_PATH,
            key=s.RETENTION_ENTITLEMENT_KEY, token=s.INTERNAL_SERVICE_TOKEN,
            timeout=s.PEER_TIMEOUT_SECONDS)
    eraser = OperationsErasure(store=c.datastore, pii_salt=s.PII_SALT,
                               max_scan=s.ERASURE_MAX_SCAN)
    sweeper = retention_core.Sweeper(
        store=c.datastore, eraser=eraser,
        runtime_config=RuntimeConfig(c.datastore, Settings, policy=RUNTIME_POLICY),
        subscriptions=subs, default=default, scan_cap=s.RETENTION_SCAN_CAP)
    out = await sweeper.sweep()

    # RECORDED AFTER, AND ONLY IF IT DID SOMETHING — the opposite of the DSAR route above, on
    # purpose. There the write-ahead exists because a half-finished erasure would otherwise leave
    # no trace; here the counts ARE the record, and a nightly write-ahead on 364 quiet nights
    # would bury the one night that mattered.
    if out.customers or out.establishments_erased:
        await request.app.state.auditor.record(
            "retention.swept", actor="", tenant="", resource="subject",
            ip=request.client.host if request.client else "")
    return out.to_dict()
