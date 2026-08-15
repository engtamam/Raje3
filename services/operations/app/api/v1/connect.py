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


@router.post("/connect", dependencies=[Depends(rate_limit)])
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

    if (body.event or "").upper() == "CANCEL":
        state = connect.classify_cancel(body.step)
        attempt = await store.record(connect.Attempt(
            tenant=tenant, state=state, step=(body.step or "").upper()))
        await request.app.state.auditor.record(
            "whatsapp.connect_stopped", actor=getattr(principal, "subject", ""), tenant=tenant,
            resource="whatsapp_connection", ip=ip)
        return attempt.public()

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
            detail="finish carried no phone_number_id"))
        await request.app.state.auditor.record(
            "whatsapp.connect_failed", actor=getattr(principal, "subject", ""), tenant=tenant,
            resource=f"waba:{body.waba_id}", ip=ip)
        return JSONResponse(status_code=200, content={
            **attempt.public(),
            "message": "أنشأتَ الحساب ولم يُوثَّق رقمك بعد. وثّق الرقم في واتساب ثم أعد الربط."})

    ok, detail = await connect.build_exchange(s).exchange(
        tenant=tenant, code=body.code, waba_id=body.waba_id,
        phone_number_id=body.phone_number_id)

    attempt = await store.record(connect.Attempt(
        tenant=tenant,
        state=connect.STATE_CONNECTED if ok else connect.STATE_FAILED,
        waba_id=body.waba_id, phone_number_id=body.phone_number_id,
        business_id=body.business_id,
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
    return attempt.public()


@router.get("/connect", dependencies=[Depends(rate_limit)])
async def whatsapp_connect_status(request: Request, principal=Depends(_OWNER)) -> Any:
    """Where this establishment stands. The screen reads it after the popup closes, and support
    reads it when an owner says nothing happened."""
    tenant = getattr(principal, "tenant", "") or ""
    attempt = await connect.ConnectionStore(request.app.state.container.datastore).get(tenant)
    if attempt is None:
        return {"state": "", "step": "", "message": "لم تبدأ الربط بعد.", "at": 0}
    return attempt.public()
