"""Phase 5a of docs/خطة-تطبيق-الإحالة-والمسوقين-2026-09-27.md — read-only performance reporting.
See core/referral_reports.py's own module docstring for what each figure means and why the metrics
NOT reported here (viral/K-factor, clicks/EPC, lifetime-value uplift) are a deliberate omission,
not a gap. `operations.read` gates every route — nothing here ever writes anything.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.api.auth import Principal
from app.api.authz import require_capability
from app.api.ratelimit import rate_limit

router = APIRouter(prefix="/referrals/reports", tags=["referral-reports"])

_READ = require_capability("operations.read")


def _tenant(principal: Principal) -> str:
    return principal.tenant or ""


@router.get("/summary", dependencies=[Depends(rate_limit)])
async def referral_summary(request: Request, since: int = 0, until: int | None = None,
                          principal: Principal = Depends(_READ)) -> dict:
    reports = request.app.state.container.referral_reports
    return await reports.summary(_tenant(principal), since=since, until=until)


@router.get("/leaderboard", dependencies=[Depends(rate_limit)])
async def referral_leaderboard(request: Request, since: int = 0, until: int | None = None,
                              limit: int = 20,
                              principal: Principal = Depends(_READ)) -> dict:
    reports = request.app.state.container.referral_reports
    # A hostile/huge limit must never turn one read into a full unbounded scan cost — the
    # underlying grants scan itself is already capped, but the RESPONSE size is a separate limit
    # a caller controls directly, so it gets its own ceiling too.
    limit = max(1, min(limit, 200))
    rows = await reports.leaderboard(_tenant(principal), since=since, until=until, limit=limit)
    return {"leaderboard": rows}


@router.get("/campaigns", dependencies=[Depends(rate_limit)])
async def referral_campaign_breakdown(request: Request, since: int = 0, until: int | None = None,
                                     principal: Principal = Depends(_READ)) -> dict:
    reports = request.app.state.container.referral_reports
    rows = await reports.campaign_breakdown(_tenant(principal), since=since, until=until)
    return {"campaigns": rows}


@router.get("/affiliates", dependencies=[Depends(rate_limit)])
async def referral_affiliate_breakdown(request: Request,
                                      principal: Principal = Depends(_READ)) -> dict:
    reports = request.app.state.container.referral_reports
    rows = await reports.affiliate_breakdown(_tenant(principal))
    return {"affiliates": rows}
