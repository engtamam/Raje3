/**
 * «أرباحي» (AffiliateEarnings.tsx) — full coverage in one clip: the balance hero, «دعم الوفاء»,
 * «رشّح نفسك لوظيفة», the commission ledger, and the withdrawal ledger, read top to bottom
 * exactly the order the component renders them. Read that file in full before writing a single
 * selector here — this project's own standing rule — and its own header comment is the one
 * fact this whole tour is built to teach: THE HERO NUMBER NEVER COMPETES WITH ANYTHING ELSE ON
 * SCREEN, and «دعم الوفاء» is a separate PROGRAM with its own card, never merged into the ledger.
 *
 * WHY THIS SCRIPT LOGS IN FOR REAL (`skipAutoSignIn: true`), UNLIKE A SHOP TOUR'S
 * `useDemoSession`. record-tour.mjs's own demo-session machinery writes a session into
 * localStorage under `raje3.session` — the SHOP's own key. The affiliate portal keeps its own,
 * separate store (`session.ts`: `raje3.affiliate.session`, minted only by
 * `/api/v1/affiliates/signin`), so there is no shortcut into it the way there is for a shop; the
 * honest way to reach this screen is the same door a real marketer uses, on camera — which
 * doubles as showing a viewer how he gets in at all.
 *
 * THE ACCOUNT ITSELF: minted once by seed-demo-affiliate.mjs — apply() then the same
 * platform-owner admin account admin-home-1-overview.mjs's own tour uses to approve()
 * (0500000902 / HomeTour2026Demo!, a throwaway dev-cluster account). `0549900110` /
 * `Raje3-Affiliate-Tour!1` is not a secret worth protecting either — no real referral, no real
 * money behind it.
 *
 * RE-SEEDED PAST THE DAY-ONE EMPTY STATE (see `media/tours/seed-affiliate-rich-demo.mjs`) —
 * hundreds of real referred shops now, a real team, real tickets. Two things stay a genuine zero
 * even so, and this clip says exactly why rather than pretending otherwise: the commission and
 * withdrawal LEDGERS, because CommissionEngine.sync() only ever creates a row from
 * billing-service's own paid-invoice history, and no billing-service is reachable from this dev
 * cluster (checked directly — `BILLING_SERVICE_URL` is blank everywhere it's read). A referred
 * shop existing is real; that shop's first invoice being PAID is a fact only a real billing
 * integration can produce, and this deployment has none. So the balance hero, both ledgers, still
 * render their honest zero/EmptyState — but «دعم الوفاء»'s progress bar and its retention/refund
 * figures are no longer at their starting line, because those read off REFERRAL counts and
 * shared-ticket KPIs, not paid invoices, and both are real and populated now.
 *
 * SELECTORS ARE STABLE LABELS, NEVER A LIVE NUMBER — «رصيدك الجاهز للسحب», «برنامج دعم الوفاء»,
 * «رشّح نفسك لوظيفة», «سجل العمولات», «سجل السحوبات» are all fixed strings the component always
 * renders regardless of balance; a hero figure like "0 ريال" is spoken over in the caption, never
 * matched by a selector, because a later run seeding a real commission onto this account would
 * change it without changing the screen's own structure.
 */
const PHONE = '0549900110';
const PASSWORD = 'Raje3-Affiliate-Tour!1';

export default {
  id: 'affiliate-earnings-1-overview',
  title: 'أرباحي — الرصيد ودعم الوفاء وسجل العمولات كاملة',
  // UNIFIED ACROSS EVERY affiliate-*.mjs SCRIPT — see affiliate-account-1-overview.mjs's own note.
  section: 'منصة المسوّقين',
  skipAutoSignIn: true,
  // THE FIRST FRAME MUST ALREADY SHOW THE DOOR, NOT A BLANK WHITE PAINT WHILE THE APP BOOTS — a
  // real recording caught frame 0 white for ~9 frames (the bundle loading before React's first
  // paint) before `preload` was added. `preload: true` performs step 0's own `goto` BEFORE
  // capture starts and waits for the page to settle, exactly like admin-home-1-overview.mjs does
  // for the same reason on a different door.
  preload: true,
  secondsCap: 240,
  steps: [
    // ── تسجيل الدخول ────────────────────────────────────────────────────────────────────────
    {
      goto: '/affiliates',
      chapter: 'تسجيل الدخول',
      say: 'بوابة المسوّقين — بابها منفصل عن محلّك',
    },
    {
      type: 'label=رقم الجوال',
      text: PHONE,
      say: 'رقم جوالك',
    },
    {
      type: 'label=كلمة المرور',
      text: PASSWORD,
      say: 'وكلمة مرورك',
    },
    {
      click: 'role=button:تسجيل الدخول',
      say: 'وتسجّل دخولك',
    },
    // A REAL ROUND TRIP THROUGH identity-service — the first stable label on the home screen
    // after sign-in confirms it actually landed before the next step touches the nav.
    { waitFor: 'role=button:أرباحي', timeoutMs: 45_000 },
    {
      click: 'role=button:أرباحي',
      chapter: 'أرباحي',
      say: 'وندخل «أرباحي» — كل فلوسك بمكان واحد',
    },
    { waitFor: 'text=رصيدك الجاهز للسحب' },

    // ── الرصيد ──────────────────────────────────────────────────────────────────────────────
    {
      hover: 'text=رصيدك الجاهز للسحب',
      say: 'أول شي فوق: رصيدك الجاهز للسحب',
    },
    {
      say: 'رقم واحد بس — ما يتزاحم مع أي رقم ثاني',
    },
    {
      say: 'مع كل محلاتها المحالة، رصيدها لسه صفر',
    },
    {
      say: 'مو لأنها ما جابت شي',
    },
    {
      say: 'بس ما فيه اشتراك مدفوع حقيقي يفعّل العمولة بعد',
    },
    {
      say: 'وتحته: كم يتبقى بالضبط لتقدر تسحب',
    },
    {
      say: 'وبطاقتان: قيد المراجعة، وتم سحبه سابقًا',
    },
    {
      say: 'تفصيل تحت الرقم الرئيسي، لا فوقه',
    },
    {
      say: 'وزر «اسحب أرباحك» يفعّل نفسه لحظة ما رصيدك يكفي',
    },

    // ── دعم الوفاء ──────────────────────────────────────────────────────────────────────────
    { waitFor: 'text=برنامج دعم الوفاء' },
    {
      hover: 'text=برنامج دعم الوفاء',
      chapter: 'برنامج دعم الوفاء',
      say: 'وتحته بطاقة منفصلة: «دعم الوفاء»',
    },
    {
      say: 'هذي مو عمولة — راتب شهري ثابت',
    },
    {
      say: 'لو حافظت على عدد محلات نشطة عندك',
    },
    {
      say: 'شريط تقدّم يوريك وين أنت من العتبة',
    },
    {
      say: 'ومحلات نشِطة كم من كم بالضبط',
    },
    {
      say: 'ومع محلاتها الكثيرة، الشريط يتقدّم فعلاً — مو فاضي',
    },
    {
      say: 'والجملة تحته توضّح كم محل ينقصها للعتبة القادمة',
    },
    {
      say: 'وتحتها أداؤها هي: الاحتفاظ والاسترجاع',
    },
    {
      say: 'ومع هالعدد من المحلات المحالة، النسب صارت حقيقية',
    },
    {
      say: 'لا شرطة فاضية هالمرة',
    },
    {
      say: 'نسبة مبنية على بيانات فعلية الآن',
    },
    {
      say: 'ومؤشرات دعم من المحلات اللي شاركت تذاكرها معها',
    },
    {
      say: 'ما وصلها بعد إذن كتابة على تذاكر أي محل',
    },
    {
      say: 'فهذي لسه غائبة',
    },

    // ── رشّح نفسك لوظيفة ────────────────────────────────────────────────────────────────────
    { waitFor: 'text=رشّح نفسك لوظيفة' },
    {
      hover: 'text=رشّح نفسك لوظيفة',
      chapter: 'رشّح نفسك لوظيفة',
      say: 'وبطاقة ثالثة منفصلة: «رشّح نفسك لوظيفة»',
    },
    {
      say: 'برنامج مختلف، بعتبة مختلفة',
    },
    {
      say: 'عملاء مشتركون فعليًا، لا عدد محلات',
    },
    {
      say: 'نفس فكرة شريط التقدّم يقرّب لك العتبة',
    },

    // ── سجل العمولات ────────────────────────────────────────────────────────────────────────
    { waitFor: 'text=سجل العمولات' },
    {
      hover: 'text=سجل العمولات',
      chapter: 'سجل العمولات',
      say: 'وتحت البطاقات: سجل عمولاتك',
    },
    {
      say: 'كل عمولة، وحالتها',
    },
    {
      say: 'قيد المراجعة، مؤكَّدة، أو مُلغاة',
    },
    {
      say: 'ثلاث حالات واضحة، ما فيه لبس',
    },
    {
      say: 'وحساب جديد يقول بصراحة: لا عمولات بعد',
    },

    // ── سجل السحوبات ────────────────────────────────────────────────────────────────────────
    { waitFor: 'text=سجل السحوبات' },
    {
      hover: 'text=سجل السحوبات',
      chapter: 'سجل السحوبات',
      say: 'وآخر قسم: سجل طلبات السحب',
    },
    {
      say: 'كل طلب مكتمل يجيبه زر إيصال',
    },
    {
      say: 'تفتح الإيصال الحقيقي بضغطة واحدة',
    },
    {
      say: 'وحسابك الجديد لسه ما طلب سحب',
    },
    {
      say: 'سجل فاضي بصراحة، بانتظار أول رصيد يكفي',
    },
    {
      say: 'وبكذا خلصنا «أرباحي» كاملة',
    },
  ],
};
