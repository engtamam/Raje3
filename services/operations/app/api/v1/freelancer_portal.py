"""The freelancer's OWN screen — docs/جديد.txt §"ثانياً: مساحة عمل المستقل". `core/
freelancer_crm.py` owns the design; this file is only the HTTP door.

TWO CAPABILITIES CAN REACH THIS FILE, ON PURPOSE (docs/جديد.txt §5 "واجهة التشغيل الداخلي" — a
shop's own owner/manager/marketer/supervisor gets a tab inside the console that is IDENTICAL to
the freelancer's own screen, same `mobile_requests.py`-style "two capabilities, one engine" shape):

  * `operations.freelancer_portal` — the ONE capability a freelancer's own token ever carries
    (minted from `core/freelancer_service.py`'s own link table, never from `roles.json` — see
    that module's own docstring). A freelancer reaches ONLY this file, never
    `api/v1/freelancers.py`.
  * `operations.freelancer_manage` — a shop's own internal staff, using the SAME actions from
    inside the console's own "التشغيل الداخلي" tab, never a second implementation.

Both land on the same `principal.tenant` either way — a freelancer's token is tenant-scoped
exactly like a staff member's (minted only after they pick ONE linked shop,
docs/خطة-تنفيذ-خدمة-العملاء.md's own Stage 6), so nothing here ever needs to ask "which shop" —
the token already answers it, the same trust boundary every other route in this service relies on.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.api.auth import Principal
from app.api.authz import require_any_capability
from app.api.ratelimit import rate_limit
from app.core.freelancer_crm import FreelancerCrmError
from app.core.notify_recipients import managers_for_branch

router = APIRouter(prefix="/staff/freelancer-portal", tags=["freelancer-portal"])

_PORTAL_CAP = "operations.freelancer_portal"
_MANAGE_CAP = "operations.freelancer_manage"
_ANY = require_any_capability(_PORTAL_CAP, _MANAGE_CAP)


def _tenant(p: Principal) -> str:
    if not p.tenant:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "NO_TENANT")
    return p.tenant


def _refuse(exc: Exception) -> None:
    raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


@router.get("/customers", dependencies=[Depends(rate_limit)])
async def list_customers(request: Request, limit: int = 50,
                         principal: Principal = Depends(_ANY)) -> dict:
    tenant = _tenant(principal)
    rows = await request.app.state.container.freelancer_crm.filtered_customers(
        tenant, limit=min(limit, 200))
    return {"customers": rows}


class RateIn(BaseModel):
    status: str


@router.post("/customers/{customer_id}/rate", dependencies=[Depends(rate_limit)])
async def rate_customer(request: Request, customer_id: str, body: RateIn,
                        principal: Principal = Depends(_ANY)) -> dict:
    tenant = _tenant(principal)
    try:
        await request.app.state.container.freelancer_crm.rate(
            tenant, customer_id, status=body.status, by=principal.subject)
    except FreelancerCrmError as exc:
        _refuse(exc)
    return {"ok": True}


@router.post("/customers/{customer_id}/do-not-disturb", dependencies=[Depends(rate_limit)])
async def do_not_disturb(request: Request, customer_id: str,
                         principal: Principal = Depends(_ANY)) -> dict:
    tenant = _tenant(principal)
    await request.app.state.container.freelancer_crm.set_do_not_disturb(tenant, customer_id)
    await request.app.state.auditor.record(
        "freelancer.customer_dnd", actor=principal.subject, tenant=tenant,
        resource=f"customer:{customer_id}", ip=request.client.host if request.client else "")
    return {"ok": True}


class GrantRewardIn(BaseModel):
    option_id: str
    subject_ref: str = Field(default="")


@router.post("/customers/{customer_id}/reward", dependencies=[Depends(rate_limit)])
async def grant_reward(request: Request, customer_id: str, body: GrantRewardIn,
                       principal: Principal = Depends(_ANY)) -> dict:
    tenant = _tenant(principal)
    try:
        grant = await request.app.state.container.freelancer_crm.grant_reward(
            tenant, customer_id, option_id=body.option_id, by=principal.subject,
            subject_ref=body.subject_ref)
    except FreelancerCrmError as exc:
        _refuse(exc)
    await request.app.state.auditor.record(
        "freelancer.reward_granted", actor=principal.subject, tenant=tenant,
        resource=f"customer:{customer_id}", ip=request.client.host if request.client else "")
    return grant


class EscalateIn(BaseModel):
    note: str = Field(min_length=1, max_length=1000)


@router.post("/customers/{customer_id}/escalate", dependencies=[Depends(rate_limit)])
async def escalate(request: Request, customer_id: str, body: EscalateIn,
                   principal: Principal = Depends(_ANY)) -> dict:
    tenant = _tenant(principal)
    container = request.app.state.container
    # TENANT-WIDE, NOT BRANCH-SCOPED — an escalation is about a customer, not a branch; `""`
    # matches every recipient the same way an unbranched row already reads as "for everyone"
    # elsewhere in this service (`managers_for_branch`'s own `_covers` rule).
    managers = await managers_for_branch(
        store=container.datastore, authz=container.authz_desk, tenant=tenant, branch_id="",
        capability=_MANAGE_CAP)
    esc = await container.freelancer_crm.escalate(
        tenant, customer_id, note=body.note, freelancer_phone=principal.subject,
        recipients=managers or [])
    await request.app.state.auditor.record(
        "freelancer.escalated", actor=principal.subject, tenant=tenant,
        resource=f"escalation:{esc.id}", ip=request.client.host if request.client else "")
    return esc.public()


class AddNoteIn(BaseModel):
    text: str = Field(default="", max_length=2000)
    status: str
    services: list[str] = Field(default_factory=list)


@router.post("/customers/{customer_id}/notes", dependencies=[Depends(rate_limit)])
async def add_note(request: Request, customer_id: str, body: AddNoteIn,
                   principal: Principal = Depends(_ANY)) -> dict:
    tenant = _tenant(principal)
    note = await request.app.state.container.freelancer_crm.add_note(
        tenant, customer_id, text=body.text, author_phone=principal.subject,
        status=body.status, services=body.services)
    return note.public()
