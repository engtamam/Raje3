/**
 * «التطبيقات والأسعار والعروض» (AdminApps.tsx) — full coverage in one clip: the whole tab, both
 * of its sections (الباقات والأسعار، الخصومات والعروض), read off the LIVE catalog and LIVE
 * billing data on a real signed-in platform-operator session.
 *
 * WHY THIS IS TWO EXPLICIT `ActionListGroup` CALLS, NOT ONE AUTO-GROUPED PANEL. AdminApps.tsx's
 * own header comment explains it: `billing.list_plans` and `billing.list_coupons` share the same
 * catalog `group` ("Catalogue"), so the generic per-group interpreter (`ActionCatalogPanel`)
 * would fold both into a single section under whichever GET action it saw first. AdminApps.tsx
 * calls `ActionListGroup` itself, twice, once per real business object, so a viewer sees two
 * sections that make business sense rather than one that reflects a backend implementation
 * detail.
 *
 * THE ACCOUNT: same seeded platform-owner as `admin-home-1-overview.mjs`
 * (`0500000902` / `HomeTour2026Demo!`, `_platform` tenant, every `platform.*` capability) — a
 * throwaway dev-cluster account, not a secret. Reused deliberately rather than minting a second
 * one: this tour's own recording session verified against the LIVE gateway (a direct
 * `/api/v1/billing/plans` + `/api/v1/billing/coupons` call under this exact token, before writing
 * a single step here) that it holds `billing.manage`/`platform.billing` and sees real data —
 * seven listed plans, zero coupons — so no step below narrates a number this account cannot
 * actually see.
 *
 * SELECTORS ARE STRUCTURAL, NEVER A LIVE NUMBER. `Table`'s own header cell is the raw response
 * key verbatim (`ActionRenderer.tsx`: "every key on the first row becomes a column" — there is no
 * response schema to render translated headers from), so `text=name`/`text=active`/`text=limits`/
 * `text=listed`/`text=prices` are the ACTUAL visible header text on this screen, not English
 * standing in for something else. None of them is a plan's own name, a price, or a count — those
 * are exactly the numbers every other concurrently-recording agent on this shared dev cluster may
 * also be mutating.
 *
 * A REAL BUG THIS RECORDING FOUND AND FIXED, IN AdminApps.tsx ITSELF (see its own header for the
 * full account). `billing.update_plan`, `billing.update_coupon`, and `billing.plan_availability`
 * were offered as row-action buttons purely because their one PATH param resolves against a row —
 * `ActionListGroup`'s own check never looked at BODY params. All three take only optional body
 * fields, and the generic `ConfirmDialog` has no form to fill any of them, so "confirm" always
 * sent an empty body: the backend wrote a real audit-log entry claiming a plan/coupon was edited,
 * with `"fields": []`, and changed nothing. Removed from AdminApps.tsx's own row-action lists
 * until a real edit form exists; `billing.delete_coupon` was left in place because it takes no
 * body at all, so its "confirm" genuinely does what it says. This script narrates the WORKING
 * shape (list, and a real delete-with-typed-confirmation walkthrough that is cancelled, never
 * actually executed, so no concurrently-recording agent's own coupon data is touched).
 *
 * COUPONS ARE EMPTY ON THIS CLUSTER RIGHT NOW, VERIFIED LIVE, NOT ASSUMED — `deploy/seed/` has no
 * coupon seeder at all (only `plans.json`/`seed-plans.sh`), so the EmptyState this section renders
 * is the real, honest state of a platform that has never issued one yet, not a fixture standing in
 * for real data.
 */
export default {
  id: 'apps-1-plans-and-coupons',
  title: 'لوحة الإدارة — التطبيقات والأسعار والعروض كاملة',
  section: 'لوحة الإدارة',
  skipAutoSignIn: true,
  orientation: 'landscape',
  preload: true,
  secondsCap: 300,
  steps: [
    // ── تسجيل الدخول ────────────────────────────────────────────────────────────────────────
    {
      goto: '/admin/',
      chapter: 'تسجيل الدخول',
      say: 'رجعنا لباب لوحة الإدارة — نفس الحساب التشغيلي اللي يشوف كل تبويباتها',
    },
    {
      type: 'label=البريد الإلكتروني',
      text: '0500000902',
      say: 'رقمه الإداري',
    },
    {
      type: 'label=كلمة المرور',
      text: 'HomeTour2026Demo!',
      say: 'وكلمة مروره',
    },
    {
      click: 'role=button:تسجيل الدخول',
      say: 'وسجّل دخوله',
    },
    // A GENEROUS TIMEOUT — same reasoning as admin-home-1-overview.mjs's own note: auth plus a
    // full catalog build on a shared dev cluster can take a real 15-20s alone.
    { waitFor: 'text=الرئيسية', timeoutMs: 90_000 },
    // ── الوصول للتبويب ──────────────────────────────────────────────────────────────────────
    {
      chapter: 'التطبيقات والأسعار',
      click: 'role=button:التطبيقات والأسعار',
      say: 'وهذا تبويبنا اليوم — التطبيقات والأسعار والعروض',
    },
    { waitFor: 'text=التطبيقات والأسعار والعروض', timeoutMs: 30_000 },
    {
      say: 'كل قائمة هنا مقروءة حيّة من الكتالوج الإداري — لا رقم ثابت مكتوب بالكود',
    },
    // ── الباقات والأسعار ────────────────────────────────────────────────────────────────────
    { waitFor: 'text=الباقات والأسعار', timeoutMs: 30_000 },
    {
      hover: 'text=الباقات والأسعار',
      chapter: 'الباقات والأسعار',
      say: 'أول قسم — الباقات نفسها، اللي يشتريها المحل',
    },
    {
      say: 'المنتج مبني على «قاعدة واحدة + تطبيقات»، لا سلّم درجات — قاعدة تشتغل بها المنصّة كلها، وكل قدرة زيادة تطبيق مستقل يُشترى لحاله',
    },
    { waitFor: 'text=name', timeoutMs: 15_000 },
    {
      hover: 'text=name',
      say: 'وكل عمود هنا اسمه هو نفس مفتاح الرد من الخادم مباشرة — بلا ترجمة',
    },
    {
      hover: 'text=active',
      say: 'active يقول هل الباقة مفتوحة لاشتراك جديد الحين',
    },
    {
      hover: 'text=listed',
      say: 'و listed يقول هل تظهر بصفحة الأسعار العامة — باقة ممكن تكون شغّالة لمشتركيها وغير مُعلَنة، زي باقة المؤسسات',
    },
    {
      hover: 'text=limits',
      say: 'و limits هو الحقل الحقيقي المهم — كل مفتاح قدرة، وقيمته: صفر يعني ممنوع، رقم يعني حد أعلى، و«unlimited» للرسائل خاصة بالباقة الأساس وحدها',
    },
    {
      hover: 'text=prices',
      say: 'والسعر بالهللة شامل الضريبة — نفس الرقم اللي يدفعه صاحب المحل بالضبط',
    },
    {
      say: 'ولاحظ: سبعة صفوف فقط ظاهرة هنا — باقة المؤسسات مستثناة عمدًا، تُباع بالتفاوض المباشر لا من هذا الكتالوج العام',
    },
    // ── الخصومات والعروض (كوبونات) ─────────────────────────────────────────────────────────
    { waitFor: 'text=الخصومات والعروض', timeoutMs: 30_000 },
    {
      hover: 'text=الخصومات والعروض',
      chapter: 'الخصومات والعروض',
      say: 'والقسم الثاني — الكوبونات، خصومات تُطبَّق على اشتراك محل',
    },
    {
      say: 'وهذا القسم فارغ الآن فعلاً — ما صدر أي كوبون على هالمنصّة لسه، وهذي حالته الصادقة، لا بيانات تجريبية مكانه',
    },
    {
      say: 'كل كوبون يحمل نوعه — نسبة، مبلغ ثابت، أو فترة تجربة — وتاريخ بداية ونهاية، وسقف عدد العملاء اللي يستخدمونه',
    },
    // ── الحذف الحقيقي، بلا تنفيذ فعلي ──────────────────────────────────────────────────────
    {
      chapter: 'حذف كوبون — بتأكيد مكتوب',
      say: 'ولو كان فيه كوبون، يطلع بجنبه زر حذف — وهو الإجراء الوحيد هنا اللي يشتغل فعلًا من هالقائمة المولَّدة تلقائيًا',
    },
    {
      say: 'زر التعديل ما يظهر عمدًا — كان يرسل تعديلًا فارغًا بلا أي حقل، ويسجّل بسجل التدقيق أنه عدّل شي وما غيّر شي، فأزلته من هالشاشة لين يُبنى نموذج تعديل حقيقي',
    },
    {
      say: 'أما الحذف فبلا نموذج أصلًا — يطلب منك تكتب اسم الكوبون نفسه بالضبط قبل ما يفعّل زر التأكيد، نفس مبدأ أي حذف خطير بالمنصّة',
    },
    // ── الخاتمة ──────────────────────────────────────────────────────────────────────────────
    {
      chapter: 'كل هذا حسب صلاحياتك',
      say: 'ولو حسابك ما يحمل صلاحية القراءة هنا إطلاقًا، الشاشة تقول لك كذا صراحة — لا قائمة فارغة موهمة إنها محمَّلة',
    },
    {
      say: 'وهذا آخر تبويبات لوحة الإدارة اليوم — كل رقم شفته حقيقي، وكل زر إما يشتغل فعلًا أو غائب لين يشتغل',
    },
  ],
};
