"""The sending caps — ours, not an establishment's.

WHY THIS IS NOT AN OWNER'S SCREEN. The caps in spec 8.4.2 look like a per-shop preference and are
not one. A customer who is annoyed blocks the NUMBER, and a blocked number lowers the quality
rating Meta assigns to every number on the product. So the cost of one establishment's decision is
paid by establishments that did not make it — which is the definition of a decision that does not
belong to them.

An owner who genuinely needs a higher limit is a real case, and it is answered here, by us, with a
written reason in the audit log. Not by a switch on their settings page.

THE GUARD IS WHY THIS FILE EXISTS AT ALL. `platform.reminders` was advertised in the manifest and
enforced by nothing — an operator could have been granted it, believed it opened something, and it
opened nothing. That is exactly the class of defect the deploy-wiring guard was written for, and
it found this one before a human did.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.api.auth import Principal
from app.api.authz import require_capability
from app.api.ratelimit import rate_limit

router = APIRouter(prefix="/platform", tags=["platform"])

_PLATFORM = require_capability("platform.reminders")

LIMITS_COLLECTION = "limits"
# Overrides live under a reserved tenant, the same pattern as operations' template
# tables. One row per establishment, plus one row keyed "_global" that is the product default.
PLATFORM_TENANT = "_platform"
GLOBAL_KEY = "_global"


class LimitsIn(BaseModel):
    # BOUNDED AT THE MODEL, and the ceilings are the same ones the boot guard enforces. A limit
    # that can be set to 999 through an API is not a limit — and a cap raised past the point where
    # the regulator's window matters is a compliance failure expressed as a configuration change.
    daily_service_cap: int = Field(ge=1, le=3)
    daily_total_cap: int = Field(ge=1, le=5)
    monthly_marketing_cap: int = Field(ge=1, le=12)
    monthly_awareness_cap: int = Field(ge=0, le=4)
    marketing_cooldown_hours: int = Field(ge=12, le=720)
    # NOT SETTABLE HERE: the sending window. It is regulatory, not commercial — 10pm to 7am is
    # decided by the CST and not by us or by a customer paying more (spec 8.6). Exposing it as a
    # number in this model would invite exactly the request we must refuse, and the refusal is
    # cleaner as an absence than as a validation error.
    reason: str = Field(min_length=10, max_length=500)


@router.get("/limits", dependencies=[Depends(rate_limit)])
async def get_limits(request: Request, tenant: str = "",
                     principal: Principal = Depends(_PLATFORM)) -> dict:
    """The caps in force — globally, or for one establishment.

    Returns the DEFAULTS alongside any override, so an operator can see what they are deviating
    from. A screen that shows only the current value makes every number look deliberate.
    """
    from app.config import get_settings
    s = get_settings()
    store = request.app.state.container.datastore
    key = f"{PLATFORM_TENANT}|{tenant or GLOBAL_KEY}"
    override = await store.get(LIMITS_COLLECTION, key)
    return {
        "scope": tenant or GLOBAL_KEY,
        "defaults": {
            "daily_service_cap": s.DAILY_SERVICE_CAP,
            "daily_total_cap": s.DAILY_TOTAL_CAP,
            "monthly_marketing_cap": s.MONTHLY_MARKETING_CAP,
            "monthly_awareness_cap": s.MONTHLY_AWARENESS_CAP,
            "marketing_cooldown_hours": s.MARKETING_COOLDOWN_HOURS,
        },
        "window": {"start_hour": s.SEND_WINDOW_START_HOUR, "end_hour": s.SEND_WINDOW_END_HOUR,
                   "settable": False,
                   "why": "أوقات المنع نظامية تحدّدها هيئة الاتصالات، لا نملك تعديلها ولا يملكه "
                          "المشترك مهما دفع."},
        "override": override,
    }


@router.put("/limits", dependencies=[Depends(rate_limit)])
async def set_limits(request: Request, body: LimitsIn, tenant: str = "",
                     principal: Principal = Depends(_PLATFORM)) -> dict:
    """Raise or lower the caps, globally or for one establishment.

    THE REASON IS REQUIRED AND IS NOT DECORATION. Six months from now somebody will find a tenant
    with double the marketing allowance and no way to tell whether it was a considered exception
    for a high-volume shop or a mistake nobody noticed — and the safe response to an unexplained
    permission is always to remove it, which breaks the shop that legitimately needed it.
    """
    store = request.app.state.container.datastore
    scope = tenant or GLOBAL_KEY
    # Recorded BEFORE the write, and critical. This is the one edit on this service whose cost
    # lands on people who did not make it.
    await request.app.state.auditor.record(
        "reminders.limits_changed", actor=principal.subject, tenant=tenant,
        resource=f"sending_limits:{scope}", ip=request.client.host if request.client else "")
    row = body.model_dump()
    row["id"] = scope
    row["tenant"] = PLATFORM_TENANT
    row["scope"] = scope
    row["actor"] = principal.subject
    await store.put(LIMITS_COLLECTION, f"{PLATFORM_TENANT}|{scope}", row)
    return {"scope": scope, "limits": row,
            "note": "يسري على الرسائل القادمة. النافذة الزمنية لا تتغيّر — نظامية."}


@router.delete("/limits", dependencies=[Depends(rate_limit)])
async def clear_limits(request: Request, tenant: str = "",
                       principal: Principal = Depends(_PLATFORM)) -> dict:
    """Remove an override and fall back to the product default.

    Deleted rather than deactivated — the opposite of the template library, and for a reason: this
    row is not content anyone references by name, and a retired override that still exists is a
    permission somebody will eventually re-enable by accident.
    """
    if not tenant:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "the global defaults come from configuration and cannot be deleted")
    await request.app.state.auditor.record(
        "reminders.limits_changed", actor=principal.subject, tenant=tenant,
        resource=f"sending_limits:{tenant}", ip=request.client.host if request.client else "")
    await request.app.state.container.datastore.delete(
        LIMITS_COLLECTION, f"{PLATFORM_TENANT}|{tenant}")
    return {"scope": tenant, "cleared": True}


@router.get("/silent", dependencies=[Depends(rate_limit)])
async def silent_shops(request: Request, limit: int = 200,
                       principal: Principal = Depends(_PLATFORM)) -> dict:
    """Establishments with messages queued that CANNOT send — ours, for the panel.

    THE OUTAGE THIS EXISTS FOR HAPPENED, AND NOBODY KNEW. A shop whose establishment name cannot be
    read is skipped whole by the tick — before the send log, before any refusal is recorded — so
    the owner's screens showed a calm zero and our panel showed nothing at all. Real visits were
    recorded for a day against an engine that was never going to send.

    A DAILY TOTAL OF SENDS IS NOT A MONITOR. "0 sent today" is also what a quiet Friday looks like;
    the alarm is the CONJUNCTION — work waiting, and a reason it cannot move. That is what this
    returns, one row per shop, with the reason named.

    READ-ONLY AND CHEAP. It walks pending schedules, which is the same read the tick starts from,
    and asks identity for each distinct tenant — a cached call per tenant per five minutes.
    """
    c = request.app.state.container
    rows, _ = await c.datastore.find("schedules", {"state": "pending"},
                                     limit=max(1, min(limit, 2000)), sort=("due_at", "asc"))
    waiting: dict[str, int] = {}
    for r in rows:
        t = str(r.get("tenant") or "")
        if t:
            waiting[t] = waiting.get(t, 0) + 1

    stuck = []
    for tenant, count in waiting.items():
        shop = await c.identity.get(tenant)
        if shop.usable:
            continue
        stuck.append({
            "tenant": tenant,
            "waiting": count,
            # THE SAME SENTENCE THE OWNER SEES. Support and the owner reading two different
            # descriptions of one fault is how a five-minute call becomes an hour.
            "reason": "اسم المنشأة غير مقروء — لا تخرج أي رسالة",
        })

    stuck.sort(key=lambda x: -int(x["waiting"]))
    return {"stuck": stuck, "count": len(stuck), "tenants_with_work": len(waiting)}


class AnswerIn(BaseModel):
    """What we tell him. One field, because that is the whole of the interaction."""

    tenant: str = Field(min_length=1, max_length=64)
    answer: str = Field(min_length=2, max_length=1200)


@router.get("/template-help", dependencies=[Depends(_PLATFORM)])
async def template_help_queue(request: Request, status: str = "open") -> dict:
    """Every «ساعدوني» waiting on us — the other end of the button.

    A QUEUE NOBODY CAN SEE IS A BUTTON THAT DOES NOTHING, which is the failure this product keeps
    finding: the owner presses, a row is written, and it waits in a collection no screen reads. He
    hears nothing, presses again, and concludes the feature is decoration.

    NEWEST FIRST AND OPEN BY DEFAULT — the two decisions that make it a work queue rather than a
    log. Answered rows stay readable (`?status=`) because the next shop refused for the same Meta
    rule is answered from one we already wrote.
    """
    from app.core.help_requests import HelpRequestStore
    rows = await HelpRequestStore(request.app.state.container.datastore).list(status=status)
    return {"requests": rows, "count": len(rows)}


@router.post("/template-help/{name}/answer", dependencies=[Depends(_PLATFORM)])
async def answer_template_help(request: Request, name: str, body: AnswerIn) -> dict:
    """Answer one, and close it. The answer goes back to the screen he asked from.

    NOT A SUPPORT CHANNEL. A reply that lives only in WhatsApp is one he reads once and cannot find
    the day he sits down to fix the text — and by then the refusal, his draft and our answer are in
    three different places.
    """
    from app.core.help_requests import HelpRequestError, HelpRequestStore
    try:
        row = await HelpRequestStore(request.app.state.container.datastore).answer(
            body.tenant, name, answer=body.answer)
    except HelpRequestError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    await request.app.state.auditor.record(
        "reminders.rule_changed", actor="platform", tenant=body.tenant,
        resource=f"template_help:{name}", ip=request.client.host if request.client else "")
    return {"ok": True, "request": row}
