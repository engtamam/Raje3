/**
 * The admin panel's own door — a SEPARATE base URL (in principle; same-origin in practice, same
 * as the affiliate portal's own api.ts), a separate token store, deliberately.
 *
 * NOT `../session.ts` (a shop) and NOT `../affiliates/api.ts` (a marketer) — a platform operator
 * signs into the ONE reserved tenant every establishment's roles are kept out of (`_platform`,
 * see `deploy/seed/operator-roles.json`/`seed-roles.sh`), never a tenant he searches for or is
 * given a link to. There is no self-service signup door here at all: an admin account is minted
 * only by `deploy/seed/seed-admin.sh` (or a platform-owner granting a new one through this same
 * panel later) — never a public form.
 */
import { announceExpiry, fresh, renew } from './renew';

const BASE = (import.meta.env.VITE_ADMIN_API_BASE ?? '').replace(/\/$/, '');

// THE ONE RESERVED TENANT — never typed, never shown, never configurable from the browser. A
// body that could name its own tenant would be a body that could sign in AS an establishment;
// this is the one door on the whole product that hardcodes which tenant it means, because it is
// the one door that must never mean any other one.
const PLATFORM_TENANT = '_platform';

/** Same shape as `../auth.ts`'s own Refused / `../affiliates/api.ts`'s own AffiliateRefused —
 *  the console-wide idiom for "a sentence AND a code the screen can act on". */
export class AdminRefused extends Error {
  constructor(message: string, readonly reason: string = '') {
    super(message);
  }
}

interface ApiResult {
  ok?: boolean;
  message?: string;
  detail?: string;
  reason?: string;
  [key: string]: unknown;
}

async function req<T>(path: string, method: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE',
                      body?: unknown, token?: string): Promise<T> {
  let bearer = token ? await fresh(token) : token;
  const headers: Record<string, string> = {};
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (bearer) headers.Authorization = `Bearer ${bearer}`;
  let res = await fetch(`${BASE}${path}`, {
    method, headers, body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (res.status === 401 && token) {
    bearer = await renew();
    if (bearer) {
      headers.Authorization = `Bearer ${bearer}`;
      res = await fetch(`${BASE}${path}`, {
        method, headers, body: body !== undefined ? JSON.stringify(body) : undefined,
      });
    }
  }
  if (res.status === 401 && token) announceExpiry();
  const text = await res.text();
  let parsed: ApiResult | null = null;
  try { parsed = text ? (JSON.parse(text) as ApiResult) : null; } catch { parsed = null; }
  if (!res.ok || parsed?.ok === false) {
    const said = parsed?.message ?? parsed?.detail;
    throw new AdminRefused(said || 'تعذّر إكمال الطلب. حاول مرة أخرى.', parsed?.reason ?? '');
  }
  return parsed as T;
}

export interface AdminSession {
  access_token: string;
  refresh_token?: string;
}

interface Minted {
  access_token?: string;
  refresh_token?: string;
  detail?: string;
}

/** Sign in as a platform operator — the tenant is never asked for, never sent from a form field;
 *  it is this file's own constant. Mirrors `services/operations/app/core/signup.py::sign_in`'s
 *  own `/api/v1/auth/tenant` shape, reached here through the gateway route added for this panel
 *  (`/api/v1/auth/tenant`, rate-limited the same as every other sign-in door). */
export async function signIn(email: string, password: string, code = ''): Promise<AdminSession> {
  const body: Record<string, string> = { tenant: PLATFORM_TENANT, username: email, password };
  if (code) body.code = code;
  const res = await fetch(`${BASE}/api/v1/auth/tenant`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const text = await res.text();
  let parsed: Minted | null = null;
  try { parsed = text ? (JSON.parse(text) as Minted) : null; } catch { parsed = null; }
  if (!res.ok || !parsed?.access_token) {
    // ONE SENTENCE FOR EVERY REFUSAL — a wrong password and an unknown email must read the same,
    // same enumeration-oracle reasoning as every other sign-in door on this product.
    throw new AdminRefused('البريد أو كلمة المرور غير صحيحة.', parsed?.detail ?? '');
  }
  return { access_token: parsed.access_token, refresh_token: parsed.refresh_token };
}

export { req };
