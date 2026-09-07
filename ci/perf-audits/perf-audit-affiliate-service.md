# Perf audit — services/affiliate-service (read-only)

Checked for: per-char loops that should be regex, unpruned directory walks, repeated
file reads, N+1 datastore/HTTP loops, O(n²) collection ops, blocking sync I/O in
async code, full-scan-where-indexed-find-would-do.

## Real findings

### 1. `app/core/payouts.py:301-305` — N+1 datastore `get` where a single batched `find` exists

```python
for cid in request.commission_ids:
    crow = await self._s.get(COMMISSIONS, cid)
    if crow and crow.get("withdrawal_id") == request.id:
        crow["withdrawal_id"] = ""
        await self._s.put(COMMISSIONS, cid, crow)
```
`request.commission_ids` is exactly the affiliate's full set of confirmed, unclaimed
commissions at request time (built the same way in `create()`, line ~208-220 via
`_all_commissions`) — for an active promoter this can be dozens to hundreds of rows.
Each iteration is a separate `get()` round-trip (a full asyncpg query against
`app/adapters/datastore/postgres.py`, or a Redis/HTTP round-trip depending on adapter),
run *sequentially* (awaited one at a time), so N commissions = N sequential DB
round-trips just to release a rejected withdrawal.

The datastore port already supports exactly the batched shape needed:
`find(collection, where)` accepts membership filters — `{field: [v1, v2, ...]}` — which
`postgres.py:163-166` turns into an OR-of-JSONB-containments still served by the GIN
index (see the adapter's own docstring at postgres.py:145-151). This loop could be
`rows, _ = await self._s.find(COMMISSIONS, {"id": request.commission_ids}, limit=len(request.commission_ids))`
followed by a loop of only `put()` calls (unavoidable — no batched write exists), cutting
the read side from N round-trips to 1. For a request with, say, 50 commissions, that's
50 sequential reads collapsed into 1.

### 2. `app/core/escalation.py:57-58` — N+1 datastore `get`, with no dedup for repeat affiliates

```python
for ref in referrals:
    affiliate = await self._affiliate(ref.affiliate_id)
```
`sweep()` (called from a k3s CronJob, see `container.py:345`,
`AFFILIATE_TICKET_ESCALATION_SWEEP_MAX`, default 200 — `escalation.py:35`) pulls up to
`sweep_max` referrals via one `all_ever()` call, then does a *separate* sequential
`self._s.get(AFFILIATES, ...)` per referral. Two things compound here:
- It's a per-item sequential round-trip loop (up to 200 per sweep tick), same class as
  finding #1, and
- affiliate_ids are NOT deduplicated: an affiliate with 5 referred shops causes the exact
  same affiliate row to be fetched 5 separate times in one sweep pass, because nothing
  caches `_affiliate()` results within the sweep.

Fix: dedupe `{ref.affiliate_id for ref in referrals}` and either batch via
`find(AFFILIATES, {"id": list(ids)})` (same membership-filter trick as #1) or at minimum
memoize `_affiliate()` per sweep with a local `dict` cache, so a manager with many
referred shops costs one lookup instead of one-per-referral.

### 3. `app/core/commission.py:235-238` and `:276-289` — N+1 cross-service calls (real, but only partly fixable in this file)

```python
for member_id in member_ids:
    totals = await self.totals_for(member_id)      # 1 local find()
    revenue = await self.revenue_for(member_id)     # -> _net_revenue -> 1+ HTTP calls
```
and inside `_net_revenue`:
```python
for ref in referrals:
    ...
    status, body = self._http.call(f"{self._billing}/internal/billing/invoices?tenant={ref.tenant}...")
```
`team_summary(member_ids)` (used by a manager's team dashboard) does 2 calls per member
sequentially, and `revenue_for`/`platform_revenue` each fan out to one **synchronous-looking
blocking `self._http.call`** per referral/shop with no batching. For a manager with, say,
30 team members each with a few referred shops, `platform_revenue()`/`team_summary()`
can serialize into 60-150+ round trips (local datastore + outbound HTTP to billing-service)
on a single request. This is a real latency multiplier on an admin-facing endpoint.
Flagging as class-4 N+1, but the actual fix is cross-service (billing-service would need
a batched "invoices for these N tenants" endpoint — it doesn't have one today) rather than
something this file alone can resolve; noting it because the shape matches the audited
class exactly and the aggregate latency is real, not because there's a same-file fix
available.

### 4. `app/core/wafa.py:180-183` — same N+1-over-referrals shape as #3

```python
for ref in referrals:
    out = await self._tickets.support_kpis(tenant=ref.tenant, grantee=affiliate_id)
```
One `support_kpis` call per referred shop, sequential. Same reasoning as #3 — real but the
fix is a batched ticket-service endpoint, which doesn't exist; not something to change
inside this file alone.

## Checked and NOT a problem (ruled out explicitly)

- **No `os.walk`/`Path.rglob`/`Path.glob` anywhere in this service** (`ci/`, `app/`,
  `tests/`) — nothing to prune.
- **Only `time.sleep` in the whole service** is `ci/security_gate.py:118`, inside a
  documented exponential-backoff retry against a live security-gate check
  (`1s, 2s — enough for a rate limiter to forget us`) — that's intentional throttling in a
  CI script, not a hot path, and it's not inside an `async def`.
- **Per-character loops found are all on short, boot-time strings, not large text.**
  `app/core/outreach_seed.py:628` (`any("0" <= ch <= "9" for ch in text)`) and the
  `str.translate` calls around it (lines 633, 650) run once at process boot, over ~30
  seed template/citation rows whose `title`/`body` fields are short marketing copy
  (a few hundred characters each) — nowhere near the "137M ord() calls over full file
  text" class of the fixed CI example. Not worth a regex rewrite.
  `app/adapters/telemetry/stdout.py:26` (`"".join(c if c.isalnum() else "_" for c in name)`)
  sanitizes a short telemetry event/metric name, called at most once per event emission —
  negligible.
- **`app/core/lead_sourcing.py:101-104`** (`for c in cities: if not all(k in c for k in (...))`)
  validates a user-submitted city list capped by the API layer to a small number of
  cities per search job — not a large-N loop.
- **No repeated re-reads of the same file path across functions** — this service does not
  do CI-style file-content scanning at all (unlike the platform/root `ci/` scripts); its
  own `ci/check_licenses.py` and `ci/security_gate.py` read license/package metadata via
  `importlib.metadata`, not raw file walks.
- **No O(n²) nested-loop-over-same-list or `list`-used-as-a-hot-path-membership-set**
  patterns found in `app/core/*` — the `in`/`any`/`all` checks found (e.g.
  `app/api/authz.py:25,37`) operate over small, fixed-size capability lists (a handful of
  strings), not production-scale collections.
- **`app/core/payouts.py:226-228`** (`for c in claimable: c.withdrawal_id = ...; await put(...)`)
  is a genuine per-item loop of writes, but there is no batched `put`/`put_many` on the
  `DataStore` port (`app/ports/datastore.py`) to fall back to — every adapter (memory,
  postgres, phone_search_ro) only exposes single-key `put`. Not a same-file fix; noted but
  not counted as an actionable finding since no batched primitive exists to switch to.

## Summary of impact ranking

1. **payouts.py `reject()`** — clearest, cheapest fix: swap an N-round-trip `get` loop for
   one `find(..., {"id": [...]})` call; the batched primitive already exists and is already
   used elsewhere in this codebase in exactly this shape.
2. **escalation.py `sweep()`** — same fix shape (dedupe + batch `get`/`find`), running on a
   periodic CronJob against up to 200 referrals per tick.
3. **commission.py `team_summary`/`_net_revenue`/wafa.py `_aggregate_support_kpis`** — real
   N+1 HTTP fan-out on manager-facing dashboards, but the actual fix requires new batched
   endpoints on billing-service/ticket-service, not a change confined to affiliate-service.
