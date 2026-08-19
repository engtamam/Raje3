# =============================================================================
# affiliate-service — the admin's queue («بوابة القبول», spec §2)
# -----------------------------------------------------------------------------
# `affiliates.manage` IS ITS OWN CAPABILITY, not folded into a generic "admin" — approving an
# applicant mints a real identity membership and, from that moment, a channel that can message
# our customers in the platform's name. That is a narrower and more consequential act than most
# things an "admin" role bundles, and it deserves its own line in roles.json rather than riding
# along on a capability granted for something else (same reasoning that split
# operations.manage_services out of operations.manage this session).
#
# EVERY DECISION IS AUDITED WRITE-AHEAD, same principle as operator.py's secret rotation in this
# same service: an approval or rejection that cannot be recorded must not happen, because the
# alternative — a membership minted with nothing proving who approved it — is indistinguishable
# from one an attacker minted.
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
from app.core.onboarding import OnboardingRefused
from app.core.pii import subject_ref

router = APIRouter(prefix="/api/v1/admin/affiliates", tags=["affiliates-admin"])

_MANAGE = require_capability("affiliates.manage")


class RejectIn(BaseModel):
    reason: str = Field(default="", max_length=500)


def _svc(request: Request):
    return request.app.state.container.onboarding


def _actor(principal: Principal) -> str:
    """A pseudonym, never the admin's raw identifier — same helper as operator.py in this
    service, and it lands in the same append-only audit chain."""
    s = get_settings()
    if not s.PII_SALT:
        return ""
    return subject_ref(s.PII_SALT, principal.tenant or "", principal.subject)


def _refused(exc: OnboardingRefused) -> JSONResponse:
    body: dict[str, Any] = {"ok": False, "message": str(exc)}
    if getattr(exc, "reason", ""):
        body["reason"] = exc.reason
    return JSONResponse(status_code=400, content=body)


@router.get("", dependencies=[Depends(_MANAGE), Depends(rate_limit)])
async def list_pending(request: Request,
                       principal: Principal = Depends(require_user)) -> dict:
    return {"applications": await _svc(request).list_pending()}


@router.post("/{application_id}/approve", dependencies=[Depends(_MANAGE), Depends(rate_limit)])
async def approve(request: Request, application_id: str,
                  principal: Principal = Depends(require_user)) -> Any:
    await request.app.state.auditor.record(
        "affiliate.application_approved", actor=_actor(principal), tenant="",
        resource=f"application:{application_id}",
        ip=request.client.host if request.client else "")
    try:
        out = await _svc(request).approve(application_id, decided_by=_actor(principal))
    except OnboardingRefused as exc:
        return _refused(exc)
    return {"ok": True, **out}


@router.post("/{application_id}/reject", dependencies=[Depends(_MANAGE), Depends(rate_limit)])
async def reject(request: Request, application_id: str, body: RejectIn,
                 principal: Principal = Depends(require_user)) -> Any:
    await request.app.state.auditor.record(
        "affiliate.application_rejected", actor=_actor(principal), tenant="",
        resource=f"application:{application_id}",
        ip=request.client.host if request.client else "",
        metadata={"reason": body.reason[:200]} if body.reason else None)
    try:
        out = await _svc(request).reject(
            application_id, decided_by=_actor(principal), reason=body.reason)
    except OnboardingRefused as exc:
        return _refused(exc)
    return {"ok": True, **out}
