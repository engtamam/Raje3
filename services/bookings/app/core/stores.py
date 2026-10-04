"""Storage for bookings — and the one place tenant isolation is enforced.

Mirrors `operations/app/core/stores.py`'s shape exactly: every read takes `tenant` as a required
argument, every write stamps it, keys are prefixed `{tenant}|{id}` so a row cannot be fetched by
guessing an id from another establishment even if a caller forgets to filter.

`booking_slots` (docs/خطة-تنفيذ-الحجوزات.md §2) is the second row `save()` writes — a derived
index the daily/weekly grid reads instead of scanning every booking on every screen-open. Its key
is `{tenant}|{branch_id}|{day_bucket}|{booking_id}`: the tenant prefix is load-bearing, not
decoration — an index key built without it would make a cross-tenant scan possible even though
`Booking` itself stays correctly isolated (§4, "a data leak through a secondary index").
"""
from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any

from app.core.models import BOOKING_SLOTS, BOOKINGS, STATUS_NO_SHOW, WORKING_HOURS, Booking
from app.core.riyadh import local

# A separate collection from BOOKINGS itself — the mutex must be claimable/expirable on its own
# terms, not entangled with the row it guards. Short-lived: this only needs to cover one
# read-then-write round trip, never a human timescale.
_SAVE_LOCKS = "booking_save_locks"
_SAVE_LOCK_TTL_SECONDS = 10.0
_SAVE_LOCK_RETRY_ATTEMPTS = 40
_SAVE_LOCK_RETRY_DELAY_SECONDS = 0.05


def new_id(prefix: str) -> str:
    """A random id, never a sequence — a sequential id tells anyone who holds one how many
    bookings an establishment has, and lets them ask for the next."""
    return f"{prefix}_{uuid.uuid4().hex}"


def _key(tenant: str, ident: str) -> str:
    return f"{tenant}|{ident}"


def day_bucket(starts_at: int) -> str:
    """Which business day `starts_at` falls on, for the shop — never midnight UTC.

    The ONE definition of "which day is it", imported everywhere a day boundary matters (§4,
    "a silent assumption deciding what policy should"). Bookings straddling midnight Riyadh time
    do not exist in practice (no shop is open then), so the calendar date of the local instant is
    the day the grid shows it on.
    """
    return local(starts_at).date().isoformat()


def _slot_key(tenant: str, branch_id: str, bucket: str, booking_id: str) -> str:
    return f"{tenant}|{branch_id}|{bucket}|{booking_id}"


class ConcurrentEditError(Exception):
    """Fails closed rather than silently dropping one writer's change (§4, "a race on a shared
    resource with no lock" — the second scenario: two edits to the SAME booking, which the
    per-operator/time-bucket claim lane does not protect, since that lane exists to serialise
    DIFFERENT bookings for one operator, not two writers of one row)."""


class WorkingHoursStore:
    """One row per tenant — the establishment's own weekly policy, not the
    branch's. Raw dict in, raw dict out: `core/operations.py` owns the shape and its defaults,
    this only persists whatever it is handed."""
    collection = WORKING_HOURS

    def __init__(self, store) -> None:
        self._s = store

    async def get(self, tenant: str) -> dict[str, Any] | None:
        if not tenant:
            return None
        return await self._s.get(self.collection, tenant)

    async def save(self, tenant: str, weekly: dict[str, Any]) -> None:
        await self._s.put(self.collection, tenant, weekly)


# THE SHOP'S OWN DEFAULT ALGORITHM, when a service is in "auto" mode (Service.assignment_mode,
# operations' own models.py) and more than one eligible operator is free for a given slot — WHICH
# one gets it. One policy per tenant, same "one document, not per-branch" shape WORKING_HOURS
# already uses, for the same reason: this is an operating philosophy, not a per-branch setting.
ASSIGNMENT_SETTINGS = "assignment_settings"

# "nearest" is the DEFAULT — the owner's own rule (always the easiest default): it needs no setup
# at all, and it is the exact behaviour every shop already had before "auto" existed (whichever
# eligible operator has the soonest opening wins) — so a shop that never opens this setting keeps
# feeling like nothing changed. "least_loaded"/"manual_order" are real, named alternatives from
# real salon platforms (Vagaro's own "Most Open Schedule"/"Website Employee Lineup") for a shop
# that wants to balance load or hand-rank its own staff instead.
DEFAULT_ASSIGNMENT_ALGORITHM = "nearest"
ASSIGNMENT_ALGORITHMS = frozenset({"nearest", "least_loaded", "manual_order"})


class AssignmentSettingsStore:
    """One row per tenant: which algorithm `assignment.py` should use when a slot has more than
    one eligible, free operator, plus the manual lineup order `manual_order` reads (a plain list
    of operator ids, most-preferred first — empty until the owner actually ranks anyone)."""
    collection = ASSIGNMENT_SETTINGS

    def __init__(self, store) -> None:
        self._s = store

    async def get(self, tenant: str) -> dict[str, Any]:
        if not tenant:
            return {"algorithm": DEFAULT_ASSIGNMENT_ALGORITHM, "manual_order": []}
        row = await self._s.get(self.collection, tenant)
        if not row:
            return {"algorithm": DEFAULT_ASSIGNMENT_ALGORITHM, "manual_order": []}
        algo = str(row.get("algorithm") or DEFAULT_ASSIGNMENT_ALGORITHM)
        if algo not in ASSIGNMENT_ALGORITHMS:
            algo = DEFAULT_ASSIGNMENT_ALGORITHM
        return {"algorithm": algo, "manual_order": list(row.get("manual_order") or [])}

    async def save(self, tenant: str, *, algorithm: str, manual_order: list[str]) -> None:
        if algorithm not in ASSIGNMENT_ALGORITHMS:
            raise ValueError(f"algorithm must be one of {sorted(ASSIGNMENT_ALGORITHMS)}")
        await self._s.put(self.collection, tenant,
                          {"algorithm": algorithm, "manual_order": list(manual_order)})


class BookingStore:
    collection = BOOKINGS

    def __init__(self, store) -> None:
        self._s = store

    async def get(self, tenant: str, ident: str) -> Booking | None:
        if not tenant or not ident:
            return None
        row = await self._s.get(self.collection, _key(tenant, ident))
        return _from_row(row) if row else None

    async def by_idempotency_key(self, tenant: str, key: str) -> Booking | None:
        """The double-tap guard's read — one indexed lookup before the write, same shape as
        `VisitStore.by_idempotency_key`."""
        if not key:
            return None
        rows, _ = await self._find(tenant, {"idempotency_key": key}, limit=1)
        return _from_row(rows[0]) if rows else None

    async def for_customer(self, tenant: str, customer_id: str, limit: int = 200
                           ) -> tuple[list[Booking], bool]:
        rows, cursor = await self._find(tenant, {"customer_id": customer_id}, limit=limit)
        return [_from_row(r) for r in rows], bool(cursor)

    async def for_subject(self, tenant: str, subject_ref: str, limit: int = 200
                          ) -> tuple[list[Booking], bool]:
        """SAME QUERY as `for_customer`, keyed by the pseudonym instead of the real id — for a
        caller that only ever holds `subject_ref` (a read-only phone→pseudonym resolution, e.g.)
        and must never be handed — or made to mint — a real `customer_id` just to look up a
        history. `subject_ref` is stamped on every booking once at creation (see `Booking`'s own
        field note), so this is exactly as complete a history as `for_customer` gives, through a
        door that costs the caller nothing to open."""
        rows, cursor = await self._find(tenant, {"subject_ref": subject_ref}, limit=limit)
        return [_from_row(r) for r in rows], bool(cursor)

    async def _find(self, tenant: str, where: dict[str, Any] | None = None, *,
                    limit: int = 200) -> tuple[list[dict], str | None]:
        filt: dict[str, Any] = {"tenant": tenant}
        if where:
            filt.update(where)
        return await self._s.find(self.collection, filt, limit=limit, sort=("created", "desc"))

    async def slots_between(self, tenant: str, branch_id: str, *,
                            start_bucket: str, end_bucket: str, limit: int = 500) -> list[Booking]:
        """The grid's own query: this branch, this date range, every operator — served from the
        index, never from a full scan of `bookings` (§2, "the daily/weekly query is not
        efficiently served by the generic store").

        Day buckets are ISO date strings, so lexical comparison IS date comparison — no parsing
        needed to filter the range.

        PAGES THROUGH THE WHOLE INDEX, THE SAME WAY `counts_between` ALREADY DOES — a single
        unbounded page here (`limit=500`, no `after` cursor) used to return only a branch's
        OLDEST 500 slot rows, because `find()`'s own sort is ascending on `bucket` and there was
        no server-side range predicate to narrow it (the store has no `>=`/`<=` operator — see
        `ports/datastore.py`). A branch past 500 booking_slots rows therefore answered "no
        conflict" for its own current/future date range no matter how full it actually was — this
        is `_refuse_if_conflicting`'s ONE re-check, so that silent miss let genuinely overlapping
        bookings through with zero refusal (found in a QA audit, 2026-09-12). Stops the moment a
        page's rows run past `end_bucket` — ascending order means nothing after that point can
        still match, so this does not have to drain a branch's entire history to answer "this
        week".
        """
        wanted: list[dict[str, Any]] = []
        after: str | None = None
        while True:
            rows, after = await self._s.find(
                BOOKING_SLOTS, {"tenant": tenant, "branch_id": branch_id}, limit=500,
                after=after, sort=("bucket", "asc"))
            past_range = False
            for row in rows:
                bucket = str(row.get("bucket") or "")
                if bucket > end_bucket:
                    past_range = True
                    break
                if bucket >= start_bucket:
                    wanted.append(row)
            if past_range or not after:
                break
        wanted = wanted[:limit]
        # ONE BATCHED READ, NOT ONE `get()` PER SLOT. `nearest_slot` calls this with `limit=500`
        # over up to a 14-day window, and a sequential `get()` per row meant up to 500 awaited
        # Postgres round trips to answer one "أقرب موعد" click. `get_many` keeps the ids in the
        # order the index gave them (it is a dict lookup on the result, not a second query), so
        # the bucket ordering `find()` already sorted by survives the swap unchanged.
        booking_ids = [str(r.get("booking_id") or "") for r in wanted]
        hydrated = await self._s.get_many(
            self.collection, [_key(tenant, bid) for bid in booking_ids if bid])
        out: list[Booking] = []
        for bid in booking_ids:
            row = hydrated.get(_key(tenant, bid))
            if row is not None:
                out.append(_from_row(row))
        return out

    async def no_show_summary(self, tenant: str, *, start_bucket: str, end_bucket: str,
                              branch_id: str = "") -> dict[str, dict[str, int]]:
        """Per-operator {"total": N, "no_show": N} over a day-bucket range — the staff-performance
        report's own read (rating app, phase 2). Reads `BOOKING_SLOTS`, the SAME derived index
        `counts_between` reads beside this method, for the same reason: it already carries
        `operator_id` and `status` per row (`save()`'s own slot_row above), so this never has to
        hydrate a single `Booking` to answer "how many of this operator's bookings were no-shows".

        `branch_id` is OPTIONAL here, unlike `counts_between`/`slots_between` — a staff-performance
        report is tenant-wide by default (an operator can work more than one branch), so an empty
        `branch_id` queries every branch's slots for this tenant; a caller that wants one branch's
        picture passes it same as any other report filter.

        Pages ascending by `bucket` and stops the moment a page runs past `end_bucket`, same
        early-exit `counts_between` already uses — a report window rarely reaches this tenant's
        entire slot history.
        """
        where: dict[str, Any] = {"tenant": tenant}
        if branch_id:
            where["branch_id"] = branch_id
        totals: dict[str, dict[str, int]] = {}
        after: str | None = None
        while True:
            rows, after = await self._s.find(BOOKING_SLOTS, where, limit=500, after=after,
                                             sort=("bucket", "asc"))
            past_range = False
            for row in rows:
                bucket = str(row.get("bucket") or "")
                if bucket > end_bucket:
                    past_range = True
                    break
                if bucket < start_bucket:
                    continue
                op = str(row.get("operator_id") or "")
                if not op:
                    continue
                entry = totals.setdefault(op, {"total": 0, "no_show": 0})
                entry["total"] += 1
                if row.get("status") == STATUS_NO_SHOW:
                    entry["no_show"] += 1
            if past_range or not after:
                break
        return totals

    async def counts_between(self, tenant: str, branch_id: str, *,
                             start_bucket: str, end_bucket: str) -> dict[str, int]:
        """The month/year view's own query — how many bookings land on each day of a range,
        NEVER the bookings themselves. `slots_between` calls `self.get()` per row, which hydrates
        a full `Booking` for every slot; fine for one day or one week, wasteful for a whole year
        (docs/خطة-تصميم-تقويم-الحجوزات.md §1). This reads the SAME `BOOKING_SLOTS` index and only
        tallies `bucket` values — no `Booking` is ever built here.

        Pages through `find()` itself rather than trusting its default `limit` — the same lesson
        this session already paid for on the affiliate side (`performance_for()`/`balance()`
        paging through every referral/commission): a busy shop's full year is exactly the case a
        single bounded page would silently undercount.
        """
        counts: dict[str, int] = {}
        after: str | None = None
        while True:
            rows, after = await self._s.find(
                BOOKING_SLOTS, {"tenant": tenant, "branch_id": branch_id}, limit=500,
                after=after, sort=("bucket", "asc"))
            for row in rows:
                bucket = str(row.get("bucket") or "")
                if start_bucket <= bucket <= end_bucket:
                    counts[bucket] = counts.get(bucket, 0) + 1
            if not after:
                break
        return counts

    async def by_actor(self, tenant: str, created_by: str, *, branch_id: str = "",
                       since: int | None = None, until: int | None = None,
                       limit: int = 2000) -> tuple[list[Booking], bool]:
        """Every booking THIS actor made (`created_by` — whatsapp-assistant's own attribution
        stamp, see `InternalCreateBookingIn`'s note in api/internal.py), optionally narrowed to one
        branch and a `created` window. Returns (rows, truncated) — `truncated` is honest the same
        way `counts_between`'s own paging loop is: a real cap was hit, the caller must not present
        the result as complete.

        `where` is equality-only (see the port's own docstring), so `since`/`until` are applied in
        Python after each page — sorted `created` DESC means the first row past `since` is where
        every later page would only get older, so the scan stops there rather than reading the
        actor's entire history to answer a bounded report window (mirrors `slots_between`'s own
        "one batched read, not an unbounded scan" discipline).
        """
        where: dict[str, Any] = {"tenant": tenant, "created_by": created_by}
        if branch_id:
            where["branch_id"] = branch_id
        out: list[Booking] = []
        after: str | None = None
        pages = 0
        while pages < 20:  # 20 * 500 = 10,000 rows per actor per report call — a real ceiling
            pages += 1
            rows, after = await self._s.find(self.collection, where, limit=500, after=after,
                                             sort=("created", "desc"))
            stop = False
            hit_limit = False
            for row in rows:
                created = int(row.get("created") or 0)
                if until is not None and created > until:
                    continue
                if since is not None and created < since:
                    stop = True
                    break
                out.append(_from_row(row))
                if len(out) >= limit:
                    stop = hit_limit = True
                    break
            if stop:
                return out, hit_limit
            if not after or not rows:
                return out, False
        return out, True

    async def save(self, b: Booking) -> Booking:
        # A RESCHEDULE MOVES THE BUCKET. `starts_at` is mutable (it IS the reschedule act), and
        # `branch_id` is fixed but read here for symmetry — either changing means the OLD slot key
        # is now for a bucket this booking no longer occupies. Left behind, it is a phantom entry
        # the grid would still show on the day the booking used to be on (§4, "a value computed
        # and dropped" wearing a different hat: the old index row is the value nobody dropped).
        previous = await self.get(b.tenant, b.id)
        new_bucket = day_bucket(b.starts_at)
        if previous is not None:
            old_bucket = day_bucket(previous.starts_at)
            if old_bucket != new_bucket or previous.branch_id != b.branch_id:
                await self._s.delete(BOOKING_SLOTS,
                                     _slot_key(b.tenant, previous.branch_id, old_bucket, b.id))

        b.rev += 1
        row = b.__dict__.copy()
        row["tenant"] = b.tenant
        await self._s.put(self.collection, _key(b.tenant, b.id), row)
        # Written in the SAME call, unconditionally — a slot row that only sometimes gets written
        # is worse than none, because the grid would silently miss exactly the bookings whose
        # write raced something else. There is one write path (`save`), so this is always in sync.
        slot_row = {"tenant": b.tenant, "branch_id": b.branch_id, "bucket": new_bucket,
                   "booking_id": b.id, "operator_id": b.operator_id, "status": b.status}
        await self._s.put(BOOKING_SLOTS, _slot_key(b.tenant, b.branch_id, new_bucket, b.id),
                          slot_row)
        return b

    async def save_if_unchanged(self, b: Booking, *, expected_rev: int) -> Booking:
        """`save()`, but refuses when the row moved under the caller between its read and this
        write — write-if-not-changed.

        ATOMIC NOW — fixed 2026-09-12, a real gap a QA audit found: the rev check and the write
        used to be two separate awaited steps with nothing between them, the identical
        check-then-act shape every OTHER guard in this codebase was hardened against. Two writers
        racing `save_if_unchanged` on the SAME booking (six call sites in operations.py call it
        directly, with no lock of their own — only three go through `_claim_and_save`'s own
        branch/operator/time-bucket lock, a DIFFERENT key entirely, so it cannot serialise this)
        could both read the same `current.rev`, both pass the check, and the second writer's
        `save()` would silently clobber the first's edit with a stale copy. A short claim-based
        mutex keyed on the booking's own (tenant, id) closes it — a DIFFERENT key namespace than
        `claiming()`'s own bucket lock, so nesting inside `_claim_and_save` never deadlocks.

        Compares `rev`, never `updated` — a wall-clock second is not fine-grained enough to tell
        two genuinely different edits apart, and a guard that cannot tell them apart is a guard
        that is silently absent exactly when it is needed.
        """
        mutex_key = f"{b.tenant}|{b.id}"
        held = False
        for _ in range(_SAVE_LOCK_RETRY_ATTEMPTS):
            held = await self._s.claim(
                _SAVE_LOCKS, mutex_key, {"held": True}, ttl_seconds=_SAVE_LOCK_TTL_SECONDS,
                now=time.time())
            if held:
                break
            await asyncio.sleep(_SAVE_LOCK_RETRY_DELAY_SECONDS)
        if not held:
            # FAIL CLOSED — proceeding unprotected here is exactly the race this mutex exists to
            # close. A busy conflict the caller can retry beats a silent clobber.
            raise ConcurrentEditError(
                "تعذّر الحفظ الآن — الحجز مشغول من عملية أخرى، أعد المحاولة بعد لحظة")
        try:
            current = await self.get(b.tenant, b.id)
            if current is not None and current.rev != expected_rev:
                raise ConcurrentEditError(
                    "تعذّر الحفظ — عُدِّل هذا الحجز للتو من مكانٍ آخر. أعد تحميل الحجز وحاول مجدداً")
            return await self.save(b)
        finally:
            if held:
                await self._s.delete(_SAVE_LOCKS, mutex_key)


def _from_row(row: dict[str, Any]) -> Booking:
    row = dict(row)
    if "service_ids" in row and row["service_ids"] is not None:
        row["service_ids"] = tuple(row["service_ids"])
    row.pop("bucket", None)
    # DROPPED, NOT MIGRATED — `series_id`/`series_seq` were dead fields: written on
    # every row (dataclass defaults, both always None) but read by nothing, ever — `for_series`,
    # the one method that would have used them, had no caller anywhere in this codebase. Every
    # existing row on disk still carries both keys (both None), so they must still be POPPED here
    # even though `Booking` no longer declares them — `Booking(**row)` below would otherwise raise
    # on the very first read of a row written before this change.
    row.pop("series_id", None)
    row.pop("series_seq", None)
    # MIGRATED, NOT DROPPED — `deposit_taken: bool` became `payment_status: str`
    # (§ "بدون عربون بعربون او مدفوع"). Every row already on disk still carries the old key; read
    # it once here rather than requiring a backfill job before this deploy is safe to roll out.
    if "deposit_taken" in row:
        old = row.pop("deposit_taken")
        row.setdefault("payment_status", "deposit" if old else "none")
    return Booking(**row)
