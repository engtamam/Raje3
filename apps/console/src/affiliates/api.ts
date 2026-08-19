/**
 * The affiliate portal's own door — a SEPARATE base URL, a separate token store, deliberately.
 *
 * NOT auth.ts, and not session.ts. Those are the shop's — `tenant`, `operator`, the action
 * catalogue — and a marketer is not a shop: he has no branch, no operator PIN, no subscription.
 * Sharing that module would mean bending its shape until it lied about the second audience it was
 * never written for, which is exactly the failure Door.tsx's own header note describes for the
 * kit's `LoginForm`/`SignupForm` — reused just enough to be wrong. So this is a second, small file
 * rather than a fork of the first.
 */
const BASE = (import.meta.env.VITE_AFFILIATE_API_BASE ?? '').replace(/\/$/, '');

/** Same shape as auth.ts's own Refused — the console-wide idiom for "a sentence AND a code the
 *  screen can act on", kept identical rather than reinvented per door. */
export class AffiliateRefused extends Error {
  constructor(message: string, readonly reason: string = '') {
    super(message);
  }
}

interface ApiResult {
  ok?: boolean;
  message?: string;
  reason?: string;
  [key: string]: unknown;
}

async function req<T>(path: string, method: 'GET' | 'POST', body?: unknown,
                      token?: string): Promise<T> {
  const headers: Record<string, string> = {};
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${BASE}${path}`, {
    method, headers, body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  const text = await res.text();
  let parsed: ApiResult | null = null;
  try { parsed = text ? (JSON.parse(text) as ApiResult) : null; } catch { parsed = null; }
  if (!res.ok || parsed?.ok === false) {
    throw new AffiliateRefused(
      parsed?.message ?? 'تعذّر إكمال الطلب. حاول مرة أخرى.', parsed?.reason ?? '');
  }
  return parsed as T;
}

export interface AffiliateSession {
  access_token: string;
  refresh_token?: string;
  tenant?: string;
}

/** «سجّل كمسوّق» — writes a ROW an admin has to look at first. No account, no token comes back;
 *  see services/affiliate-service/app/core/onboarding.py::apply for the whole reasoning. */
export async function apply(input: {
  phone: string; name: string; password: string; referralCode?: string;
}): Promise<{ application_id: string; status: string }> {
  return req('/api/v1/affiliates/apply', 'POST', {
    phone: input.phone, name: input.name, password: input.password,
    referral_code: input.referralCode || '',
  });
}

export async function signIn(phone: string, password: string): Promise<AffiliateSession> {
  return req('/api/v1/affiliates/signin', 'POST', { phone, password });
}

/** The other half of a manager's invite — no token yet, same reason `apply` has none. */
export async function acceptInvite(token: string, password: string): Promise<{ affiliate_id: string }> {
  return req('/api/v1/affiliates/accept-invite', 'POST', { token, password });
}

/** A manager naming somebody for his own team. Needs a signed-in manager's own token; the server
 *  is the one place that actually decides whether the caller may (see api/v1/affiliate_self.py). */
export async function invite(session: AffiliateSession, phone: string, name: string):
    Promise<{ application_id: string; status: string }> {
  return req('/api/v1/affiliates/me/invite', 'POST', { phone, name }, session.access_token);
}
