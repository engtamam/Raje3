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


def _tenant(p) -> str:
    return getattr(p, "tenant", "") or ""


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

    decision = may_subscribe(connected=connected, trial_days=trial_days)
    if not decision.allowed:
        # RETURNED, NEVER RAISED. The platform's error handler strips an HTTPException's detail,
        # so a raised refusal arrives as a bare 402 and the sentence telling him what to do — the
        # only useful part — is thrown away.
        await request.app.state.auditor.record(
            "subscription.refused", actor=principal.subject, tenant=tenant,
            resource=f"plan:{body.plan_id}",
            ip=request.client.host if request.client else "")
        return JSONResponse(status_code=status.HTTP_402_PAYMENT_REQUIRED,
                            content={"error": "WHATSAPP_NOT_CONNECTED",
                                     "message": decision.reason})

    status_code, out = await c.billing_plans.subscribe(
        tenant=tenant, plan_id=body.plan_id, interval=body.interval)
    if status_code >= 400:
        # BILLING'S REFUSAL IS BILLING'S. We do not translate it into a sentence of our own — an
        # invented explanation for somebody else's decision is how support ends up answering for a
        # rule that does not exist.
        return JSONResponse(status_code=status_code,
                            content={"error": "BILLING_REFUSED", "detail": out})

    await request.app.state.auditor.record(
        "subscription.created", actor=principal.subject, tenant=tenant,
        resource=f"plan:{body.plan_id}", ip=request.client.host if request.client else "")
    return JSONResponse(status_code=status.HTTP_201_CREATED, content=out)
