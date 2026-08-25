/**
 * «تسجيل الزيارة» — PART 1 OF 2. Read Visit.tsx (and WhoIsSaving.tsx, ServiceGrid.tsx) directly
 * before writing a single selector here — this project's own standing rule. Split into two clips
 * the same way محلّي briefly was and «الحجوزات» is planned to be: by the screen's own natural
 * story-phase, not an arbitrary step count. Part 1 is «who is this customer, and what does he
 * carry» — search, then offers and points, EXTRA DEPTH here specifically ("شوية
 * صعب" — the counter card, the checkbox that never applies itself, the manager-approval reward —
 * deserve more than a passing caption each). Part 2 (visit-2-services-save.mjs) is «pick the
 * work, and who's doing it» — services, self-attribution, save.
 *
 * WHY THIS TOUR NEEDS ITS OWN SEEDED CUSTOMER. Every other seeded customer in this demo account
 * honestly has nothing to redeem — that's the correct, common state, and not what this tour is
 * FOR. seed-demo-account.mjs's own seedHeroCustomer() builds exactly one customer (fixed phone
 * 0555010101) with real points, two real rewards (one plain, one manager-approval), from real
 * recorded visits — never a fabricated balance. Her OFFER is seeded separately, in-cluster (see
 * that function's own printed instructions) — there is no owner-facing action that creates one,
 * by the platform's own design (deploy/seed/seed-field-offer.py's header).
 *
 * ORDER MATCHES Visit.tsx's OWN JOURNEY: «رقم جوال العميل» → «عروضه ونقاطه» → «الخدمات». This
 * shop has no plate mode (services offered are hair/beauty, not car-trade), so the plate step
 * never appears — confirmed live, not assumed.
 */
const HERO_PHONE = '0555010101';

export default {
  id: 'visit-1-search-perks',
  title: 'تسجيل الزيارة 1 — دوّر عن عميلك وعروضه ونقاطه',
  section: 'تسجيل زيارة', // nav.ts's own label
  useDemoSession: true,
  // WITHOUT THIS the first step's `goto` runs inside the capture loop itself, so frame 0 (and
  // several seconds after it) is a blank/white screen while the page navigates and loads —
  // confirmed by pulling the actual first frame with ffmpeg. `preload: true` makes record-tour.mjs
  // perform this navigation BEFORE capture starts, the same fix services-1-overview.mjs already
  // uses for the same reason.
  preload: true,
  steps: [
    {
      goto: '/visit',
      chapter: 'دوّر عن عميلك',
      say: 'تعرف كيف تسجّل زيارة بأقل من دقيقة؟ تعال أوريك',
    },
    {
      type: 'label=رقم الجوال',
      text: HERO_PHONE,
      say: 'اكتب رقم جواله — والنتائج تطلع وأنت تكتب',
    },
    {
      say: 'ما تحتاج تكمل الرقم كامل — لو ظهر بالنتائج اضغط عليه',
    },
    {
      // THE DOTS NAVIGATE BY STEP TITLE — Steps.tsx's own aria-label={s.title} on each one, a
      // real clickable control (not the swipe gesture a phone user would use, which this
      // recorder can't simulate). Same title Visit.tsx names this pane.
      click: 'role=button:عروضه ونقاطه',
      chapter: 'عروضه ونقاطه',
      say: 'هذي أهم صفحة بكل الزيارة — عروضه ونقاطه',
    },
    {
      // THE OFFER/BALANCE FETCH IS DEBOUNCED (220ms) THEN NETWORKED — Visit.tsx's own effect.
      // Against the real cluster (this recorder's tunnel, not a local dev server) that round
      // trip can outlast a plain click's short actionability wait, so this waits for the
      // offer text itself to actually be there before touching it.
      waitFor: 'text=عرضٌ خاص بهذا العميل',
      timeoutMs: 30_000,
    },
    {
      click: 'text=عرضٌ خاص بهذا العميل',
      say: 'عنده عرض خاص — يعرضه النظام نفسه',
    },
    {
      say: 'اقرأه بصوت عالي — يطمّن العميل إنه موثّق',
    },
    {
      click: 'label=طبّقتُ العرض على هذه الزيارة',
      say: 'مهم: العرض ما يُطبَّق نفسه — لازم تعلّم هنا إنك طبّقته فعليًا',
    },
    {
      say: 'ليه؟ عشان ما ناخذ منه عرض يبيه يحفظه لزيارة ثانية',
    },
    {
      // SAME OFFER/BALANCE FETCH, SAME REAL-CLUSTER LATENCY as the offer step above — the
      // balance renders on its own Promise.allSettled branch and can still be mid-flight here.
      waitFor: 'text=رصيده',
      timeoutMs: 30_000,
    },
    {
      click: 'text=رصيده',
      say: 'وتحت العرض — رصيد نقاطه، وكم يقدر يستبدل بيها الحين',
    },
    {
      click: 'text=قهوة مجانية',
      say: 'مكافأة عادية — ضغطة وحدة وتستبدلها له مباشرة',
    },
    {
      click: 'text=جلسة مجانية VIP',
      say: 'وهذي أكبر — تحتاج اعتماد المدير قبل ما تُستبدل',
    },
    {
      type: 'label=اسم المدير المعتمِد',
      text: 'مدير الفرع',
      say: 'يكتب اسم المدير المعتمِد هنا فقط',
    },
    {
      click: 'role=button:اعتمد واستبدل',
      say: 'وبعدها تقدر تستبدلها — كل شي موثّق باسم صاحبه',
    },
  ],
};
