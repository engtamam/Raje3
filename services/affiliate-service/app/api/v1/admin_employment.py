# =============================================================================
# affiliate-service — «رشّح نفسك لوظيفة» (spec §8): the platform's own decision
# -----------------------------------------------------------------------------
# `platform.affiliates` — same capability as approving an applicant / suspending an affiliate
# (admin.py), deliberately: this is an HR-family decision ("who becomes staff"), not a money-
# moving one, so it does NOT ride on `platform.affiliates_payouts` the way admin_wafa.py's
# recurring stipend decision does.
# =============================================================================
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.api.auth import Principal, require_user
from app.api.authz import require_capability
from app.api.ratelimit import rate_limit
from app.config import get_settings
from app.core.employment import EmploymentError
from app.core.pii import subject_ref

router = APIRouter(prefix="/api/v1/admin/employment-requests", tags=["affiliates-admin-employment"])

_MANAGE = require_capability("platform.affiliates")


class DecideIn(BaseModel):
    decision: str = Field(min_length=1, max_length=16)
    reason: str = Field(default="", max_length=500)


def _svc(request: Request):
    return request.app.state.container.employment


def _actor(principal: Principal) -> str:
    s = get_settings()
    if not s.PII_SALT:
        return ""
    return subject_ref(s.PII_SALT, principal.tenant or "", principal.subject)


def _refused(exc: EmploymentError) -> JSONResponse:
    body: dict[str, Any] = {"ok": False, "message": str(exc)}
    if getattr(exc, "reason", ""):
        body["reason"] = exc.reason
    return JSONResponse(status_code=400, content=body)


async def _audit_refused(request: Request, action: str, *, resource: str, actor: str,
                        exc: Exception) -> None:
    """A second, corrective entry for the SAME action/resource — fixed 2026-09-12, a real gap a
    QA audit found: `decide` records "employment_decided" write-ahead, but a refused decision
    (an already-resolved request, an invalid transition) used to leave that entry claiming a
    decision that never actually took effect, with nothing to say so. Append-only, same
    convention as every other write-ahead correction on this platform — never edits the first
    entry."""
    await request.app.state.auditor.record(
        action, actor=actor, tenant="", resource=resource,
        ip=request.client.host if request.client else "",
        metadata={"outcome": "refused", "reason": getattr(exc, "reason", "") or str(exc)})


@router.get("", dependencies=[Depends(_MANAGE), Depends(rate_limit)])
async def list_pending(request: Request,
                       principal: Principal = Depends(require_user)) -> dict:
    rows = await _svc(request).list_pending()
    return {"employment_requests": [r.to_dict() for r in rows]}


@router.post("/{request_id}/decision", dependencies=[Depends(_MANAGE), Depends(rate_limit)])
async def decide(request: Request, request_id: str, body: DecideIn,
                 principal: Principal = Depends(require_user)) -> Any:
    await request.app.state.auditor.record(
        "affiliate.employment_decided", actor=_actor(principal), tenant="",
        resource=f"employment_request:{request_id}",
        ip=request.client.host if request.client else "",
        metadata={"decision": body.decision})
    try:
        out = await _svc(request).decide(
            request_id, decision=body.decision, decided_by=_actor(principal), reason=body.reason)
    except EmploymentError as exc:
        await _audit_refused(request, "affiliate.employment_decided",
                             resource=f"employment_request:{request_id}",
                             actor=_actor(principal), exc=exc)
        return _refused(exc)
    return {"ok": True, **out.to_dict()}
