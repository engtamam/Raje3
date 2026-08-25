# =============================================================================
# affiliate-service — the admin's queue («بوابة القبول», spec §2)
# -----------------------------------------------------------------------------
# `platform.affiliates` IS ITS OWN CAPABILITY, not folded into a generic "admin" — approving an
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
from app.core.models import ACTIVE, AFFILIATES, Affiliate
from app.core.onboarding import OnboardingRefused
from app.core.pii import subject_ref

router = APIRouter(prefix="/api/v1/admin/affiliates", tags=["affiliates-admin"])

_MANAGE = require_capability("platform.affiliates")


class RejectIn(BaseModel):
    reason: str = Field(default="", max_length=500)


class PlatformRevenueIn(BaseModel):
    enabled: bool


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


# ── suspending / reactivating an EXISTING affiliate (spec §10: «تعليق لا حذف») ────────────────
@router.post("/{affiliate_id}/suspend", dependencies=[Depends(_MANAGE), Depends(rate_limit)])
async def suspend(request: Request, affiliate_id: str,
                  principal: Principal = Depends(require_user)) -> Any:
    await request.app.state.auditor.record(
        "affiliate.suspended", actor=_actor(principal), tenant="",
        resource=f"affiliate:{affiliate_id}",
        ip=request.client.host if request.client else "")
    try:
        out = await _svc(request).suspend(affiliate_id, decided_by=_actor(principal))
    except OnboardingRefused as exc:
        return _refused(exc)
    return {"ok": True, **out}


@router.post("/{affiliate_id}/reactivate", dependencies=[Depends(_MANAGE), Depends(rate_limit)])
async def reactivate(request: Request, affiliate_id: str,
                     principal: Principal = Depends(require_user)) -> Any:
    await request.app.state.auditor.record(
        "affiliate.reactivated", actor=_actor(principal), tenant="",
        resource=f"affiliate:{affiliate_id}",
        ip=request.client.host if request.client else "")
    try:
        out = await _svc(request).reactivate(affiliate_id, decided_by=_actor(principal))
    except OnboardingRefused as exc:
        return _refused(exc)
    return {"ok": True, **out}


# ── spec §10's optional whole-platform revenue view — OFF by default, admin-granted only ───────
@router.post("/{affiliate_id}/platform-revenue", dependencies=[Depends(_MANAGE), Depends(rate_limit)])
async def set_platform_revenue(request: Request, affiliate_id: str, body: PlatformRevenueIn,
                               principal: Principal = Depends(require_user)) -> Any:
    await request.app.state.auditor.record(
        "affiliate.platform_revenue_visibility_changed", actor=_actor(principal), tenant="",
        resource=f"affiliate:{affiliate_id}",
        ip=request.client.host if request.client else "",
        metadata={"enabled": body.enabled})
    try:
        out = await _svc(request).set_platform_revenue_visibility(affiliate_id, enabled=body.enabled)
    except OnboardingRefused as exc:
        return _refused(exc)
    return {"ok": True, **out}


# ── the admin panel's own dashboard reads — cross-affiliate, never per-manager ─────────────────
#
# NOT AUDITED, matching `admin_sectors.py::platform_sector_stats`'s own precedent exactly: these
# are read-only aggregate views (a count, a leaderboard, a revenue total already exposed
# opt-in per-manager via `sees_platform_revenue`) — no money moves and no PII crosses a boundary
# it wasn't already crossing. If that convention ever changes here, it changes for `sectors.stats`
# too, not just here.
@router.get("/stats", dependencies=[Depends(_MANAGE), Depends(rate_limit)])
async def platform_affiliate_stats(request: Request,
                                   principal: Principal = Depends(require_user)) -> dict:
    """How many affiliates are actually active right now, and what the whole channel has ever
    brought the platform (`CommissionEngine.platform_revenue()` — every referral ever stamped,
    regardless of tree or status, same figure a manager sees opt-in via `sees_platform_revenue`)."""
    c = request.app.state.container
    rows = await c.datastore.scan_all(AFFILIATES, 5000)
    active_count = sum(1 for r in rows if r.get("status") == ACTIVE)
    revenue = await c.commissions.platform_revenue()
    return {"active_affiliates": active_count, "total_affiliates": len(rows),
           "total_net_revenue_minor": revenue["total_net_revenue_minor"],
           "revenue_partial": revenue["revenue_partial"]}


@router.get("/leaderboard", dependencies=[Depends(_MANAGE), Depends(rate_limit)])
async def platform_affiliate_leaderboard(request: Request, limit: int = 20,
                                         principal: Principal = Depends(require_user)) -> dict:
    """Every ACTIVE affiliate's own measurable performance (`WafaService.performance_for` — the
    exact metrics a manager's own eyes and the Wafa recommendation are already built from, one
    computation, never a second driftable copy), ranked by referrals then retention.

    A LOOP, NOT A NEW BULK METHOD — same shape `sector_stats`'s cross-manager scan already uses.
    At the affiliate counts this product runs at today this is cheap; if the roster ever grows
    large enough for this to matter, the fix is a real `performance_for_all()` in `wafa.py`, not
    a workaround here."""
    c = request.app.state.container
    rows = await c.datastore.scan_all(AFFILIATES, 5000)
    board = []
    for r in rows:
        aff = Affiliate.from_dict(r)
        if aff.status != ACTIVE:
            continue
        perf = await c.wafa.performance_for(aff.id)
        board.append({"affiliate_id": aff.id, "name": aff.name, **perf})
    board.sort(key=lambda x: (x["total_referrals"], x["retention_rate"]), reverse=True)
    return {"leaderboard": board[: max(1, min(limit, 100))]}
