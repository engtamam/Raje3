# =============================================================================
# affiliate-service — settling a withdrawal (spec §5)
# -----------------------------------------------------------------------------
# `platform.affiliates_payouts` IS ITS OWN CAPABILITY, separate from `platform.affiliates`
# (admin.py) — Tamam, 2026-08-20: "who becomes a marketer" is a different decision from "settling
# a commission", the exact reasoning deploy/seed/operator-roles.json's own platform-finance role
# already states for every other money-moving action on the platform. A holder of one must not
# automatically hold the other.
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
from app.core.payouts import PayoutError
from app.core.pii import subject_ref

router = APIRouter(prefix="/api/v1/admin/withdrawals", tags=["affiliates-admin-payouts"])

_FINANCE = require_capability("platform.affiliates_payouts")


class CompleteIn(BaseModel):
    #: A URL, or an object-store key — never the file itself in this body. Required: spec §5's
    #: whole point is that a completion with no attached proof is the exact dispute it prevents.
    receipt_reference: str = Field(min_length=1, max_length=500)


class RejectIn(BaseModel):
    reason: str = Field(default="", max_length=500)


def _svc(request: Request):
    return request.app.state.container.payouts


def _actor(principal: Principal) -> str:
    s = get_settings()
    if not s.PII_SALT:
        return ""
    return subject_ref(s.PII_SALT, principal.tenant or "", principal.subject)


def _refused(exc: PayoutError) -> JSONResponse:
    body: dict[str, Any] = {"ok": False, "message": str(exc)}
    if getattr(exc, "reason", ""):
        body["reason"] = exc.reason
    return JSONResponse(status_code=400, content=body)


@router.get("", dependencies=[Depends(_FINANCE), Depends(rate_limit)])
async def list_pending(request: Request,
                       principal: Principal = Depends(require_user)) -> dict:
    rows = await _svc(request).list_pending()
    return {"withdrawals": [r.to_dict() for r in rows]}


@router.post("/{withdrawal_id}/complete", dependencies=[Depends(_FINANCE), Depends(rate_limit)])
async def complete(request: Request, withdrawal_id: str, body: CompleteIn,
                   principal: Principal = Depends(require_user)) -> Any:
    await request.app.state.auditor.record(
        "affiliate.withdrawal_completed", actor=_actor(principal), tenant="",
        resource=f"withdrawal:{withdrawal_id}",
        ip=request.client.host if request.client else "")
    try:
        out = await _svc(request).complete(
            withdrawal_id, decided_by=_actor(principal), receipt_reference=body.receipt_reference)
    except PayoutError as exc:
        return _refused(exc)
    return {"ok": True, **out}


@router.post("/{withdrawal_id}/reject", dependencies=[Depends(_FINANCE), Depends(rate_limit)])
async def reject(request: Request, withdrawal_id: str, body: RejectIn,
                 principal: Principal = Depends(require_user)) -> Any:
    await request.app.state.auditor.record(
        "affiliate.withdrawal_rejected", actor=_actor(principal), tenant="",
        resource=f"withdrawal:{withdrawal_id}",
        ip=request.client.host if request.client else "",
        metadata={"reason": body.reason[:200]} if body.reason else None)
    try:
        out = await _svc(request).reject(
            withdrawal_id, decided_by=_actor(principal), reason=body.reason)
    except PayoutError as exc:
        return _refused(exc)
    return {"ok": True, **out}
