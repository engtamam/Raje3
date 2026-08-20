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

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from app.api.auth import Principal, require_user
from app.api.authz import require_capability
from app.api.ratelimit import rate_limit
from app.config import get_settings
from app.core.payouts import (
    PayoutError,
    is_uploaded_receipt,
    receipt_key,
    receipt_object_key,
)
from app.core.pii import subject_ref
from app.ports.errors import NotFound

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


@router.post("/{withdrawal_id}/receipt", dependencies=[Depends(_FINANCE), Depends(rate_limit)])
async def upload_receipt(request: Request, withdrawal_id: str,
                         file: UploadFile = File(...),
                         principal: Principal = Depends(require_user)) -> Any:
    """The FILE half of "كل الطرق ممكنة" (Tamam, 2026-08-20) — an admin may either upload the
    real transfer confirmation here, or just paste a link straight into POST .../complete's own
    `receipt_reference`; both end up in that exact same field (core/payouts.py's own note)."""
    s = get_settings()
    if file.content_type not in s.affiliate_receipt_content_types:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            f"نوع الملف غير مدعوم: {file.content_type}")
    data = await file.read()
    if len(data) > s.AFFILIATE_RECEIPT_MAX_BYTES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            f"الملف أكبر من الحد المسموح ({s.AFFILIATE_RECEIPT_MAX_BYTES} bytes).")

    try:
        request_row = await _svc(request).save_receipt_upload(
            withdrawal_id, content_type=file.content_type or "application/octet-stream")
    except PayoutError as exc:
        return _refused(exc)

    # THE BYTES THEMSELVES, written only after the service layer confirmed the request exists
    # and is still pending — an upload for a completed/rejected/unknown request must not leave
    # an orphan object nothing ever points at.
    await request.app.state.container.object_store.put(
        receipt_key(withdrawal_id), data, content_type=file.content_type)
    await request.app.state.auditor.record(
        "affiliate.withdrawal_receipt_uploaded", actor=_actor(principal), tenant="",
        resource=f"withdrawal:{withdrawal_id}",
        ip=request.client.host if request.client else "")
    return {"ok": True, "receipt_reference": request_row.receipt_reference}


@router.get("/{withdrawal_id}/receipt", dependencies=[Depends(_FINANCE), Depends(rate_limit)])
async def download_receipt(request: Request, withdrawal_id: str,
                           principal: Principal = Depends(require_user)) -> Response:
    return await _serve_receipt(request, withdrawal_id)


async def _serve_receipt(request: Request, withdrawal_id: str) -> Response:
    """Shared by the admin route above and the marketer's own (affiliate_self.py) — same
    reference, same rules, so the two can never drift on what counts as "the receipt"."""
    wd = await request.app.state.container.payouts.get(withdrawal_id)
    if wd is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND")
    if not wd.receipt_reference:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NO_RECEIPT")
    if not is_uploaded_receipt(wd.receipt_reference):
        # A pasted URL — nothing here to stream; the admin who pasted it already has it, and a
        # marketer viewing his own withdrawal reads the plain reference off the JSON body
        # instead (GET .../withdrawals already returns it).
        raise HTTPException(status.HTTP_409_CONFLICT, "NOT_AN_UPLOAD")
    try:
        data = await request.app.state.container.object_store.get(
            receipt_object_key(wd.receipt_reference))
    except NotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND")
    return Response(content=data, media_type=wd.receipt_content_type or "application/octet-stream")


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
