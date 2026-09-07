# Perf audit — services/operations (audit-only, no edits made)

Scope covered: app/core/, app/api/ (hot paths, priority), plus ci/check_licenses.py and
ci/security_gate.py (service-local CI scripts). platform/ and repo-root ci/ were out of scope
and not touched.

## Finding 1 (real, moderate impact): N+1 datastore reads in `TillHealth.for_tenants`

**File:** `services/operations/app/core/till_health.py:66-72`

```python
out: list[dict[str, Any]] = []
for tenant in tenants:
    row = await self._s.get(TILL_HEALTH, tenant)
    ...
```

Called from `services/operations/app/api/v1/platform.py:354` — the platform admin panel that
lists till-health for a set of tenants. This issues one datastore round-trip **per tenant**
instead of a single batched read. The store's own `DataStore.find()` port
(`services/operations/app/ports/datastore.py:44-66`) explicitly supports membership queries —
`where={"tenant": [t1, t2, ...]}` — which is the exact shape already used elsewhere in this
codebase (e.g. `core/connect.py:300` and `:360` use `find(..., {"state": state})`). For a
platform panel listing health across N tenants (hundreds in production, per the codebase's own
"fleet in the hundreds" comment in `core/connect.py:347`), this is N sequential awaited round
trips to Postgres where one `find(TILL_HEALTH, {"tenant": tenants})` would do — the same
N+1-vs-batched-`find` pattern the task description calls out. On Postgres each `get` is a
separate round-trip (network latency, not just CPU), so with hundreds of tenants this is
hundreds of sequential awaits instead of one query — the difference is dominated by network
RTT× N rather than CPU, but the fix is a straight swap to the existing `find()` with a `tenant`
membership list, then re-indexing the results by tenant in memory (O(n), same as the current
loop's bookkeeping).

**Fix:** replace the per-tenant loop with one `find(TILL_HEALTH, {"tenant": tenants}, limit=len(tenants) or more)`
call, build a `{tenant: row}` dict from the result, then iterate `tenants` in memory to build
`out` (preserving the "absent row → never sent" logic, which stays because `find` will simply
omit tenants with no row).

## Finding 2 (real, lower priority — batch/cron path, not per-request): nested N+1 in the monthly commission run

**File:** `services/operations/app/core/statements_run.py:68-76`

```python
for partner in await reg.list():
    ...
    stamps = [st for st in await reg.stamps_of(pid)
              if not await _is_sandbox(store, st.get("tenant", ""))]
```

`_is_sandbox` (`services/operations/app/core/integration.py:59-72`) does one
`await store.get(STANDING, tenant)` per call. So for every partner, for every shop ("stamp")
attributed to that partner, this does one more sequential awaited datastore read — a genuine
N×M pattern (partners × shops-per-partner) inside a monthly statements-issuing job. Unlike
Finding 1 this is not a per-request hot path (it's a scheduled/admin-triggered run), so the
user-facing latency cost is lower, but it will scale linearly-times-linearly with partner/shop
growth and each unit is a full network round trip, not just CPU. Given `is_sandbox` reads are
keyed by tenant, this could be resolved the same way as Finding 1: collect the distinct tenants
across all partners' stamps up front, do one `find(STANDING, {"tenant": [...]})` (or reuse
`scan_all` since STANDING is presumably small), and look sandbox status up from an in-memory
dict inside the loop instead of awaiting per stamp.

## Checked and NOT a real bottleneck (documented so it isn't re-flagged)

- `services/operations/app/core/connect.py:364` (`if tenant and tenant not in out:` inside a
  loop, `out` being a plain list) — worst case is 2 states × up to 2000 rows = at most ~4000
  membership checks against a list that grows to at most 2000 entries, i.e. low millions of
  simple string comparisons on a sweep that runs hourly, not per-request. Real inefficiency in
  principle (should be a set-lookup with an ordered list built after), but at this bound it's not
  a measurable win — not reported as a primary finding.
- `services/operations/app/api/v1/till.py:259` and `:270` (`set(unstable)` re-built inside a
  list-comprehension filter, evaluated once per outer iteration → O(n²) construction) — looks
  like the same class of defect as the ord()-loop example, but `TillBatchIn.visits` is capped at
  `max_length=50` (`app/api/v1/till.py:105`, mirrored in `app/api/internal.py:156`), so n² tops
  out at 2,500 — not measurable. Not reported as a primary finding.
- `services/operations/app/api/v1/staff.py:1300-1358` (bulk service CSV import: `by_external_id`
  / `by_name` dicts + `touched_ids` set) — already correctly implemented with O(1) dict/set
  lookups, not an O(n²) loop as the surrounding code's shape first suggested. No issue.
- `services/operations/app/core/retention.py:290-329` (customer-erasure sweep) — uses
  `scan_all` once with a cap, groups rows into a `dict[tenant, list]` in one pass, then iterates
  per tenant. Correctly avoids repeated scans; not an issue.
- Per-character loops found (`core/operations.py:684`, `core/plate.py:48/51`,
  `core/operator_ticket.py:61`, `adapters/telemetry/stdout.py:26`) all operate on short strings
  (phone numbers, plate text, metric names — tens of characters, not file-sized text), so unlike
  the `ci/check_deploy_wiring.py` example (137M ord() calls over full file contents) these are
  not a real cost. Not reported as findings.
- No `os.walk`/`rglob`/`Path.glob` directory walks exist under `services/operations/app/` or
  `services/operations/ci/` at all — the directory-walk defect class from the example does not
  apply to this service's own code.
- `services/operations/ci/check_licenses.py` and `ci/security_gate.py` — operate over installed
  package metadata (hundreds of distributions) and shell out to external scanners; no
  per-character or unpruned-tree scanning present.

## Summary

Two genuine N+1 datastore-call patterns found, both matching the task's pattern #4 (a loop doing
one datastore call per item where the store's own `find(..., where={field: [values]})` shape —
already used elsewhere in this codebase — would do it in one call): `TillHealth.for_tenants`
(admin panel, moderate priority — runs on every panel refresh across potentially hundreds of
tenants) and the commission `statements_run` sandbox check (monthly batch job, lower priority).
Everything else that pattern-matched the described defect classes (list-membership-in-a-loop,
O(n²) set rebuilding, per-character string loops, CSV bulk-import) was checked and found to be
either already correctly implemented or bounded too tightly (by request size caps or small
fixed collections) to be a measurable bottleneck.
