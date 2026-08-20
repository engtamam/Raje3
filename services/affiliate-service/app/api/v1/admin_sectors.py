# =============================================================================
# affiliate-service — §٦'s managed sector taxonomy: the admin's side
# -----------------------------------------------------------------------------
# `platform.affiliates` — same capability as approving an applicant / the platform-revenue
# toggle: "who runs the affiliate program's own configuration", not a money-moving action.
# =============================================================================
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.api.auth import Principal, require_user
from app.api.authz import require_capability
from app.api.ratelimit import rate_limit
from app.config import get_settings
from app.core.lead_sourcing import LeadSourcingService
from app.core.pii import subject_ref

router = APIRouter(prefix="/api/v1/admin/sectors", tags=["affiliates-admin-sectors"])

_MANAGE = require_capability("platform.affiliates")


class SectorIn(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)


def _actor(principal: Principal) -> str:
    s = get_settings()
    if not s.PII_SALT:
        return ""
    return subject_ref(s.PII_SALT, principal.tenant or "", principal.subject)


@router.get("", dependencies=[Depends(_MANAGE), Depends(rate_limit)])
async def list_sectors(request: Request,
                       principal: Principal = Depends(require_user)) -> dict:
    """Every sector, active and deactivated — the admin's own management view. Marketers read
    the active-only subset instead (GET /api/v1/affiliates/me/sectors)."""
    sectors = await request.app.state.container.sectors.list(active_only=False)
    return {"sectors": [s.to_dict() for s in sectors]}


@router.put("", dependencies=[Depends(_MANAGE), Depends(rate_limit)])
async def create_sector(request: Request, body: SectorIn,
                        principal: Principal = Depends(require_user)) -> Any:
    """Create a new sector, or re-activate/rename an existing code — see SectorService.create's
    own upsert reasoning. Not critical to audit: a mislabelled sector costs nothing an admin
    cannot fix by calling this again."""
    await request.app.state.auditor.record(
        "affiliate.sector_changed", actor=_actor(principal), tenant="",
        resource=f"sector:{body.code}", ip=request.client.host if request.client else "",
        metadata={"name": body.name, "active": True})
    sector = await request.app.state.container.sectors.create(code=body.code, name=body.name)
    return {"ok": True, **sector.to_dict()}


@router.delete("/{code}", dependencies=[Depends(_MANAGE), Depends(rate_limit)])
async def deactivate_sector(request: Request, code: str,
                            principal: Principal = Depends(require_user)) -> dict:
    """Deactivate, never delete — every historical Lead stamped with this code keeps a legible
    label forever (see Sector's own module docstring)."""
    await request.app.state.auditor.record(
        "affiliate.sector_changed", actor=_actor(principal), tenant="",
        resource=f"sector:{code}", ip=request.client.host if request.client else "",
        metadata={"active": False})
    deactivated = await request.app.state.container.sectors.deactivate(code)
    return {"ok": True, "deactivated": deactivated}


@router.get("/stats", dependencies=[Depends(_MANAGE), Depends(rate_limit)])
async def platform_sector_stats(request: Request,
                                principal: Principal = Depends(require_user)) -> dict:
    """The platform-wide sector × city dashboard's own data source — every manager's finds, not
    scoped to one (spec §٦'s own point: "نعرف وين السوق مطلوب... نركز عليه"). `keys=None` is
    safe here too — this read never advances a search job (see affiliate_self.py's own
    `_lead_sourcing` for why that is the only method that needs one)."""
    c = request.app.state.container
    svc = LeadSourcingService(store=c.datastore, keys=None, onboarding=c.onboarding,
                              sectors=c.sectors)
    stats = await svc.sector_stats()
    return {"stats": stats}
