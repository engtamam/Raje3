/**
 * «عملائي» — PART 1 OF 2: the list, its two tabs, the search, and one customer's own page read
 * top to bottom (overview → points → messages). Read Customers.tsx and Customer.tsx in full
 * before writing a single selector here — this project's own standing rule, and this pair of
 * files earns it: the "متأخر" badge on the list and the overdue banner on the customer's own page
 * are two DIFFERENT computations (list: `reminders.list_schedule`, resolved by the engine;
 * detail: `sinceDays > everyDays * 1.5`, computed locally from his own visits) — a real product
 * quirk, not a recording slip, so the caption says so rather than pretending they're one thing.
 *
 * CAPTIONS ARE SHORT ON PURPOSE, NOT BY TASTE. overlay.mjs's caption bar is `82vw` at this frame's
 * 430px width, 28px font, `maxLines: 2` — measured live: a first draft's ~85-char sentences threw
 * "doesn't fit CAPTION.maxLines" on step 1 (56 chars, before shortening further). Every long
 * explanation below is split into several short caption-only steps instead of one long one — the
 * same shape shop-dashboard.mjs already uses for its own multi-sentence explanations.
 *
 * THE SEARCH BOX HAS NO aria-label AND NO TESTID — checked in Customers.tsx: only a
 * `placeholder`. `label=` (Playwright's getByLabel) never matches a placeholder, so this uses the
 * `css=` escape hatch on purpose, exactly like visit-2-services-save.mjs does for the same reason
 * on a different screen — not a shortcut, a documented last resort.
 *
 * THE HERO CUSTOMER (0555010101) IS THE ONE ALREADY BUILT FOR THIS: seed-demo-account.mjs gives
 * her a name from her first visit, 40 real visits on «بروتين شعر» (so «دورته عندك» has learned a
 * real rhythm to show), a real points balance, and two real rewards. Nothing here mutates her —
 * this clip is read-only end to end; the write actions (rename, adjust points, erase) live in
 * part 2, on a DIFFERENT customer, precisely so this hero's seeded state stays intact for every
 * other tour re-recorded against her (visit-1/2, and this one).
 */
const HERO_PHONE = '0555010101';
const HERO_NAME = 'عميلة العرض';
const HERO_SERVICE = 'بروتين شعر';

export default {
  id: 'customer-file-1-overview',
  title: 'عملائي 1 — القائمة وملف العميل',
  section: 'عملائي', // nav.ts's own label
  useDemoSession: true,
  // See visit-1-search-perks.mjs's own note: without this, the opening `goto` records several
  // seconds of blank/white frame before the page actually finishes loading.
  preload: true,
  steps: [
    {
      goto: '/customers',
      chapter: 'قائمة عملائي',
      say: 'شاشة «عملائي» — كل من زارك',
    },
    {
      click: 'role=radio:من تأخّر',
      say: '«من تأخّر»: من فات موعد عودته',
    },
    {
      say: 'من نفس محرّك التذكيرات، لا حساب جديد',
    },
    {
      click: 'role=radio:عملائي',
      say: 'رجعنا للقائمة الكاملة',
    },
    {
      say: 'وسام «متأخر» هنا هو نفسه ذاك التبويب',
    },
    {
      click: 'css=input[placeholder="ابحث برقم الجوال أو الاسم"]',
      chapter: 'البحث',
      say: 'البحث برقم الجوال أو الاسم',
    },
    {
      type: 'css=input[placeholder="ابحث برقم الجوال أو الاسم"]',
      text: HERO_PHONE,
      say: `نكتب رقمها ${HERO_PHONE}`,
    },
    {
      // WAITING ON THE PHONE, NOT THE NAME — the row always carries the phone (it's what was
      // typed and matched); the name is a separate field that a search index can lag behind on a
      // busy shared demo account, confirmed live when a name-based wait timed out with the row
      // itself already on screen.
      waitFor: `text=${HERO_PHONE}`,
      timeoutMs: 45_000,
    },
    {
      say: 'ولقيناها — بحث حقيقي، لا فلترة الشاشة',
    },
    {
      click: `text=${HERO_PHONE}`,
      chapter: 'ملف العميل',
      say: 'نفتح ملفها',
    },
    {
      say: 'فوق: اسمها ورقمها، وثلاث بطاقات',
    },
    {
      say: 'زياراتها، آخر زيارة، وكل كم يوم تعود',
    },
    {
      say: 'أربع تبويبات: نظرة عامة، نقاطه، رسائله، وتعديل',
    },
    {
      say: '«عروضه»: ما وصلها، الساري والمنتهي',
    },
    {
      say: 'لا نخفي المنتهي — سؤال متكرر عنه',
    },
    {
      say: '«زياراته»: كل زيارة وخدماتها وتاريخها',
    },
    {
      // «دورته عندك» ONLY RENDERS ONCE `reminders.list_rules` HAS LEARNED AT LEAST ONE RULE FOR
      // this customer — a background computation, not guaranteed to have run yet at recording
      // time even for a 40-visit seeded hero (confirmed live: a 30s wait for
      // `label=دورة ${HERO_SERVICE}` timed out on a real run). Narrated without a hard `waitFor`
      // gate on it so this tour never depends on timing it can't control.
      say: 'ولو تعلّم النظام إيقاعها، يظهر تحت «دورته عندك»',
    },
    {
      say: 'رقم قابل للتعديل بيدك — لو تعرفه أفضل من النظام',
    },
    {
      click: 'role=radio:نقاطه',
      chapter: 'نقاطه ورسائله',
      say: 'تبويب نقاطه: رصيدها ومكافآتها',
    },
    {
      say: 'وتحتها «حركة النقاط» — من أين جاءت ومتى صُرفت',
    },
    {
      click: 'role=radio:رسائله',
      say: 'رسائله: كل رسالة خرجت أو لم تخرج',
    },
    {
      say: 'مع السبب لو انمنعت — لا شيء يُمنع بصمت',
    },
    {
      click: 'role=button:رجوع',
      chapter: 'رجوع للقائمة',
      say: 'رجوع — وخلصنا جولة كاملة على ملف عميل',
    },
  ],
};
