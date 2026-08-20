# =============================================================================
# affiliate-service — what an affiliate does about HIS OWN team, not the platform's
# -----------------------------------------------------------------------------
# NO CAPABILITY GATE HERE, deliberately — and that is not an oversight, it is the same shape as
# operations.hire() (a shop owner needs no platform capability to hire his own staff; the gate is
# "is this his shop", a DATA check, not an RBAC check). Here it is "is this an ACTIVE manager
# affiliate", checked inside onboarding.invite() against the caller's own person_id — a
# capability would answer "may marketers in general invite", which is the wrong question; the
# real one is "is the caller himself a manager", and only a data lookup on his own identity
# answers that honestly.
# =============================================================================
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from app.api.auth import Principal, require_user
from app.api.ratelimit import rate_limit
from app.core.onboarding import OnboardingRefused
from app.core.payouts import PayoutError
from app.core.wafa import WafaError

router = APIRouter(prefix="/api/v1/affiliates/me", tags=["affiliates-self"])


class InviteIn(BaseModel):
    phone: str = Field(min_length=6, max_length=32)
    name: str = Field(min_length=1, max_length=200)


class PayoutMethodIn(BaseModel):
    channel: str = Field(min_length=1, max_length=32)
    channel_name: str = Field(default="", max_length=100)
    account_ref: str = Field(min_length=1, max_length=200)


def _svc(request: Request):
    return request.app.state.container.onboarding


def _refused(exc: OnboardingRefused) -> JSONResponse:
    body: dict[str, Any] = {"ok": False, "message": str(exc)}
    if getattr(exc, "reason", ""):
        body["reason"] = exc.reason
    status_code = 403 if exc.reason in ("not_an_active_affiliate", "managers_only") else 400
    return JSONResponse(status_code=status_code, content=body)


def _payout_refused(exc: PayoutError) -> JSONResponse:
    body: dict[str, Any] = {"ok": False, "message": str(exc)}
    if getattr(exc, "reason", ""):
        body["reason"] = exc.reason
    return JSONResponse(status_code=400, content=body)


def _wafa_refused(exc: WafaError) -> JSONResponse:
    body: dict[str, Any] = {"ok": False, "message": str(exc)}
    if getattr(exc, "reason", ""):
        body["reason"] = exc.reason
    return JSONResponse(status_code=400, content=body)


async def _my_affiliate_id(request: Request, principal: Principal) -> str:
    """404s the route the same way `me`/`commissions` already do — never a silent empty string
    that would let a caller with no affiliate row somehow query payout data for `affiliate_id:
    ""`, which every store lookup below would then simply find nothing for and answer as if it
    were a legitimate empty account rather than "you are not one at all"."""
    affiliate = await _svc(request).me(principal.subject)
    if affiliate is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_AN_AFFILIATE")
    return affiliate["id"]


@router.get("", dependencies=[Depends(rate_limit)])
async def me(request: Request, principal: Principal = Depends(require_user)) -> dict:
    """Who I am, and — since his own `id` IS his referral code (spec §1) — everything the console
    needs to show him his own link: `?aff=<id>` for a shop, `?ref=<id>` for another marketer
    applying under him."""
    out = await _svc(request).me(principal.subject)
    if out is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_AN_AFFILIATE")
    return out


@router.post("/invite", dependencies=[Depends(rate_limit)])
async def invite(request: Request, body: InviteIn,
                 principal: Principal = Depends(require_user)) -> Any:
    """A manager names somebody he wants on his team — still goes through the admin gate (spec
    §2); see onboarding.invite() for the whole reasoning. `principal.subject` is the token's
    `sub`, which — for this service's tenant — IS the identity person_id the affiliate row was
    minted under; there is no separate lookup table to keep in step."""
    try:
        out = await _svc(request).invite(
            inviter_person_id=principal.subject, phone=body.phone, name=body.name)
    except OnboardingRefused as exc:
        return _refused(exc)
    return {"ok": True, **out}


@router.get("/commissions", dependencies=[Depends(rate_limit)])
async def commissions(request: Request, principal: Principal = Depends(require_user)) -> dict:
    """His own commissions (core/commission.py — conversion only; renewal commissions retired
    2026-08-20). The read ITSELF
    advances any commission whose hold has lapsed from pending to confirmed
    (CommissionEngine.confirm_if_due, same lazy-check shape as everywhere else in this service) —
    so a marketer looking at his own dashboard is exactly the moment that matters, never a sweep
    running on nobody's clock."""
    onboarding = _svc(request)
    affiliate = await onboarding.me(principal.subject)
    if affiliate is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_AN_AFFILIATE")
    engine = request.app.state.container.commissions
    rows = await engine.of_affiliate(affiliate["id"])
    confirmed = [await engine.confirm_if_due(r.id) for r in rows]
    return {"commissions": [c.to_dict() for c in confirmed if c is not None]}


@router.get("/team", dependencies=[Depends(rate_limit)])
async def team(request: Request, principal: Principal = Depends(require_user)) -> Any:
    """spec §10: a manager's real revenue transparency — who is on his team AND what each of them
    actually earned, not just the roster invite() already let him build. A promoter calling this
    is not a manager: he simply has no children (parent_id never points AT him), so this answers
    an honest empty team rather than needing a role check to refuse anything."""
    onboarding = _svc(request)
    affiliate = await onboarding.me(principal.subject)
    if affiliate is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_AN_AFFILIATE")
    members = await onboarding.team(affiliate["id"])
    engine = request.app.state.container.commissions
    wafa = request.app.state.container.wafa
    my_own = await engine.revenue_for(affiliate["id"])   # his OWN direct referrals — spec §10's
                                                          # "مبيعاته المباشرة", not just his team's
    summary = await engine.team_summary([m["id"] for m in members])
    by_id = {m["affiliate_id"]: m for m in summary["members"]}
    empty = {"confirmed_halalas": 0, "pending_halalas": 0, "commission_count": 0,
            "shops": [], "total_net_revenue_minor": 0, "revenue_partial": False}
    # spec §8's own ask (Tamam, 2026-08-20): a manager backs a «دعم الوفاء» decision with the SAME
    # measurable numbers the system's own recommendation uses (WafaService.performance_for) —
    # never a second, driftable copy of that math.
    perf = {m["id"]: await wafa.performance_for(m["id"]) for m in members}
    merged = [{**m, **by_id.get(m["id"], empty), **perf[m["id"]]} for m in members]
    out = {"my_shops": my_own["shops"], "my_net_revenue_minor": my_own["total_net_revenue_minor"],
          "my_revenue_partial": my_own["revenue_partial"],
          "members": merged, "team_confirmed_halalas": summary["team_confirmed_halalas"],
          "team_pending_halalas": summary["team_pending_halalas"],
          "team_net_revenue_minor": summary["team_net_revenue_minor"],
          "team_revenue_partial": summary["team_revenue_partial"],
          "platform_revenue_enabled": affiliate["sees_platform_revenue"]}
    # spec §10's OPTIONAL whole-platform view (Tamam, 2026-08-20) — an admin-only per-manager
    # grant (Affiliate.sees_platform_revenue), OFF by default. The read itself is not free (it
    # walks every referral ever stamped, platform-wide), so it only happens for the handful of
    # managers this is actually turned on for — never computed and then hidden client-side.
    if affiliate["sees_platform_revenue"]:
        platform = await engine.platform_revenue()
        out["platform_net_revenue_minor"] = platform["total_net_revenue_minor"]
        out["platform_revenue_partial"] = platform["revenue_partial"]
    return out


@router.put("/payout-method", dependencies=[Depends(rate_limit)])
async def set_payout_method(request: Request, body: PayoutMethodIn,
                            principal: Principal = Depends(require_user)) -> Any:
    """spec §5, extended (Tamam, 2026-08-20): a bank IBAN or an intermediary payment platform
    (بحر or any other — `channel_name` is free text so a new one never needs a code change).
    Setting this does NOT touch any withdrawal already requested — see WithdrawalRequest's own
    note on why the method is copied, not re-read, at request time."""
    affiliate_id = await _my_affiliate_id(request, principal)
    try:
        out = await request.app.state.container.payouts.set_payout_method(
            affiliate_id, channel=body.channel, channel_name=body.channel_name,
            account_ref=body.account_ref)
    except PayoutError as exc:
        return _payout_refused(exc)
    return {"ok": True, **out}


@router.get("/balance", dependencies=[Depends(rate_limit)])
async def balance(request: Request, principal: Principal = Depends(require_user)) -> dict:
    affiliate_id = await _my_affiliate_id(request, principal)
    return await request.app.state.container.payouts.balance(affiliate_id)


@router.post("/withdrawals", dependencies=[Depends(rate_limit)])
async def request_withdrawal(request: Request,
                             principal: Principal = Depends(require_user)) -> Any:
    affiliate_id = await _my_affiliate_id(request, principal)
    try:
        out = await request.app.state.container.payouts.request_withdrawal(affiliate_id)
    except PayoutError as exc:
        return _payout_refused(exc)
    return {"ok": True, **out}


@router.get("/withdrawals", dependencies=[Depends(rate_limit)])
async def my_withdrawals(request: Request,
                         principal: Principal = Depends(require_user)) -> dict:
    affiliate_id = await _my_affiliate_id(request, principal)
    rows = await request.app.state.container.payouts.of_affiliate(affiliate_id)
    return {"withdrawals": [r.to_dict() for r in rows]}


@router.get("/withdrawals/{withdrawal_id}/receipt", dependencies=[Depends(rate_limit)])
async def my_withdrawal_receipt(request: Request, withdrawal_id: str,
                                principal: Principal = Depends(require_user)) -> Response:
    """spec §5: "يقدر المسوّق يعرضه لاحقاً" — his own proof of payment, not just the admin's.
    Ownership checked HERE, before touching the shared serving logic — a marketer must never
    reach another marketer's receipt by guessing an id."""
    affiliate_id = await _my_affiliate_id(request, principal)
    wd = await request.app.state.container.payouts.get(withdrawal_id)
    if wd is None or wd.affiliate_id != affiliate_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND")
    from app.api.v1.admin_payouts import _serve_receipt
    return await _serve_receipt(request, withdrawal_id)


# ── «برنامج دعم الوفاء» (spec §8) — the marketer's own side ─────────────────────────────────────

class WafaManagerDecisionIn(BaseModel):
    decision: str = Field(min_length=1, max_length=16)
    reason: str = Field(default="", max_length=500)


@router.post("/wafa-requests", dependencies=[Depends(rate_limit)])
async def request_wafa(request: Request,
                       principal: Principal = Depends(require_user)) -> Any:
    affiliate_id = await _my_affiliate_id(request, principal)
    try:
        out = await request.app.state.container.wafa.request(affiliate_id)
    except WafaError as exc:
        return _wafa_refused(exc)
    return {"ok": True, **out}


@router.get("/wafa-requests", dependencies=[Depends(rate_limit)])
async def my_wafa_requests(request: Request,
                           principal: Principal = Depends(require_user)) -> dict:
    affiliate_id = await _my_affiliate_id(request, principal)
    rows = await request.app.state.container.wafa.of_affiliate(affiliate_id)
    return {"wafa_requests": [r.to_dict() for r in rows]}


@router.get("/team/wafa-requests", dependencies=[Depends(rate_limit)])
async def team_wafa_requests(request: Request,
                             principal: Principal = Depends(require_user)) -> dict:
    """A manager's own review queue — every PENDING request from someone directly on his team
    (spec §8: he sees the performance and gives an advisory call before the platform's own
    binding one). Scoped by `parent_id`, same ownership boundary as GET /me/team."""
    onboarding = _svc(request)
    affiliate = await onboarding.me(principal.subject)
    if affiliate is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_AN_AFFILIATE")
    members = await onboarding.team(affiliate["id"])
    member_ids = {m["id"] for m in members}
    wafa = request.app.state.container.wafa
    pending = await wafa.list_pending(limit=500)
    mine = [r for r in pending if r.affiliate_id in member_ids]
    return {"wafa_requests": [r.to_dict() for r in mine]}


@router.post("/team/wafa-requests/{wafa_id}/decision", dependencies=[Depends(rate_limit)])
async def decide_team_wafa_request(request: Request, wafa_id: str, body: WafaManagerDecisionIn,
                                   principal: Principal = Depends(require_user)) -> Any:
    """The manager's ADVISORY call (spec §8) — never binding; see core/wafa.py's own module
    docstring on why the platform keeps the final word regardless of what he says here."""
    onboarding = _svc(request)
    affiliate = await onboarding.me(principal.subject)
    if affiliate is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_AN_AFFILIATE")
    wafa = request.app.state.container.wafa
    target = await wafa.get(wafa_id)
    members = await onboarding.team(affiliate["id"])
    if target is None or target.affiliate_id not in {m["id"] for m in members}:
        # Same ownership shape as my_withdrawal_receipt: a manager must never reach another
        # manager's team member's request by guessing an id.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND")
    try:
        out = await wafa.manager_decide(
            wafa_id, decision=body.decision, decided_by=affiliate["id"], reason=body.reason)
    except WafaError as exc:
        return _wafa_refused(exc)
    return {"ok": True, **out.to_dict()}
