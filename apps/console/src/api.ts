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

// AR-ONLY, ON PURPOSE, NOT `translate()` FROM `./operator-i18n` — THAT MODULE IMPORTS THIS ONE
// (`getMyLocale`/`setMyLocale`), so importing it back here would be a real circular module
// dependency, not a stylistic one (confirmed live: it broke `registerOperatorStrings` at import
// time — CATALOGS not yet initialized when this module's own side-effect import ran). These are
// only the DEFAULT for a caller that has no live `t` in scope (this file's own tests, and the one
// direct throw below); every real render site still passes its own `t` from context, and the same
// keys are registered for every locale in `./api-i18n` — imported from `App.tsx` instead, which
// nothing here is on the other end of a cycle with.
const AR_DEFAULT: Record<string, string> = {
  'api.sessionExpired': 'انتهت الجلسة — أعد فتح الشاشة.',
  'api.serviceDown': 'الخدمة لا تستجيب الآن. حاول بعد قليل.',
  'api.noConnection': 'لا يوجد اتصال — تحقّق من الشبكة وحاول مرة أخرى.',
  'api.searchUnavailable': 'تعذّر البحث الآن — حاول بعد لحظات',
};

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
export function sentenceFor(
  e: unknown, fallback: string, t: (key: string) => string = (k) => AR_DEFAULT[k] ?? k,
): string {
  if (e instanceof ApiError) {
    const body = e.body as { message?: string; detail?: string; reason?: string } | null;
    // THE PEER'S OWN WORDS FIRST. `reason` is the key our services answer refusals with; `message`
    // and `detail` are the platform's. Whichever arrives, it was written for this person.
    const said = body?.message || body?.detail || body?.reason;
    if (said) return String(said);
    if (e.status === 401 || e.status === 403) return t('api.sessionExpired');
    if (e.status >= 500) return t('api.serviceDown');
    return fallback;
  }
  // A network failure is the NORMAL case in a workshop, not an exception — and it is the one
  // message that must not alarm.
  if (e instanceof TypeError) return t('api.noConnection');
  // A REQUEST THAT NEVER ANSWERED, not one that was refused — `fetchWithTimeout`'s own abort()
  // throws this, never an ApiError, because no response ever arrived to build one from. To the
  // person reading it, "nothing came back within 10 seconds" and "no connection" are the same
  // fact, so they get the same sentence rather than a raw "AbortError".
  if (e instanceof DOMException && e.name === 'AbortError') return t('api.noConnection');

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

// A REQUEST MUST NOT HANG FOREVER. Confirmed live under real concurrent load (load
// test): a request that never gets a reply — not rejected, not slow, just gone — leaves whichever
// screen made it sitting on its own "يُحمَّل…" skeleton indefinitely; the screen's own retry UI
// («تعذّر القراءة», a real button) never even appears, because nothing ever tells the screen the
// read failed. 10s is generous for anything this console actually calls, and short enough that a
// person waiting on a real counter is not staring at a spinner for a full minute first.
const REQUEST_TIMEOUT_MS = 10_000;

async function fetchWithTimeout(url: string, init: RequestInit): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

// A BURST-DENIED READ USUALLY CLEARS WITHIN A SECOND. Confirmed live: 429/503 under real
// concurrent load are transient — the same request seconds later succeeds once the burst passes.
// Retrying quietly, ONLY for a GET (never a write — a POST/PATCH must not be replayed just because
// this file decided to, idempotency keys or not; that decision belongs to the caller, not here),
// turns most of those into "a little slower" instead of the screen's own error state firing at
// all. Two extra tries, short and increasing backoff — enough to ride out a burst, not enough to
// turn a REAL outage into a long silent wait before the honest failure the screen already handles.
const TRANSIENT_RETRY_STATUSES = new Set([429, 503]);
const RETRY_DELAYS_MS = [400, 900];

async function fetchIdempotent(url: string, init: RequestInit): Promise<Response> {
  let res = await fetchWithTimeout(url, init);
  if ((init.method ?? 'GET') !== 'GET') return res;
  for (const delay of RETRY_DELAYS_MS) {
    if (!TRANSIENT_RETRY_STATUSES.has(res.status)) break;
    await new Promise((resolve) => setTimeout(resolve, delay));
    res = await fetchWithTimeout(url, init);
  }
  return res;
}

async function call<T>(session: Session, path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set('Authorization', `Bearer ${session.token}`);
  if (init.body) headers.set('Content-Type', 'application/json');
  let res = await fetchIdempotent(`${BASE}${path}`, { ...init, headers });
  if (res.status === 401) {
    // RENEW BEFORE DECLARING ANYTHING. The bearer is good for 15 minutes and the refresh token for
    // 31 days; on this screen especially — the one an operator keeps open all day at the counter —
    // a 401 almost always means the shift outlasted the token, not that the session ended.
    const token = await renew();
    if (token) {
      headers.set('Authorization', `Bearer ${token}`);
      res = await fetchIdempotent(`${BASE}${path}`, { ...init, headers });
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
  /** Minutes this service takes, for the booking dialog's own duration snapshot
   *  (docs/خطة-تنفيذ-الحجوزات.md §2/§4). 0 or absent means NOT CONFIGURED — never a guess. */
  duration_minutes?: number;
  /** Halalas. 0 or absent means no catalogue price is set — the booking dialog's own total then
   *  has nothing to suggest, which is an honest state and not an error. */
  price_minor?: number;
  /** WHO CAN ACTUALLY DO IT. Absent/empty = every active FIELD-ROLE operator (role === 'operator'
   *  — server-enforced, operations' own service-eligibility route, assignment-mode redesign phase
   *  2) — the booking dialog reads this to decide whether one merged operator step still covers
   *  every chosen service, or whether it has to expand into one row per service
   *  (docs/خطة-تنفيذ-الحجوزات.md's smart-scheduling plan). */
  eligible_staff_ids?: string[];
  /** NAMED vs AUTO (assignment-mode redesign, phase 1/3) — does the booking dialog ask "which
   *  operator" for this service at all. See Services.tsx's own Service.assignment_mode docstring
   *  for the full rule; this is the same field, read here rather than written. */
  assignment_mode?: 'named' | 'auto';
  /** Whether this service has a photo — never the photo itself; see `serviceImageUrl` below for
   *  why the bytes are a separate, authenticated request rather than a URL in this JSON. */
  has_image?: boolean;
}

/**
 * A named, priced GROUP of the shop's own services — «باقة العناية», not a single service.
 *
 * ONLY WHAT THE COUNTER TILE NEEDS. `Package.public()` on the server carries scheduling fields
 * too (starts_at/recurrence/…), which is why `/field/catalogue` filters to offerable-right-now
 * BEFORE this ever reaches the console (see `catalogue_packages`'s own docstring) — this screen
 * never re-derives "is this package on right now", it only ever sees packages that already are.
 */
export interface CataloguePackage {
  id: string;
  name: string;
  /** The services this package bundles — tapping the tile selects all of them at once. */
  service_ids: string[];
  /** Halalas. Owner-entered, never derived from summing the components (see the server's own
   *  Package docstring) — this is the number on the tile, not a computed total. */
  price_minor: number;
  description?: string;
  has_image?: boolean;
}

/** An extra input the visit sheet renders — the full descriptor, so this app never carries its
 *  own idea of what "plate" or "meter" means. */
export interface VisitField {
  name: string;
  label?: string;
  type?: string;
  required?: boolean;
}

/**
 * The grid AND the inputs, in one answer.
 *
 * WHICH FIELDS RENDER IS THE SERVER'S TO SAY, not this app's. The plate belongs to a shop that
 * works on cars and does not exist at all in a salon — not disabled, not empty, absent — and the
 * answer is a list of NAMES rather than a flag, so the screen asks «is `plate` among my fields»
 * and the day a second vehicle input is added no console release is needed.
 *
 * A shop that does not work on cars answers an empty list — which renders the phone and nothing
 * else, and is always valid.
 */
export function fetchCatalogue(
  session: Session,
): Promise<{
  services: CatalogueService[];
  /** Already filtered server-side to active AND offerable right now — see `catalogue_packages`'s
   *  own docstring. Absent-treated-as-empty by every caller, same as `fields` below, so an older
   *  cached response or a service that has not deployed this yet still renders correctly. */
  packages?: CataloguePackage[];
  tracks_vehicle: boolean;
  fields: VisitField[];
}> {
  return call(session, '/api/v1/field/catalogue');
}

/**
 * The photo itself, as a blob URL the caller puts straight into an `<img src>` and revokes when
 * done — same mechanism as `downloadUrl` in catalog.ts, duplicated rather than shared because that
 * one resolves its path from an `Action` in a manifest this screen (Visit.tsx, no `catalog` prop)
 * never loads. Read-gated (`operations.read`, not `operations.manage_services`) precisely so an
 * ordinary field operator — never a manager here — can load it; see field.py's own docstring on
 * `catalogue_service_image`/`catalogue_package_image` for why these are separate routes from the
 * manage-only ones Services.tsx/PackagesTab.tsx call.
 */
async function catalogueImageUrl(session: Session, path: string): Promise<string> {
  const bearer = session.token;
  let res = await fetch(`${BASE}${path}`, { headers: { Authorization: `Bearer ${bearer}` } });
  if (res.status === 401) {
    const token = await renew();
    if (token) res = await fetch(`${BASE}${path}`, { headers: { Authorization: `Bearer ${token}` } });
  }
  if (!res.ok) throw new ApiError(res.status, null, `GET ${path} → ${res.status}`);
  return URL.createObjectURL(await res.blob());
}

export function serviceImageUrl(session: Session, serviceId: string): Promise<string> {
  return catalogueImageUrl(
    session, `/api/v1/field/catalogue/services/${encodeURIComponent(serviceId)}/image`);
}

export function packageImageUrl(session: Session, packageId: string): Promise<string> {
  return catalogueImageUrl(
    session, `/api/v1/field/catalogue/packages/${encodeURIComponent(packageId)}/image`);
}

/**
 * FIXES THE ONE THING A BOOKING ACTUALLY REFUSES WITHOUT, FROM WHERE THE REFUSAL HAPPENED.
 *
 * The booking dialog used to send him away — "اضبطها من «خدماتي ومنتجاتي»" — to fix exactly the
 * duration this same screen already knows is missing, on the same service it is already showing
 * him. Same route Services.tsx's own edit row calls (`operations.update_service`); called by path
 * here because the dialog holds no `catalog` to resolve an action id from.
 */
export function setServiceDuration(
  session: Session, serviceId: string, minutes: number,
): Promise<unknown> {
  return call(session, `/api/v1/staff/services/${serviceId}`, {
    method: 'PATCH',
    body: JSON.stringify({ duration_minutes: minutes }),
  });
}

/** THE CATALOGUE'S OWN PRICE — explicit, and only ever called when he actually ticks "احفظ كسعر
 *  الخدمة". A booking's own `price_override_minor` (createBooking's draft) is a completely
 *  separate write; this one is the one that changes what every FUTURE booking of this service
 *  defaults to. */
export function setServicePrice(
  session: Session, serviceId: string, minor: number,
): Promise<unknown> {
  return call(session, `/api/v1/staff/services/${serviceId}`, {
    method: 'PATCH',
    body: JSON.stringify({ price_minor: minor }),
  });
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
  /** Denormalised on the Customer row itself (services/operations `Customer.public()`) — free,
   *  no extra join. Present on `operations.recent` and `operations.customers_by_refs` results;
   *  ABSENT on a search-service `suggest` hit, whose index carries only id/phone/name/plate. Never
   *  substitute a guess when it is missing — the row simply says less, honestly, for that source. */
  last_visit?: number;
  visit_count?: number;
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
  // OPERATIONS, NOT SEARCH-SERVICE (ط-3). This used to call the platform's two search routes
  // itself — `/suggest` for the terms and `POST /search` for the people — and neither of them
  // knows what a branch is. A supervisor scoped to Jeddah typed four digits and read Riyadh's
  // customers by name, number and plate, walking around every narrowing operations already had,
  // because the keypad never asked operations anything.
  //
  // AND THE FILTER COULD NOT LIVE HERE. Sending `filters: {branch_id: …}` from this file would
  // read like a guard and be none: the next caller sends whatever it likes, and a browser is not
  // a place a scope can be enforced. Operations resolves it from the token.
  //
  // The two-call dance and the «add the typed text» rule moved with it, comments and all — see
  // the route. What is left here is one request.
  const q = new URLSearchParams({ prefix });
  const out = await call<{ customers?: unknown[]; ok?: boolean }>(
    session, `/api/v1/field/customers/suggest?${q.toString()}`);
  // `ok: false` IS «WE COULD NOT ASK», NOT «NOBODY MATCHED». The caller draws a different sentence
  // for each, and telling a man at the counter he is not registered when the index was merely
  // unreachable is the one wrong answer this screen must never give.
  if (out.ok === false) throw new ApiError(503, out, AR_DEFAULT['api.searchUnavailable']);
  return (out.customers ?? [])
    .map((h) => {
      const f = (h ?? {}) as Record<string, unknown>;
      return {
        id: String(f.id ?? ''),
        phone: String(f.phone ?? ''),
        name: f.name ? String(f.name) : undefined,
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
 * Resolve or create a customer by phone, with NO visit attached.
 *
 * THE BOOKING DIALOG'S ONE STEP BEFORE IT HAS A `customer_id` TO GIVE BOOKINGS. Same act as
 * `recordVisit`'s own customer resolution (docs/خطة-تنفيذ-الحجوزات.md §6.2: "نفس الفعل
 * الخلفي الذي يستعمله VisitIn, لا إعادة تنفيذ") — never reimplemented here, only called.
 */
export function ensureCustomer(
  session: Session, phone: string, name?: string,
): Promise<{ customer: (CustomerHit & { subject_ref?: string }) | null; reason?: string }> {
  return call(session, '/api/v1/field/customers/ensure', {
    method: 'POST',
    body: JSON.stringify({ phone, name: name || undefined }),
  });
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
  /**
   * THE DISCOUNT ITSELF — «20%», «50 ريال» (أ-7).
   *
   * It was typed when the campaign was built, rendered into the message the customer is holding,
   * and then existed nowhere a person could read it again. `text` may be the owner's own line,
   * which does not have to restate the amount — so the operator's only source was the customer
   * telling him what his discount was.
   */
  value?: string;
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
  /** Whether a manager must put his name to this one before it may be handed over (spec §9.5).
   *  Computed by loyalty from the shop's own threshold, never by this app: the offer and the
   *  refusal have to come from the same rule, or the counter is offered a reward the tap then
   *  refuses with the customer already holding out his hand. */
  needs_approval?: boolean;
}
export interface Balance {
  points: number;
  rewards: FieldReward[];
  to_next_reward: number;
  expires_at?: number;
  /** Points from which approval is required. 0 means the owner set no such rule. */
  manager_threshold?: number;
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
  /**
   * THE KEY IS THE CALLER'S, AND IT HAS NO DEFAULT (د-12).
   *
   * This function used to mint one per CALL — `newIdempotencyKey()` on this line — so a retry was
   * a different redemption to the server. The phone loses signal after the request arrives: the
   * points are already spent, the screen says «تعذّر», the cashier presses again with the customer
   * watching, and the balance is deducted TWICE while two receipts go out.
   *
   * The key must be minted where the INTENT is — at the press — and be the same on every retry of
   * that intent, exactly as the visit queue mints one and keeps it. A default here would let the
   * next screen forget again, silently, and the failure would only appear on a bad connection.
   */
  idempotencyKey: string,
  approvedBy = '',
): Promise<{ balance?: number; entry_id?: string; message?: string }> {
  return call(session, '/api/v1/loyalty/redeem', {
    method: 'POST',
    body: JSON.stringify({
      subject_ref: subjectRef,
      reward_id: rewardId,
      idempotency_key: idempotencyKey,
      // WHO ALLOWED IT — and no screen in this app ever sent it. loyalty refuses any reward at or
      // above the shop's threshold without a name, so the owner who set that rule watched every
      // expensive reward be refused with no box anywhere to type the name into. Empty on the
      // ordinary redemption, which is most of them; the service decides whether that is allowed.
      approved_by: approvedBy,
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

/** One recorded service event — a WALK-IN, not a booking. Its own model in operations, with no
 *  relationship to `Booking` at all unless it was created by attending one (see `Booking.
 *  visit_id`) — that link runs one way, from the booking, and this record never carries a
 *  `booking_id` back. `services` is already joined to real names server-side; never `زيارة` for a
 *  named service. */
export interface VisitRecord {
  id: string;
  customer_id: string;
  service_ids: string[];
  services: string;
  branch_id: string;
  occurred_at: number;
  note: string;
  custom_service: string;
}

/** "متى كان آخر مرة جاء؟" — the record an operator opens to answer exactly that. Branch-scoped by
 *  the route itself (a supervisor over one branch reads only that branch's visits on this same
 *  customer, per `SCOPE.visible` server-side), never a second filter needed here. */
export function customerRecord(session: Session, customerId: string): Promise<{
  customer: CustomerHit; visits: VisitRecord[];
}> {
  return call(session, `/api/v1/field/customers/${encodeURIComponent(customerId)}`);
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
  /**
   * WHEN HE PRESSED SAVE — seconds, his clock (أ-3).
   *
   * The queue held this all along and never sent it, so a morning of visits taken with no coverage
   * were all stamped with the moment the network returned: «أوقات الذروة» named the reconnection,
   * and the visit confirmation reached the customer hours after he had gone. The server bounds
   * what a device clock may claim; what it cannot do is recover a time it was never told.
   */
  occurred_at?: number;
  /**
   * WHO SAVED IT, and the proof that the name is his to use (أ-2, و-4).
   *
   * The door has accepted `operator_id` since it was written and no screen has ever sent one — so
   * every visit taken on a phone had no operator on it, and `_branch_for` reads exactly this field
   * to decide which BRANCH the work belongs to. The branch comparison table was a column of zeros,
   * `last_branch_id` was never written so a branch campaign found nobody, and «من صرف نقاط هذا
   * العميل» had no answer. Empty is honest and means «nobody proved who this was»; what is refused
   * is a name without its ticket.
   */
  operator_id?: string;
  operator_ticket?: string;
  /** SET ONLY WHEN HE SOLD A PACKAGE — `service_ids` above still carries its component services
   *  either way, so the visit itself never depends on this; it is purely the attribution loyalty
   *  reads to price the visit by the package's own value instead of summing the components
   *  (services/operations `Visit.package_id`'s own docstring). A forged/unknown id is dropped
   *  server-side rather than trusted, so sending one is never a way to fake a visit's contents. */
  package_id?: string;
  /** SHOP-TO-SHOP COUPON, RIDING ON THIS VISIT — all four absent/empty means "no grant
   *  attempted", the ordinary case. See operations' own `field.py::VisitIn` — the grant is
   *  attempted only after the visit itself is safely recorded, and never blocks or fails it. */
  coupon_phone?: string;
  coupon_percent?: number;
  coupon_general?: boolean;
  coupon_app_keys?: string[];
  /** HOW MANY OF EACH — "2× غسيل خارجي", exactly like an integrated till's own line quantity
   *  (services/operations `field.py::VisitIn.quantities`). A service missing here means one; this
   *  is never a second way to select a service, only a count on one already in `service_ids`. */
  quantities?: Record<string, number>;
}

export interface VisitAck {
  visit: { id: string; [k: string]: unknown };
  customer: CustomerHit;
  created_customer: boolean;
  /** A repeat of the same key answers 201 with this true — a SUCCESS, not a conflict. The operator
   *  wanted one visit and there is one visit; a 409 on a double tap teaches him the screen lies. */
  duplicate: boolean;
}

/** A name the field sheet can offer. `has_pin` is what makes it offerable at all. */
export interface FieldOperator {
  id: string;
  name: string;
  active: boolean;
  has_pin: boolean;
  /** Empty means unbranched — visible to every branch, the same rule operations' own staff route
   *  documents. Read by the booking dialog's staff picker (§6, docs/خطة-تنفيذ-الحجوزات.md). */
  branch_id?: string;
  /** Team.tsx's own ROLES value ('operator'|'supervisor'|'marketer'|'manager') — 'operator' is
   *  «الموظف الميداني», the one role the server auto-includes in an unrestricted service's
   *  eligible set (assignment-mode redesign phase 2). */
  role?: string;
}

export async function listOperators(session: Session): Promise<FieldOperator[]> {
  const out = await call<{ operators?: FieldOperator[] }>(session, '/api/v1/staff/operators');
  return (out.operators ?? []).filter((o) => o.active && o.has_pin);
}

// ── لغة الحساب (operator-i18n.tsx) — PLATFORM-WIDE, أي حساب مسجّل دخول، المالك ضمناً ───────────
//
// USED TO BE OPERATOR-ONLY (`getMyOperator`/`setMyOperatorLocale` against
// `/api/v1/staff/operators/me/locale`) — an owner holds no Operator row at all, so that route
// 404s for him structurally, and the console had to hide its own language switch for him because
// of it (2026-09-11 audit finding). `/api/v1/account/me/locale` needs nothing but a valid token —
// no capability, no Operator row — and the backend carries forward an already-saved operator
// locale the first time it is read, so nobody's existing preference resets silently.

interface MyLocaleRow {
  locale?: string;
}

export async function getMyLocale(session: Session): Promise<MyLocaleRow> {
  return call<MyLocaleRow>(session, '/api/v1/account/me/locale');
}

export async function setMyLocale(session: Session, locale: string): Promise<void> {
  await call(session, '/api/v1/account/me/locale', {
    method: 'PATCH', body: JSON.stringify({ locale }),
  });
}

// ── الإشعارات (rating-app-feature.md phase 8) ──────────────────────────────────────────────────
//
// notification-service's OWN in-app feed — the read/write side any of our services already write
// into via POST /internal/notify (channel=inapp), gated `require_user` only, no capability: every
// signed-in account reads its own feed, same as `/account/me/locale` above. `InAppItem` (the real
// stored shape) carries only `id`/`title`/`body`/`read`/`ts` — no severity, no icon, no category,
// no action link. The console's OWN rendering (NotificationBell.tsx) does not invent fields the
// backend never sends; it presents exactly this, well.

export interface NotificationItem {
  id: string;
  title: string;
  body: string;
  read: boolean;
  ts: string;
}

export async function listNotifications(session: Session): Promise<NotificationItem[]> {
  const out = await call<{ items?: NotificationItem[] }>(session, '/api/v1/notifications');
  return out.items ?? [];
}

export async function markNotificationRead(session: Session, id: string): Promise<void> {
  await call(session, `/api/v1/notifications/${encodeURIComponent(id)}/read`, { method: 'POST' });
}

// ── الحجوزات (docs/خطة-تنفيذ-الحجوزات.md §6) ───────────────────────────────────────────────────

/** A name the booking dialog can offer — active staff, whichever branch they work in.
 *
 * NOT `listOperators` ABOVE. That list is filtered to `has_pin` — the visit screen's own «من
 * يحفظ؟» sheet needs a PIN to attribute a save; a booking is attributed by WHO IS SIGNED IN, and
 * requiring a PIN here would hide every operator who has never been given one, on the one screen
 * that is meant to reuse `Operator.id` exactly as VisitIn does (وصف-تطبيق-الحجوزات.md §6.2).
 */
export async function listBookingStaff(session: Session): Promise<FieldOperator[]> {
  const out = await call<{ operators?: FieldOperator[] }>(session, '/api/v1/staff/operators');
  return (out.operators ?? []).filter((o) => o.active);
}

/** One row of the grid, or one booking dialog's answer — the server's own shape (`Booking.public()`). */
export interface Booking {
  id: string;
  branch_id: string;
  operator_id: string;
  customer_id: string;
  service_ids: string[];
  starts_at: number;
  duration_minutes: number;
  status: 'booked' | 'attended' | 'no_show' | 'cancelled';
  visit_id: string | null;
  /** "بدون عربون بعربون او مدفوع" — one field, three states, never inferred
   *  from `status`: an attended booking can still owe money, and a booked one can already be
   *  paid in full days ahead. */
  payment_status: 'none' | 'deposit' | 'paid';
  /** Required whenever `payment_status` is `'deposit'`, `null` otherwise — «مدفوع» needs no
   *  amount of its own; the booking's own price already says what was owed. */
  deposit_amount_minor: number | null;
  /** THIS booking's own price, when it was negotiated away from the catalogue's — never a write
   *  to the service itself. `null` means "whatever the catalogue says". */
  price_override_minor: number | null;
  /** A reward he asked for AT BOOKING TIME, spent only at attend() — never here: the intent to
   *  redeem is recorded up front, but the redemption itself is not immediate. Still set on an
   *  ATTENDED booking means the spend failed or needed an approval nobody automated could give —
   *  redeem him by hand from the visit screen. `null` means either "never asked" or "already spent". */
  intended_reward_id: string | null;
  note: string;
  reason_no_show: string | null;
  created: number;
  created_by: string;
  updated: number;
  cancelled_reason: string | null;
  thumb_up: boolean | null;
  rev: number;
  /** HOW MANY OF EACH — "2× غسيل خارجي", a snapshot recomputed the same two moments
   *  `duration_minutes` is (create, and an explicit services edit). Missing entry means one. */
  quantities?: Record<string, number>;
}

/** One weekday's own policy. `0`=Monday..`6`=Sunday — `date.weekday()`'s own numbering, the same
 *  one the server's `availability.Schedule` already uses, so no translation happens at the wire. */
export interface DayHours {
  closed: boolean;
  start_minute: number;
  end_minute: number;
}
export type WeeklyHours = Record<string, DayHours>;

/** The shop's own weekly policy — ONE per tenant, every branch shares it.
 *  Unconfigured reads as 08:00-22:00 every day, the same honest default the server always used. */
export function workingHours(session: Session): Promise<{ weekly: WeeklyHours }> {
  return call(session, '/api/v1/bookings/working-hours');
}

/** `bookings.manage` only — a 403 here is expected for most staff and the caller shows it as a
 *  sentence, not a crash. */
export function setWorkingHours(
  session: Session, weekly: WeeklyHours,
): Promise<{ weekly: WeeklyHours }> {
  return call(session, '/api/v1/bookings/working-hours', {
    method: 'PATCH', body: JSON.stringify({ weekly }),
  });
}

/** The shop's own "auto" tie-breaker (assignment-mode redesign, phase 2/3) — which of an "auto"
 *  service's several free, eligible operators actually gets a given slot. `manual_order` only
 *  means anything when `algorithm === 'manual_order'`; carried regardless so switching TO manual
 *  later does not lose a lineup set earlier. Not in the action catalog (same as `workingHours`
 *  above) — a plain fetch, not `action(catalog, ...)`. */
export interface AssignmentSettings {
  algorithm: 'nearest' | 'least_loaded' | 'manual_order';
  manual_order: string[];
}
export function assignmentSettings(session: Session): Promise<AssignmentSettings> {
  return call(session, '/api/v1/bookings/assignment-settings');
}

/** `bookings.manage` only, same gate `setWorkingHours` uses. */
export function setAssignmentSettings(
  session: Session, settings: AssignmentSettings,
): Promise<AssignmentSettings> {
  return call(session, '/api/v1/bookings/assignment-settings', {
    method: 'PATCH', body: JSON.stringify(settings),
  });
}

/** The grid's own read — every booking for one branch, one business day. `date` is `YYYY-MM-DD`,
 *  the shop's own business day, exactly as `day_bucket()` computes it server-side. */
export function listBookings(
  session: Session, branchId: string, date: string,
): Promise<{ bookings: Booking[] }> {
  const q = new URLSearchParams({ branch_id: branchId, date });
  return call(session, `/api/v1/bookings?${q.toString()}`);
}

/** The month/year view's own read — how many bookings land on each day of a range, never the
 *  bookings themselves (docs/خطة-تصميم-تقويم-الحجوزات.md §1). `start`/`end` are `YYYY-MM-DD`,
 *  inclusive, the shop's own business-day buckets. Keys missing from `counts` mean zero, same as
 *  an explicit `0` — the caller should read a missing day as empty. */
export function fetchBookingCounts(
  session: Session, branchId: string, start: string, end: string,
): Promise<{ counts: Record<string, number> }> {
  const q = new URLSearchParams({ branch_id: branchId, start, end });
  return call(session, `/api/v1/bookings/counts?${q.toString()}`);
}

/** His own history, newest first — the customer page's own section (docs/وصف-تطبيق-الحجوزات.md
 *  §3: "مواعيده القادمة والسابقة، ونسبة حضوره"). Not branch-scoped: his history is his across
 *  every branch he was ever served at. */
export function bookingsForCustomer(
  session: Session, customerId: string,
): Promise<{ bookings: Booking[] }> {
  const q = new URLSearchParams({ customer_id: customerId });
  return call(session, `/api/v1/bookings/for-customer?${q.toString()}`);
}

export interface CreateBookingDraft {
  branch_id: string;
  operator_id: string;
  customer_id: string;
  service_ids: string[];
  /** HOW MANY OF EACH — see Booking.quantities. Ignored server-side on a package booking. */
  quantities?: Record<string, number>;
  starts_at: number;
  note?: string;
  idempotency_key?: string;
  payment_status?: 'none' | 'deposit' | 'paid';
  deposit_amount_minor?: number;
  /** THIS booking only — see Booking.price_override_minor. */
  price_override_minor?: number;
  intended_reward_id?: string;
}

export function createBooking(session: Session, draft: CreateBookingDraft): Promise<Booking> {
  return call(session, '/api/v1/bookings', { method: 'POST', body: JSON.stringify(draft) });
}

/** THE DRAG-AND-DROP IS THIS CALL (§6.1.1 من مستند القرارات) — Stage 7 reuses it unchanged. */
export function rescheduleBooking(
  session: Session, id: string, startsAt: number, operatorId?: string,
): Promise<Booking> {
  return call(session, `/api/v1/bookings/${encodeURIComponent(id)}/reschedule`, {
    method: 'PATCH',
    body: JSON.stringify({ starts_at: startsAt, operator_id: operatorId || undefined }),
  });
}

export function editBookingServices(
  session: Session, id: string, serviceIds: string[], quantities?: Record<string, number>,
): Promise<Booking> {
  return call(session, `/api/v1/bookings/${encodeURIComponent(id)}/services`, {
    method: 'PATCH',
    body: JSON.stringify({ service_ids: serviceIds, quantities: quantities ?? {} }),
  });
}

export function editBookingPayment(
  session: Session, id: string, paymentStatus: 'none' | 'deposit' | 'paid',
  depositAmountMinor?: number,
): Promise<Booking> {
  return call(session, `/api/v1/bookings/${encodeURIComponent(id)}/payment`, {
    method: 'PATCH',
    body: JSON.stringify({
      payment_status: paymentStatus,
      deposit_amount_minor: depositAmountMinor ?? undefined,
    }),
  });
}

export function editBookingReward(
  session: Session, id: string, rewardId: string | null,
): Promise<Booking> {
  return call(session, `/api/v1/bookings/${encodeURIComponent(id)}/reward`, {
    method: 'PATCH', body: JSON.stringify({ reward_id: rewardId }),
  });
}

export function editBookingNote(session: Session, id: string, note: string): Promise<Booking> {
  return call(session, `/api/v1/bookings/${encodeURIComponent(id)}/note`, {
    method: 'PATCH', body: JSON.stringify({ note }),
  });
}

export function cancelBooking(session: Session, id: string, reason?: string): Promise<Booking> {
  return call(session, `/api/v1/bookings/${encodeURIComponent(id)}/cancel`, {
    method: 'PATCH', body: JSON.stringify({ reason: reason || undefined }),
  });
}

/** ALLOWED even on a lapsed subscription (app/core/licence.py) — closing an existing booking's
 *  status is never the growing half. */
export function attendBooking(session: Session, id: string, occurredAt?: number): Promise<Booking> {
  return call(session, `/api/v1/bookings/${encodeURIComponent(id)}/attend`, {
    method: 'PATCH', body: JSON.stringify({ occurred_at: occurredAt || undefined }),
  });
}

export function noShowBooking(session: Session, id: string, reason?: string): Promise<Booking> {
  return call(session, `/api/v1/bookings/${encodeURIComponent(id)}/no-show`, {
    method: 'PATCH', body: JSON.stringify({ reason: reason || undefined }),
  });
}

/** A number beside her name, never a verdict (docs/وصف-تطبيق-الحجوزات.md §2.6) — how many of her
 *  last five CLOSED appointments she did not attend. */
export interface NoShowRisk {
  considered: number;
  no_shows: number;
  risky: boolean;
  /** The shop's own configured cutoff (config, not a constant), so the
   *  screen can say the actual percentage rather than a bare "خطر" nobody can act on. */
  threshold_percent: number;
}
export function noShowRisk(session: Session, customerId: string): Promise<NoShowRisk> {
  const q = new URLSearchParams({ customer_id: customerId });
  return call(session, `/api/v1/bookings/risk?${q.toString()}`);
}

/** The "أقرب موعد" button (§6.2) — `null` when nothing is free in the search window. */
export function nearestSlot(
  session: Session, branchId: string, operatorId: string, serviceIds: string[], after: number,
  /** The booking being RESCHEDULED, when there is one — its own current hour must not read as
   *  taken while searching for a new one for it. Omitted for a brand-new booking. */
  excludeBookingId?: string,
  /** HOW MANY OF EACH — a search for "2× غسيل خارجي" needs a slot twice as long. Sent as a JSON
   *  object string (`bookings.py::_parse_quantities`'s own note) since a query string carries no
   *  dict natively, same reasoning `service_ids` going comma-separated already gives. */
  quantities?: Record<string, number>,
): Promise<{ starts_at: number | null }> {
  const q = new URLSearchParams({
    branch_id: branchId, operator_id: operatorId, service_ids: serviceIds.join(','),
    after: String(after),
  });
  if (excludeBookingId) q.set('exclude_booking_id', excludeBookingId);
  if (quantities && Object.keys(quantities).length > 0) q.set('quantities', JSON.stringify(quantities));
  return call(session, `/api/v1/bookings/nearest?${q.toString()}`);
}

/** The «أي متاح» merge (Phase 0) — ONE call across every eligible operator, replacing the old
 *  per-operator sequential loop this used to be built from in BookingDialog.tsx. Each returned
 *  slot names the operator it actually belongs to. */
export function nearestSlotsAny(
  session: Session, branchId: string, operatorIds: string[], serviceIds: string[],
  after: number, windowEnd: number, maxSlots: number,
  excludeBookingId?: string,
  quantities?: Record<string, number>,
): Promise<{ slots: { operator_id: string; starts_at: number }[] }> {
  const q = new URLSearchParams({
    branch_id: branchId, operator_ids: operatorIds.join(','), service_ids: serviceIds.join(','),
    after: String(after), window_end: String(windowEnd), max_slots: String(maxSlots),
  });
  if (excludeBookingId) q.set('exclude_booking_id', excludeBookingId);
  if (quantities && Object.keys(quantities).length > 0) q.set('quantities', JSON.stringify(quantities));
  return call(session, `/api/v1/bookings/nearest-any?${q.toString()}`);
}

/**
 * Confirm who is saving, and come back with the PROOF — not just the name.
 *
 * The route has existed since the field screen did and nothing has ever called it (أ-2). A name
 * without this ticket is refused at the door, which is the point: `operator_id` decides which
 * BRANCH the visit is filed under, so a free string there moves a shop's numbers between cities.
 */
export function verifyPin(
  session: Session, operatorId: string, pin: string,
): Promise<{ operator: { id: string; name: string }; ticket: string; ticket_ttl: number }> {
  return call(session, '/api/v1/staff/operators/verify-pin', {
    method: 'POST',
    body: JSON.stringify({ operator_id: operatorId, pin }),
  });
}

export function recordVisit(session: Session, draft: VisitDraft): Promise<VisitAck> {
  return call<VisitAck>(session, '/api/v1/field/visits', {
    method: 'POST',
    body: JSON.stringify(draft),
  });
}

// ── the "?" icon — a direct, anchor-keyed lookup, no ranking and no model ──────────────────────
//
// assistant-service's `by_anchor()` (app/core/retrieval.py) matches an entry's `anchor` field
// EXACTLY — never its `id`, and catalog-generated entries never set one (only hand-authored KB
// entries do, KB_SOURCE_DRIVER=composite/file). So this 404s for every anchor until Phase 4 (the
// shop platform's own hand-authored glossary) actually writes one with a matching `anchor`. That
// is expected, not a bug: `fetchAssistantHelp` returns `null` on a 404 rather than throwing, and
// AssistantHint.tsx treats "nothing yet" as its own quiet state, never an error banner.
export interface AssistantHelpEntry {
  id: string;
  anchor: string;
  title: string;
  body: string;
  kind: string;
  related: string[];
}

// ── the chat — a typed question, ranked and answered (Phase 6) ─────────────────────────────────
//
// STATELESS PER TURN, ON THE SERVER'S OWN DESIGN: POST /ask takes only `question` (no
// conversation_id — see app/api/v1/assistant.py's own AskIn model), so there is no server-side
// multi-turn context to thread. A "conversation" on screen is a client-side running list of
// independent Q&A turns; the server still records each one (assistant.message_attributed) for
// history, independent of what the screen shows.
export interface AssistantAnswer {
  answer: string;
  message_id: string;
  grounded: boolean;
  citations: { ref: string; entry_id: string; title: string }[];
  actions: { id: string; label: string; method: string; path: string; service: string; capability: string }[];
  abstained_because: string;
  searched: number;
  redacted: string[];
}

export function askAssistant(
  session: Session, question: string, surface: string,
): Promise<AssistantAnswer> {
  return call<AssistantAnswer>(session, '/api/v1/assistant/ask', {
    method: 'POST',
    body: JSON.stringify({ question, surface }),
  });
}

export async function fetchAssistantHelp(
  session: Session, anchor: string,
): Promise<AssistantHelpEntry | null> {
  try {
    return await call<AssistantHelpEntry>(
      session, `/api/v1/assistant/help?anchor=${encodeURIComponent(anchor)}`);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
}

// ── before there is a session ──────────────────────────────────────────────────────────────────

