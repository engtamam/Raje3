/**
 * WHO IS USING THIS SCREEN — asked in exactly one place.
 *
 * Every screen calls `useSession()`; not one of them reads a token, a tenant, or storage. That was
 * built as a seam while there was no login at all, and it is what made adding the door a change to
 * this file rather than to every call site.
 *
 * IT SURVIVES A CLOSED TAB, and that is a shop-floor decision rather than a security preference.
 * The console runs on a phone behind a counter that is locked, pocketed and reopened forty times a
 * day; a session that ended with the tab would mean typing a password forty times, and the answer
 * to that is always a password taped to the till. The token still expires on the server's clock,
 * which is the limit that actually holds.
 *
 * THE TOKEN IS THE ONLY THING STORED. No capabilities, no role, no plan: everything the UI decides
 * from comes out of the action catalogue on load, so a stale copy of a permission cannot outlive a
 * change to it.
 */
import { useCallback, useEffect, useState } from 'react';

import { forgetCatalog } from './catalog';
import { SESSION_EXPIRED } from './expired';
import { SESSION_RENEWED } from './renew';

export interface Session {
  /** The establishment. Every request is scoped by it, and the server enforces the scope. */
  tenant: string;
  /** WHO recorded the visit. It comes from the session and is never a field on the screen —
   *  spec 3.5: an operator asked to pick his own name will pick the first one in the list. */
  operator: string;
  operatorName: string;
  /** The bearer token. Held here and nowhere else, so a screen cannot log it or put it in a URL. */
  token: string;
  /**
   * THE 31 DAYS. The bearer above lives 15 minutes — a deliberate, short blast radius — and this
   * is what buys the next one. Without it stored, «مدة الجلسة 31 يوماً» was a claim about a token
   * nobody kept: the owner was thrown out mid-screen a quarter of an hour after signing in.
   */
  refresh?: string;
}

export const ANONYMOUS: Session = { tenant: '', operator: '', operatorName: '', token: '' };

export const KEY = 'raje3.session';

/**
 * IT NEVER INVENTS A TENANT. An incomplete stored value reads as signed out, because a placeholder
 * establishment would let every screen appear to work while writing visits nobody asked for into a
 * tenant nobody owns — discovered in production, in somebody's data.
 */
function read(): Session {
  let raw: Partial<Session> | undefined;
  try {
    raw = JSON.parse(localStorage.getItem(KEY) || 'null') ?? undefined;
  } catch {
    raw = undefined;
  }
  // The host page may still inject one — that is how the field screens ran before there was a
  // door, and how a test harness supplies a session without typing a password.
  raw = raw ?? (globalThis as { __RAJE3_SESSION__?: Partial<Session> }).__RAJE3_SESSION__;
  if (!raw || !raw.tenant || !raw.token) return ANONYMOUS;
  return {
    tenant: String(raw.tenant),
    operator: String(raw.operator ?? ''),
    operatorName: String(raw.operatorName ?? ''),
    token: String(raw.token),
    refresh: raw.refresh ? String(raw.refresh) : '',
  };
}

export function useSession(): {
  session: Session;
  signedIn: (s: Session) => void;
  signOut: () => void;
} {
  const [session, setSession] = useState<Session>(read);

  // RE-READ ON RETURN TO THE TAB, and on a write from another one. An owner who signs out on his
  // laptop and leaves the same page open on his phone is otherwise holding a screen that still
  // works — and `storage` is the only event that reports the other tab's write.
  useEffect(() => {
    const again = () => setSession(read());
    window.addEventListener('focus', again);
    window.addEventListener('storage', again);
    return () => {
      window.removeEventListener('focus', again);
      window.removeEventListener('storage', again);
    };
  }, []);

  // AND ON A REFUSED TOKEN, from wherever in the app it was refused. Any request may be the one
  // that discovers the session ended; before this, each screen caught its own 401, printed it to a
  // console nobody has open, and left the person staring at a skeleton that would never fill.
  useEffect(() => {
    const gone = () => {
      localStorage.removeItem(KEY);
      forgetCatalog();
      setSession(read());
    };
    window.addEventListener(SESSION_EXPIRED, gone);
    return () => window.removeEventListener(SESSION_EXPIRED, gone);
  }, []);

  // AND ON A RENEWED ONE. Renewal happens inside a request already in flight, below every
  // component, and writes the new bearer straight to storage. Without re-reading it here the hook
  // would keep handing screens the dead token, so the next call they make 401s and renews again —
  // working, but paying for a round trip on every request for the rest of the session.
  useEffect(() => {
    const fresh = () => setSession(read());
    window.addEventListener(SESSION_RENEWED, fresh);
    return () => window.removeEventListener(SESSION_RENEWED, fresh);
  }, []);

  const signedIn = useCallback((s: Session) => {
    localStorage.setItem(KEY, JSON.stringify(s));
    setSession(s);
  }, []);

  const signOut = useCallback(() => {
    localStorage.removeItem(KEY);
    // AND THE CATALOGUE WITH IT. It is keyed by token so it could not be served to the next
    // person anyway, but leaving one person's capabilities in a shared browser is not a thing to
    // rely on a key for.
    forgetCatalog();
    setSession(ANONYMOUS);
  }, []);

  return { session, signedIn, signOut };
}

export function isSignedIn(s: Session): boolean {
  return Boolean(s.tenant && s.token);
}
