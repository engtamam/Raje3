/**
 * «لوحة تحكم راجِع» — الرئيسية (AdminHome.tsx) + التحليل المتقدم (AdminAnalytics.tsx), full
 * coverage in ONE clip: the first screen a platform operator sees signing in, top to bottom.
 *
 * WHY THIS SCREEN IS "REAL NUMBERS ONLY", AND THAT IS THE WHOLE STORY WORTH TELLING. AdminHome's
 * own header comment says it outright: phase 4 shipped the first two numbers computed from
 * actions ALREADY declared and audited elsewhere (`billing.platform_invoices`, `tenant.list`) —
 * every other of the 35 planned tiles is built in later phases, and NONE of them is faked with a
 * placeholder in the meantime. Every `state.x != null ? <KpiCard/> : null` in the component is
 * that same discipline applied per tile: a capability the signed-in operator doesn't hold, or a
 * number nobody has computed yet, means the TILE IS ABSENT, never a zero standing in for "we
 * don't know" or "you can't see this." The narration leans on that on purpose — it is the one
 * design decision a viewer would otherwise read as "half-built" rather than "honest."
 *
 * WHY THIS SCRIPT LOGS IN FOR REAL (`skipAutoSignIn: true`, real `type`/`click` steps), UNLIKE
 * every shop tour's `useDemoSession`. AdminPortal has its own session store (`admin/session.ts`,
 * `raje3.admin.session` — a different key from the shop's own), its own door (`AdminDoor.tsx`),
 * and — critically — no self-service signup at all: an operator account exists only because
 * `deploy/seed/seed-admin.sh` (or a platform-owner granting one through this same panel) minted
 * it. record-tour.mjs has no admin-session helper the way it has `useDemoSession` for a shop, so
 * the honest way to reach this screen is the same door a real operator uses, on camera, which
 * doubles as the one honest way to show a viewer how they get in at all.
 *
 * THE ACCOUNT ITSELF: seeded once, over `/internal/tenancy/seed-owner` (identity-service's own
 * bootstrap primitive, `only_if_empty: false` — the `_platform` tenant already had an owner from
 * an earlier session, and this is deliberately a SECOND one, not a takeover of the first) with
 * role `platform-owner` — every `platform.*` capability `operator-roles.json` defines, which is
 * exactly what lets every tile on this screen that CAN render, render. `0500000902` /
 * `HomeTour2026Demo!` is not a secret worth protecting: it is a throwaway account on a dev
 * cluster with no real establishment on it.
 *
 * A REAL BUG THIS RECORDING FOUND AND FIXED. `platformMetrics.ts`'s ~13 fetch functions each
 * called `req()` with no try/catch — an `AdminRefused` thrown by ANY one of them (this session
 * hit a live 403 from `audit.query`, a scope the catalog didn't predict would be refused) fell
 * straight through `Promise.all` in AdminHome's own effect, out through React, as an UNHANDLED
 * rejection. `setState(...)` after the `Promise.all` never ran, so the WHOLE screen stayed on
 * "جارٍ التحميل…" forever — every tile that would have succeeded never rendered either, with no
 * error, no retry, nothing a viewer or an operator could act on. Fixed at the source
 * (`platformMetrics.ts`'s new `safely()` wrapper around every one of those calls, returning
 * `{ ok: false }` the same shape a missing capability already does) rather than in this script,
 * because a script cannot make a production dashboard resilient to its own backend's bad day.
 *
 * SELECTORS READ OFF THE LIVE PAGE, never off the source, and NEVER include a live number. This
 * screen aggregates real, constantly-changing platform data (tenant counts, retention, at-risk
 * counts) that every other tour-recording agent on this dev cluster is also mutating in real
 * time — a selector built from "٨٧ محلاً" today is a selector that fails the next time this runs.
 * Every `text=` selector below is a STABLE LABEL (a KpiCard's own `label`, a section's own `h3`),
 * confirmed present against a real signed-in session before this script was written; the numbers
 * themselves are left to the caption's own words ("رقمك أنت", never a specific figure spoken as
 * if it were fixed). Two tiles observed absent on that same real session — «تذاكر مفتوحة» (no
 * `tickets.inbox` capability on this catalog) and «أعضاء فريق الإدارة النشطين» (no sampled
 * first-response yet) — are narrated as ABSENT-BY-DESIGN rather than pointed at directly, so no
 * step here depends on a tile that may or may not exist for the operator watching.
 */
export default {
  id: 'admin-home-1-overview',
  title: 'لوحة الإدارة — الرئيسية والتحليل المتقدم كاملة',
  section: 'لوحة الإدارة',
  skipAutoSignIn: true,
  preload: true,
  // A LONG, DATA-HEAVY SCREEN: the home tiles AND the whole of AdminAnalytics (insights, the
  // retention trend, the peak heatmap, the affiliates section) in one clip — see bookings-2's own
  // note on why a screen this size needs more than the 180s runaway default.
  secondsCap: 360,
  steps: [
    // ── تسجيل الدخول ────────────────────────────────────────────────────────────────────────
    {
      goto: '/admin/',
      chapter: 'تسجيل الدخول',
      say: 'لوحة تحكم راجِع بابها منفصل تمامًا',
    },
    {
      say: 'لفريق المنصّة، لا لأصحاب المحلات',
    },
    {
      say: 'ولا يوجد تسجيل جديد هنا إطلاقًا',
    },
    {
      say: 'حساب المشغّل يُصنع مرة واحدة من خارج الشاشة',
    },
    {
      type: 'label=البريد الإلكتروني',
      text: '0500000902',
      say: 'ادخل برقم جوالك الإداري',
    },
    {
      type: 'label=كلمة المرور',
      text: 'HomeTour2026Demo!',
      say: 'وكلمة مرورك',
    },
    {
      click: 'role=button:تسجيل الدخول',
      say: 'وسجّل دخولك',
    },
    // AUTH IS A REAL ROUND TRIP THROUGH identity-service (/api/v1/auth/tenant) THEN A FULL
    // catalog BUILD (admin/catalog.ts's own fetchCatalog, which is what every tile below depends
    // on) — both can take a real few seconds on a shared dev cluster, so this waits for the
    // screen's own first stable label rather than a fixed pause.
    // A GENEROUS TIMEOUT, NOT THE 30s DEFAULT — this dev cluster is shared with every other
    // tour-recording agent at once, and a real /api/v1/auth/tenant round trip through the shared
    // ssh tunnel has been observed taking 15-20s alone under that load, before the catalog fetch
    // that follows it even starts.
    { waitFor: 'text=الإيراد الكلي هالشهر', timeoutMs: 180_000 },
    {
      say: 'وهذي أول شاشة تفتح لك — الرئيسية',
    },
    // ── أرقام حقيقية لا مُختلَقة ────────────────────────────────────────────────────────────
    {
      hover: 'text=الإيراد الكلي هالشهر',
      chapter: 'أرقام حقيقية لا مُختلَقة',
      say: 'أول شي تشوفه إيراد المنصّة كلها هالشهر',
    },
    {
      say: 'رقمك أنت، لا رقم تجريبي',
    },
    {
      say: 'ومحسوب من فواتير حقيقية مدفوعة',
    },
    {
      say: 'جُمّعت هالشهر مقابل الشهر اللي قبله',
    },
    {
      hover: 'text=إجمالي المحلات النشطة',
      say: 'وجنبه كم محل نشط عندك الحين',
    },
    {
      say: 'من أصل كل المحلات المسجَّلة',
    },
    {
      hover: 'text=محلات جديدة هالشهر',
      say: 'وكم محل جديد انضم بالذات هالشهر',
    },
    {
      say: 'نبض نمو المنصّة',
    },
    {
      say: 'وهذي الأربعة ما تظهر إلا',
    },
    {
      say: 'لمن يحمل صلاحية القراءة عليها',
    },
    {
      say: 'لا رقم بلا صلاحية',
    },
    {
      hover: 'text=طلبات مسوّقين معلّقة',
      say: 'وهذي طلبات انضمام مسوّقين لسه ما بتّ فيها',
    },
    {
      say: 'تحتاج قرارك',
    },
    {
      say: 'ولاحظ: كل بطاقة هنا إما رقم حقيقي محسوب الآن',
    },
    {
      say: 'أو غائبة تمامًا',
    },
    {
      say: 'لا صفر مزيّف مكانها',
    },
    // ── تنبيهات فورية ───────────────────────────────────────────────────────────────────────
    {
      chapter: 'تنبيهات فورية',
      say: 'ولو صار شي يحتاج تدخّلك الآن',
    },
    {
      say: 'دفع توقّف، تذاكر تأخّرت، خدمة ما ردّت',
    },
    {
      say: 'يطلع شريط أحمر هنا فوق',
    },
    {
      say: 'يجمعها كلها بمكان واحد بدل',
    },
    {
      say: 'ما تدوّر عليها بكل شاشة على حدة',
    },
    // ── تحليل متقدم — صحة المنصّة ───────────────────────────────────────────────────────────
    { waitFor: 'text=تحليل متقدم', timeoutMs: 120_000 },
    {
      hover: 'text=تحليل متقدم',
      chapter: 'تحليل متقدم',
      say: 'وتحت كذا يبدأ «تحليل متقدم»',
    },
    {
      say: 'أدوات أعمق من أي شاشة محل عندك',
    },
    { waitFor: 'text=صحة المنصّة والاحتفاظ', timeoutMs: 120_000 },
    {
      hover: 'text=صحة المنصّة والاحتفاظ',
      say: 'أولها صحة المنصّة كلها والاحتفاظ بعملائها',
    },
    {
      say: 'عبر كل محل عندك، لا محل واحد',
    },
    {
      hover: 'text=متوسط معدل الاحتفاظ',
      say: 'متوسط كم عميل يرجع بعد أول زيارته',
    },
    {
      say: 'عبر المنصّة كلها',
    },
    {
      hover: 'text=محلات بخطر انقطاع عملائها',
      say: 'ومحلات عملاؤها بدؤوا ينقطعون',
    },
    {
      say: 'تحتاج انتباه فريقك قبل ما تخسرهم',
    },
    {
      say: 'وتحتها اتجاه الاحتفاظ عبر آخر ستّ فترات',
    },
    {
      say: 'تصعد أو تهبط؟',
    },
    {
      say: 'وخريطة أوقات الذروة',
    },
    {
      say: 'أي يوم وأي ساعة الزحمة الحقيقية عبر كل محلاتك',
    },
    // ── المسوّقين والتسويق ──────────────────────────────────────────────────────────────────
    { waitFor: 'text=المسوّقين والتسويق', timeoutMs: 120_000 },
    {
      hover: 'text=المسوّقين والتسويق',
      chapter: 'المسوّقين والتسويق',
      say: 'وآخر قسم — قناة المسوّقين',
    },
    {
      hover: 'text=مسوّقون نشطون',
      say: 'كم مسوّق نشط عندك الحين، من أصل كل من انضم',
    },
    {
      hover: 'text=الإيراد المُحال عبر القناة',
      say: 'وكم إيراد جاءك بالضبط عن طريقهم',
    },
    {
      say: 'لا تخمين، رقم محسوب من إحالاتهم الحقيقية',
    },
    {
      say: 'ولو عندك مسوّقون بأداء عالٍ',
    },
    {
      say: 'تطلع قائمتهم هنا مباشرة',
    },
    {
      say: 'الأفضل أداءً أولًا',
    },
    // ── الخاتمة ──────────────────────────────────────────────────────────────────────────────
    { waitFor: 'text=إجراء إداري متاح', timeoutMs: 120_000 },
    {
      hover: 'text=إجراء إداري متاح',
      chapter: 'كل هذا حسب صلاحياتك',
      say: 'وآخر سطر يقول لك بالضبط كم',
    },
    {
      say: 'إجراء إداري متاح لصلاحياتك أنت تحديدًا',
    },
    {
      say: 'يزيد لو صلاحياتك أوسع، وينقص لو أضيق',
    },
    {
      say: 'نفس المبدأ من أول بطاقة لآخر سطر',
    },
  ],
};
