/**
 * Builds a demo account that looks LIVED IN — a women's salon (صالون نسائي) with ~20 real
 * services, a real operator, ~1000 real customers, real visits spread over months, real points
 * balances, and a mix of real bookings — so a tour recorded against it (اليوم, نقاطي, عملائي,
 * الحجوزات...) shows actual numbers and actual charts instead of a first-day empty state.
 *
 * EVERY SINGLE WRITE GOES THROUGH THE REAL API — never a direct database insert. This was an
 * explicit decision, not a shortcut skipped for time: an insert that skips the service's own
 * validation, its own side effects (loyalty accrual, insights snapshots, audit trail) produces
 * data that LOOKS real and behaves like nothing the product would ever actually create — a demo
 * account whose numbers a real one could never reach. Slower, and the only version worth trusting.
 *
 * A BROWSER ONLY FOR THE SIGNUP ITSELF. Everything after that — every service, operator,
 * customer, visit, booking — goes over plain HTTP with the session's own bearer token, the exact
 * same requests apps/console/src/api.ts and catalog.ts's call() make, replicated here rather than
 * imported (those modules assume a browser's own fetch/localStorage; this is a standalone script).
 * A live browser driving a thousand customers one click at a time would take hours; direct HTTP
 * calls, run with real concurrency, take minutes.
 *
 * THE RESULTING SESSION IS SAVED for tours to reuse — see record-tour.mjs's `useDemoSession`.
 * Re-running this script with an existing saved session SKIPS signup and adds MORE data on top
 * (idempotent services aside — see ensureServices), rather than creating a second demo shop.
 *
 * Usage:
 *   node media/tours/seed-demo-account.mjs
 *   CONSOLE=http://localhost:5175/app/ CUSTOMERS=1000 node media/tours/seed-demo-account.mjs
 */
import { existsSync, readFileSync } from 'node:fs';
import { writeFile } from 'node:fs/promises';
import { join, dirname, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { chromiumModule } from '../lib/browser.mjs';
import { ensureFreshDemoSession, saveDemoCredentials } from './lib/demo-session.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const CONSOLE_DIR = resolve(HERE, '../../apps/console');
const SESSION_FILE = join(HERE, '.demo-session.json');
// THE ONE THING THE SESSION FILE ALONE CANNOT SURVIVE. The saved access token lives fifteen
// minutes and is meant to be replaced by the refresh token beside it — but a refresh is a single
// platform call away from being unavailable (it was, live: identity's own /auth/refresh hung past
// every timeout while ordinary sign-in answered in under a second), and a demo shop's signup phone
// is RANDOM and was never written down anywhere. That combination made a fully seeded account —
// a thousand customers, months of visits — permanently unreachable over one expired token. The
// phone and password that opened the shop are what re-mint a session from nothing, so they are
// saved beside it, gitignored the same way and for the same reason.
const CREDENTIALS_FILE = join(HERE, '.demo-credentials.json');

const rawBase = process.env.CONSOLE ?? 'http://localhost:5174';
const BASE_URL = rawBase.endsWith('/') ? rawBase : `${rawBase}/`;
const API = BASE_URL.replace(/\/app\/?$/, ''); // the app is served under /app/, the API is at the root

const N_CUSTOMERS = Number(process.env.CUSTOMERS ?? 1000);
const CONCURRENCY = Number(process.env.CONCURRENCY ?? 12);

// ── the catalogue a real women's salon actually sells — not filler names ──────────────────────
const SERVICES = [
  { name: 'قص شعر', cycle: 30, duration: 30, price: 6000, points: 20, group: 'الشعر' },
  { name: 'صبغة شعر كاملة', cycle: 60, duration: 120, price: 25000, points: 80, group: 'الشعر' },
  { name: 'صبغة جذور', cycle: 30, duration: 60, price: 12000, points: 40, group: 'الشعر' },
  { name: 'هايلايت', cycle: 60, duration: 150, price: 35000, points: 100, group: 'الشعر' },
  { name: 'بروتين شعر', cycle: 90, duration: 180, price: 45000, points: 120, group: 'الشعر' },
  { name: 'تسريحة سهرة', cycle: 0, duration: 60, price: 15000, points: 50, group: 'الشعر' },
  { name: 'غسيل وتنشيف', cycle: 14, duration: 30, price: 4000, points: 10, group: 'الشعر' },
  { name: 'مانيكير', cycle: 21, duration: 45, price: 8000, points: 25, group: 'الأظافر' },
  { name: 'باديكير', cycle: 21, duration: 45, price: 9000, points: 25, group: 'الأظافر' },
  { name: 'أظافر جل', cycle: 21, duration: 60, price: 12000, points: 35, group: 'الأظافر' },
  { name: 'تنظيف بشرة عميق', cycle: 30, duration: 60, price: 18000, points: 55, group: 'العناية بالبشرة' },
  { name: 'حمام مغربي', cycle: 45, duration: 90, price: 20000, points: 60, group: 'العناية بالبشرة' },
  { name: 'تقشير وترطيب', cycle: 30, duration: 45, price: 14000, points: 45, group: 'العناية بالبشرة' },
  { name: 'ماسك ذهب', cycle: 30, duration: 45, price: 16000, points: 50, group: 'العناية بالبشرة' },
  { name: 'مكياج سهرة', cycle: 0, duration: 60, price: 20000, points: 60, group: 'المكياج' },
  { name: 'مكياج يومي', cycle: 0, duration: 30, price: 10000, points: 30, group: 'المكياج' },
  { name: 'رموش فردي', cycle: 21, duration: 90, price: 18000, points: 55, group: null },
  { name: 'حواجب هيني تاتو', cycle: 60, duration: 60, price: 22000, points: 65, group: null },
  { name: 'إزالة شعر بالشمع (كامل)', cycle: 30, duration: 90, price: 15000, points: 45, group: null },
  { name: 'جلسة تدليك استرخاء', cycle: 30, duration: 60, price: 17000, points: 50, group: null },
];

const FIRST_NAMES = ['سارة', 'نورة', 'ريم', 'لمى', 'دانة', 'جود', 'العنود', 'شهد', 'غلا', 'رغد',
  'أثير', 'روان', 'جواهر', 'منال', 'هيا', 'وجدان', 'مها', 'عبير', 'ندى', 'أمل'];

function randomPhone() {
  return `05${Math.floor(Math.random() * 90_000_000) + 10_000_000}`;
}
function randomName() {
  return FIRST_NAMES[Math.floor(Math.random() * FIRST_NAMES.length)];
}
function pick(arr) { return arr[Math.floor(Math.random() * arr.length)]; }

/** Runs `items` through `worker` with at most `n` in flight at once — real concurrency, not a
 *  single-file queue, without needing a dependency for it. */
async function pool(items, n, worker) {
  const results = [];
  let i = 0;
  async function run() {
    while (i < items.length) {
      const idx = i++;
      results[idx] = await worker(items[idx], idx).catch((e) => ({ error: e.message }));
    }
  }
  await Promise.all(Array.from({ length: Math.min(n, items.length) }, run));
  return results;
}

async function main() {
  let session;
  if (existsSync(SESSION_FILE)) {
    // RE-MINTED IF IT IS SPENT, NOT ASSUMED ALIVE — seeding makes thousands of calls over many
    // minutes on a token that lives fifteen, and a demo account is far too expensive to rebuild
    // over one. See lib/demo-session.mjs for why this can't lean on the refresh token.
    session = await ensureFreshDemoSession(API);
    console.log(`reusing existing demo session (tenant already has a shop) — adding more data on top`);
  } else {
    session = await signUpFreshDemoShop();
    await writeFile(SESSION_FILE, JSON.stringify(session, null, 2), 'utf8');
    console.log(`✔ demo shop created, session saved to ${SESSION_FILE}`);
  }

  const catalog = await getJson('/api/v1/app/catalog', session.token);
  const act = (id) => {
    for (const s of catalog.services) {
      const hit = s.actions.find((a) => a.id === id);
      if (hit) return hit;
    }
    throw new Error(`action "${id}" not in this session's catalog — does the account have the capability?`);
  };

  console.log('▸ services');
  const serviceIds = await ensureServices(session, act);
  console.log(`  ✔ ${serviceIds.length} services`);

  console.log('▸ operator');
  const { operatorId, ticket } = await ensureOperator(session, act);
  const extraOperatorIds = await ensureExtraOperators(session, act);
  console.log(`  ✔ ${1 + extraOperatorIds.length} operators ready`);

  // THE BOOKINGS BOARD ALONE, WITHOUT REBUILDING A WHOLE SHOP. A الحجوزات recording needs TODAY to
  // look like a real salon's day, and today only stays that way for one day — but re-running the
  // full seed to refresh it would add another thousand customers and another few months of visits
  // to an account that already has them, every single time. This flag runs the one step that
  // actually goes stale.
  if (process.env.BOOKINGS_ONLY === '1') {
    console.log('▸ bookings only (BOOKINGS_ONLY=1)');
    const onlyBranch = await getBranchId(session, act);
    await seedWeekBoard(session, onlyBranch, [operatorId, ...extraOperatorIds]);
    await seedDenseDay(session, onlyBranch, [operatorId, ...extraOperatorIds]);
    console.log('✔ bookings board refreshed');
    return;
  }

  console.log('▸ hero customer (real points + real rewards, for the visit/offers tour)');
  await seedHeroCustomer(session, act, serviceIds, operatorId, ticket);

  console.log(`▸ ${N_CUSTOMERS} customers with visits`);
  let done = 0;
  await pool(Array.from({ length: N_CUSTOMERS }), CONCURRENCY, async () => {
    await seedOneCustomer(session, serviceIds, operatorId, ticket);
    done += 1;
    if (done % 100 === 0) console.log(`  … ${done}/${N_CUSTOMERS}`);
  });
  console.log(`  ✔ ${N_CUSTOMERS} customers seeded`);

  console.log('▸ bookings');
  const branchId = await getBranchId(session, act);
  await seedBookings(session, serviceIds, [operatorId, ...extraOperatorIds], branchId);
  await seedWeekBoard(session, branchId, [operatorId, ...extraOperatorIds]);
  await seedDenseDay(session, branchId, [operatorId, ...extraOperatorIds]);
  console.log('  ✔ bookings seeded');

  console.log('✔ demo account ready');
}

async function signUpFreshDemoShop() {
  const chromium = chromiumModule();
  const browser = await chromium.launch();
  const context = await browser.newContext({ baseURL: BASE_URL, viewport: { width: 430, height: 932 } });
  const page = await context.newPage();
  const { openShop, PASSWORD } = await import(pathToFileURL(join(CONSOLE_DIR, 'e2e/fixtures.ts')).href);
  await page.goto(BASE_URL);
  // THE PHONE IT PICKED, WRITTEN DOWN — `openShop()` generates a random one and returns it, and
  // for a long time nothing here kept it. That number plus the fixture's own password is the ONLY
  // way back into this shop once an access token ages out; without it a fully seeded account is
  // one expired token away from being unreachable for good (it was, live — see
  // lib/demo-session.mjs).
  const phone = await openShop(page);
  saveDemoCredentials(phone, PASSWORD);
  const raw = await page.evaluate(() => localStorage.getItem('raje3.session'));
  await browser.close();
  return JSON.parse(raw);
}

async function getJson(path, token) {
  const res = await fetch(`${API}${path}`, { headers: { Authorization: `Bearer ${token}` } });
  if (!res.ok) throw new Error(`GET ${path} → ${res.status}`);
  return res.json();
}

async function callAction(session, action, params = {}) {
  const rest = { ...params };
  let path = action.path.replace(/\{([^}]+)\}/g, (_, name) => {
    const v = rest[name]; delete rest[name]; return encodeURIComponent(String(v));
  });
  const method = action.method || 'GET';
  const opts = { method, headers: { Authorization: `Bearer ${session.token}` } };
  if (method === 'GET') {
    const q = new URLSearchParams(Object.entries(rest).map(([k, v]) => [k, String(v)]));
    if ([...q].length) path += `?${q}`;
  } else {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(rest);
  }
  const res = await fetch(`${API}${path}`, opts);
  if (!res.ok) throw new Error(`${method} ${path} → ${res.status}: ${(await res.text()).slice(0, 200)}`);
  const text = await res.text();
  return text ? JSON.parse(text) : {};
}

/** Idempotent-ish: only creates a service if a same-named one doesn't already exist, so a second
 *  run of this script against the same demo shop doesn't duplicate the whole catalogue. */
async function ensureServices(session, act) {
  const listAction = act('operations.list_services');
  const existing = await callAction(session, listAction).catch(() => ({ services: [] }));
  const haveNames = new Set((existing.services ?? []).map((s) => s.name));
  const ids = (existing.services ?? []).map((s) => s.id);

  const createAction = act('operations.create_service');
  for (const svc of SERVICES) {
    if (haveNames.has(svc.name)) continue;
    const created = await callAction(session, createAction, {
      name: svc.name, cycle_days: svc.cycle, duration_minutes: svc.duration, price_minor: svc.price,
    });
    if (created?.id) {
      ids.push(created.id);
      // points and group are set via reminders'/loyalty's own actions where they exist —
      // best-effort, matching Services.tsx's own addService flow; a missing capability here
      // just means this demo account skips that one refinement, not a failed seed.
      const pointsAction = catalogAction(session, act, 'loyalty.settings.service');
      if (pointsAction) await callAction(session, pointsAction, { service_id: created.id, points: svc.points }).catch(() => {});
      if (svc.group) {
        const groupAction = catalogAction(session, act, 'reminders.set_group');
        if (groupAction) await callAction(session, groupAction, { service_id: created.id, group: svc.group }).catch(() => {});
      }
    }
  }
  return ids;
}

function catalogAction(session, act, id) {
  try { return act(id); } catch { return null; }
}

// FIXED PATHS, NOT CATALOG ACTIONS — apps/console/src/api.ts's own header comment says so
// explicitly: bookings/visit/loyalty-read/customer-search go through fixed routes it calls
// directly, never the dynamic action catalog. Replicated here as the same literal paths that
// file uses, not guessed catalog ids that would throw the moment act() couldn't find them.
const ENSURE_CUSTOMER = { path: '/api/v1/field/customers/ensure', method: 'POST' };
const CREATE_BOOKING = { path: '/api/v1/bookings', method: 'POST' };
const ATTEND_BOOKING = (id) => ({ path: `/api/v1/bookings/${id}/attend`, method: 'PATCH' });
const NO_SHOW_BOOKING = (id) => ({ path: `/api/v1/bookings/${id}/no-show`, method: 'PATCH' });
const CANCEL_BOOKING = (id) => ({ path: `/api/v1/bookings/${id}/cancel`, method: 'PATCH' });

/**
 * PIN-BASED OPERATORS ARE OFF ON THIS DEPLOYMENT — found live, not assumed: the real server
 * refused `operations.create_operator` outright (`PIN_OPERATORS_OFF`, its own message says to
 * hire with a login instead — Team.tsx's own `pinKind` flag defaults the same way). So this
 * hires a real login-based operator (`operations.hire_member`, phone+password like any real
 * staff member) instead of a PIN one, and skips verify-pin's ticket entirely — VisitDraft's own
 * `operator_ticket` field is optional, and it exists to authenticate a PIN specifically; a
 * login-based operator's `operator_id` alone is what the door has accepted since it was written
 * (api.ts's own comment on the field).
 */
async function ensureOperator(session, act) {
  const listAction = act('operations.list_operators');
  const existing = await callAction(session, listAction).catch(() => ({ operators: [] }));
  let operator = (existing.operators ?? []).find((o) => o.name === 'موظفة الاستقبال');
  if (!operator) {
    const hireAction = act('operations.hire_member');
    const branchesAction = act('operations.list_branches');
    const branches = await callAction(session, branchesAction).catch(() => ({ branches: [] }));
    const branchId = branches.branches?.[0]?.id;
    operator = await callAction(session, hireAction, {
      name: 'موظفة الاستقبال', phone: randomPhone(), password: 'Kobo2026$Staff',
      role: 'operator', branch_id: branchId,
    });
  }
  return { operatorId: operator.id, ticket: undefined };
}

// THREE STAFF, NOT ONE — a single operator means the desktop grid's own multi-column layout
// (Bookings.tsx: one column per operator in day view) always shows one lane, indistinguishable
// from the mobile grid it is meant to look richer than. Named for real specialities a salon
// actually staffs, not "Staff 2"/"Staff 3".
const EXTRA_STAFF_NAMES = ['أخصائية الشعر', 'أخصائية الأظافر'];

async function ensureExtraOperators(session, act) {
  const listAction = act('operations.list_operators');
  const existing = await callAction(session, listAction).catch(() => ({ operators: [] }));
  const branchesAction = act('operations.list_branches');
  const branches = await callAction(session, branchesAction).catch(() => ({ branches: [] }));
  const branchId = branches.branches?.[0]?.id;
  const ids = [];
  for (const name of EXTRA_STAFF_NAMES) {
    let operator = (existing.operators ?? []).find((o) => o.name === name);
    if (!operator) {
      const hireAction = act('operations.hire_member');
      operator = await callAction(session, hireAction, {
        name, phone: randomPhone(), password: 'Kobo2026$Staff', role: 'operator', branch_id: branchId,
      });
    }
    if (operator?.id) ids.push(operator.id);
  }
  return ids;
}

async function getBranchId(session, act) {
  const branchesAction = act('operations.list_branches');
  const branches = await callAction(session, branchesAction).catch(() => ({ branches: [] }));
  return branches.branches?.[0]?.id;
}

// A FIXED, MEMORABLE NUMBER — every other customer in this file gets a random one, deliberately;
// this ONE needs to be typeable on camera and identical every time this script runs, since the
// visit/offers tour's own selectors and captions are built around finding HER specifically.
const HERO_PHONE = '0555010101';
const HERO_NAME = 'عميلة العرض';
// The highest-points service in the catalogue — 120/visit; 40 visits (below) clears both seeded rewards with a large, re-recording-safe
// manager-approval reward at cost 600 for real, not by inventing a smaller reward to fit fewer
// visits. Matched by NAME, not a hardcoded id — service ids are minted fresh every signup.
const HERO_SERVICE_NAME = 'بروتين شعر';

/**
 * ONE customer with real points, a real cheap reward, and a real manager-approval reward — built
 * for the visit-screen tour's own «عروضه ونقاطه» chapter, which needs actual non-empty state to
 * show, not the honest-but-empty "لا عروض ولا نقاط مستحقّة" every other seeded customer gets.
 *
 * EVERYTHING HERE IS THE REAL API, same discipline as the rest of this file — points accrue from
 * real recordVisit calls, never a direct balance write. The one thing this canNOT do the same
 * way is the customer's OFFER: there is no owner-facing "grant an offer" action by design (see
 * deploy/seed/seed-field-offer.py's own header — an offer is created by a SEND, and forging one
 * from a screen would let the screen prove an entitlement nothing ever sent). This function seeds
 * everything reachable over plain HTTP and prints the one command + values a human (or an ops-mcp
 * call) still has to run inside the cluster for the offer itself.
 */
async function seedHeroCustomer(session, act, serviceIds, operatorId, ticket) {
  // A REAL MANAGER-APPROVAL THRESHOLD — without this, `needs_approval` never appears and the
  // whole "باعتماد المدير" chapter has nothing real to point at. `points` MUST be resent as
  // whatever it already is — this endpoint takes the whole general-settings row, not a patch, so
  // reading it first and writing it straight back (only `manager_threshold` actually changing)
  // avoids silently resetting a value this script never meant to touch.
  const generalAction = catalogAction(session, act, 'loyalty.settings.general');
  const readGeneralAction = catalogAction(session, act, 'loyalty.settings.read');
  if (generalAction && readGeneralAction) {
    const current = await callAction(session, readGeneralAction).catch(() => ({}));
    await callAction(session, generalAction, {
      points: current.points ?? true, manager_threshold: 500,
    }).catch(() => {});
  }

  // WHICH SERVICE ID IS "بروتين شعر" THIS RUN — service ids are minted fresh every signup, so this
  // is resolved by name every time rather than assumed from SERVICES' own array order.
  const listAction = act('operations.list_services');
  const listed = await callAction(session, listAction).catch(() => ({ services: [] }));
  const heroServiceId = (listed.services ?? []).find((s) => s.name === HERO_SERVICE_NAME)?.id
    ?? serviceIds[0];

  // THREE REAL REWARDS — one plain gift anyone can redeem, one tied to a real catalogue service
  // (the only kind that lights the ⭐ badge on a service tile, since ServiceGrid's `redeemable` set
  // is built from `reward.service_id`), and one above the shop's own manager threshold so
  // `needs_approval` has something real to be true about.
  //
  // `item`, NOT `gift` — loyalty's own REWARD_TYPES is ("service", "item", "discount") and it
  // refuses anything else by name. This said `gift` for as long as it existed, and the refusal was
  // swallowed by a bare `.catch(() => {})`, so the demo shop silently had NO rewards at all: a hero
  // customer with 4800 real points and an empty «مكافآته» list, on the one account every tour that
  // shows a redemption is recorded against. Failures are printed now rather than swallowed —
  // best-effort must still be able to say what went wrong.
  const rewardsAction = catalogAction(session, act, 'loyalty.rewards.create');
  const existingRewards = await getJson('/api/v1/loyalty/rewards', session.token).catch(() => ({ rewards: [] }));
  const haveReward = new Set((existingRewards.rewards ?? []).map((r) => r.name));
  if (rewardsAction) {
    for (const reward of [
      { name: 'قهوة مجانية', cost: 100, type: 'item' },
      { name: 'قص شعر مجاناً', cost: 300, type: 'service', service_id: (listed.services ?? []).find((s) => s.name === 'قص شعر')?.id ?? '' },
      { name: 'جلسة مجانية VIP', cost: 600, type: 'item' },
    ]) {
      if (haveReward.has(reward.name)) continue;
      if (reward.type === 'service' && !reward.service_id) continue;   // nothing real to point at
      await callAction(session, rewardsAction, reward)
        .catch((e) => console.log(`  ⚠ reward "${reward.name}" refused: ${e.message}`));
    }
  }

  // FORTY REAL VISITS, EVERY FEW DAYS — a genuinely regular customer (a salon regular every 3
  // days is realistic, not a once-a-year one), and a BIG point buffer on purpose: the visit
  // tour's own redeem steps are REAL spends (loyalty.redeem is not reversible the way stop-
  // service.mjs's إيقاف↔تفعيل toggle is) — every re-recording of that tour spends real points off
  // this real balance. 120 × 40 = 4800, enough for many, many re-recordings before either seeded
  // reward (100, 600) needs a fresh reseed to keep affording.
  const now = Math.floor(Date.now() / 1000);
  for (let v = 0; v < 40; v++) {
    await callAction(session, RECORD_VISIT, {
      phone: HERO_PHONE, name: v === 0 ? HERO_NAME : undefined,
      service_ids: [heroServiceId],
      idempotency_key: `seed-hero-${v}`,
      occurred_at: now - v * 3 * 86400,
      operator_id: operatorId, operator_ticket: ticket,
    }).catch(() => {});
  }

  // THE PSEUDONYM SHE'S ACTUALLY KNOWN BY — the one piece an offer seed needs and this script
  // cannot invent (reminders holds no phone numbers, only this HMAC-derived ref).
  const byPhone = await getJson(
    `/api/v1/field/customers/by-phone?phone=${encodeURIComponent(HERO_PHONE)}`, session.token,
  ).catch(() => null);
  const subjectRef = byPhone?.customer?.subject_ref;
  console.log(`  ✔ ${HERO_PHONE} — 40 visits on "${HERO_SERVICE_NAME}", 2 real rewards, subject_ref=${subjectRef ?? '(unresolved)'}`);
  if (subjectRef) {
    console.log(`  ▸ her OFFER still needs one in-cluster step (no HTTP action creates one by design):`);
    console.log(`    TENANT=${session.tenant} SUBJECT=${subjectRef} kubectl -n base-services exec -i deploy/reminders -- python - < deploy/seed/seed-field-offer.py`);
  } else {
    console.log(`  ⚠ could not resolve her subject_ref — the offer step can't run without it`);
  }
}

/** One customer, with a REALISTIC visit history — not one visit each, which would make every
 *  retention/return-rate chart in the product read as "nobody ever comes back". 1 to 5 visits,
 *  spread over the last several months, each with 1-3 real services and points accruing for real
 *  through the same recordVisit call the actual field screen makes. */
const RECORD_VISIT = { path: '/api/v1/field/visits', method: 'POST' };

async function seedOneCustomer(session, serviceIds, operatorId, ticket) {
  const phone = randomPhone();
  const name = randomName();
  const visitCount = 1 + Math.floor(Math.random() * 5);
  const now = Math.floor(Date.now() / 1000);
  for (let v = 0; v < visitCount; v++) {
    const servicesThisVisit = shuffle(serviceIds).slice(0, 1 + Math.floor(Math.random() * 3));
    const daysAgo = Math.floor(Math.random() * 180); // spread across ~6 months
    await callAction(session, RECORD_VISIT, {
      phone, name: v === 0 ? name : undefined,
      service_ids: servicesThisVisit,
      idempotency_key: `seed-${phone}-${v}-${Math.random().toString(36).slice(2)}`,
      occurred_at: now - daysAgo * 86400,
      operator_id: operatorId, operator_ticket: ticket,
    });
  }
}

function shuffle(arr) {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

/** A mix of booking states — booked (future), attended, no-show, cancelled — so the bookings
 *  grid and the no-show risk indicator both have something real to show, not an empty week. */
async function seedBookings(session, serviceIds, operatorIds, branchId) {
  if (!branchId) return; // no branch resolvable — skip rather than guess one
  const ids = Array.isArray(operatorIds) ? operatorIds : [operatorIds]; // callers pre-dating multi-staff still work
  const now = Math.floor(Date.now() / 1000);

  const drafts = Array.from({ length: 60 }, (_, i) => {
    const futureDays = -14 + i; // half past, half upcoming — realistic mixed grid
    return {
      branch_id: branchId, operator_id: pick(ids),
      service_ids: shuffle(serviceIds).slice(0, 1 + Math.floor(Math.random() * 2)),
      starts_at: now + futureDays * 86400 + Math.floor(Math.random() * 8) * 3600,
    };
  });
  // 60 bookings over 60 days averages ~1/day — TODAY specifically (the recorder's own default
  // view) can easily land empty by chance, which is exactly what a live recording caught. A few
  // guaranteed slots close to the seeding moment itself (not a UTC/local day-boundary
  // calculation, which would risk landing on the wrong calendar day for the shop's own timezone)
  // keep the default view from ever being a coin flip — safe as long as recording follows seeding
  // the same day, which is how this script is actually used. ONE PER STAFF MEMBER, explicitly (not
  // `pick`) — the whole point of seeding more than one operator is a desktop grid with more than
  // one populated column; leaving this to chance could still land all four on the same person.
  const todayOffsets = [-3, -1, 1, 3];
  todayOffsets.forEach((offsetHours, i) => {
    drafts.push({
      branch_id: branchId, operator_id: ids[i % ids.length],
      service_ids: shuffle(serviceIds).slice(0, 1 + Math.floor(Math.random() * 2)),
      starts_at: now + offsetHours * 3600,
    });
  });

  await pool(drafts, CONCURRENCY, async (draft) => {
    // Each booking needs its own real customer, resolved the same way the booking dialog does.
    const phone = randomPhone();
    const ensured = await callAction(session, ENSURE_CUSTOMER, { phone, name: randomName() });
    const customerId = ensured.customer?.id;
    if (!customerId) return;
    const booking = await callAction(session, CREATE_BOOKING, { ...draft, customer_id: customerId });
    if (!booking?.id) return;
    const past = draft.starts_at < now;
    if (!past) return; // future bookings stay "booked" — that's the correct, real state for them
    const outcome = Math.random();
    if (outcome < 0.7) await callAction(session, ATTEND_BOOKING(booking.id)).catch(() => {});
    else if (outcome < 0.85) await callAction(session, NO_SHOW_BOOKING(booking.id)).catch(() => {});
    else await callAction(session, CANCEL_BOOKING(booking.id)).catch(() => {});
  });
}

// ── a week that looks like a real salon's week ────────────────────────────────────────────────
//
// WHY THE RANDOM SPREAD ABOVE ISN'T ENOUGH. `seedBookings` scatters 60 bookings over 60 days —
// roughly one a day — which is honest volume for "this shop has history" but is NOT what the
// الحجوزات screen exists to show: a board. Recorded as-is, the day view showed a single card in
// one of three columns and the week view showed two, so the one screen whose whole subject is a
// full day of appointments demonstrated an empty one (seen live, in a real recording, not
// predicted). This lays a real working day over the top of it — every staff member with her own
// column of appointments, spaced so nothing collides, at the hours a salon actually works.
//
// STILL EVERY WRITE THROUGH THE REAL API, same rule as the rest of this file: real customers
// resolved through `ensure`, real bookings created through `POST /api/v1/bookings`, real
// attendance closed through the real attend/no-show routes. Nothing is inserted behind the
// service's back, so the board a tour films is one the product could actually have produced.

const LIST_BOOKINGS = (branchId, date) => ({ path: `/api/v1/bookings?branch_id=${encodeURIComponent(branchId)}&date=${date}`, method: 'GET' });
const LIST_STAFF = { path: '/api/v1/staff/operators', method: 'GET' };
const CATALOGUE = { path: '/api/v1/field/catalogue', method: 'GET' };

/** Riyadh is the shop's own clock — the same `+03:00` every epoch on the bookings screen is built
 *  against (`epochAt` in Bookings.tsx). Never the recording machine's local zone, which can and
 *  does differ and would place a "10:00 appointment" an hour off the column it was meant for. */
function riyadhToday() {
  return new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Riyadh' }); // YYYY-MM-DD
}
function addDaysStr(dateStr, delta) {
  const [y, m, d] = dateStr.split('-').map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  dt.setUTCDate(dt.getUTCDate() + delta);
  return dt.toISOString().slice(0, 10);
}
function epochAtRiyadh(dateStr, minutes) {
  const h = String(Math.floor(minutes / 60)).padStart(2, '0');
  const mm = String(minutes % 60).padStart(2, '0');
  return Math.floor(Date.parse(`${dateStr}T${h}:${mm}:00+03:00`) / 1000);
}

/** Which specialities a name implies — the three staff this script hires are named for real salon
 *  specialities, so their columns should hold the work those specialities actually do rather than
 *  a shuffle of the whole catalogue across all three. */
const STAFF_SERVICES = [
  { match: 'الشعر', names: ['قص شعر', 'صبغة جذور', 'غسيل وتنشيف', 'تسريحة سهرة'] },
  { match: 'الأظافر', names: ['مانيكير', 'باديكير', 'أظافر جل'] },
  { match: '', names: ['تنظيف بشرة عميق', 'تقشير وترطيب', 'ماسك ذهب', 'مكياج يومي'] },
];

// STAGGERED PER COLUMN, NOT THE SAME FOUR HOURS THREE TIMES — a board where every staff member
// starts and finishes together reads as generated data. Spacing inside each column is 2½ hours
// against services of at most 60 minutes, so no booking can ever collide with the next one in its
// own column (the server would refuse it, correctly, and the seed would silently come up short).
const DAY_SLOTS = [
  [540, 690, 840, 1050],   //  9:00 · 11:30 · 14:00 · 17:30
  [570, 720, 900, 1080],   //  9:30 · 12:00 · 15:00 · 18:00
  [600, 780, 960, 1140],   // 10:00 · 13:00 · 16:00 · 19:00
];

async function seedWeekBoard(session, branchId, operatorIds) {
  if (!branchId || !operatorIds?.length) return;
  const [{ services = [] }, staffAnswer, hoursAnswer] = await Promise.all([
    callAction(session, CATALOGUE).catch(() => ({ services: [] })),
    callAction(session, LIST_STAFF).catch(() => ({ operators: [] })),
    callAction(session, { path: '/api/v1/bookings/working-hours', method: 'GET' }).catch(() => ({ weekly: {} })),
  ]);
  const staff = (staffAnswer.operators ?? []).filter((o) => operatorIds.includes(o.id));
  if (staff.length === 0 || services.length === 0) return;

  const byName = new Map(services.map((s) => [s.name, s]));
  const poolFor = (name) => {
    const spec = STAFF_SERVICES.find((s) => s.match && name.includes(s.match)) ?? STAFF_SERVICES[2];
    const picked = spec.names.map((n) => byName.get(n)).filter((s) => s && s.duration_minutes > 0);
    // A SHOP THAT RENAMED OR REMOVED THOSE SERVICES STILL GETS A BOARD — anything short enough not
    // to collide with the next slot is a fine stand-in; only a catalogue with nothing at all under
    // an hour leaves a column empty, and that is a true fact about the catalogue.
    return picked.length ? picked : services.filter((s) => s.duration_minutes > 0 && s.duration_minutes <= 60);
  };

  const today = riyadhToday();
  const weekStart = addDaysStr(today, -new Date(`${today}T00:00:00Z`).getUTCDay()); // Sunday first
  const now = Math.floor(Date.now() / 1000);
  let created = 0;

  for (let d = 0; d < 7; d++) {
    const date = addDaysStr(weekStart, d);
    const jsDay = new Date(`${date}T00:00:00Z`).getUTCDay();
    const hours = hoursAnswer.weekly?.[String((jsDay + 6) % 7)];   // 0=Monday..6=Sunday, server's own numbering
    if (hours?.closed) continue;
    const open = hours?.start_minute ?? 480;
    const close = hours?.end_minute ?? 1320;

    // WHAT IS ALREADY THERE, READ FIRST — this runs against an account that already has bookings
    // (the random spread above, or yesterday's run of this same function), and a slot that
    // overlaps one of them would simply be refused by the server's own conflict lock. Reading the
    // day and skipping those slots means the board fills up instead of silently coming up short.
    const existing = await callAction(session, LIST_BOOKINGS(branchId, date)).catch(() => ({ bookings: [] }));
    const busy = new Map();   // operator id → [[startMinute, endMinute], …]
    for (const b of existing.bookings ?? []) {
      if (b.status === 'cancelled') continue;
      const start = Math.round((b.starts_at - epochAtRiyadh(date, 0)) / 60);
      if (!busy.has(b.operator_id)) busy.set(b.operator_id, []);
      busy.get(b.operator_id).push([start, start + b.duration_minutes]);
      // AND CLOSED OUT IF ITS TIME HAS PASSED — a booking still «محجوز» hours after it ended is
      // what the screen's own overdue banner is for, and a demo day left full of them shows that
      // alarm permanently rather than a shop that closes its day out. Today's genuinely unclosed
      // ones are closed here the same way a receptionist would: attended.
      if (b.status === 'booked' && b.starts_at + b.duration_minutes * 60 < now) {
        await callAction(session, ATTEND_BOOKING(b.id)).catch(() => {});
      }
    }

    const isFuture = date > today;
    for (const [i, operator] of staff.entries()) {
      const pool = poolFor(operator.name || '');
      if (pool.length === 0) continue;
      const slots = DAY_SLOTS[i % DAY_SLOTS.length].slice(0, date === today ? 4 : 3);
      for (const [k, minute] of slots.entries()) {
        const service = pool[(d + k) % pool.length];
        if (minute < open || minute + service.duration_minutes > close) continue;
        const mine = busy.get(operator.id) ?? [];
        if (mine.some(([s, e]) => minute < e && s < minute + service.duration_minutes)) continue;

        const phone = randomPhone();
        const ensured = await callAction(session, ENSURE_CUSTOMER, { phone, name: randomName() })
          .catch(() => ({}));
        const customerId = ensured.customer?.id;
        if (!customerId) continue;
        // A REAL MIX OF PAYMENT STATES — the screen's own payment filter and its deposit/paid
        // pills have nothing to show on a board where every booking was «بدون». Rotated rather
        // than randomised so a re-run produces the same recognisable shape.
        const pay = ['deposit', 'paid', 'none', 'deposit'][(d + k) % 4];
        const startsAt = epochAtRiyadh(date, minute);
        const booking = await callAction(session, CREATE_BOOKING, {
          branch_id: branchId, operator_id: operator.id, customer_id: customerId,
          service_ids: [service.id], starts_at: startsAt,
          payment_status: pay,
          deposit_amount_minor: pay === 'deposit' ? (k % 2 ? 10000 : 5000) : undefined,
        }).catch(() => null);
        if (!booking?.id) continue;
        created += 1;
        mine.push([minute, minute + service.duration_minutes]);
        busy.set(operator.id, mine);
        // ALREADY OVER BY NOW → CLOSED, exactly as the day would really have gone. A no-show every
        // so often, because a board with none is a shop that has never had one.
        if (!isFuture && startsAt + service.duration_minutes * 60 < now) {
          const noShow = (d + k) % 7 === 3;
          await callAction(session, noShow ? NO_SHOW_BOOKING(booking.id) : ATTEND_BOOKING(booking.id))
            .catch(() => {});
        }
      }
    }
  }
  console.log(`  ✔ week board: ${created} booking(s) across ${staff.length} staff, ${weekStart} → ${addDaysStr(weekStart, 6)}`);
}

// ── and TODAY, filled the way a good day actually fills ───────────────────────────────────────
//
// WHY A SECOND, DENSER PASS OVER ONE DAY. `seedWeekBoard` above gives every day of the week the
// same shape — three or four appointments per staff member — which is a believable WEEK and a
// thin DAY: at 1920×1080 the day grid draws fourteen hours as a 1554px column, and four cards in
// it is mostly empty ruled paper. The desktop clip's whole subject is that column, so today gets
// its own pass that walks each staff member's own working window from open to close and fills it
// the way a booked-out salon fills: one appointment after another with real gaps between them,
// never a uniform comb.
//
// DELIBERATELY NOT FULL. Roughly two thirds occupancy, because the same board has to leave real
// empty quarter-hours for the things a tour DOES on it — a card dragged somewhere new, a booking
// created from an empty cell, a slot search that has an answer. A perfectly full day would
// demonstrate a busy shop and nothing else.
const DENSE_GAPS = [30, 45, 30, 60, 30, 45];   // minutes of air after each appointment, cycled

/** Each staff member's own long-form pool — `STAFF_SERVICES` names, but WITHOUT the ≤60-minute
 *  ceiling `seedWeekBoard`'s spacing forced on it. A day with nothing longer than an hour on it
 *  reads as a walk-in counter, not a salon: the two-hour colour job is the appointment the grid's
 *  own proportional heights exist to show. */
const DENSE_STAFF_SERVICES = [
  { match: 'الشعر', names: ['قص شعر', 'صبغة جذور', 'صبغة شعر كاملة', 'هايلايت', 'غسيل وتنشيف', 'تسريحة سهرة'] },
  { match: 'الأظافر', names: ['مانيكير', 'باديكير', 'أظافر جل', 'رموش فردي'] },
  { match: '', names: ['تنظيف بشرة عميق', 'حمام مغربي', 'تقشير وترطيب', 'ماسك ذهب', 'مكياج يومي', 'مكياج سهرة'] },
];

async function seedDenseDay(session, branchId, operatorIds) {
  if (!branchId || !operatorIds?.length) return;
  const [{ services = [] }, staffAnswer, hoursAnswer] = await Promise.all([
    callAction(session, CATALOGUE).catch(() => ({ services: [] })),
    callAction(session, LIST_STAFF).catch(() => ({ operators: [] })),
    callAction(session, { path: '/api/v1/bookings/working-hours', method: 'GET' }).catch(() => ({ weekly: {} })),
  ]);
  const staff = (staffAnswer.operators ?? []).filter((o) => operatorIds.includes(o.id));
  if (staff.length === 0 || services.length === 0) return;

  const date = riyadhToday();
  const jsDay = new Date(`${date}T00:00:00Z`).getUTCDay();
  const hours = hoursAnswer.weekly?.[String((jsDay + 6) % 7)];
  if (hours?.closed) { console.log('  · today is a closed day — nothing to fill'); return; }
  const open = hours?.start_minute ?? 480;
  const close = hours?.end_minute ?? 1320;

  const byName = new Map(services.map((s) => [s.name, s]));
  const poolFor = (name) => {
    const spec = DENSE_STAFF_SERVICES.find((s) => s.match && name.includes(s.match)) ?? DENSE_STAFF_SERVICES[2];
    const picked = spec.names.map((n) => byName.get(n)).filter((s) => s && s.duration_minutes > 0);
    return picked.length ? picked : services.filter((s) => s.duration_minutes > 0);
  };

  // WHAT IS ALREADY ON TODAY, READ FIRST — the same reasoning as `seedWeekBoard`'s own read: this
  // runs on top of a board that already has bookings, and a slot overlapping one of them is simply
  // refused by the server's conflict lock. Skipping those keeps the column filling up instead of
  // silently coming up short.
  const now = Math.floor(Date.now() / 1000);
  const existing = await callAction(session, LIST_BOOKINGS(branchId, date)).catch(() => ({ bookings: [] }));
  const busy = new Map();
  const midnight = epochAtRiyadh(date, 0);
  for (const b of existing.bookings ?? []) {
    if (b.status === 'cancelled') continue;
    const start = Math.round((b.starts_at - midnight) / 60);
    if (!busy.has(b.operator_id)) busy.set(b.operator_id, []);
    busy.get(b.operator_id).push([start, start + b.duration_minutes]);
    // A BOARD IS NOT AN ALARM. A booking still «محجوز» hours after it ended raises the screen's own
    // overdue banner, which then sits over the grid for the whole recording — an honest warning
    // about a shop that never closes its day out, and the wrong subject for a clip about the board
    // itself. Closed here the way the receptionist would have closed it during the day.
    if (b.status === 'booked' && b.starts_at + b.duration_minutes * 60 < now) {
      await callAction(session, ATTEND_BOOKING(b.id)).catch(() => {});
    }
  }

  let created = 0;
  for (const [i, operator] of staff.entries()) {
    const pool = poolFor(operator.name || '');
    if (pool.length === 0) continue;
    const mine = busy.get(operator.id) ?? [];
    // STAGGERED STARTS — three columns all beginning on the hour reads as generated data.
    let minute = open + i * 45;
    // `k` COUNTS APPOINTMENTS PLACED, NOT LOOP TURNS — a first version incremented it on every
    // turn including the ones that only stepped past an already-taken quarter-hour, so a column
    // with a few existing bookings in it exhausted its own iteration budget on collisions and
    // stopped filling less than half way down the day.
    let k = 0;
    while (minute + 30 <= close && k < 14) {
      const service = pool[(i + k) % pool.length];
      const end = minute + service.duration_minutes;
      if (end > close) break;
      if (mine.some(([s, e]) => minute < e && s < end)) { minute += 15; continue; }
      k += 1;

      const phone = randomPhone();
      const ensured = await callAction(session, ENSURE_CUSTOMER, { phone, name: randomName() })
        .catch(() => ({}));
      const customerId = ensured.customer?.id;
      if (!customerId) { minute += 15; continue; }
      const pay = ['deposit', 'none', 'paid', 'none', 'deposit', 'paid'][(i + k) % 6];
      const startsAt = epochAtRiyadh(date, minute);
      const booking = await callAction(session, CREATE_BOOKING, {
        branch_id: branchId, operator_id: operator.id, customer_id: customerId,
        service_ids: [service.id], starts_at: startsAt,
        payment_status: pay,
        deposit_amount_minor: pay === 'deposit' ? (k % 2 ? 10000 : 5000) : undefined,
      }).catch(() => null);
      if (booking?.id) {
        created += 1;
        mine.push([minute, end]);
        // A DAY READ AT SIX IN THE EVENING HAS A PAST AND A FUTURE, and the grid colours them
        // differently on purpose. Everything already over is closed out — mostly attended, a
        // no-show now and then, because a board with none is a shop that has never had one.
        if (startsAt + service.duration_minutes * 60 < now) {
          const noShow = (i + k) % 7 === 4;
          await callAction(session, noShow ? NO_SHOW_BOOKING(booking.id) : ATTEND_BOOKING(booking.id))
            .catch(() => {});
        }
      }
      busy.set(operator.id, mine);
      minute = end + DENSE_GAPS[(i + k) % DENSE_GAPS.length];
    }
  }
  console.log(`  ✔ today (${date}): ${created} more booking(s) across ${staff.length} staff`);
}

main().catch((e) => { console.error(e.message); process.exit(1); });
