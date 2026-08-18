# =============================================================================
# operations — Internal tier (service-to-service, X-Internal-Token)
# -----------------------------------------------------------------------------
# NOT user-facing. Guarded by a shared token compared in CONSTANT TIME
# (CWE-208: observable timing discrepancy). Never a user JWT.
# =============================================================================
from __future__ import annotations

import hmac
import time
from typing import Any

from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from app.config import Settings, get_settings
from app.core import evidence as EV
from app.core import privacy_requests as PR
from app.core.erasure import OperationsErasure
from app.core import retention as retention_core
from app.core.models import CUSTOMERS, VISITS
from app.core import invoices as _invoices
from app.core.integration import Integration
from app.core.partners import PartnerError, PartnerRegistry
from app.core.stores import (AssetStore, BranchStore, CustomerStore, PrivacyRequestStore,
                             ServiceStore, VisitStore, new_id)
from app.core.operations import OperationError, RecordedVisit
from app.core import backup as _backup
from app.backup_manifest import BACKUP
from app.manifest import build_manifest
from app.core.riyadh import RIYADH

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

    # ENUMERATED, BECAUSE THE CALLER PAIRS BY POSITION (ك-7). Every result below carries the
    # item's index in the batch AS THE CALLER SENT IT. Without it a till has only
    # `idempotency_key` to match on — and that key is frequently one WE derived (`inv:{tenant}:
    # {invoice}` a few lines above, or `_key_for` in the till route), so it is not a string the
    # caller ever held. Unable to pair an answer with a sale, an SDK does the only safe thing
    # left: it re-posts the whole batch, or drops it whole.
    for index, item in enumerate(body.visits):
        # ── invoice lines become services BEFORE the visit is recorded ────────────────────────
        # Resolved per item rather than per batch: two items may belong to different tenants, and
        # a catalogue write scoped to the wrong one is the worst bug this endpoint could have.
        extra_custom = ""
        item_quantities: dict[str, int] = {}
        # 0 IS «NOT KNOWN», and for a field visit that is the truth — the screen records no money.
        item_total_minor = 0
        if item.lines:
            try:
                res = await _invoices.resolve(
                    _invoices.parse_lines(item.lines), tenant=item.tenant,
                    service_store=ServiceStore(c.datastore), new_id=new_id,
                    now=int(time.time()))
                item.service_ids = list(dict.fromkeys(list(item.service_ids) + res.service_ids))
                # THE COUNT TRAVELS WITH THE IDS, or the group-basket test reads an empty map for
                # ever — which is what it did: `parse_lines` looked for `quantity` while our own
                # till model calls the field `qty`, so every line arrived as one.
                item_quantities = dict(res.quantities)
                # AND THE MONEY, on the same journey as the count (أ-1). The till sends
                # `amount_minor` per line and `parse_lines` read it — into a field nothing carried
                # any further. So the visit reached loyalty with no amount, its earn rule computed
                # `(0 // 100) * points_per_riyal`, and a 480-riyal invoice was worth zero points
                # while the recorded reason said «no points configured».
                item_total_minor = res.total_minor
                # THE SHOP HAS JUST TOLD US IT IS INTEGRATED, by doing the one thing only an
                # integrated shop does. Nobody could answer this at signup — the till company
                # often connects weeks later, sometimes without the owner — so it is read from
                # evidence instead of asked. Runs once; every invoice after this is a single read.
                await Integration(store=c.datastore).note_invoice(item.tenant)
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
            results.append({"index": index, "idempotency_key": item.idempotency_key, "status": "rejected",
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
                quantities=item_quantities, total_minor=item_total_minor,
                idempotency_key=item.idempotency_key, occurred_at=item.occurred_at,
                # ONLY on this path. A till cannot know our catalogue, and refusing a service it
                # sent would lose the visit — which loses the customer from the product. On the
                # field screen the operator picks from the grid, so an unknown id there is a bug
                # and must fail loudly.
                allow_unknown_services=True)
        except OperationError as exc:
            # REJECTED, not retryable. The reason travels back so the SDK can dead-letter it with
            # something a support engineer can read, instead of retrying it into eternity.
            results.append({"index": index, "idempotency_key": item.idempotency_key, "status": "rejected",
                            "reason": str(exc)})
            continue

        if res.duplicate:
            results.append({"index": index, "idempotency_key": item.idempotency_key, "status": "duplicate",
                            "visit_id": res.visit.id})
            continue

        entry = {"index": index, "idempotency_key": item.idempotency_key, "status": "accepted",
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
    # Kept because the caller still sends it and the answer still differs: an integrated shop's
    # services arrive from its till's invoices, a manual shop's from its owner typing them.
    integrated: bool = False
    # Who brought it. Stamped here, at creation, so attribution exists before the first invoice —
    # and stamped ONCE, so a later key cannot rewrite it (core/partners.py).
    partner_key: str = Field(default="", max_length=128)


@router.post("/operations/seed-tenant", dependencies=[Depends(require_internal_token)])
async def seed_tenant(request: Request, body: SeedTenantIn) -> dict:
    """Stamp who brought a new establishment. It gets NO catalogue.

    THE NAME IS HISTORY AND THE ROUTE IS NOT. It used to copy a whole service list into a new
    tenant from the trade its owner picked; nothing is seeded now, because a catalogue guessed from
    a trade we have never seen is wrong on its first day for any shop that does two things. The
    shop writes its own in «خدماتي», and this route is left holding the one thing it still does:
    recording the partner who brought it, before the first invoice can arrive.

    Called once, by the provisioning path, at the moment a tenant is created. Internal tier because
    it is service-to-service by nature — the establishment is not signed in yet, so there is no
    user token to carry, and minting a platform-capable one for this would put a very powerful
    credential in the signup flow.
    """
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

    return {"tenant": body.tenant, "services_created": 0,
            "integrated": body.integrated, "stamp_error": stamp_error}


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


class ReindexIn(BaseModel):
    tenant: str = Field(min_length=1, max_length=128)
    limit: int = Field(default=2000, ge=1, le=20000)


@router.post("/operations/reindex-customers", dependencies=[Depends(require_internal_token)])
async def reindex_customers(request: Request, body: ReindexIn) -> dict:
    """Rewrite the search documents for a tenant's existing customers.

    WHY IT HAD TO EXIST. The index is written on every VISIT (seams.py), which keeps it fresh and
    costs nothing — but it also means a field added to the document reaches a customer only when he
    next comes in. We added the plate, and every car already in the yard stayed unfindable by it:
    the shop that most needs the search — a tyre shop with three years of customers — would have
    been the last to get it, one returning car at a time.

    IDEMPOTENT AND BOUNDED. It writes the same document the visit path writes, so running it twice
    changes nothing, and `limit` keeps a large tenant from turning one call into an unbounded scan.
    """
    c = request.app.state.container
    if c.search is None:
        return {"ok": False, "reason": "no search backend configured", "indexed": 0}

    rows, _ = await c.datastore.find(CUSTOMERS, {"tenant": body.tenant}, limit=body.limit)
    store = VisitStore(c.datastore)
    assets = AssetStore(c.datastore)
    done = 0
    for r in rows or []:
        cid = str(r.get("id") or "")
        if not cid:
            continue
        plates = [a.plate for a in await assets.for_customer(body.tenant, cid) if a.plate]
        try:
            phone = str(r.get("phone") or "")
            await c.seams.index_customer_row(
                tenant=body.tenant, customer_id=cid, phone=phone,
                name=str(r.get("name") or ""), plates=plates,
                # THE BACKFILL CARRIES IT TOO, and that is the whole point of the backfill: a
                # branch field written only by new visits would leave every customer from before
                # today invisible to a scoped reader — which is the same leak inverted.
                branch_id=str(r.get("last_branch_id") or ""))
            done += 1
        except Exception:                                                   # noqa: BLE001
            # ONE BAD DOCUMENT MUST NOT COST THE OTHER TWO THOUSAND. The count reported is what
            # actually landed, so a partial run is visible rather than reported as complete.
            continue
    _ = store
    return {"ok": True, "indexed": done, "customers": len(rows or [])}


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


class RedeemedIn(BaseModel):
    tenant: str = Field(min_length=1, max_length=128)
    # ONE ROW PER RECIPIENT campaigns REACHED, each carrying its OWN `since` — the moment THIS
    # campaign sent to them, not a shared cutoff. Bounded the same way `resolve_customers` is:
    # a report card, not a hot path, and a shop's whole customer table is thousands at most.
    reached: list[dict] = Field(default_factory=list, max_length=2000)


@router.post("/operations/offers-redeemed", dependencies=[Depends(require_internal_token)])
async def offers_redeemed(request: Request, body: RedeemedIn) -> dict:
    """How many of a campaign's recipients came back and spent an offer (ط-3).

    THE QUESTION THAT HAD NOWHERE TO BE ASKED. `offer_ref` has been written on every visit that
    spent one since §5.6.2 shipped, and `campaigns` has recorded exactly who it reached and when
    in `campaign_reached` since the day dedup needed it — «كم واحداً رجع وصرف؟» sat unanswered with
    every piece of its answer already on disk in two services that never spoke to each other.

    ONLY REDEMPTIONS AT OR AFTER `since` COUNT. A customer holding an unrelated, earlier offer from
    a DIFFERENT campaign must not inflate this one's number — the spend has to have happened after
    THIS campaign reached him, which is why `since` travels per recipient rather than once for the
    whole call.
    """
    c = request.app.state.container
    tenant = body.tenant
    # A RECIPIENT WITH NO CUTOFF IS NOT COUNTED (review of ط-3). `int(row.get("since") or 0)`
    # made a missing cutoff mean ZERO, and zero means «any redemption ever counts» — so one
    # malformed row would credit this campaign with a discount the customer spent last year,
    # which is the exact inflation the per-recipient cutoff exists to prevent. Unknown is not
    # zero; it is unknown, and an unknown recipient is left out of the answer.
    since_by_ref: dict[str, int] = {}
    for row in body.reached:
        ref = str(row.get("subject_ref") or "")
        since = int(row.get("since") or 0)
        if ref and since > 0:
            since_by_ref[ref] = since
    if not since_by_ref:
        return {"redeemed": 0}

    customers = await CustomerStore(c.datastore).by_refs(tenant, set(since_by_ref))
    visits = VisitStore(c.datastore)
    redeemed = 0
    for customer in customers:
        since = since_by_ref.get(customer.subject_ref, 0)
        # THE SAME BOUND `offers_spent` USES, AND FOR THE SAME REASON — not the default 20.
        # A busy customer can pass twenty visits inside one campaign's window, and the twenty
        # newest would then hide the visit where the discount was actually spent: the report
        # would under-count silently, which is worse than a report that is late.
        rows = await visits.for_customer(tenant, customer.id, limit=200)
        if any(v.offer_ref and v.offer_used_at >= since for v in rows):
            redeemed += 1
    return {"redeemed": redeemed}


@router.post("/operations/customer-visits", dependencies=[Depends(require_internal_token)])
async def customer_visits(request: Request, body: CustomerVisitsIn) -> dict:
    """One customer's own visit history, for their page.

    SHAPED FOR DISPLAY, NOT FOR EXPORT. It returns the service names, a formatted date and the
    BRANCH NAME — and nothing else. No operator, no note, no amount: everything omitted here is
    something the portal would otherwise show to whoever holds a forwarded link, and a field is
    far easier not to send than to remember to hide.

    THE BRANCH IS IN, AND THAT IS A DECIDED TRADE RATHER THAN A RELAXATION. A chain's customer
    reading «زيارتك — تغيير زيت» cannot tell which of four places he was at, which makes his own
    history useless to him and makes a booking (the next thing this page will carry) impossible to
    place. It is his own visit, at a shop he chose, and it is strictly less than the service names
    already on the row.

    THE NAME, NEVER THE ID. `brn-7f21` is not information, and an id on a public page is an
    invitation to guess the next one.

    NO PHONE AND NO NAME even though this service holds both: the caller identifies the customer
    by pseudonym and gets back only what happened, never who it happened to.

    Returns an empty list for an unknown subject rather than 404 — the portal renders the same
    page either way, and a 404 here would travel through it as an oracle.
    """
    c = request.app.state.container
    crows, _ = await c.datastore.find(
        CUSTOMERS, {"tenant": body.tenant, "subject_ref": body.subject_ref}, limit=1)
    cust = crows[0] if crows else None
    if cust is None:
        return {"visits": [], "count": 0}

    # HIS OWN VISITS, ASKED FOR BY NAME — not the shop's last 200 filtered down to him.
    #
    # THE BUG THAT WAS: this read the tenant's most recent 200 visits and then dropped every row
    # whose customer was somebody else. A quiet shop was fine. A shop recording 200 visits in two
    # days served its month-old customer an EMPTY history — on the page we send him a link to,
    # from a message in the shop's name. Nothing failed: the list was simply the wrong list, and
    # the busier the establishment the more certainly it was empty.
    rows = [v.__dict__ for v in await VisitStore(c.datastore).for_customer(
        body.tenant, str(cust.get("id") or ""), limit=max(body.limit, 1))]
    rows.sort(key=lambda r: int(r.get("occurred_at") or r.get("created") or 0), reverse=True)

    names = {s.id: s.name for s in await ServiceStore(c.datastore).list(body.tenant,
                                                                       active_only=False)}
    # CLOSED BRANCHES INCLUDED. A visit that happened at a place the shop has since shut is still
    # a visit that happened there, and «» in its place would read as a missing record.
    branch_names = {b.id: b.name for b in await BranchStore(c.datastore).list(body.tenant)}
    out = []
    for r in rows:
        labels = [names.get(sid, "") for sid in (r.get("service_ids") or [])]
        labels = [x for x in labels if x] or [r.get("custom_service") or "زيارة"]
        out.append({"services": "، ".join(labels[:3]),
                    # EMPTY WHEN UNKNOWN, and the page then says nothing rather than «غير محدَّد».
                    # Most shops have one branch and record no branch at all; a label on every row
                    # of a single-branch shop is noise that teaches him to stop reading the row.
                    "branch": branch_names.get(r.get("branch_id") or "", ""),
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
    d = datetime.fromtimestamp(int(epoch), RIYADH)
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


class ServiceDurationsIn(BaseModel):
    tenant: str = Field(min_length=1, max_length=128)
    service_ids: list[str] = Field(min_length=1, max_length=20)


@router.post("/operations/service-durations", dependencies=[Depends(require_internal_token)])
async def internal_service_durations(request: Request, body: ServiceDurationsIn) -> dict:
    """The sum of `Service.duration_minutes` for a set of services, or `null` if ANY of them is
    not configured — for `bookings`, the one question it asks this service (its own
    `app/core/operations.py::DurationLookup`).

    NULL, NOT ZERO, on a missing/unconfigured duration. Zero would be indistinguishable from a
    real (if useless) zero-minute service, and bookings' own refusal ("مدة غير مضبوطة") depends on
    telling "not configured" apart from "configured as zero" — the exact "silent default decides
    policy" family this whole feature is built to avoid.
    """
    c = request.app.state.container
    services = await ServiceStore(c.datastore).list(body.tenant, active_only=False)
    by_id = {s.id: s for s in services}
    total = 0
    for sid in body.service_ids:
        svc = by_id.get(sid)
        if svc is None or not svc.duration_minutes:
            return {"duration_minutes": None}
        total += svc.duration_minutes
    return {"duration_minutes": total}


class VisitFromCustomerIn(BaseModel):
    tenant: str = Field(min_length=1, max_length=128)
    customer_id: str = Field(min_length=1, max_length=64)
    service_ids: list[str] = Field(min_length=1, max_length=20)
    operator_id: str = Field(default="", max_length=64)
    branch_id: str = Field(default="", max_length=64)
    note: str = Field(default="", max_length=1000)
    idempotency_key: str = Field(min_length=1, max_length=128)
    occurred_at: int = Field(default=0, ge=0)


@router.post("/operations/visits/from-customer", dependencies=[Depends(require_internal_token)])
async def internal_visit_from_customer(request: Request, body: VisitFromCustomerIn) -> dict:
    """`bookings`' one call into the booking->visit gateway (docs/خطة-تنفيذ-الحجوزات.md §4, Stage
    4): a booking already holds `customer_id` — this SERVICE's identity for the person, not a
    phone bookings would have to hold a second copy of — so this resolves by id and hands off to
    the SAME `record_visit()` every other path uses, rather than re-implementing visit creation.

    404-shaped refusal, not a 500, when the customer no longer exists (deleted between the booking
    being made and the appointment being attended — rare, but not impossible over weeks).

    `idempotency_key` REQUIRED, unlike the interactive route — this is a service-to-service call
    with no user re-tapping a screen, so the caller (bookings, keying on its own booking id) is the
    only party that can tell a genuine retry from a second attendance.
    """
    c = request.app.state.container
    customer = await CustomerStore(c.datastore).get(body.tenant, body.customer_id)
    if customer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "العميلة غير موجودة")
    try:
        recorded = await c.operations.record_visit(
            tenant=body.tenant, phone=customer.phone, service_ids=body.service_ids,
            operator_id=body.operator_id, branch_id=body.branch_id, note=body.note,
            idempotency_key=body.idempotency_key, occurred_at=body.occurred_at)
    except OperationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return {"visit_id": recorded.visit.id, "customer_id": recorded.customer.id,
           "duplicate": recorded.duplicate}


class CustomerSubjectRefIn(BaseModel):
    tenant: str = Field(min_length=1, max_length=128)
    customer_id: str = Field(min_length=1, max_length=64)


@router.post("/operations/customers/subject-ref", dependencies=[Depends(require_internal_token)])
async def internal_customer_subject_ref(request: Request, body: CustomerSubjectRefIn) -> dict:
    """A customer's PSEUDONYM, for a peer that holds `customer_id` (this service's own identifier)
    and needs the identifier every OTHER service already carries every day — `reminders`' whole
    schedule table is keyed on it, `insights` counts by it, `campaigns` targets by it.

    NOT `/operations/recipient`'s sibling — that route turns a pseudonym back into a PHONE NUMBER
    and is, by its own docstring, "the single most sensitive surface this service has". This one
    goes the other way and stops at the pseudonym everybody already holds; it reveals nothing a
    peer could not already ask for by other means, and unlike the recipient route it answers
    ONE identifier a caller already possesses (`customer_id`) with another, not a phone number.

    Empty string, not 404, for an unknown or erased customer — same reasoning as `/recipient`: a
    404 here would let anyone holding the internal token probe which customer ids exist.
    """
    c = request.app.state.container
    row = await c.datastore.get(CUSTOMERS, f"{body.tenant}|{body.customer_id}")
    return {"subject_ref": str((row or {}).get("subject_ref") or "")}


class CustomersIn(BaseModel):
    tenant: str = Field(min_length=1, max_length=128)
    # Bounded, and the ceiling is a product decision: an establishment with more customers than
    # this in one campaign is a case we want to look at before it goes out.
    limit: int = Field(default=5000, ge=1, le=5000)
    # WHICH BRANCH'S CUSTOMERS, or every one of them when empty (spec 12.2).
    #
    # FILTERED HERE, NOT BY THE CALLER, and that is the whole point of the field being on the
    # request. `limit` is applied by the datastore: a caller that asked for everybody and then kept
    # the Jeddah rows would be filtering the 5000 most recent customers of the WHOLE shop — for a
    # chain, that is a Jeddah audience with most of Jeddah missing, and it would look perfectly
    # plausible while being wrong.
    branch_id: str = Field(default="", max_length=64)


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
    where: dict[str, Any] = {"tenant": body.tenant}
    if body.branch_id:
        where["last_branch_id"] = body.branch_id
    # LEAST RECENTLY SEEN FIRST, AND IT USED TO BE THE OPPOSITE. `sort=("last_visit","desc")`
    # returned the customers who came in MOST recently — so for a shop with more customers than
    # `limit`, a «win them back» campaign drew its audience from precisely the people who have not
    # gone anywhere, and the long-absent were never even considered. Every goal this route feeds
    # reasons about absence; ascending is the order that puts the subject of the question first.
    rows, cursor = await c.datastore.find(CUSTOMERS, where,
                                          limit=body.limit, sort=("last_visit", "asc"))
    return {"customers": [{"subject_ref": r.get("subject_ref", ""),
                           "last_visit": int(r.get("last_visit") or 0),
                           "visit_count": int(r.get("visit_count") or 0),
                           # CARRIED BACK so the caller can say who it is about without a second
                           # read. A campaign report that cannot name the branch it went to is a
                           # report the owner has to take on trust.
                           "last_branch_id": r.get("last_branch_id", "")}
                          for r in rows if r.get("subject_ref")],
            "count": len(rows),
            # SAID OUT LOUD. The caller counts a truncation of its OWN candidate list and reports
            # it on the preview screen, but it had no way to know this SOURCE had been cut — so a
            # chain whose customer book is larger than `limit` was shown an audience drawn from
            # part of its shop, labelled as the whole of it. Whether the source stopped early is
            # something only this side can know, so only this side can say it.
            "truncated": cursor is not None}


@router.post("/operations/tenants-with-visits", dependencies=[Depends(require_internal_token)])
async def tenants_with_visits(request: Request) -> dict:
    """Every establishment that has ever recorded a visit — NAMES ONLY, no visit rows.

    WHY THIS EXISTS AS ITS OWN ROUTE. `insights` used to derive its tenant list from one page of
    `/operations/visits-since`: five hundred visit rows, and `scan_all` orders by KEY, which for a
    visit is `tenant|visit_id`. So a single establishment whose id sorts first alphabetically and
    which has five hundred visits consumed the entire page — and the answer was a list of ONE
    tenant. Forty shops on the cluster, thirty-nine of them never visited by the snapshot cron
    again: their dashboard is computed once, the first time somebody opens it, and served
    unchanged for ever after.

    The question was never «give me some visits and I will work out who exists». It is «who
    exists», and that answer is a set of at most a few hundred strings however many millions of
    visits sit behind it. Reading it as a side effect of a page of visits is what made the size of
    one shop able to hide every other shop.

    PAGED TO EXHAUSTION, AND HONEST WHEN IT IS NOT. `scan_all` now takes a cursor, so this walks
    the whole collection in key order accumulating distinct tenants. The budget is high because
    what is kept is a set of tenant ids rather than rows; crossing it sets `exhaustive: false`
    rather than returning a shorter list that looks complete.
    """
    c = request.app.state.container
    PAGE, MAX_PAGES = 1000, 500          # up to 500,000 visit rows walked, holding only the names
    tenants: set[str] = set()
    after: str | None = None
    pages = 0
    exhaustive = True
    while pages < MAX_PAGES:
        rows = await c.datastore.scan_all(VISITS, limit=PAGE, after=after)
        pages += 1
        if not rows:
            break
        for r in rows:
            name = r.get("tenant") or ""
            if name:
                tenants.add(name)
        if len(rows) < PAGE:
            break
        after = f"{rows[-1].get('tenant', '')}|{rows[-1].get('id', '')}"
    else:
        exhaustive = False

    return {"tenants": sorted(tenants), "count": len(tenants), "exhaustive": exhaustive}


class VisitsSinceIn(BaseModel):
    # EMPTY MEANS EVERY TENANT, and that is not a convenience — it is what makes the catch-up able
    # to BOOTSTRAP. A consumer that can only ask about tenants it already knows can never learn
    # about the one whose very first event it missed, which is precisely the case the catch-up
    # exists to repair. Found by running the tick on a live cluster and getting "tenants: 0".
    tenant: str = Field(default="", max_length=128)
    # Exclusive watermark. The caller stores the highest `created` it has processed and asks for
    # what came after — a cursor it owns, not a subscription we owe it.
    since: int = Field(ge=0)
    # THE CEILING COMES FROM CONFIG, NOT FROM A LITERAL. Written here as `le=1000` it was invisible
    # to the service that had to respect it, and insights asked for five thousand — so every
    # snapshot was refused 422 before any work was done. Now both sides read one declared number
    # and `ci/check_paired_config.py` fails the build the day they part.
    limit: int = Field(default=200, ge=1, le=get_settings().VISITS_PAGE_MAX)
    # NEWEST FIRST, FOR THE READER THAT WANTS A WINDOW RATHER THAN A CATCH-UP.
    #
    # The catch-up needs ascending: a watermark that skips a row is a visit no consumer will ever
    # hear about again. The SNAPSHOT needs the opposite — its indicators are all «the last ninety
    # days» — and it was walking ascending from zero with a sixty-page budget, so a shop with
    # 120,000 visits had its dashboard computed from 2021–2022 and `active_customers(90)` answered
    # zero. Two readers, two orders, and forcing the second to walk the first's order is what made
    # the busiest shops the ones with the worst numbers.
    #
    # `since` is ignored when this is set, deliberately: «the newest N» and «everything after a
    # watermark» are different questions, and answering both at once would be a third question
    # nobody asked.
    newest_first: bool = False


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
    exhaustive = True
    if body.tenant and body.newest_first:
        # ONE READ, DESCENDING. No paging and no watermark: the caller asked for the newest
        # `limit` visits and that is exactly one page. `exhaustive` says whether there were more
        # behind them, so a snapshot can report itself partial rather than wrong.
        rows, cursor = await c.datastore.find(
            VISITS, {"tenant": body.tenant}, limit=body.limit, sort=("created", "desc"))
        exhaustive = cursor is None
    elif body.tenant:
        # PAGE FORWARD PAST WHAT THE READER ALREADY HAS — and the reason this is not one read.
        #
        # The datastore's `where` is equality only (ports/datastore.py), so `created > since`
        # cannot be expressed as a query and has to be applied to the rows. Reading ONE page and
        # filtering it meant that once a shop passed `limit` lifetime visits, that first page was
        # entirely older than the watermark, `fresh` came back empty, and the catch-up — the safety
        # net for an at-most-once bus — silently stopped catching up. For ever, and for exactly the
        # busy shops that need it.
        #
        # So the cursor is followed until enough fresh rows are collected or the collection ends.
        # Bounded by MAX_PAGES so a shop with a decade of history cannot turn a five-minute cron
        # into an unbounded scan; when the bound is hit, `exhaustive` says so rather than letting
        # a truncated answer read as a complete one.
        MAX_PAGES = 50
        rows, cursor, pages = [], None, 0
        while pages < MAX_PAGES:
            page, cursor = await c.datastore.find(
                VISITS, {"tenant": body.tenant}, limit=body.limit,
                after=cursor, sort=("created", "asc"))
            pages += 1
            rows.extend(r for r in page if int(r.get("created") or 0) > body.since)
            if not cursor or len(rows) >= body.limit:
                break
        else:
            exhaustive = False
        if pages >= MAX_PAGES and cursor:
            exhaustive = False
        rows = rows[:body.limit]
    else:
        # sweeper: reading EVERY tenant's visits IS the operation here, not a forgotten filter.
        # This is the bootstrap path — a consumer that can only ask about tenants it already knows
        # can never learn about the one whose first event it missed, and the event bus is
        # at-most-once. `find` correctly refuses an empty `where`; this says out loud that the
        # absence of a filter is the point.
        #
        # It is internal-token only, bounded by `limit`, and driven by a five-minute cron, so the
        # cost is a bounded read every five minutes rather than anything on a request path.
        # THE SWEEPER'S OWN LIMIT, and it is not the caller's. A whole-collection scan cannot be
        # paged, so a page-sized scan filtered afterwards has the identical defect the tenant path
        # just fixed. Reading a wider window makes the bootstrap actually bootstrap; `exhaustive`
        # below reports honestly when even that window was full.
        scan_cap = max(body.limit * 10, 2000)
        rows = await c.datastore.scan_all(VISITS, limit=scan_cap)
        exhaustive = len(rows) < scan_cap
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
            # READ BY THE GROUP-BASKET TEST, and by nothing else. insights asked for `quantities`
            # from the first day; this row never carried the key, so the test that drops a party's
            # receipt from learning has never had anything to work with.
            "quantities": dict(r.get("quantities") or {}),
            # SAME NAME AS THE EVENT, because loyalty's catch-up reads this row when the bus drops
            # one — two spellings would make a repaired visit earn differently from a live one.
            "amount_halalas": int(r.get("total_minor") or 0),
            # SAME NAME AS THE EVENT, for the same reason every other field here is: the catch-up
            # reads this row when the bus drops one, and a free wash must not earn on the repaired
            # path when it earned nothing on the live one.
            "free": bool(r.get("free")),
            "asset_id": r.get("asset_id", ""),
            "operator_id": r.get("operator_id", ""),
            "branch_id": r.get("branch_id", ""),
            "visit_count": (cust or {}).get("visit_count", 0),
            "occurred_at": r.get("occurred_at") or r.get("created"),
            "created": r.get("created"),
        })
    return {"visits": out, "count": len(out),
            # WHETHER THIS ANSWER IS THE WHOLE ANSWER. A caller that cannot tell a complete page
            # from a truncated one will advance its watermark past visits it never received.
            "exhaustive": exhaustive,
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
    # THIS VISIT WAS BOUGHT WITH POINTS, NOT WITH MONEY (ب-6). loyalty has sent this flag since the
    # route existed and the model did not declare it, so pydantic dropped it: the free wash was
    # recorded as an ordinary visit, and the earn rule then paid the customer points for spending
    # points. The reward costs the shop twice and the balance drifts upward for nobody's reason.
    #
    # Default False, because every OTHER caller of a visit door is recording a sale.
    free: bool = False


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
            free=body.free,
            note="مكافأة ولاء")
    except OperationError as exc:
        return {"recorded": False, "reason": str(exc)}
    if not res.duplicate:
        # THE SEAMS RUN HERE TOO (د-20). A free wash is a visit like any other: it must restart
        # the reminder cycle and reach the index. Without this the customer is reminded to come in
        # for the service he was handed at the counter, and the search that finds him by plate does
        # not know he was here. Inline rather than a background task, as in the batch door: nobody
        # is watching this call, so there is no screen budget to protect.
        await c.seams.after_visit(res)
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


@router.post("/operations/branches", dependencies=[Depends(require_internal_token)])
async def read_branches(request: Request, body: CatalogueIn) -> dict:
    """One establishment's places — id and name, nothing else.

    FOR `insights`, and for one reason: its branch table is grouped by the `branch_id` carried on
    each visit, and it has no way at all to turn that id into a word. The table rendered every row
    as «بلا اسم» because the name lives here and nothing carried it across.

    CLOSED ONES INCLUDED. A shop that shut a branch in March still has February's visits under it,
    and a report that cannot name them is the same defect one month later.

    The same shape as the catalogue read above, deliberately: a second idiom for "read a list of
    this tenant's rows" is a second thing to keep correct.
    """
    c = request.app.state.container
    rows = await BranchStore(c.datastore).list(body.tenant)
    return {"branches": [{"id": b.id, "name": b.name, "active": b.active} for b in rows],
            "count": len(rows)}



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


class PrivacyRequestIn(BaseModel):
    tenant: str = Field(min_length=1, max_length=128)
    subject_ref: str = Field(min_length=8, max_length=128)
    # `export` or `erase`. Correction is deliberately not offered from the page: it is a sentence
    # at the counter and the operator fixes it in a second, which is faster than any queue.
    type: str = Field(min_length=3, max_length=16)


@router.post("/operations/privacy-request", dependencies=[Depends(require_internal_token)])
async def privacy_request(request: Request, body: PrivacyRequestIn) -> dict:
    """A customer asked HIS SHOP for his data, from his own page.

    RECORDED, NOT EXECUTED. The establishment is the controller under the PDPL and the right is
    exercised against it; a page that erased a customer's history the moment he tapped would be us
    acting for the controller without its knowledge — and would hand anyone holding a page link a
    delete button for somebody else's record. The owner already has the control (§ pdpl 3); what he
    never had was any way to know a request existed.

    THE MOMENT IS THE POINT. It is when the thirty-day clock in the regulation starts, and this row
    is what proves it started — so it survives the erasure it asks for, holding a pseudonym and a
    type and nothing else about him.
    """
    kind = body.type.strip().lower()
    if kind not in PR.TYPES:
        return {"ok": False, "reason": f"type must be one of {list(PR.TYPES)}"}
    # THE STORE, NOT A HELPER THAT NEVER EXISTED. This line called `_svc(request)` — a name defined
    # nowhere in this module — so every privacy request a customer made through his own page raised
    # NameError and returned 500. The request was never recorded, so PDPL's thirty-day clock never
    # started and nothing anywhere showed it had been asked for. Import succeeded, the app booted
    # and the suite was green throughout: only the line itself could have failed, and only when a
    # real customer ran it.
    req = await PrivacyRequestStore(request.app.state.container.datastore).open_request(
        body.tenant, body.subject_ref, kind)
    await request.app.state.auditor.record(
        "privacy.requested", actor="", tenant=body.tenant, resource=f"privacy:{req.id}",
        metadata={"type": kind})
    return {"ok": True, "id": req.id, "at": req.at}


@router.post("/operations/whatsapp/health", dependencies=[Depends(require_internal_token)])
async def whatsapp_health(request: Request) -> dict:
    """Hourly: ask Meta about every live number and stop the ones whose access is gone.

    A CONNECTION HAS NO EVENT TO WAIT FOR. Access ends in the owner's Business Manager or at Meta,
    and the webhook that would announce it is at-most-once — a service restarting during that one
    delivery never hears about it again. So this is a READ, run on a clock: the state of a
    connection is always recoverable from Meta rather than from an event we may have missed.

    NO BODY AND NO TENANT: the clock decides the work list, not the caller.
    """
    from app.core import connect as connect_core

    c = request.app.state.container
    out = await connect_core.health_sweep(
        connect_core.ConnectionStore(c.datastore), connect_core.build_registration(get_settings()))
    for key in out.get("stopped_keys", []):
        # AUDITED PER NUMBER, because «متى توقّف رقمي» is the first question after «لماذا توقّفت
        # الرسائل» — and the actor is this sweep, not a person.
        await request.app.state.auditor.record(
            "whatsapp.connection_lost", actor="cron:whatsapp-health",
            tenant=key.split("|")[0], resource=f"connection:{key}", ip="")
    return out


@router.post("/operations/gauges/reconcile", dependencies=[Depends(require_internal_token)])
async def gauges_reconcile(request: Request) -> dict:
    """Report every establishment's true seat and branch count to billing. Driven by a CronJob.

    WHY THIS HAS TO EXIST. `allows_one_more` fails OPEN on purpose — an unreachable billing must
    not stop a shop hiring somebody — and its comment justifies that with «the next report corrects
    the count anyway». There was no next report: `report()` ran only on the write path, moments
    after a create, during the very outage that let the extra seat through, and it swallows its own
    errors. So a five-seat shop that hired during a billing hiccup kept seats six and seven for
    ever, unbilled, and nothing anywhere would have said so.

    NO BODY AND NO TENANT ARGUMENT, the same rule as the retention sweep below: a reconciliation
    that took a tenant would be a usage-writing endpoint with a filter on it, and the internal
    token is held by every service in the mesh.
    """
    from app.core import seats as S
    from app.core.models import BRANCHES as BRANCHES_COLLECTION
    from app.core.models import OPERATORS

    c = request.app.state.container
    cap = 5000
    tenants: set[str] = set()
    # BOTH COLLECTIONS. A shop with branches and no staff still owes billing a branch count, and a
    # work-list built from one of them would silently exclude the other's outliers.
    for collection in (OPERATORS, BRANCHES_COLLECTION):
        for row in (await c.datastore.scan_all(collection, cap) or []):
            if row.get("tenant"):
                tenants.add(str(row["tenant"]))
    return await S.reconcile(datastore=c.datastore, gauges=c.gauges, tenants=sorted(tenants))


@router.post("/operations/visits/reseam", dependencies=[Depends(require_internal_token)])
async def visits_reseam(request: Request) -> dict:
    """Finish the after-work for visits whose process went away before it ran (ز-7).

    THE SEAMS RUN AFTER THE RESPONSE, which is right — the operator has a customer in front of him
    and must not wait on our fan-out. But it also means they run in a window where the pod can be
    evicted, and when that happened the visit was saved and NONE of it was done: no search index,
    so the keypad cannot find that customer; and no event, so reminders scheduled nothing and
    insights counted nothing. The reminder is the entire product, and it was simply absent.

    NOTHING LOOKED. `seams.py` said in its own docstring that a failure «lets the sweep or the next
    visit repair it» — there was no sweep, and the next visit repairs nothing: it indexes its own
    customer and emits its own event, neither of which schedules the reminder the lost visit owed.
    A reason given for a decision has to be a mechanism, and this is the mechanism.

    ONLY THE SETTLED ONES. A visit seconds old has its seams running right now; picking it up would
    duplicate work that is about to succeed. `_RESEAM_AFTER` is the margin.

    NO BODY AND NO TENANT: the clock decides the work list, not the caller.
    """
    from app.core.models import VISITS

    c = request.app.state.container
    now = int(time.time())
    cap = 5000
    tenants: set[str] = set()
    for row in (await c.datastore.scan_all(VISITS, cap) or []):
        if row.get("tenant"):
            tenants.add(str(row["tenant"]))

    store = VisitStore(c.datastore)
    customers = CustomerStore(c.datastore)
    repaired = 0
    for tenant in sorted(tenants):
        for visit in await store.unseamed(tenant, before=now - _RESEAM_AFTER):
            customer = await customers.get(tenant, visit.customer_id)
            if customer is None:
                # A visit whose customer is gone — erased under PDPL, most likely. There is
                # nothing to index and nobody to remind, and leaving it unmarked would make the
                # sweep pick it up for ever.
                visit.seamed_at = now
                await store.save(visit)
                continue
            await c.seams.after_visit(RecordedVisit(
                visit=visit, customer=customer, created_customer=False, duplicate=False))
            repaired += 1
    return {"repaired": repaired, "tenants": len(tenants)}


#: How long a visit must have been settled before the sweep treats its missing seams as lost
#: rather than as still in flight. Generous on purpose: a repeat pass costs one index write and
#: one event, and racing a request that is about to succeed costs a duplicate of both.
_RESEAM_AFTER = 300

#: Names for the two hourly template passes' rotation cursors.
#:
#: ONE EACH, NOT ONE SHARED. They do different work at different costs — reading Meta's verdicts is
#: a single call per shop, handing the library over is sixty-seven — so they run out of window at
#: different places. A shared mark would let the cheap pass drag the expensive one's cursor past
#: shops it had never published for, which is the starvation this rotation exists to end, hidden
#: one level deeper.
SWEEP_APPROVALS = "template-approvals"
SWEEP_PUBLISH = "template-publish"


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


@router.post("/operations/templates/sync-approvals",
             dependencies=[Depends(require_internal_token)])
async def sync_template_approvals(request: Request) -> dict:
    """Ask Meta — through notification-service — what became of every connected shop's templates.

    THE MISSING CALLER. notification-service holds a correct per-tenant sweep and said in its own
    docstring that the scheduler drives it; nothing ever did. So a template Meta approved within
    the hour stayed `pending` with us for ever, and the send path — which rightly prefers an
    approved template — refused every message with «ما زالت قيد مراجعة واتساب». The engine was not
    broken and nothing was logged as wrong: it was waiting on a fact nobody went to read.

    NO TENANT ARGUMENT, like the retention sweep above and for the same reason: the internal token
    is held by every service in the mesh, and a sweep that takes a tenant is a per-shop endpoint
    with a filter on it. This one only does what the clock already decided.

    ONE SHOP'S FAILURE IS NOT THE PASS'S. An unreachable account, a revoked token, a WABA deleted
    at Meta's end — each is counted and named in telemetry, and the sweep moves to the next shop.
    Anything else lets one broken establishment keep the whole fleet's statuses stale.
    """
    from app.core.approvals import build_approvals
    from app.core.connect import ConnectionStore

    c = request.app.state.container
    s = get_settings()
    approvals = build_approvals(s)
    if getattr(approvals, "driver", "null") == "null":
        # HONEST, NOT QUIET. "0 tenants" from an unconfigured sweep looks exactly like a fleet
        # with nothing to do — and that is the shape of the bug this whole route exists to fix.
        return {"ok": False, "configured": False, "tenants": 0, "synced": 0, "failed": 0}

    # LEAST-RECENTLY-SYNCED FIRST, AND THE MARK IS WRITTEN AS WE GO. This used to take the newest
    # connections, capped, in the same order every hour — so a pass that ran out of window restarted
    # at the head rather than resuming, and the shops behind the cut were never read at all.
    store = ConnectionStore(c.datastore)
    tenants = await store.live_tenants(limit=s.TEMPLATE_SYNC_MAX_TENANTS, sweep=SWEEP_APPROVALS)
    synced = failed = 0
    for tenant in tenants:
        out = await approvals.sync(tenant)
        # MARKED WHETHER IT SUCCEEDED OR NOT. A shop whose sync fails every time would otherwise
        # keep its place at the head of the queue for ever and starve everybody behind it — the
        # same defect one layer down. A failure is reported; it does not get priority.
        await store.mark_swept(SWEEP_APPROVALS, tenant, int(time.time()))
        if out.get("ok", False) is False:
            failed += 1
            c.telemetry.event("template_sync_failed", tenant=tenant,
                              reason=str(out.get("reason", ""))[:120])
            continue
        synced += 1
    if failed:
        c.telemetry.event("template_sync_pass", tenants=len(tenants), synced=synced, failed=failed)
    return {"ok": True, "configured": True, "tenants": len(tenants),
            "synced": synced, "failed": failed}


@router.post("/operations/templates/publish",
             dependencies=[Depends(require_internal_token)])
async def publish_template_libraries(request: Request) -> dict:
    """Make sure every connected shop's library is registered and moving through Meta's queue.

    THE CONNECT PATH ALREADY DOES THIS for a shop that has just finished Embedded Signup. This is
    the pass that covers what that moment cannot:

      · a connection made before this code existed — every shop already live;
      · a library that half-registered because notification-service restarted mid-publish;
      · Meta's 100-per-account-per-hour cap, which no single request may exceed. A library of 66
        fits, but a shop that also wrote its own templates does not, and the remainder has to be
        handed over on a later tick. That is what `submit-pending` is for and why this is hourly.

    IDEMPOTENT AT BOTH ENDS, which is what makes an hourly re-run safe rather than merely tolerable:
    registering is an upsert that explicitly never resets an approved template to pending, and the
    drain submits only templates that have never been handed over.

    ONE SHOP'S FAILURE IS NOT THE PASS'S — the same rule as the approvals sweep above.
    """
    from app.core.connect import ConnectionStore
    from app.core.library import publish

    c = request.app.state.container
    s = get_settings()
    if getattr(c.library, "driver", "null") == "null":
        # HONEST, NOT QUIET. "0 tenants" from an unconfigured pass reads exactly like a fleet with
        # nothing to do — and that shape is the bug this route exists to end.
        return {"ok": False, "configured": False, "tenants": 0, "published": 0, "failed": 0}

    templates = await c.templates.list()
    # THE SLOWEST PASS IN THE FLEET, AND THE ONE STARVATION COST MOST. One shop here is 66 register
    # calls plus a drain, so a handful of them can fill an entire window — and the shops that never
    # came round had no template registered at all, which means no template approved, which means
    # the send path refuses every message they will ever try to send.
    store = ConnectionStore(c.datastore)
    tenants = await store.live_tenants(limit=s.TEMPLATE_SYNC_MAX_TENANTS, sweep=SWEEP_PUBLISH)
    published = failed = 0
    for tenant in tenants:
        out = await publish(c.library, templates, tenant)
        await store.mark_swept(SWEEP_PUBLISH, tenant, int(time.time()))
        if out.get("failed") or not out.get("drain", {}).get("ok", False):
            failed += 1
            c.telemetry.event("template_publish_failed", tenant=tenant,
                              registered=out.get("registered", 0),
                              reason=str(out.get("drain", {}).get("reason", ""))[:120])
            continue
        published += 1
    if failed:
        c.telemetry.event("template_publish_pass", tenants=len(tenants),
                          published=published, failed=failed)
    return {"ok": True, "configured": True, "tenants": len(tenants),
            "published": published, "failed": failed}


class StatementRunIn(BaseModel):
    """An OPTIONAL body — the scheduler sends none.

    A cron POSTs an empty request; a required model here is a 422 before a line of this code runs,
    which is how every heartbeat in this product was found silently failing one night. The two
    fields exist for the manual re-run of a closed month, and for nothing else.
    """

    period_start: int = Field(default=0, ge=0)
    period_end: int = Field(default=0, ge=0)


@router.post("/operations/partners/statements/run",
             dependencies=[Depends(require_internal_token)])
async def run_partner_statements(request: Request,
                                 body: StatementRunIn | None = None) -> dict:
    """Issue last month's commission statements — the call the engine never had.

    DRIVEN BY THE CLOCK, NEVER BY A PARTNER. `api/v1/partner.py` is read-only for exactly this
    reason: a disputed month a partner can re-run until the total suits them is not a statement.
    An operator may re-run one from our own panel, which is a different thing with a name on it.

    IDEMPOTENT. Keyed by partner and period, a second run overwrites with the same figures —
    `build` is pure and takes its boundaries as arguments — unless the settlements themselves
    moved, in which case the new number is the correct one.
    """
    body = body or StatementRunIn()
    c = request.app.state.container
    from app.core import statements_run

    period = None
    if body.period_start and body.period_end and body.period_end > body.period_start:
        period = (body.period_start, body.period_end)

    out = await statements_run.issue(
        store=c.datastore, settlements_source=c.settlements, period=period)
    if out.get("skipped"):
        # LOUD IN TELEMETRY, EMPTY ON DISK. Issuing zeros because a peer was unreachable would put
        # a number in front of a partner that we would have to withdraw next month.
        c.telemetry.event("partner_statements_skipped", reason=out["skipped"],
                          period_start=out["period_start"])
    else:
        await request.app.state.auditor.record(
            "partner.statements_issued", actor="schedule", tenant="_platform",
            resource=f"period:{out['period_start']}",
            metadata={"issued": out.get("issued", 0)})
    return out


class BranchScopeIn(BaseModel):
    tenant: str = Field(min_length=1, max_length=128)
    # The token's `sub`. A pseudonymous person id, never a name or a number.
    subject: str = Field(min_length=1, max_length=128)


@router.post("/operations/branch-scope", dependencies=[Depends(require_internal_token)])
async def branch_scope_of(request: Request, body: BranchScopeIn) -> dict:
    """Which branch this person may see — the one answer another service cannot work out.

    THE JOIN IS OURS ALONE. A token carries a subject and a tenant; the row that says where
    somebody works lives here, beside the seat count and the branch list. `insights` renders a
    dashboard per branch and has no idea who works where; `loyalty` holds a ledger with a branch on
    every movement and the same blindness. Either could be handed the answer at read time, or each
    could grow its own copy of our staffing — and the second is how two services come to disagree
    about who may see what.

    EMPTY MEANS THE WHOLE ESTABLISHMENT, and it is the common answer: the owner has no operator
    row at all, and most shops assign nobody. Narrowing is opt-in per person.

    IT IS A READ AND IT REFUSES NOTHING. The caller decides what to do with the scope; this route
    only says what it is.
    """
    from app.api.scope import branch_scope
    from types import SimpleNamespace

    scope = await branch_scope(request.app.state.container.datastore,
                              SimpleNamespace(subject=body.subject, tenant=body.tenant))
    # AND «STOPPED» IS ITS OWN FIELD, because it cannot be said in `branch_id`. Every consumer
    # reads that field as `str(... or "")`, so a null — or any empty answer — becomes "", and ""
    # means the WHOLE establishment. A dismissed employee would have been widened to the entire
    # chain by three services at once. The flag is unmissable and the empty string stays honest.
    # TWO FIELDS, BECAUSE THE ANSWER IS A SET AND THE OLD ONE COULD ONLY HOLD A NAME. `branches` is
    # what he may see — empty meaning «no narrowing» — and `branch_id` stays beside it carrying the
    # single-branch case, so a consumer deployed before this release keeps reading the answer it
    # understands rather than silently reading "" and showing him the whole chain. A man who watches
    # several has no honest `branch_id`, and it is left empty ONLY together with a `branches` list
    # that says so.
    branches = sorted(scope) if isinstance(scope, (set, frozenset)) else ([scope] if scope else [])
    return {"branch_id": branches[0] if len(branches) == 1 else "",
            "branches": branches,
            "revoked": scope is None}


class EvidenceIn(BaseModel):
    tenant: str = Field(min_length=1, max_length=128)
    # A WINDOW, NOT «EVERYTHING». Every real question is about a period — a complaint, an audit, a
    # dispute — and a file that answers "everything" is both unreadable and a disclosure larger
    # than the question asked.
    since: int = Field(default=0, ge=0)
    until: int = Field(default=0, ge=0)
    # Who asked. Carried rather than inferred: this route is internal-tier, so the caller is our
    # own panel and the person behind it is the fact that matters.
    actor: str = Field(default="", max_length=128)


@router.post("/operations/evidence", dependencies=[Depends(require_internal_token)])
async def evidence_file(request: Request, body: EvidenceIn) -> dict:
    """One establishment's evidence file — see core/evidence.py for what it is and is not.

    THE DISCLOSURE IS RECORDED FIRST, and that order is the point. A file handed over and then
    audited is a file whose record can be lost between the two — and the one moment this trail
    exists for is the moment somebody takes a copy of it.
    """
    c = request.app.state.container
    await request.app.state.auditor.record(
        "compliance.evidence_exported", actor=body.actor or "internal", tenant=body.tenant,
        resource="evidence_file", ip=request.client.host if request.client else "",
        # BOTH NAMES, BECAUSE THEY ARE DIFFERENT FACTS — proven on the cluster, where the row came
        # back carrying the CALLING SERVICE's subject rather than the person we passed. The caller
        # is what the platform can verify; `asked_by` is the human who pressed the button, and a
        # disclosure record that names only the machine answers «which service» when the question
        # is «which person».
        metadata={"since": body.since, "until": body.until,
                  "asked_by": body.actor or "unnamed"})

    file = EV.EvidenceFile(
        privacy_store=PrivacyRequestStore(c.datastore),
        consent_reader=getattr(c, "evidence_peer", None),
        legal_reader=getattr(c, "legal_acceptances", None))
    return await file.build(body.tenant, since=body.since, until=body.until,
                            actor=body.actor)
