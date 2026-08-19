/**
 * WHO IS USING THE AFFILIATE PORTAL — a SEPARATE store from session.ts (a different key, a
 * different shape), for the same reason api.ts is a separate file: a marketer is not a shop.
 */
import { useCallback, useState } from 'react';
import type { AffiliateSession } from './api';

export const KEY = 'raje3.affiliate.session';

export const ANONYMOUS: AffiliateSession = { access_token: '' };

function read(): AffiliateSession {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) || 'null') as Partial<AffiliateSession> | null;
    if (!raw?.access_token) return ANONYMOUS;
    return { access_token: String(raw.access_token), refresh_token: raw.refresh_token,
             tenant: raw.tenant };
  } catch {
    return ANONYMOUS;
  }
}

export function isSignedIn(s: AffiliateSession): boolean {
  return Boolean(s.access_token);
}

export function useAffiliateSession() {
  const [session, setSession] = useState<AffiliateSession>(read);

  const signIn = useCallback((s: AffiliateSession) => {
    localStorage.setItem(KEY, JSON.stringify(s));
    setSession(s);
  }, []);

  const signOut = useCallback(() => {
    localStorage.removeItem(KEY);
    setSession(ANONYMOUS);
  }, []);

  return { session, signedIn: isSignedIn(session), signIn, signOut };
}
