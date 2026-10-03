"""The route the owner's browser calls the instant Embedded Signup answers.

WHY THIS IS ITS OWN ROUTER AND NOT A PATH UNDER /subscription. Connecting is not subscribing: it
happens BEFORE a paid subscription (that is the rule subscribe.py enforces), it happens again when
a shop changes its number, and it happens during a trial when there is no subscription at all. A
path that read /subscription/whatsapp/connect would have described the sequence we happen to ship
rather than the thing being done.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.api.authz import require_capability
from app.api.ratelimit import rate_limit
from app.api import scope as SCOPE
from app.api.scope import REVOKED, branch_scope
from app.config import get_settings
from app.core import branches as B
from app.core import connect
from app.core import sending_identity as SI
from app.core.stores import BranchStore
from app.api.subscribed import no_subscription_needed

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])

# THE OWNER'S OWN CAPABILITY. He is connecting his own account; a route needing a platform
# capability would mean no shop could connect without one of us on the call — which is the whole
# point of Embedded Signup being self-service.
_OWNER = require_capability("billing.self")


class SignupResultIn(BaseModel):
    """What Embedded Signup posts back to the browser.

    PERMISSIVE, AND THAT IS THE DESIGN RATHER THAN A RELAXATION. This body arrives with about thirty
    seconds of life in it. A validation refusal here costs the owner the entire popup journey to fix
    a field we could have accepted, and the exchange is the real validation anyway — Meta rejects a
    bad code far more reliably than a regex here would.
    """

    # FINISH carries the identifiers and the code; CANCEL carries only the step.
    event: str = Field(default="FINISH", max_length=32)
    code: str = Field(default="", max_length=4096)
    waba_id: str = Field(default="", max_length=128)
    phone_number_id: str = Field(default="", max_length=128)
    business_id: str = Field(default="", max_length=128)
    step: str = Field(default="", max_length=64)
    # WHICH BRANCH'S NUMBER THIS IS — empty is the establishment's own, which is every shop in the
    # default mode. Ignored entirely while the shop is central: see `sending_identity.resolve`,
    # which drops it rather than letting one screen decide differently from another.
    branch_id: str = Field(default="", max_length=64)
    # WHAT META SAID WHEN THE OWNER REPORTED A PROBLEM FROM INSIDE THE POPUP (Embedded Signup v4
    # sends `error_message` / `error_code` on that CANCEL). The popup is Meta's window and we
    # cannot see into it, so this is the only account of a failure that had a stated cause.
    #
    # HELD, NEVER SHOWN. It is English and it is theirs — `Attempt.public()` does not carry
    # `detail`, and `sentence_for` writes the owner's sentence in Arabic from the STATE. Support
    # reads this to answer «why did the connect fail on Thursday» instead of guessing from a step.
    #
    # AND IT IS THE BROWSER'S WORD, so it is bounded and never interpreted: nothing branches on it.
    detail: str = Field(default="", max_length=400)


@router.post("/connect", dependencies=[Depends(no_subscription_needed), Depends(rate_limit)])
async def whatsapp_connect(request: Request, body: SignupResultIn,
                           background: BackgroundTasks, principal=Depends(_OWNER)) -> Any:
    """Receive the Embedded Signup result and act on it inside this request.

    NO WORK BEFORE THE EXCHANGE, which inverts this service's usual write-ahead rule and does so for
    a reason that applies here and nowhere else: Meta's code lives about thirty seconds, so an audit
    round-trip taken first is time spent on the one thing that cannot afford it. An audit row about
    a code that expired while we were writing the row records a failure we caused.
    """
    tenant = getattr(principal, "tenant", "") or ""
    if not tenant:
        return JSONResponse(status_code=403,
                            content={"message": "لا توجد منشأة في هذه الجلسة."})

    c = request.app.state.container
    s = get_settings()
    store = connect.ConnectionStore(c.datastore)
    ip = request.client.host if request.client else ""

    # ── A NUMBER NOBODY PROVED MUST NOT BIND THE SHOP'S WHATSAPP (و-7) ─────────────────────────
    #
    # Nothing stands between typing a phone number and an account existing on it: the proof is
    # deferred to sign-in. So a stranger can open a shop on a number he does not hold, and THIS is
    # the act that turns that into somebody else's loss — the WhatsApp account a real business
    # sends from, bound under a login the real owner never chose.
    #
    # GATED ON THE SAME RULE THAT ALREADY GOVERNS SIGN-IN, deliberately. Where a code cannot be
    # delivered at all (SIGNUP_OTP_DELIVERABLE, task #167) nobody could ever satisfy this, and a
    # requirement no one can meet would close the product rather than protect it. Where sign-in
    # demands proof, so does this.
    if s.SIGNUP_REQUIRE_OTP and not await c.signup.phone_proven(tenant):
        await request.app.state.auditor.record(
            "whatsapp.connect_refused", actor=getattr(principal, "subject", ""), tenant=tenant,
            resource="connection", ip=ip)
        return JSONResponse(status_code=403, content={
            "message": "أكّد رقم جوالك قبل ربط واتساب المحل. "
                       "الرمز يصلك على الرقم الذي سجّلت به."})

    # ── WHICH NUMBER IS BEING CONNECTED, AND UNDER WHAT NAME ───────────────────────────────────
    # The identity is what the platform seals the credentials against. `tenant` for a central shop
    # — byte for byte what it has always sent — and `tenant:branch` only for a chain that has
    # deliberately moved to a number per branch (core/shop_mode.py).
    #
    # THE BRANCH IS VALIDATED AGAINST THIS TENANT'S REAL BRANCHES BEFORE IT NAMES ANYTHING (fixed
    # 2026-09-12, a real gap a QA audit found). Every other branch-scoped write in this service
    # checks the id against `branches.known()` (staff.py's hire/update, via `resolve_required`) —
    # this route alone took `body.branch_id` as-is and let it become half of a sealed credential
    # key. `B.resolve` (not `_required`) is the right member of that pair here: an empty branch is
    # a legitimate answer — the establishment's own number — so only an id that names something
    # that does not exist is dropped, logged, and treated as empty; it is never refused outright.
    validated_branch_id = await B.resolve(BranchStore(c.datastore), tenant, body.branch_id)

    # RESOLVED ONCE, HERE. The branch is dropped for a central shop in that one function, so the
    # row, the seal and the screen cannot disagree about which number this is.
    identity = await SI.resolve(c.datastore, tenant, validated_branch_id)
    branch_id = SI.split(identity)[1]

    if (body.event or "").upper() == "CANCEL":
        state = connect.classify_cancel(body.step)
        attempt = await store.record(connect.Attempt(
            tenant=tenant, state=state, step=(body.step or "").upper(), branch_id=branch_id,
            # WHAT META SAID, WHEN META SAID ANYTHING. Embedded Signup v4 sends `error_message`
            # and `error_code` on the CANCEL an owner raises from inside the popup — and that
            # popup is Meta's window, so this is the only account of a failure we can ever get.
            # Without it, «توقف عند خطوة الصلاحيات» was the whole record of a connect that failed
            # for a stated reason nobody kept.
            detail=body.detail))
        await request.app.state.auditor.record(
            "whatsapp.connect_stopped", actor=getattr(principal, "subject", ""), tenant=tenant,
            resource="whatsapp_connection", ip=ip)
        return attempt.public(can_send=await _can_send(identity, attempt))

    if not body.code:
        # A FINISH WITHOUT A CODE. Not a cancellation and not a failure of ours; it is the one shape
        # that means the browser lost the message, and the owner can only be asked to try again.
        return JSONResponse(status_code=400, content={
            "message": "لم يصل رمز الربط من واتساب. أعد فتح الربط وأكمل الخطوات."})

    # ── A FINISH WITH NO NUMBER IS NOT A CONNECTION ─────────────────────────────────────────────
    # Embedded Signup v2 required a verified phone number before it would finish. v3 and v4 do not:
    # the owner may complete the flow with an unverified number or none at all, and Meta returns a
    # session whose `phone_number_id` is simply absent.
    #
    # EXCHANGING ANYWAY IS THE WORST OUTCOME AVAILABLE. The token would be sealed against an EMPTY
    # phone-number id, the shop would read as «مربوط» on every screen, and every send would resolve
    # a credential that addresses no number — a shop that believes it is live and is mute. That is
    # this product's signature failure, and here it would be written deliberately.
    #
    # SO IT IS RECORDED, NOT EXCHANGED, and the sentence says what is missing and what to do. The
    # code is lost — it lives thirty seconds — and reconnecting after verifying the number is the
    # only honest path; pretending otherwise would cost him a day of silent messages instead.
    if not body.phone_number_id:
        attempt = await store.record(connect.Attempt(
            tenant=tenant, state=connect.STATE_FINISHED_UNCONFIRMED,
            waba_id=body.waba_id, business_id=body.business_id,
            detail="finish carried no phone_number_id", branch_id=branch_id))
        await request.app.state.auditor.record(
            "whatsapp.connect_failed", actor=getattr(principal, "subject", ""), tenant=tenant,
            resource=f"waba:{body.waba_id}", ip=ip)
        return JSONResponse(status_code=200, content={
            **attempt.public(),
            "message": "أنشأتَ الحساب ولم يُوثَّق رقمك بعد. وثّق الرقم في واتساب ثم أعد الربط."})

    # SEALED AGAINST THE SENDING IDENTITY, NOT THE TENANT. The platform treats this as an opaque
    # key — it never learns what a branch is — so a second number under the same establishment gets
    # its own credentials instead of overwriting the first shop-wide seal.
    # WRITE-AHEAD, BECAUSE THE SEAL IS THE POINT OF NO RETURN (ز-12). The exchange spends Meta's
    # code — thirty seconds of life, single use — and hands the platform credentials to store. A
    # crash between that call and the write below used to leave nothing here at all: the vault held
    # a working connection, every screen said «غير مربوط», and the code was gone, so no retry could
    # finish what had already succeeded. His only route was a support conversation.
    #
    # This row is the question, not the answer. `whatsapp_health` asks the platform — the only
    # party that knows — and settles it.
    await store.record(connect.Attempt(
        tenant=tenant, state=connect.STATE_EXCHANGING,
        waba_id=body.waba_id, phone_number_id=body.phone_number_id,
        business_id=body.business_id, branch_id=branch_id))

    ok, detail = await connect.build_exchange(s).exchange(
        tenant=identity, code=body.code, waba_id=body.waba_id,
        phone_number_id=body.phone_number_id, branch_id=branch_id,
        # THE BARE TENANT, SEPARATE FROM `identity` (2026-09-19) — `identity` stays the composite
        # notification-service's own secret store already keys on, unchanged; this is the one new
        # field WhatsAppNumberIndex's own `tenant` column needs, so the far side never has to
        # re-derive it by parsing our composite string.
        root_tenant=tenant)

    attempt = await store.record(connect.Attempt(
        tenant=tenant,
        state=connect.STATE_CONNECTED if ok else connect.STATE_FAILED,
        waba_id=body.waba_id, phone_number_id=body.phone_number_id,
        business_id=body.business_id, branch_id=branch_id,
        # KEPT AND NOT SHOWN. Support needs "Meta rejected the code" to tell it apart from "our app
        # secret is wrong"; the owner needs neither, and one of the two is about us.
        detail="" if ok else detail))
    await request.app.state.auditor.record(
        "whatsapp.connected" if ok else "whatsapp.connect_failed",
        actor=getattr(principal, "subject", ""), tenant=tenant,
        resource=f"waba:{body.waba_id}", ip=ip)

    if ok:
        # ── THE LIBRARY GOES UP HERE, AND THIS IS THE WHOLE POINT OF THE TASK ────────────────
        # An establishment used to finish this exact flow, be recorded `connected`, and own no
        # templates anywhere. Somebody had to run a script by hand for each new shop; until they
        # did, the send path had no approved template to pick and refused every message with a
        # sentence about a review nobody had asked for. Connected, green, and mute.
        #
        # AFTER THE RESPONSE, NOT INSIDE IT. Sixty-six upserts is not something an owner watches a
        # spinner through, and a failure here must not turn a SUCCESSFUL connection into an error
        # on his screen — the account IS connected, and that fact is already recorded and audited.
        # What can still go wrong is a slow or half-finished publish, and the hourly pass
        # (/internal/operations/templates/publish) is what covers it.
        from app.config import Settings
        from app.core.flows import provision_shop_flow
        from app.core.library import publish
        from app.core.runtime_config import RuntimeConfig
        from app.runtime_policy import RUNTIME_POLICY

        # RATING FLOW REMOVED (2026-09-16, [[task-service-procedure-checklists]] phase 2) — the
        # customer rating screen moved from a native WhatsApp Flow to a hosted web page (a link in
        # the template body/button instead), so there is no Flow left to clone at connect time.
        # REPORT FLOW ALSO REMOVED — its template was deleted 2026-09-13 (the owner's decision to
        # drop the weekly-digest feature entirely) but this clone-at-connect call was accidentally
        # left behind; found and removed alongside the rating Flow cleanup rather than repeating
        # that same incomplete-deletion mistake a second time.
        rc = RuntimeConfig(c.datastore, Settings, policy=RUNTIME_POLICY)
        # THE SAME CLONE-AT-CONNECT-TIME PATTERN, STILL — the WhatsApp booking Flow
        # (Phase 5, deploy/seed/bootstrap-booking-flow.sh). Its own master id, minted from
        # notification-service's own JSON generator (the definition is config-driven and shared
        # by every tenant, unlike rating/report's static per-file content) — an install that has
        # not run that script yet gets "no master booking_flow configured" from provision(), same
        # harmless after-the-response failure as an unconfigured rating/report Flow. This
        # provisions the Flow itself; the SEPARATE per-tenant encryption key it needs before it
        # can actually receive traffic is the next background task below.
        from app.core.flows import BOOKING_FLOW_CATEGORIES, BOOKING_FLOW_NAME
        master_booking_flow_id = await rc.get(
            tenant="", key="MASTER_BOOKING_FLOW_ID", default=s.MASTER_BOOKING_FLOW_ID)
        # THIS SHOP'S OWN CALLBACK URL — see PUBLIC_BASE_URL's own docstring (config.py) on why
        # only booking, among the three Flows here, needs one at all.
        booking_endpoint_uri = (f"{s.PUBLIC_BASE_URL}/webhooks/whatsapp/flow/{tenant}"
                                if s.PUBLIC_BASE_URL else "")
        background.add_task(provision_shop_flow, c.flows, tenant, master_booking_flow_id,
                            flow_name=BOOKING_FLOW_NAME, categories=BOOKING_FLOW_CATEGORIES,
                            endpoint_uri=booking_endpoint_uri)
        # SUBSCRIPTION RENEWAL IS DELIBERATELY NOT CLONED HERE (owner's decision, 2026-09-10) —
        # unlike rating/report/booking above, it is a PLATFORM-owned Flow (sent from OUR OWN
        # WhatsApp number to a shop owner about THEIR bill, same category as the `auth_otp`
        # template — see AdminWhatsAppTemplates.tsx's own note on the reserved `_platform`
        # tenant), authored ONCE on our own account, never per shop. See
        # app/api/v1/platform.py's `seed_subscription_renewal_flow` for where it is actually
        # minted (an explicit admin action, not a connect-time background task) and
        # app/adapters/renewal_provider.py for how one Flow instance still answers every shop's
        # own invoice (tenant carried inside the Flow's own seed data, not the connect URL).
        # THE FLOW'S OTHER HALF — a sealed per-tenant encryption key and its public half
        # registered with Meta (base-services v0.18.55). No longer escalated: this closes the
        # one gap that was genuinely outside our hands. Idempotent on notification-service's own
        # side (never regenerates an existing key), so running it on every connect is safe —
        # including a reconnect, or a shop adding a second number later.
        from app.core.flows import provision_shop_flow_encryption
        background.add_task(provision_shop_flow_encryption, c.flows, tenant)
        background.add_task(publish, c.library, await c.templates.list(), tenant)
        # Meta Business Agent full onboarding (eligibility -> create agent -> Connector/tools ->
        # Skill -> Knowledge -> enable) — same after-the-response, never-fails-the-connection
        # posture as the three tasks above. `body.phone_number_id` is the SAME entity_id
        # knowledge_export.py already uses, fresh from this exact Embedded Signup exchange — see
        # meta_agent_provisioning.py's own docstring for why that matters (no other place in the
        # code derives a tenant's phone_number_id after the fact).
        #
        # CORRECTED, 2026-09-20 (the owner caught a real bug in the reasoning below, since fixed):
        # this route used to be gated `Depends(subscribed_write_or_whatsapp)`, which made this
        # comment's claim ("already scoped to feature.whatsapp, no separate check needed") true
        # — but that gate was ITSELF wrong: this file's own header docstring says connecting
        # "happens BEFORE a paid subscription... and during a trial when there is no subscription
        # at all", which the `subscribed_write_or_whatsapp` dependency directly contradicted. The
        # route is now `Depends(no_subscription_needed)`, matching that stated intent — so a
        # shop with ZERO subscriptions can connect a number. That means THIS check is no longer
        # redundant: it is the ONLY place left that keeps Meta provisioning scoped to shops who
        # actually hold بوت خدمة العملاء الذكي (feature.whatsapp) — the app this whole sequence
        # exists to replace. `False`/`None` (could not ask) both fail closed, same posture every
        # `subscribed_write_or` gate in this product already holds.
        if await c.whatsapp_licence.allowed(tenant):
            background.add_task(c.meta_agent_provision_trigger.trigger,
                                tenant=tenant, entity_id=body.phone_number_id)
        # Meta Commerce Catalog provisioning (WhatsApp Direct Ordering) — same after-the-response,
        # never-fails-the-connection posture, fired unconditionally on every successful connect
        # (not gated on feature.whatsapp licence like the Business Agent trigger above, since
        # ordering is not sold as part of that app): `catalog_provisioning.py::provision_catalog`
        # is idempotent (reuses an existing catalog rather than minting a second one), so a
        # reconnect or a second branch number is always safe to re-trigger.
        background.add_task(_provision_catalog_and_backfill, c, tenant=tenant,
                            business_id=body.business_id, waba_id=body.waba_id,
                            phone_number_id=body.phone_number_id)
    # THE SENTENCE AT THE END OF THE JOURNEY, and the one that used to promise sending. See
    # core/connect.py `sentence_for`: the connection is his, the sending is ours, and until the
    # second is open the screen says so rather than sending him off to wait for messages that
    # cannot leave.
    return attempt.public(can_send=await _can_send(identity, attempt))


async def _can_send(identity: str, attempt) -> bool:
    """Can a message actually leave — the ONE answer both doors give (د-16).

    `identity` IS THE SENDING IDENTITY (`tenant` or `tenant:branch`), NEVER THE BARE TENANT — the
    credential Meta's registration status is read against is sealed under that composite key
    (`connect.py`'s own note on `/connect/register`: "THE SEAL IS KEYED BY THE SENDING IDENTITY").
    Both call sites used to pass the bare tenant here even for a branch's own connection, which
    would have asked Meta about the ESTABLISHMENT's number while reporting on a BRANCH's — the
    exact "connected, green, and mute" defect this function exists to prevent, just one door over.

    THE DEFECT WAS TWO ANSWERS. The GET computed this properly; the POST returned
    `SIGNUP_OTP_DELIVERABLE` alone. And the screen reads the POST first — `Connect.tsx`
    renders the whole PIN form behind `connected && can_send === false` — so the moment the
    flag was raised the owner read «جاهز للإرسال», the code field never appeared at all, and
    every message bounced 133010 because his number was never registered. Green and mute,
    with no way forward on the screen.

    TWO FACTS, AND BOTH MUST BE TRUE.

    1. OUR CHANNEL IS OPEN — the same flag the signup path obeys, flipped in the same change
       that points WhatsApp at Meta, with a guard that fails the build if the two disagree.
    2. HIS NUMBER IS REGISTERED — read live from Meta (v0.16.10). A token exchange
       succeeding means Meta gave us credentials; it does not mean the number may send, and
       assuming it is exactly how a shop ends up «مربوط» and mute.

    AND «WE COULD NOT ASK» IS NOT «NOT READY». An unreadable status leaves the answer to the
    deployment flag alone rather than telling him his number is unverified — a screen that
    invents a fault sends him chasing one.
    """
    s = get_settings()
    channel_open = bool(s.SIGNUP_OTP_DELIVERABLE)
    if not channel_open or attempt.state != connect.STATE_CONNECTED:
        return channel_open
    live = await connect.build_registration(s).status(identity, attempt.phone_number_id)
    verified = str(live.get("code_verification_status") or "").upper()
    return verified in ("VERIFIED", "EXPIRED_VERIFIED") if verified else channel_open


async def _provision_catalog_and_backfill(c: Any, *, tenant: str, business_id: str, waba_id: str,
                                          phone_number_id: str) -> None:
    """Step 1 (catalog provisioning), then — ONLY once it actually succeeds — Step 2's own
    backfill for every service this tenant already has.

    THE REAL CASE THIS CLOSES: a shop that built a full priced-and-photographed catalogue BEFORE
    ever connecting WhatsApp must not sit with an empty Meta catalog until someone happens to edit
    each service again. `catalog_item_sync_trigger.sync`'s own call on create/update/image-upload
    only ever reaches services touched AFTER a connect — this is the one pass that reaches
    everything that already existed.

    ONE BACKGROUND TASK, NOT TWO — chaining them here (rather than two separate
    `background.add_task` calls) is what makes "only backfill if provisioning actually worked"
    possible at all; two independent tasks have no way to see each other's result."""
    from app.core.stores import ServiceStore

    provisioned = await c.catalog_provision_trigger.trigger(
        tenant=tenant, business_id=business_id, waba_id=waba_id, phone_number_id=phone_number_id)
    if not provisioned:
        return
    services = await ServiceStore(c.datastore).list(tenant, active_only=False)
    await c.catalog_item_sync_trigger.backfill(tenant=tenant, services=services)


@router.get("/connect", dependencies=[Depends(rate_limit)])
async def whatsapp_connect_status(request: Request, branch_id: str = "",
                                  principal=Depends(_OWNER)) -> Any:
    """Where this establishment — or, in per_branch mode, this ONE BRANCH — stands. The screen
    reads it after the popup closes, and support reads it when an owner says nothing happened.

    `branch_id` WAS ACCEPTED EVERYWHERE ELSE AND NOWHERE HERE. `ConnectionStore.get` already takes
    it, the POST routes already resolve it — this was the one door that could not answer "is THIS
    branch's number connected", so a chain's second branch always read its OWN status as the
    establishment's (or as unconnected, once a central attempt existed under the bare tenant key).

    FOUND BY THE GATE (ci/check_branch_scope.py): unlike every other branch-scoped read in this
    service, `branch_id` here was taken from the caller and used as-is — a manager scoped to one
    branch could pass ANY OTHER branch's id and read whether ITS number is connected and able to
    send. Scoped the same way as `recent_customers`/`list_operators`: `branch_scope` says what
    this caller may see, and a request outside it is answered as if nothing had been requested —
    his own scope, never a 403 — same "not an accusation" reasoning as every other narrowed read.
    """
    tenant = getattr(principal, "tenant", "") or ""
    c = request.app.state.container
    scope = await branch_scope(c.datastore, principal)
    if scope is REVOKED:
        return {"state": "", "step": "", "message": "لم تبدأ الربط بعد.", "at": 0,
               "can_send": False}
    narrowed = SCOPE.narrow(scope, branch_id)
    resolved_branch_id = branch_id if narrowed == branch_id else ""
    identity = await SI.resolve(c.datastore, tenant, resolved_branch_id)
    resolved_branch = SI.split(identity)[1]
    attempt = await connect.ConnectionStore(c.datastore).get(tenant, resolved_branch)
    if attempt is None:
        return {"state": "", "step": "", "message": "لم تبدأ الربط بعد.", "at": 0,
                "can_send": False}
    # ── CAN A MESSAGE ACTUALLY LEAVE? TWO FACTS, AND BOTH MUST BE TRUE ────────────────────────
    #
    # 1. OUR CHANNEL IS OPEN — the same flag the signup path obeys, flipped in the same change that
    #    points WhatsApp at Meta, with a guard that fails the build if the two disagree.
    # 2. HIS NUMBER IS REGISTERED — read live from Meta (v0.16.10). A token exchange succeeding
    #    means Meta gave us credentials; it does not mean the number may send, and assuming it is
    #    exactly how a shop ends up «مربوط» and mute.
    #
    # AND «WE COULD NOT ASK» IS NOT «NOT READY». An unreadable status leaves the answer to the
    # deployment flag alone rather than telling him his number is unverified — a screen that
    # invents a fault sends him chasing one.
    return attempt.public(can_send=await _can_send(identity, attempt))


@router.get("/config", dependencies=[Depends(rate_limit)])
async def whatsapp_meta_config(request: Request, principal=Depends(_OWNER)) -> Any:
    """What the console needs to even OPEN the Embedded Signup popup — the App ID and Facebook
    Login Config ID, read live from notification-service's own sealed values, never a copy held
    here. NOT SECRET (see `HttpMetaConfig`'s own docstring) — gated on `billing.self` anyway,
    same "every console call authenticates" convention as `/connect`/`/connect/register` right
    beside it, even though nothing in the response could not already be read from the browser's
    own network tab during a real popup open.

    `configured: false` for EVERY reason it could be unset or unreachable — never a distinct
    error shape, so the console's one "عُطلٌ من عندنا" sentence covers all of them honestly.
    """
    s = get_settings()
    out = await connect.build_meta_config(s).read()
    return {
        "app_id": str(out.get("app_id") or ""),
        "config_id": str(out.get("config_id") or ""),
        "graph_version": str(out.get("graph_version") or ""),
        "configured": bool(out.get("configured")),
    }


class RegisterIn(BaseModel):
    """The 6-digit PIN, and which number it is for."""

    # SHAPE-CHECKED HERE, BEFORE IT TRAVELS. Meta locks a number after 10 registration attempts in
    # 72 hours, and a malformed PIN must never spend one of them.
    pin: str = Field(pattern=r"^[0-9]{6}$")
    # Empty is the establishment's own number — every shop in the default mode.
    branch_id: str = Field(default="", max_length=64)


# The three refusals Meta distinguishes, in the owner's language. Each says what to DO, and the
# middle one says what NOT to do: retrying inside the lock spends attempts on a wait.
_REGISTER_SENTENCE = {
    "WRONG_PIN": "الرمز غير صحيح. أدخل رمز التحقق بخطوتين (6 أرقام) الخاص بحساب واتساب أعمالك.",
    "RATE_LIMITED": "حاولنا كثيراً وقفلت واتساب المحاولات 72 ساعة. لا تعِد المحاولة الآن — "
                    "انتظر ثم أدخل الرمز مرة واحدة.",
    "NO_PIN": "أدخل رمز التحقق بخطوتين (6 أرقام).",
    "NOT_CONNECTED": "أكمل ربط واتساب أولاً — لا يوجد حساب مرتبط بهذا الرقم بعد.",
    "NOT_CONFIGURED": "تفعيل الإرسال غير مُهيَّأ لدينا بعد — عُطلٌ عندنا لا في حسابك.",
}
_REGISTER_FALLBACK = "تعذّر تفعيل الإرسال الآن. حاول بعد قليل، ولا تكرّر المحاولة كثيراً."


@router.post("/connect/register", dependencies=[Depends(no_subscription_needed), Depends(rate_limit)])
async def whatsapp_register(request: Request, body: RegisterIn,
                            principal=Depends(_OWNER)) -> Any:
    """Finish the connection: register the number so it can actually send.

    WHY IT IS A SEPARATE ACT AND NOT PART OF THE POPUP. The PIN is the business's own two-step
    verification code — we do not have it and must never invent one. Embedded Signup returns a
    token in about thirty seconds and cannot pause for a person to fetch a PIN, so the connection
    is stored first and this completes it. That also makes it RETRYABLE: a number whose
    registration failed is not lost, which was the whole trap before.

    RETURNED, NEVER RAISED — the platform strips a raised detail, and every sentence here is one
    the owner must be able to read and act on.
    """
    tenant = getattr(principal, "tenant", "") or ""
    if not tenant:
        return JSONResponse(status_code=403,
                            content={"message": "لا توجد منشأة في هذه الجلسة."})

    c = request.app.state.container
    s = get_settings()
    store = connect.ConnectionStore(c.datastore)

    # SAME VALIDATION AS `/connect` ABOVE (fixed 2026-09-12) — otherwise a caller could register a
    # PIN against a `tenant:branch` identity for a branch that does not exist.
    validated_branch_id = await B.resolve(BranchStore(c.datastore), tenant, body.branch_id)
    identity = await SI.resolve(c.datastore, tenant, validated_branch_id)
    branch_id = SI.split(identity)[1]
    attempt = await store.get(tenant, branch_id)
    if attempt is None or attempt.state != connect.STATE_CONNECTED:
        return JSONResponse(status_code=400, content={
            "registered": False, "message": _REGISTER_SENTENCE["NOT_CONNECTED"]})

    ok, reason = await connect.build_registration(s).register(
        # THE SEAL IS KEYED BY THE SENDING IDENTITY, exactly as the credentials are — so a chain's
        # second number registers on its own rather than over the first.
        tenant=identity, phone_number_id=attempt.phone_number_id, pin=body.pin)

    await request.app.state.auditor.record(
        "whatsapp.number_registered" if ok else "whatsapp.register_failed",
        actor=getattr(principal, "subject", ""), tenant=tenant,
        resource=f"phone:{attempt.phone_number_id}",
        ip=request.client.host if request.client else "")

    if ok:
        return {"registered": True,
                "message": "تم تفعيل الإرسال. رقمك جاهز الآن."}
    return JSONResponse(status_code=400, content={
        "registered": False,
        "message": _REGISTER_SENTENCE.get(reason.split(":")[0], _REGISTER_FALLBACK)})


# ── ONE FLOW'S REAL SCREENS, FOR «رسائلي»'s OWN PREVIEW (not the platform-admin one — that lives
# at platform.py::whatsapp_flow_json, gated by `platform.operations`) ─────────────────────────────
#
# ANY SIGNED-IN STAFF MEMBER, NOT JUST THE OWNER. `_OWNER` above is right for connecting the
# shop's own WhatsApp number — a real financial/security act. Looking at what a template's Flow
# looks like is a read with no side effect, so it takes the same broad `operations.read`
# every other shop-facing screen read already uses (see `user_actions.py`'s own routes).
#
# NOT TENANT-SCOPED, AND DELIBERATELY. The engine's screens (their Arabic text, their fields) come
# from the platform's own `FlowDefinition` config — identical for every shop that has that Flow
# cloned, never shop-specific content. Scoping this by tenant would ask for a distinction that does
# not exist and could never be answered differently per shop.
_READ = require_capability("operations.read")


@router.get("/flow-json", dependencies=[Depends(rate_limit)])
async def shop_whatsapp_flow_json(request: Request, name: str,
                                  principal: Principal = Depends(_READ)) -> Any:
    """Same read as `platform.py::whatsapp_flow_json`, reachable from the shop's own console
    (`رسائلي`) rather than the admin panel — see `WhatsAppDiagnostics.flow_json`'s own docstring."""
    desk = request.app.state.container.whatsapp_diagnostics
    status, out = await desk.flow_json(name)
    if status != 200:
        return JSONResponse(out, status_code=status)
    return out
