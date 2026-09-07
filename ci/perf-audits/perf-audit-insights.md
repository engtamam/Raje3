# Perf audit — services/insights/ (read-only)

Scope: services/insights/app, services/insights/tests, services/insights/ci.
Looked specifically for the CI-gate class of bug (per-char Python loop instead of a compiled
regex; unpruned `rglob`/`os.walk` walking node_modules/.venv/platform; repeated file reads;
N+1 datastore/HTTP calls where a batch/find already exists; O(n²) algorithms on
production-sized collections; blocking I/O inside async code; full-scan where an indexed
`find(...)` would do).

## Bugs of that class: none found

- `services/insights/ci/security_gate.py` and `ci/check_licenses.py` are the only two CI
  scripts specific to this service. Neither walks a directory tree (`check_licenses.py` reads
  installed package metadata via `importlib.metadata.distributions()`, not the filesystem tree)
  and neither has a per-character loop — `security_gate.py`'s only regex-adjacent work is a JSON
  parse of scanner output. `time.sleep(2 ** attempt)` in `gate_cve()` (security_gate.py:118) is
  inside a synchronous CI retry loop calling `subprocess.run`, not async code, so it is not the
  "blocking I/O inside an async function" defect.
- No `rglob`, `os.walk`, or `Path.glob` calls anywhere under `app/`, `tests/`, or `ci/` in this
  service.
- `app/ports/datastore.py` exposes `get`/`put`/`find`/`scan_all` but no batch-get; every
  per-tenant loop that calls `store.get`/`store.put` once per item (`app/core/rollup.py:37-40`,
  `app/core/tick.py:389-390`, `app/core/tick.py:361-362`) is doing so because that IS the
  existing repository shape here — there is no `find`/list-by-keys method being bypassed. Not
  the "an existing batched call would do the same job" pattern; it's the intended shape of a
  bounded, resumable per-tenant sweep (see the module's own docstrings on why it's O(tenants),
  not O(tenants²)).

## Two small, real, non-urgent findings (not the same magnitude as the CI-gate bug)

1. **`app/core/indicators.py:502-547` (`retention_series`) redundantly rebuilds the per-customer
   index twice per point.** For each of the 6 trailing windows it calls
   `people = len(_by_customer(slice_))` (line 541) and then `return_rate(slice_)`
   (line 546), and `return_rate` (line 41) itself calls `per = _by_customer(visits)` again on
   the same `slice_`. `_by_customer` (lines 24-32) is O(n) but does a dict build *and* a
   per-customer `sort()` — so this is 12 builds-and-sorts of overlapping windows instead of 6.
   Real but small: `visits` here is capped at `visit_limit` (default 5000, see
   `app/core/tick.py:45`), so worst case this is roughly 2x work on an already-bounded list, not
   an unbounded blowup. Fix, if worth it: compute `_by_customer(slice_)` once per point and pass
   the customer map into an inlined return-rate calc instead of re-deriving it inside
   `return_rate`.

2. **`app/core/associations.py:249-274` (`missed_opportunities`) is a nested loop over every
   customer sequence × every actionable pair** (`for ref, services in sequences.items(): for p
   in actionable:`). This is architecturally O(customers × pairs), not O(n²) on the same list —
   `sequences` can be a shop's whole customer base (thousands) but `actionable` is bounded by
   the association engine's own catalogue-sized pair count (tens, since a shop's catalogue is
   "ten to forty services" per the module's own docstring, line 67), so in practice this is
   O(customers × small-constant), not quadratic in anything large. The function already caps
   output at `limit=500` but does NOT break out of the outer customer loop early — the `if
   len(out) >= limit: break` (line 272-273) only breaks the customer loop after a customer has
   been fully scanned, not the pair loop, so it's a minor, not a slam-dunk, inefficiency. Not
   flagging as a real bottleneck; noting only because it's the one genuine nested-loop-over-two-
   collections in this service's core logic.

## Checked and NOT a bottleneck (ruled out explicitly)

- `app/core/dispute_report.py::_fetch_legal` (lines 272-291) makes one HTTP call per legal
  document (`hist_out = peers.get(...)` inside a `for doc in docs_out...` loop) — a real N+1,
  but there is no batch "history for N doc_ids" endpoint on compliance-service to call instead,
  and this only runs on an admin-triggered, low-frequency dispute report (not a request-path
  hot loop), with a handful of legal documents per tenant. Not the same class as an unindexed
  full-table scan on a hot path — ruled out.
- `app/core/tick.py::_coverage` (lines 393-408) does 4 separate `sum(1 for v in visits ...)`
  passes over the same `visits` list. Each is O(n) so the total is still O(n), just a constant
  factor of 4 instead of 1, on a list already capped at 5000. Not worth flagging as a real
  bottleneck.
- `app/security/checks.py::NoSecretLeakCheck._scan` (lines 86-99) recursively walks a response
  dict/list — bounded by response payload size (small dashboard/API responses), not a large
  production collection. Not a bottleneck.
- `app/core/associations.py::count_pairs` uses `itertools.combinations(items, 2)` per basket —
  O(items²) per basket, but a basket/receipt is 2-3 services in this domain (per the module's
  own docstring: "a basket here is two or three"), so this is O(1) per basket in practice.
- No repeated re-reads of the same file path across functions found in this service (nothing
  resembling the config-re-parsed-per-check pattern).

## Conclusion

This service's own code (app/, tests/, ci/) does not have anything resembling the
`ci/check_deploy_wiring.py` per-character-loop-over-137M-chars bug, nor an unpruned
`rglob`/`os.walk` walking `node_modules`/`.venv`/`platform`. The two items under "small, real
findings" are legitimate but minor (constant-factor redundancy on already-bounded lists), and
everything else checked and ruled out above is genuinely fine at production scale for this
service's domain (a shop's own visits/customers/catalogue, not a platform-wide unbounded
collection).
