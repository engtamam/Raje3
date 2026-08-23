/**
 * Renewing the affiliate portal's bearer token — the exact same fix `../renew.ts` already made
 * for the shop console, ported here because the two doors keep separate stores (session.ts's own
 * header note) and this one never got it: `sign_in()` (services/affiliate-service/app/core/
 * onboarding.py) returns identity's token pair VERBATIM — the same short-lived access token and
 * 31-day refresh token every other door gets, refreshable at the same shared `/api/v1/auth/refresh`
 * (routed at the gateway with `auth: none`, same as the shop's). `api.ts`'s `req()` never renewed
 * and never retried a 401, so a marketer using the portal for more than fifteen minutes hit a wall
 * of 401s and had to sign out and back in — while a shop owner, behind `../renew.ts`, never did.
 *
 * See `../renew.ts` for the full reasoning (early-renewal window, shared in-flight promise, why a
 * network failure is not a sign-out); this file only differs in which storage key and event name
 * it owns, since the two sessions must never cross-trigger each other's re-render.
 */
import { KEY } from './session';
import type { AffiliateSession } from './api';

const BASE = (import.meta.env.VITE_AFFILIATE_API_BASE ?? '').replace(/\/$/, '');

export const AFFILIATE_SESSION_RENEWED = 'raje3:affiliate-session-renewed';

/** The affiliate portal's own `SESSION_EXPIRED` (`../expired.ts`) — a marketer whose refresh
 *  token is ALSO dead (not just the 15-minute bearer) gets a real, deliberate sign-out instead
 *  of being left half-signed-in, staring at a screen that 401s on everything with no explanation.
 *  Fired only after `req()` has tried renewal and it genuinely failed — never on a bare 401 that
 *  renewal might still fix. */
export const AFFILIATE_SESSION_EXPIRED = 'raje3:affiliate-session-expired';

export function announceExpiry(): void {
  window.dispatchEvent(new Event(AFFILIATE_SESSION_EXPIRED));
}

let inFlight: Promise<string> | null = null;

const EARLY_SECONDS = 60;

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

/** The token to send RIGHT NOW — renewed first if it is about to die. */
export async function fresh(token: string): Promise<string> {
  if (!token) return token;
  const exp = expiresAt(token);
  if (!exp) return token;
  const left = exp - Math.floor(Date.now() / 1000);
  if (left > EARLY_SECONDS) return token;
  return (await renew()) || token;
}

function stored(): AffiliateSession | null {
  try {
    return JSON.parse(localStorage.getItem(KEY) || 'null') as AffiliateSession | null;
  } catch {
    return null;
  }
}

/** Trade the refresh token for a new bearer. Returns '' when renewal is impossible or refused. */
export function renew(): Promise<string> {
  if (inFlight) return inFlight;

  const s = stored();
  if (!s?.refresh_token) return Promise.resolve('');

  inFlight = (async () => {
    try {
      const res = await fetch(`${BASE}/api/v1/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: s.refresh_token }),
      });
      if (!res.ok) return '';
      const body = (await res.json()) as { access_token?: string; refresh_token?: string };
      const token = body.access_token || '';
      if (!token) return '';
      const next: AffiliateSession = {
        ...s, access_token: token, refresh_token: body.refresh_token || s.refresh_token,
      };
      localStorage.setItem(KEY, JSON.stringify(next));
      window.dispatchEvent(new Event(AFFILIATE_SESSION_RENEWED));
      return token;
    } catch {
      return '';
    } finally {
      inFlight = null;
    }
  })();

  return inFlight;
}
