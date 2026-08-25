/**
 * Builds the ONE affiliate account «عملائي المحتملين» needs — nothing more, because there is
 * nothing more to honestly give it. A `Lead` row is created in exactly one place on this whole
 * platform: `core/lead_sourcing.py`'s search job, which calls the REAL Google Places API with a
 * manager's own BYOK key (`core/leads.py`'s own module docstring). No deploy of this platform —
 * checked directly against `affiliate-service-secrets` and the deployment's own env — carries a
 * real key or a platform-wide fallback, and this script will not fabricate a Google account or a
 * direct database insert to manufacture one (the same discipline seed-demo-account.mjs's own
 * header states: every write here goes through the real API, never a shortcut that produces data
 * the product itself could never have produced). So this account is seeded exactly like
 * seed-affiliate-tools.mjs's own manager — apply() then the platform-owner admin's approve(),
 * nothing else — and the tour recorded against it narrates the list and detail screens' real
 * mechanics over a REAL, honest zero, the same discipline affiliate-home-1-overview.mjs already
 * set for this portal's empty states.
 *
 * IDEMPOTENT ON RE-RUN — signs in first with the fixed phone, only falls through to
 * apply()/approve() when that doesn't already work.
 *
 * Usage:
 *   node media/tours/seed-affiliate-leads.mjs
 *   CONSOLE=http://localhost:5174 node media/tours/seed-affiliate-leads.mjs
 */
import { writeFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const SESSION_FILE = join(HERE, '.demo-affiliate-leads-session.json');

const rawBase = process.env.CONSOLE ?? 'http://localhost:5174';
const withSlash = rawBase.endsWith('/') ? rawBase : `${rawBase}/`;
const API = withSlash.replace(/\/app\/?$/, '').replace(/\/$/, '');

// SAME PLATFORM-OWNER ACCOUNT EVERY OTHER SEEDER IN THIS FAMILY USES — seeded once by
// deploy/seed/seed-admin.sh, not by this file.
const ADMIN_PHONE = '0500000902';
const ADMIN_PASSWORD = 'HomeTour2026Demo!';
const PLATFORM_TENANT = '_platform';

export const PROMOTER = { phone: '0502223334', password: 'LeadsTour2026Demo!', name: 'خالد — مسوّق قوائم العملاء' };

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

async function ensureAffiliate(adminToken, { phone, password, name }) {
  try {
    const session = await affiliateSignIn(phone, password);
    console.log(`  · ${name} — already active, signed in`);
    return session;
  } catch { /* falls through to apply()+approve() below */ }

  let applicationId;
  try {
    const applied = await req('/api/v1/affiliates/apply', 'POST', { phone, name, password, agreed: true });
    applicationId = applied.application_id;
  } catch (e) {
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

  console.log(`▸ ${PROMOTER.name}`);
  const session = await ensureAffiliate(adminToken, PROMOTER);
  writeFileSync(SESSION_FILE, JSON.stringify({
    access_token: session.access_token, refresh_token: session.refresh_token, tenant: session.tenant,
  }, null, 2), 'utf8');

  console.log('✔ affiliate leads demo account ready — no lead can honestly be seeded onto it (see');
  console.log('  this file\'s own header: real leads only come from a real Google Places search, and');
  console.log('  no deploy of this platform carries a working key). phone/password:');
  console.log(`    ${PROMOTER.phone} / ${PROMOTER.password}`);
}

main().catch((e) => { console.error(e.message); process.exit(1); });
