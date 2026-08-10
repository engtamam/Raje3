/**
 * The action catalogue — the only source of a path in this application.
 *
 * THE RULE, AND IT IS ABSOLUTE: no screen composes a URL. Every call is an action the backend
 * declared, carrying its method, its path, its capability and its params. Two CI gates keep those
 * declarations honest — one proves the route exists, the other proves the declared capability is
 * the one the handler actually enforces — so a screen built on this cannot call something that is
 * not there, and cannot render a control the caller will be refused.
 *
 * WHAT THAT BUYS BEYOND TIDINESS. The gateway has ALREADY filtered by capability before we see it:
 * an action the caller cannot use is not in the response at all. So "should this button exist" is
 * never a question the UI answers — which is what makes the manager's console correct without a
 * single `if (role === …)`, and what stops the operator's screen from listing sections he cannot
 * reach. Hiding in the client would be a decision; this is a consequence.
 *
 * AND WHY THIS IS ONE FETCH RATHER THAN A CALL PER SERVICE: the gateway aggregates every service's
 * manifest, so a service that is down appears in `unreachable` instead of failing the whole load.
 * A nav that vanishes because one backend restarted would be worse than a nav with one gap.
 */
import type { Session } from './session';

export interface Action {
  id: string;
  label: string;
  method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  path: string;
  capability: string;
  group?: string;
  help?: string;
  /** The console asks before firing. Both are the BACKEND's judgement, not a screen's styling. */
  confirm?: boolean;
  danger?: boolean;
  params?: { name: string; in: 'path' | 'query' | 'body'; type: string; required?: boolean }[];
}

export interface Catalog {
  services: { service: string; actions: Action[] }[];
  /** Named, never silent: a section missing because a service is down must be distinguishable
   *  from a section missing because this person may not have it. */
  unreachable: string[];
}

const BASE = (import.meta.env.VITE_API_BASE ?? '').replace(/\/$/, '');

export async function fetchCatalog(session: Session): Promise<Catalog> {
  const res = await fetch(`${BASE}/api/v1/app/catalog`, {
    headers: { Authorization: `Bearer ${session.token}` },
  });
  if (!res.ok) throw new Error(`catalog ${res.status}`);
  return (await res.json()) as Catalog;
}

/** Every action, flattened — the shape the screens actually want. */
export function allActions(c: Catalog): Action[] {
  return c.services.flatMap((s) => s.actions);
}

/**
 * Find the action a screen needs, BY ID.
 *
 * Returning undefined rather than throwing is deliberate: an action absent because the caller
 * lacks the capability is the normal case, and the screen's answer is to render nothing — not to
 * fail. A missing action is a permission fact, not an error.
 */
export function action(c: Catalog, id: string): Action | undefined {
  return allActions(c).find((a) => a.id === id);
}

/** Does this session hold everything a section needs to be worth showing? */
export function hasAll(c: Catalog, ...ids: string[]): boolean {
  const have = new Set(allActions(c).map((a) => a.id));
  return ids.every((id) => have.has(id));
}

/**
 * Call an action.
 *
 * Path params are substituted from `params`; whatever is left over becomes the query string on a
 * GET and the body on anything else. The screen names the action and its values, and never a URL.
 */
export async function call<T>(
  session: Session,
  a: Action,
  params: Record<string, unknown> = {},
): Promise<T> {
  const rest = { ...params };
  let path = a.path.replace(/\{([^}]+)\}/g, (_, name: string) => {
    const v = rest[name];
    delete rest[name];
    return encodeURIComponent(String(v ?? ''));
  });

  const init: RequestInit = {
    method: a.method,
    headers: { Authorization: `Bearer ${session.token}` },
  };
  if (a.method === 'GET' || a.method === 'DELETE') {
    const q = new URLSearchParams();
    for (const [k, v] of Object.entries(rest)) if (v !== undefined && v !== null) q.set(k, String(v));
    if ([...q].length) path += `?${q.toString()}`;
  } else {
    init.headers = { ...init.headers, 'Content-Type': 'application/json' };
    init.body = JSON.stringify(rest);
  }

  const res = await fetch(`${BASE}${path}`, init);
  const text = await res.text();
  let body: unknown = null;
  try { body = text ? JSON.parse(text) : null; } catch { body = { raw: text }; }
  if (!res.ok) {
    // THE SENTENCE THE BACKEND WROTE, IF IT WROTE ONE. Our services return their refusals in the
    // body rather than raising, precisely because the platform's error handler strips an
    // HTTPException's detail — so the message that tells the owner what to do is in `message`.
    const said = (body as { message?: string; detail?: string } | null)?.message
      ?? (body as { detail?: string } | null)?.detail;
    throw new Error(said || `${a.method} ${a.path} → ${res.status}`);
  }
  return body as T;
}
