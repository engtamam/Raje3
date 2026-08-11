"""The owner's subscribe path — ours, so a product rule has somewhere to live.

    POST /api/v1/subscription     subscribe this establishment to a plan

WHY NOT CALL BILLING DIRECTLY, which is what happened before this file: because there was then no
moment that belonged to us. billing-service is the platform's, shared by every product built on
it, and it must never learn that ours requires WhatsApp before it will take money.

So this is thin on purpose — one question, then their route, then their answer. It holds no plan,
prices nothing, and stores no subscription. Everything about money stays where it already works.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.api.authz import require_capability
from app.config import get_settings
from app.core.subscribe import may_subscribe
from app.api.ratelimit import rate_limit

# The parent router in __init__ already carries /api/v1.
router = APIRouter(prefix="/subscription", tags=["subscription"])

# THE OWNER'S OWN CAPABILITY, not an operator's. He is buying his own subscription, and requiring
# a platform capability here would mean nobody could subscribe without us.
_OWNER = require_capability("billing.self")


class SubscribeIn(BaseModel):
    plan_id: str = Field(min_length=1, max_length=64)
    # `once` for a one-time purchase, `month` otherwise. Passed through rather than inferred: the
    # plan's PRICE carries an interval but the SUBSCRIPTION takes its own, and defaulting it here
    # would repeat the bug that made a pack renew monthly.
    interval: str = Field(default="month", max_length=16)
    # WHAT THE GATEWAY'S FORM HANDED THE BROWSER — a single-use reference to a card we never see.
    # Absent on a trial, required on anything paid: see may_subscribe.
    payment_token: str = Field(default="", max_length=256)


def _tenant(p) -> str:
    return getattr(p, "tenant", "") or ""


@router.get("/payment", dependencies=[Depends(rate_limit)])
async def payment_state(principal=Depends(_OWNER)) -> dict:
    """Is there a live way to pay — and what does the screen need in order to offer it?

    THE SCREEN MUST NOT GUESS. Until this existed the plans page assumed payment worked, so with no
    gateway configured every press wrote «باقتك» over the last one and no riyal moved. A product
    that hands out its paid tiers to whoever presses hardest is not generous; it is broken, and the
    first shop to notice tells the second.

    AND IT FLIPS BY ITSELF. One key decides: absent, the screen apologises and sells nothing;
    present, the card form appears and a subscription waits for a real charge. Nobody edits code
    on the day we sign with a provider — the key goes in the secret and the product starts selling.

    THE PUBLISHABLE KEY IS MEANT TO BE READ BY A BROWSER — it can mint a single-use token and do
    nothing else. The secret key lives in billing-service and appears in no response, ever.
    """
    cfg = get_settings()
    key = (cfg.PAYMENT_PUBLISHABLE_KEY or "").strip()
    return {"enabled": bool(key), "provider": cfg.PAYMENT_PROVIDER if key else "",
            "publishable_key": key,
            "message": "" if key else
                       "الدفع الإلكتروني غير متاح مؤقتاً. نعتذر — نعمل على تفعيله، "
                       "وحتى ذلك الحين تواصل معنا لتفعيل باقتك."}


@router.post("", dependencies=[Depends(rate_limit)])
async def subscribe(request: Request, body: SubscribeIn,
                    principal=Depends(_OWNER)) -> JSONResponse:
    """Subscribe, once the one rule that is ours has been satisfied."""
    c = request.app.state.container
    tenant = _tenant(principal)
    if not tenant:
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN,
                            content={"error": "NO_TENANT"})

    # THE PLAN'S TRIAL DECIDES WHETHER THE RULE APPLIES, so it is read before the check rather
    # than assumed. A plan with a trial is an evaluation and needs no connection.
    trial_days = await c.billing_plans.trial_days(body.plan_id)
    connected = await c.connections.connected(tenant)

    # PAID MEANS A TOKEN WE CAN ACTUALLY CHARGE. An empty one is not "pay later"; it is the press
    # of a button with no money behind it, and the plan must not start on it.
    decision = may_subscribe(connected=connected, trial_days=trial_days,
                             paid=bool(body.payment_token))
    if not decision.allowed:
        # RETURNED, NEVER RAISED. The platform's error handler strips an HTTPException's detail,
        # so a raised refusal arrives as a bare 402 and the sentence telling him what to do — the
        # only useful part — is thrown away.
        await request.app.state.auditor.record(
            "subscription.refused", actor=principal.subject, tenant=tenant,
            resource=f"plan:{body.plan_id}",
            ip=request.client.host if request.client else "")
        return JSONResponse(status_code=status.HTTP_402_PAYMENT_REQUIRED,
                            content={"error": "PAYMENT_REQUIRED",
                                     "message": decision.reason})

    status_code, out = await c.billing_plans.subscribe(
        tenant=tenant, plan_id=body.plan_id, interval=body.interval,
        payment_token=body.payment_token)
    if status_code >= 400:
        # BILLING'S REFUSAL IS BILLING'S. We do not translate it into a sentence of our own — an
        # invented explanation for somebody else's decision is how support ends up answering for a
        # rule that does not exist.
        return JSONResponse(status_code=status_code,
                            content={"error": "BILLING_REFUSED", "detail": out})

    await request.app.state.auditor.record(
        "subscription.created", actor=principal.subject, tenant=tenant,
        resource=f"plan:{body.plan_id}", ip=request.client.host if request.client else "")
    # WHAT IS STILL OWED, ALONGSIDE THE RECEIPT. He may subscribe unconnected — see
    # core/subscribe.py for why that gate was removed — but he must never learn it from the
    # absence of messages a week later. The notice travels with the success, not instead of it.
    if decision.notice:
        out = {**out, "notice": decision.notice}
    return JSONResponse(status_code=status.HTTP_201_CREATED, content=out)
