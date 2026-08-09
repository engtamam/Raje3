"""The platform console surface — sectors, edited by US at runtime.

NOT AN ESTABLISHMENT'S SURFACE. Every route here is gated by `platform.operations`, which no
tenant token carries: a tyre shop must not be able to rename "بنشر" for every other tyre shop on
the product. This is our own operators curating the content the whole platform is built from.

WHY IT EXISTS AT ALL — the alternative was a JSON file read at boot, and it was wrong. Adding a
sector, correcting a service name, or changing a cycle would have meant editing a ConfigMap and
restarting a service. Sectors are content: somebody will want a new one on a Tuesday afternoon
because a customer asked. Content that needs a deploy is content that does not get edited, and a
product whose sector list is frozen at build time serves only the sectors somebody thought of in
the first month.

EVERY MUTATION IS AUDITED. Changing a sector changes what every establishment created afterwards
receives, which makes it one of the highest-leverage edits anyone can make here — a wrong cycle
propagated to a thousand new tenants is not visible until their customers start getting reminders
at the wrong time.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.api.auth import Principal
from app.api.authz import require_capability
from app.api.ratelimit import rate_limit
from app.core.sectors import SectorCatalogue, SectorError

# The parent router in __init__ already carries /api/v1 — this prefix is appended to it.
router = APIRouter(prefix="/platform", tags=["platform"])

_PLATFORM = require_capability("platform.operations")


def _cat(request: Request) -> SectorCatalogue:
    return SectorCatalogue(request.app.state.container.datastore)


class ServiceDefault(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    # 0 = no natural cycle, and it is a real value rather than a missing one. See the seed file:
    # defaulting this to 30 would schedule a reminder for a puncture repair.
    cycle_days: int = Field(default=0, ge=0, le=3650)
    sort: int = Field(default=0, ge=0, le=9999)


class SectorIn(BaseModel):
    key: str = Field(min_length=2, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    name: str = Field(min_length=1, max_length=128)
    # "vehicle" or "none". The vehicle is the ONLY asset in the product (spec §13.2) — for
    # everything else the service cycle follows the customer, not a thing they own.
    asset: str = Field(default="none", pattern="^(vehicle|none)$")
    fields: list[str] = Field(default_factory=list, max_length=10)
    services: list[ServiceDefault] = Field(default_factory=list, max_length=60)
    sort: int = Field(default=0, ge=0, le=9999)
    active: bool = True


@router.get("/sectors", dependencies=[Depends(rate_limit)])
async def list_sectors(request: Request, principal: Principal = Depends(_PLATFORM)) -> dict:
    """Every sector, active or not.

    Including the inactive ones deliberately: a console that can only show what is live cannot
    show an operator what they switched off last month, which is the first thing they look for
    when an establishment asks why their sector disappeared.
    """
    cat = _cat(request)
    return {"sectors": await cat.list(), "fields": await cat.fields()}


@router.put("/sectors/{key}", dependencies=[Depends(rate_limit)])
async def upsert_sector(request: Request, key: str, body: SectorIn,
                        principal: Principal = Depends(_PLATFORM)) -> dict:
    """Create or replace a sector. Takes effect on the NEXT tenant created.

    Deliberately not retroactive. Changing a sector does not rewrite the catalogues of
    establishments that already have one — they have edited their own services by now, and
    overwriting an owner's list because we corrected a default would destroy real work.
    """
    if key != body.key:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "the key in the path and the body must match")
    await request.app.state.auditor.record(
        "platform.sector_changed", actor=principal.subject, tenant="",
        resource=f"sector:{key}", ip=request.client.host if request.client else "")
    try:
        row = await _cat(request).upsert(body.model_dump())
    except SectorError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    return row


@router.delete("/sectors/{key}", dependencies=[Depends(rate_limit)])
async def deactivate_sector(request: Request, key: str,
                            principal: Principal = Depends(_PLATFORM)) -> dict:
    """DEACTIVATE, never delete.

    Establishments already point at this sector. Deleting it would leave them referring to
    something that no longer exists — a signup screen that works and a tenant record that does not
    resolve, discovered by whoever tries to read it months later.
    """
    await request.app.state.auditor.record(
        "platform.sector_deactivated", actor=principal.subject, tenant="",
        resource=f"sector:{key}", ip=request.client.host if request.client else "")
    if not await _cat(request).deactivate(key):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND")
    return {"key": key, "active": False}


class FieldSpecsIn(BaseModel):
    # The whole map, replaced at once rather than patched field by field. A field spec is small and
    # read as a unit by the screen; a partial update would let the console leave a sector pointing
    # at a field whose definition was removed in the same session.
    specs: dict = Field(default_factory=dict)


@router.put("/sector-fields", dependencies=[Depends(rate_limit)])
async def set_field_specs(request: Request, body: FieldSpecsIn,
                          principal: Principal = Depends(_PLATFORM)) -> dict:
    """What each per-sector input means — label, type, help text.

    Held once and referenced by name, so `plate` means the same thing in every vehicle sector. The
    alternative — repeating the definition inside each sector — is five copies that drift.
    """
    await request.app.state.auditor.record(
        "platform.sector_fields_changed", actor=principal.subject, tenant="",
        resource="sector_fields", ip=request.client.host if request.client else "")
    return await _cat(request).set_field_specs(body.specs)
