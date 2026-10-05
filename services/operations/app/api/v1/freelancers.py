"""Customer-service freelancers — the shop's OWN admin door. See `core/freelancer_service.py` and
`core/freelancer_crm.py` for the full design; this file is only the HTTP door for the TAJER's side
of it (add/remove freelancers, business rules, reward catalog, escalation inbox). The freelancer's
OWN door is `api/v1/freelancer_portal.py` — a deliberately separate file, same split
`mobile_requests.py`'s own module docstring documents for its two capabilities.

ONE CAPABILITY ONLY — `operations.freelancer_manage` — granted in `deploy/seed/roles.json` to
owner/manager/marketer/supervisor, explicitly withheld from `operator` (the field role has no
business running customer-service escalations) and from `partner` (the till-reseller role, walled
off from a shop's own customers/phone numbers by design — see `core/freelancer_service.py`'s own
module docstring for why granting it here would be exactly the leak that role exists to prevent).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.api.auth import Principal
from app.api.authz import require_capability
from app.api.ratelimit import rate_limit
from app.core.freelancer_crm import FreelancerCrmError
from app.core.freelancer_service import FreelancerError

router = APIRouter(prefix="/staff/freelancers", tags=["freelancers"])

_MANAGE_CAP = "operations.freelancer_manage"
_MANAGE = require_capability(_MANAGE_CAP)


def _tenant(p: Principal) -> str:
    if not p.tenant:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "NO_TENANT")
    return p.tenant


def _refuse(exc: Exception) -> None:
    raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


# ── freelancers themselves (max 3 active, enforced in core/freelancer_service.py) ────────────────

@router.get("", dependencies=[Depends(rate_limit)])
async def list_freelancers(request: Request, principal: Principal = Depends(_MANAGE)) -> dict:
    tenant = _tenant(principal)
    rows = await request.app.state.container.freelancers.list(tenant)
    return {"freelancers": [r.public() for r in rows]}


class AddFreelancerIn(BaseModel):
    phone: str = Field(min_length=5, max_length=20)
    display_name: str = Field(min_length=1, max_length=80)


@router.post("", dependencies=[Depends(rate_limit)])
async def add_freelancer(request: Request, body: AddFreelancerIn,
                         principal: Principal = Depends(_MANAGE)) -> dict:
    tenant = _tenant(principal)
    try:
        row = await request.app.state.container.freelancers.add(
            tenant, phone=body.phone, display_name=body.display_name, actor=principal.subject)
    except FreelancerError as exc:
        _refuse(exc)
    await request.app.state.auditor.record(
        "freelancer.added", actor=principal.subject, tenant=tenant,
        resource=f"freelancer:{row.id}", ip=request.client.host if request.client else "")
    return row.public()


@router.post("/{link_id}/deactivate", dependencies=[Depends(rate_limit)])
async def deactivate_freelancer(request: Request, link_id: str,
                                principal: Principal = Depends(_MANAGE)) -> dict:
    tenant = _tenant(principal)
    try:
        row = await request.app.state.container.freelancers.deactivate(tenant, link_id)
    except FreelancerError as exc:
        _refuse(exc)
    await request.app.state.auditor.record(
        "freelancer.deactivated", actor=principal.subject, tenant=tenant,
        resource=f"freelancer:{link_id}", ip=request.client.host if request.client else "")
    return row.public()


# ── business rules ─────────────────────────────────────────────────────────────────────────────

@router.get("/rules", dependencies=[Depends(rate_limit)])
async def get_rules(request: Request, principal: Principal = Depends(_MANAGE)) -> dict:
    tenant = _tenant(principal)
    rules = await request.app.state.container.freelancer_crm.get_rules(tenant)
    return rules.public()


class SetRulesIn(BaseModel):
    cooldown_days: int = Field(ge=0, le=365)
    daily_cap: int = Field(ge=0, le=1000)
    quiet_start_minute: int = Field(default=0, ge=0, le=1440)
    quiet_end_minute: int = Field(default=0, ge=0, le=1440)


@router.post("/rules", dependencies=[Depends(rate_limit)])
async def set_rules(request: Request, body: SetRulesIn,
                    principal: Principal = Depends(_MANAGE)) -> dict:
    tenant = _tenant(principal)
    try:
        rules = await request.app.state.container.freelancer_crm.set_rules(
            tenant, cooldown_days=body.cooldown_days, daily_cap=body.daily_cap,
            quiet_start_minute=body.quiet_start_minute, quiet_end_minute=body.quiet_end_minute)
    except FreelancerCrmError as exc:
        _refuse(exc)
    await request.app.state.auditor.record(
        "freelancer.rules_set", actor=principal.subject, tenant=tenant,
        resource=f"tenant:{tenant}", ip=request.client.host if request.client else "")
    return rules.public()


# ── reward catalog ─────────────────────────────────────────────────────────────────────────────

@router.get("/reward-options", dependencies=[Depends(rate_limit)])
async def list_reward_options(request: Request, principal: Principal = Depends(_MANAGE)) -> dict:
    tenant = _tenant(principal)
    rows = await request.app.state.container.freelancer_crm.list_reward_options(tenant)
    return {"options": [r.public() for r in rows]}


class AddRewardOptionIn(BaseModel):
    kind: str
    label: str = Field(min_length=1, max_length=80)
    percent: int = Field(default=0, ge=0, le=100)
    points: int = Field(default=0, ge=0, le=100000)


@router.post("/reward-options", dependencies=[Depends(rate_limit)])
async def add_reward_option(request: Request, body: AddRewardOptionIn,
                            principal: Principal = Depends(_MANAGE)) -> dict:
    tenant = _tenant(principal)
    try:
        opt = await request.app.state.container.freelancer_crm.add_reward_option(
            tenant, kind=body.kind, label=body.label, percent=body.percent, points=body.points)
    except FreelancerCrmError as exc:
        _refuse(exc)
    return opt.public()


# ── escalation inbox ───────────────────────────────────────────────────────────────────────────

@router.get("/escalations", dependencies=[Depends(rate_limit)])
async def list_escalations(request: Request, status_filter: str = "",
                           principal: Principal = Depends(_MANAGE)) -> dict:
    tenant = _tenant(principal)
    rows = await request.app.state.container.freelancer_crm.list_escalations(
        tenant, status=status_filter)
    return {"escalations": [r.public() for r in rows]}


class ResolveEscalationIn(BaseModel):
    resolution_note: str = Field(default="", max_length=1000)
    new_status: str = Field(default="satisfied")


@router.post("/escalations/{escalation_id}/resolve", dependencies=[Depends(rate_limit)])
async def resolve_escalation(request: Request, escalation_id: str, body: ResolveEscalationIn,
                             principal: Principal = Depends(_MANAGE)) -> dict:
    tenant = _tenant(principal)
    try:
        row = await request.app.state.container.freelancer_crm.resolve_escalation(
            tenant, escalation_id, resolved_by=principal.subject,
            resolution_note=body.resolution_note, new_status=body.new_status)
    except FreelancerCrmError as exc:
        _refuse(exc)
    await request.app.state.auditor.record(
        "freelancer.escalation_resolved", actor=principal.subject, tenant=tenant,
        resource=f"escalation:{escalation_id}", ip=request.client.host if request.client else "")
    return row.public()


# ── export ──────────────────────────────────────────────────────────────────────────────────────

@router.get("/notes/export", dependencies=[Depends(rate_limit)])
async def export_notes(request: Request, since: int, until: int, include_pii: bool = False,
                       principal: Principal = Depends(_MANAGE)) -> dict:
    tenant = _tenant(principal)
    text = await request.app.state.container.freelancer_crm.export_notes(
        tenant, since=since, until=until, include_pii=include_pii)
    if include_pii:
        await request.app.state.auditor.record(
            "freelancer.notes_exported_with_pii", actor=principal.subject, tenant=tenant,
            resource=f"tenant:{tenant}", ip=request.client.host if request.client else "")
    return {"text": text}
