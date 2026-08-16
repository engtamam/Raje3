/**
 * The only place in this app that speaks HTTP.
 *
 * Every screen calls a named function here — `recordVisit`, `suggestByPrefix` — and none of them
 * knows a URL, a header or a token. That is not tidiness: a token that appears in two places
 * eventually appears in a log, a query string, or an error report, and this app runs on a shared
 * tablet in a workshop.
 *
 * THE BASE URL IS CONFIGURATION, NOT A CONSTANT. It differs between a developer's machine, a
 * staging cluster and production, and a literal here would be a value we could not change without
 * a rebuild.
 *
 * EVERY SHAPE BELOW WAS READ OUT OF THE SERVICE, NOT ASSUMED. Three of them would have been wrong
 * if guessed, and each is noted where it matters: the idempotency key is a body field and not a
 * header; the services array is `service_ids`; and prefix search is NOT served by operations at
 * all.
 */
import { announceExpiry } from './expired';
import { renew } from './renew';
import { newIdempotencyKey } from './queue';
import type { Session } from './session';

const BASE = (import.meta.env.VITE_API_BASE ?? '').replace(/\/$/, '');

export class ApiError extends Error {
  constructor(readonly status: number, readonly body: unknown, message: string) {
    super(message);
  }
}

/** The sentence an operator reads. NEVER a status code and never an English exception: he cannot
 *  act on either, and the customer is standing in front of him while he reads it.
 *
 *  THIS FUNCTION EXISTED AND NOTHING CALLED IT — and the sweep that found it is worth writing
 *  down, because the first count was wrong. Thirty-seven `catch` blocks read
 *  `e instanceof Error ? e.message : '<arabic>'`, which LOOKS like the defect everywhere. It is
 *  not: `catalog.call` and `auth.post` both already dig the service's own sentence out of the body
 *  and put it in `.message`, so on those paths the Arabic branch is the unreachable one and the
 *  reachable one is correct.
 *
 *  ONE PATH DOES NOT: `call` in this file throws an ApiError whose message is built for a LOG —
 *  `POST /api/v1/loyalty/redeem → 400`. The single screen that renders it is the redemption on the
 *  visit screen, where a cashier stands in front of the customer and reads a route and a number
 *  instead of «رصيد العميل لا يكفي» — the sentence loyalty was changed to RETURN rather than raise
 *  for precisely that moment.
 *
 *  `fallback` IS THE CALL SITE'S OWN WORDS, and it is required rather than defaulted: «تعذّر
 *  السحب» and «تعذّر الحذف» are not the same sentence, and one generic message for both is how a
 *  screen stops telling anyone which act failed. */
export function sentenceFor(e: unknown, fallback: string): string {
  if (e instanceof ApiError) {
    const body = e.body as { message?: string; detail?: string; reason?: string } | null;
    // THE PEER'S OWN WORDS FIRST. `reason` is the key our services answer refusals with; `message`
    // and `detail` are the platform's. Whichever arrives, it was written for this person.
    const said = body?.message || body?.detail || body?.reason;
    if (said) return String(said);
    if (e.status === 401 || e.status === 403) return 'انتهت الجلسة — أعد فتح الشاشة.';
    if (e.status >= 500) return 'الخدمة لا تستجيب الآن. حاول بعد قليل.';
    return fallback;
  }
  // A network failure is the NORMAL case in a workshop, not an exception — and it is the one
  // message that must not alarm.
  if (e instanceof TypeError) return 'لا يوجد اتصال — تحقّق من الشبكة وحاول مرة أخرى.';

  // AN ARABIC MESSAGE WAS WRITTEN FOR A PERSON; KEEP IT.
  //
  // Not every thrower is this file. `auth.post` raises `Refused` and `catalog.call` raises a plain
  // Error, and BOTH have already dug the service's own sentence out of the response body — so
  // their `.message` is «رقم الجوال مسجّل مسبقاً», not a route. Discarding that in favour of a
  // generic fallback would break two paths in order to fix one, and would do it silently.
  //
  // THE TEST IS THE SCRIPT, NOT A LIST OF THROWERS. A message a person can read is in Arabic; a
  // message built for a log is `POST /api/v1/... → 400`. Asking which script it is written in is
  // the one question that stays true when a third thrower is added next month.
  if (e instanceof Error && /[؀-ۿ]/.test(e.message)) return e.message;
  return fallback;
}

async function call<T>(session: Session, path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set('Authorization', `Bearer ${session.token}`);
  if (init.body) headers.set('Content-Type', 'application/json');
  let res = await fetch(`${BASE}${path}`, { ...init, headers });
  if (res.status === 401) {
    // RENEW BEFORE DECLARING ANYTHING. The bearer is good for 15 minutes and the refresh token for
    // 31 days; on this screen especially — the one an operator keeps open all day at the counter —
    // a 401 almost always means the shift outlasted the token, not that the session ended.
    const token = await renew();
    if (token) {
      headers.set('Authorization', `Bearer ${token}`);
      res = await fetch(`${BASE}${path}`, { ...init, headers });
    }
  }
  const text = await res.text();
  let body: unknown = null;
  try { body = text ? JSON.parse(text) : null; } catch { body = { raw: text }; }
  // THE SESSION ENDS HERE, ONCE, for whichever screen happened to be the one that found out —
  // and only after renewal has been tried and failed.
  if (res.status === 401) announceExpiry();
  if (!res.ok) throw new ApiError(res.status, body, `${init.method ?? 'GET'} ${path} → ${res.status}`);
  return body as T;
}

// ── the catalogue: what the buttons are ────────────────────────────────────────────────────────

export interface CatalogueService {
  id: string;
  name: string;
  icon?: string;
  colour?: string;
  cycle_days?: number;
}

/** A field the sector renders — the full descriptor, so this app never carries its own idea of
 *  what "plate" or "meter" means. */
export interface SectorField {
  name: string;
  label?: string;
  type?: string;
  required?: boolean;
}

/**
 * The grid AND the inputs, in one answer.
 *
 * WHICH FIELDS RENDER IS THE SERVER'S TO SAY, not this app's. The plate exists in a tyre shop and
 * does not exist at all in a salon (spec 13.2) — and a list of sector keys written into this file
 * would be a copy of our own data living where the console cannot reach it: an operator adds a
 * fifth sector at runtime and the screen keeps rendering the four it was built with.
 *
 * An establishment provisioned before we recorded sectors answers an empty list — which renders
 * the phone and nothing else, and is always valid.
 */
export function fetchCatalogue(
  session: Session,
): Promise<{ services: CatalogueService[]; sector: string; fields: SectorField[] }> {
  return call(session, '/api/v1/field/catalogue');
}

// ── the customer ───────────────────────────────────────────────────────────────────────────────

export interface CustomerHit {
  id: string;
  phone: string;
  /** His plates, space-joined, when the shop keeps vehicles. */
  plate?: string;
  name?: string;
  visits?: number;
  points?: number;
  /** Whether marketing messages reach him. Shown as a hint so the operator can say the balance out
   *  loud (spec 4.7) — a customer who opted out earns points and is never told he has them. */
  marketing?: boolean;
}

/**
 * PREFIX SEARCH IS SEARCH-SERVICE'S, NOT OPERATIONS'.
 *
 * operations serves /customers/by-phone for an EXACT number and says so in its own docstring: a
 * prefix scan over the datastore is a table scan, and this sits inside a five-second budget. And
 * POST /search matches whole tokens, so `96650` finds nothing against a stored `966501234567` —
 * only /suggest answers a partial number.
 *
 * Getting this wrong is the failure the spec calls out by name: the operator types four digits,
 * sees nothing, concludes the customer is new, and registers him a second time — and the product's
 * entire premise disappears quietly.
 */
export async function suggestByPrefix(session: Session, prefix: string): Promise<CustomerHit[]> {
  // STEP ONE: /suggest ANSWERS TERMS, NOT PEOPLE — `{"suggestions": ["0527463428", …]}`, a list of
  // strings. This function used to read `r.phone` off each one, get `undefined` from a string, and
  // filter the whole list away: measured on the live cluster, «05» returned five numbers and this
  // returned nothing. Every suggestion list in the product — the keypad AND the plate — was empty,
  // and it looked exactly like "no such customer", which is the one wrong answer this screen must
  // never give.
  const q = new URLSearchParams({ index: 'customers', prefix });
  const out = await call<{ suggestions?: unknown[] }>(
    session, `/api/v1/search/suggest?${q.toString()}`);
  const terms = (out.suggestions ?? []).filter((t): t is string => typeof t === 'string' && !!t);

  // AND THE TYPED TEXT ITSELF, because /suggest deliberately omits it. An autocomplete does not
  // offer you the word you have already finished typing — so the list appeared at «123» and
  // VANISHED at «1234», the moment the operator finished the number he was reading off the bumper.
  // The one keystroke that should have confirmed the car is the one that emptied the screen.
  // It costs nothing: a partial token matches no document, and a complete one is the answer.
  const words = [...new Set([...terms, ...prefix.trim().split(/\s+/).filter(Boolean)])];
  if (!words.length) return [];

  // STEP TWO: the terms fetch the people. POST /search matches WHOLE tokens and unions its terms —
  // and a suggested term is by construction a whole token, so this is the one call it answers
  // exactly. Bounded: at most `suggest_max` terms, one round trip, and no scan on our side.
  const found = await call<{ hits?: { id?: string; fields?: Record<string, unknown> }[] }>(
    session, '/api/v1/search', {
      method: 'POST',
      body: JSON.stringify({ index: 'customers', text: words.join(' '), size: 8, highlight: false }),
    });

  return (found.hits ?? [])
    .map((h) => {
      const f = h.fields ?? {};
      return {
        id: String(h.id ?? ''),
        phone: String(f.phone ?? ''),
        name: f.name ? String(f.name) : undefined,
        // THE PLATE COMES BACK TOO, because the same document carries it (seams.py) — and in a
        // vehicle shop it is the only field the operator has actually looked at.
        plate: f.plate ? String(f.plate) : undefined,
      };
    })
    .filter((c) => c.phone || c.plate);
}

/** The full number has been typed. Answers `{customer: {...} | null}`. */
export function customerByPhone(
  session: Session, phone: string,
): Promise<{ customer: (CustomerHit & { subject_ref?: string }) | null }> {
  return call(session, `/api/v1/field/customers/by-phone?phone=${encodeURIComponent(phone)}`);
}

/**
 * What this customer is OWED, for the person standing in front of him.
 *
 * THE OFFER IS AN ENTITLEMENT, NOT A POSTER (§5.6.2). It was sent to him and nobody else, it has
 * an expiry, and the only place it can actually be honoured is the counter — so the worker taking
 * the visit has to see it without being told to look. Everything else about the offer was built:
 * the send log records it, the customer's page counts down to it, the owner reads it on the
 * customer record. This screen, the one where it is redeemed, showed nothing.
 *
 * `subject_ref` IS THE PSEUDONYM, not the phone. reminders holds no names by design, so this is
 * the only handle it answers to — and it arrives on the by-phone lookup for exactly this.
 */
export interface FieldOffer {
  text?: string;
  expires_at?: number;
  service_ids?: string[];
  /** The code the customer reads off his phone — shown so both sides quote the same string. */
  code?: string;
}

export async function offerFor(session: Session, subjectRef: string): Promise<FieldOffer | null> {
  const q = new URLSearchParams({ subject_ref: subjectRef });
  const out = await call<{ offer: FieldOffer | null }>(
    session, `/api/v1/reminders/offer?${q.toString()}`);
  return out.offer ?? null;
}

/**
 * HIS POINTS, AND WHAT THEY CAN BUY — read at the counter, spent at the counter.
 *
 * `rewards` IS ONLY WHAT THIS BALANCE AFFORDS. The service filters before answering, deliberately:
 * a sheet listing everything and greying out most of it turns a moment of goodwill into a list of
 * things he cannot have. `to_next_reward` carries the encouragement instead, and it is 0 when
 * there is nothing useful to say — either he can afford everything or the shop has no rewards, and
 * «تبقى لك 0 نقطة» is a sentence that means nothing to the person reading it.
 */
export interface FieldReward {
  id: string;
  name: string;
  cost: number;
  type?: string;
  /** The service this reward IS, when it is one — «غسلة مجانية» is the wash (§9.4). The badge on
   *  the tile needs it, and the route has always sent it. */
  service_id?: string;
}
export interface Balance {
  points: number;
  rewards: FieldReward[];
  to_next_reward: number;
  expires_at?: number;
}

/**
 * What each service EARNS — the shop's own earning rules, three levels deep.
 *
 * READ ONCE PER ENTRY TO THE SCREEN, not per customer: this is the shop's configuration and does
 * not change between two visits a minute apart. It is what lets the operator say «هذي تجيب لك 5
 * نقاط» while his hand is on the tile — the sentence that makes a loyalty programme exist outside
 * the database.
 */
export interface EarnSettings {
  general?: { points?: number };
  groups?: Record<string, { points?: number }>;
  services?: Record<string, { points?: number }>;
  service_group?: Record<string, string>;
  /**
   * THE PLATFORM'S OWN FLOOR, AND THE LEVEL THIS TYPE USED TO OMIT.
   *
   * loyalty resolves a number over FOUR levels — service, its group, the shop's general figure,
   * then this — and nothing is written into a shop at signup on purpose: a service stores only
   * what its owner overrode, so raising the general figure later actually moves every service
   * that was following it. (Copy the number in at signup and it looks identical on day one, then
   * the owner raises the general number on day thirty, twenty services keep their copies, nothing
   * changes and nothing errors — see loyalty/core/earning.py.)
   *
   * The server sent `defaults` all along. This type did not name it, so `pointsByService`
   * resolved three levels and fell to 0 — and the grid hides a badge at 0, which is why a new
   * shop's tiles showed no points while the API was answering 10.
   */
  defaults?: { points?: number };
}

export function earnSettings(session: Session): Promise<EarnSettings> {
  return call(session, '/api/v1/loyalty/settings');
}

/**
 * The effective number for every service — service, then its group, then general (§9.2).
 *
 * INHERITED IS SHOWN, NOT HIDDEN. Resolving only the explicit per-service values would print a
 * number on the three tiles somebody customised and nothing on the rest, which reads as "these
 * three earn points and the others do not" — the opposite of what the shop configured.
 */
export function pointsByService(earn: EarnSettings | null, ids: string[]): Record<string, number> {
  if (!earn) return {};
  const out: Record<string, number> = {};
  for (const id of ids) {
    const own = earn.services?.[id]?.points;
    if (own !== undefined) { out[id] = own; continue; }
    const group = earn.service_group?.[id];
    const fromGroup = group ? earn.groups?.[group]?.points : undefined;
    // FOUR LEVELS, IN THE SERVER'S OWN ORDER — service, group, the shop's general, the platform
    // default. Stopping at three made every shop that had customised nothing look like a shop
    // where nothing earns.
    out[id] = fromGroup ?? earn.general?.points ?? earn.defaults?.points ?? 0;
  }
  return out;
}

export function balanceFor(session: Session, subjectRef: string): Promise<Balance> {
  return call(session, `/api/v1/loyalty/balance/${encodeURIComponent(subjectRef)}`);
}

/**
 * Spend the points.
 *
 * THE KEY IS REQUIRED BY THE ROUTE and minted here, at the press. A field phone retries, and a
 * retry without a key is a second spend the customer holds a receipt for.
 *
 * NO `branch_id`, AND THE PARAMETER IS GONE. This used to take one, on the reasoning that only the
 * screen knows where it is standing. The screen does not: nothing in this app ever asked, no caller
 * ever passed one, and every redemption made from here was filed under «غير محدَّد» — while the
 * till's were filed correctly, so «أيّ فرع يصرف أكثر؟» was answered from half the shop.
 *
 * The branch is a fact about the PERSON, and loyalty now resolves it from his operator row, the
 * same way the visit path always has (spec 12.2). Sending one from here would be a value nobody
 * could check.
 */
export function redeem(
  session: Session, subjectRef: string, rewardId: string,
): Promise<{ balance?: number; entry_id?: string; message?: string }> {
  return call(session, '/api/v1/loyalty/redeem', {
    method: 'POST',
    body: JSON.stringify({
      subject_ref: subjectRef,
      reward_id: rewardId,
      idempotency_key: newIdempotencyKey(),
    }),
  });
}

/**
 * Apply the offer to this visit — the tap that turns a message into a fact.
 *
 * NOTHING SPENDS AN OFFER AUTOMATICALLY. A customer who came in for something else and was
 * silently charged an offer he was saving is a customer we took something from; he may be holding
 * it for next month, and that is his to decide. So the only thing that consumes one is a person
 * pressing a button in front of him.
 *
 * AND IT IS ALSO THE ONLY MOMENT WE LEARN THE OFFER WORKED — the join between a campaign and the
 * visit it produced exists nowhere else.
 */
export function applyOffer(
  session: Session, subjectRef: string, visitId: string,
): Promise<{ applied: boolean; reason?: string }> {
  // ON THE VISIT, NOT ON THE OFFER (§5.6.2). The spend is recorded where it happened — the send
  // log is append-only and every message cap is counted against it — and the services come off
  // the visit itself rather than from this screen, so the two can never disagree.
  return call(session, `/api/v1/field/visits/${encodeURIComponent(visitId)}/offer`, {
    method: 'POST',
    body: JSON.stringify({ subject_ref: subjectRef }),
  });
}

/**
 * Whose car this is — the lookup a vehicle shop starts from.
 *
 * IT SAVES THE OPERATOR A QUESTION HE SHOULD NOT HAVE TO ASK. The plate is on the bumper; the
 * number of the man who owns it is already ours. Asking for it again on every visit is asking
 * something we can answer, with a customer standing there.
 */
export function customerByPlate(
  session: Session, plate: string,
): Promise<{ customer: CustomerHit & { subject_ref?: string } | null }> {
  return call(session, `/api/v1/field/customers/by-plate?plate=${encodeURIComponent(plate)}`);
}

/** The strip along the top — today's customers, one tap away. */
export function recentCustomers(session: Session, limit = 10): Promise<{ customers: CustomerHit[] }> {
  return call(session, `/api/v1/field/customers/recent?limit=${limit}`);
}

// ── the visit ──────────────────────────────────────────────────────────────────────────────────

export interface VisitDraft {
  phone: string;
  service_ids: string[];
  name?: string;
  plate?: string;
  meter?: number;
  custom_service?: string;
  /**
   * MINTED ON THE DEVICE, ONE PER ENTRY ON THE SCREEN — and it is a BODY FIELD, not a header.
   *
   * Two taps on a slow button, a retry after a timeout, and a queued visit replayed when the
   * network returns are all the same visit; without this they become two records, two reminders
   * and two messages somebody pays for. It cannot be server-side, because a server cannot tell a
   * double tap from a customer who genuinely came back an hour later.
   */
  idempotency_key: string;
}

export interface VisitAck {
  visit: { id: string; [k: string]: unknown };
  customer: CustomerHit;
  created_customer: boolean;
  /** A repeat of the same key answers 201 with this true — a SUCCESS, not a conflict. The operator
   *  wanted one visit and there is one visit; a 409 on a double tap teaches him the screen lies. */
  duplicate: boolean;
}

export function recordVisit(session: Session, draft: VisitDraft): Promise<VisitAck> {
  return call<VisitAck>(session, '/api/v1/field/visits', {
    method: 'POST',
    body: JSON.stringify(draft),
  });
}

// ── before there is a session ──────────────────────────────────────────────────────────────────

/** A sector a new shop may choose. Key and label only — see the route for why it is not the
 *  platform's fuller listing. */
export interface Sector {
  key: string;
  label: string;
}

/**
 * THE ONE READ THAT CARRIES NO TOKEN, and it is here rather than in auth.ts because it is a read
 * of ordinary product data — the sectors we sell to — rather than part of proving who anyone is.
 *
 * A failure answers an empty list, and the form then has nothing to offer: better than a hardcoded
 * pair that keeps working while the real catalogue has three, which is the failure nobody notices
 * until an owner asks for the sector he saw on the website.
 */
export async function listSectors(): Promise<Sector[]> {
  const res = await fetch(`${BASE}/api/v1/signup/sectors`);
  if (!res.ok) throw new ApiError(res.status, null, 'sectors');
  const body = (await res.json()) as { sectors?: Sector[] };
  return body.sectors ?? [];
}
