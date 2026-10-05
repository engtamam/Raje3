/**
 * The app registry — one place that answers "what does this platform sell, and where does it show".
 *
 * WHY THIS EXISTS BEFORE THE APPS DO. The product is moving from four subscription tiers to apps
 * a shop buys one by one, and the ones already sold (campaigns, points, the engine, the link) are
 * only the
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

/** One real, separately-nameable capability — the wire shape every "features, not services"
 *  backend route returns (bookings/loyalty/campaigns/whatsapp-assistant/insights's own
 *  `GET .../features`, and operations' `apps()` for تسجيل زيارة/جهات الاتصال/التقييم, inline).
 *  `icon`/`tone` are KEYS, not components/classes — `rj-ui/AppFeatureList.tsx` owns the one
 *  mapping from each to a real Lucide icon / colour pair, so a new backend feature never needs a
 *  matching console PR just to render. */
export interface AppFeature {
  id: string;
  title: string;
  detail: string;
  icon: string;
  tone: string;
  shared_with: string[];
  owned_by: string;
}

/** What a shop holds, as billing answers it. `null` while the answer has not arrived. */
import { isDenied, isReady, type Loading } from './loading';
export interface Owned {
  checked: boolean;
  message: string;
  keys: string[];
  apps: { key: string; name: string; what: string; screen: string; owned: boolean | null;
          /** When THIS app's own subscription renews. `null` when he does not hold it, or when
           *  billing could not be read — «لا أعرف» and «لا يتجدّد» are different sentences. */
          renews_at: number | null;
          /** ONLY FOR APPS OPERATIONS ITSELF OWNS (تسجيل زيارة/جهات الاتصال/التقييم) — their real
           *  features ride along with this same read, since operations' own `apps.py` already
           *  carries them. Every other app's features are absent here and fetched from its own
           *  `featuresAction` instead (see `AppRow` below) — a peer call operations does not proxy. */
          features?: AppFeature[] }[];
  /** THE BASE SUBSCRIPTION ITSELF — its tier, its status and when it renews, straight from
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
  /** What it does for HIS shop. Never the tier: "this is a different app you haven't bought" is a
   *  fact about our price list, and «نكتشف الخدمات التي تُطلب معاً» is a fact about him. */
  what: string;
  /** The nav section id it owns, from nav.ts. Empty when it only adds to existing screens. */
  section: string;
  /** What it contributes inside the customer's page — the seam every future app uses. */
  onCustomer: string;
  /** THE ONE ICON KEY for this app's own header badge — `rj-ui/AppFeatureList.tsx`'s `APP_ICONS`
   *  is the single place that resolves it to a real component, replacing the three
   *  uncoordinated icon maps (Plans.tsx's own `APP_ICON`, PlanCards.tsx's `LIMIT_ICON`, and
   *  Locked.tsx's plain generic lock) this app card system used to carry. */
  icon: string;
  /** THE ONE COLOUR KEY for this app's own header badge — matches one of `rj-ui/Badge.tsx`'s real
   *  tones (`accent`/`success`/`warning`/`danger`/`info`) via `rj-ui/AppFeatureList.tsx`'s
   *  `TONE_CLASSES`, so a shelf of cards reads as distinct products at a glance rather than one
   *  colour repeated on every card (2026-09-11 product decision — the owner's own screenshot
   *  feedback on the first mockup: "مافي تمايز الوان").
   */
  tone: string;
  /** THE CATALOG ACTION ID to fetch this app's real feature list from, when it is not this app's
   *  own operations row (`Owned.apps[].features` above) — same `action(catalog, id)` + `call()`
   *  pattern every other read in this console already uses, so capability/permission visibility
   *  stays enforced exactly like every other action. Absent for base/visit/contacts/rating: those
   *  come inline. */
  featuresAction?: string;
  /** WHERE TO OPEN IT when `section` is empty — an app that adds to an EXISTING screen instead of
   *  owning a rail row of its own (صفقات's own cards inside «محلّي», واتساب's own config tab
   *  inside «حسابي»). The launcher's own catalog (`launcherCatalog.ts::allApps`) reads this so
   *  «كل التطبيقات» can still offer a real tile for it — the old متجر التطبيقات screen sold every
   *  row here regardless of whether it owned a page, and the launcher silently dropped the two
   *  that don't until this field existed (found live: the owner's own comparison against the old
   *  store screen). */
  openPath?: string;
}

export const APP_ROWS: AppRow[] = [
  {
    id: 'campaigns',
    key: 'feature.campaigns',
    name: 'الحملات',
    what: 'يعيد إليك عملاءك على وشك مغادرتك، فيكبر إيرادك من قاعدة عملائك الحالية بدل الاعتماد على زبون جديد فقط.',
    section: 'messages',
    onCustomer: 'العروض التي وصلته، وما استهلكه منها',
    icon: 'megaphone', tone: 'danger',
    featuresAction: 'campaigns.features',
  },
  {
    id: 'loyalty',
    key: 'feature.loyalty',
    name: 'برنامج النقاط',
    what: 'يبني ولاء عميلك لمحلك نفسه، لا لموظف بعينه — فيضمن رجوعه إليك دائماً أياً كان من يخدمه.',
    section: 'points',
    onCustomer: 'رصيده، وما يستطيع استبداله',
    icon: 'gift', tone: 'warning',
    featuresAction: 'loyalty.features',
  },
  {
    id: 'bookings',
    key: 'feature.bookings',
    name: 'الحجوزات',
    what: 'يستثمر كل دقيقة في جدولك، فيرفع عدد العملاء الذين تخدمهم بنفس عدد موظفيك وساعاتهم.',
    section: 'bookings',
    onCustomer: '',
    icon: 'calendar', tone: 'accent',
    featuresAction: 'bookings.features',
  },
  {
    id: 'insights',
    key: 'feature.insights.engine',
    name: 'صفقات',
    what: 'يحوّل بيانات محلك اليومية إلى نصيحة واضحة بمستوى محلل مبيعات مختص، يقودك كل يوم لأعلى فرصة ترفع دخلك.',
    // NO SECTION OF ITS OWN, and that is the pattern to copy. «محلّي» is free for every shop —
    // it is what sells everything else — and the engine locks three cards INSIDE it. An app that
    // hid the whole section would hide the argument for buying it.
    section: '',
    onCustomer: '',
    icon: 'sparkles', tone: 'info',
    featuresAction: 'insights.features',
    openPath: '/shop',
  },
  // BUILT AND WIRED — the whole pipeline (per-shop Flow clone, the template's real flow_button,
  // the send/receive round-trip, its own dedicated «التقييم» rail section gated on
  // `operations.ratings`) is live; see plans.json's own note on this row for the full audit.
  // `listed: false` there is a pure go-live decision now, not a placeholder — `owns()` already
  // answers correctly the day it flips, and `Plans.tsx` simply starts offering it for purchase
  // then, no console change needed.
  {
    id: 'rating',
    key: 'feature.rating',
    name: 'التقييم',
    what: 'يحميك من خسارة عملاء دون علمك — يكشف مشكلة بموظف أو خدمة وتعالجها قبل أن تتفاقم.',
    // ITS OWN RAIL SECTION NOW (nav.ts's own «التقييم» row) — it started as a tab inside «عملائي»
    // while all it did was list ratings; it now carries a real management tool of its own (the
    // staff-comparison quadrant, the switchable leaderboard), which earns it a place of its own on
    // the rail rather than staying a corner of a screen about something else.
    section: 'rating',
    onCustomer: '',
    icon: 'star', tone: 'warning',
    // NO featuresAction — operations owns this app's row too (core/apps.py's RATING_FEATURES),
    // so its features arrive inline on `Owned.apps[].features`, same as visit/contacts below.
  },
  // THE FREE STANDALONE APP — plans.json's own «جهات الاتصال», amount 0, held by every fresh
  // shop from day one (services/operations/app/core/signup.py::_start_contacts_grant), whether
  // or not it also holds الأساس. Listed here so the same catalogue screens that show every other
  // app (Locked.tsx, PlanCards.tsx) can name this one instead of falling through to an unknown key.
  {
    id: 'contacts',
    key: 'feature.contacts',
    name: 'جهات الاتصال',
    what: 'يبني لك قاعدة عملاء حقيقية من أول يوم لافتتاح محلك، تصبح أصلاً تسوّق عليه متى شئت.',
    // «عملائي» IS THIS APP'S OWN SECTION — the owner's own instruction (2026-09-16): جهات الاتصال
    // was listed here with no section at all (it used to have nowhere of its own to open), leaving
    // it invisible to the launcher's «تطبيقاتي» shelf, which only lists rows with a section. Tied
    // to nav.ts's `customers` id — the same rail row `Customer.tsx`/`Bookings.tsx` already open.
    section: 'customers',
    onCustomer: '',
    icon: 'user-plus', tone: 'accent',
    // NO featuresAction — see «التقييم»'s own note above; operations owns this row too.
  },
  // «تسجيل زيارة» — the visit register sold on its own (plans.json's own note on the row) —
  // nav.ts's own «تسجيل زيارة» entry is unrelated: that nav item is a page reachable by every
  // shop server-side (api/subscribed.py's OR-gate, not this key alone), so no `section` tie-in
  // is added here.
  {
    id: 'visit',
    key: 'feature.visit',
    name: 'تسجيل زيارة',
    what: 'يجعل بيانات عملائك ملكاً لمحلك، تكبر معك مهما تغيّر فريق العمل.',
    section: '',
    onCustomer: '',
    icon: 'check-circle', tone: 'success',
    // NO featuresAction — see «التقييم»'s own note above; operations owns this row too.
  },
  // NO SECTION OF ITS OWN — «ربط واتساب» is a sub-tab under «حسابي», not a rail entry, and the
  // connect card itself stays open regardless (a shop needs to see the connect flow to understand
  // what it is buying). This row exists so its TWO CONFIGURATION cards — what the assistant knows
  // about this shop, and the customer-message word limit — can be locked behind AppGate: both
  // configure the assistant's own behaviour and were editable with no bot bought at all, found
  // live (screenshot: a fresh shop with no WhatsApp app could still type notes for an assistant
  // that would never read them).
  {
    id: 'whatsapp',
    key: 'feature.whatsapp',
    name: 'المساعد الذكي عبر واتساب',
    what: 'يحوّل واتساب إلى مندوب مبيعات يعرف ذوق كل عميل، ويقترح عليه باقاتك وعروضك ونقاطه في الوقت المناسب، فيرفع متوسط فاتورتك.',
    section: '',
    onCustomer: '',
    icon: 'message-circle', tone: 'accent',
    featuresAction: 'whatsapp_assistant.features',
    // ITS OWN DEDICATED WORKSPACE (2026-09-16) — `WhatsAppAssistant.tsx`, not «حسابي»'s own
    // ربط واتساب tab (that tab stays a GENERAL establishment fact, the owner's own instruction:
    // "ربط الواتساب مكانه صحيح ما نغيره لانه عام مو مخصص للبوات").
    openPath: '/whatsapp-assistant',
  },
  // «ولاء الشركاء» — shop-to-shop: a discount on ANOTHER registered shop's own subscription with
  // us, applied at its next renewal (deploy/seed/plans.json's own note on this row). Really an
  // indirect loyalty mechanic between business partners (the owner's own framing) rather than a
  // marketing/growth play — grouped with برنامج النقاط accordingly. RENAMED 2026-09-22 from
  // `coupons`/«تحالف استراتيجي» — the old name read as a near-duplicate of «تبادل منافع»
  // (mutual-benefit), a genuinely different app. `id`/`key`/`section` renamed with it (no
  // live data existed yet); docs/خطة-كوبونات-محل-لمحل.md keeps its old filename as history, never
  // re-read as a live naming source.
  {
    id: 'partner-loyalty',
    key: 'feature.partner_loyalty',
    name: 'ولاء الشركاء',
    what: 'كوّن تحالفاً حقيقياً مع محل آخر مسجّل عندنا — امنحه امتيازاً على اشتراكه معنا يُطبَّق تلقائياً عند تجديده القادم، ويثبّت علاقتك التجارية معه بخطوة ملموسة لا كلام فقط.',
    section: 'partner-loyalty',
    onCustomer: '',
    // NOT `gift`/`warning` — برنامج النقاط already owns that exact pair, and a shelf of cards
    // must read as distinct products (see this file's own `tone` doc-comment above).
    icon: 'users', tone: 'danger',
    // NO featuresAction — see «التقييم»'s own note above; operations owns this row too.
  },
  // «تبادل منافع» — cross-tenant customer referral: a shop's own customer who meets a real
  // condition at a SHOP IT TRUSTS becomes automatically eligible for a grant here, mutual-consent
  // only (docs/خطة-شراكة-استراتيجية-الإحالة.md, core/mutual_benefit.py's own module
  // docstring). NOT `coupons` — that row moves money on OUR subscription; this one moves real
  // customers between two real shops, backed by both shops' own catalogues (a gift is a real
  // service/product, a discount is a real service/blanket/group — never a typed note). `screen:
  // 'mutual-benefit'` is THIS pass — the backend has held that name since the backend-only
  // pass; this is the UI half finally landing.
  {
    id: 'mutual-benefit',
    key: 'feature.mutual_benefit',
    name: 'تبادل منافع',
    what: 'وسّع قاعدة عملائك دون ريال إعلان واحد — عميل محل تثق به يصير مستحقاً تلقائياً لعرضك بمجرد أن يثبت أنه عميل حقيقي، فتبنيان علاقة تجارية تكبر بها معاً، لا صفقة عابرة.',
    section: 'mutual-benefit',
    onCustomer: '',
    icon: 'hand-heart', tone: 'success',
    // NO featuresAction — operations owns this app's row too, same posture as coupons/mobile
    // requests above.
  },
  // «الإحالة والمسوّقين» — services/referrals + core/referral_redemption.py, now fully real
  // (campaigns, till-side redemption, the affiliate tier, configurable beneficiary eligibility).
  // FOUND MISSING LIVE (2026-09-27, the same day its plan row was flipped to `listed: true`):
  // this row never existed here at all, so `allApps()`'s own `APP_ROWS.filter((a) => a.section ||
  // a.openPath)` had nothing to find — a real, priced, screen-having app was invisible on the one
  // shelf whose entire job is selling it, even though nav.ts's own `referrals` section (and the
  // real Referrals.tsx screen behind it) already existed.
  {
    id: 'referrals',
    key: 'feature.referrals',
    name: 'الإحالة والمسوّقين',
    what: 'يحوّل عملاءك الحاليين إلى فريق مبيعات حقيقي — كل عميل يجلب عميلاً جديداً يكسب الاثنان مكافأة حقيقية.',
    section: 'referrals',
    onCustomer: '',
    icon: 'user-plus', tone: 'info',
    // NO featuresAction — operations owns this app's row too, same posture as coupons/mobile
    // requests/mutual-benefit above.
  },
  // «المساعد الذكي (تطبيق الجوال)» — on-device (Gemma 4, apps/mobile only). NO console screen
  // EXISTS OR EVER WILL — this app's whole surface is the phone (owner's own words: "كل شي في
  // تطبيق الجوال"). `openPath: '/account'` is a DELIBERATE, HONEST fallback, not a real
  // destination: `allApps()`/`myApps()` in launcher/launcherCatalog.ts both require a row to
  // carry a `section` OR an `openPath` to appear in «متجر التطبيقات»/«تطبيقاتي» AT ALL (checked
  // against their own source before picking this) — with neither, the card the owner explicitly
  // asked for ("يشوفه في متجر التطبيقات وفي تطبيقاتي") would simply never render. «حسابي» is the
  // least-surprising place to land a shop owner who taps a card with nothing of its own to open.
  // Priced 0 on purpose (deploy/seed/plans.json's own note) — a real, listed, subscribe/cancel-
  // able plan, changing the price later needs no code change here.
  {
    id: 'mobile-ai-assistant',
    key: 'feature.mobile_ai_assistant',
    name: 'المساعد الذكي (تطبيق الجوال)',
    what: 'يجاوبك ويرشدك داخل تطبيق الجوال بصوتك أو بالكتابة، فوراً وبلا انتظار.',
    section: '',
    onCustomer: '',
    icon: 'bot', tone: 'info',
    openPath: '/account',
    // NO featuresAction — operations owns this app's row too, same posture as every other
    // operations-only row on this file.
  },
  // «خدمات متنقلة» — a shop whose service travels TO the customer (mobile car wash, home visit).
  // STANDALONE (owner's own decision, 2026-09-15) — never needs «المساعد الذكي عبر واتساب» first;
  // a request can be typed in by the shop's own staff from day one (see MobileRequests.tsx's own
  // «إضافة طلب» button) and over WhatsApp too, once that app is added later.
  {
    id: 'mobile-requests',
    key: 'feature.mobile_requests',
    name: 'خدمات متنقلة',
    what: 'خدمتك تروح لعنده هو — يطلب موعداً، تراجعه وتقرر، ثم تسجّله زيارة حقيقية بعد ما تتم فعلاً.',
    section: 'mobile-requests',
    onCustomer: '',
    icon: 'truck', tone: 'warning',
    // NO featuresAction — see «التقييم»'s own note above; operations owns this row too.
  },
  // «طلبات التوصيل عبر الواتساب» — WhatsApp Direct Ordering, a standalone delivery product
  // competing with HungerStation/Jahez etc, NEVER to be confused with «خدمات متنقلة» above (the
  // owner's own correction, 2026-10-05: "كل تطبيق منعزل عن الاخر"). Catalog-based ordering, the
  // shop's own payment gateway, delivered by the shop's own rep. `feature.whatsapp_delivery_orders`
  // is already registered in deploy/seed/plans.json with `listed: false` — a deliberate, separate
  // pricing decision not yet made by the owner, untouched here.
  {
    id: 'whatsapp-orders',
    key: 'feature.whatsapp_delivery_orders',
    name: 'طلبات التوصيل عبر الواتساب',
    what: 'عميلك يطلب من كتالوجك عبر واتساب ويدفع لحسابك مباشرة — تتابع كل طلب من لحظة الطلب إلى التسليم.',
    section: 'whatsapp-orders',
    onCustomer: '',
    icon: 'receipt', tone: 'danger',
    // NO featuresAction — operations owns this row too, same posture as «خدمات متنقلة» above.
  },
  // «خدمات ما بعد البيع» — core/freelancer_service.py + core/freelancer_crm.py's own module
  // docstrings. A shop hands post-visit customer follow-up to an EXTERNAL freelancer it brought in
  // itself (max 3 linked), never a marketplace. REQUIRES_ANY one of the real visit-recording apps
  // (deploy/seed/plans.json's own note on this row) — a freelancer has nobody to call without one.
  // `listed: false` on the backend row until this screen shipped; this IS that screen landing.
  {
    id: 'freelancers',
    key: 'feature.customer_service',
    name: 'خدمات ما بعد البيع',
    what: 'مستقل تثق به يتابع رضا عملائك بعد الزيارة — يسجّل ملاحظة، يمنح ترضية بسقف تحدده أنت، ويصعّد لك أي حالة غاضبة فوراً.',
    section: 'freelancers',
    onCustomer: '',
    icon: 'headphones', tone: 'success',
    // NO featuresAction — operations owns this row too, same posture as «خدمات متنقلة» above.
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
 * because BILLING says so, and a screen that recomputed «30 - days since signup» would disagree
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

/**
 * WHICH SUBSCRIPTION IS THE ONE WORTH A BANNER — never assumed to be الأساس. A shop with no base
 * at all can still hold a standalone app bought on its own (تسجيل زيارة), and that one is what is
 * actually ending for him. جهات الاتصال is excluded by construction rather than by name: it is
 * free and subscribed with `interval='once'` (never renews), so it never carries a `renews_at`
 * and simply never wins the search below — no special-case needed for it here.
 *
 * RETURNS `null` WHEN THERE IS NOTHING TO NAME — no base, and no standalone app carrying a
 * renewal date. `SubscriptionBar` already shows nothing in that case.
 */
export function relevantSubscription(
  owned: Loading<Owned>,
): { name: string; renewsAt: number } | null {
  if (!isReady(owned) || !owned.checked) return null;
  if (owned.base) {
    return { name: 'الأساس', renewsAt: owned.base.renews_at };
  }
  // THE SOONEST-ENDING STANDALONE APP HE HOLDS, if any — same "don't guess" discipline as
  // `base_plan_id` on the server: several could carry a `renews_at`, and the one closest to
  // today is the one worth a banner.
  const candidates = owned.apps.filter((a) => a.owned && a.renews_at);
  if (candidates.length === 0) return null;
  const soonest = candidates.reduce((a, b) => (a.renews_at! < b.renews_at! ? a : b));
  return { name: soonest.name, renewsAt: soonest.renews_at! };
}
