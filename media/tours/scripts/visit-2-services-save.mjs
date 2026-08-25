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
  // See visit-1-search-perks.mjs's own note: without this, the opening `goto` records several
  // seconds of blank/white frame before the page actually finishes loading.
  preload: true,
  steps: [
    {
      goto: '/visit',
      chapter: 'من عروضه ونقاطه إلى الخدمات',
      say: 'كملنا من الجزء اللي فات — لقينا عميلتنا',
    },
    { waitFor: 'label=رقم الجوال', timeoutMs: 30_000 },
    { type: 'label=رقم الجوال', text: HERO_PHONE },
    { click: 'role=button:الخدمات', say: 'الحين ندخل صفحة الخدمات مباشرة' },
    {
      // EXTRA CAPTION-ONLY MARGIN — the 10s chapter-gap check still failed at 9.8s on a real run
      // even after moving the chapter mark past the network wait below; this buys the missing
      // margin honestly (real narration, not a bare pause).
      say: 'كل خدمة تعرض سعرها ومدتها مباشرة',
    },
    {
      // THE GRID'S OWN LIST (and each card's offer/points badges) is fetched, same real-cluster
      // latency as part 1's offer/balance — wait for the actual card before touching it.
      waitFor: `text=${REDEEMABLE_SERVICE}`,
      timeoutMs: 30_000,
    },
    {
      // CHAPTER MOVED HERE, NOT ON THE CLICK ABOVE — with `preload: true` (this tour's own fix
      // for the blank-first-frame bug) the app is already loaded before capture starts, so the
      // opening chapter-to-here gap shrank under YouTube's 10s minimum on a real run (verified
      // live: exactly the trap services-1-overview.mjs's own header warns about). The real
      // network wait just above buys back the needed real time before this chapter fires.
      click: `text=${REDEEMABLE_SERVICE}`,
      chapter: 'اختر الخدمة',
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
