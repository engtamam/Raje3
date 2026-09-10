"""«ايش فيه هذا التطبيق فعلاً» — the app-store catalog read, not the operational grid.

WHY ITS OWN ROUTER, SEPARATE FROM `bookings.py`. Everything in that file needs `bookings.read`/
`bookings.write` — capabilities a shop only holds once it has ALREADY bought the app. This route
is the opposite case on purpose: a shop deciding WHETHER to buy has to be able to read what it
would get, so it carries no `bookings.*` capability and no licence check at all — same posture as
`deploy/seed/plans.json`'s own price list, readable by anyone signed in regardless of what they
own. See `app/core/features.py`'s own docstring for the content itself and why it lives in code.

NOT TENANT-SCOPED, DELIBERATELY. The catalog is identical for every shop — real code shipped once,
not a per-tenant configuration — so this never reads `principal.tenant` at all; only `require_user`
guards it, the same "signed in, nothing more" bar `no_subscription_needed`-style routes hold
elsewhere in this fleet.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.auth import require_user
from app.api.ratelimit import rate_limit
from app.core.features import public_features

router = APIRouter(prefix="/api/v1/bookings", tags=["bookings"])


@router.get("/features", dependencies=[Depends(rate_limit)])
async def list_features(principal=Depends(require_user)) -> dict:
    """The app-store card's own content — see `core/features.py::public_features`."""
    return {"features": public_features()}
