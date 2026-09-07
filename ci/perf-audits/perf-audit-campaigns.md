# Performance audit — services/campaigns/ (read-only)

## Finding 1 (real, high impact): every peer HTTP call is synchronous urllib inside `async def`, never offloaded to a thread

**File:** `services/campaigns/app/adapters/internal_http.py:51-73` (`send`, `read`, `get_json`, `post_json`)
all call `urllib.request.urlopen(...)` directly — a blocking socket call.

**Every caller of it is `async def` and awaits nothing while it runs:**
- `app/adapters/peers/__init__.py:97` — `HttpTemplates._raw` (called by `pick`/`enabled_types`/`blocked_reasons`, i.e. every `/campaigns/goals` and `/campaigns/preview` request)
- `app/adapters/peers/__init__.py:177,189` — ceiling/reserve reads used by `_todays_share` on every preview and every manual-campaign fire
- `app/adapters/peers/__init__.py:237,250,276,311,352,403` — `HttpAudience` (customers, learned rhythms, eligibility gate, redeemed, package-offerable) — called on every audience resolution, i.e. every preview, every campaign create, every dispatcher pass, every tick evaluation
- `app/adapters/peers/__init__.py:436` — another `_get`
- `app/core/licence.py:96` (`HttpLicence.allowed`) — called once per tenant on every `/campaigns` create and every `tick.run` pass
- `app/adapters/consent_gate/http.py:40` and `app/adapters/audit_sink/http.py:42` — same `internal_http.send` pattern

**Why this is a real bottleneck, not speculative:** the codebase's own comment in
`app/adapters/token_verifier/jwks.py:23-31` already documents this exact defect for the JWT
verifier and calls it out as a production incident: *"`verify()` below runs SYNCHRONOUSLY inside
an `async def` route (never wrapped in run_in_executor/asyncio.to_thread), so it blocks this pod's
ENTIRE single-worker event loop for as long as the fetch takes — including its own /healthz and
/readyz probes. Found live: a single slow JWKS fetch left a pod's health checks timing out."*

That documented incident is the JWKS case specifically, but the *identical* pattern (sync
`urlopen` called straight from `async def`, no `to_thread`) is used for every other peer call in
this service — templates, audience/customers, licence, ceiling/reserve, redeemed, consent gate,
audit sink. Each of these is on a hot path: a single `/campaigns/preview` request can make 3-5 of
these blocking calls in sequence (`templates.pick`, `audience.resolve_for` → customers + rhythms +
eligibility, `ceiling.read`, `engine_load`/reserve), and `dispatcher.fire`/`tick.run` make more per
pass. Under this service's single-worker event loop, each blocking call freezes every other
in-flight request (including `/healthz`/`/readyz`) for the full round-trip time to the peer —
turning what should be concurrent I/O-bound work into serialized request handling. A slow peer
(reminders, operations, billing) degrading by even a couple hundred ms turns into the whole pod
looking unresponsive, exactly as already observed for the JWKS case.

**Contrast:** `app/adapters/object_store/local.py:32,37,44,50,53` gets this right — every blocking
filesystem call there is wrapped in `asyncio.to_thread(...)`. The peer HTTP layer never received
the same treatment.

**Fix:** wrap the calls in `internal_http.py` (`send`/`read`, or each `get_json`/`post_json`) in
`asyncio.to_thread(...)`, the same way `object_store/local.py` already does for file I/O — or
switch to an async HTTP client. This is a one-file, low-risk change since every caller already
goes through `internal_http.get_json`/`post_json`.

## Checked, not a real problem

- **`ci/security_gate.py`, `ci/check_licenses.py`** — no directory walking, no per-character loops;
  `check_licenses.py:70` (`for c in md.get_all("Classifier", [])`) iterates over a handful of
  metadata classifier strings per installed package, not file content — not the same class of
  defect as the fixed `check_deploy_wiring.py` issue.
- **`app/core/audience.py:resolve`** — single pass over the customer rows the peer handed back,
  bounded by `max_audience` (default 5000) and by the source page size; no nested loop over the
  same collection.
- **`app/core/dispatch.py:_already_reached`** — now correctly uses `drain()` (cursor-paged,
  budget-bounded) rather than a single truncated `find(limit=10000)` — the docstring records that
  the truncated version was exactly the "N+1 disguised as an off-by-one" bug this audit looks for,
  already fixed.
- **`app/core/backup.py`, `app/core/erasure.py`** — both page through `find()`/`scan_all()` with
  explicit cursors and bounded budgets; no repeated whole-collection scans.
- **`app/adapters/datastore/postgres.py`** — `find()` builds one indexed, cursor-paged query
  (GIN + btree, verified against a mismatched-index case in the file's own comment); `scan_all` is
  key-ordered and resumable. No N+1 or table-scan pattern.
- **`app/adapters/datastore/memory.py`** — in-memory dict scan per `find()`/`scan_all()` call is
  appropriate for a test/dev backend of bounded size; not a production hot path.
- **`app/api/v1/campaigns.py:list_goals` (lines 122-126)** — loops over `GOAL_TEMPLATE.values()`
  (9 goals) calling `c.templates.pick()` per goal. This *looks* like an N+1 at first glance, but
  `HttpTemplates._raw()` (`app/adapters/peers/__init__.py:80-99`) caches the whole per-tenant
  answer for `ttl_seconds` (default 300s) keyed by tenant, so after the first `pick()` in the loop
  all subsequent calls in the same request (and across requests within the TTL) are cache hits —
  no repeated network call. (The *first* call is still the blocking-urllib problem in Finding 1,
  not a distinct N+1.)
- **`app/core/report.py`, `app/core/goals.py`, `app/core/spread.py`, `app/core/preview.py`** — all
  operate on already-bounded, small, in-memory collections (a page of runs ≤200, an audience
  capped at `max_audience`, 9 goal cards). No quadratic behavior on inputs that can grow large in
  production.
- **`app/security/checks.py:115`** — `{c.name: c for c in checks}` builds a dict from a small,
  fixed, in-process list of security checks (not per-request, not large).

## Summary

One real, high-impact finding: the peer HTTP layer (`app/adapters/internal_http.py`) makes fully
synchronous `urllib` calls from `async def` functions with no thread offload, on every route that
talks to reminders/operations/billing (previews, campaign creation, dispatch, the tick). The
service's own code already documents this exact pattern as a production incident for the JWKS
verifier but never applied the fix elsewhere. Everything else audited (audience resolution,
dispatch's dedup ledger, backup/erasure paging, the Postgres/memory datastore adapters, the CI
license/security gates) is already careful about pagination, indexing, and bounded collections —
no per-character loops, no unpruned directory walks, no quadratic list scans found.
