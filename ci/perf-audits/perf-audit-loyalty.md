# Performance audit — services/loyalty/

Scope: app/, tests/, ci/ (this service only). Read-only, no edits made.

## Summary

Nothing at the scale of the ci/check_deploy_wiring.py example (no per-character regex-shaped
Python loop over full file text; no unpruned Path.rglob/os.walk over the tree; no CI script here
touches the filesystem tree at all — ci/check_licenses.py and ci/security_gate.py both operate on
installed package metadata via `importlib.metadata`, and security_gate.py just shells out to
external scanners). The app/ code is consistently built around bounded pagination (`find(...,
limit=...)` with cursors), single natural-key lookups, and a single `Ledger.post()` write path —
this is a codebase that was already tuned for exactly these defect classes (see the extensive
"the sweep used to re-read the same 500 rows forever" commentary in app/core/expiry.py, and the
`drain()`-bounded reconcile in app/core/ledger.py). No FastAPI/backend collection is walked
unbounded anywhere I found.

## Findings (minor — not padding, but neither is a real bottleneck)

### 1. app/core/report.py:24-58 — four separate O(n) passes over the same row list

```python
granted = sum(int(r["delta"]) for r in rows if r.get("reason") == "earn")
consumed = -sum(int(r["delta"]) for r in rows if r.get("reason") == "redeem")
expired = -sum(int(r["delta"]) for r in rows if r.get("reason") == "expire")
adjusted = sum(int(r["delta"]) for r in rows if r.get("reason") == "adjust")
...
"customers": len({r.get("subject_ref") for r in rows}),
```
`rows` can be up to `limit=100000` (the default cap passed into `build()`). This makes 5 full
passes over up to 100k dicts (4 sums + 1 set-comprehension) where a single accumulating loop would
do it in one pass. This is a constant-factor (~5x) inefficiency, not an algorithmic-class defect —
each pass is still O(n), just done 5 times instead of 1. At 100k rows this is on the order of a
few hundred ms of avoidable CPU in the worst case, not the tens-of-seconds-to-minutes class the
per-character regex example was. I would combine into one `for r in rows:` loop with running
totals if this endpoint is called often, but it's a report page, not a hot path, so I'm not
flagging it as urgent — just noting it as the one real constant-factor win in the service.

### 2. app/core/runtime_config.py:185-196 — `effective()` does one store.get() per policy key (N+1 shape, but N is tiny)

```python
for key in sorted(self._policy):
    if not settable(key, self._cls, self._policy):
        continue
    out[key] = await self.get(tenant=tenant, key=key, default=getattr(settings, key, None))
```
This is the textbook N+1 shape (a loop issuing one datastore read per item instead of one batched
read), and `self.get()` itself does up to 2 reads per key (tenant scope then platform scope) — so
worst case 2×|policy| round trips. However `RUNTIME_POLICY` is a small, hand-declared set of
config knobs per service (on the order of single digits to low tens, based on how it's used
elsewhere in this codebase), and `effective()` is only called when rendering the admin runtime-config
screen — not a per-request hot path. I checked this because it matches pattern #4 in the brief, but
at this N and this call frequency it is not a real bottleneck; a batched `find()` would need the
datastore to support multi-key `IN` fetches by key, which this store's `find(where=...)` shape
doesn't naturally offer for a set of unrelated keys anyway. Noting it, not flagging it as urgent.

## Explicitly checked and found clean

- **app/core/expiry.py** — cursor-based sweep, explicitly rewritten (per its own docstring) to stop
  re-reading the same 500 rows forever; single bounded page per call.
- **app/core/erasure.py** — bounded `while True` scan over ENTRIES/REDEMPTIONS with an explicit
  `max_scan` cap (default 100k) and truncation reporting; no unbounded loop.
- **app/core/recovery.py** — bounded `max_batches` loop over paged visit reads.
- **app/core/ledger.py** — single-key lookups (`store.get`) for balance/idempotency; `reconcile()`
  uses the existing `drain()` helper (bounded read) rather than an unbounded scan.
- **app/core/redeem.py** — `_existing()` uses `find(..., limit=1)` on an indexed idem_key lookup,
  not a scan; single `Ledger.post()` write per redemption, no per-item loop against the store.
- **app/core/earn.py / earning.py** — `EarnTree.resolve()`/`points_for()` iterate only over the
  services on one visit (bounded by what a shop's service list actually is, realistically single
  digits), no nested loops against the datastore.
- **app/core/rewards.py** — `list()`/`affordable()` are single `find(limit=500)` calls with
  in-memory filter/sort; no per-reward datastore round trip.
- **app/core/backup.py** — explicitly paginated (`_PAGE = 500`) tenant-scoped reads; whole-collection
  `scan_all` is used only for the deliberate whole-service backup case, which is documented as the
  one place that operation is legitimate.
- **ci/check_licenses.py** — iterates `importlib.metadata.distributions()` (installed packages, not
  files) and does simple substring checks (`"AGPL" in u`) on short classifier strings — not a
  per-character loop over file text, and nowhere near the volume the example's CI gate was scanning.
- **ci/security_gate.py** — orchestrates external scanner subprocesses (bandit, detect-secrets,
  pip-audit, trivy); does not itself walk the file tree.
- No `os.walk`, `Path.rglob`, or `Path.glob` calls found anywhere under services/loyalty/app,
  services/loyalty/tests, or services/loyalty/ci.
- No `time.sleep` inside an `async def` found (the one `time.sleep` in ci/security_gate.py's retry
  backoff is in a synchronous subprocess-orchestration script, not an async request path).

## Conclusion

Nothing significant found at the severity of the example fix. The one real, if minor, win is
report.py's 4-5 redundant passes over up to 100k rows (constant-factor, not algorithmic-class) —
worth collapsing into a single loop if/when this report path gets busy, but not urgent.
