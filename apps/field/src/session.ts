/**
 * WHO IS USING THIS SCREEN — asked in exactly one place, answered differently over time.
 *
 * There is no login screen in this app yet, and that was a decision rather than an omission: the
 * field screens are worth more than the door, and building the door first would have meant
 * building it before we knew what it opens onto. Phone-and-password sign-in arrives once, later,
 * for every app at the same time.
 *
 * BUT DEFERRING A DOOR IS ONLY SAFE IF NOTHING BEHIND IT KNOWS THE DOOR IS MISSING. So identity
 * enters through this one function. Every screen asks `useSession()`; not one of them reads a
 * token, a tenant, or storage. The day sign-in lands, the body of `read()` changes and nothing
 * else does — the difference between adding a feature and rewriting an app.
 *
 * If instead each screen reached for its own token, "add login" would mean touching every call
 * site, and the ones missed would keep working against whatever was left lying in storage.
 */
import { useEffect, useState } from 'react';

export interface Session {
  /** The establishment. Every request is scoped by it, and the server enforces the scope. */
  tenant: string;
  /** WHO recorded the visit. It comes from the session and is never a field on the screen —
   *  spec 3.5: an operator asked to pick his own name will pick the first one in the list. */
  operator: string;
  operatorName: string;
  /** The bearer token. Held here and nowhere else, so a screen cannot log it or put it in a URL. */
  token: string;
  /** Which sector this establishment is, because it decides which inputs render (spec 13.2) —
   *  the plate exists in a بنشر and does not exist at all in a صالون. */
  sector: string;
}

export const ANONYMOUS: Session = {
  tenant: '', operator: '', operatorName: '', token: '', sector: '',
};

/**
 * WHERE IT COMES FROM TODAY. A value handed to the app at startup — injected by the host page, or
 * a local file in development. NOT a login, and it does not pretend to be one.
 *
 * IT NEVER INVENTS A TENANT. An empty session stays empty and the screen says so, because a
 * placeholder establishment would let every screen appear to work while writing visits nobody
 * asked for into a tenant nobody owns — and that is discovered in production, in somebody's data.
 */
function read(): Session {
  const raw = (globalThis as { __RAJE3_SESSION__?: Partial<Session> }).__RAJE3_SESSION__;
  if (!raw || !raw.tenant || !raw.token) return ANONYMOUS;
  return {
    tenant: String(raw.tenant),
    operator: String(raw.operator ?? ''),
    operatorName: String(raw.operatorName ?? ''),
    token: String(raw.token),
    sector: String(raw.sector ?? ''),
  };
}

export function useSession(): Session {
  const [session, setSession] = useState<Session>(read);
  // RE-READ ON RETURN TO THE TAB. When sign-in does land it will refresh tokens in the background,
  // and a screen holding the first token it ever saw would start failing after an hour with a 401
  // the operator cannot act on.
  useEffect(() => {
    const again = () => setSession(read());
    window.addEventListener('focus', again);
    return () => window.removeEventListener('focus', again);
  }, []);
  return session;
}

export function isSignedIn(s: Session): boolean {
  return Boolean(s.tenant && s.token);
}
