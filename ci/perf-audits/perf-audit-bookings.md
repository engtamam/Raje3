# Performance audit — services/bookings/ (read-only)

## Finding 1 (real, moderate-high impact): N+1 datastore reads in `BookingStore.slots_between`

File: `services/bookings/app/core/stores.py:117-135`

```python
async def slots_between(self, tenant, branch_id, *, start_bucket, end_bucket, limit=500):
    rows, _ = await self._s.find(
        BOOKING_SLOTS, {"tenant": tenant, "branch_id": branch_id}, limit=limit,
        sort=("bucket", "asc"))
    wanted = [r for r in rows if start_bucket <= str(r.get("bucket") or "") <= end_bucket]
    out: list[Booking] = []
    for row in wanted:
        b = await self.get(tenant, str(row.get("booking_id") or ""))   # <-- one datastore round trip PER row
        if b is not None:
            out.append(b)
    return out
```

`find()` fetches the index rows in one query, but hydrating each into a real `Booking` is done with a separate `await self.get(...)` per row, sequentially, inside the loop. Against `PostgresDataStore.get()` (`app/adapters/datastore/postgres.py:110-117`), each of those calls does `pool.acquire()` + a full round trip (`SELECT value FROM kv_store WHERE collection=$1 AND key=$2`). For a busy branch this is not a rare edge case — it's on the hot path twice:

- `BookingOperations._refuse_if_conflicting` (`app/core/operations.py:750-756`) calls it on **every single booking write** (create/reschedule), scoped to one day bucket — usually cheap (a handful of bookings/day/branch), but still N+1 shaped.
- `BookingOperations.nearest_slot` (`app/core/operations.py:684-685`) calls it with `limit=500` over up to a 14-day search window — a busy branch/operator combo can plausibly have hundreds of slot-index rows in that window, meaning **up to 500 sequential awaited Postgres round trips** (each with its own pool-acquire) to answer one "أقرب موعد" click. At even 1-2ms/round-trip under load (or more if the pool is near its `pool_max=5` ceiling and calls queue for a connection), that is worst-case several hundred ms to a couple seconds serialized, vs. a single batched query.

**Fix**: add a batched multi-get to the datastore port (e.g. `get_many(collection, keys: list[str]) -> dict[key, value]`), implemented in Postgres as one `SELECT value FROM kv_store WHERE collection=$1 AND key = ANY($2)` and in the memory adapter as a plain dict lookup loop (no I/O cost there anyway). `slots_between` would then build the list of `_key(tenant, booking_id)` keys once and issue one query instead of `len(wanted)` queries. This is the same class of defect as the audit's own example: doing per-item work in Python/serial I/O when a single set-oriented call does the same job in one round trip.

Note: `counts_between` (`stores.py:137-162`) deliberately avoids this exact trap already — its own docstring calls out that `slots_between` hydrates a full `Booking` per row and is "wasteful for a whole year", which is why the counts path reads the index only. That confirms the N+1 in `slots_between` is a known, accepted-for-now cost for short ranges (1 day / a couple weeks) — but at `limit=500` in `nearest_slot` it is large enough to be a genuine, fixable bottleneck, not a false positive.

## Checked and NOT a problem (ruled out explicitly)

- **`ci/check_licenses.py`, `ci/security_gate.py`** — small, bounded collections (installed distributions, a handful of gate results); regex/list-comprehension usage here is over tens of strings, not millions of characters. No per-character loop over file text anywhere in this service's CI scripts. No directory walk at all (`rglob`/`os.walk`/`Path.glob`) in this service's own code or CI — nothing to prune.
- **`app/core/erasure.py` `_page()`** — pages through `find()` with a bounded `_max` (100,000) and an explicit `after` cursor; does not re-scan, does not do N+1 (batch `find` per page, not per row). This is exactly the pattern the audit was looking for and it's already correct here.
- **`app/core/stores.py` `counts_between`** — pages the index correctly (`after` cursor, `find()` per page) and deliberately reads ONLY the index (`bucket` field), avoiding the exact per-row hydration `slots_between` does. No fix needed.
- **`app/core/availability.py` `free_slots`** — nested loop (days × windows × grid steps × busy intervals) is pure in-memory over caller-bounded inputs (`search_days` default 14, `busy` bounded by `slots_between`'s own `limit=500`). Not O(n²) on an unbounded production collection; profiled by inspection as bounded and cheap.
- **`app/api/authz.py` `require_capability`/`require_any_capability`** — `any(c in held for c in caps)` where `held` is a `frozenset[str]` (see `effective_caps` → `principal.caps: frozenset[str]`), so each `in` check is O(1); `caps` itself is a handful of literal strings from the route decorator, not a runtime-sized collection. Not a real O(n²).
- **`app/security/cwe_guard.py`, `app/security/checks.py`** — small in-memory dict/list operations over a fixed, small catalog of checks; no scan of anything request-sized.
- No `time.sleep` or other blocking I/O found inside any `async def` in this service (`app/`, `ci/`, `tests/`).

## Bottom line

One real, fixable finding: the N+1 `get()`-per-row hydration in `BookingStore.slots_between` (`app/core/stores.py:117-135`), most impactful through `nearest_slot`'s `limit=500` call site (`app/core/operations.py:684-685`). Everything else checked in this service's own code is either already correctly batched/paged (erasure, counts_between) or too small/bounded to be a real bottleneck.
