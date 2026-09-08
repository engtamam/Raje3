"""The two user-tier signal routes: reading the stream, and adding to it from a browser.

TWO DOORS, TWO DIFFERENT PRIVILEGES, AND THAT ASYMMETRY IS THE POINT.

READING requires `platform.observability` — a capability of ours, held by our operators, not by an
establishment. The stream crosses every tenant on the platform by construction (a pod's stack trace
belongs to no shop), so a route that let a shop owner read it would be a cross-tenant read wearing
a support screen's clothes.

REPORTING requires only a valid session. Any authenticated person's browser may say "this broke in
front of me" — gating that behind a capability would mean the only errors we ever hear about are
the ones that happen to operators, which is the population least likely to hit them. It is
rate-limited and size-capped instead, which is the right control for an open write: the risk is
volume, not privilege.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from starlette.responses import JSONResponse

from app.api.auth import Principal, require_user
from app.api.authz import require_capability
from app.api.ratelimit import rate_limit
from app.config import get_settings
from app.core.pii import subject_ref
from app.core.signals import SignalIn, SignalStore, public

router = APIRouter(prefix="/signals", tags=["signals"])

# OURS. See the module docstring — the stream spans every tenant, so the capability that opens it
# is a platform one and is declared as such in app/admin_actions.py and app/manifest.py.
_OBSERVE = require_capability("platform.observability")


def _refuse(reason: str, status_code: int = 400) -> JSONResponse:
    """A refusal the operator can read — returned, not raised.

    The platform's error handler strips `detail` from every HTTPException on purpose (CWE-209),
    which is right for a stack trace and wrong for a sentence we wrote ourselves: raised, it
    arrives as `{"error": "BAD_REQUEST"}` and the reason is gone. THE STATUS IS KEPT, so a caller
    checking `response.ok` behaves exactly as before; only the body gains the sentence.
    """
    return JSONResponse({"error": "BAD_REQUEST", "reason": reason}, status_code=status_code)


def _store(request: Request) -> SignalStore:
    s = get_settings()
    return SignalStore(request.app.state.container.datastore,
                       retention_days=s.SIGNAL_RETENTION_DAYS,
                       reap_limit=s.SIGNAL_REAP_LIMIT)


def _split(values: list[str] | None) -> list[str]:
    """Accept both shapes a client might send: repeated params AND one comma-separated value.

    `?severity=error&severity=warning` and `?severity=error,warning` mean the same thing to every
    person who types either, and a filter that silently returns nothing for one of them is a screen
    the operator concludes is broken.
    """
    out: list[str] = []
    for raw in values or []:
        for part in str(raw).split(","):
            part = part.strip()
            if part and part not in out:
                out.append(part)
    return out


@router.get("", dependencies=[Depends(rate_limit)])
async def list_signals(
    request: Request,
    principal: Principal = Depends(_OBSERVE),
    source: list[str] | None = Query(default=None),
    severity: list[str] | None = Query(default=None),
    service: str = Query(default="", max_length=128),
    since: int = Query(default=0, ge=0),
    until: int = Query(default=0, ge=0),
    q: str = Query(default="", max_length=256),
    limit: int = Query(default=100, ge=1, le=500),
    after: str = Query(default="", max_length=512),
) -> dict:
    """The stream, newest first, filtered and paged.

    `sources` AND `severities` COME BACK WITH THE PAGE. The screen's filter checkboxes are built
    from the values actually present rather than from a list hardcoded in the console — which is
    the other half of `source` and `severity` being free-form strings. A new source starts
    appearing as a checkbox the moment something posts one, with no console deploy.

    NOT AUDITED. This is a read performed on every page load and on every filter change; recording
    it would bury the writes an investigation actually looks for under a stream of list calls. It
    is also the only read on this service, and it returns nobody's personal record — it returns
    what broke.
    """
    store = _store(request)
    rows, next_cursor = await store.browse(
        sources=_split(source), severities=_split(severity), service=service.strip(),
        since=since, until=until, q=q, limit=limit, after=after)
    return {
        "signals": [public(r) for r in rows],
        "next_cursor": next_cursor,
        "sources": await store.distinct("source"),
        "severities": await store.distinct("severity"),
        "services": await store.distinct("service"),
    }


@router.post("/report", dependencies=[Depends(rate_limit)])
async def report_signal(request: Request, body: SignalIn,
                        principal: Principal = Depends(require_user)) -> dict:
    """A browser saying what just broke in front of somebody.

    THE SAME MODEL FLUENT BIT POSTS. One contract, two doors — see app/core/signals.py.

    THE ATTRIBUTION IS TAKEN FROM THE TOKEN, NEVER FROM THE BODY. The reporter's tenant and their
    pseudonym are what make this row reachable by an erasure later; a body-supplied tenant would be
    an unverified claim written into a store an operator reads as fact.

    ANY AUTHENTICATED USER, NO CAPABILITY. See the module docstring.
    """
    s = get_settings()
    tenant = getattr(principal, "tenant", "") or ""
    subject = getattr(principal, "subject", "") or ""
    # No salt configured means no pseudonym — and an unsalted identifier must never be written.
    # An empty ref makes the row unattributed, which is honest, and the boot guard is what stops a
    # production deploy from being in this state at all.
    ref = subject_ref(s.PII_SALT, tenant, subject) if (s.PII_SALT and tenant and subject) else ""
    row = await _store(request).record(body, tenant=tenant, subject_ref=ref)
    return {"id": row["id"], "received_at": row["received_at"]}
