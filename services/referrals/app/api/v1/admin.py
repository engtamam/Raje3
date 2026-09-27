"""The shop's own admin surface (spec §2/§3/§4) — everything an owner does to configure a referral
campaign. Same shape as every other per-shop admin route in this fleet (`coworking.manage`,
`campaigns.manage`, ...): a token belonging to a person at THIS shop, never a platform operator.
`principal.tenant` is what scopes every read and write here to that one shop; nothing in this file
ever accepts a tenant from the request body.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field
from starlette.responses import JSONResponse

from app.api.auth import Principal, require_user
from app.api.authz import require_capability
from app.api.ratelimit import rate_limit
from app.core.campaigns import CampaignError

router = APIRouter(prefix="/api/v1/referrals", tags=["referrals-admin"])

_MANAGE = require_capability("referrals.manage")


def _tenant(principal: Principal) -> str:
    return principal.tenant or ""


def _refuse(reason: str, *, status_code: int = status.HTTP_400_BAD_REQUEST) -> JSONResponse:
    return JSONResponse({"error": "BAD_REQUEST", "reason": reason}, status_code=status_code)


class CampaignIn(BaseModel):
    mode: str
    reward_type: str
    reward_params: dict = Field(default_factory=dict)
    new_customer_reward_type: str
    new_customer_reward_params: dict = Field(default_factory=dict)
    x_times_limit: int = Field(default=0, ge=0)
    min_spend_minor: int = Field(default=0, ge=0)
    usage_cap_period: str = Field(default="", max_length=16)
    usage_cap_limit: int = Field(default=0, ge=0)
    # See core/models.py's own CAP_SCOPE_CAMPAIGN/CAP_SCOPE_LIFETIME — default keeps today's
    # behaviour (a new campaign resets the count) for every shop that never sets this.
    cap_scope: str = Field(default="campaign", max_length=16)
    # Who may redeem at all — "new" (default, today's unconditional rule) / "max_visits" / "open".
    # See core/models.py's own ELIGIBILITY_* constants.
    beneficiary_eligibility: str = Field(default="new", max_length=16)
    beneficiary_max_visits: int = Field(default=0, ge=0)


@router.post("/campaigns", dependencies=[Depends(rate_limit)])
async def create_campaign(request: Request, body: CampaignIn,
                          principal: Principal = Depends(_MANAGE)) -> dict:
    if not principal.tenant:
        return _refuse("هذا الاعتماد غير مرتبط بمنشأة.", status_code=status.HTTP_403_FORBIDDEN)
    c = request.app.state.container
    try:
        campaign = await c.campaigns.create(
            _tenant(principal), mode=body.mode, reward_type=body.reward_type,
            reward_params=body.reward_params,
            new_customer_reward_type=body.new_customer_reward_type,
            new_customer_reward_params=body.new_customer_reward_params,
            x_times_limit=body.x_times_limit, min_spend_minor=body.min_spend_minor,
            usage_cap_period=body.usage_cap_period, usage_cap_limit=body.usage_cap_limit,
            cap_scope=body.cap_scope,
            beneficiary_eligibility=body.beneficiary_eligibility,
            beneficiary_max_visits=body.beneficiary_max_visits,
        )
    except CampaignError as exc:
        return _refuse(str(exc))
    return campaign.to_dict()


@router.get("/campaigns", dependencies=[Depends(rate_limit)])
async def list_campaigns(request: Request, active_only: bool = False,
                         principal: Principal = Depends(_MANAGE)) -> dict:
    if not principal.tenant:
        return _refuse("هذا الاعتماد غير مرتبط بمنشأة.", status_code=status.HTTP_403_FORBIDDEN)
    c = request.app.state.container
    rows = await c.campaigns.list(_tenant(principal), active_only=active_only)
    return {"campaigns": [r.to_dict() for r in rows]}


@router.get("/campaigns/{campaign_id}", dependencies=[Depends(rate_limit)])
async def get_campaign(request: Request, campaign_id: str,
                       principal: Principal = Depends(_MANAGE)) -> dict:
    if not principal.tenant:
        return _refuse("هذا الاعتماد غير مرتبط بمنشأة.", status_code=status.HTTP_403_FORBIDDEN)
    c = request.app.state.container
    campaign = await c.campaigns.get(_tenant(principal), campaign_id)
    if campaign is None:
        return _refuse("الحملة غير موجودة", status_code=status.HTTP_404_NOT_FOUND)
    return campaign.to_dict()


class ActiveIn(BaseModel):
    active: bool


@router.put("/campaigns/{campaign_id}/active", dependencies=[Depends(rate_limit)])
async def set_campaign_active(request: Request, campaign_id: str, body: ActiveIn,
                              principal: Principal = Depends(_MANAGE)) -> dict:
    if not principal.tenant:
        return _refuse("هذا الاعتماد غير مرتبط بمنشأة.", status_code=status.HTTP_403_FORBIDDEN)
    c = request.app.state.container
    try:
        campaign = await c.campaigns.set_active(_tenant(principal), campaign_id, active=body.active)
    except CampaignError as exc:
        return _refuse(str(exc), status_code=status.HTTP_404_NOT_FOUND)
    return campaign.to_dict()
