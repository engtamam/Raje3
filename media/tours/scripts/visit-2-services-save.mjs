/**
 * «تسجيل الزيارة» — PART 2 OF 2. Read Visit.tsx, ServiceGrid.tsx and WhoIsSaving.tsx directly
 * before writing a single selector here — this project's own standing rule. Part 1
 * (visit-1-search-perks.mjs) ends on the same hero customer (0555010101), already found and on
 * the «عروضه ونقاطه» pane; this part continues from there: pick the work, save it.
 *
 * WHY THIS TOUR NEVER SHOWS «من يحفظ؟» — checked live in Visit.tsx (WhoIsSaving usage) and
 * WhoIsSaving.tsx itself before assuming anything: `save()` only opens that sheet when
 * `!proof()` — no LIVE PIN ticket cached — and even then WhoIsSaving.tsx auto-skips via
 * `onSkip()` the instant `listOperators()` returns zero PIN-capable operators, which is this
 * demo account's real state (seed-demo-account.mjs's operator is a LOGIN operator, PIN
 * operators are disabled on this deployment — PIN_OPERATORS_OFF). So on THIS account «حفظ
 * وإرسال» commits straight through with no sheet — recorded as it actually behaves, not as the
 * feature would look on a shop that had PIN staff. The caption says so honestly instead of
 * narrating a screen that will not appear.
 */
const HERO_PHONE = '0555010101';
const REDEEMABLE_SERVICE = 'بروتين شعر'; // the one seedHeroCustomer() actually recorded her visits on
const PLAIN_SERVICE = 'قص شعر';

export default {
  id: 'visit-2-services-save',
  title: 'تسجيل الزيارة 2 — اختر الخدمة واحفظ الزيارة',
  section: 'تسجيل زيارة', // nav.ts's own label
  useDemoSession: true,
  steps: [
    {
      goto: '/visit',
      chapter: 'من عروضه ونقاطه إلى الخدمات',
      say: 'كملنا من الجزء اللي فات — لقينا عميلتنا',
    },
    { waitFor: 'label=رقم الجوال', timeoutMs: 30_000 },
    { type: 'label=رقم الجوال', text: HERO_PHONE },
    { click: 'role=button:الخدمات', chapter: 'اختر الخدمة', say: 'الحين ندخل صفحة الخدمات مباشرة' },
    {
      // THE GRID'S OWN LIST (and each card's offer/points badges) is fetched, same real-cluster
      // latency as part 1's offer/balance — wait for the actual card before touching it.
      waitFor: `text=${REDEEMABLE_SERVICE}`,
      timeoutMs: 30_000,
    },
    {
      click: `text=${REDEEMABLE_SERVICE}`,
      say: 'عليها عرض ونقاط — شايف العلامتين؟',
    },
    {
      say: 'التاج 🏷 عرض، والنجمة ⭐ تستبدلها بنقاطه',
    },
    {
      click: `text=${PLAIN_SERVICE}`,
      say: 'وممكن تختار أكثر من خدمة بنفس الزيارة — عادي',
    },
    {
      say: 'وفوق شريط: طبّق العرض واستبدل، زي قبل',
    },
    {
      // NO aria-label AND NO <label> ON THIS INPUT — checked in Visit.tsx: only a `placeholder`.
      // `label=` (Playwright's getByLabel) never matches a placeholder, so this uses the css
      // escape hatch on purpose, not by default.
      click: 'css=input[placeholder="الاسم (اختياري)"]',
      say: 'اسم العميل اختياري، تقدر تكتبه لو تعرفه',
    },
    {
      say: 'وأخيرًا — زر حفظ وإرسال تحت',
    },
    {
      click: 'role=button:حفظ وإرسال',
      chapter: 'تم الحفظ',
      say: 'ضغطة وحدة، والزيارة تسجّلت — وتصله رسالة تلقائيًا',
    },
    {
      say: 'كذا خلصنا زيارة كاملة — أقل من دقيقة فعليًا',
    },
  ],
};
