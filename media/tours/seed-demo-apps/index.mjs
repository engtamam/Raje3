/**
 * ONE demo shop that holds EVERY app this product sells, with fifty customers whose activity is
 * spread across different apps, so every console and mobile screen opens on real, varied data.
 *
 *   node media/tours/seed-demo-apps/index.mjs              # every app, in MODULES order
 *   node media/tours/seed-demo-apps/index.mjs visit loyalty  # only these modules (by file name)
 *   VERIFY_ONLY=1 node media/tours/seed-demo-apps/index.mjs  # re-check, write nothing new (same
 *                                                            # day as the seed — plans are dated
 *                                                            # from "today"; a later re-seed tops up)
 *   CONSOLE=http://localhost:5174 …                          # default; the stack from local_stack.py
 *
 * AGAINST THE LOCAL STACK, three terminals (or background jobs):
 *   python media/tours/seed-demo-apps/local_stack.py up    # Postgres+Redis (Docker) and every service
 *   cd apps/console && npx vite --port 5174                # the console; its proxy targets :8090
 *   node media/tours/seed-demo-apps/index.mjs              # this
 * Then sign in at http://localhost:5174/app/ with `.demo-credentials.apps.json`'s phone/password.
 *
 * Same discipline as seed-demo-account.mjs, whose helpers this reuses (lib/demo-api.mjs): EVERY
 * write is the real HTTP API — never a database row — and a browser only for the signup itself.
 * The session lives in `.demo-session.apps.json` (lib/demo-session.mjs's "apps" profile), separate
 * from the salon tour shop's, and re-running adds to the SAME shop instead of opening another.
 *
 * ── ADDING A NEW APP ─────────────────────────────────────────────────────────────────────────────
 * One new file, one line here. Nothing else is touched — not foundation.mjs, not another module.
 *
 *   1. Create `seed-demo-apps/<app>.mjs` exporting:
 *        export const app = 'feature.<key>';       // its key in services/operations/app/core/apps.py
 *        export async function seed(ctx) { … }     // writes, through the real API; returns a summary
 *        export async function verify(ctx) { … }   // reads it back; throws if anything is off
 *      where `ctx` is { api, session, customers, shop, rng, log }:
 *        api        lib/demo-api.mjs's makeApi(): api.act('<catalog action id>'), api.call(action,
 *                   params), api.req(method, path, body) for fixed routes, api.get(path)
 *        customers  the fifty: [{ index, id, phone, name, subject_ref }] — the module picks its
 *                   own subset (most apps 15-35 of 50, niche ones fewer) with `rng`
 *        shop       { services, branchId, operators } from foundation.mjs
 *        rng        a PRNG seeded on the module's own name: the same subset every run, so a re-run
 *                   tops up the same people rather than scattering a second history
 *        log        prints one indented line under the module's heading
 *      seed() must be safe to run again (resolve-or-create, idempotency keys, or read-then-skip).
 *      An app whose subject is ANOTHER shop imports `ensurePartnerShop()` from partner-shop.mjs (a
 *      second real signed-up shop) rather than inventing one.
 *   2. Import it below and add it to MODULES.
 *
 * The shop's entitlement to the new app needs no code: `ensureEntitlements` below subscribes to
 * whatever key in /subscription/apps the shop does not hold yet, through the same
 * POST /api/v1/subscription the store's own button calls.
 */
import { API, makeApi, signUpFreshDemoShop } from '../lib/demo-api.mjs';
import { ensureFreshDemoSession, readDemoSession } from '../lib/demo-session.mjs';
import { STAFF, ensureCustomers, ensureShop } from './foundation.mjs';

import * as visit from './visit.mjs';
import * as bookings from './bookings.mjs';
import * as loyalty from './loyalty.mjs';
import * as mobile_requests from './mobile_requests.mjs';
import * as coworking from './coworking.mjs';
import * as customer_service from './customer_service.mjs';
import * as insights from './insights.mjs';
import * as mutual_benefit from './mutual_benefit.mjs';
import * as partner_loyalty from './partner_loyalty.mjs';
import * as referrals from './referrals.mjs';
import * as campaigns from './campaigns.mjs';
import * as contacts from './contacts.mjs';
import * as rating from './rating.mjs';
import * as whatsapp_delivery_orders from './whatsapp_delivery_orders.mjs';

const PROFILE = 'apps';

// ORDER MATTERS ONLY WHERE ONE APP READS ANOTHER'S ROWS. Every module that RECORDS VISITS runs
// before the ones that read them: loyalty spends what those visits earned, contacts reads the
// return dates reminders learned from them, insights recounts all of them — so insights is last.
//
// TWO SOLD APPS HAVE NO MODULE, deliberately: «بوت خدمة العملاء الذكي» (feature.whatsapp) is a
// conversation on a connected WhatsApp number, and «المساعد الذكي» (feature.mobile_ai_assistant)
// runs on the phone with nothing stored server-side. The shop HOLDS both (ensureEntitlements);
// neither has a row any HTTP door could create.
export const MODULES = {
  visit, bookings, mobile_requests, mutual_benefit, loyalty, coworking, customer_service,
  partner_loyalty, referrals, campaigns, rating, contacts, whatsapp_delivery_orders, insights,
};

/** mulberry32 seeded from a string — deterministic per module, so its customer subset is stable. */
function rngFor(name) {
  let h = 2166136261;
  for (const ch of name) h = Math.imul(h ^ ch.charCodeAt(0), 16777619);
  let a = h >>> 0;
  const next = () => {
    a = (a + 0x6D2B79F5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  return {
    next,
    int: (lo, hi) => lo + Math.floor(next() * (hi - lo + 1)),
    pick: (arr) => arr[Math.floor(next() * arr.length)],
    /** `n` distinct items, stable for a given module. */
    sample(arr, n) {
      const a = [...arr];
      for (let i = a.length - 1; i > 0; i--) {
        const j = Math.floor(next() * (i + 1));
        [a[i], a[j]] = [a[j], a[i]];
      }
      return a.slice(0, Math.min(n, a.length));
    },
  };
}

/** A platform operator's session — the same `_platform` sign-in door the admin console uses
 *  (`/api/v1/auth/tenant`). Defaults are the throwaway dev-only operator local_stack.py seeds and
 *  the tour scripts already use; ADMIN_PHONE/ADMIN_PASSWORD point it at another deployment's. */
let adminToken = null;
async function platformAdmin() {
  if (adminToken) return adminToken;
  const res = await fetch(`${API}/api/v1/auth/tenant`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tenant: '_platform', username: process.env.ADMIN_PHONE ?? '0500000902',
      password: process.env.ADMIN_PASSWORD ?? 'HomeTour2026Demo!' }),
  });
  const out = await res.json().catch(() => ({}));
  if (!out.access_token) throw new Error(`platform admin sign-in refused (${res.status}) — set ADMIN_PHONE/ADMIN_PASSWORD`);
  adminToken = out.access_token;
  return adminToken;
}

/** Subscribe to one plan the way the store does: the free/trial door first, and for a paid plan
 *  the paid door (`checkout-link`) — which, for a plan carrying no trial of its own, billing opens
 *  on the platform's default trial, so nothing is owed yet. A purchase that would really need
 *  money is reported, never faked. */
async function subscribe(api, plan, idem) {
  try {
    return await api.req('POST', '/api/v1/subscription', { plan_id: plan.id, interval: 'month' });
  } catch (e) {
    if (!/→ 402/.test(e.message)) throw e;
  }
  const out = await api.req('POST', '/api/v1/subscription/checkout-link',
    { plan_id: plan.id, interval: 'month', idempotency_key: idem });
  if (out.checkout_required) throw new Error(`${plan.name} needs a real payment (${out.amount_minor} halalas) — not seeded`);
  return out;
}

/**
 * Every app key the shop does not hold yet, bought through the store's own doors. Signup already
 * opened a trial on every listed app that carries one (core/signup.py::_start_trials); what can
 * be left is a free app with no trial (bought straight), and an UNLISTED one — which no shop can
 * see until a platform operator shows it to that shop (core/app_visibility.py, the admin
 * console's own «العملاء» screen), after which the shop subscribes like any other app.
 *
 * Plus staff seats: hiring a login needs `staff.seats`, which only the «مقاعد إضافية» pack grants.
 * Bought through the paid door, then raised to `seats` with the same `billing.change_plan` the
 * console's capacity stepper calls.
 */
async function ensureEntitlements(api, seats) {
  const owned = await api.req('GET', '/api/v1/subscription/apps');
  if (!owned.checked) throw new Error(`billing could not be read: ${owned.message}`);
  const missing = owned.apps.filter((a) => !a.owned).map((a) => a.key);
  const listed = (await api.req('GET', '/api/v1/billing/plans')).plans ?? [];
  const grants = (p, key) => Object.keys(p.limits ?? {}).includes(key);
  const bought = [];
  for (const key of missing) {
    let plan = listed.find((p) => grants(p, key));
    if (!plan) {
      // HIDDEN FROM EVERY SHOP UNTIL AN OPERATOR SHOWS IT TO THIS ONE — the owner may read the
      // hidden list (billing.manage), but subscribing to an app nobody revealed would be a path
      // no real shop has; the reveal goes through the operator's own door first.
      const hidden = (await api.req('GET', '/api/v1/billing/plans?include_hidden=true')).plans ?? [];
      plan = hidden.find((p) => grants(p, key) && p.active !== false);
      if (!plan) { console.log(`  ⚠ ${key}: no plan grants it — not held`); continue; }
      const res = await fetch(`${API}/api/v1/platform/app-visibility`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${await platformAdmin()}` },
        body: JSON.stringify({ tenant: api.session.tenant, feature_key: key, visible: true }),
      });
      if (!res.ok) { console.log(`  ⚠ ${key}: operator reveal refused ${res.status}`); continue; }
    }
    const out = await subscribe(api, plan, `apps-seed-${key}`).catch((e) => ({ error: e.message }));
    if (out.error) console.log(`  ⚠ ${key}: subscribe refused — ${out.error}`);
    else bought.push(key);
  }

  const seatPlan = listed.find((p) => p.limits?.['staff.seats']);
  if (seatPlan && seats > 0) {
    const live = () => api.req('GET', '/api/v1/billing/subscriptions').then((x) => (x.subscriptions ?? [])
      .find((s) => s.plan_id === seatPlan.id && !['canceled', 'incomplete'].includes(s.status)));
    let sub = await live();
    if (!sub) { await subscribe(api, seatPlan, 'apps-seed-seats'); sub = await live(); }
    if (sub && (sub.quantity ?? 1) < seats) {
      await api.call(api.act('billing.change_plan'), { id: sub.id, new_plan_id: seatPlan.id, quantity: seats });
    }
  }

  const after = await api.req('GET', '/api/v1/subscription/apps');
  const still = after.apps.filter((a) => !a.owned).map((a) => a.key);
  return { held: after.apps.length - still.length, of: after.apps.length, bought, still };
}

async function main() {
  const only = process.argv.slice(2);
  const unknown = only.filter((n) => !MODULES[n]);
  if (unknown.length) throw new Error(`unknown module(s): ${unknown.join(', ')} — have: ${Object.keys(MODULES).join(', ')}`);

  let session = readDemoSession(PROFILE) ? await ensureFreshDemoSession(API, PROFILE) : null;
  if (session) console.log(`▸ reusing the demo shop (tenant ${session.tenant})`);
  else {
    console.log('▸ signing up a fresh demo shop (browser)');
    session = await signUpFreshDemoShop(PROFILE);
    console.log(`  ✔ tenant ${session.tenant}`);
  }
  const api = await makeApi(session, PROFILE);
  const verifyOnly = process.env.VERIFY_ONLY === '1';

  console.log('▸ entitlements');
  const ent = await ensureEntitlements(api, STAFF.length);
  console.log(`  ✔ holds ${ent.held}/${ent.of ?? ent.held} apps${ent.bought.length ? ` (just subscribed: ${ent.bought.join(', ')})` : ''}`);
  if (ent.still?.length) console.log(`  ⚠ still not held: ${ent.still.join(', ')}`);
  await api.refresh();

  console.log('▸ shop + customers');
  const log = (m) => console.log(`  ${m}`);
  const shop = await ensureShop(api, log);
  const customers = await ensureCustomers(api);
  log(`customers: ${customers.length}`);

  // ONE MODULE'S FAILURE DOES NOT COST THE OTHERS THEIR RUN — every module is self-contained, so a
  // whole-shop seed reports every failure at the end instead of stopping at the first one.
  const failed = [];
  for (const [name, mod] of Object.entries(MODULES)) {
    if (only.length && !only.includes(name)) continue;
    console.log(`▸ ${name} (${mod.app})`);
    const ctx = { api, session: api.session, customers, shop, rng: rngFor(name), log };
    try {
      const seeded = verifyOnly ? null : await mod.seed(ctx);
      if (seeded) log(`seeded: ${JSON.stringify(seeded)}`);
      const verified = await mod.verify({ ...ctx, rng: rngFor(name) });
      log(`✔ verified: ${JSON.stringify(verified)}`);
    } catch (e) {
      log(`✗ ${e.message}`);
      failed.push(name);
    }
  }
  if (failed.length) {
    console.log(`✗ ${failed.length} module(s) failed: ${failed.join(', ')}`);
    process.exitCode = 1;
  } else {
    console.log('✔ done — every module seeded and verified');
  }
}

// `exitCode`, never `process.exit()` mid-flight: on Windows an exit while fetch's sockets are still
// closing trips a libuv assertion that cuts off the output still buffered for the console.
main().catch((e) => { console.error(e.stack || e.message); process.exitCode = 1; });
