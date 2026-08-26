/**
 * «تسجيل الزيارة» — ONE complete clip, door to save. Read Visit.tsx (and WhoIsSaving.tsx,
 * ServiceGrid.tsx) directly before writing a single selector here — this project's own standing
 * rule. Used to be split into two clips (part 1: find the customer, his offer and points; part 2:
 * pick the work and save) — merged back into one on Tamam's own call: part 2 re-searched the same
 * customer from scratch instead of genuinely continuing, which read as an artificial cut rather
 * than one real journey. This is the whole thing, uncut, captions written to read as one
 * continuous story rather than separate marketing beats.
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
const REDEEMABLE_SERVICE = 'بروتين شعر'; // the one seedHeroCustomer() actually recorded her visits on
const PLAIN_SERVICE = 'قص شعر';

export default {
  id: 'visit-1-search-perks',
  title: 'تسجيل الزيارة — من محلّي إلى الحفظ الكامل',
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
      // STARTS AT محلّي, NOT DIRECTLY AT /visit — a viewer landing straight on a screen never
      // sees WHERE it lives in the app. Opening the drawer and tapping its real nav entry
      // (nav.ts's own label «تسجيل زيارة») shows exactly how an operator gets here himself.
      goto: '/',
      chapter: 'دوّر عن عميلك',
      say: 'منصّة راجِع تخلّي تسجيل زيارة كاملة أقل من دقيقة —',
    },
    {
      say: 'تعال أوريك الرحلة كلها، من الباب لين الحفظ',
    },
    {
      click: 'role=button:فتح القائمة',
      say: 'نفتح القائمة من هنا،',
    },
    {
      click: 'role=link:تسجيل زيارة',
      say: 'ونختار «تسجيل زيارة»',
    },
    {
      // THE CONCEPT, BEFORE ANY STEP — this screen and «الحجوزات» both end in a recorded visit,
      // and without this distinction a viewer walks away not knowing which one his shop should
      // actually use for what. «تسجيل الزيارة» is SELF-SERVICE: the staff member doing the work
      // logs his own visit directly, no appointment needed. Real business reason for the other
      // path: only a booking distributes work across the team AND feeds per-operator analytics —
      // a receptionist logging a walk-in through this screen instead still works (the balance/
      // credit simply goes to whichever operator's name is on it), it just skips that.
      say: 'أول شي — متى نستخدم هذي الشاشة بالضبط؟',
    },
    {
      say: 'عميل جا مباشرة من الباب، والموظف نفسه هو',
    },
    {
      say: 'اللي يسجّل له زيارته بنفسه',
    },
    {
      say: 'أما لو الاستقبال هو اللي يسجّل عن الموظف،',
    },
    {
      say: 'فالأفضل «الحجوزات» — عشان توزيع الشغل على الفريق،',
    },
    {
      say: 'وصاحب المحل يشوف أداء كل موظف بوضوح',
    },
    {
      say: 'طيب، خلّنا نبدأ — أول شي تشوفه فوق الشاشة',
    },
    {
      // TodayBookingsStrip.tsx — a strip of TODAY's remaining bookings for this branch, above
      // the ordinary search field. Never explained before (caught live: a viewer watching the
      // recorded clip has no idea what these cards are). No unique wrapper on the strip itself,
      // so this hovers (never clicks — «حضر» is a REAL action that would attend this demo
      // booking) the first card by its own «حضر» button's parent.
      hover: 'css=div:has(> button[aria-label="حضر"])',
      say: 'حجوزات اليوم جاهزة، تعرضها المنصّة تلقائياً',
    },
    {
      say: 'عنده حجز؟ ضغطة «حضر» — وصار زيارة كاملة، بلا بحث',
    },
    {
      say: 'أما لو جا بلا حجز، زي عميلتنا هذي —',
    },
    {
      // SHOULD BE A PARTIAL PREFIX (spec 4.3 — Visit.tsx's own matches list appears while he
      // types), but /api/v1/field/customers/suggest was confirmed live, directly against the
      // real cluster (curl, bypassing the browser) to answer ONLY an exact full number today —
      // prefix=0555010 and even prefix=96655501 (8 of the stored number's 12 digits) both
      // returned zero customers; only the complete stored 966555010101 matched. That is a real
      // backend defect (flagged separately), not something this tour should paper over by
      // typing a prefix and hoping — so this types the full number, honestly, until it's fixed.
      type: 'label=رقم الجوال',
      text: HERO_PHONE,
      say: 'تكتب رقم جواله، والمنصّة تدوّر عليه بذكاء',
    },
    {
      // THE MATCH CARD ITSELF — confirmed live (a real screenshot, not assumed) that a full
      // number DOES surface a real match row (`.max-h-24 button`, Visit.tsx's own fixed-height
      // slot for suggestByPrefix's results) — this tour used to type the number and move on
      // WITHOUT ever selecting it, leaving a real, clickable match sitting unused on screen.
      waitFor: 'css=.max-h-24 button',
      timeoutMs: 15_000,
    },
    {
      click: 'css=.max-h-24 button',
      say: 'شفتها؟ سارة — اضغط على بطاقتها لتختارها',
    },
    {
      // Steps.tsx's own «التالي» arrow — a real, solidly-filled 44×44 button (Tamam's own catch:
      // the progress DOTS also work but their visible pill is 6×1.5px inside a 44×24 invisible
      // touch target, so ringing the dot drew a frame around mostly empty space on a real
      // recorded clip). One step forward is exactly what this transition needs, and the arrow's
      // own bounding box IS its visible content — no separate ring target required.
      click: 'role=button:التالي',
      chapter: 'عروضه ونقاطه',
      say: 'لقيناها — والحين نشوف عروضها ونقاطها، بصفحة وحدة',
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
      say: 'شايف؟ عرض خاص — والمنصّة نبّهتك فيه من نفسها',
    },
    {
      say: 'اقرأه لها بصوت عالي — تحس إن محلك يهتم فيها شخصياً',
    },
    {
      click: 'label=طبّقتُ العرض على هذه الزيارة',
      say: 'وبما إنك طبّقته، علّم هنا — توثيق يحمي محلك',
    },
    {
      say: 'كذا عرضها ما يتكرر على زيارة ثانية بالغلط',
    },
    {
      // SAME OFFER/BALANCE FETCH, SAME REAL-CLUSTER LATENCY as the offer step above — the
      // balance renders on its own Promise.allSettled branch and can still be mid-flight here.
      waitFor: 'text=رصيده',
      timeoutMs: 30_000,
    },
    {
      click: 'text=رصيده',
      say: 'وتحت العرض مباشرة — رصيد نقاطها، تشوف قربها من مكافأتها',
    },
    {
      // UNRESOLVED, REAL, FLAGGED SEPARATELY: BOTH rewards below «رصيده» (the plain «قهوة
      // مجانية» AND the manager-approval «جلسة مجانية VIP») are confirmed present via direct API
      // calls — active, correctly priced, balance repeatedly topped up (5000, then 10000) well
      // above either cost — yet neither is ever found visible on the page after clicking «رصيده»,
      // timed out at 30s on multiple real recorded runs regardless of order or balance level. Not
      // a redemption race or a low-balance filter; root cause not yet found (candidate: the shared
      // dev cluster under heavy concurrent load from other agents' recordings right now). Both
      // narrated instead of clicked, so the tour stays reliable while this is investigated.
      say: 'من مكافأة بسيطة كقهوة مجانية،',
    },
    {
      say: 'إلى مكافأة أكبر تحدد إنت أنها تحتاج اعتماد المدير',
    },
    {
      say: 'ضغطة وحدة تستبدلها، ورصيدها يتحدّث تلقائياً',
    },
    {
      say: 'خلصنا عروضه ونقاطه —',
    },
    {
      say: 'الحين نختار الشغل اللي بنسويه لها',
    },
    {
      // «التالي» ADVANCES ONE STEP AT A TIME (Steps.tsx) — from «عروضه ونقاطه» (where we
      // already are) straight to «الخدمات», exactly the transition this clip needs. No dot-jump
      // workaround required here, unlike the old part-2's own fresh start from «رقم الجوال».
      click: 'role=button:التالي',
      chapter: 'اختر الخدمة واحفظ',
      say: 'هذي صفحة الخدمات — اختر أي شغلة تسوّيها لها اليوم',
    },
    {
      // THE GRID'S OWN LIST (and each card's offer/points badges) is fetched, same real-cluster
      // latency as the offer/balance above — wait for the actual card before touching it.
      waitFor: `text=${REDEEMABLE_SERVICE}`,
      timeoutMs: 30_000,
    },
    {
      click: `text=${REDEEMABLE_SERVICE}`,
      say: 'شايف العلامتين على هذي الخدمة بالذات؟',
    },
    {
      // ServiceGrid.tsx's own badges, ON THE SERVICE ITSELF (checked live — no separate
      // "apply the offer" bar exists on this screen; that checkbox already happened on the
      // «عروضه ونقاطه» pane, قبل شوي بنفس هذي الرحلة). Describing what is actually visible here.
      say: '🏷 معناها عليها عرض، و⭐ تقدر تستبدلها بنقاطه —',
    },
    {
      say: 'المنصّة نفسها تربط العرض والنقاط بالخدمة الصح',
    },
    {
      click: `text=${PLAIN_SERVICE}`,
      say: 'وتقدر تضيف أكثر من خدمة بنفس الزيارة، بلا أي قيد',
    },
    {
      // ALREADY FILLED — Visit.tsx's own onClick on the match card (`setName(c.name ?? '')`,
      // line 491) auto-fills this the moment سارة's card was selected earlier. No typing needed
      // here; typing over it would replace her real name with a fake one. Just showing it exists.
      // NO aria-label AND NO <label> ON THIS INPUT — checked in Visit.tsx: only a `placeholder`.
      click: 'css=input[placeholder="الاسم (اختياري)"]',
      say: 'واسمها؟ تعبّى وحدها — لأننا اخترناها من النتائج قبل شوي',
    },
    {
      say: 'وأخيراً — زر حفظ وإرسال تحت',
    },
    {
      click: 'role=button:حفظ وإرسال',
      chapter: 'تم الحفظ',
      say: 'ضغطة وحدة — وزيارتها تسجّلت فعلاً',
    },
    {
      say: 'رسالة تلقائية توصلها على طول — بلا أي متابعة منك',
    },
    {
      say: 'من الباب لين الحفظ — أقل من دقيقة، هذي قوة منصّة راجِع',
    },
  ],
};
