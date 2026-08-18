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
from app.config import get_settings
from app.core import connect
from app.core import sending_identity as SI
from app.api.subscribed import no_subscription_needed, subscribed_write

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


@router.post("/connect", dependencies=[Depends(subscribed_write), Depends(rate_limit)])
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
    # RESOLVED ONCE, HERE. The branch is dropped for a central shop in that one function, so the
    # row, the seal and the screen cannot disagree about which number this is.
    identity = await SI.resolve(c.datastore, tenant, body.branch_id)
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
        return attempt.public(can_send=await _can_send(tenant, attempt))

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
        phone_number_id=body.phone_number_id)

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
        from app.core.library import publish

        background.add_task(publish, c.library, await c.templates.list(), tenant)
    # THE SENTENCE AT THE END OF THE JOURNEY, and the one that used to promise sending. See
    # core/connect.py `sentence_for`: the connection is his, the sending is ours, and until the
    # second is open the screen says so rather than sending him off to wait for messages that
    # cannot leave.
    return attempt.public(can_send=await _can_send(tenant, attempt))


async def _can_send(tenant: str, attempt) -> bool:
    """Can a message actually leave — the ONE answer both doors give (د-16).

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
    live = await connect.build_registration(s).status(tenant, attempt.phone_number_id)
    verified = str(live.get("code_verification_status") or "").upper()
    return verified in ("VERIFIED", "EXPIRED_VERIFIED") if verified else channel_open


@router.get("/connect", dependencies=[Depends(rate_limit)])
async def whatsapp_connect_status(request: Request, principal=Depends(_OWNER)) -> Any:
    """Where this establishment stands. The screen reads it after the popup closes, and support
    reads it when an owner says nothing happened."""
    tenant = getattr(principal, "tenant", "") or ""
    attempt = await connect.ConnectionStore(request.app.state.container.datastore).get(tenant)
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
    return attempt.public(can_send=await _can_send(tenant, attempt))


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


@router.post("/connect/register", dependencies=[Depends(subscribed_write), Depends(rate_limit)])
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

    identity = await SI.resolve(c.datastore, tenant, body.branch_id)
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
