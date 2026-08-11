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
