/**
 * Builds a real affiliate MANAGER with a real team under him, over plain HTTP — the same
 * discipline seed-demo-account.mjs follows for the shop console (never a direct database
 * insert): every account here is minted the exact way a real person gets one, apply() then an
 * admin's own approve(), because AffiliateTeam.tsx («فريقي») only ever renders for
 * `role === 'affiliate_manager'` and only ever lists real rows under his own `parent_id`.
 *
 * WHY THIS CANNOT REUSE seed-demo-account.mjs's OWN SESSION MACHINERY. That file signs into a
 * SHOP (`raje3.session`, `/api/v1/signup/signin`) — a completely different door, a completely
 * different token store, from the marketer's own (`raje3.affiliate.session`,
 * `/api/v1/affiliates/signin` — see api.ts's own header on why the two are separate files at
 * all). This is its own script for the same reason AffiliateTeam.tsx's own header gives for not
 * reusing another screen's component: a different audience, bent to fit, is the failure this
 * avoids.
 *
 * WHY A MANAGER NEEDS AN ADMIN TO EXIST AT ALL, UNLIKE A SHOP'S OWN SIGNUP. onboarding.py's own
 * module docstring: apply() never mints an account by itself — spec §2 requires a platform admin
 * to look at every applicant before anything is usable. So this script signs in as the SAME
 * platform-owner account admin-home-1-overview.mjs's own tour uses (seeded once by
 * deploy/seed/seed-admin.sh, not by this file) and calls the real
 * POST /api/v1/admin/affiliates/{id}/approve route — the exact button an admin would press on
 * the real panel — never a shortcut that skips it.
 *
 * FIXED PHONE NUMBERS, ON PURPOSE — same reasoning as seed-demo-account.mjs's own HERO_PHONE: a
 * tour script's own selectors and captions are built around finding THESE people specifically,
 * and a fixed number is what makes a re-recording of this tour idempotent (sign in if the
 * account already exists, apply+approve only if it doesn't) instead of piling up a fresh manager
 * and a fresh team on every run.
 *
 * NO WAFA REQUEST IS SEEDED HERE, DELIBERATELY. core/wafa.py's own request() refuses below 50
 * active shops — a real threshold this script cannot fake honestly without either a direct
 * database write (the one thing this whole family of scripts refuses to do) or seeding dozens of
 * real referred, paying shops for a single screen's queue section. TeamWafaQueue's own component
 * already renders nothing when the queue is empty (`if (rows.length === 0) return null`) — the
 * same honest-empty-state discipline this product follows everywhere else — so the tour narrates
 * that section from the code and the screen's own words, not from invented rows.
 *
 * Usage:
 *   node media/tours/seed-affiliate-team.mjs
 *   CONSOLE=http://localhost:5174 node media/tours/seed-affiliate-team.mjs
 */
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const SESSION_FILE = join(HERE, '.demo-affiliate-session.json');

const rawBase = process.env.CONSOLE ?? 'http://localhost:5174';
const withSlash = rawBase.endsWith('/') ? rawBase : `${rawBase}/`;
// SAME STRIP AS seed-demo-account.mjs's OWN `API` — the app is served under /app/, every service
// (identity, affiliate) sits at the bare root behind the same gateway.
const API = withSlash.replace(/\/app\/?$/, '').replace(/\/$/, '');

// THE SAME PLATFORM-OWNER ACCOUNT admin-home-1-overview.mjs's TOUR SIGNS INTO — seeded once by
// deploy/seed/seed-admin.sh, a throwaway dev-cluster account with no real establishment on it
// (see that tour's own header note). Reused rather than re-described here so there is exactly
// one place this password is written down.
const ADMIN_PHONE = '0500000902';
const ADMIN_PASSWORD = 'HomeTour2026Demo!';
const PLATFORM_TENANT = '_platform';

const MANAGER = { phone: '0555020202', password: 'Kobo2026$Mgr!', name: 'ريم — مديرة التسويق' };
// TWO PROMOTERS, NOT ONE — a roster of one row cannot show what «أرباح فريقك» actually sums
// (Team.tsx's own note: it always renders a total across every member, plural by nature), and a
// tour narrating "أعضاء فريقك" over a single row reads as an edge case rather than the normal
// shape of the screen.
const PROMOTERS = [
  { phone: '0555020203', password: 'Kobo2026$Prm1!', name: 'سلطان — مسوّق' },
  { phone: '0555020204', password: 'Kobo2026$Prm2!', name: 'هند — مسوّقة' },
];

async function req(path, method, body, token) {
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${API}${path}`, {
    method, headers, body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  const text = await res.text();
  let parsed = null;
  try { parsed = text ? JSON.parse(text) : null; } catch { /* non-JSON error body */ }
  if (!res.ok || parsed?.ok === false) {
    const message = parsed?.message ?? parsed?.detail ?? `${method} ${path} → ${res.status}`;
    throw new Error(`${message}${parsed?.reason ? ` (${parsed.reason})` : ''}`);
  }
  return parsed;
}

async function adminSignIn() {
  const out = await req('/api/v1/auth/tenant', 'POST',
    { tenant: PLATFORM_TENANT, username: ADMIN_PHONE, password: ADMIN_PASSWORD });
  if (!out?.access_token) throw new Error('admin sign-in answered with no access_token');
  return out.access_token;
}

async function affiliateSignIn(phone, password) {
  return req('/api/v1/affiliates/signin', 'POST', { phone, password });
}

/** Reuses an existing account when the fixed phone already signs in; otherwise applies and has
 *  the admin approve it — the real two-step path onboarding.py's own module docstring describes,
 *  never a shortcut that mints the row directly. */
async function ensureAffiliate(adminToken, { phone, password, name, referralCode = '' }) {
  try {
    const session = await affiliateSignIn(phone, password);
    console.log(`  · ${name} — already active, signed in`);
    return session;
  } catch {
    // No live account yet — fall through to apply()+approve() below.
  }

  let applicationId;
  try {
    const applied = await req('/api/v1/affiliates/apply', 'POST', {
      phone, name, password, referral_code: referralCode, agreed: true,
    });
    applicationId = applied.application_id;
  } catch (e) {
    // ALREADY PENDING FROM A PRIOR RUN THAT DIED BETWEEN apply() AND approve() — found by its
    // own name in the admin's queue rather than re-applying, which onboarding.py's own apply()
    // correctly refuses ("طلبك السابق ما زال قيد المراجعة").
    if (!/قيد المراجعة|already_pending/.test(e.message)) throw e;
    const pending = await req('/api/v1/admin/affiliates', 'GET', undefined, adminToken);
    applicationId = pending.applications?.find((a) => a.name === name)?.id;
    if (!applicationId) throw new Error(`"${name}" is pending but not found in the admin queue`);
  }

  await req(`/api/v1/admin/affiliates/${applicationId}/approve`, 'POST', undefined, adminToken);
  console.log(`  ✔ ${name} — applied and approved`);
  return affiliateSignIn(phone, password);
}

async function main() {
  console.log(`▸ signing in as the platform admin (${ADMIN_PHONE})`);
  const adminToken = await adminSignIn();

  console.log(`▸ ${MANAGER.name}`);
  const managerSession = await ensureAffiliate(adminToken, MANAGER);
  writeFileSync(SESSION_FILE, JSON.stringify({
    access_token: managerSession.access_token, refresh_token: managerSession.refresh_token,
    tenant: managerSession.tenant,
  }, null, 2), 'utf8');
  console.log(`  session saved to ${SESSION_FILE}`);

  // THE MANAGER'S OWN id IS HIS REFERRAL CODE (api.ts's own note on `me()`) — resolved fresh
  // every run rather than assumed, since a re-seed against a fresh cluster mints a new one.
  const me = await req('/api/v1/affiliates/me', 'GET', undefined, managerSession.access_token);
  console.log(`  referral code (his own affiliate id): ${me.id}`);

  console.log(`▸ ${PROMOTERS.length} team members under him`);
  for (const promoter of PROMOTERS) {
    await ensureAffiliate(adminToken, { ...promoter, referralCode: me.id });
  }

  console.log('✔ affiliate manager + team ready — manager phone/password:');
  console.log(`    ${MANAGER.phone} / ${MANAGER.password}`);
}

main().catch((e) => { console.error(e.message); process.exit(1); });
