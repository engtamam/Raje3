/**
 * The demo seeders' one HTTP layer — how a script outside the browser talks to the real API.
 *
 * MOVED HERE FROM seed-demo-account.mjs, NOT REWRITTEN. That script grew these helpers first, and
 * seed-demo-apps/ (the every-app test shop) needs exactly the same ones: the same URL resolution
 * with its double-slash trap, the same `callAction` that turns a catalog action into a request,
 * the same browser-only-for-signup step. Two copies would drift the first time one of them learned
 * something the hard way — every comment below is one of those lessons.
 *
 * THE SAME REQUESTS THE CONSOLE MAKES. apps/console/src/api.ts and catalog.ts's call() build these
 * same paths and bodies; they are replicated rather than imported because those modules assume a
 * browser's own fetch/localStorage, and this is a standalone node script.
 */
import { join, dirname, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { chromiumModule } from '../../lib/browser.mjs';
import { ensureFreshDemoSession, saveDemoCredentials, saveDemoSession } from './demo-session.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const CONSOLE_DIR = resolve(HERE, '../../../apps/console');

const rawBase = process.env.CONSOLE ?? 'http://localhost:5174';
export const BASE_URL = rawBase.endsWith('/') ? rawBase : `${rawBase}/`;
// THE APP IS SERVED UNDER /app/, THE API AT THE ROOT — and the root must carry NO trailing slash
// of its own, because every call below builds its URL as `${API}${path}` with `path` already
// starting with one. A `CONSOLE` given as a bare origin (`http://host:5173`, which is exactly how
// a tunnel is usually named) is the case that breaks: the `/app/` strip finds nothing to remove,
// BASE_URL's own trailing slash survives, and every request goes to `//api/v1/…` — a path the
// gateway answers 404 to, which reads as "this account has no catalogue" rather than "the URL has
// two slashes in it" (a full seeding run was lost to exactly that reading).
export const API = BASE_URL.replace(/\/app\/?$/, '').replace(/\/$/, '');

export function randomPhone() {
  return `05${Math.floor(Math.random() * 90_000_000) + 10_000_000}`;
}
export function pick(arr) { return arr[Math.floor(Math.random() * arr.length)]; }
export function shuffle(arr) {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

/** Runs `items` through `worker` with at most `n` in flight at once — real concurrency, not a
 *  single-file queue, without needing a dependency for it. */
export async function pool(items, n, worker) {
  const results = [];
  let i = 0;
  async function run() {
    while (i < items.length) {
      const idx = i++;
      results[idx] = await worker(items[idx], idx).catch((e) => ({ error: e.message }));
    }
  }
  await Promise.all(Array.from({ length: Math.min(n, items.length) }, run));
  return results;
}

export async function getJson(path, token) {
  const res = await fetch(`${API}${path}`, { headers: { Authorization: `Bearer ${token}` } });
  if (!res.ok) throw new Error(`GET ${path} → ${res.status}`);
  return res.json();
}

export async function callAction(session, action, params = {}) {
  const rest = { ...params };
  let path = action.path.replace(/\{([^}]+)\}/g, (_, name) => {
    const v = rest[name]; delete rest[name]; return encodeURIComponent(String(v));
  });
  const method = action.method || 'GET';
  const opts = { method, headers: { Authorization: `Bearer ${session.token}` } };
  if (method === 'GET') {
    const q = new URLSearchParams(Object.entries(rest).filter(([, v]) => v !== undefined).map(([k, v]) => [k, String(v)]));
    if ([...q].length) path += `${path.includes('?') ? '&' : '?'}${q}`;
  } else {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(rest);
  }
  const res = await fetch(`${API}${path}`, opts);
  if (!res.ok) throw new Error(`${method} ${path} → ${res.status}: ${(await res.text()).slice(0, 300)}`);
  const text = await res.text();
  return text ? JSON.parse(text) : {};
}

/** The signup itself, in a real browser — the one step that is never replayed as plain HTTP,
 *  because a shop's first session is minted by the door's own sign-in behind the signup call, and
 *  the only proof that worked is a screen only a session can render (see e2e/fixtures.ts). */
export async function signUpFreshDemoShop(profile = '') {
  const chromium = chromiumModule();
  const browser = await chromium.launch();
  const context = await browser.newContext({ baseURL: BASE_URL, viewport: { width: 430, height: 932 } });
  const page = await context.newPage();
  const { openShop, PASSWORD } = await import(pathToFileURL(join(CONSOLE_DIR, 'e2e/fixtures.ts')).href);
  await page.goto(BASE_URL);
  // THE PHONE IT PICKED, WRITTEN DOWN — `openShop()` generates a random one and returns it, and
  // for a long time nothing here kept it. That number plus the fixture's own password is the ONLY
  // way back into this shop once an access token ages out; without it a fully seeded account is
  // one expired token away from being unreachable for good (it was, live — see
  // lib/demo-session.mjs).
  const phone = await openShop(page);
  saveDemoCredentials(phone, PASSWORD, profile);
  const raw = await page.evaluate(() => localStorage.getItem('raje3.session'));
  await browser.close();
  const session = JSON.parse(raw);
  saveDemoSession(session, profile);
  return session;
}

/** Riyadh is the shop's own clock — the same `+03:00` every epoch on the bookings screen is built
 *  against (`epochAt` in Bookings.tsx). Never the recording machine's local zone, which can and
 *  does differ and would place a "10:00 appointment" an hour off the column it was meant for. */
export function riyadhToday() {
  return new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Riyadh' }); // YYYY-MM-DD
}
export function addDaysStr(dateStr, delta) {
  const [y, m, d] = dateStr.split('-').map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  dt.setUTCDate(dt.getUTCDate() + delta);
  return dt.toISOString().slice(0, 10);
}
export function epochAtRiyadh(dateStr, minutes) {
  const h = String(Math.floor(minutes / 60)).padStart(2, '0');
  const mm = String(minutes % 60).padStart(2, '0');
  return Math.floor(Date.parse(`${dateStr}T${h}:${mm}:00+03:00`) / 1000);
}

/**
 * One handle a long-running seed passes around instead of a raw session: the same `callAction`,
 * but the token is checked before every call and re-minted from the saved login when it is about
 * to expire. A whole every-app seed runs for much longer than the fifteen minutes an access token
 * lives, and losing the run halfway over an expired token was exactly the failure
 * lib/demo-session.mjs was written for.
 *
 * `act(id)` resolves a catalog action the way seed-demo-account.mjs's own `act` does — from the
 * session's live `/api/v1/app/catalog`, so a missing capability fails loudly by name. `refresh()`
 * re-reads the catalog (after a subscription changes what the shop may do).
 */
export async function makeApi(session, profile = '') {
  let catalog = await getJson('/api/v1/app/catalog', session.token);
  const api = {
    session,
    async fresh() {
      const next = await ensureFreshDemoSession(API, profile);
      if (next) Object.assign(api.session, next);
      return api.session;
    },
    async call(action, params = {}) {
      await api.fresh();
      return callAction(api.session, action, params);
    },
    async get(path) {
      await api.fresh();
      return getJson(path, api.session.token);
    },
    /** A fixed route (the console calls these directly, not through the catalog). */
    async req(method, path, body) {
      return api.call({ method, path }, body);
    },
    act(id) {
      for (const s of catalog.services ?? []) {
        const hit = (s.actions ?? []).find((a) => a.id === id);
        if (hit) return hit;
      }
      throw new Error(`action "${id}" not in this session's catalog — does the account have the capability?`);
    },
    tryAct(id) {
      try { return api.act(id); } catch { return null; }
    },
    async refresh() {
      await api.fresh();
      catalog = await getJson('/api/v1/app/catalog', api.session.token);
      return catalog;
    },
    catalog: () => catalog,
  };
  return api;
}
