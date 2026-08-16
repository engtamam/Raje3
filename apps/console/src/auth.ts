/**
 * The door — the ONE part of this application that composes a URL.
 *
 * Everywhere else the rule is absolute: a screen names an action and the catalogue supplies the
 * path. Sign-in cannot obey it, because the catalogue is fetched WITH a token and the whole point
 * of this file is that we do not have one yet. So the exception is stated here, in one file, with
 * two paths in it — rather than left as a habit that spreads.
 *
 * BOTH PATHS ARE OURS (services/operations/app/api/v1/signup.py), not the platform's, and that is
 * what keeps this file two lines long instead of a flow chart. identity registers a user INTO a
 * tenant and logs a user IN to a named tenant; neither creates a tenant, and the owner does not
 * know his tenant id and should never be shown it. Our service resolves the shop from the number
 * and forwards the login, so the browser sends what the owner typed and nothing else.
 */
import type { Session } from './session';

const BASE = (import.meta.env.VITE_API_BASE ?? '').replace(/\/$/, '');

/** The four values that open a shop. Every one of them is on the list for a reason — see
 *  core/signup.py; the register, the address and the VAT number are all asked later. */
export interface NewShop {
  phone: string;
  password: string;
  shopName: string;
  sector: string;
}

interface Minted {
  access_token?: string;
  refresh_token?: string;
  tenant?: string;
  message?: string;
  ok?: boolean;
}

/**
 * A refusal the screen can ACT on rather than only print.
 *
 * One refusal in this flow is a step and not a wall: an owner who closed the tab on the
 * verification screen. Telling him «أكّد رقم جوالك» and leaving him on a login form is the worst
 * of both — he learns what is wrong and is given no way to fix it. `reason` is a stable code
 * beside the sentence, so the console can route him to the code screen without matching Arabic
 * text that somebody will improve one day.
 */
export class Refused extends Error {
  constructor(message: string, readonly reason: string = '') {
    super(message);
  }
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const text = await res.text();
  let parsed: unknown = null;
  try { parsed = text ? JSON.parse(text) : null; } catch { parsed = null; }
  const said = (parsed as { message?: string; detail?: string } | null)?.message
    ?? (parsed as { detail?: string } | null)?.detail;
  // THE SENTENCE THE SERVICE WROTE. Our refusals are RETURNED in the body rather than raised,
  // precisely because the platform's handler strips an HTTPException's detail — so `message` is
  // where the line that tells the owner what to do actually is. A 200 carrying `ok: false` is a
  // refusal too, and treating it as success would let a failed signup fall through to a sign-in.
  if (!res.ok || (parsed as { ok?: boolean } | null)?.ok === false) {
    const reason = (parsed as { reason?: string } | null)?.reason ?? '';
    throw new Refused(said || 'تعذّر إكمال الطلب. حاول مرة أخرى.', reason);
  }
  return parsed as T;
}

/** Sign in: the phone, the password, and an OTP only when the server asks for one. */
export async function signIn(phone: string, password: string, code = ''): Promise<Session> {
  const t = await post<Minted>('/api/v1/signup/signin', { phone, password, code });
  return {
    tenant: t.tenant || '',
    // WHO he is comes off the token the server minted, never off the form. Identity is a claim we
    // read, not a value a screen carries — see session.ts.
    operator: '',
    operatorName: '',
    token: t.access_token || '',
    // KEPT, because the access token is deliberately short-lived and this is the only thing that
    // can replace it without asking him for his password again.
    refresh: t.refresh_token || '',
  };
}

/**
 * Open a shop, then walk straight through the door.
 *
 * The signup response carries NO token, deliberately: the account exists and the ordinary sign-in
 * is one call away, so there is no second mint path to keep correct for ever. The owner does not
 * see the second call — he sees his shop.
 */
export async function openShop(shop: NewShop): Promise<Session> {
  await post<{ tenant: string }>('/api/v1/signup', {
    phone: shop.phone,
    password: shop.password,
    shop_name: shop.shopName,
    sector: shop.sector,
  });
  const session = await signIn(shop.phone, shop.password);

  // ── THE NAME, WRITTEN WHERE THE ENGINE READS IT ─────────────────────────────────────────────
  //
  // THIS ONE LINE IS WHY A LIVE SHOP SENT NOTHING FOR A DAY, IN SILENCE.
  //
  // The signup saga hands the name to the tenant registry as `name`. The registry's INTERNAL read
  // — the only one our services may call — answers with id, slug, status, config and branding, and
  // no name at all. reminders therefore read a blank establishment; a blank name is the one thing
  // that must stop a send (a message signed by nobody is worse than a late one), so the tick
  // skipped the whole shop with «no establishment identity» BEFORE reaching the send log. Nothing
  // sent, nothing suppressed, nothing written down: «رسائلي» stayed empty and said the system was
  // calm.
  //
  // `branding.display_name` IS THE FIELD THE PLATFORM DOES RETURN, and every one of our services
  // already prefers it. There is no internal route that writes branding — only the tenant's OWN
  // `PUT /api/v1/tenant/branding`, which is exactly what this session now holds the capability
  // for. So the write happens here, one call after the door opens, rather than in a saga that
  // cannot reach it.
  //
  // FAILURE IS NOT FATAL TO SIGNUP. His account exists and every screen works; what he loses is
  // sending, which «اليوم» now says out loud and «حسابي» repairs in one field.
  // TRIED TWICE, BECAUSE THE LIKELY FAILURE IS A RACE WE CAUSED.
  //
  // The result used to be ignored entirely — `await fetch(...)` with no `res.ok` — so a 403 from a
  // token whose capability has not propagated yet was indistinguishable from success, and only a
  // network throw ever reached the catch. That is the most probable failure here and the one that
  // fixes itself in a moment: this write happens ONE call after the door opens.
  //
  // ONE RETRY, NOT A LOOP. If the second attempt fails the cause is not timing, and hammering the
  // tenant service during signup would turn a naming problem into a slow signup.
  //
  // AND STILL NOT FATAL. «اليوم» reads `can_send`/`blocked` from reminders — which checks the same
  // identity adapter the tick checks — so a shop whose name never landed is TOLD, in a sentence
  // that names the repair, on the screen whose whole question is «هل كل شيء يعمل؟». The retry
  // makes that sentence rarer; it is not what makes the failure visible.
  const writeBranding = async () =>
    fetch(`${BASE}/api/v1/tenant/branding`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${session.token}`,
      },
      body: JSON.stringify({ branding: { display_name: shop.shopName.trim() } }),
    });

  try {
    const first = await writeBranding();
    if (!first.ok) {
      await new Promise((r) => setTimeout(r, 700));
      await writeBranding();
    }
  } catch {
    // Swallowed on purpose: see above. The shop is open either way, and «اليوم» says what is wrong.
  }

  return session;
}

// ── proving the number ─────────────────────────────────────────────────────────────────────────
//
// THROUGH OUR SERVICE, NOT STRAIGHT TO IDENTITY — and the first version did the latter, which is
// how the hole was found by using the product rather than by reading it.
//
// identity issues the code and consumes it and records NO verdict; it answers "verified" and
// forgets. Our sign-in path had nothing to ask, so an owner who closed the tab on the verification
// screen and came back through the front door was signed straight in. The step was a screen, not
// a rule.
//
// operations now performs the exchange and writes the verdict on the same row it already keys by
// this number — so `signIn` refuses until it is true. The code still never leaves identity's
// keeping; what changed is that somebody remembers the answer.

export async function requestCode(phone: string): Promise<void> {
  await post('/api/v1/signup/code', { phone });
}

export async function verifyCode(phone: string, code: string): Promise<void> {
  await post('/api/v1/signup/verify', { phone, code });
}

/**
 * WHERE THE SIGNUP CONSENT IS REMEMBERED, and why it is a marker rather than a record.
 *
 * The RECORD is written by the legal gate, against the version in force, through
 * `compliance.accept_legal` — that is the only acceptance PDPL Art. 6 can be shown. This marker
 * exists so the gate does not ask a person the same question thirty seconds after he answered it
 * on the form. It holds a phone number and nothing else.
 */
export const AGREED_KEY = 'raje3.agreedAt.signup';
