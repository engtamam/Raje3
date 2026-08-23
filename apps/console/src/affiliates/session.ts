/**
 * WHO IS USING THE AFFILIATE PORTAL — a SEPARATE store from session.ts (a different key, a
 * different shape), for the same reason api.ts is a separate file: a marketer is not a shop.
 */
import { useCallback, useEffect, useState } from 'react';
import type { AffiliateSession } from './api';
import { AFFILIATE_SESSION_EXPIRED, AFFILIATE_SESSION_RENEWED } from './renew';

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

  // renew.ts writes the fresh token straight to storage, below any component — this is how that
  // reaches whoever's holding `session` in state, the same pattern `../session.ts` already uses.
  useEffect(() => {
    const onRenewed = () => setSession(read());
    window.addEventListener(AFFILIATE_SESSION_RENEWED, onRenewed);
    return () => window.removeEventListener(AFFILIATE_SESSION_RENEWED, onRenewed);
  }, []);

  // A CLEAN SIGN-OUT, NOT A SCREEN FULL OF 401s. Fired from api.ts only after renewal itself has
  // been tried and failed — a real end, not a screen that raced ahead of a fresh bearer.
  useEffect(() => {
    const onExpired = () => {
      localStorage.removeItem(KEY);
      setSession(ANONYMOUS);
    };
    window.addEventListener(AFFILIATE_SESSION_EXPIRED, onExpired);
    return () => window.removeEventListener(AFFILIATE_SESSION_EXPIRED, onExpired);
  }, []);

  return { session, signedIn: isSignedIn(session), signIn, signOut };
}
