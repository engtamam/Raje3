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
from app.core.templates import TemplateError, TemplateLibrary

# The parent router in __init__ already carries /api/v1 — this prefix is appended to it.
router = APIRouter(prefix="/platform", tags=["platform"])

_PLATFORM = require_capability("platform.operations")


def _cat(request: Request) -> SectorCatalogue:
    return SectorCatalogue(request.app.state.container.datastore)


def _lib(request: Request) -> TemplateLibrary:
    return TemplateLibrary(request.app.state.container.datastore)


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


# ── the message-template library ───────────────────────────────────────────────────────────────
class TemplateIn(BaseModel):
    name: str = Field(min_length=3, max_length=512, pattern=r"^[a-z][a-z0-9_]*$")
    type: str = Field(default="", max_length=128)
    tone: str = Field(default="", pattern="^(brief|warm|formal|)$")
    label: str = Field(default="", max_length=200)
    # The five regulatory classes (spec §8.4.1). Validated, not accepted: the class decides the
    # rules, so a template filed under the wrong one carries the wrong constraints.
    cls: str = Field(alias="class", pattern="^(service|personal|awareness|warning|marketing)$")
    # Which kind of business this template is FOR (spec 16.6.5). Declared on the model, not only in
    # the core: pydantic drops an undeclared key silently and with a 200, which is exactly how the
    # `fills` rule was enforced in the core and bypassed at the door an hour after it was written.
    model: str = Field(default="both", pattern="^(cycle|loyalty|both)$")
    model_why: str = Field(default="", max_length=300)
    category: str = Field(pattern="^(UTILITY|MARKETING|AUTHENTICATION)$")
    language: str = Field(default="ar", max_length=8)
    body: str = Field(min_length=1, max_length=1024)
    header: str = Field(default="", max_length=60)
    button: str | None = Field(default=None, max_length=32)
    # Who fills each variable — "system", "catalogue", or "owner", one entry per variable. It MUST
    # be declared here: pydantic drops a field the model does not name, silently and with a 200.
    # A live call caught exactly that — a template declaring two owner fields was accepted because
    # `fills` never reached the library that refuses it, and the unit test passed because it called
    # the library directly, never crossing this model. The rule was real; the path to it was not.
    fills: list[str] = Field(default_factory=list, max_length=4)
    active: bool = True

    model_config = {"populate_by_name": True}


@router.get("/templates", dependencies=[Depends(rate_limit)])
async def list_templates(request: Request, cls: str = "", tone: str = "", model: str = "",
                         principal: Principal = Depends(_PLATFORM)) -> dict:
    """The whole library, filterable by class or tone.

    Inactive ones included: a console that shows only what is live cannot show an operator what
    they retired last month, which is the first thing they look for when asked why a message
    stopped going out.
    """
    lib = _lib(request)
    if model:
        # Filtered by model rather than by class: this is the query a console makes when it wants
        # "what should a cafe be offered?", and answering it with a class filter would return the
        # cycle templates a cafe has no use for.
        try:
            rows = await lib.for_model(model)
        except TemplateError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
        if cls:
            rows = [r for r in rows if r.get("class") == cls]
        if tone:
            rows = [r for r in rows if r.get("tone") == tone]
        return {"templates": rows}
    return {"templates": await lib.list(cls=cls, tone=tone)}


@router.put("/templates/{name}", dependencies=[Depends(rate_limit)])
async def upsert_template(request: Request, name: str, body: TemplateIn,
                          principal: Principal = Depends(_PLATFORM)) -> dict:
    """Create or replace a template — at runtime, with no rebuild and no restart.

    Takes effect for establishments onboarded AFTERWARDS. It does not rewrite what a tenant
    already has registered with Meta: that copy is approved under its own name, and silently
    diverging from an approved text is how a send starts failing for a reason nobody can see.
    """
    if name != body.name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "the name in the path and the body must match")
    await request.app.state.auditor.record(
        "platform.template_changed", actor=principal.subject, tenant="",
        resource=f"template:{name}", ip=request.client.host if request.client else "")
    try:
        return await _lib(request).upsert(body.model_dump(by_alias=True))
    except TemplateError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


@router.delete("/templates/{name}", dependencies=[Depends(rate_limit)])
async def deactivate_template(request: Request, name: str,
                              principal: Principal = Depends(_PLATFORM)) -> dict:
    """Deactivate, never delete. Establishments carry this name in their registry and Meta holds
    an approved copy under it — deleting our row leaves both pointing at nothing we can explain."""
    await request.app.state.auditor.record(
        "platform.template_deactivated", actor=principal.subject, tenant="",
        resource=f"template:{name}", ip=request.client.host if request.client else "")
    if not await _lib(request).deactivate(name):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND")
    return {"name": name, "active": False}
