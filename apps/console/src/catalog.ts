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
import { renew } from './renew';
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

/**
 * An expired session, told apart from everything else.
 *
 * A TOKEN THAT RAN OUT IS NOT AN OUTAGE, and the app said it was: the catalogue answered 401, the
 * shell rendered «تعذّر الوصول إلى المنصة — حسابك سليم», and an owner sat waiting for a platform
 * that was working perfectly. He needed one thing and it was the one thing the screen did not
 * offer — the door.
 */
export class SessionExpired extends Error {}

/**
 * The catalogue, kept for the length of a session.
 *
 * WHY THIS IS WORTH A CACHE WHEN ALMOST NOTHING ELSE IS. The gateway builds this answer by asking
 * twenty-three services for their manifests, so it costs about two seconds — and NOTHING renders
 * until it lands, because the navigation itself is derived from it. Every reload paid that in
 * full, staring at an empty shell.
 *
 * SESSION STORAGE, NOT LOCAL. It dies with the tab, so a person who is granted a capability today
 * sees the new section by closing the tab rather than by clearing a cache nobody told him about —
 * and a stale copy can never outlive the token it was fetched with.
 *
 * AND IT IS KEYED BY TOKEN. A different session is a different set of capabilities; serving one
 * person's catalogue to another would render controls he may not use, and the refusals would look
 * like bugs.
 */
const CACHE_KEY = 'raje3.catalog';

function cached(token: string): Catalog | null {
  try {
    const raw = sessionStorage.getItem(CACHE_KEY);
    if (!raw) return null;
    const held = JSON.parse(raw) as { token: string; catalog: Catalog };
    return held.token === token ? held.catalog : null;
  } catch {
    return null;
  }
}

function remember(token: string, catalog: Catalog): void {
  try {
    sessionStorage.setItem(CACHE_KEY, JSON.stringify({ token, catalog }));
  } catch {
    // Private mode, or a full quota. The app simply fetches again — a cache that throws must not
    // be a cache that breaks the page.
  }
}

/** Dropped on sign-out, so the next person on this browser starts from the server. */
export function forgetCatalog(): void {
  try {
    sessionStorage.removeItem(CACHE_KEY);
  } catch { /* nothing to clear */ }
}

export async function fetchCatalog(session: Session): Promise<Catalog> {
  const held = cached(session.token);
  if (held) return held;

  let token = session.token;
  let res = await fetch(`${BASE}/api/v1/app/catalog`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  // THE FIRST CALL OF EVERY RELOAD, so this is where a session left overnight is most often found
  // to have aged out — and where signing him out would be most obviously wrong, since the refresh
  // token in his browser is good for another month.
  if (res.status === 401) {
    const fresh = await renew();
    if (fresh) {
      token = fresh;
      res = await fetch(`${BASE}/api/v1/app/catalog`, {
        headers: { Authorization: `Bearer ${token}` },
      });
    }
  }
  if (res.status === 401 || res.status === 403) throw new SessionExpired();
  if (!res.ok) throw new Error(`catalog ${res.status}`);
  const catalog = (await res.json()) as Catalog;
  // NOT CACHED WHEN EVERY SERVICE WAS UNREACHABLE. An outage answer kept for the session would
  // turn a two-minute blip into an empty application until the tab is closed.
  if (catalog.services.length > 0) remember(token, catalog);
  return catalog;
}

/** Every action, flattened — the shape the screens actually want. */
export function allActions(c: Catalog): Action[] {
  return c.services.flatMap((s) => s.actions);
}

/**
 * Find the action a screen needs.
 *
 * AN ID IS UNIQUE WITHIN A SERVICE, NOT ACROSS THE FLEET — which is the platform's design, not an
 * accident: thirteen of its services each declare `operator.get_config`, because the catalogue
 * groups actions under their service and a console reads the pair. An earlier version of this
 * function flattened and took the first match, which would have made those thirteen one.
 *
 * So an id that more than one service declares must be asked for WITH its service. `service`
 * stays optional because most ids are unambiguous and requiring it everywhere would be noise;
 * ci/check_ui_actions.py fails the build if an ambiguous one is named without it.
 *
 * Returning undefined rather than throwing is deliberate: an action absent because the caller
 * lacks the capability is the normal case, and the screen's answer is to render nothing — not to
 * fail. A missing action is a permission fact, not an error.
 */
export function action(c: Catalog, id: string, service?: string): Action | undefined {
  for (const s of c.services) {
    if (service && s.service !== service) continue;
    const hit = s.actions.find((a) => a.id === id);
    if (hit) return hit;
  }
  return undefined;
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

  let res = await fetch(`${BASE}${path}`, init);
  if (res.status === 401) {
    // ONE RENEWAL, THEN ONE RETRY. The bearer lives 15 minutes and the refresh token 31 days, so
    // the overwhelmingly likely cause of a 401 here is simply that time passed while he worked.
    // Only when renewal itself fails is the session actually over — and then the 401 falls through
    // to whoever announces expiry, unchanged.
    const token = await renew();
    if (token) {
      init.headers = { ...init.headers, Authorization: `Bearer ${token}` };
      res = await fetch(`${BASE}${path}`, init);
    }
  }
  const text = await res.text();
  let body: unknown = null;
  try { body = text ? JSON.parse(text) : null; } catch { body = { raw: text }; }
  if (!res.ok) {
    // THE SENTENCE THE BACKEND WROTE, IF IT WROTE ONE. Our services return their refusals in the
    // body rather than raising, precisely because the platform's error handler strips an
    // HTTPException's detail — so the message that tells the owner what to do is in `message`.
    // `reason` is the key OUR services use (`_refuse`); `message`/`detail` cover the platform's
    // own shapes. Reading only the last two dropped every sentence we wrote ourselves — the owner
    // switching to invoice earning saw an uncaught 400 and no explanation.
    const r = body as { reason?: string; message?: string; detail?: string } | null;
    const said = r?.reason ?? r?.message ?? r?.detail;
    throw new Error(said || `${a.method} ${a.path} → ${res.status}`);
  }
  return body as T;
}
