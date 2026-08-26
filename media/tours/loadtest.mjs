/**
 * Progressive load test against the live cluster — finds the real concurrency ceiling by
 * stepping concurrency up with NO fixed cap, until the server visibly can't keep up (error rate
 * > 10%), not until an arbitrary number.
 *
 * WHY THESE SPECIFIC ENDPOINTS. Same mix محلّي itself fires on open (confirmed live this session
 * via network tracing) — the busiest real read path a signed-in owner actually exercises, not a
 * synthetic ping. Hitting only `/healthz` would prove nothing about real capacity.
 *
 * WHY THIS DOES NOT PROVISION ITS OWN TENANTS. It used to, inline, per level — until a live run
 * showed self-inflicted failures: provisioning is a multi-step write transaction (tenant create
 * -> identity seed-owner -> roles bootstrap), and running it WHILE this script's own concurrent
 * READ burst was hammering the same shared services made that transaction genuinely fail
 * mid-chain (confirmed via services/operations/app/core/signup.py's _bootstrap_roles failure
 * path, not a rate limit). Provisioning and load generation are now two fully separate phases —
 * run provision-load-test-tenants.mjs to completion FIRST, then this.
 *
 * WHY EVERY LEVEL GETS BRAND-NEW TENANTS, NEVER REUSED. An earlier version reused a growing
 * prefix of the pool across levels — level 10 and level 40 shared the same first ten, so their
 * per-subject rate budget accumulated real usage across the ramp and produced a 429 "ceiling"
 * that was really just tenant reuse, not a server limit (confirmed live: the same burst run in
 * isolation against untouched tenants passed at 0% errors). Every level here draws a disjoint
 * window from the pool, so a ceiling found here is a property of the SERVER at that concurrency.
 *
 * WHY BASE IS OVERRIDABLE. Run through the local dev tunnel (Vite -> SSH -> cluster) and a
 * "ceiling" can be the tunnel's own concurrency limit, not the server's — confirmed live: a
 * burst that showed 82.9% "500"s here left barely any trace in api-gateway's own access log (160
 * requests logged out of 770 sent), meaning most never reached the cluster at all. LOADTEST_BASE
 * lets this same script run from INSIDE the cluster instead (BASE=http://api-gateway:8000, no
 * tunnel, no local proxy in the path) so a ceiling found there is the server's, not the harness's.
 *
 * WHY EVERY USER SIGNS IN FRESH RIGHT BEFORE ITS BURST. Access tokens expire in 15 minutes
 * (exp - iat = 900s). A pool file that stores a token minted at PROVISION time goes stale the
 * moment total provisioning time exceeds that window — confirmed live: a 800-tenant pool ran
 * long enough that the first tenants' saved tokens were already ~8 minutes expired by the time
 * this script started, producing 100% 401 at the very first level. provision-load-test-tenants.mjs
 * saves {tenant, phone, password} instead of a token for exactly this reason — this script signs
 * in for real, once per user, immediately before that user's own burst, so token age is always
 * seconds, never however long the whole pool took to provision.
 *
 * Usage:
 *   node provision-load-test-tenants.mjs 250   # once, first — needs enough for every level below
 *   node loadtest.mjs
 *   LOADTEST_BASE=http://api-gateway:8000 node loadtest.mjs   # in-cluster, no tunnel
 */
import { readFileSync, writeFileSync } from 'node:fs';

const BASE = process.env.LOADTEST_BASE || 'http://localhost:5174';

const tenants = JSON.parse(readFileSync(new URL('.loadtest-tenants.json', import.meta.url), 'utf8'));
if (tenants.length === 0) throw new Error('no tenants — run provision-load-test-tenants.mjs first');

const ENDPOINTS = [
  '/api/v1/app/catalog',
  '/api/v1/reminders/today',
  '/api/v1/insights/dashboard',
  '/api/v1/whatsapp/connect',
  '/api/v1/insights/branches',
  '/api/v1/subscription/apps',
  '/api/v1/staff/branches',
];

async function signInFresh(phone, password) {
  const si = await fetch(`${BASE}/api/v1/signup/signin`, {
    method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ phone, password, code: '' }),
  });
  if (!si.ok) return null;
  const j = await si.json();
  return j.access_token || null;
}

async function oneUser(t) {
  const token = await signInFresh(t.phone, t.password);
  if (!token) return [{ path: '(signin)', status: 0, ms: 0, ok: false, err: 'fresh signin failed' }];
  const results = [];
  for (const path of ENDPOINTS) {
    const t0 = Date.now();
    try {
      const res = await fetch(BASE + path, { headers: { authorization: `Bearer ${token}` } });
      results.push({ path, status: res.status, ms: Date.now() - t0, ok: res.ok });
    } catch (e) {
      results.push({ path, status: 0, ms: Date.now() - t0, ok: false, err: e.message });
    }
  }
  return results;
}

let cursor = 0;
function nextWindow(concurrency) {
  if (cursor + concurrency > tenants.length) {
    throw new Error(`need ${cursor + concurrency} distinct tenants total, only have ${tenants.length} — run provision-load-test-tenants.mjs with a higher count`);
  }
  const window = tenants.slice(cursor, cursor + concurrency);
  cursor += concurrency;
  return window;
}

async function runLevel(concurrency) {
  const t0 = Date.now();
  const all = await Promise.all(nextWindow(concurrency).map((t) => oneUser(t)));
  const flat = all.flat();
  const wall = Date.now() - t0;
  const okCount = flat.filter((r) => r.ok).length;
  const errCount = flat.length - okCount;
  const times = flat.map((r) => r.ms).sort((a, b) => a - b);
  const p50 = times[Math.floor(times.length * 0.5)];
  const p95 = times[Math.floor(times.length * 0.95)];
  const max = times[times.length - 1];
  const errorsByStatus = {};
  for (const r of flat) if (!r.ok) errorsByStatus[r.status || 'network'] = (errorsByStatus[r.status || 'network'] || 0) + 1;
  return { concurrency, wallMs: wall, total: flat.length, ok: okCount, err: errCount, errorRate: flat.length ? errCount / flat.length : 0, p50, p95, max, errorsByStatus };
}

const log = (msg) => { console.log(msg); };

// Unbounded escalation — each round ~1.5x the last, no fixed cap. A hard backstop exists only to
// stop a runaway loop if the pool or the server never gives out; it is not the intended stop.
let concurrency = 10;
const runs = [];

log(`Load test starting against ${BASE} — ${ENDPOINTS.length} real endpoints × N concurrent simulated users, escalating with no cap until the real ceiling. Pool: ${tenants.length} pre-provisioned tenants.`);
log('concurrency | wall_ms | ok/total | error_rate | p50_ms | p95_ms | max_ms | errors_by_status');

while (cursor + concurrency <= tenants.length) {
  const r = await runLevel(concurrency);
  runs.push(r);
  log(`${String(r.concurrency).padStart(11)} | ${String(r.wallMs).padStart(7)} | ${r.ok}/${r.total}`.padEnd(0) +
      ` | ${(r.errorRate * 100).toFixed(1)}%`.padStart(11) +
      ` | ${String(r.p50).padStart(6)} | ${String(r.p95).padStart(6)} | ${String(r.max).padStart(6)} | ${JSON.stringify(r.errorsByStatus)}`);
  if (r.errorRate > 0.1) {
    log(`\n⚠ error rate exceeded 10% at concurrency=${r.concurrency} — this is the practical ceiling. Stopping.`);
    break;
  }
  // Cool-down between levels so one level's burst doesn't bleed into the next's measurement.
  await new Promise((res) => setTimeout(res, 3000));
  concurrency = Math.ceil(concurrency * 1.5);
}
if (cursor + concurrency > tenants.length && runs.length && runs[runs.length - 1].errorRate <= 0.1) {
  log(`\nRan out of pool (${tenants.length} tenants) before finding a ceiling — no error above 10% yet. Provision more to push further.`);
}

writeFileSync(new URL('.loadtest-result.json', import.meta.url), JSON.stringify(runs, null, 2));
log('\nDone. Cross-check `sudo k3s kubectl -n base-services get pods` for any RESTARTS that climbed during this run.');
