# =============================================================================
# affiliate-service — «برنامج دعم الوفاء» (spec §8): the platform's own BINDING decision
# -----------------------------------------------------------------------------
# `platform.affiliates_payouts` — same capability as admin_payouts.py, deliberately: a monthly
# stipend is money leaving the platform on a recurring basis, the same financial family as
# settling a commission, not "who becomes a marketer" (admin.py's own `platform.affiliates`).
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
from app.core.pii import subject_ref
from app.core.wafa import WafaError

router = APIRouter(prefix="/api/v1/admin/wafa-requests", tags=["affiliates-admin-wafa"])

_FINANCE = require_capability("platform.affiliates_payouts")


class DecideIn(BaseModel):
    decision: str = Field(min_length=1, max_length=16)
    reason: str = Field(default="", max_length=500)


def _svc(request: Request):
    return request.app.state.container.wafa


def _actor(principal: Principal) -> str:
    s = get_settings()
    if not s.PII_SALT:
        return ""
    return subject_ref(s.PII_SALT, principal.tenant or "", principal.subject)


def _refused(exc: WafaError) -> JSONResponse:
    body: dict[str, Any] = {"ok": False, "message": str(exc)}
    if getattr(exc, "reason", ""):
        body["reason"] = exc.reason
    return JSONResponse(status_code=400, content=body)


@router.get("", dependencies=[Depends(_FINANCE), Depends(rate_limit)])
async def list_pending(request: Request,
                       principal: Principal = Depends(require_user)) -> dict:
    """The system's own recommendation AND the manager's advisory call ride along on every row —
    the admin decides with both in front of him, bound by neither."""
    rows = await _svc(request).list_pending()
    return {"wafa_requests": [r.to_dict() for r in rows]}


@router.post("/{wafa_id}/decision", dependencies=[Depends(_FINANCE), Depends(rate_limit)])
async def decide(request: Request, wafa_id: str, body: DecideIn,
                 principal: Principal = Depends(require_user)) -> Any:
    """THE BINDING decision (spec §8) — may grant despite a manager's rejection, or refuse
    despite a manager's approval. Whatever the manager said stays on the row either way, never
    silently overridden without a trace."""
    await request.app.state.auditor.record(
        "affiliate.wafa_decided", actor=_actor(principal), tenant="",
        resource=f"wafa:{wafa_id}", ip=request.client.host if request.client else "",
        metadata={"decision": body.decision})
    try:
        out = await _svc(request).admin_decide(
            wafa_id, decision=body.decision, decided_by=_actor(principal), reason=body.reason)
    except WafaError as exc:
        return _refused(exc)
    return {"ok": True, **out.to_dict()}
