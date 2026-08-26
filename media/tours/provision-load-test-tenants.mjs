/**
 * Creates N genuinely distinct demo tenants (real POST /api/v1/signup + real POST
 * /api/v1/signup/signin, the exact same contract apps/console/src/auth.ts::openShop uses) — one
 * real business/owner subject per entry, not 100 requests from the same identity.
 *
 * RUNS TO COMPLETION BEFORE ANY LOAD TEST STARTS — deliberately. Signup is a multi-step
 * transaction (tenant create -> identity seed-owner -> roles bootstrap, each its own internal
 * HTTP call with its own DB access); running provisioning WHILE the load test's own concurrent
 * read traffic is hammering the same shared services caused real, transient failures in that
 * chain (confirmed live: a fresh single signup attempt got a genuine 400 mid-burst, root-caused
 * to services/operations/app/core/signup.py's _bootstrap_roles failure path, not a rate limit).
 * So provisioning and load generation are two separate phases now, never concurrent with each
 * other's traffic — this script finishes fully before loadtest.mjs fires a single request.
 *
 * RETRIES EACH TENANT UP TO 3x — a transient failure during provisioning (the same shared-service
 * contention above, just from THIS script's own batching) should not shrink the pool; only a
 * consistently-failing signup should.
 *
 * SAVES CREDENTIALS, NOT THE TOKEN — access tokens expire in 15 minutes (exp - iat = 900s,
 * confirmed live), and provisioning a large pool (800 tenants) takes longer than that. A run that
 * provisions-then-tests against saved TOKENS found the earliest ones already expired by the time
 * the test started (100% 401 at the first level) — the tenant minted first is also used first, and
 * by then its token was ~8 minutes past expiry. Saving {tenant, phone, password} instead lets
 * loadtest.mjs sign in FRESH right before each burst, decoupling "how long provisioning took" from
 * "how old the token is" entirely — correct at any pool size or provisioning duration.
 *
 * Writes media/tours/.loadtest-tenants.json — an array of {tenant, phone, password}.
 *
 * Usage: node provision-load-test-tenants.mjs [count]
 *        LOADTEST_BASE=http://api-gateway:8000 node provision-load-test-tenants.mjs 250   # in-cluster
 */
import { writeFileSync } from 'node:fs';

const BASE = process.env.LOADTEST_BASE || 'http://localhost:5174';
const COUNT = Number(process.argv[2] || 100);

function randomPhone() {
  return `05${Math.floor(Math.random() * 90_000_000) + 10_000_000}`;
}

async function attemptOne(i, attempt) {
  const phone = randomPhone();
  const password = 'Kobo2026$Load' + i + '_' + attempt;
  const shop_name = `منشأة اختبار حمل ${i}`;
  const su = await fetch(`${BASE}/api/v1/signup`, {
    method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ phone, password, shop_name, affiliate_ref: '' }),
  });
  if (!su.ok) return { error: `signup ${su.status}` };
  const si = await fetch(`${BASE}/api/v1/signup/signin`, {
    method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ phone, password, code: '' }),
  });
  if (!si.ok) return { error: `signin ${si.status}` };
  const j = await si.json();
  // Signing in here only PROVES the credentials work — the returned token is discarded, not saved
  // (see the module note on why: it would be stale by the time a large pool gets used).
  return { tenant: j.tenant, phone, password };
}

async function makeOne(i) {
  let last = { error: 'unknown' };
  for (let attempt = 0; attempt < 3; attempt++) {
    last = await attemptOne(i, attempt);
    if (last.tenant) return { i, ...last };
    // Short backoff — long enough for a transient contention spike to pass, short enough not to
    // slow the whole pool down by much even with a full 250-tenant run.
    await new Promise((res) => setTimeout(res, 500 * (attempt + 1)));
  }
  return { i, ...last };
}

async function main() {
  console.log(`Provisioning ${COUNT} distinct real tenants against ${BASE} (real signup + signin each, up to 3 attempts)...`);
  const results = [];
  // Batches of 10 concurrent signups — real onboarding side effects (trial activation etc.)
  // fire per signup, so a full-blast N-at-once would itself be an uncontrolled load spike on
  // the very thing we're about to measure.
  const BATCH = 10;
  for (let start = 0; start < COUNT; start += BATCH) {
    const batch = await Promise.all(
      Array.from({ length: Math.min(BATCH, COUNT - start) }, (_, k) => makeOne(start + k)),
    );
    results.push(...batch);
    const ok = batch.filter((r) => r.tenant).length;
    console.log(`  ${start + batch.length}/${COUNT} provisioned (${ok}/${batch.length} this batch ok)`);
  }
  const good = results.filter((r) => r.tenant);
  const bad = results.filter((r) => !r.tenant);
  console.log(`Done: ${good.length} usable, ${bad.length} failed.`);
  if (bad.length) console.log('Failures:', bad.slice(0, 5));
  writeFileSync(
    new URL('.loadtest-tenants.json', import.meta.url),
    JSON.stringify(good.map(({ tenant, phone, password }) => ({ tenant, phone, password })), null, 2),
  );
}

main();
