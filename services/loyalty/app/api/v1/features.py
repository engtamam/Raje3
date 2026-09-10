"""«ايش فيه هذا التطبيق فعلاً» — the app-store card's own content, not the operational surface.

Same reasoning as bookings-service's own `api/v1/features.py`: a shop deciding WHETHER to buy
برنامج النقاط has to be able to read what it would get, so this carries no `loyalty.*` capability
and no licence check at all — only `require_user`, the same "signed in, nothing more" bar. Not
tenant-scoped either: the catalog is identical for every shop, real code shipped once.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.auth import require_user
from app.api.ratelimit import rate_limit
from app.core.features import public_features

router = APIRouter(prefix="/loyalty", tags=["loyalty"])


@router.get("/features", dependencies=[Depends(rate_limit)])
async def list_features(principal=Depends(require_user)) -> dict:
    return {"features": public_features()}
