/**
 * WHO IS USING THE ADMIN PANEL — a SEPARATE store from `../session.ts` and from
 * `../affiliates/session.ts` (a different key, a different shape): a platform operator is
 * neither a shop nor a marketer. Same pattern as the affiliate portal's own session.ts — see its
 * header note for the full reasoning on why each door keeps its own store.
 */
import { useCallback, useEffect, useState } from 'react';
import type { AdminSession } from './api';
import { ADMIN_SESSION_EXPIRED, ADMIN_SESSION_RENEWED } from './renew';

export const KEY = 'raje3.admin.session';

export const ANONYMOUS: AdminSession = { access_token: '' };

function read(): AdminSession {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) || 'null') as Partial<AdminSession> | null;
    if (!raw?.access_token) return ANONYMOUS;
    return { access_token: String(raw.access_token), refresh_token: raw.refresh_token };
  } catch {
    return ANONYMOUS;
  }
}

export function isSignedIn(s: AdminSession): boolean {
  return Boolean(s.access_token);
}

export function useAdminSession() {
  const [session, setSession] = useState<AdminSession>(read);

  const signIn = useCallback((s: AdminSession) => {
    localStorage.setItem(KEY, JSON.stringify(s));
    setSession(s);
  }, []);

  const signOut = useCallback(() => {
    localStorage.removeItem(KEY);
    setSession(ANONYMOUS);
  }, []);

  useEffect(() => {
    const onRenewed = () => setSession(read());
    window.addEventListener(ADMIN_SESSION_RENEWED, onRenewed);
    return () => window.removeEventListener(ADMIN_SESSION_RENEWED, onRenewed);
  }, []);

  // A CLEAN SIGN-OUT, NOT A SCREEN FULL OF 401s — fired from api.ts only after renewal itself
  // has been tried and failed, same as the affiliate portal's own session.ts.
  useEffect(() => {
    const onExpired = () => {
      localStorage.removeItem(KEY);
      setSession(ANONYMOUS);
    };
    window.addEventListener(ADMIN_SESSION_EXPIRED, onExpired);
    return () => window.removeEventListener(ADMIN_SESSION_EXPIRED, onExpired);
  }, []);

  return { session, signedIn: isSignedIn(session), signIn, signOut };
}
