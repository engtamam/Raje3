/**
 * Renewing the bearer token, once, for everybody.
 *
 * THE BUG THIS FILE EXISTS FOR. The access token lives 900 seconds. That is a deliberate choice and
 * a good one — a stolen bearer is worth fifteen minutes — and the server mints a refresh token
 * beside it that is good for 31 days precisely so the short life costs the owner nothing. We stored
 * only the first. So «مدة الجلسة 31 يوماً» described a token nobody kept, and the owner was thrown
 * out to the login screen a quarter of an hour after signing in, mid-visit, at the counter.
 *
 * ONE RENEWAL AT A TIME. A screen fires several requests together; they can all meet the 401 at the
 * same moment. Renewing per request would spend the refresh token several times over and — because
 * the server rotates it on use — the later attempts would present one already replaced and be
 * refused, turning a recoverable expiry into a real sign-out. So the in-flight promise is shared:
 * whoever asks second waits on the first one's answer.
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
export function renew(): Promise<string> {
  if (inFlight) return inFlight;

  const s = stored();
  if (!s?.refresh) return Promise.resolve('');

  inFlight = (async () => {
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
    } finally {
      inFlight = null;
    }
  })();

  return inFlight;
}
