"""The back office — operators, branches and the service catalogue.

A DIFFERENT PRIVILEGE FROM THE FIELD SCREEN, and separated on purpose. Recording a visit is what
everyone does all day; adding an operator, changing a price or deactivating a service is the
owner's. A shop that hires seasonal help must be able to grant the first without the second.

THE PIN IS ATTRIBUTION, NOT AUTHENTICATION — and the distinction decides the whole design.

A four-digit PIN is guessable by construction: ten thousand possibilities, and a colleague standing
beside you can watch it being typed. It is not, and cannot be, what protects an establishment's
data. That is the establishment's session, which is a real token behind a real login.

What the PIN answers is a narrower and genuinely useful question: WHICH of the three people sharing
this tablet recorded that visit. It is asked at SAVE, not at the start of a shift, because the
screen stays open all day and a login per visit would destroy the five-second rule — and the
predictable result of that is one device signed in as one person recording everybody's work, which
is worse than no attribution because it is attribution that lies.

So it is hashed (never stored readable), it is rate-limited (guessing four digits is otherwise
trivial), a wrong one is audited (a pattern of failures is the signal worth having), and it is
never returned by any read.
"""
from __future__ import annotations

import hashlib
import hmac
import time

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.api.auth import Principal
from app.api.authz import require_capability
from app.api.ratelimit import rate_limit
from app.core.models import Branch, Operator, Service
from app.core.stores import BranchStore, OperatorStore, ServiceStore, new_id

# The parent router in __init__ already carries /api/v1 — this prefix is appended to it.
router = APIRouter(prefix="/staff", tags=["staff"])

_MANAGE = require_capability("operations.manage")
_READ = require_capability("operations.read")


def _tenant(p: Principal) -> str:
    if not p.tenant:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "NO_TENANT")
    return p.tenant


def _pin_hash(salt: str, tenant: str, operator_id: str, pin: str) -> str:
    """Salted and bound to the operator.

    Bound to (tenant, operator_id) so the same four digits produce different hashes for different
    people — otherwise a leaked table would show at a glance which operators share a PIN, and
    "1234" would be identifiable across every establishment we host.
    """
    return hmac.new(salt.encode("utf-8"),
                    f"{tenant}|{operator_id}|{pin}".encode("utf-8"),
                    hashlib.sha256).hexdigest()


# ── operators ─────────────────────────────────────────────────────────────────────────────────
class OperatorIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    # Four digits, and no longer. A longer PIN is not meaningfully safer for what this protects,
    # and it IS meaningfully slower to type a hundred times a day — which is the cost that decides
    # whether the product gets used.
    pin: str = Field(min_length=4, max_length=4, pattern=r"^\d{4}$")
    role: str = Field(default="operator", max_length=32)
    branch_id: str = Field(default="", max_length=64)


@router.post("/operators", status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(rate_limit)])
async def create_operator(request: Request, body: OperatorIn,
                          principal: Principal = Depends(_MANAGE)) -> dict:
    tenant = _tenant(principal)
    await request.app.state.auditor.record(
        "operator.created", actor=principal.subject, tenant=tenant, resource="operator",
        ip=request.client.host if request.client else "")

    settings = request.app.state.container_settings
    op = Operator(id=new_id("opr"), tenant=tenant, name=body.name.strip(), role=body.role,
                  branch_id=body.branch_id, created=int(time.time()))
    op.pin_hash = _pin_hash(settings.PII_SALT, tenant, op.id, body.pin)
    await OperatorStore(request.app.state.container.datastore).save(op)
    # public() omits pin_hash — a hash that is never returned cannot be attacked offline by
    # somebody who reached a read endpoint.
    return op.public()


@router.get("/operators", dependencies=[Depends(rate_limit)])
async def list_operators(request: Request, principal: Principal = Depends(_READ)) -> dict:
    rows = await OperatorStore(request.app.state.container.datastore).list(_tenant(principal))
    return {"operators": [o.public() for o in rows]}


class PinVerifyIn(BaseModel):
    operator_id: str = Field(min_length=1, max_length=64)
    pin: str = Field(min_length=4, max_length=4, pattern=r"^\d{4}$")


@router.post("/operators/verify-pin", dependencies=[Depends(rate_limit)])
async def verify_pin(request: Request, body: PinVerifyIn,
                     principal: Principal = Depends(_READ)) -> dict:
    """Confirm which operator is saving. Called by the field screen at the moment of saving.

    Rate-limited like every route here, and that is what makes a four-digit secret defensible at
    all: ten thousand possibilities fall in minutes to an unthrottled endpoint.
    """
    tenant = _tenant(principal)
    settings = request.app.state.container_settings
    op = await OperatorStore(request.app.state.container.datastore).get(tenant, body.operator_id)

    expected = op.pin_hash if op else ""
    candidate = _pin_hash(settings.PII_SALT, tenant, body.operator_id, body.pin)
    # compare_digest on both paths, and an unknown operator takes the same path as a wrong PIN:
    # one answer for "no such operator", "wrong PIN" and "deactivated" (CWE-203/208). Anything
    # else lets a caller enumerate who works here.
    ok = bool(op) and op.active and hmac.compare_digest(expected, candidate)

    if not ok:
        # Audited. One failure is a fat finger; a pattern of them is the signal worth having, and
        # it cannot be seen if failures are not recorded.
        await request.app.state.auditor.record(
            "operator.pin_rejected", actor=principal.subject, tenant=tenant,
            resource=f"operator:{body.operator_id}",
            ip=request.client.host if request.client else "")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "PIN_REJECTED")

    return {"operator": op.public()}


# ── branches ──────────────────────────────────────────────────────────────────────────────────
class BranchIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)


@router.post("/branches", status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(rate_limit)])
async def create_branch(request: Request, body: BranchIn,
                        principal: Principal = Depends(_MANAGE)) -> dict:
    tenant = _tenant(principal)
    await request.app.state.auditor.record(
        "branch.created", actor=principal.subject, tenant=tenant, resource="branch",
        ip=request.client.host if request.client else "")
    b = Branch(id=new_id("brn"), tenant=tenant, name=body.name.strip(), created=int(time.time()))
    await BranchStore(request.app.state.container.datastore).save(b)
    return b.public()


@router.get("/branches", dependencies=[Depends(rate_limit)])
async def list_branches(request: Request, principal: Principal = Depends(_READ)) -> dict:
    rows = await BranchStore(request.app.state.container.datastore).list(_tenant(principal))
    return {"branches": [b.public() for b in rows]}


# ── the service catalogue ─────────────────────────────────────────────────────────────────────
class ServiceIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    # 0 means "no natural cycle" — a one-off repair generates no reminder. Explicitly a valid
    # value rather than a missing one, because a default of 30 would schedule a reminder for a
    # puncture repair and teach a customer that our messages are noise.
    cycle_days: int = Field(default=0, ge=0, le=3650)
    # Minor units. No float ever touches an amount.
    price_minor: int = Field(default=0, ge=0)
    sort: int = Field(default=0, ge=0, le=9999)


@router.post("/services", status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(rate_limit)])
async def create_service(request: Request, body: ServiceIn,
                         principal: Principal = Depends(_MANAGE)) -> dict:
    tenant = _tenant(principal)
    await request.app.state.auditor.record(
        "service.created", actor=principal.subject, tenant=tenant, resource="service",
        ip=request.client.host if request.client else "")
    s = Service(id=new_id("srv"), tenant=tenant, name=body.name.strip(),
                cycle_days=body.cycle_days, price_minor=body.price_minor, sort=body.sort,
                created=int(time.time()))
    await ServiceStore(request.app.state.container.datastore).save(s)
    return s.public()


class ServicePatch(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    cycle_days: int | None = Field(default=None, ge=0, le=3650)
    price_minor: int | None = Field(default=None, ge=0)
    active: bool | None = None
    sort: int | None = Field(default=None, ge=0, le=9999)


@router.patch("/services/{service_id}", dependencies=[Depends(rate_limit)])
async def update_service(request: Request, service_id: str, body: ServicePatch,
                         principal: Principal = Depends(_MANAGE)) -> dict:
    """Edit a catalogue entry.

    DEACTIVATE rather than delete — `active: false`. Deleting a service would orphan every visit
    that references it, and a shop that stops offering something still needs last year's records
    to make sense.
    """
    tenant = _tenant(principal)
    store = ServiceStore(request.app.state.container.datastore)
    s = await store.get(tenant, service_id)
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND")

    await request.app.state.auditor.record(
        "service.updated", actor=principal.subject, tenant=tenant,
        resource=f"service:{service_id}", ip=request.client.host if request.client else "")

    for fld in ("name", "cycle_days", "price_minor", "active", "sort"):
        val = getattr(body, fld)
        if val is not None:
            setattr(s, fld, val.strip() if isinstance(val, str) else val)
    await store.save(s)
    return s.public()
