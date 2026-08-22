# =============================================================================
# affiliate-service — what an affiliate does about HIS OWN team, not the platform's
# -----------------------------------------------------------------------------
# EVERY ROUTE HERE NOW CARRIES `_SELF` (`affiliates.self`, 2026-08-22) — the one capability every
# approved affiliate token holds, proving "is this a real, approved affiliate at all", the same
# shape as billing-service's `billing.self`/compliance-service's `compliance.self`. It answers
# NOTHING about which rows he may touch — that is still, and only, the ownership/role DATA check
# baked into each route (the same shape as operations.hire(): a shop owner needs no platform
# capability to hire his own staff; the question is "is this HIS shop", never "may owners in
# general do this"). `invite()` below is the clearest example: `_SELF` only proves he is signed
# in as an affiliate; onboarding.invite() still checks his own person_id resolves to an ACTIVE
# manager before anything happens — a capability would answer "may marketers in general invite",
# which is the wrong question.
#
# WHY THIS EXISTS AT ALL: before 2026-08-22 no route here checked a capability, because no role
# in this tenant had ever been bootstrapped with one (`onboarding.py::_ensure_tenant_ready` minted
# both roles with `"capabilities": []`, unnoticed because zero real affiliates had ever completed
# approval on the live server). `_SELF` closes that — see core/models.py's own note on
# `AFFILIATE_SELF`.
# =============================================================================
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from app.api.auth import Principal, require_user
from app.api.authz import require_capability
from app.api.ratelimit import rate_limit
from app.config import get_settings
from app.core.employment import EmploymentError
from app.core.lead_sourcing import LeadError, LeadSourcingService
from app.core.leads import LeadSourcingKeys
from app.core.models import AFFILIATE_SELF, AFFILIATES, REQUESTED, Affiliate
from app.core.onboarding import OnboardingRefused
from app.core.payouts import PayoutError
from app.core.secret_store import SecretError, SecretStore
from app.core.tickets import TicketError
from app.core.wafa import WafaError

router = APIRouter(prefix="/api/v1/affiliates/me", tags=["affiliates-self"])
_SELF = require_capability(AFFILIATE_SELF)


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


def _employment_refused(exc: EmploymentError) -> JSONResponse:
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


@router.get("", dependencies=[Depends(_SELF), Depends(rate_limit)])
async def me(request: Request, principal: Principal = Depends(require_user)) -> dict:
    """Who I am, and — since his own `id` IS his referral code (spec §1) — everything the console
    needs to show him his own link: `?aff=<id>` for a shop, `?ref=<id>` for another marketer
    applying under him."""
    out = await _svc(request).me(principal.subject)
    if out is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_AN_AFFILIATE")
    return out


@router.post("/invite", dependencies=[Depends(_SELF), Depends(rate_limit)])
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


@router.get("/commissions", dependencies=[Depends(_SELF), Depends(rate_limit)])
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


@router.get("/team", dependencies=[Depends(_SELF), Depends(rate_limit)])
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


@router.put("/payout-method", dependencies=[Depends(_SELF), Depends(rate_limit)])
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


@router.get("/balance", dependencies=[Depends(_SELF), Depends(rate_limit)])
async def balance(request: Request, principal: Principal = Depends(require_user)) -> dict:
    affiliate_id = await _my_affiliate_id(request, principal)
    return await request.app.state.container.payouts.balance(affiliate_id)


@router.post("/withdrawals", dependencies=[Depends(_SELF), Depends(rate_limit)])
async def request_withdrawal(request: Request,
                             principal: Principal = Depends(require_user)) -> Any:
    affiliate_id = await _my_affiliate_id(request, principal)
    try:
        out = await request.app.state.container.payouts.request_withdrawal(affiliate_id)
    except PayoutError as exc:
        return _payout_refused(exc)
    return {"ok": True, **out}


@router.get("/withdrawals", dependencies=[Depends(_SELF), Depends(rate_limit)])
async def my_withdrawals(request: Request,
                         principal: Principal = Depends(require_user)) -> dict:
    affiliate_id = await _my_affiliate_id(request, principal)
    rows = await request.app.state.container.payouts.of_affiliate(affiliate_id)
    return {"withdrawals": [r.to_dict() for r in rows]}


@router.get("/withdrawals/{withdrawal_id}/receipt", dependencies=[Depends(_SELF), Depends(rate_limit)])
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


@router.post("/wafa-requests", dependencies=[Depends(_SELF), Depends(rate_limit)])
async def request_wafa(request: Request,
                       principal: Principal = Depends(require_user)) -> Any:
    affiliate_id = await _my_affiliate_id(request, principal)
    try:
        out = await request.app.state.container.wafa.request(affiliate_id)
    except WafaError as exc:
        return _wafa_refused(exc)
    return {"ok": True, **out}


@router.get("/wafa-requests", dependencies=[Depends(_SELF), Depends(rate_limit)])
async def my_wafa_requests(request: Request,
                           principal: Principal = Depends(require_user)) -> dict:
    affiliate_id = await _my_affiliate_id(request, principal)
    rows = await request.app.state.container.wafa.of_affiliate(affiliate_id)
    return {"wafa_requests": [r.to_dict() for r in rows]}


@router.get("/wafa-eligibility", dependencies=[Depends(_SELF), Depends(rate_limit)])
async def my_wafa_eligibility(request: Request,
                              principal: Principal = Depends(require_user)) -> dict:
    """The read-only "how close am I" a promoter could never see before without actually filing
    a request and having it refused below threshold — see WafaService.eligibility_preview's own
    docstring."""
    affiliate_id = await _my_affiliate_id(request, principal)
    return await request.app.state.container.wafa.eligibility_preview(affiliate_id)


@router.get("/team/wafa-requests", dependencies=[Depends(_SELF), Depends(rate_limit)])
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


@router.post("/team/wafa-requests/{wafa_id}/decision", dependencies=[Depends(_SELF), Depends(rate_limit)])
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


# ── «رشّح نفسك لوظيفة» (spec §8) — the marketer's own side ─────────────────────────────────────

@router.post("/employment-requests", dependencies=[Depends(_SELF), Depends(rate_limit)])
async def request_employment(request: Request,
                             principal: Principal = Depends(require_user)) -> Any:
    affiliate_id = await _my_affiliate_id(request, principal)
    try:
        out = await request.app.state.container.employment.request(affiliate_id)
    except EmploymentError as exc:
        return _employment_refused(exc)
    return {"ok": True, **out}


@router.get("/employment-requests", dependencies=[Depends(_SELF), Depends(rate_limit)])
async def my_employment_requests(request: Request,
                                 principal: Principal = Depends(require_user)) -> dict:
    affiliate_id = await _my_affiliate_id(request, principal)
    rows = await request.app.state.container.employment.of_affiliate(affiliate_id)
    return {"employment_requests": [r.to_dict() for r in rows]}


@router.get("/employment-eligibility", dependencies=[Depends(_SELF), Depends(rate_limit)])
async def my_employment_eligibility(request: Request,
                                    principal: Principal = Depends(require_user)) -> dict:
    """Same gap, same fix as /wafa-eligibility — see EmploymentService.eligibility_preview."""
    affiliate_id = await _my_affiliate_id(request, principal)
    return await request.app.state.container.employment.eligibility_preview(affiliate_id)


# ── §٦ Lead Sourcing — a manager's OWN Google Places API key (BYOK, Tamam 2026-08-20) ──────────

class PlacesApiKeyIn(BaseModel):
    api_key: str = Field(min_length=1, max_length=512)


def _leads_keys(request: Request) -> LeadSourcingKeys:
    s = get_settings()
    if not s.SECRETS_KEK:
        # Same refusal shape as operator.py's own _secret_store — no KEK, nothing to seal with,
        # storing the key anyway is the one outcome that must never happen.
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "SECRETS_UNAVAILABLE")
    store = SecretStore(request.app.state.container.datastore, s.SECRETS_KEK,
                        rotation_window_s=s.SECRETS_ROTATION_WINDOW_SECONDS)
    return LeadSourcingKeys(secret_store=store, fallback_api_key=s.LEADS_PLACES_API_KEY_FALLBACK)


async def _my_manager_affiliate(request: Request, principal: Principal) -> dict[str, Any]:
    """§٦: "للمدير فقط" — lead sourcing (and the API key that powers it) is not a promoter's
    concern. A data check on the caller's own role, same shape as invite()'s own
    `managers_only` — never a capability, since the question is "is the caller himself a
    manager", not "may managers in general do this"."""
    affiliate = await _svc(request).me(principal.subject)
    if affiliate is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_AN_AFFILIATE")
    if affiliate["role"] != get_settings().AFFILIATE_MANAGER_ROLE:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "MANAGERS_ONLY")
    return affiliate


@router.put("/places-api-key", dependencies=[Depends(_SELF), Depends(rate_limit)])
async def set_places_api_key(request: Request, body: PlacesApiKeyIn,
                             principal: Principal = Depends(require_user)) -> Any:
    affiliate = await _my_manager_affiliate(request, principal)
    # AUDITED BEFORE THE WRITE (operator.py's own convention for exactly this family): the old
    # key is overwritten by the action itself, so an unrecorded rotation is unreconstructable.
    await request.app.state.auditor.record(
        "affiliate.places_api_key_set", actor=affiliate["id"], tenant="",
        resource=f"affiliate:{affiliate['id']}",
        ip=request.client.host if request.client else "")
    try:
        info = await _leads_keys(request).set_key(
            affiliate["id"], value=body.api_key, actor_ref=affiliate["id"])
    except SecretError as exc:
        return JSONResponse(status_code=400, content={"ok": False, "message": str(exc)})
    return {"ok": True, "hint": info.hint, "set_at": info.set_at}


@router.get("/places-api-key", dependencies=[Depends(_SELF), Depends(rate_limit)])
async def get_places_api_key(request: Request,
                             principal: Principal = Depends(require_user)) -> dict:
    """A hint only — same write-only guarantee as operator.py's own secrets. Never the value."""
    affiliate = await _my_manager_affiliate(request, principal)
    info = await _leads_keys(request).info(affiliate["id"])
    if info is None:
        return {"set": False}
    return {"set": True, "hint": info.hint, "set_at": info.set_at}


@router.delete("/places-api-key", dependencies=[Depends(_SELF), Depends(rate_limit)])
async def clear_places_api_key(request: Request,
                               principal: Principal = Depends(require_user)) -> dict:
    affiliate = await _my_manager_affiliate(request, principal)
    await request.app.state.auditor.record(
        "affiliate.places_api_key_cleared", actor=affiliate["id"], tenant="",
        resource=f"affiliate:{affiliate['id']}",
        ip=request.client.host if request.client else "")
    cleared = await _leads_keys(request).clear_key(affiliate["id"])
    return {"ok": True, "cleared": cleared}


# ── §٦ Lead Sourcing — the search itself + assignment ───────────────────────────────────────────

class CityIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    region: str = Field(default="", max_length=100)
    lat: float
    lng: float
    w_km: float = Field(gt=0, le=500)
    h_km: float = Field(gt=0, le=500)


class SearchIn(BaseModel):
    place_type: str = Field(default="", max_length=100)
    #: Sector.code, from the managed taxonomy (GET /me/sectors) — Tamam, 2026-08-20: "قطاعات...
    #: ما لها دخل بالمرادفات". The analytics column; never typed free, always picked.
    sector_code: str = Field(min_length=1, max_length=64)
    #: Synonyms searched TOGETHER in one job (places_scraper_v2.py's own multi-keyword loop —
    #: "صالون نسائي"/"مركز تجميل نسائي"/... found the same businesses under different listings).
    #: The API's own ceiling stays generous (20); Tamam, 2026-08-20: the CONSOLE limits its own
    #: form to 6 fields (each extra keyword multiplies the grid's own request count by one more
    #: full pass) — a UI/UX guard, not a hard API limit a future caller might need past.
    keywords: list[str] = Field(min_length=1, max_length=20)
    radius_km: float = Field(default=5.0, gt=0, le=50)
    cities: list[CityIn] = Field(min_length=1, max_length=30)
    apply_filter: bool = False
    filter_indicators: list[str] = Field(default_factory=list)


class AssignIn(BaseModel):
    promoter_id: str = Field(min_length=1, max_length=100)


def _lead_sourcing(request: Request) -> LeadSourcingService:
    """`keys=None` is deliberate and safe: every route in this file starts/reads/assigns a job
    but never advances one (LeadSourcingService.step, the only method that resolves an API key,
    is reached only from POST /internal/leads/tick). Requiring SECRETS_KEK here would 503 a
    promoter's own GET /me/leads for a reason that has nothing to do with him."""
    return LeadSourcingService(store=request.app.state.container.datastore, keys=None,
                               onboarding=_svc(request),
                               sectors=request.app.state.container.sectors)


def _lead_refused(exc: LeadError) -> JSONResponse:
    body: dict[str, Any] = {"ok": False, "message": str(exc)}
    if getattr(exc, "reason", ""):
        body["reason"] = exc.reason
    return JSONResponse(status_code=400, content=body)


@router.post("/leads/search", dependencies=[Depends(_SELF), Depends(rate_limit)])
async def start_lead_search(request: Request, body: SearchIn,
                            principal: Principal = Depends(require_user)) -> Any:
    """§٦: a manager starts a grid search — real runtime is HOURS (places_scraper_v2.py's own
    estimate), so this returns a job id immediately; POST /internal/leads/tick advances it on a
    schedule. See core/lead_sourcing.py's own module docstring."""
    affiliate = await _my_manager_affiliate(request, principal)
    try:
        out = await _lead_sourcing(request).start_job(
            affiliate["id"], place_type=body.place_type, sector_code=body.sector_code,
            keywords=body.keywords, radius_km=body.radius_km,
            cities=[c.model_dump() for c in body.cities],
            apply_filter=body.apply_filter, filter_indicators=body.filter_indicators)
    except LeadError as exc:
        return _lead_refused(exc)
    return {"ok": True, **out}


@router.get("/leads/search", dependencies=[Depends(_SELF), Depends(rate_limit)])
async def my_lead_searches(request: Request,
                           principal: Principal = Depends(require_user)) -> dict:
    affiliate = await _my_manager_affiliate(request, principal)
    jobs = await _lead_sourcing(request).jobs_of(affiliate["id"])
    return {"jobs": [j.to_dict() for j in jobs]}


@router.get("/leads/search/{job_id}", dependencies=[Depends(_SELF), Depends(rate_limit)])
async def lead_search_status(request: Request, job_id: str,
                             principal: Principal = Depends(require_user)) -> dict:
    """§٦: "المدير يشوف تقدّم البحث بالخلفية، لا ينتظره" — polled from here."""
    affiliate = await _my_manager_affiliate(request, principal)
    job = await _lead_sourcing(request).get_job(job_id)
    if job is None or job.affiliate_id != affiliate["id"]:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND")
    return job.to_dict()


@router.get("/leads", dependencies=[Depends(_SELF), Depends(rate_limit)])
async def my_leads(request: Request, principal: Principal = Depends(require_user)) -> dict:
    """spec §٩: "كل مسوّق يشوف فقط العملاء المحتملين المُسنَدين له، لا القائمة الكاملة" — a
    promoter sees what was ASSIGNED to him; a manager sees what HIS OWN search found (still
    pending assignment or already handed out), never each other's. One route, branched on the
    caller's own role — the same "is the caller himself an X" data check as everywhere else in
    this file, never a capability."""
    affiliate = await _svc(request).me(principal.subject)
    if affiliate is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_AN_AFFILIATE")
    svc = _lead_sourcing(request)
    if affiliate["role"] == get_settings().AFFILIATE_MANAGER_ROLE:
        leads = await svc.leads_of_manager(affiliate["id"])
    else:
        leads = await svc.leads_assigned_to(affiliate["id"])
    return {"leads": [l.to_dict() for l in leads]}


@router.get("/leads/stale", dependencies=[Depends(_SELF), Depends(rate_limit)])
async def my_stale_leads(request: Request, stale_after_days: int = 3,
                         principal: Principal = Depends(require_user)) -> dict:
    """The home screen's "بانتظارك الآن" candidate — leads assigned to the CALLER with no
    activity in `stale_after_days`. Deliberately his own assigned leads only (same scope as
    `leads_assigned_to`, never the whole team) — a manager rarely holds leads assigned to
    himself the way a promoter does, so this answers honestly for whichever role asks it rather
    than silently becoming a team-wide sweep."""
    affiliate_id = await _my_affiliate_id(request, principal)
    leads = await _lead_sourcing(request).stale_leads(
        affiliate_id, stale_after_seconds=max(1, stale_after_days) * 86400)
    return {"leads": [l.to_dict() for l in leads]}


@router.post("/leads/{lead_id}/assign", dependencies=[Depends(_SELF), Depends(rate_limit)])
async def assign_lead(request: Request, lead_id: str, body: AssignIn,
                      principal: Principal = Depends(require_user)) -> Any:
    affiliate = await _my_manager_affiliate(request, principal)
    try:
        out = await _lead_sourcing(request).assign(
            lead_id, manager_id=affiliate["id"], promoter_id=body.promoter_id)
    except LeadError as exc:
        return _lead_refused(exc)
    return {"ok": True, **out.to_dict()}


class SetLeadStatusIn(BaseModel):
    status: str = Field(min_length=1, max_length=32)
    text: str = Field(default="", max_length=1000)


@router.post("/leads/{lead_id}/status", dependencies=[Depends(_SELF), Depends(rate_limit)])
async def set_lead_status(request: Request, lead_id: str, body: SetLeadStatusIn,
                          principal: Principal = Depends(require_user)) -> Any:
    """Tamam, 2026-08-20: a real follow-up pipeline, so the marketing team actually tracks who
    they contacted and how it went — see core/lead_sourcing.py::set_status for the exact
    ownership rule (the assigned promoter, or his own manager, never anyone else)."""
    affiliate = await _svc(request).me(principal.subject)
    if affiliate is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_AN_AFFILIATE")
    try:
        out = await _lead_sourcing(request).set_status(
            lead_id, affiliate_id=affiliate["id"], new_status=body.status, text=body.text)
    except LeadError as exc:
        return _lead_refused(exc)
    return {"ok": True, **out.to_dict()}


class LinkRegistrationIn(BaseModel):
    tenant: str = Field(min_length=1, max_length=128)


@router.post("/leads/{lead_id}/link-registration", dependencies=[Depends(_SELF), Depends(rate_limit)])
async def link_lead_registration(request: Request, lead_id: str, body: LinkRegistrationIn,
                                 principal: Principal = Depends(require_user)) -> Any:
    """Tamam, 2026-08-20: a shop sometimes signs up with a phone Google never had — the marketer
    himself says "this lead became THIS real shop", by hand, from HIS OWN referrals only. See
    core/lead_sourcing.py::link_registration for why nothing here is inferred automatically."""
    affiliate = await _svc(request).me(principal.subject)
    if affiliate is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_AN_AFFILIATE")
    try:
        out = await _lead_sourcing(request).link_registration(
            lead_id, affiliate_id=affiliate["id"], tenant=body.tenant,
            referrals=request.app.state.container.referrals)
    except LeadError as exc:
        return _lead_refused(exc)
    return {"ok": True, **out.to_dict()}


@router.get("/leads/sector-stats", dependencies=[Depends(_SELF), Depends(rate_limit)])
async def my_lead_sector_stats(request: Request,
                               principal: Principal = Depends(require_user)) -> dict:
    """§٦'s own point: sector × city counts for a data-driven dashboard — a manager's own finds
    only (spec §9's own scoping)."""
    affiliate = await _my_manager_affiliate(request, principal)
    stats = await _lead_sourcing(request).sector_stats(affiliate_id=affiliate["id"])
    return {"stats": stats}


@router.get("/sectors", dependencies=[Depends(_SELF), Depends(rate_limit)])
async def list_active_sectors(request: Request,
                              principal: Principal = Depends(require_user)) -> dict:
    """The managed taxonomy — read-only here, for the search form's own picker. Any signed-in
    affiliate may read it (it names no one, it is not sensitive); only an admin may change it
    (see api/v1/admin.py)."""
    sectors = await request.app.state.container.sectors.list(active_only=True)
    return {"sectors": [s.to_dict() for s in sectors]}


# ── §١٣: a shop's tickets, consent-scoped to the marketer who referred it ──────────────────────

class ReplyIn(BaseModel):
    body: str = Field(min_length=1, max_length=20_000)


class OpenTicketIn(BaseModel):
    type: str = Field(min_length=1, max_length=64)
    subject: str = Field(default="", max_length=512)
    body: str = Field(default="", max_length=20_000)
    priority: str = Field(default="normal", max_length=16)


def _ticket_refused(exc: TicketError) -> JSONResponse:
    body: dict[str, Any] = {"ok": False, "message": str(exc)}
    if getattr(exc, "reason", ""):
        body["reason"] = exc.reason
    status_code = 404 if exc.reason == "not_found" else 400
    return JSONResponse(status_code=status_code, content=body)


async def _my_shop_grant(request: Request, principal: Principal, tenant: str) -> str:
    """spec §13: a marketer reaches only a shop THAT REFERRED THROUGH HIM — ownership, checked
    against ReferralRegistry's own record, never a capability. Returns his own affiliate id (the
    grantee ticket-service already knows). A tenant he did not bring is 404, same shape as the
    lead/wafa ownership checks elsewhere in this file."""
    affiliate = await _svc(request).me(principal.subject)
    if affiliate is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_AN_AFFILIATE")
    referral = await request.app.state.container.referrals.of_tenant(tenant)
    if referral is None or referral.affiliate_id != affiliate["id"]:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND")
    return affiliate["id"]


def _ticket_reader(request: Request):
    reader = request.app.state.container.tickets
    if reader is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "TICKETS_UNAVAILABLE")
    return reader


@router.get("/shops/{tenant}/tickets", dependencies=[Depends(_SELF), Depends(rate_limit)])
async def shop_tickets(request: Request, tenant: str,
                       principal: Principal = Depends(require_user)) -> Any:
    grantee = await _my_shop_grant(request, principal, tenant)
    try:
        tickets = await _ticket_reader(request).list_tickets(tenant=tenant, grantee=grantee)
    except TicketError as exc:
        return _ticket_refused(exc)
    return {"tickets": tickets}


@router.get("/shops/{tenant}/tickets/{ticket_id}", dependencies=[Depends(_SELF), Depends(rate_limit)])
async def shop_ticket(request: Request, tenant: str, ticket_id: str,
                      principal: Principal = Depends(require_user)) -> Any:
    grantee = await _my_shop_grant(request, principal, tenant)
    try:
        out = await _ticket_reader(request).get_ticket(
            tenant=tenant, grantee=grantee, ticket_id=ticket_id)
    except TicketError as exc:
        return _ticket_refused(exc)
    return out


@router.post("/shops/{tenant}/tickets", status_code=201, dependencies=[Depends(_SELF), Depends(rate_limit)])
async def open_shop_ticket(request: Request, tenant: str, body: OpenTicketIn,
                           principal: Principal = Depends(require_user)) -> Any:
    grantee = await _my_shop_grant(request, principal, tenant)
    try:
        out = await _ticket_reader(request).open_ticket(
            tenant=tenant, grantee=grantee, type=body.type, subject=body.subject,
            body=body.body, priority=body.priority)
    except TicketError as exc:
        return _ticket_refused(exc)
    await request.app.state.auditor.record(
        "affiliate.shop_ticket_opened", actor=grantee, tenant=tenant,
        resource=f"ticket:{out.get('id', '')}", ip=request.client.host if request.client else "")
    return out


@router.post("/shops/{tenant}/tickets/{ticket_id}/replies", status_code=201,
             dependencies=[Depends(_SELF), Depends(rate_limit)])
async def reply_shop_ticket(request: Request, tenant: str, ticket_id: str, body: ReplyIn,
                            principal: Principal = Depends(require_user)) -> Any:
    """spec §13's own point: a shop raises a problem, the marketer who brought it replies and
    actually engages — not just watches a KPI number."""
    grantee = await _my_shop_grant(request, principal, tenant)
    try:
        out = await _ticket_reader(request).reply(
            tenant=tenant, grantee=grantee, ticket_id=ticket_id, body=body.body)
    except TicketError as exc:
        return _ticket_refused(exc)
    await request.app.state.auditor.record(
        "affiliate.shop_ticket_replied", actor=grantee, tenant=tenant,
        resource=f"ticket:{ticket_id}", ip=request.client.host if request.client else "")
    return out


# ── the home screen — ONE call instead of six-to-eight ──────────────────────────────────────────
@router.get("/home", dependencies=[Depends(_SELF), Depends(rate_limit)])
async def home(request: Request, principal: Principal = Depends(require_user)) -> dict:
    """Composite, server-side fan-out — the gap the design research kept surfacing: every number
    a home screen needs already exists behind its OWN route, but a client assembling it had to
    make six to eight separate calls. This does the fan-out here instead, once, so the screen
    itself stays a single request.

    Every figure below is read fresh from its owning service — nothing here is a stored
    duplicate of another route's answer, and nothing here is a NEW fact this service didn't
    already know how to compute."""
    onboarding = _svc(request)
    affiliate = await onboarding.me(principal.subject)
    if affiliate is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_AN_AFFILIATE")
    aff_id = affiliate["id"]
    is_manager = affiliate["role"] == get_settings().AFFILIATE_MANAGER_ROLE
    c = request.app.state.container

    # `onboarding.me()` deliberately answers with NAMED FIELDS ONLY (its own docstring: never
    # `.to_dict()`, which carries `invite_token`) — `payout_channel` is not one of them, so it is
    # read here straight off the row, the same way `set_payout_method`'s own route would.
    raw = await c.datastore.get(AFFILIATES, aff_id)
    payout_channel = Affiliate.from_dict(raw).payout_channel if raw else ""

    balance = await c.payouts.balance(aff_id)
    withdrawals = await c.payouts.of_affiliate(aff_id)
    stale = await _lead_sourcing(request).stale_leads(aff_id, stale_after_seconds=3 * 86400)
    wafa_elig = await c.wafa.eligibility_preview(aff_id)
    employment_elig = await c.employment.eligibility_preview(aff_id)
    # stats() already returns its rows sorted by -advance_rate — the first one IS the answer to
    # "which of MY OWN templates actually moves a lead forward the most", no re-sorting needed.
    my_template_stats = await c.template_uses.stats(used_by=aff_id)
    top_template = my_template_stats[0] if my_template_stats else None

    out: dict[str, Any] = {
        "affiliate": {"id": aff_id, "name": affiliate["name"], "role": affiliate["role"]},
        "balance": balance,
        "payout_method_set": bool(payout_channel),
        "stale_leads_count": len(stale),
        "stale_leads": [l.to_dict() for l in stale[:10]],
        "wafa_eligibility": wafa_elig,
        "employment_eligibility": employment_elig,
        "top_template_this_period": top_template,
    }
    if any(w.status == REQUESTED for w in withdrawals):
        out["pending_withdrawal"] = True

    if is_manager:
        members = await onboarding.team(aff_id)
        summary = await c.commissions.team_summary([m["id"] for m in members])
        pending_wafa = await c.wafa.list_pending(limit=500)
        member_ids = {m["id"] for m in members}
        out["team"] = {
            "member_count": len(members),
            "team_confirmed_halalas": summary["team_confirmed_halalas"],
            "team_pending_halalas": summary["team_pending_halalas"],
            "pending_wafa_requests_count": sum(1 for r in pending_wafa
                                               if r.affiliate_id in member_ids),
        }
        # NEVER 503 THE WHOLE HOME SCREEN over an unconfigured Places API key subsystem — the
        # same reason _leads_keys() itself was written to refuse loudly on its OWN dedicated
        # route (no KEK means nothing to seal a key with), but a home screen's job is to degrade,
        # not to go dark because one manager-only widget's dependency is missing.
        try:
            key_info = await _leads_keys(request).info(aff_id)
            out["places_api_key_set"] = key_info is not None
        except HTTPException:
            out["places_api_key_set"] = None
    return out
