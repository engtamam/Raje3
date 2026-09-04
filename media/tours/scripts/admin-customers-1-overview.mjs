/**
 * «العملاء والدعم» — لوحة الإدارة، كامل ما هو مبني فعلاً اليوم في مقطع واحد: طلبات المسوّقين
 * المعلّقة (عبر المحرّك العام `ActionCatalogPanel`) وتشخيص واتساب لمحل (شاشة يدوية مصقولة).
 *
 * WHY ONLY TWO SUB-TABS, NOT THE SIX THIS SECTION EVENTUALLY OWNS. AdminCustomers.tsx's own
 * header comment says it outright: this is phase 3 only — the seven-column customer table and
 * the six-tab customer file are later phases (7/9), never faked here with a placeholder table.
 * A tour that pretended those existed would teach a viewer to look for controls that aren't
 * there yet. Narrating that gap honestly, the same way admin-home-1-overview narrated an absent
 * KPI tile as "not yet, not broken", is the point of this clip as much as what IS built.
 *
 * WHY AFFILIATES RENDERS THROUGH THE GENERIC ENGINE. `ActionCatalogPanel` builds a table straight
 * from whatever the catalog declares for group "Affiliates" — columns come from the FIRST ROW'S
 * OWN KEYS, not a fixed schema, so this script never selects a specific column header or row: on
 * a shared dev cluster, which affiliate applications are pending right now is exactly as
 * unpredictable as bookings-2's own real numbers, and a selector built from today's applicant
 * name is a selector that breaks the next time this runs. The section heading itself
 * (`s.listAction.label`, "طلبات التسويق المعلّقة") is the one stable anchor, so that is what
 * every wait in this section keys on.
 *
 * WHY NO ROW IS APPROVED OR REJECTED ON CAMERA. Both actions are declared `confirm: true`, and
 * reject is `danger: true` — armed, per ConfirmDialog's own rule, by typing the target's own
 * name. Whatever application is pending right now on this shared dev cluster may belong to
 * another agent's own test data; approving or rejecting it for a recording would be a real
 * mutation with no way to undo it cleanly. So this script narrates the mechanism from the code
 * (confirm-by-name for the destructive path) rather than clicking a row that might not even be
 * there when this runs.
 *
 * WHY WHATSAPP DIAGNOSTICS IS SEARCHED FOR REAL, WITH A TENANT THAT DEFINITELY EXISTS. `_platform`
 * is the platform's own tenant id — not a shop, so this is a real round trip through the actual
 * gateway, not a scripted stand-in. ON THIS DEV CLUSTER THE ROUTE ITSELF ANSWERS 404 — this
 * recording confirmed with a direct curl that the deployed `operations-service` pod predates
 * `api/v1/platform.py`'s own `/whatsapp/diagnostics` route (a real deploy-lag on a shared dev
 * cluster, not a bug in this screen's own code), so the honest thing on camera is the SAME
 * failure state a real operator would see today, narrated as what it actually is.
 *
 * A REAL BUG THIS RECORDING FOUND AND FIXED ANYWAY, ONE LAYER UP. Investigating that failure
 * surfaced that `apps/console/src/admin/api.ts`'s generic `req()` only ever read
 * `message`/`detail` off a refused response — every OTHER operations-service route that answers
 * `{error, reason}` (`_refuse`'s own shape in `platform.py`, used across at least four routes
 * including this one's own 502 path) had its real, specific `reason` sentence silently dropped in
 * favour of the generic "تعذّر إكمال الطلب. حاول مرة أخرى." — even when the backend had already
 * written the operator a precise explanation. Fixed at the source (`req()` now falls back to
 * `reason` too), so any of those routes that DOES reach this screen live shows its own real
 * sentence from here on, not a placeholder — the same discipline admin-home-1-overview's own
 * header note describes for its real bug. Per this screen's own header comment, there is also
 * deliberately no "create a ticket from this" action yet — ticket-service has no admin primitive
 * for it — so this script narrates that as a real limit too, not a missing button.
 *
 * LOGIN MIRRORS admin-home-1-overview.mjs EXACTLY — same seeded `platform-owner` account
 * (`0500000902` / `HomeTour2026Demo!`), same real door (`skipAutoSignIn: true`, no admin
 * equivalent of the shop's `useDemoSession`), same generous auth timeout for the shared tunnel.
 */
export default {
  id: 'admin-customers-1-overview',
  title: 'لوحة الإدارة — العملاء والدعم كاملة',
  section: 'لوحة الإدارة',
  skipAutoSignIn: true,
  preload: true,
  secondsCap: 240,
  steps: [
    // ── تسجيل الدخول ────────────────────────────────────────────────────────────────────────
    {
      goto: '/admin/',
      chapter: 'تسجيل الدخول',
      say: 'باب لوحة الإدارة — منفصل عن باب أصحاب المحلات',
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
    // A GENEROUS TIMEOUT, NOT THE 30s DEFAULT — same shared-tunnel reasoning as admin-home-1's own.
    { waitFor: 'text=الإيراد الكلي هالشهر', timeoutMs: 180_000 },
    // ── الانتقال إلى العملاء والدعم ─────────────────────────────────────────────────────────
    {
      click: 'role=button:العملاء والدعم',
      chapter: 'العملاء والدعم',
      say: 'وهذا قسم اليوم — العملاء والدعم',
    },
    { waitFor: 'text=طلبات المسوّقين', timeoutMs: 60_000 },
    {
      say: 'واليوم فيه بابين اثنين فقط',
    },
    {
      say: 'طلبات المسوّقين، وتشخيص واتساب',
    },
    {
      say: 'وبقية هذا القسم',
    },
    {
      say: 'جدول العملاء وملف العميل الكامل',
    },
    {
      say: 'مرحلة قادمة، ما بُنيت بعد',
    },
    {
      say: 'وما راح تشوفها اليوم',
    },
    // ── طلبات المسوّقين ─────────────────────────────────────────────────────────────────────
    { waitFor: 'text=طلبات التسويق المعلّقة', timeoutMs: 60_000 },
    {
      hover: 'text=طلبات التسويق المعلّقة',
      chapter: 'طلبات المسوّقين المعلّقة',
      say: 'أول باب — كل طلب انضمام مسوّق لسه ينتظر قرارك',
    },
    {
      say: 'هذا الجدول ما هو مبني',
    },
    {
      say: 'يدويًا لهذي الشاشة بالذات',
    },
    {
      say: 'محرّك عام واحد يرسم أي',
    },
    {
      say: 'إجراء إداري معلَن بالكتالوج',
    },
    {
      say: 'فأعمدته تتغيّر حسب شكل البيانات نفسها',
    },
    {
      say: 'لا حسب تصميم ثابت من قبل',
    },
    {
      say: 'ولكل طلب زرّان',
    },
    {
      say: 'قبول، أو رفض. والرفض مقفول خلف تأكيد صارم',
    },
    {
      say: 'لازم تكتب اسم الطلب نفسه',
    },
    {
      say: 'بالضبط قبل ما يفعّل زر التأكيد',
    },
    {
      say: 'قرار لا يُتّخذ بضغطة واحدة بالغلط',
    },
    // ── تشخيص واتساب ────────────────────────────────────────────────────────────────────────
    {
      click: 'role=radio:تشخيص واتساب',
      chapter: 'تشخيص واتساب',
      say: 'والباب الثاني — تشخيص واتساب لمحل',
    },
    // AdminWhatsAppDiagnostics fetches its OWN catalog copy on mount (a separate round trip from
    // the one already done to sign in) — a generous timeout for the same shared-tunnel reasoning
    // as every other admin clip's own note, not the 30s default.
    { waitFor: 'text=تشخيص واتساب لمحل', timeoutMs: 120_000 },
    {
      say: 'سؤال يتكرر من أصحاب المحلات',
    },
    {
      say: '«ليش ما وصلت رسالتي؟»',
    },
    {
      say: 'وهذي إجابته المباشرة',
    },
    {
      hover: 'label=معرّف التينانت',
      say: 'ابحث إما بمعرّف تينانت المحل نفسه',
    },
    {
      hover: 'label=رقم ميتا (phone_number_id)',
      say: 'أو برقم ميتا',
    },
    {
      say: 'رقم واتساب الأعمال المسجَّل عندهم',
    },
    {
      type: 'label=معرّف التينانت',
      text: '_platform',
      say: 'أبحث الآن بمعرّف تينانت المنصّة نفسها',
    },
    {
      say: 'تينانت حقيقي موجود دائمًا',
    },
    {
      click: 'role=button:بحث',
      say: 'وأضغط بحث',
    },
    // A REAL ROUND TRIP THROUGH THE ACTUAL GATEWAY — on this dev cluster the route itself is not
    // deployed yet (confirmed by a direct curl: 404 NOT_FOUND), so the screen shows a real failure
    // state, honestly, exactly as a real operator would see it today.
    { waitFor: 'text=تعذّر إكمال الطلب', timeoutMs: 30_000 },
    {
      say: 'وهذا رد صادق، لا رقم مزيّف',
    },
    {
      say: 'الخدمة المسؤولة ما ردّت بنجاح الآن',
    },
    {
      say: 'ولو نجح الاتصال',
    },
    {
      say: 'تشوف هنا حالة كل رسالة أُرسلت لهذا المحل',
    },
    {
      say: 'وصلت، تأخّرت، أو رفضتها ميتا مع سبب الرفض',
    },
    {
      say: 'ولاحظ: ما فيه زر «أنشئ تذكرة» من هذي النتيجة',
    },
    {
      say: 'وهذا حدّ حقيقي اليوم',
    },
    {
      say: 'خدمة التذاكر ما تقدر تفتح',
    },
    {
      say: 'تذكرة نيابة عن عميل من هنا بعد',
    },
    {
      say: 'لا نقص تصميم',
    },
  ],
};
