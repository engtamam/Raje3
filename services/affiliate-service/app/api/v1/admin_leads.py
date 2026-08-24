# =============================================================================
# affiliate-service — the admin panel's cross-manager leads map (§6 + §9 scope note)
# -----------------------------------------------------------------------------
# §9 IS EXPLICIT: a manager sees only what HIS OWN search found — no cross-manager listing exists
# for the manager surface, on purpose. This route does not weaken that: it is an admin-only read
# (`platform.affiliates`, a capability no manager token carries), and it projects out exactly four
# geo/taxonomy fields — never `phone`, `name`, `decision_maker_*`, `address`, `notes`. A pin on a
# map answers "where is the market", never "who do I call".
# =============================================================================
from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.api.auth import Principal, require_user
from app.api.authz import require_capability
from app.api.ratelimit import rate_limit
from app.core.models import LEADS

router = APIRouter(prefix="/api/v1/admin/leads", tags=["affiliates-admin-leads"])

_MANAGE = require_capability("platform.affiliates")


@router.get("/geo", dependencies=[Depends(_MANAGE), Depends(rate_limit)])
async def leads_geo_map(request: Request,
                        principal: Principal = Depends(require_user)) -> dict:
    """Every located lead, across every manager — same cross-manager `scan_all` shape
    `admin_sectors.py::platform_sector_stats` already uses. Rows with no coordinates are dropped,
    not shown at (0, 0) — a lead found by keyword/city alone (before geocoding finished, or a
    source with no lat/lng) said nothing about a real point on the map."""
    rows = await request.app.state.container.datastore.scan_all(LEADS, 5000)
    points = [
        {"id": r.get("id", ""), "lat": r.get("lat", 0.0), "lng": r.get("lng", 0.0),
         "city": r.get("city", ""), "sector_code": r.get("sector_code", "")}
        for r in rows if r.get("lat") or r.get("lng")
    ]
    return {"points": points}
