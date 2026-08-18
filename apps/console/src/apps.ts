/**
 * The app registry — one place that answers "what does this platform sell, and where does it show".
 *
 * WHY THIS EXISTS BEFORE THE APPS DO. The product is moving from four plans to apps a shop buys
 * one by one, and the ones already sold (campaigns, points, the engine, the link) are only the
 * first four. Invoicing and CRM are coming, and after them things nobody has named yet.
 *
 * THE FAILURE THIS PREVENTS is not a bug — it is a screen that stops making sense. If each new app
 * arrives as its own island, the owner ends up with six places that each know part of his
 * customer: one for visits, one for points, one for invoices, one for the CRM stage. He then has
 * to hold the customer together in his head, which is the exact job the product was bought to do.
 *
 * SO AN APP NEVER BRINGS ITS OWN WORLD. It declares two things and no more:
 *
 *   `section`  — the one place in the rail it owns, if it owns one at all;
 *   `onCustomer` — what it adds INSIDE the customer's page. Not a page beside it.
 *
 * The base — the customer, the visit, the catalogue — belongs to everybody and is never locked. An
 * app plugs into it; it does not sit next to it.
 *
 * THE ORDER IS THIS FILE'S, NOT EACH SCREEN'S. The same rule as the reason registry: the list is
 * the authority, screens read it, and adding an app is a row here rather than an `if` in four
 * files that will disagree within a month.
 */

/** What a shop holds, as billing answers it. `null` while the answer has not arrived. */
import { isDenied, isReady, type Loading } from './loading';
export interface Owned {
  checked: boolean;
  message: string;
  keys: string[];
  apps: { key: string; name: string; what: string; screen: string; owned: boolean | null;
          /** When THIS app's own subscription renews. `null` when he does not hold it, or when
           *  billing could not be read — «لا أعرف» and «لا يتجدّد» are different sentences. */
          renews_at: number | null }[];
  /** THE BASE SUBSCRIPTION ITSELF — its plan, its status and when it renews, straight from
   *  billing's subscription list. `null` when this shop has no base. It replaced a `feature.base`
   *  entitlement flag, which could say only THAT one existed: «يتجدّد في 12 سبتمبر» is the first
   *  thing an owner opening «الاشتراك» wants, and a boolean could never carry it. */
  base?: { plan_id: string; status: string; renews_at: number } | null;
}

export interface AppRow {
  id: string;
  /** The entitlement key, or null for the base — which is everything a subscription includes. */
  key: string | null;
  name: string;
  /** What it does for HIS shop. Never the tier: "this is in a higher plan" is a fact about our
   *  price list, and «نكتشف الخدمات التي تُطلب معاً» is a fact about him. */
  what: string;
  /** The nav section id it owns, from nav.ts. Empty when it only adds to existing screens. */
  section: string;
  /** What it contributes inside the customer's page — the seam every future app uses. */
  onCustomer: string;
}

export const APP_ROWS: AppRow[] = [
  {
    id: 'base',
    key: null,
    name: 'الأساس',
    what: 'عملاؤك وزياراتهم وخدماتك، وتأكيد الزيارة والتذكير بها، وربط صندوقك.',
    section: '',
    onCustomer: 'الزيارات، والخدمات التي أخذها',
  },
  {
    id: 'campaigns',
    key: 'feature.campaigns',
    name: 'الحملات',
    what: 'ترسل عرضاً أو خبراً لمجموعة من عملائك، ويقيس النظام مَن رجع بسببه.',
    section: 'messages',
    onCustomer: 'العروض التي وصلته، وما استهلكه منها',
  },
  {
    id: 'loyalty',
    key: 'feature.loyalty',
    name: 'برنامج النقاط',
    what: 'نقاطٌ على كل زيارة، ومكافآت يستبدلها العميل من صفحته أو عند الصندوق.',
    section: 'points',
    onCustomer: 'رصيده، وما يستطيع استبداله',
  },
  {
    id: 'bookings',
    key: 'feature.bookings',
    name: 'الحجوزات',
    what: 'حجزٌ بالوقت لكل عميلة، لموظفةٍ بعينها — وحضورها يفتح زيارتها تلقائياً.',
    section: 'bookings',
    onCustomer: '',
  },
  {
    id: 'insights',
    key: 'feature.insights.engine',
    name: 'فرصي',
    what: 'يقول لك أين الفرصة: أي خدمتين تُطلبان معاً، ومن كان سيشتري أكثر، وأثر رسائلك.',
    // NO SECTION OF ITS OWN, and that is the pattern to copy. «محلّي» is free for every shop —
    // it is what sells everything else — and the engine locks three cards INSIDE it. An app that
    // hid the whole section would hide the argument for buying it.
    section: '',
    onCustomer: '',
  },
];

/** The key that locks a nav section, or null when the section belongs to the base. */
export function keyForSection(sectionId: string): string | null {
  const row = APP_ROWS.find((a) => a.section === sectionId);
  return row ? row.key : null;
}

/**
 * May this shop use that app?
 *
 * THREE ANSWERS, NEVER TWO — the whole reason the backend reports `checked` separately. While the
 * answer has not arrived, and when billing could not be asked, this is `null`: the screen shows
 * neither the surface nor a lock, because telling a paying shop it has not paid is worse than
 * telling it to wait a moment. Nothing here is a security decision; the service refuses regardless.
 */
export function owns(owned: Loading<Owned>, key: string | null): boolean | null {
  if (key === null) return true;             // the base is not for sale separately
  // NOT HIS TO ASK is an answer, and it is «show him the surface». The catalogue simply does not
  // carry the entitlement read for a role that cannot buy — and the acts behind the surface are
  // gated by the services regardless, so drawing neither lock nor skeleton is both the honest and
  // the useful reading.
  if (isDenied(owned)) return true;
  if (!isReady(owned) || !owned.checked) return null;
  return owned.keys.includes(key);
}

/**
 * The base subscription's own state, as the four words a screen actually needs.
 *
 * WHY THIS EXISTS NOW AND NOT BEFORE. `owns(owned, null)` returns `true` for the base and says so
 * in a comment — «the base is not for sale separately». That was true while nothing enforced
 * `feature.base`. It stopped being true the day operations and reminders began refusing writes on
 * a lapsed month: the screen went on promising what the services had stopped promising, which is
 * this repository's oldest defect wearing a new shirt.
 *
 * `owns` IS LEFT ALONE ON PURPOSE. It answers «may he use this app», and for the base the answer
 * is still yes — he keeps reading his customers, his history and his messages when the month
 * lapses. What changed is that he may not ADD to them, and that is a different question, so it
 * gets a different function rather than a third meaning for `true`.
 *
 * FOUR STATES, AND «unknown» IS ONE OF THEM. While billing has not answered, and when it could not
 * be asked, a screen must show neither a countdown nor a lock — telling a paying shop its
 * subscription ended is worse than telling it nothing for a moment.
 */
export type BaseState = 'unknown' | 'none' | 'trial' | 'active' | 'lapsed';

/** billing's own words for a subscription that still entitles: `_BILLABLE` in billing_service. */
const LIVE = ['active', 'trialing', 'past_due'];

export function baseState(owned: Loading<Owned>): BaseState {
  if (!isReady(owned) || !owned.checked) return 'unknown';
  const base = owned.base;
  if (!base) return 'none';
  if (base.status === 'trialing') return 'trial';
  return LIVE.includes(base.status) ? 'active' : 'lapsed';
}

/**
 * Whole days left before the base period ends, or `null` when there is nothing to count.
 *
 * READ FROM `renews_at`, NEVER FROM A LOCAL CLOCK PLUS AN ASSUMED LENGTH. The trial is thirty days
 * because a PLAN says so, and a screen that recomputed «30 - days since signup» would disagree
 * with billing the moment anybody changed the number, extended a trial by hand, or crossed a month
 * boundary. `now` is a parameter so a test can state the day instead of waiting for one.
 */
export function daysLeft(owned: Loading<Owned>, now: number): number | null {
  if (!isReady(owned) || !owned.checked || !owned.base?.renews_at) return null;
  const seconds = owned.base.renews_at - Math.floor(now / 1000);
  // ALREADY PAST IS NOT «0 DAYS LEFT», it is not a countdown at all — `baseState` says «lapsed»
  // and the screen shows the sentence for that, not a zero that reads like a deadline today.
  return seconds <= 0 ? null : Math.ceil(seconds / 86400);
}
