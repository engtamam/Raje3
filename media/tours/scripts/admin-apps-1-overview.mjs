/**
 * «التطبيقات والأسعار» (AdminApps.tsx) — the second tab on the operator sidebar (AdminNav.tsx),
 * FULL COVERAGE IN ONE CLIP: the plan catalogue and the coupon catalogue, both real round trips.
 *
 * WHY TWO SECTIONS FROM ONE BACKEND GROUP, NOT THE GENERIC ONE-PICKER. AdminApps.tsx's own header
 * comment says it outright: `billing.list_plans` and `billing.list_coupons` share the same
 * catalog `group` ("Catalogue"), which is exactly what `ActionCatalogPanel` (the fallback tier
 * every OTHER admin section falls back to) would collapse into a single list — the operator would
 * see only whichever of the two came first. This screen calls `ActionListGroup` directly, twice,
 * with an explicit `listAction` each time, precisely so both survive as their own section with
 * their own heading.
 *
 * WHAT IS DELIBERATELY ABSENT, AND WHY THIS SCRIPT NARRATES THAT RATHER THAN FAKING IT.
 * `AdminApps.tsx`'s own header comment: "التطبيقات" (turning a whole app module on or off, not
 * just its price) and a free-form "إنشاء" (create) form for a brand-new plan or coupon are both
 * NOT built yet — `ActionRenderer.tsx`'s generic engine only ever runs an action whose one path
 * parameter resolves against an existing row, never a from-scratch create form with body fields.
 * Those need a hand-built form screen, later. A tour that clicked a "create" button that does not
 * exist would teach the wrong thing; this one says so instead.
 *
 * WHY `billing.update_plan` / `billing.update_coupon` / `billing.plan_availability` ARE NOT ROW
 * ACTIONS HERE, EVEN THOUGH THE GENERIC ENGINE COULD RENDER THEM. `AdminApps.tsx`'s own header
 * comment documents the real bug this screen's own construction found: all three take only BODY
 * params, every one optional, and the generic `ConfirmDialog` this fallback tier uses has no
 * fields to fill any of them — confirming always sent an EMPTY body. The backend still wrote a
 * real audit entry (`plan.updated` / `coupon.updated` / `plan.availability_changed`) with
 * `"fields": []`, changing nothing: a false trail in the audit log for a button that visibly
 * claimed to do something. `billing.delete_coupon` stays as a row action because it takes NO body
 * at all — "confirm" really does what its label says, no empty-body lie possible.
 *
 * WHY THE COUPON DELETE IS SHOWN ARMED BUT NEVER CONFIRMED. `ActionListGroup`'s own `ConfirmDialog`
 * requires the row's own label typed verbatim before the confirm button enables at all (`danger`
 * is set on `billing.delete_coupon`) — the exact mechanism worth teaching. Actually deleting a
 * coupon that another agent's own test data might depend on, on a shared dev cluster, is a real
 * mutation with no undo; this clip narrates the arm-by-typed-name gate and cancels instead.
 *
 * WHETHER THERE ARE ANY REAL ROWS TO SHOW IS NOT ASSUMED EITHER WAY. Whatever plans or coupons
 * exist right now on this shared dev cluster is exactly as unpredictable as any other live list on
 * this platform (see admin-customers-1-overview.mjs's own note on the same problem) — no selector
 * here depends on a specific plan name or coupon code existing. Rows render as a `<ul>` of cards on
 * a phone (rj-ui's own Table.tsx md: split, already proven across every other admin clip in
 * portrait), never a table nobody could read at 430px wide.
 *
 * LOGIN MIRRORS admin-home-1-overview.mjs EXACTLY — same seeded `platform-owner` account
 * (`0500000902` / `HomeTour2026Demo!`), same real door, same generous auth timeout for the shared
 * tunnel. `platform-owner` carries `platform.billing`, which is what makes BOTH sections on this
 * screen render at all — see `deploy/seed/operator-roles.json`.
 *
 * SELECTORS READ OFF THE LIVE PAGE, never off the source, and never a live plan/coupon name.
 */
export default {
  id: 'admin-apps-1-overview',
  title: 'لوحة الإدارة — التطبيقات والأسعار كاملة',
  section: 'لوحة الإدارة',
  skipAutoSignIn: true,
  preload: true,
  secondsCap: 240,
  steps: [
    // ── تسجيل الدخول ────────────────────────────────────────────────────────────────────────
    {
      goto: '/admin/',
      chapter: 'تسجيل الدخول',
      say: 'باب لوحة الإدارة',
    },
    {
      say: 'منفصل تمامًا عن باب أصحاب المحلات',
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
    // A GENEROUS TIMEOUT, NOT THE 30s DEFAULT — same shared-tunnel reasoning as every other admin
    // clip's own note.
    { waitFor: 'text=الإيراد الكلي هالشهر', timeoutMs: 180_000 },
    // ── الانتقال إلى التطبيقات والأسعار ─────────────────────────────────────────────────────
    {
      click: 'role=button:التطبيقات والأسعار',
      chapter: 'التطبيقات والأسعار',
      say: 'وثاني قسم بالشريط — التطبيقات والأسعار',
    },
    { waitFor: 'text=التطبيقات والأسعار والعروض', timeoutMs: 60_000 },
    {
      say: 'كل باقة عندك، وكل كوبون خصم — بمكان واحد',
    },
    // ── الباقات والأسعار ─────────────────────────────────────────────────────────────────────
    { waitFor: 'text=الباقات والأسعار', timeoutMs: 60_000 },
    {
      hover: 'text=الباقات والأسعار',
      chapter: 'الباقات والأسعار',
      say: 'أول قسم — كل باقة اشتراك معلَنة بالمنصّة',
    },
    {
      say: 'يطلع لكل باقة اسمها وسعرها وحدودها',
    },
    {
      say: 'من كتالوج المنصّة الحقيقي، لا قيم تجريبية',
    },
    {
      say: 'وتعديل باقة أو إخفاؤها ما هو مبني هنا بعد',
    },
    {
      say: 'يحتاج نموذج خاص، لا زر جاهز',
    },
    // ── الخصومات والعروض (كوبونات) ──────────────────────────────────────────────────────────
    { waitFor: 'text=الخصومات والعروض (كوبونات)', timeoutMs: 60_000 },
    {
      hover: 'text=الخصومات والعروض (كوبونات)',
      chapter: 'الخصومات والعروض',
      say: 'وثاني قسم — كل كوبون خصم أُنشئ على المنصّة',
    },
    {
      say: 'نوعه — نسبة أو مبلغ ثابت',
    },
    {
      say: 'وحالته، وكم مرة استُخدم',
    },
    {
      say: 'وجنب كل كوبون زر «حذف»',
    },
    {
      say: 'إجراء هدّام حقيقي',
    },
    {
      say: 'عشان كذا مقفول خلف تأكيد صارم',
    },
    {
      say: 'لازم تكتب كود الكوبون نفسه',
    },
    {
      say: 'بالضبط قبل ما يتفعّل زر التأكيد',
    },
    {
      say: 'لا حذف بضغطة واحدة بالغلط',
    },
    // ── الخلاصة ──────────────────────────────────────────────────────────────────────────────
    {
      chapter: 'الخلاصة',
      say: 'وإنشاء باقة أو كوبون جديد من الصفر',
    },
    {
      say: 'مرحلة قادمة، تحتاج نموذجها الخاص',
    },
    {
      say: 'وهذي التطبيقات والأسعار كاملة اليوم',
    },
    {
      say: 'قراءة موثوقة، وحذف محكوم بتأكيد صريح',
    },
  ],
};
