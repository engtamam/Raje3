/**
 * Renewing the admin panel's bearer token — same fix as `../affiliates/renew.ts`, ported for the
 * same reason: this door keeps its own storage key and its own event names, so the three sessions
 * (shop, affiliate, admin) never cross-trigger each other's re-render. See that file for the full
 * reasoning (early-renewal window, shared in-flight promise, why a network failure is not a
 * sign-out) — this file only differs in which key/events it owns.
 *
 * CROSS-TAB LOCK, SAME FIX AS `../renew.ts` (2026-09-16, found live on the shop console, ported
 * here for the identical reason): the in-flight promise below only ever covered one tab's own JS
 * memory. Two tabs of the same signed-in admin session share the same stored tokens and hit the
 * same expiry at the same moment; each fires `/auth/refresh` with the same refresh token, and
 * identity-service's rotation treats that concurrent reuse as theft — it revokes the WHOLE
 * session, not just the loser. `navigator.locks` serializes every tab of this origin through the
 * same named lock, and the winner of the wait re-reads storage before ever touching the network.
 */
import { KEY } from './session';
import type { AdminSession } from './api';

const BASE = (import.meta.env.VITE_ADMIN_API_BASE ?? '').replace(/\/$/, '');

export const ADMIN_SESSION_RENEWED = 'raje3:admin-session-renewed';
export const ADMIN_SESSION_EXPIRED = 'raje3:admin-session-expired';

export function announceExpiry(): void {
  window.dispatchEvent(new Event(ADMIN_SESSION_EXPIRED));
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

function stored(): AdminSession | null {
  try {
    return JSON.parse(localStorage.getItem(KEY) || 'null') as AdminSession | null;
  } catch {
    return null;
  }
}

const LOCK_NAME = 'raje3-admin-token-refresh';

/** Trade the refresh token for a new bearer. Returns '' when renewal is impossible or refused. */
export function renew(): Promise<string> {
  if (inFlight) return inFlight;

  inFlight = (async () => {
    try {
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
  const s = stored();
  if (!s?.refresh_token) return '';
  if (s.access_token) {
    const left = expiresAt(s.access_token) - Math.floor(Date.now() / 1000);
    if (left > EARLY_SECONDS) return s.access_token;
  }
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
    const next: AdminSession = {
      ...s, access_token: token, refresh_token: body.refresh_token || s.refresh_token,
    };
    localStorage.setItem(KEY, JSON.stringify(next));
    window.dispatchEvent(new Event(ADMIN_SESSION_RENEWED));
    return token;
  } catch {
    return '';
  }
}
