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

from app.api.auth import Principal, require_user
from app.api.authz import require_capability
from app.api.deps import get_runtime_config
from app.api.ratelimit import rate_limit
from app.config import get_settings
from app.core.pii import subject_ref
from app.core.signals import SignalIn, SignalStore, public

router = APIRouter(prefix="/signals", tags=["signals"])

# OURS. See the module docstring — the stream spans every tenant, so the capability that opens it
# is a platform one and is declared as such in app/admin_actions.py and app/manifest.py.
_OBSERVE = require_capability("platform.observability")


async def _store(request: Request) -> SignalStore:
    """RETENTION/REAP NOW RESOLVE THROUGH RuntimeConfig — fixed 2026-09-12, a real gap a QA audit
    found: the operator config panel advertised these two as its "only two settings today" while
    every actual reader took them straight off `settings`, so a saved override never did anything.
    `default=` keeps the deploy's own env value as the fallback the first time nobody has set an
    override yet — unchanged behaviour for every shop that never opens this screen."""
    s = get_settings()
    rc = get_runtime_config(request)
    retention_days = await rc.get(tenant="", key="SIGNAL_RETENTION_DAYS",
                                  default=s.SIGNAL_RETENTION_DAYS)
    reap_limit = await rc.get(tenant="", key="SIGNAL_REAP_LIMIT", default=s.SIGNAL_REAP_LIMIT)
    return SignalStore(request.app.state.container.datastore,
                       retention_days=retention_days, reap_limit=reap_limit)


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
    tenant: str = Query(default="", max_length=128),
    subject_ref: str = Query(default="", max_length=128),
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

    `tenant`/`subject_ref` ANSWER «أي أخطاء صارت لهذا العميل؟» — the admin panel resolves a phone
    number to a pseudonym first (operations' own by-phone lookup), then asks here with the SAME
    pseudonym. Narrower than a tenant filter alone; see `SignalStore.browse`'s own note on why
    `subject_ref` is never accepted without `tenant` alongside it.

    NOT AUDITED. This is a read performed on every page load and on every filter change; recording
    it would bury the writes an investigation actually looks for under a stream of list calls. It
    is also the only read on this service, and it returns nobody's personal record — it returns
    what broke. `tenant`/`subject_ref` narrow it, they do not turn it into one: no message text
    named a person before this filter existed, and this filter does not add any.
    """
    store = await _store(request)
    rows, next_cursor = await store.browse(
        sources=_split(source), severities=_split(severity), service=service.strip(),
        tenant=tenant.strip(), subject_ref=subject_ref.strip() if tenant.strip() else "",
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
    store = await _store(request)
    row = await store.record(body, tenant=tenant, subject_ref=ref)
    return {"id": row["id"], "received_at": row["received_at"]}
