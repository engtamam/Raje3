/**
 * The demo shop's session, kept alive — one place, for the seeder and the recorder both.
 *
 * WHY THIS EXISTS. The saved access token lives fifteen minutes. The console app renews itself
 * from the refresh token beside it, and for a long time that was enough for both of these scripts
 * too: open the app, let it renew, write the rotated session back.
 *
 * Then the renewal path itself failed — identity's own `/auth/refresh` stopped answering (every
 * call hung past the gateway's own upstream timeout, while an ordinary sign-in came back in under
 * a second). That turned an expired token into a LOST ACCOUNT: a demo shop's signup phone is
 * generated at random inside `openShop()` and was never written down, so there was no second way
 * in — a thousand real customers and months of real visits, unreachable, over a token that had
 * quietly aged out fifteen minutes after it was minted.
 *
 * So the shop's own login is saved at signup (`.demo-credentials.json`, gitignored beside the
 * session for the same reason), and a session is MINTED FRESH whenever the saved one is spent —
 * the same `/api/v1/signup/signin` the door itself calls, never a second auth path of our own.
 * Refresh is not replaced by this and does not need to be: this simply never depends on it.
 */
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
export const SESSION_FILE = join(HERE, '..', '.demo-session.json');
export const CREDENTIALS_FILE = join(HERE, '..', '.demo-credentials.json');

/** Seconds of remaining life below which a token is treated as already spent — the same sixty
 *  seconds apps/console/src/renew.ts uses, for the same reason: a slow call must not start on a
 *  token that dies mid-flight. */
const EARLY_SECONDS = 60;

function expiresAt(token) {
  try {
    const part = String(token).split('.')[1];
    return part ? Number(JSON.parse(Buffer.from(part, 'base64url').toString('utf8')).exp || 0) : 0;
  } catch {
    return 0;
  }
}

export function readDemoSession() {
  if (!existsSync(SESSION_FILE)) return null;
  return JSON.parse(readFileSync(SESSION_FILE, 'utf8'));
}

export function readDemoCredentials() {
  if (!existsSync(CREDENTIALS_FILE)) return null;
  return JSON.parse(readFileSync(CREDENTIALS_FILE, 'utf8'));
}

export function saveDemoCredentials(phone, password) {
  writeFileSync(CREDENTIALS_FILE, JSON.stringify({ phone, password }, null, 2), 'utf8');
}

export function saveDemoSession(session) {
  writeFileSync(SESSION_FILE, JSON.stringify(session, null, 2), 'utf8');
}

/**
 * The saved session, guaranteed usable right now — re-minted from the saved login when its token
 * is spent (or about to be), and written back so the next caller starts from the live one.
 *
 * `apiBase` is the API root the caller already resolved (the tunnel, a local gateway) — this
 * module never guesses one of its own.
 *
 * A session that is still good is returned untouched: no needless sign-in, no needless write.
 * A session with no credentials beside it is returned as-is too rather than thrown over — an old
 * account predating this file still records fine while its token is alive, and the caller's own
 * failure will say what actually went wrong if it isn't.
 */
export async function ensureFreshDemoSession(apiBase) {
  const session = readDemoSession();
  if (!session) return null;
  const left = expiresAt(session.token) - Math.floor(Date.now() / 1000);
  if (left > EARLY_SECONDS) return session;

  const creds = readDemoCredentials();
  if (!creds?.phone || !creds?.password) return session;

  const res = await fetch(`${apiBase}/api/v1/signup/signin`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ phone: creds.phone, password: creds.password, code: '' }),
  });
  if (!res.ok) {
    throw new Error(`demo session expired and re-minting it failed: signin → ${res.status} ${(await res.text()).slice(0, 200)}`);
  }
  const minted = await res.json();
  if (!minted.access_token) throw new Error('demo signin answered 200 with no access_token');
  const next = {
    ...session,
    tenant: minted.tenant || session.tenant,
    token: minted.access_token,
    refresh: minted.refresh_token || session.refresh,
  };
  saveDemoSession(next);
  return next;
}
