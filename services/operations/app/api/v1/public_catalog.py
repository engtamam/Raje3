"""The ONE route in this service a stranger may call with no token at all — see
`core/public_catalog_image.py`'s own module docstring for why it has to exist and why a capability
token, never tenant/service_id, is what gates it.

RATE LIMITED HARD, same discipline `reminders/api/v1/prefs.py`'s own module docstring documents for
the identical shape of surface: an unthrottled unauthenticated read is an invitation regardless of
how little it reveals, and this one returns only a product photo nothing else protects.
"""
# gateway: auth none
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from starlette.responses import Response

from app.api.ratelimit import rate_limit

router = APIRouter(tags=["public-catalog"])


@router.get("/public_catalog/{token}", dependencies=[Depends(rate_limit)])
async def get_public_catalog_image(request: Request, token: str) -> Response:
    """No `Principal`, no `tenant` — deliberately the one route on this whole service that takes
    neither. ONE GENERIC 404 for every failure shape (bad token, revoked token, service vanished,
    image missing) — see `public_catalog_image.resolve`'s own docstring on why these must never be
    told apart in the response.

    LONG, IMMUTABLE CACHE — the token rotates on every re-upload (staff.py's own upload route), so
    the content behind any given token never changes; letting Meta's crawler (and any CDN in
    front of this) cache it hard is free performance with no staleness risk.
    """
    from app.core import public_catalog_image as PCI
    from app.core.catalogue_image import read_image
    from app.core.stores import ServiceStore
    from app.ports.errors import NotFound

    resolved = await PCI.resolve(request.app.state.container.datastore, token)
    if resolved is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND")
    tenant, service_id = resolved
    s = await ServiceStore(request.app.state.container.datastore).get(tenant, service_id)
    # THE TOKEN ON THE ROW MUST STILL MATCH — a service re-uploaded its photo (minting a new token
    # and revoking this one) normally removes the index entry already, but this is the second,
    # independent check belt-and-suspenders style: an index entry that somehow survived a revoke
    # must never serve a photo the row itself no longer claims this token for.
    if s is None or not s.image_key or s.public_image_token != token:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND")
    try:
        data, ctype = await read_image(request.app.state.container.object_store, s.image_key)
    except NotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND")
    return Response(content=data, media_type=ctype,
                    headers={"Cache-Control": "public, max-age=31536000, immutable"})
