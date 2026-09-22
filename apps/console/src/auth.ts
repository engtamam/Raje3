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
import { translate } from './operator-i18n';
import type { Session } from './session';
import './auth-i18n';

const BASE = (import.meta.env.VITE_API_BASE ?? '').replace(/\/$/, '');

/** The four values that open a shop. Every one of them is on the list for a reason — see
 *  core/signup.py; the register, the address and the VAT number are all asked later.
 *
 *  `affiliateRef` IS NOT ONE OF THE FOUR — it never came from the owner typing anything.
 *  See `affiliateRefFromUrl()` below for where it actually comes from. */
export interface NewShop {
  phone: string;
  password: string;
  shopName: string;
  // OPTIONAL — see core/signup.py's own NewShop.owner_name note for why this never becomes a
  // required fifth value. Empty means the greeting (mobile) or account pane (here) still reads
  // his phone number until he sets one, at signup or later from «حسابي».
  ownerName?: string;
  affiliateRef?: string;
  // EMPTY ON A DEPLOYMENT THAT HAS NOT TURNED OTP-AT-SIGNUP ON — the backend only spends it when
  // `SIGNUP_REQUIRE_OTP` is set (services/operations `open_shop_verified`); an unset field costs
  // nothing until that flag flips.
  code?: string;
}

/**
 * WHICH MARKETER'S LINK THIS OWNER ARRIVED ON, if any — read from `?aff=`, never typed.
 *
 * A BODY THAT COULD NAME ITS OWN AFFILIATE ID WOULD BE A BODY THAT COULD REDIRECT SOMEBODY
 * ELSE'S COMMISSION — same reasoning core/signup.py already applies to a partner key on a
 * till-company claim. The owner never sees or edits this value; it rides along silently from
 * the URL he happened to open, exactly once, at the one form that can still use it.
 */
export function affiliateRefFromUrl(): string {
  try {
    return new URLSearchParams(window.location.search).get('aff') ?? '';
  } catch {
    return '';
  }
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
    throw new Refused(said || translate('ar', 'auth.requestFailed'), reason);
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

/** Extra facts an `openShop` caller needs about the trial, carried alongside a thrown `Refused`
 *  too (the «أكّد رقمك» step) — the shop already exists and its trial already opened by the time
 *  sign-in is what refuses, and that fact must not be lost on the one path that retries it. */
export interface OpenedShop {
  session: Session;
  trialStarted: boolean;
  /** Unix seconds, or 0 when no trial was opened — never a hardcoded day count (§ signup.py's
   *  own note: how long a trial runs is billing's decision, not a promise baked into either
   *  service). */
  trialEnd: number;
}

/**
 * Open a shop, then walk straight through the door.
 *
 * The signup response carries NO token, deliberately: the account exists and the ordinary sign-in
 * is one call away, so there is no second mint path to keep correct for ever. The owner does not
 * see the second call — he sees his shop.
 */
export async function openShop(shop: NewShop): Promise<OpenedShop> {
  const out = await post<{ tenant: string; trial_started?: boolean; trial_end?: number }>(
    '/api/v1/signup', {
      phone: shop.phone,
      password: shop.password,
      shop_name: shop.shopName,
      owner_name: shop.ownerName || '',
      affiliate_ref: shop.affiliateRef || '',
      code: shop.code || '',
    });
  const trialStarted = out.trial_started === true;
  const trialEnd = Number(out.trial_end) || 0;

  // ── THE NAME, WRITTEN WHERE THE ENGINE READS IT ─────────────────────────────────────────────
  //
  // THIS ONE LINE IS WHY A LIVE SHOP SENT NOTHING FOR A DAY, IN SILENCE.
  // THE NAME IS THE SAGA'S, AND NOTHING FOLLOWS IT. It is handed to the registry at creation
  // and changed afterwards from «حسابي» through `operations.set_shop_name` — one field, one
  // write, one name, and no copy of it anywhere in this file.

  try {
    const session = await signIn(shop.phone, shop.password);
    return { session, trialStarted, trialEnd };
  } catch (err) {
    // THE SHOP AND ITS TRIAL ALREADY EXIST BY HERE — only the immediate sign-in refused, most
    // often «أكّد رقمك». Stamped onto the error rather than swallowed, so the caller's own retry
    // (after the OTP screen) can still show the same welcome once he is actually in.
    if (err instanceof Error) {
      Object.assign(err, { trialStarted, trialEnd });
    }
    throw err;
  }
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

/**
 * ONE-TIME CUE FOR THE WELCOME SCREEN, session-scoped on purpose — it must survive the brief
 * moment between opening a shop and `App` first rendering signed-in, and must NOT survive past
 * this browser tab closing or a later sign-in from a different device: the welcome is for the
 * one person who just typed the form, once, never replayed on a routine sign-in.
 */
export const WELCOME_TRIAL_KEY = 'raje3.justOpened.trialEnd';
