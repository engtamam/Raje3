"""How long a person's number is kept — three clocks, and only one of them is ours to start.

THE DISTINCTION THAT DECIDES EVERYTHING. The ESTABLISHMENT is the controller of its customers'
data: it collected the numbers, for its purpose, from its own customers. We are the processor. That
settles who may decide to delete, and it is why this file has three different answers rather than
one policy.

────────────────────────────────────────────────────────────────────────────────────────────────
1 · A CUSTOMER OF AN ACTIVE ESTABLISHMENT — THE SHOP DECIDES, WE ENFORCE

We do not delete on our own initiative, and the two reasons point the same way.

Legally: a processor that deletes the controller's data by itself is exceeding its authority, not
complying with anything.

And commercially, which is the stronger argument: A CUSTOMER WHO HAS BEEN AWAY THREE YEARS IS
EXACTLY WHAT WE SELL. The entire return engine exists to bring back the absent. Deleting him
because he is absent would delete the raw material of the most valuable thing this product does.

But "we do not delete" is not "for ever" — retention without purpose is the thing the law actually
forbids. So the shop owns the number, we hold a generous default, and the default is deliberately
far longer than any service cycle we have seen.

────────────────────────────────────────────────────────────────────────────────────────────────
2 · AN ESTABLISHMENT THAT LEFT — OURS, AND THE CLOCK IS ONE WE START OURSELVES

"Left" means the subscription ended. NOT "stopped logging in": an owner who does not open the
dashboard for two months is a product working correctly — the weekly report exists precisely
because he does not log in. Login is a terrible clock. Cancelling is a deliberate act.

AND WE DO NOT ASK BILLING WHEN IT HAPPENED, because billing exposes no internal route carrying a
subscription's end — the same gap we found with trial_end. Instead the sweep OBSERVES: the first
day it finds a tenant with no billable entitlement, it writes that date down, and the grace runs
from there.

That is better than the date we cannot get, not merely a substitute for it. It is correct even
when a subscription ends by a route that never touched us — an expiry, an operator action, a
lapse — and it starts from the day the shop actually stopped being served rather than from a
field somebody might have back-dated.

AND IT IS CLEARED THE MOMENT HE COMES BACK. A shop that resubscribes has no clock at all.

────────────────────────────────────────────────────────────────────────────────────────────────
3 · AN INDIVIDUAL'S ERASURE REQUEST — ALREADY BUILT, AND NOT A RETENTION QUESTION

core/erasure.py, immediate, nobody's decision to make. Nothing here touches it.

────────────────────────────────────────────────────────────────────────────────────────────────
AND DELETION IS NOT ERASURE OF HISTORY — WHICH IS WHY THIS FILE WRITES NO DELETION OF ITS OWN

It calls the erasure that already exists. The number and the name go; `subject_ref`, the visit
counts and the dates stay. The indicators are unaffected because they already run on pseudonyms —
an establishment does not lose three years of statistics because one number was cleared.

Writing a second deletion here would be a second definition of "erased", and the first time the
two disagreed, one of them would be the one a regulator read.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any
from app.adapters import internal_http

from app.core.models import CUSTOMERS

# Where we record the first day an establishment was found unsubscribed. Ours, not billing's.
LAPSED = "lapsed_since"

# The per-tenant setting, read through RuntimeConfig — which already exists, is already audited,
# and is already settable from the operator console. A new table and a new screen would have been
# a second way to configure something the platform configures.
#
# SPELLED AS THE SETTINGS FIELD, not as a dotted name of our own: RuntimeConfig refuses any key
# that is not a real field on Settings, precisely so a knob cannot be offered that nothing reads.
KEY_CUSTOMER_YEARS = "RETENTION_CUSTOMER_YEARS"

DAY = 86400
YEAR = 365 * DAY


def _now() -> int:
    return int(time.time())


@dataclass(frozen=True)
class Policy:
    """The two numbers, and where each comes from."""

    # HIS, with our default. Five years without a visit is far longer than any cycle we serve —
    # a car needs oil twice a year, a workshop sees a customer within one. The generosity is the
    # point: the cost of keeping a number too long is bounded, and the cost of deleting a
    # returning customer's history is the product.
    customer_years: int = 5
    # OURS. Two years after the subscription ended, because deleting his history is exactly what a
    # competitor needs in order to take him (spec §16.4.2) — and a shop that finds its data
    # waiting comes back. Long enough to be a welcome, short enough to be a policy.
    lapsed_years: int = 2

    def customer_horizon(self, now: int) -> int:
        """A last_visit older than this is past the line."""
        return now - self.customer_years * YEAR

    def lapsed_horizon(self, now: int) -> int:
        return now - self.lapsed_years * YEAR


def due_customers(rows: list[dict], *, now: int, policy: Policy) -> list[dict]:
    """Which customers are past the horizon — and which are deliberately not.

    NEVER TOUCHED, whatever their date:

      a row already cleared    no phone and no name means the erasure ran. Running it again would
                               count work nobody did and log a deletion that deleted nothing.
      a row with no last_visit It has never been seen. Treating "unknown" as "ancient" would erase
                               a customer recorded this morning by an import that did not carry
                               dates — the failure that looks like data loss and is.
    """
    horizon = policy.customer_horizon(now)
    out = []
    for row in rows or []:
        if not (row.get("phone") or row.get("name")):
            continue
        last = int(row.get("last_visit") or 0)
        if last <= 0:
            continue
        if last < horizon:
            out.append(row)
    return out


@dataclass
class Lapsed:
    """The first day we found this establishment without a live subscription."""

    tenant: str
    since: int = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.tenant, "tenant": self.tenant, "since": self.since}


class LapsedStore:
    """Our own clock, because billing does not expose the one we would rather have.

    ONE ROW PER ESTABLISHMENT, WRITTEN ONCE. The question is "since when", so a second write on the
    second day would reset the very clock it is meant to measure — and nothing would look wrong.
    """

    def __init__(self, store: Any) -> None:
        self._s = store

    async def note(self, tenant: str, *, now: int | None = None) -> int:
        """Record that this establishment has no live subscription. Returns the date it started.

        Idempotent by design: called on every sweep, it writes only the first time.
        """
        row = await self._s.get(LAPSED, tenant)
        if row is not None:
            return int(row.get("since") or 0)
        rec = Lapsed(tenant=tenant, since=_now() if now is None else now)
        await self._s.put(LAPSED, tenant, rec.to_dict())
        return rec.since

    async def clear(self, tenant: str) -> None:
        """He came back. The clock does not just stop — it never happened."""
        await self._s.delete(LAPSED, tenant)

    async def since(self, tenant: str) -> int:
        row = await self._s.get(LAPSED, tenant)
        return int((row or {}).get("since") or 0)

    async def count(self, limit: int = 500) -> int:
        """How many establishments have a clock running. The operator console's one number."""
        return len(await self._s.scan_all(LAPSED, limit) or [])

    async def due(self, *, now: int, policy: Policy, limit: int = 500) -> list[str]:
        """Establishments whose grace has run out."""
        horizon = policy.lapsed_horizon(now)
        rows = await self._s.scan_all(LAPSED, limit)
        return [str(r.get("tenant")) for r in (rows or [])
                if int(r.get("since") or 0) and int(r["since"]) < horizon]


async def policy_for(runtime_config: Any, tenant: str, default: Policy = Policy()) -> Policy:
    """The establishment's own retention, or ours.

    READ THROUGH RuntimeConfig, which already exists and is already audited — so the setting has an
    operator surface, a history of who changed it, and no new model. A shop may SHORTEN it; the
    ceiling is ours, because "keep everything for fifty years" is not a preference we may honour.
    """
    if runtime_config is None:
        return default
    try:
        years = int(await runtime_config.get(tenant=tenant, key=KEY_CUSTOMER_YEARS,
                                             default=default.customer_years))
    except (TypeError, ValueError):
        return default
    # A NONSENSE VALUE FALLS BACK RATHER THAN APPLYING. Zero would erase every customer on the next
    # sweep, and a negative would erase them all including this morning's — from one bad edit in a
    # console field.
    if years < 1 or years > default.customer_years:
        return default
    return Policy(customer_years=years, lapsed_years=default.lapsed_years)


class NullSubscriptions:
    """Says UNKNOWN, and unknown never starts a clock.

    The default, so a misconfiguration cannot begin counting toward a deletion. A retention clock
    started by an unreachable billing would be indistinguishable from a real one two years later.
    """

    async def live(self, tenant: str) -> bool | None:
        return None


class HttpSubscriptions:
    """Does this establishment still have a live subscription?

    ASKED BY ENTITLEMENT, not by reading a subscription row, because entitlements are the answer
    billing actually publishes internally: `NOT_ENTITLED` is the same signal the message quota
    already acts on, and it is true for every way a subscription can end.

    UNREACHABLE ANSWERS UNKNOWN, NEVER "GONE". Fail-open here is not a convenience — an outage
    that answered "gone" would write a lapse date for every establishment in the platform, and
    nothing would look wrong until the grace expired.
    """

    def __init__(self, *, billing_url: str, check_path: str, key: str, token: str,
                 timeout: int = 8) -> None:
        self._url = billing_url.rstrip("/") + check_path
        self._key = key
        self._token = token
        self._timeout = timeout

    async def live(self, tenant: str) -> bool | None:
        import json
        import urllib.error
        import urllib.parse

        q = urllib.parse.urlencode({"tenant": tenant, "key": self._key, "amount": 1})
        try:
            # Built in adapters/internal_http.py, the one place this service attaches the token.
            # OFF THE EVENT LOOP — fixed 2026-09-12, a real gap a QA audit found: get_json() is a
            # blocking urllib call, unwrapped, directly inside this async method.
            out = await asyncio.to_thread(
                internal_http.get_json, f"{self._url}?{q}", self._token, self._timeout)
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
            return None
        if str(out.get("error") or "") == "NOT_ENTITLED":
            return False
        # ALLOWED IS NOT THE TEST — a quota exhausted this month still means a live subscription.
        # Only the absence of any entitlement says he left.
        return True


@dataclass
class Swept:
    """What the sweep did, in the shape the cron logs and the audit record read."""

    customers: int = 0
    tenants_lapsed: int = 0
    establishments_erased: int = 0
    scanned: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {"customers": self.customers, "tenants_lapsed": self.tenants_lapsed,
                "establishments_erased": self.establishments_erased, "scanned": self.scanned}


class Sweeper:
    """The nightly pass. It decides WHO is past the line; it does not decide what erasing means.

    Every deletion goes through core/erasure.py — the same code a DSAR runs. A second deletion
    written here would be a second definition of "erased", and the first time the two disagreed,
    one of them would be the one a regulator read.
    """

    def __init__(self, *, store: Any, eraser: Any, runtime_config: Any = None,
                 subscriptions: Any = None, default: Policy = Policy(),
                 scan_cap: int = 20_000) -> None:
        self._store = store
        self._eraser = eraser
        self._config = runtime_config
        self._subs = subscriptions or NullSubscriptions()
        self._default = default
        self._cap = scan_cap
        self.lapsed = LapsedStore(store)

    async def sweep(self, *, now: int | None = None) -> Swept:
        now = _now() if now is None else now
        rows = await self._store.scan_all(CUSTOMERS, self._cap) or []
        out = Swept(scanned=len(rows))

        # THE TENANT SET COMES OUT OF THE ROWS, not from a registry — because operations keeps no
        # tenant table, and inventing one here would be a second list of establishments to drift
        # against the real one.
        by_tenant: dict[str, list[dict]] = {}
        for row in rows:
            by_tenant.setdefault(str(row.get("tenant") or ""), []).append(row)
        by_tenant.pop("", None)

        for tenant, tenant_rows in by_tenant.items():
            policy = await policy_for(self._config, tenant, self._default)
            live = await self._subs.live(tenant)
            gone = False
            if live is True:
                await self.lapsed.clear(tenant)
            elif live is False:
                await self.lapsed.note(tenant, now=now)
                since = await self.lapsed.since(tenant)
                gone = bool(since) and since < policy.lapsed_horizon(now)
            # live is None → UNKNOWN. No clock started, no clock cleared.

            if gone:
                # HIS GRACE RAN OUT, so every customer goes, not only the old ones.
                for row in tenant_rows:
                    if row.get("phone") or row.get("name"):
                        await self._erase(tenant, row)
                        out.customers += 1
                out.establishments_erased += 1
                # THE LAPSE ROW STAYS. It carries the date we first saw him gone, which is the
                # only remaining answer to "when did this start" once the customers are cleared —
                # and clearing it here would restart the two years on a shop that no longer has
                # anything to delete. Only his RETURN clears it.
                continue

            for row in due_customers(tenant_rows, now=now, policy=policy):
                await self._erase(tenant, row)
                out.customers += 1

        out.tenants_lapsed = await self.lapsed.count()
        return out

    async def _erase(self, tenant: str, row: dict) -> None:
        # BY PHONE, because that is what erase() hashes into the subject_ref it locates by. A row
        # already cleared has no phone — which is why due_customers skips it rather than sending
        # an empty string here and erasing whoever hashes to it.
        await self._eraser.erase(tenant, str(row.get("phone") or ""))
