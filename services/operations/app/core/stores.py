"""Storage for operations' entities — and the one place tenant isolation is enforced.

WHY ISOLATION LIVES HERE AND NOT IN THE HANDLERS. A handler that remembers to filter by tenant is
a handler that can forget, and the forgetting is invisible: the endpoint works, the tests pass
against one tenant's data, and the leak is discovered by a customer. Every read below takes the
tenant as a required argument and every write stamps it, so the only way to cross a boundary is to
pass the wrong tenant deliberately — and the tenant comes off a verified token, never off a body.

KEYS ARE PREFIXED BY TENANT. `{tenant}|{id}` rather than a bare id, which means a row cannot be
fetched by guessing an id from another establishment even if a handler is wrong. Defence in depth:
the filter is the control, the key layout is what catches the day the filter is not.
"""
from __future__ import annotations

import time

import uuid
from typing import Any

from app.adapters.datastore.drain import drain
from app.core import privacy_requests as PR
from app.core.models import (ASSETS, BRANCHES, CUSTOMERS, OPERATORS, SERVICES, VISITS,
                             Asset, Branch, Customer, Operator, Service, Visit)

_PAGE = 100


def new_id(prefix: str) -> str:
    """A random id, never a sequence. A sequential id tells anyone who holds one how many
    customers an establishment has, and lets them ask for the next."""
    return f"{prefix}_{uuid.uuid4().hex}"


def _key(tenant: str, ident: str) -> str:
    return f"{tenant}|{ident}"


class _Base:
    collection = ""

    def __init__(self, store) -> None:
        self._s = store

    async def _get(self, tenant: str, ident: str) -> dict[str, Any] | None:
        if not tenant or not ident:
            return None
        return await self._s.get(self.collection, _key(tenant, ident))

    async def _put(self, tenant: str, ident: str, row: dict[str, Any]) -> None:
        # `tenant` is written into the row as well as the key: `find` filters on the field, and a
        # row whose field disagrees with its key would be invisible to every query that matters.
        row["tenant"] = tenant
        await self._s.put(self.collection, _key(tenant, ident), row)

    async def _find(self, tenant: str, where: dict[str, Any] | None = None, *,
                    limit: int = _PAGE, after: str | None = None,
                    sort: tuple[str, str] = ("created", "desc")) -> tuple[list[dict], str | None]:
        filt: dict[str, Any] = {"tenant": tenant}
        if where:
            filt.update(where)
        return await self._s.find(self.collection, filt, limit=limit, after=after, sort=sort)


class PrivacyRequestStore(_Base):
    """What his customers asked HIM for — see core/privacy_requests.py for why we record and he acts."""

    collection = PR.PRIVACY_REQUESTS

    async def open_request(self, tenant: str, subject_ref: str, kind: str) -> PR.PrivacyRequest:
        """Record an ask, or return the one already standing.

        IDEMPOTENT ON PURPOSE. A customer who taps twice — or taps again after being asked to
        confirm — has made one request. Two rows would show his shop a queue that overstates what
        is owed, and a shop that sees five requests where there is one stops reading the list.
        """
        ident = PR.natural_key(tenant, subject_ref, kind).replace("|", "_")
        row = await self._get(tenant, ident)
        if row and row.get("status") == PR.OPEN:
            return PR.PrivacyRequest(**row)
        req = PR.PrivacyRequest(id=ident, tenant=tenant, subject_ref=subject_ref, type=kind)
        await self._put(tenant, ident, req.__dict__.copy())
        return req

    async def list_open(self, tenant: str, limit: int = 50) -> list[PR.PrivacyRequest]:
        rows, _ = await self._find(tenant, {"status": PR.OPEN}, limit=limit, sort=("at", "asc"))
        return [PR.PrivacyRequest(**r) for r in rows]

    async def all_for_tenant(self, tenant: str, limit: int = 500) -> list[dict[str, Any]]:
        """Open AND closed — the evidence file needs both, and closed is the half that proves we
        answered. `list_open` is the working queue and deliberately shows only what is owed."""
        rows, _ = await self._find(tenant, {}, limit=limit, sort=("at", "asc"))
        return list(rows)

    async def close(self, tenant: str, request_id: str, by: str) -> bool:
        """Answered. WHO closed it is kept, because "we answered him" is a claim that needs a name."""
        row = await self._get(tenant, request_id)
        if not row:
            return False
        row["status"] = PR.DONE
        row["closed_at"] = int(time.time())
        row["closed_by"] = by
        await self._put(tenant, request_id, row)
        return True


class CustomerStore(_Base):
    collection = CUSTOMERS

    async def get(self, tenant: str, ident: str) -> Customer | None:
        row = await self._get(tenant, ident)
        return Customer(**row) if row else None

    async def by_phone(self, tenant: str, phone: str) -> Customer | None:
        """The lookup the field screen makes on every save. Exact match — the PREFIX search that
        the keypad needs is served by search-service's /suggest, not by this store: a prefix scan
        over a datastore is a table scan, and this call sits inside a five-second budget."""
        rows, _ = await self._find(tenant, {"phone": phone}, limit=1)
        return Customer(**rows[0]) if rows else None

    async def save(self, c: Customer) -> Customer:
        await self._put(c.tenant, c.id, c.__dict__.copy())
        return c

    async def recent(self, tenant: str, limit: int = 10) -> list[Customer]:
        """The recent-customers strip. Sorted by last_visit, which is why that field is
        denormalised onto the customer — computing it from visits on every keystroke would put a
        join on the hot path."""
        rows, _ = await self._find(tenant, limit=limit, sort=("last_visit", "desc"))
        return [Customer(**r) for r in rows]

    async def by_refs(self, tenant: str, refs: set[str]) -> list[Customer]:
        """The customers behind a set of pseudonyms — for the overdue list, which arrives from
        reminders carrying `subject_ref` and no names at all.

        ONE READ, FILTERED IN MEMORY, and that is a deliberate trade rather than laziness. The
        datastore has no `in` predicate, so the alternative is one round trip per pseudonym: fifty
        overdue customers would be fifty reads to paint one list. An establishment's customer table
        is thousands of rows at most — the size of one shop, not of the product.
        """
        if not refs:
            return []
        # DRAINED, AND THE OLD `limit=10_000` WAS WORSE THAN IT LOOKS. Without a `sort` the store
        # defaults to `("created", "desc")` — NEWEST FIRST — so a shop past ten thousand customers
        # resolved this set against its most recently created ones. And the people this list is
        # about are the OVERDUE, who are by definition the oldest: two hundred pseudonyms came back
        # as forty names, and «رجع وصرف: 61» was shown where the truth was three hundred. That is
        # the number an owner reads when he decides whether to stop a campaign.
        rows = await drain(self._s, self.collection, {"tenant": tenant}, sort=("created", "asc"))
        return [Customer(**r) for r in rows if r.get("subject_ref") in refs]

    async def all_for_tenant(self, tenant: str) -> list[Customer]:
        """Every customer of one establishment — all of them, or an error saying why not."""
        rows = await drain(self._s, self.collection, {"tenant": tenant}, sort=("created", "asc"))
        return [Customer(**r) for r in rows]


class AssetStore(_Base):
    collection = ASSETS

    async def get(self, tenant: str, ident: str) -> Asset | None:
        row = await self._get(tenant, ident)
        return Asset(**row) if row else None

    async def by_plate(self, tenant: str, plate: str) -> list[Asset]:
        """Cars carrying this plate, newest first. A list, because a plate is not unique: it is
        typed by a person and cars change hands (models.py). The caller decides; we do not pick
        silently and pretend there was only one."""
        rows, _ = await self._find(tenant, {"plate": plate}, limit=5, sort=("created", "desc"))
        return [Asset(**r) for r in rows]

    async def for_customer(self, tenant: str, customer_id: str) -> list[Asset]:
        rows, _ = await self._find(tenant, {"customer_id": customer_id})
        return [Asset(**r) for r in rows]

    async def save(self, a: Asset) -> Asset:
        await self._put(a.tenant, a.id, a.__dict__.copy())
        return a


class ServiceStore(_Base):
    collection = SERVICES

    async def get(self, tenant: str, ident: str) -> Service | None:
        row = await self._get(tenant, ident)
        return Service(**row) if row else None

    async def list(self, tenant: str, *, active_only: bool = True) -> list[Service]:
        rows, _ = await self._find(tenant, {"active": True} if active_only else None,
                                   limit=200, sort=("sort", "asc"))
        return [Service(**r) for r in rows]

    async def catchall(self, tenant: str) -> Service | None:
        """The tenant's "خدمة أخرى" entry, if it has one.

        Looked up rather than assumed: a tenant provisioned before the catch-all existed does not
        have one, and an integration sending an unknown service to such a tenant must get a clean
        rejection rather than a crash.
        """
        rows, _ = await self._find(tenant, {"catchall": True}, limit=1)
        return Service(**rows[0]) if rows else None

    async def save(self, s: Service) -> Service:
        await self._put(s.tenant, s.id, s.__dict__.copy())
        return s

    async def save_new(self, **fields: Any) -> Service:
        """Create a service from an invoice line (core/invoices.py).

        A thin wrapper rather than making the caller build a Service: the invoice path is the one
        place a service is created by a machine rather than by a person, and a constructor call
        spread across two modules is a field somebody forgets on one side.
        """
        svc = Service(**fields)
        await self.save(svc)
        return svc

    async def by_external_id(self, tenant: str, external_id: str) -> Service | None:
        if not external_id:
            return None
        for s in await self.list(tenant, active_only=False):
            if s.external_id == external_id:
                return s
        return None


class VisitStore(_Base):
    collection = VISITS

    async def get(self, tenant: str, ident: str) -> Visit | None:
        row = await self._get(tenant, ident)
        return Visit(**row) if row else None

    async def by_idempotency_key(self, tenant: str, key: str) -> Visit | None:
        """The double-tap guard's read. Cheap by design: one indexed lookup before the write, not
        a lock and not a transaction — the cost of this check is paid on every save, so it has to
        be the cheapest thing that is correct."""
        if not key:
            return None
        rows, _ = await self._find(tenant, {"idempotency_key": key}, limit=1)
        return Visit(**rows[0]) if rows else None

    async def for_customer(self, tenant: str, customer_id: str, limit: int = 20) -> list[Visit]:
        rows, _ = await self._find(tenant, {"customer_id": customer_id}, limit=limit)
        return [Visit(**r) for r in rows]

    async def offers_spent(self, tenant: str, customer_id: str, limit: int = 200) -> list[str]:
        """The send-log rows this customer has already spent — the answer reminders needs.

        BOUNDED, and the bound is the point: an offer older than the last 200 visits is long
        expired, and an unbounded read on a path the counter waits for is how a screen becomes
        slow for the shops that use us most.
        """
        rows, _ = await self._find(tenant, {"customer_id": customer_id}, limit=limit)
        return [str(r.get("offer_ref") or "") for r in rows if r.get("offer_ref")]

    async def unseamed(self, tenant: str, *, before: int, limit: int = 200) -> list[Visit]:
        """Visits whose after-work never finished — the sweep's work list (ز-7).

        `before` excludes the ones still in flight: a visit recorded three seconds ago has its
        seams running right now, and picking it up would race the request that is still finishing.
        The caller passes «now minus a few minutes».

        BOUNDED, like every read on a clock in this service. A shop with a backlog gets the oldest
        first and the rest on the next tick; an unbounded read here is a five-minute cron that
        becomes a ten-minute one on the busiest shop we have.
        """
        rows, _ = await self._find(tenant, limit=limit, sort=("created", "asc"))
        return [Visit(**r) for r in rows
                if not int(r.get("seamed_at") or 0) and int(r.get("created") or 0) < before]

    async def save(self, v: Visit) -> Visit:
        await self._put(v.tenant, v.id, v.__dict__.copy())
        return v


class OperatorStore(_Base):
    collection = OPERATORS

    async def get(self, tenant: str, ident: str) -> Operator | None:
        row = await self._get(tenant, ident)
        return Operator(**row) if row else None

    async def list(self, tenant: str) -> list[Operator]:
        rows, _ = await self._find(tenant, limit=200)
        return [Operator(**r) for r in rows]

    async def get_by_person(self, tenant: str, person_id: str) -> Operator | None:
        """The row for the operator asking — not by his ROLE (many share `operator`), by WHO he
        actually is at identity. A linear scan over one tenant's roster (`list`'s own 200-row
        cap), same scale assumption every other read here already makes; a real index is worth it
        only past that size."""
        if not person_id:
            return None
        for o in await self.list(tenant):
            if o.person_id == person_id:
                return o
        return None

    async def save(self, o: Operator) -> Operator:
        await self._put(o.tenant, o.id, o.__dict__.copy())
        return o


class BranchStore(_Base):
    collection = BRANCHES

    async def get(self, tenant: str, ident: str) -> Branch | None:
        row = await self._get(tenant, ident)
        return Branch(**row) if row else None

    async def list(self, tenant: str) -> list[Branch]:
        rows, _ = await self._find(tenant, limit=200)
        return [Branch(**r) for r in rows]

    async def save(self, b: Branch) -> Branch:
        await self._put(b.tenant, b.id, b.__dict__.copy())
        return b

    async def browse_platform(self, *, limit: int = 200,
                              after: str | None = None) -> tuple[list[Branch], str | None]:
        """A page of branches ACROSS ALL TENANTS — same fence as billing-service's own
        `browse_platform`: this deliberately crosses the tenancy wall this module's own header
        note exists to enforce everywhere else, so it takes a MANDATORY, whitelisted filter
        (`active`) rather than calling `self._s.find` with an empty one — an unfiltered
        cross-tenant dump is an exfiltration primitive, not a feature. Gated at the route on
        `platform.operations` alone, and audited there.
        """
        rows, nxt = await self._s.find(self.collection, {"active": True},
                                       limit=limit, after=after, sort=("created", "desc"))
        return [Branch(**r) for r in rows], nxt
