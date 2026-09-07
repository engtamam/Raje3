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

import uuid
from typing import Any

from app.core.models import BOOKING_SLOTS, BOOKINGS, WORKING_HOURS, Booking
from app.core.riyadh import local


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

    async def for_customer(self, tenant: str, customer_id: str, limit: int = 200) -> list[Booking]:
        rows, _ = await self._find(tenant, {"customer_id": customer_id}, limit=limit)
        return [_from_row(r) for r in rows]

    async def for_subject(self, tenant: str, subject_ref: str, limit: int = 200) -> list[Booking]:
        """SAME QUERY as `for_customer`, keyed by the pseudonym instead of the real id — for a
        caller that only ever holds `subject_ref` (a read-only phone→pseudonym resolution, e.g.)
        and must never be handed — or made to mint — a real `customer_id` just to look up a
        history. `subject_ref` is stamped on every booking once at creation (see `Booking`'s own
        field note), so this is exactly as complete a history as `for_customer` gives, through a
        door that costs the caller nothing to open."""
        rows, _ = await self._find(tenant, {"subject_ref": subject_ref}, limit=limit)
        return [_from_row(r) for r in rows]

    async def for_series(self, tenant: str, series_id: str, limit: int = 50) -> list[Booking]:
        rows, _ = await self._find(tenant, {"series_id": series_id}, limit=limit)
        return sorted([_from_row(r) for r in rows], key=lambda b: b.series_seq or 0)

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
        """
        rows, _ = await self._s.find(
            BOOKING_SLOTS, {"tenant": tenant, "branch_id": branch_id}, limit=limit,
            sort=("bucket", "asc"))
        wanted = [r for r in rows if start_bucket <= str(r.get("bucket") or "") <= end_bucket]
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
        write — write-if-not-changed, not a real lock: cheap, and correct for the case it exists
        for (a moderate-frequency two-tab edit of one booking), not for a hot contested path
        (that is what `lock.py`'s claim lane is for).

        Compares `rev`, never `updated` — a wall-clock second is not fine-grained enough to tell
        two genuinely different edits apart, and a guard that cannot tell them apart is a guard
        that is silently absent exactly when it is needed.
        """
        current = await self.get(b.tenant, b.id)
        if current is not None and current.rev != expected_rev:
            raise ConcurrentEditError(
                "تعذّر الحفظ — عُدِّل هذا الحجز للتو من مكانٍ آخر. أعد تحميل الحجز وحاول مجدداً")
        return await self.save(b)


def _from_row(row: dict[str, Any]) -> Booking:
    row = dict(row)
    if "service_ids" in row and row["service_ids"] is not None:
        row["service_ids"] = tuple(row["service_ids"])
    row.pop("bucket", None)
    # MIGRATED, NOT DROPPED (2026-08-19) — `deposit_taken: bool` became `payment_status: str`
    # (§ "بدون عربون بعربون او مدفوع"). Every row already on disk still carries the old key; read
    # it once here rather than requiring a backfill job before this deploy is safe to roll out.
    if "deposit_taken" in row:
        old = row.pop("deposit_taken")
        row.setdefault("payment_status", "deposit" if old else "none")
    return Booking(**row)
