"""«ايش فيه هذا التطبيق فعلاً» — the app-store card's own content, not the operational surface.

Same reasoning as bookings-service's own `api/v1/features.py`: no `insights.*` capability and no
licence check — only `require_user`. Not tenant-scoped: the catalog is identical for every shop.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.auth import require_user
from app.api.ratelimit import rate_limit
from app.core.features import public_features

router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("/features", dependencies=[Depends(rate_limit)])
async def list_features(principal=Depends(require_user)) -> dict:
    return {"features": public_features()}
