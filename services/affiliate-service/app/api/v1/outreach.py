# =============================================================================
# affiliate-service — the outbound conversion playbook's own routes (2026-08-22)
# -----------------------------------------------------------------------------
# READS ARE OPEN TO ANY AFFILIATE — a promoter needs the stage list and the template library to
# do his own job. WRITES TO THE SHARED LIBRARY (stages, templates) are manager-only, same data
# check as everywhere else in this file family (`_my_manager_affiliate`, imported from
# affiliate_self.py rather than re-implemented — one role check, not two that could drift).
# WRITES TO A SPECIFIC LEAD (logging a use, its outcome, the decision-maker's contact) are
# ownership-checked INSIDE core/outreach.py, never here — see that module's own docstring.
# =============================================================================
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.api.auth import Principal, require_user
from app.api.ratelimit import rate_limit
from app.api.v1.affiliate_self import _my_manager_affiliate, _svc
from app.core.outreach import OutreachError

router = APIRouter(prefix="/api/v1/affiliates/me", tags=["affiliates-outreach"])


def _refused(exc: OutreachError) -> JSONResponse:
    body: dict[str, Any] = {"ok": False, "message": str(exc)}
    if getattr(exc, "reason", ""):
        body["reason"] = exc.reason
    status_code = 404 if exc.reason in ("not_found", "template_not_found") else \
        403 if exc.reason == "not_yours" else 400
    return JSONResponse(status_code=status_code, content=body)


# ── reads — any affiliate ────────────────────────────────────────────────────────────────────
@router.get("/outreach-stages", dependencies=[Depends(rate_limit)])
async def list_outreach_stages(request: Request,
                               principal: Principal = Depends(require_user)) -> dict:
    stages = await request.app.state.container.outreach_stages.list(active_only=True)
    return {"stages": [s.to_dict() for s in stages]}


@router.get("/templates", dependencies=[Depends(rate_limit)])
async def list_templates(request: Request, stage_code: str = "",
                         principal: Principal = Depends(require_user)) -> dict:
    tpls = await request.app.state.container.templates.list(stage_code=stage_code,
                                                             active_only=True)
    return {"templates": [t.to_dict() for t in tpls]}


@router.get("/template-stats", dependencies=[Depends(rate_limit)])
async def template_stats(request: Request, stage_code: str = "",
                         principal: Principal = Depends(require_user)) -> dict:
    """Which TEMPLATE actually moves a lead forward — see core/outreach.py::stats."""
    stats = await request.app.state.container.template_uses.stats(stage_code=stage_code)
    return {"stats": stats}


@router.get("/template-kind-stats", dependencies=[Depends(rate_limit)])
async def template_kind_stats(request: Request,
                              principal: Principal = Depends(require_user)) -> dict:
    """Which CONTENT TYPE actually moves a lead forward, across every template sharing it."""
    stats = await request.app.state.container.template_uses.kind_stats()
    return {"stats": stats}


# ── acting on one lead — ownership checked inside the service, any affiliate ────────────────────
class TemplateUseIn(BaseModel):
    template_id: str = Field(min_length=1, max_length=64)


@router.post("/leads/{lead_id}/template-uses", status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(rate_limit)])
async def log_template_use(request: Request, lead_id: str, body: TemplateUseIn,
                           principal: Principal = Depends(require_user)) -> Any:
    affiliate = await _svc(request).me(principal.subject)
    if affiliate is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_AN_AFFILIATE")
    try:
        out = await request.app.state.container.template_uses.log_use(
            lead_id, template_id=body.template_id, used_by=affiliate["id"])
    except OutreachError as exc:
        return _refused(exc)
    return {"ok": True, **out.to_dict()}


class SetOutcomeIn(BaseModel):
    outcome: str = Field(min_length=1, max_length=32)
    note: str = Field(default="", max_length=1000)
    new_stage_code: str = Field(default="", max_length=64)


@router.patch("/template-uses/{use_id}", dependencies=[Depends(rate_limit)])
async def set_template_use_outcome(request: Request, use_id: str, body: SetOutcomeIn,
                                   principal: Principal = Depends(require_user)) -> Any:
    """The one place a lead's outcome — and, explicitly, its next stage — is recorded. Never
    inferred: see core/outreach.py::set_outcome's own docstring."""
    affiliate = await _svc(request).me(principal.subject)
    if affiliate is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_AN_AFFILIATE")
    try:
        out = await request.app.state.container.template_uses.set_outcome(
            use_id, outcome=body.outcome, by=affiliate["id"], note=body.note,
            new_stage_code=body.new_stage_code or None,
            stages=request.app.state.container.outreach_stages)
    except OutreachError as exc:
        return _refused(exc)
    return {"ok": True, **out.to_dict()}


@router.get("/leads/{lead_id}/template-uses", dependencies=[Depends(rate_limit)])
async def lead_template_uses(request: Request, lead_id: str,
                             principal: Principal = Depends(require_user)) -> dict:
    uses = await request.app.state.container.template_uses.uses_for_lead(lead_id)
    return {"uses": [u.to_dict() for u in uses]}


class DecisionMakerIn(BaseModel):
    name: str = Field(default="", max_length=200)
    phone: str = Field(default="", max_length=32)
    role: str = Field(default="", max_length=64)


@router.patch("/leads/{lead_id}/decision-maker", dependencies=[Depends(rate_limit)])
async def set_decision_maker(request: Request, lead_id: str, body: DecisionMakerIn,
                             principal: Principal = Depends(require_user)) -> Any:
    """The reception's own line (`Lead.phone`) is Google's, often unreachable-to-the-owner; this
    is the real decision-maker's contact, recorded ONLY once a promoter actually obtained it."""
    affiliate = await _svc(request).me(principal.subject)
    if affiliate is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_AN_AFFILIATE")
    try:
        out = await request.app.state.container.template_uses.set_decision_maker(
            lead_id, by=affiliate["id"], name=body.name, phone=body.phone, role=body.role)
    except OutreachError as exc:
        return _refused(exc)
    return {"ok": True, **out.to_dict()}


# ── the shared library — manager-only writes ────────────────────────────────────────────────────
class StageIn(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    order: int = Field(default=0, ge=0, le=10000)


@router.put("/outreach-stages", dependencies=[Depends(rate_limit)])
async def upsert_outreach_stage(request: Request, body: StageIn,
                                principal: Principal = Depends(require_user)) -> Any:
    affiliate = await _my_manager_affiliate(request, principal)
    try:
        out = await request.app.state.container.outreach_stages.create(
            code=body.code, name=body.name, order=body.order)
    except OutreachError as exc:
        return _refused(exc)
    await request.app.state.auditor.record(
        "affiliate.outreach_stage_changed", actor=affiliate["id"], tenant="",
        resource=f"outreach_stage:{out.code}",
        ip=request.client.host if request.client else "")
    return {"ok": True, **out.to_dict()}


@router.delete("/outreach-stages/{code}", dependencies=[Depends(rate_limit)])
async def deactivate_outreach_stage(request: Request, code: str,
                                    principal: Principal = Depends(require_user)) -> dict:
    affiliate = await _my_manager_affiliate(request, principal)
    changed = await request.app.state.container.outreach_stages.deactivate(code)
    if changed:
        await request.app.state.auditor.record(
            "affiliate.outreach_stage_changed", actor=affiliate["id"], tenant="",
            resource=f"outreach_stage:{code}",
            ip=request.client.host if request.client else "")
    return {"ok": True, "changed": changed}


class TemplateIn(BaseModel):
    stage_code: str = Field(min_length=1, max_length=64)
    kind: str = Field(default="", max_length=64)
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(default="", max_length=4000)
    media_url: str = Field(default="", max_length=1000)
    objection_type: str = Field(default="", max_length=64)


@router.post("/templates", status_code=status.HTTP_201_CREATED, dependencies=[Depends(rate_limit)])
async def create_template(request: Request, body: TemplateIn,
                         principal: Principal = Depends(require_user)) -> Any:
    affiliate = await _my_manager_affiliate(request, principal)
    try:
        out = await request.app.state.container.templates.create(
            stage_code=body.stage_code, kind=body.kind, title=body.title, body=body.body,
            media_url=body.media_url, objection_type=body.objection_type,
            created_by=affiliate["id"])
    except OutreachError as exc:
        return _refused(exc)
    await request.app.state.auditor.record(
        "affiliate.template_changed", actor=affiliate["id"], tenant="",
        resource=f"template:{out.id}", ip=request.client.host if request.client else "")
    return {"ok": True, **out.to_dict()}


@router.put("/templates/{template_id}", dependencies=[Depends(rate_limit)])
async def update_template(request: Request, template_id: str, body: TemplateIn,
                         principal: Principal = Depends(require_user)) -> Any:
    affiliate = await _my_manager_affiliate(request, principal)
    try:
        out = await request.app.state.container.templates.update(
            template_id, stage_code=body.stage_code, kind=body.kind, title=body.title,
            body=body.body, media_url=body.media_url, objection_type=body.objection_type)
    except OutreachError as exc:
        return _refused(exc)
    await request.app.state.auditor.record(
        "affiliate.template_changed", actor=affiliate["id"], tenant="",
        resource=f"template:{template_id}", ip=request.client.host if request.client else "")
    return {"ok": True, **out.to_dict()}


@router.delete("/templates/{template_id}", dependencies=[Depends(rate_limit)])
async def deactivate_template(request: Request, template_id: str,
                              principal: Principal = Depends(require_user)) -> dict:
    affiliate = await _my_manager_affiliate(request, principal)
    changed = await request.app.state.container.templates.deactivate(template_id)
    if changed:
        await request.app.state.auditor.record(
            "affiliate.template_changed", actor=affiliate["id"], tenant="",
            resource=f"template:{template_id}",
            ip=request.client.host if request.client else "")
    return {"ok": True, "changed": changed}
