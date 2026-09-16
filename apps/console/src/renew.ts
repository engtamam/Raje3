/**
 * Renewing the bearer token, once, for everybody.
 *
 * THE BUG THIS FILE EXISTS FOR. The access token lives 900 seconds. That is a deliberate choice and
 * a good one — a stolen bearer is worth fifteen minutes — and the server mints a refresh token
 * beside it that is good for 31 days precisely so the short life costs the owner nothing. We stored
 * only the first. So «مدة الجلسة 31 يوماً» described a token nobody kept, and the owner was thrown
 * out to the login screen a quarter of an hour after signing in, mid-visit, at the counter.
 *
 * ONE RENEWAL AT A TIME — ACROSS TABS, NOT JUST WITHIN ONE. A screen fires several requests
 * together; they can all meet the 401 at the same moment. Renewing per request would spend the
 * refresh token several times over and — because the server ROTATES it on use, and REVOKES THE
 * WHOLE SESSION FAMILY the instant two callers present the same token concurrently
 * (identity-service's `AuthService.refresh`, the CAS on `consume(jti)` — its own comment names
 * this "indistinguishable from theft") — the later attempts would not just fail, they would sign
 * the account out entirely. The module-level `inFlight` promise below only ever covered ONE TAB's
 * own JS memory. Two tabs of the SAME signed-in session (an owner with two tabs open — ordinary
 * real usage, not a test artifact) share the identical stored tokens and hit the same 15-minute
 * expiry at the same wall-clock moment; each tab's own `inFlight` is `null` to the OTHER tab, so
 * both fire `/auth/refresh` with the same refresh token — exactly the race the server treats as
 * theft, and BOTH tabs get logged out (found live: reproduced with no dev-server restarts, no
 * Playwright, nothing but the product's own real, ordinary two-tabs-open usage).
 * `navigator.locks` closes this for real: every tab asks for the SAME named lock before renewing,
 * so only one tab's callback ever runs at a time across the whole browser — and the one that
 * waited RE-READS storage once it gets the lock, in case the tab ahead of it already rotated the
 * token, so it never even attempts to spend an already-consumed one.
 *
 * IT WRITES BACK TO STORAGE, NOT TO REACT. The session hook re-reads storage on the event this
 * fires, so the new token reaches every screen without any of them knowing renewal exists. That
 * matters because the retry happens inside a request already in flight, below the components.
 */
import { KEY, type Session } from './session';

const BASE = (import.meta.env.VITE_API_BASE ?? '').replace(/\/$/, '');

/** Fires after a successful renewal so `useSession` re-reads what we just wrote. */
export const SESSION_RENEWED = 'raje3:session-renewed';

let inFlight: Promise<string> | null = null;

/**
 * HOW LONG BEFORE EXPIRY WE STOP TRUSTING A TOKEN.
 *
 * Sixty seconds covers a slow connection and a clock that disagrees with the server's by a little,
 * which is the ordinary case on a phone that has been asleep in a pocket.
 */
const EARLY_SECONDS = 60;

/**
 * When this token stops being accepted, read from the token itself.
 *
 * NO EXTRA FIELD AND NO SEPARATE CLOCK. `exp` is already inside every JWT the platform mints, and
 * storing our own copy beside it would be a second number to keep in step — which is how a session
 * comes to believe it is valid for longer than the server does.
 *
 * A token we cannot parse returns 0, which reads as "expired" and simply falls back to the old
 * behaviour: fire, get a 401, renew, retry. Never the other way round.
 */
function expiresAt(token: string): number {
  try {
    const part = token.split('.')[1];
    if (!part) return 0;
    const json = atob(part.replace(/-/g, '+').replace(/_/g, '/'));
    return Number((JSON.parse(json) as { exp?: number }).exp || 0);
  } catch {
    return 0;
  }
}

/**
 * The token to send RIGHT NOW — renewed first if it is about to die.
 *
 * WHY THIS EXISTS AT ALL, GIVEN THE 401 PATH ALREADY WORKS. It works, and it is loud: the browser
 * prints every 401 in red whatever we catch, because it is the network's answer and not an
 * exception of ours. An owner reading his console sees what looks like a broken product every
 * fifteen minutes — and a real failure hides among them.
 *
 * It also costs a round trip. Every fifteen minutes, the first action a person takes goes out,
 * comes back refused, renews, and goes out again — at the counter, with a customer waiting.
 */
export async function fresh(token: string): Promise<string> {
  if (!token) return token;
  const exp = expiresAt(token);
  if (!exp) return token;
  const left = exp - Math.floor(Date.now() / 1000);
  if (left > EARLY_SECONDS) return token;
  // SHARED WITH THE 401 PATH. `renew()` holds one in-flight promise for the whole app, so several
  // screens arriving here together spend the refresh token once rather than racing each other into
  // a real sign-out.
  return (await renew()) || token;
}

function stored(): Session | null {
  try {
    return JSON.parse(localStorage.getItem(KEY) || 'null') as Session | null;
  } catch {
    return null;
  }
}

/**
 * Trade the refresh token for a new bearer.
 *
 * Returns the new access token, or an empty string when renewal is impossible or refused — which
 * is the caller's signal that the session is genuinely over and expiry may now be announced.
 */
const LOCK_NAME = 'raje3-token-refresh';

export function renew(): Promise<string> {
  if (inFlight) return inFlight;

  inFlight = (async () => {
    try {
      // CROSS-TAB MUTEX — every tab of this same origin asks for the SAME named lock before
      // touching the network, so only one tab's callback runs at a time across the whole browser.
      // `navigator.locks` degrades gracefully (plain call, no lock) on the one engine that lacks
      // it (Safari < 15.4) — the per-tab guard above still holds there, same risk this file
      // always had, just not closed on that one browser yet.
      if (typeof navigator !== 'undefined' && 'locks' in navigator) {
        return await navigator.locks.request(LOCK_NAME, doRenew);
      }
      return await doRenew();
    } finally {
      inFlight = null;
    }
  })();

  return inFlight;
}

async function doRenew(): Promise<string> {
  // RE-READ STORAGE NOW THAT WE HOLD THE LOCK — a tab ahead of us in the queue may already have
  // rotated the token while we waited; presenting that ALREADY-CONSUMED refresh token ourselves
  // is exactly the replay the server treats as theft (revokes the WHOLE session, not just refuses
  // us). If storage already carries a bearer that is not about to expire, another tab did the
  // work for us — hand it back with no network call at all.
  const s = stored();
  if (!s?.refresh) return '';
  if (s.token) {
    const left = expiresAt(s.token) - Math.floor(Date.now() / 1000);
    if (left > EARLY_SECONDS) return s.token;
  }
  try {
    const res = await fetch(`${BASE}/api/v1/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: s.refresh }),
    });
    if (!res.ok) return '';
    const body = (await res.json()) as { access_token?: string; refresh_token?: string };
    const token = body.access_token || '';
    if (!token) return '';
    // THE NEW REFRESH TOKEN REPLACES THE OLD ONE when the server rotates it, and the old one is
    // dead the moment it is spent. Keeping the previous value would work exactly once more.
    const next: Session = { ...s, token, refresh: body.refresh_token || s.refresh };
    localStorage.setItem(KEY, JSON.stringify(next));
    window.dispatchEvent(new Event(SESSION_RENEWED));
    return token;
  } catch {
    // A NETWORK FAILURE IS NOT AN EXPIRY. Returning '' here would sign him out because his phone
    // lost signal for a second, so the caller treats it as "could not renew now" and the next
    // request tries again.
    return '';
  }
}
