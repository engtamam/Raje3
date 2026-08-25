/**
 * Mints ONE approved affiliate (manager role, no referrer) so affiliate-earnings-1-overview.mjs
 * (and any later affiliate tour) has a real account to sign into — the same "every write goes
 * through the real API" discipline seed-demo-account.mjs already follows for the shop side, just
 * a much shorter path: apply() → admin approve() → signin(), three real round trips.
 *
 * WHY THIS NEEDS THE ADMIN DOOR TOO, UNLIKE THE SHOP SEEDER. A shop's signup activates itself
 * instantly; an affiliate's apply() only ever creates a PENDING row (onboarding.py's own
 * `apply()`) — nobody can sign in until a platform operator approves it. There is no seed-side
 * shortcut around that gate (a direct DB write would skip identity's own membership minting,
 * producing an account that looks approved but cannot authenticate), so this signs into the
 * admin panel with the same throwaway operator account admin-home-1-overview.mjs already uses
 * (0500000902 / HomeTour2026Demo! — a dev-cluster-only account, not a secret) and calls the same
 * `/api/v1/admin/affiliates/{id}/approve` route a real operator's click would hit.
 *
 * IDEMPOTENT ON RE-RUN. apply() itself refuses a second application for the same phone while one
 * is pending, and refuses outright once the phone already has an affiliate account — both are
 * treated as success here (the credentials file is what matters, and it's already right), never
 * a fatal error that would force a new phone number on every re-run.
 *
 * Usage:
 *   node media/tours/seed-demo-affiliate.mjs
 *   CONSOLE=http://localhost:5174 node media/tours/seed-demo-affiliate.mjs
 */
import { writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const CREDENTIALS_FILE = join(HERE, '.demo-affiliate-credentials.json');

const rawBase = process.env.CONSOLE ?? 'http://localhost:5174';
const withSlash = rawBase.endsWith('/') ? rawBase : `${rawBase}/`;
const API = withSlash.replace(/\/app\/?$/, '').replace(/\/$/, '');

// A FIXED, RECOGNIZABLE NUMBER — never random like the shop seeder's signup phone, on purpose:
// this account is meant to be reused run after run (re-recording a tour, adding a second
// affiliate clip later) without a fresh admin approval each time.
const PHONE = '0549900110';
const PASSWORD = 'Raje3-Affiliate-Tour!1';
const NAME = 'مسوّق العرض';

const ADMIN_PHONE = '0500000902';
const ADMIN_PASSWORD = 'HomeTour2026Demo!';

async function call(path, body) {
  const res = await fetch(`${API}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const text = await res.text();
  let parsed = null;
  try { parsed = text ? JSON.parse(text) : null; } catch { /* non-JSON error page */ }
  return { status: res.status, ok: res.ok, body: parsed };
}

async function main() {
  console.log(`seeding demo affiliate against ${API}`);

  // ── apply (idempotent: already-pending / already-affiliate both read as "keep going") ──────
  const applied = await call('/api/v1/affiliates/apply', {
    phone: PHONE, name: NAME, password: PASSWORD, agreed: true,
  });
  const reason = applied.body?.reason;
  if (!applied.ok && reason !== 'already_pending' && reason !== 'already_affiliate') {
    throw new Error(`apply() refused: ${applied.status} ${JSON.stringify(applied.body)}`);
  }
  console.log(applied.ok ? '✔ application submitted' : `application already exists (${reason})`);

  if (reason !== 'already_affiliate') {
    // ── sign into the admin panel with the platform-owner throwaway account ───────────────────
    const adminAuth = await call('/api/v1/auth/tenant', {
      tenant: '_platform', username: ADMIN_PHONE, password: ADMIN_PASSWORD,
    });
    if (!adminAuth.ok || !adminAuth.body?.access_token) {
      throw new Error(`admin sign-in refused: ${adminAuth.status} ${JSON.stringify(adminAuth.body)}`);
    }
    const adminToken = adminAuth.body.access_token;

    // ── find the pending application by phone, approve it ────────────────────────────────────
    const listRes = await fetch(`${API}/api/v1/admin/affiliates`, {
      headers: { Authorization: `Bearer ${adminToken}` },
    });
    const applications = await listRes.json();
    const rows = Array.isArray(applications) ? applications
      : Array.isArray(applications?.applications) ? applications.applications : [];
    const mine = rows.find((a) => a.phone === PHONE || a.phone === `+966${PHONE.slice(1)}`);
    if (!mine) throw new Error(`no pending application found for ${PHONE} — listed ${rows.length}`);

    const approveRes = await fetch(`${API}/api/v1/admin/affiliates/${mine.id}/approve`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${adminToken}` },
    });
    const approveBody = await approveRes.json().catch(() => null);
    if (!approveRes.ok) {
      throw new Error(`approve() refused: ${approveRes.status} ${JSON.stringify(approveBody)}`);
    }
    console.log(`✔ application approved — affiliate_id=${approveBody?.affiliate_id ?? '(already)'}`);
  }

  // ── confirm sign-in actually works before writing credentials down ─────────────────────────
  const signedIn = await call('/api/v1/affiliates/signin', { phone: PHONE, password: PASSWORD });
  if (!signedIn.ok || !signedIn.body?.access_token) {
    throw new Error(`sign-in check failed: ${signedIn.status} ${JSON.stringify(signedIn.body)}`);
  }

  writeFileSync(CREDENTIALS_FILE, JSON.stringify({ phone: PHONE, password: PASSWORD }, null, 2), 'utf8');
  console.log(`✔ demo affiliate ready — credentials saved to ${CREDENTIALS_FILE}`);
}

main().catch((err) => { console.error(err.message || err); process.exit(1); });
