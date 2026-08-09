"""The partner console — their shops, their money, and nothing else.

THE MOST DANGEROUS SURFACE ON THE PRODUCT, and it is worth being blunt about why. Every other role
here is either an establishment looking at its own data or us looking at everything. A partner is
the first party that is NEITHER: it has a legitimate claim on some rows of a tenant it does not own,
and no claim at all on the rest.

WHAT A PARTNER MAY SEE: which establishments it brought, whether each is subscribed, and its own
commission statements.

WHAT A PARTNER MAY NEVER SEE: a shop's customers, their phone numbers, their visits, their messages,
or their revenue. Not because it is sensitive to us — because it is the shop's, and the shop never
agreed to share it with the company that sold them the till.

That distinction is easy to state and easy to lose. A console that gains "just show me how the shop
is doing" grows into a customer list, one reasonable request at a time. So the boundary is enforced
by the capability being scoped to a PARTNER ID rather than to a tenant, and every route here reads
only from the two collections a partner is entitled to: stamps, and statements.

THE CAPABILITY CARRIES THE PARTNER, AND THE ROUTE TRUSTS THE TOKEN, NEVER THE PATH. A partner id in
a URL is a partner id an attacker can change. It comes off the verified token — the same rule as
the tenant claim everywhere else on this platform, and for exactly the same reason.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.auth import Principal
from app.api.authz import require_capability
from app.api.ratelimit import rate_limit
from app.config import get_settings
from app.core.commission import StatementStore
from app.core.partners import PartnerRegistry

router = APIRouter(prefix="/partner", tags=["partner"])

_PARTNER = require_capability("partner.read")


def _partner_id(principal: Principal) -> str:
    """The partner this token speaks for.

    Read from the `partner` claim, NEVER from the path. A partner id in a URL is a partner id an
    attacker can change to somebody else's, and this is the one route family where that would hand
    over another company's commercial position.
    """
    pid = (principal.raw or {}).get("partner") or ""
    if not pid:
        # 403, not 400. The token is structurally valid and simply does not speak for a partner —
        # telling the caller which field is missing helps them forge a better one.
        raise HTTPException(status.HTTP_403_FORBIDDEN, "FORBIDDEN")
    return str(pid)


@router.get("/shops", dependencies=[Depends(rate_limit)])
async def my_shops(request: Request, principal: Principal = Depends(_PARTNER)) -> dict:
    """The establishments this partner brought.

    RETURNS THE TENANT ID AND THE DATE. Not the shop's name, not its owner, not its phone, not its
    customer count. A partner knows which shops it signed up — it does not need us to describe them,
    and every field added here is a field somebody later argues should include "just a bit more".
    """
    c = request.app.state.container
    s = get_settings()
    reg = PartnerRegistry(c.datastore, salt=s.PII_SALT)
    pid = _partner_id(principal)
    tenants = await reg.tenants_of(pid)
    return {"partner_id": pid, "count": len(tenants), "shops": tenants}


@router.get("/statements", dependencies=[Depends(rate_limit)])
async def my_statements(request: Request, limit: int = 24,
                        principal: Principal = Depends(_PARTNER)) -> dict:
    """This partner's commission statements, newest first.

    Read-only and computed elsewhere: a partner must never be able to trigger a recomputation, or a
    disputed month becomes a month they can re-run until they like the number.
    """
    c = request.app.state.container
    pid = _partner_id(principal)
    rows = await StatementStore(c.datastore).for_partner(pid, limit=min(max(limit, 1), 24))
    return {"partner_id": pid, "statements": rows}


@router.get("/statements/{period_start}", dependencies=[Depends(rate_limit)])
async def one_statement(request: Request, period_start: int,
                        principal: Principal = Depends(_PARTNER)) -> dict:
    """One month, with its per-shop lines.

    Scoped by the token's partner id before the lookup, so a period from another partner's
    statement cannot be read by guessing a timestamp — timestamps are guessable by construction.
    """
    c = request.app.state.container
    pid = _partner_id(principal)
    row = await StatementStore(c.datastore).get(pid, period_start)
    if row is None or row.get("partner_id") != pid:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND")
    return row
