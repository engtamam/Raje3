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

import asyncio
import time

import uuid
from typing import Any

from app.adapters.datastore.drain import drain
from app.core import privacy_requests as PR
from app.core.models import (ACCOUNT_SETTINGS, ASSETS, BRANCHES, CUSTOMERS, OPERATOR_STEP_STATS,
                             OPERATORS, PACKAGES, PROCEDURE_STEPS, SERVICES, TRANSLATIONS, VISITS,
                             Asset, Branch, Customer, Operator, OperatorStepStat, Package,
                             ProcedureStep, Service, TranslationEntry, Visit)
from app.core.translations import detect_change

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

    async def get_many(self, tenant: str, ids: set[str]) -> dict[str, Customer]:
        """A page of ratings' own enrichment — the rating app's «التقييمات» tab shows who left
        each one, so it can be answered or reached, never just an anonymous `customer_id`.

        DIRECT KEY GETS, ONE PER ID, NOT `by_refs`'s FULL-TABLE DRAIN — a ratings page is at most
        a hundred rows (the route's own `limit` cap), so a hundred direct-key reads is a fraction
        of `by_refs`'s cost, which exists only because IT has no key to get by (a pseudonym is not
        this store's own id). Concurrent, since each is an independent read with nothing to order.
        """
        if not ids:
            return {}
        found = await asyncio.gather(*(self.get(tenant, i) for i in ids))
        return {c.id: c for c in found if c is not None}

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

    async def conversion_by_source(self, tenant: str) -> dict[str, dict[str, int]]:
        """How many customers each channel brought in, and how many of them ever became a real
        visit — the one question behind insights' own lead-conversion indicator
        (services/insights/app/core/tick.py's own `lead_conversion`).

        `visit_count > 0` IS "CONVERTED", NOT A SEPARATE BOOKING CHECK. An attended booking is
        already a Visit by the time it reaches this store — bookings-service's own
        `VisitGateway.record` is the ONLY path that ever produces one (see its own docstring) —
        so this single counter already answers "ever visited OR ever attended a booking" without
        this service needing to ask a peer anything.
        """
        rows = await drain(self._s, self.collection, {"tenant": tenant}, sort=("created", "asc"))
        out: dict[str, dict[str, int]] = {}
        for r in rows:
            src = str(r.get("source") or "manual")
            bucket = out.setdefault(src, {"total": 0, "converted": 0})
            bucket["total"] += 1
            if int(r.get("visit_count") or 0) > 0:
                bucket["converted"] += 1
        return out


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
        """The WHOLE catalogue, not a page of it (fixed 2026-09-12, a real gap a QA audit found).

        The old `limit=200` silently discarded the cursor: every caller treated the 200 rows it
        got back as the complete catalogue, and a shop past that size had services `by_external_id`
        could never find (so an invoice line for its 201st product auto-created a duplicate every
        time) and a «خدماتي» screen that never showed the rest. `drain` pages until the store is
        exhausted and raises rather than truncating if a tenant somehow has more than its budget.
        """
        where: dict[str, Any] = {"tenant": tenant}
        if active_only:
            where["active"] = True
        rows = await drain(self._s, self.collection, where, sort=("sort", "asc"))
        return [Service(**r) for r in rows]

    async def has_any_active(self, tenant: str) -> bool:
        """Cheap existence check — one row, not the whole catalogue. For a caller (the customer-
        success scan) asking «did this shop ever add a service?» across every tenant, `list()`'s
        own 200-row page would be 200x the real cost for an answer that only needs 0 or 1."""
        rows, _ = await self._find(tenant, {"active": True}, limit=1)
        return bool(rows)

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
        await TranslationStore(self._s).detect_and_mark(
            s.tenant, "service", s.id, "name", s.name)
        await TranslationStore(self._s).detect_and_mark(
            s.tenant, "service", s.id, "description", s.description)
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


class PackageStore(_Base):
    collection = PACKAGES

    async def get(self, tenant: str, ident: str) -> Package | None:
        row = await self._get(tenant, ident)
        return Package(**row) if row else None

    async def list(self, tenant: str, *, active_only: bool = True) -> list[Package]:
        rows, _ = await self._find(tenant, {"active": True} if active_only else None,
                                   limit=200, sort=("sort", "asc"))
        return [Package(**r) for r in rows]

    async def save(self, p: Package) -> Package:
        await self._put(p.tenant, p.id, p.__dict__.copy())
        return p


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

    async def has_any(self, tenant: str) -> bool:
        """Cheap existence check — one row, not a count. The customer-success scan's own "has this
        shop ever recorded a visit at all?" needs exactly this, across every tenant; a real count
        would cost a full scan per tenant for a question a single indexed row already answers."""
        rows, _ = await self._find(tenant, {}, limit=1)
        return bool(rows)

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

    async def staff_performance(self, tenant: str, *, since: int, until: int, branch_id: str = ""
                                ) -> dict[str, dict[str, int]]:
        """Per-operator {"visits", "ratings", "rating_sum"} over `[since, until]` (epoch seconds)
        — the rating app's staff-performance report (a shop owner comparing staff, not one visit).

        DRAINS THE WHOLE TENANT SET rather than reading one capped page like `ratings_summary`
        does — that method's own docstring accepts undercounting past its `limit` because it feeds
        a rolling digest number; a report an owner reads to judge a specific employee needs an
        exact count, not an approximation that quietly gets worse the more that employee works.
        `where` is equality-only (same limitation `ratings`/`by_actor` already document), so the
        time window is applied in Python after the full set comes back.

        `occurred_at` (the device-claimed time the service actually happened) is preferred over
        `created` (our own receipt time) for "which period does this visit belong to" — the two
        differ when a visit is recorded late, and a report window should follow the work, not the
        keystroke. Falls back to `created` for the rare row with no `occurred_at` set.
        """
        where: dict[str, Any] = {"tenant": tenant}
        if branch_id:
            where["branch_id"] = branch_id
        rows = await drain(self._s, self.collection, where, sort=("created", "desc"))
        by_operator: dict[str, dict[str, int]] = {}
        for row in rows:
            occurred = int(row.get("occurred_at") or 0) or int(row.get("created") or 0)
            if occurred < since or occurred > until:
                continue
            op = str(row.get("operator_id") or "")
            if not op:
                continue
            entry = by_operator.setdefault(op, {"visits": 0, "ratings": 0, "rating_sum": 0})
            entry["visits"] += 1
            rating = int(row.get("rating") or 0)
            if rating:
                entry["ratings"] += 1
                entry["rating_sum"] += rating
        return by_operator

    async def ratings(self, tenant: str, *, stars: int | None = None, handled: bool | None = None,
                      branch_id: str = "", operator_id: str = "", limit: int = 50,
                      after: str | None = None) -> tuple[list[Visit], str | None]:
        """Every visit a customer actually rated — the console's «التقييمات» tab (rating-app-
        feature.md phase 5). `stars` narrows to one exact rank when given; otherwise "has any
        rating at all", expressed as membership on [1, 2, 3, 4, 5] (0 is the model's own «not yet»
        sentinel, never itself a valid filter value, so it is simply excluded by the list).

        `handled=False` is an EXACT filter (`rating_handled_at == 0`, the field's own untouched
        value) and pages correctly like any other `_find` call. `handled=True` cannot be
        expressed as an equality filter (any nonzero timestamp qualifies, and `_find` only
        supports exact/membership match) — it is applied AFTER the page is fetched instead, which
        is a KNOWN, ACCEPTED LIMITATION: a page can come back with fewer than `limit` handled rows
        even though more exist, since the underlying page was capped before this filter ran. The
        owner-facing screen is not paginating thousands of ratings, so this is an acceptable
        approximation rather than a real gap — same "known limit, stated honestly" posture as
        `unseamed`'s own bounded read above.

        `operator_id` — one staff member's own ratings only, sorted newest-first same as everything
        else here — the rating-drop alert's own read (`core/rating_alerts.py`): "his last N ratings",
        never a page some OTHER operator's ratings could crowd out.
        """
        where: dict[str, Any] = {"rating": [stars] if stars else [1, 2, 3, 4, 5]}
        if branch_id:
            where["branch_id"] = branch_id
        if operator_id:
            where["operator_id"] = operator_id
        if handled is False:
            where["rating_handled_at"] = 0
        rows, cursor = await self._find(tenant, where, limit=limit, after=after,
                                        sort=("rated_at", "desc"))
        visits = [Visit(**r) for r in rows]
        if handled is True:
            visits = [v for v in visits if v.rating_handled_at > 0]
        return visits, cursor


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


class AccountSettingsStore(_Base):
    """Platform-wide account preferences — TODAY, ONLY `locale` — keyed by the JWT subject
    directly (`{tenant}|{subject}`, same key layout `_Base` already uses everywhere else), never
    by an `Operator` row. That is the whole point of this store existing separately from
    `OperatorStore`: an owner has no Operator row and never will (see `Operator`'s own docstring),
    so a preference keyed on one structurally excludes him. A JWT subject exists for every
    logged-in account regardless of role."""

    collection = ACCOUNT_SETTINGS

    async def get_by_subject(self, tenant: str, subject: str) -> dict[str, Any] | None:
        return await self._get(tenant, subject)

    async def set_locale(self, tenant: str, subject: str, locale: str) -> dict[str, Any]:
        row = await self.get_by_subject(tenant, subject) or {}
        row["locale"] = locale
        await self._put(tenant, subject, row)
        return row

    async def set_name(self, tenant: str, subject: str, name: str) -> dict[str, Any]:
        """The account holder's own display name — same reasoning as `set_locale`: an owner has
        no `Operator` row (the ONLY place a name existed before this), so every OTHER account
        (an employee hired through `hire()`) already had a real name and the owner alone had
        none anywhere in the product. Keyed by subject, same as locale, so it works for any
        logged-in account regardless of role."""
        row = await self.get_by_subject(tenant, subject) or {}
        row["name"] = name
        await self._put(tenant, subject, row)
        return row


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


class ProcedureStepStore(_Base):
    """The shared protocol catalogue — see `ProcedureStep`'s own docstring for why this is a real
    collection rather than free text repeated on each service."""

    collection = PROCEDURE_STEPS

    async def get(self, tenant: str, ident: str) -> ProcedureStep | None:
        row = await self._get(tenant, ident)
        return ProcedureStep(**row) if row else None

    async def get_many(self, tenant: str, ids: list[str]) -> dict[str, ProcedureStep]:
        """Resolves a `Service.procedure_step_ids` list (or a `Visit.rating_issue_step_ids` one)
        back to real text, in one call — same "direct key gets, concurrent" shape as
        `CustomerStore.get_many`, for the same reason: a service's own protocol is at most a few
        dozen steps, never a scan-sized collection."""
        if not ids:
            return {}
        found = await asyncio.gather(*(self.get(tenant, i) for i in set(ids)))
        return {s.id: s for s in found if s is not None}

    async def list(self, tenant: str, *, active_only: bool = True) -> list[ProcedureStep]:
        """The WHOLE catalogue — same `drain`-not-`limit` reasoning `ServiceStore.list`'s own
        docstring gives: a shop's protocol list is exactly the kind of thing an owner expects to
        see in full the moment he opens the new tab, not truncated at an arbitrary page size."""
        where: dict[str, Any] = {"tenant": tenant}
        if active_only:
            where["active"] = True
        rows = await drain(self._s, self.collection, where, sort=("created", "asc"))
        return [ProcedureStep(**r) for r in rows]

    async def save(self, s: ProcedureStep) -> ProcedureStep:
        await self._put(s.tenant, s.id, s.__dict__.copy())
        await TranslationStore(self._s).detect_and_mark(
            s.tenant, "procedure_step", s.id, "text", s.text)
        return s


class OperatorStepStatStore(_Base):
    """The per-operator training signal — see `OperatorStepStat`'s own docstring for the
    incremental-update design and its one stated trade-off (read-modify-write, not a true atomic
    counter)."""

    collection = OPERATOR_STEP_STATS

    @staticmethod
    def _stat_id(operator_id: str, step_id: str) -> str:
        return f"{operator_id}:{step_id}"

    async def get(self, tenant: str, operator_id: str, step_id: str) -> OperatorStepStat | None:
        row = await self._get(tenant, self._stat_id(operator_id, step_id))
        return OperatorStepStat(**row) if row else None

    async def for_operator(self, tenant: str, operator_id: str) -> list[OperatorStepStat]:
        """The whole "أين يحتاج تدريباً" list for one person's own record — a staff profile page,
        never a tenant-wide scan (filtered on `operator_id`, an indexed-by-containment field the
        same way every other `_find` call in this file already is)."""
        rows, _ = await self._find(tenant, {"operator_id": operator_id}, limit=200,
                                   sort=("times_flagged", "desc"))
        return [OperatorStepStat(**r) for r in rows]

    async def record_issue(self, tenant: str, operator_id: str, step_id: str, *,
                           critical: bool, visit_id: str, at: int) -> OperatorStepStat:
        """Called once per flagged step, from the same webhook that already writes
        `Visit.rating_issue_step_ids` — see `OperatorStepStat`'s own docstring for why this is a
        get-then-put rather than a database-level atomic increment, and why that trade-off is
        acceptable here."""
        ident = self._stat_id(operator_id, step_id)
        row = await self._get(tenant, ident)
        stat = OperatorStepStat(**row) if row else OperatorStepStat(
            id=ident, tenant=tenant, operator_id=operator_id, step_id=step_id)
        stat.times_flagged += 1
        if critical:
            stat.times_flagged_critical += 1
        stat.last_flagged_at = at
        stat.last_visit_id = visit_id
        await self._put(tenant, ident, stat.__dict__.copy())
        return stat


class TranslationStore(_Base):
    """One row per (entity_type, entity_id, field) — see `TranslationEntry`'s own docstring, and
    `core/translations.py` for the hash comparison `detect_and_mark` runs on every call."""

    collection = TRANSLATIONS

    async def get(self, tenant: str, entity_type: str, entity_id: str,
                  field: str) -> TranslationEntry | None:
        from app.core.translations import entry_id
        row = await self._get(tenant, entry_id(entity_type, entity_id, field))
        return TranslationEntry(**row) if row else None

    async def get_many(self, tenant: str, entity_type: str, entity_ids: list[str],
                       fields: tuple[str, ...]) -> dict[str, TranslationEntry]:
        """Every (entity_id, field) pair's own entry, in one round trip — same "direct key gets,
        concurrent" shape `ProcedureStepStore.get_many`'s own docstring already uses, for a locale-
        aware list read that would otherwise be one lookup per row per field. Keyed by `entry.id`
        (`f"{entity_type}:{entity_id}:{field}"`) so a caller resolving a specific row's specific
        field never needs to reconstruct it."""
        if not entity_ids or not fields:
            return {}
        found = await asyncio.gather(*(
            self.get(tenant, entity_type, eid, f) for eid in entity_ids for f in fields))
        return {e.id: e for e in found if e is not None}

    async def detect_and_mark(self, tenant: str, entity_type: str, entity_id: str, field: str,
                              source_text: str) -> TranslationEntry | None:
        """Called from `ServiceStore.save`/`ProcedureStepStore.save` on EVERY save — cheap when
        nothing changed (one get, one hash, no write) and correct when it did (see
        `detect_change`'s own docstring for why a hash rather than a dirty flag)."""
        existing = await self.get(tenant, entity_type, entity_id, field)
        updated = detect_change(existing, tenant=tenant, entity_type=entity_type,
                                entity_id=entity_id, field=field, source_text=source_text)
        if updated is None:
            return existing
        await self._put(tenant, updated.id, updated.__dict__.copy())
        return updated

    async def list_pending(self, limit: int = 500) -> list[TranslationEntry]:
        """EVERY shop's own untranslated text, across every tenant — the phase-3 worker's whole
        work list, same cross-tenant `scan_all` shape `WhatsAppConnections.all()`
        (core/connect.py) already uses for its own fleet-wide sweep. Never exposed on a route a
        shop's own token could reach; only `translations_scan` (internal-token-gated,
        api/internal.py) calls this."""
        rows = await self._s.scan_all(self.collection, max(1, min(2000, limit)))
        return [TranslationEntry(**r) for r in rows if r.get("status") == "pending"][:limit]

    async def write_result(self, tenant: str, entry_id_: str, source_hash: str,
                           translations: dict[str, str]) -> str:
        """Write a worker's own translation result back — COMPARE-AND-SWAP ON `source_hash`, not a
        blind overwrite. `entry_id_` is `TranslationEntry.id` (already includes entity_type/
        entity_id/field); `source_hash` is the hash the WORKER translated against, captured when
        its job was enqueued.

        THE HARD CASE THIS EXISTS FOR: a shop edits the same field again AFTER a translation job
        was enqueued but BEFORE it finishes — `detect_and_mark` (called from the very next `save`)
        already overwrote the row with a NEW hash and reset it to `pending`. Writing the OLD
        translation over that row would silently resurrect stale text under a `status="done"` that
        claims to answer text the shop no longer has. So this reads the row fresh, and only writes
        when its CURRENT hash still matches what the worker translated — otherwise it is a no-op,
        and returns `"stale"` so the caller acks the job without treating it as a failure (the
        entry is already correctly `pending` again, under its own new hash, for a future scan to
        pick up).

        Returns `"written"` | `"stale"` | `"missing"` (the row no longer exists — retired data,
        an entity deleted between enqueue and this write) — never raises for any of the three;
        all three are real, ordinary outcomes for a worker running well after the fact.
        """
        row = await self._s.get(self.collection, _key(tenant, entry_id_))
        if row is None:
            return "missing"
        current = TranslationEntry(**row)
        if current.source_hash != source_hash:
            return "stale"
        if not translations:
            return "stale"
        current.translations = dict(translations)
        # DONE ONLY WHEN EVERY TARGET LOCALE ANSWERED — a partial result (one locale's own
        # inference failed, see `Nllb200TranslationEngine.translate`'s own docstring) stays
        # `pending` so the NEXT scan re-enqueues exactly this entry rather than the caller having
        # to track "which locales are still missing" anywhere.
        from app.core.translations import TARGET_LOCALES
        current.status = "done" if all(l in current.translations for l in TARGET_LOCALES) else "pending"
        current.updated_at = int(time.time())
        await self._put(tenant, entry_id_, current.__dict__.copy())
        return "written"
