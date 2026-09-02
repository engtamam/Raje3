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

/** Ask identity to mint and deliver a reset code over WhatsApp (OTP_DELIVERY_CHANNEL is already
 *  "whatsapp" for this deployment — see deploy/services/identity-service.values.yaml). Same
 *  no-oracle shape as sign-in: the response never distinguishes an unknown identifier from a real
 *  one, so this never throws for that reason — always resolves, whether or not anything was sent.
 *  `/api/v1/otp/verify` is deliberately never called from here (see api-gateway.values.yaml's own
 *  note on why /api/v1/otp is not routed at all) — the code is consumed once, atomically with the
 *  password write, by `resetPassword` below. */
export async function requestPasswordResetOtp(identifier: string): Promise<void> {
  await fetch(`${BASE}/api/v1/otp/request`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ identifier, purpose: 'reset' }),
  });
}

/** The one call that both verifies the code AND sets the new password — never two calls, so the
 *  code is never consumed by a check that then leaves the actual reset to a second round trip
 *  that could fail. Mirrors identity-service's `POST /api/v1/auth/reset-password` response shape
 *  exactly (confirmed against base-services-de, 2026-09-02 — the service genericises
 *  HTTPException.detail on purpose, CWE-209, so these named codes ride `error`, never `detail`):
 *    200 {"status": "ok"}
 *    400 {"error": "WEAK_PASSWORD"}    — checked BEFORE the code is consumed, so a typo'd
 *                                        password does not burn the operator's one code
 *    400 {"error": "INVALID_RESET"}    — wrong code, expired code, or an unknown/inactive
 *                                        identifier, all one bucket (no oracle)
 *    429 {"error": "RATE_LIMITED"}     — per-source AND per-identifier cooldowns both live here */
export async function resetPassword(identifier: string, code: string, newPassword: string): Promise<void> {
  const res = await fetch(`${BASE}/api/v1/auth/reset-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ identifier, code, new_password: newPassword }),
  });
  if (res.ok) return;
  const text = await res.text();
  let code_ = '';
  try { code_ = (JSON.parse(text) as { error?: string }).error ?? ''; } catch { /* not json */ }
  if (code_ === 'WEAK_PASSWORD') throw new AdminRefused('كلمة المرور ضعيفة — 12 حرفاً فأكثر.', code_);
  if (code_ === 'RATE_LIMITED') throw new AdminRefused('محاولات كثيرة — انتظر قليلاً وحاول مرة أخرى.', code_);
  throw new AdminRefused('الرمز غير صحيح أو منتهٍ.', code_ || 'INVALID_RESET');
}

export { req };
