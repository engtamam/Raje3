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
export interface Owned {
  checked: boolean;
  message: string;
  keys: string[];
  apps: { key: string; name: string; what: string; screen: string; owned: boolean | null }[];
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
    what: 'عملاؤك وزياراتهم وخدماتك، وتأكيد الزيارة والتذكير بها.',
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
    id: 'insights',
    key: 'feature.insights.engine',
    name: 'محرك التحليلات',
    what: 'الاقترانات بين خدماتك، والباقات المقترحة، وأثر الرسائل على الرجوع.',
    // NO SECTION OF ITS OWN, and that is the pattern to copy. «محلّي» is free for every shop —
    // it is what sells everything else — and the engine locks three cards INSIDE it. An app that
    // hid the whole section would hide the argument for buying it.
    section: '',
    onCustomer: '',
  },
  {
    id: 'link',
    key: 'feature.api',
    name: 'الربط البرمجي',
    what: 'يربط صندوقك أو نظامك بحسابك هنا، فتُسجَّل الزيارات بلا إدخال يدوي.',
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
export function owns(owned: Owned | null, key: string | null): boolean | null {
  if (key === null) return true;             // the base is not for sale separately
  if (!owned || !owned.checked) return null;
  return owned.keys.includes(key);
}
