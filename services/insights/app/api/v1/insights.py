"""The dashboard's routes — reads only, and one subscription switch.

EVERYTHING HERE READS A SNAPSHOT. No route computes an indicator on the request path: that is the
whole reason the snapshot exists (core/tick.py), and a route that "just recomputes this one" is how
the guarantee is lost one endpoint at a time.

THE PLAN IS CHECKED AT EVERY ROUTE, NOT ONLY IN THE CATALOGUE. The console is a map and never the
authority — a client that stops asking is a client that sees everything.

AND A TENANT WITH NO SNAPSHOT NEVER GETS A BLANK. It gets "أحسب الآن" with the next pass time. An
empty dashboard reads as broken, and an owner who concludes that on his first day does not return
on his second.
"""
from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.api.auth import Principal
from app.api.authz import require_capability
from app.api.ratelimit import rate_limit
from app.core import bundles as _bundles
from app.core import plans
from app.core.coverage import blocked, group_by
from app.core.models import Coverage, PAIRS, SNAPSHOTS, Pair

router = APIRouter(prefix="/insights", tags=["insights"])

_READ = require_capability("insights.read")
_PLATFORM = require_capability("platform.insights")


def _refuse(reason: str, code: int = status.HTTP_400_BAD_REQUEST) -> JSONResponse:
    """A refusal the owner can read — returned, not raised.

    The platform's handler strips `detail` from every HTTPException on purpose (CWE-209), which is
    right for a trace and wrong for a sentence we wrote ourselves. See playbook §4.25.
    """
    return JSONResponse({"error": "BAD_REQUEST", "reason": reason}, status_code=code)


def _tenant(principal: Principal) -> str:
    t = getattr(principal, "tenant", "") or ""
    if not t:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "no establishment on this token")
    return t


# THE PLAN IS NOT ON THE TOKEN — see core/plans.py. It is asked of billing, per request, and a
# failure to reach billing denies. `_keys` is the one place that asks.
async def _keys(c, tenant: str) -> set[str]:
    return await plans.allowed_keys(c.peers, tenant)


LOCKED = "هذه الميزة في باقة أعلى"


async def _snapshot(c, tenant: str, branch_id: str = "") -> dict | None:
    return await c.datastore.get(SNAPSHOTS, f"{tenant}|{branch_id or '_all'}")


@router.get("/dashboard", dependencies=[Depends(rate_limit)])
async def dashboard(request: Request, branch_id: str = "",
                    principal: Principal = Depends(_READ)) -> dict:
    """Everything the panel renders, in one read.

    ONE CALL, because eleven indicators fetched separately is eleven round trips on a phone, and
    the screen would paint itself in pieces.
    """
    c = request.app.state.container
    tenant = _tenant(principal)
    keys = await _keys(c, tenant)
    snap = await _snapshot(c, tenant, branch_id)

    if not snap:
        # NOT an empty dashboard. See the module docstring.
        return {"computing": True,
                "message": "أحسب مؤشرات محلك الآن — تظهر خلال ساعات",
                "values": {}, "as_of": 0}

    now = int(time.time())
    age_hours = (now - int(snap.get("computed_at") or 0)) // 3600
    values = plans.filter_snapshot(snap.get("values") or {}, keys)

    # The pairs are a paid surface, and the teaser is the ONE deliberate exception to "what a plan
    # does not include is not rendered at all".
    pairs = [_as_pair(r) for r in (snap.get("values", {}).get("associations", {}) or {})
             .get("pairs", [])]
    teaser = plans.teaser(keys, pairs)

    cov = snap.get("coverage") or {}
    not_enabled = []
    for name, raw in cov.items():
        b = blocked(name, coverage=Coverage(total=int(raw.get("total") or 0),
                                            known=int(raw.get("known") or 0)))
        if b:
            not_enabled.append({"indicator": name, **b})
    assoc = (snap.get("values") or {}).get("associations") or {}
    b = blocked("associations", learning=assoc)
    if b and not plans.can_see("associations", keys):
        pass          # a locked surface is not "not enabled" — it is not bought. Two different
                      # sentences, and mixing them tells the owner to fix something he cannot.
    elif b:
        not_enabled.append({"indicator": "associations", **b})

    return {
        "computing": False,
        "values": values,
        "coverage": cov,
        "as_of": int(snap.get("computed_at") or 0),
        # SHOWN, ALWAYS. An owner comparing our number to his till at 2pm must see that ours was
        # computed at 3am, or he stops trusting both.
        "as_of_hours_ago": age_hours,
        "stale": age_hours >= 30,
        "branch_id": branch_id,
        "visits": snap.get("visits", 0),
        "not_enabled": not_enabled,
        "teaser": teaser,
        # WHAT HE HOLDS, not what plan he is on. The console renders a lock from the absence of a
        # key rather than from a plan name it would otherwise have to know the ladder of.
        "entitlements": sorted(keys),
    }


def _as_pair(row: dict) -> Pair:
    p = Pair(tenant=row.get("tenant", ""), a=row.get("a", ""), b=row.get("b", ""),
             lift_basket=float(row.get("lift_basket") or 0),
             lift_customer=float(row.get("lift_customer") or 0),
             customers=int(row.get("customers") or 0),
             verdict=row.get("verdict", "none"))
    p.id = row.get("id", p.id)
    return p


@router.get("/associations", dependencies=[Depends(rate_limit)])
async def associations(request: Request, principal: Principal = Depends(_READ)):
    """The pairs themselves — a paid surface (spec §15).

    Returns the VERDICT and the customer count, and never the arithmetic. No lift value leaves
    this service: the engine is the product's own IP (core/associations.py).
    """
    c = request.app.state.container
    tenant = _tenant(principal)
    if not plans.can_see("associations", await _keys(c, tenant)):
        return _refuse(LOCKED, status.HTTP_402_PAYMENT_REQUIRED)
    snap = await _snapshot(c, tenant)
    assoc = ((snap or {}).get("values") or {}).get("associations") or {}
    if assoc.get("learning"):
        return {"learning": True, "have": assoc.get("have", 0), "need": assoc.get("need", 0),
                "pairs": []}
    return {"learning": False,
            "pairs": [{"a": p["a"], "b": p["b"], "verdict": p["verdict"],
                       "customers": p["customers"]}
                      for p in assoc.get("pairs", []) if p.get("verdict") != "group"]}


@router.get("/bundles", dependencies=[Depends(rate_limit)])
async def suggested_bundles(request: Request, principal: Principal = Depends(_READ)):
    """The suggested-bundles page (spec §10.6.2.1) — where, never how much."""
    c = request.app.state.container
    tenant = _tenant(principal)
    if not plans.can_see("suggested_bundles", await _keys(c, tenant)):
        return _refuse(LOCKED, status.HTTP_402_PAYMENT_REQUIRED)
    snap = await _snapshot(c, tenant)
    values = (snap or {}).get("values") or {}
    pairs = [_as_pair(r) for r in (values.get("associations") or {}).get("pairs", [])]
    missing: dict[tuple[str, str], int] = {}
    for m in values.get("missed_opportunities") or []:
        k = (m.get("has", ""), m.get("missing", ""))
        missing[k] = missing.get(k, 0) + 1
    cards = _bundles.build(pairs, names=values.get("service_names") or {},
                           missing_counts=missing)
    return {"bundles": cards, "count": len(cards)}


@router.get("/branches", dependencies=[Depends(rate_limit)])
async def branches(request: Request, principal: Principal = Depends(_READ)):
    """The branch table, with its unspecified row and its ranking rule (spec §10.6.3)."""
    c = request.app.state.container
    tenant = _tenant(principal)
    if not plans.can_see("branch_comparison", await _keys(c, tenant)):
        return _refuse(LOCKED, status.HTTP_402_PAYMENT_REQUIRED)
    snap = await _snapshot(c, tenant)
    cov = ((snap or {}).get("coverage") or {}).get("branch_comparison") or {}
    return {"coverage": cov,
            "rows": ((snap or {}).get("values") or {}).get("branch_rows") or [],
            "unknown": cov.get("unknown", 0),
            "can_rank": bool(((snap or {}).get("values") or {}).get("branch_can_rank"))}


class DigestIn(BaseModel):
    on: bool
    # Empty = the caller themselves. A manager subscribing himself is the common case, and making
    # him type his own id would be a form nobody fills.
    subject: str = Field(default="", max_length=128)


@router.put("/digest", dependencies=[Depends(rate_limit)])
async def set_digest(request: Request, body: DigestIn,
                     principal: Principal = Depends(_READ)) -> dict:
    """Subscribe to the weekly report — PER PERSON, not per establishment.

    A manager may want it and the owner may not; one flag on the establishment forces them to
    agree, and makes unsubscribing an act that silently switches a colleague off.
    """
    c = request.app.state.container
    subject = body.subject or str(getattr(principal, "subject", "") or "")
    if not subject:
        return _refuse("لا يمكن تحديد المشترك")
    return await c.subscriptions.set(_tenant(principal), subject, on=body.on)


@router.post("/platform/recompute", dependencies=[Depends(rate_limit)])
async def platform_recompute(request: Request, principal: Principal = Depends(_PLATFORM)) -> dict:
    """Recompute one establishment's snapshot now — OURS, for support.

    The tenant comes off the body here, which is why the route is separate and why it needs a
    platform capability: support is answering a question about a shop that is not theirs.
    """
    body = await request.json()
    tenant = str((body or {}).get("tenant") or "")
    if not tenant:
        return _refuse("tenant is required")
    c = request.app.state.container
    await request.app.state.auditor.record(
        "insights.recomputed", actor=getattr(principal, "subject", ""), tenant=tenant,
        resource="snapshot", ip=request.client.host if request.client else "")
    snap = await c.tick.compute(tenant, now=int(time.time()))
    return {"tenant": tenant, "computed_at": snap.computed_at, "visits": snap.visits}
