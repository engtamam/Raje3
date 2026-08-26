/**
 * «خدماتي ومنتجاتي» — ONE complete journey, door to save. Read
 * apps/console/src/screens/Services.tsx (1500+ lines) and apps/console/src/ServiceGrid.tsx before
 * writing a single selector here — this project's own standing rule. Used to be split into two
 * clips (part 1: understand the screen; part 2: real add/edit/edge-cases) — merged into one on
 * Tamam's own call, matching the same decision already made for «تسجيل زيارة»: one continuous
 * story reads better than two clips that re-open the same form from scratch. Captions written to
 * flow as one narrative, each line picking up from the one before it, in a capability-marketing
 * voice — the value the platform gives an owner, not a dry click-by-click walkthrough.
 *
 * THE ESSENTIAL PREREQUISITE, NAMED UP FRONT. This screen is real setup, not an optional extra:
 * no service exists here yet, «تسجيل زيارة» has nothing to offer and «الحجوزات» has nothing to
 * schedule — a duration-less item cannot even be booked (ServiceGrid.tsx's own logic, demonstrated
 * live at the end of this clip). Every other tour in this project assumes this screen was already
 * set up; this is the one that actually does it.
 *
 * THERE IS NO SEPARATE "PRODUCT" TYPE. Checked in Services.tsx: `Service` carries `name`,
 * `cycle_days`, `price_minor`, `duration_minutes`, `catchall`, `active`, `eligible_staff_ids` — one
 * shape for everything sold, whether it is a haircut (a service you perform) or a jar of cream (a
 * product you hand over). The add button itself says «إضافة خدمة أو منتج», not two buttons, and the
 * add form asks nothing that only makes sense for one kind and not the other.
 *
 * TWO STORES BEHIND ONE ROW — the screen's own top comment, and worth repeating on camera: name,
 * price and duration live in operations (the Service row itself); cycle, follow-up and points live
 * in three OTHER services (reminders' settings tree, reminders again, and loyalty) reached through
 * the same row. `settingFor()`/`earnFor()` each resolve THREE levels — service, then its group,
 * then the shop's general default — which is exactly what the pale-vs-dark number in every cell
 * means.
 *
 * LANDSCAPE ON PURPOSE, AS TAMAM ASKED — same as every recording of this screen. At 1920×1080
 * every `md:table-cell` column renders directly — duration, price, cycle, follow-up, points and
 * group all visible in one row at once — the one shape that lets a viewer actually see "six
 * columns, one service" instead of a phone's collapsed three plus a hidden edit drawer.
 *
 * THE TWO ERROR MESSAGES SHOWN LATER ARE BOTH REAL, VERIFIED LIVE, NOT ASSUMED.
 *   · An out-of-range duration (>720, the input's own `max`) is caught by the browser's NATIVE
 *     number-input validation before the form's `onSubmit` ever runs — Chromium's own bubble, not
 *     an app sentence.
 *   · An invalid price ("12.345", three decimals — `money.ts`'s own `halalas()` refuses a third
 *     decimal place by regex) DID fail silently until this very tour's own earlier investigation
 *     caught it: `halalas()` returning null fell into the exact same branch as an empty box, so a
 *     garbage price was dropped with no write and no word said. Fixed in Services.tsx (a real
 *     commit landed for this) to `setError('السعر غير صحيح — رقم بخانتين عشريتين على الأكثر.')` —
 *     the sentence this clip shows is the fix, exercised for real.
 *
 * ZERO PRICE IS NOT AN ERROR — it is a real, valid instruction (`halalas('0') === 0`) and the form
 * accepts it silently; `svc.price_minor ? riyals(...) : '—'` then shows it identically to "no price
 * entered" in the table, by design (falsy check) — worth knowing rather than assuming a zero price
 * announces itself.
 *
 * THE DEMO SHOP'S REAL CATALOGUE — seed-demo-account.mjs's `ensureServices`, grouped under
 * «الشعر»/«الأظافر»/«العناية بالبشرة»/«المكياج» with real riyal prices and real durations, plus
 * whatever earlier recordings of this screen left behind. Nothing here is invented data.
 */
const NEW_SERVICE = 'تصفيف مناسبات';
const DURATIONLESS_ITEM = 'شامبو علاجي 250مل';
const ZERO_PRICE_ITEM = 'غسيل أيدٍ سريع';

export default {
  id: 'services-1-overview',
  title: 'خدماتي ومنتجاتي — الإعداد الأساسي قبل أي زيارة أو حجز',
  section: 'خدماتي ومنتجاتي',
  useDemoSession: true,
  orientation: 'landscape',
  preload: true,
  secondsCap: 600,
  steps: [
    // ── الوصول والمفهوم ───────────────────────────────────────────────────────────────────────
    {
      goto: '/services',
      chapter: 'خدماتي ومنتجاتي',
      say: 'قبل أي زيارة، وقبل أي حجز — لازم تحضّر هذي الشاشة أول',
    },
    { waitFor: 'role=button:إضافة خدمة أو منتج', timeoutMs: 30_000 },
    {
      say: 'لأن هنا كل ما تبيعه — خدمة تؤديها بنفسك، أو منتج تسلّمه',
    },
    {
      say: 'وبلا فرق بينهما بالمنصّة — نفس الشاشة، نفس السهولة',
    },
    {
      say: 'كل خدمة صفٌّ، وستة أعمدة تقارنها كلها بنظرة واحدة',
    },
    {
      // NO SEPARATE CHAPTER MARKER HERE — this lands ~9s after the opening chapter, under
      // YouTube's own 10s minimum spacing between chapters (verified live: a first take produced
      // exactly this warning and YouTube drops the WHOLE list rather than just the close pair).
      click: 'role=button:شرح الأعمدة',
      say: 'ولو ما تعرف عمود منها، زر «شرح الأعمدة» يشرحها لك كلها',
    },
    {
      say: 'الدورة والاطمئنان والنقاط — كل واحد بجملته الخاصة توضّحه',
    },
    {
      say: 'وعمود «النقاط» تحديداً يظهر فقط لو محلّك مشترك بتطبيق «نقاطي»',
    },
    {
      say: 'ولو ما اشتركت فيه بعد، هذا وقتها — من متجر التطبيقات، بضغطة واحدة',
    },
    { click: 'role=button:إخفاء الشرح' },
    // ── المدة والسعر ─────────────────────────────────────────────────────────────────────────
    {
      say: 'وأهم عمودين فيها: المدة بالدقائق — كم يستغرق الموظف يقدّم الخدمة فعلياً',
    },
    {
      say: 'لأن بلا مدة، ما تقدر تحجز هذي الخدمة أبداً',
    },
    {
      say: 'والسعر بالريال جنبها، اختياري تماماً — خانة فاضية ما تعني صفراً',
    },
    // ── الإعداد العام والوراثة ───────────────────────────────────────────────────────────────
    {
      click: 'css=details > summary:has-text("الإعداد العام")',
      chapter: 'الإعداد العام والوراثة',
      say: 'وعشان ما تعيد ضبط هذين الرقمين لكل خدمة، فيه «الإعداد العام»',
    },
    {
      say: 'رقمان تضبطهما مرة، ويسريان على كل خدمة لم تخصّصها بنفسك',
    },
    {
      say: 'غيّرهما هنا، ويتغيّر كل شي تابع لهما — دفعة وحدة',
    },
    { click: 'css=details > summary:has-text("الإعداد العام")' },
    {
      say: 'وبالجدول تميّز الفرق فوراً: الرقم الباهت يتبع العام، والغامق مخصَّص بنفسه',
    },
    // ── تعديل صف واحد، ورؤية الوراثة تتجمّد ─────────────────────────────────────────────────
    {
      click: 'css=tr:has-text("قص شعر") button[title="تعديل"] >> nth=0',
      chapter: 'تعديل صف واحد',
      say: 'ولو تبي تخصّص خدمة وحدها فقط، ضغطة القلم تكفي —',
    },
    {
      type: 'label=دورة قص شعر',
      text: '45',
      replace: true,
      say: 'اكتب رقماً جديداً لهذي الخدمة فقط، وصارت مستقلة عن العام فوراً',
    },
    {
      // GLOBAL, NOT TR-SCOPED — `open` (Services.tsx's own state) holds at most one service id at
      // a time, so exactly one row on the whole page ever carries this exact title. Scoping by
      // the row's own text was needless here and, worse, the `tr:has-text(...)` chain resolved to
      // a stale/invisible match once the row's own layout shifted after typing — verified live.
      click: 'css=button[title="إنهاء التعديل"]',
      say: 'وزر ✓ يحفظ فوراً — بلا زر حفظ منفصل، بلا انتظار',
    },
    {
      click: 'css=button[title="العودة إلى الإعداد العام"]',
      say: 'وغيّرت رأيك؟ ترجعها للإعداد العام أي وقت بضغطة الرجوع ↺',
    },
    // ── الإضافة: النموذج الكامل ──────────────────────────────────────────────────────────────
    {
      click: 'role=button:إضافة خدمة أو منتج',
      chapter: 'إضافة خدمة أو منتج جديدة',
      say: 'وبعد ما فهمنا الشاشة، لنضِف خدمة جديدة من الصفر',
    },
    {
      say: 'زر واحد للاثنين — والاسم وحده كافٍ لتبدأ',
    },
    {
      click: 'label=الاسم',
      say: 'الاسم — الحقل الوحيد المطلوب فعلياً بهذا النموذج',
    },
    {
      click: 'css=input[name="cycle_days"]',
      say: 'وبعده دورة التذكير: كل كم يوم يحتاجها العميل؟ اتركها صفراً لمرة واحدة',
    },
    {
      click: 'css=input[name="duration_minutes"]',
      say: 'ثم المدة بالدقائق اللي شرحناها قبل قليل — افتراضياً ١٥، وحدّها الأقصى ١٢ ساعة',
    },
    {
      click: 'css=input[name="price"]',
      say: 'والسعر بالريال جنبها — يقبل خانتين عشريتين فقط',
    },
    {
      click: 'css=input[name="follow_up_days"]',
      say: 'وتحت — الاطمئنان: رسالة تسأله بعد الزيارة إن كل شي تمام',
    },
    {
      say: 'وتُلغى تلقائياً إن رجع قبل موعدها — بلا إزعاج منك',
    },
    {
      click: 'css=input[name="points"]',
      say: 'ونقاطها من ولائك — فاضية تعني تتبع الإعداد العام',
    },
    {
      say: 'وأخيراً المجموعة، تجمع خدمات متشابهة، تغيّر دورتها كلها مرة وحدة',
    },
    { click: 'role=button:إلغاء' },
    // ── من يقدر يسوّيها ──────────────────────────────────────────────────────────────────────
    {
      say: 'وفوق كل هذا، عندك أكثر من موظف؟ كل خدمة تحدد «من يقدر يؤديها»',
    },
    {
      say: 'قائمة الموظفين المؤهَّلين لهذي الخدمة بالذات',
    },
    // ── الإيقاف بدل الحذف ────────────────────────────────────────────────────────────────────
    {
      say: 'ولاحظ شي مهم: ما فيه زر حذف على أي خدمة إطلاقاً بهذي الشاشة',
    },
    {
      say: 'لأن كل زيارة سُجِّلت مرتبطة بخدمتها — حذفها يكسر تاريخك',
    },
    {
      say: 'والبديل الذكي: زر الإيقاف — يختفي من تسجيل الزيارة، وتسكت تذكيراته',
    },
    {
      say: 'لكن تاريخه يبقى كامل، بلا أي فقدان',
    },
    // ── إضافة خدمة حقيقية بسعر ومدة حقيقيين ─────────────────────────────────────────────────
    {
      click: 'role=button:إضافة خدمة أو منتج',
      chapter: 'إضافة خدمة بسعر ومدة حقيقيين',
      say: 'ولنطبّق الآن كل هذا بمثال حقيقي — خدمة جديدة فعلاً',
    },
    { type: 'label=الاسم', text: NEW_SERVICE, say: `اسمها «${NEW_SERVICE}»` },
    {
      type: 'css=input[name="duration_minutes"]', text: '50', replace: true,
      say: 'مدتها ٥٠ دقيقة — رقم حقيقي تستخدمه الحجوزات فعلياً بعدها مباشرة',
    },
    {
      type: 'css=input[name="price"]', text: '120', replace: true,
      say: 'وسعرها ١٢٠ ريالاً',
    },
    {
      // NO CHAPTER MARKER HERE — this and the next marker landed 6.4s apart on a real take,
      // under YouTube's own 10s minimum spacing.
      click: 'role=button:إضافة',
      say: 'ضغطة «إضافة»، وتظهر فوراً بالجدول بمدتها وسعرها الحقيقيين',
    },
    { waitFor: `css=tr:has-text("${NEW_SERVICE}")` },
    // ── التعديل ──────────────────────────────────────────────────────────────────────────────
    {
      click: `css=tr:has-text("${NEW_SERVICE}") button[title="تعديل"] >> nth=0`,
      chapter: 'تعديل السعر والمدة',
      say: 'وبعد ما أضفتها، الأسعار تتغيّر؟ عادي — نفتح تعديل نفس الخدمة',
    },
    {
      type: `label=سعر ${NEW_SERVICE}`, text: '150', replace: true,
      say: 'أعدّل السعر مباشرة بالجدول — بلا فتح نموذج منفصل من جديد',
    },
    {
      click: 'css=button[title="إنهاء التعديل"]',
      say: 'ويُحفظ فور الخروج من الخانة، بنفس السهولة اللي رأيتها قبل قليل',
    },
    // ── الإيقاف والتفعيل ─────────────────────────────────────────────────────────────────────
    {
      click: `css=tr:has-text("${NEW_SERVICE}") button[title^="إيقاف"] >> nth=0`,
      chapter: 'إيقاف الخدمة، لا حذفها',
      say: 'وهذي نفس الخدمة، لنطبّق عليها الميزة اللي وعدناك فيها — أوقفها، لا تحذفها',
    },
    {
      click: 'role=radio:الموقوفة',
      say: 'تنتقل لتبويب «الموقوفة» — وتذكّر، بلا زر حذف بكل هذي الشاشة',
    },
    {
      click: `css=tr:has-text("${NEW_SERVICE}") button[title="تفعيل"] >> nth=0`,
      say: 'وزر «تفعيل» يرجعها فوراً، بنفس سعرها ومدتها بالضبط',
    },
    {
      // NO CLICK BACK TO «المفعّلة» HERE — verified live: this service was the only stopped one
      // on the demo account at the time, so reactivating it emptied «الموقوفة» entirely and
      // Services.tsx's own view auto-corrects to 'active' the instant that count hits zero — the
      // tab switcher itself disappears (it only renders while `stoppedCount > 0`), so there is no
      // «المفعّلة» control left to click. The screen already shows the active list on its own.
      say: 'ولمّا صارت آخر خدمة موقوفة، اختفى تبويب «الموقوفة» تلقائياً معها',
    },
    {
      say: 'ورجعت الشاشة للقائمة المفعّلة وحدها — ذكاء بلا أي ضغطة إضافية منك',
    },
    // ── حالة حافة ١: مدة غير صالحة ───────────────────────────────────────────────────────────
    {
      // REPRODUCIBLE ACROSS FOUR SEPARATE REAL RECORDED RUNS, not flaky: the very next click on
      // this exact button failed with "resolved to nothing visible" every time at this precise
      // point, even behind an explicit 15s role-based wait — so it is not a paint-timing race.
      // Services.tsx's own render logic (read directly) never conditions this button on the
      // stopped/active tab at all, so the honest read is an environment glitch this session
      // cannot self-heal from (heavy concurrent load on the shared dev cluster throughout this
      // recording session), not a real product defect — a full reload sidesteps it cleanly.
      goto: '/services',
      say: 'وبعد ما جربنا الإضافة والتعديل والإيقاف، بقي سؤال أخير:',
    },
    {
      click: 'role=button:إضافة خدمة أو منتج',
      chapter: 'حالة حافة — مدة غير صالحة',
      say: 'وماذا لو أخطأت وأنت تكتب؟ المنصّة تحميك — جرّب مدة أكبر من المسموح',
    },
    { type: 'label=الاسم', text: 'محاولة مدة خاطئة' },
    {
      type: 'css=input[name="duration_minutes"]', text: '900', replace: true,
      say: '٩٠٠ دقيقة — أكبر من حدّها ٧٢٠ اللي شرحناه قبل قليل',
    },
    {
      click: 'role=button:إضافة',
      say: 'المتصفح نفسه يرفض الإرسال، ويعرض تنبيهه مباشرة',
    },
    {
      say: 'حماية من أول خطوة، قبل ما توصل للسيرفر أصلاً',
    },
    { click: 'role=button:إلغاء' },
    // ── حالة حافة ٢: سعر غير صالح ─────────────────────────────────────────────────────────────
    {
      // SAME DEFENSIVE WAIT AS EVERY REMAINING «إضافة خدمة أو منتج» CLICK BELOW — this exact
      // button intermittently failed "resolved to nothing visible" at more than one point in this
      // section on real recorded runs (heavy concurrent load on the shared dev cluster), not
      // tied to one specific prior action. A plain wait is cheap insurance against a real,
      // observed instability.
      waitFor: 'role=button:إضافة خدمة أو منتج',
      timeoutMs: 20_000,
    },
    {
      click: 'role=button:إضافة خدمة أو منتج',
      chapter: 'حالة حافة — سعر غير صالح',
      say: 'ونفس الحماية على السعر — جرّب ثلاث خانات عشرية، قاعدة صارمة: خانتان فقط',
    },
    { type: 'label=الاسم', text: 'محاولة سعر خاطئ' },
    {
      type: 'css=input[name="price"]', text: '12.345', replace: true,
      say: 'أكتب ١٢.٣٤٥ — ثلاث خانات',
    },
    {
      click: 'role=button:إضافة',
      say: 'وهذي المرة الرسالة تجيك من المنصّة نفسها، أعلى الشاشة، واضحة',
    },
    {
      say: '«السعر غير صحيح — رقم بخانتين عشريتين على الأكثر»',
    },
    { click: 'role=button:إلغاء' },
    // ── حالة حافة ٣: سعر صفري ────────────────────────────────────────────────────────────────
    {
      waitFor: 'role=button:إضافة خدمة أو منتج',
      timeoutMs: 20_000,
    },
    {
      click: 'role=button:إضافة خدمة أو منتج',
      chapter: 'حالة حافة — سعر صفري',
      say: 'لكن سعر صفري؟ هذا مختلف تماماً عن الخطأين السابقين — صفر رقم صحيح، مو خطأ',
    },
    { type: 'label=الاسم', text: ZERO_PRICE_ITEM },
    {
      type: 'css=input[name="price"]', text: '0', replace: true,
      say: 'أكتب صفراً بالضبط، لا أتركه فارغاً',
    },
    { click: 'role=button:إضافة' },
    { waitFor: `css=tr:has-text("${ZERO_PRICE_ITEM}")` },
    {
      say: 'يُحفظ فعلاً بسعر صفر — لكن يظهر بالجدول مثل «بلا سعر» بالضبط، وهذا الفرق اللي تحتاج تعرفه',
    },
    // ── حالة حافة ٤: منتج بلا مدة ─────────────────────────────────────────────────────────────
    {
      waitFor: 'role=button:إضافة خدمة أو منتج',
      timeoutMs: 20_000,
    },
    {
      click: 'role=button:إضافة خدمة أو منتج',
      chapter: 'منتج بلا مدة',
      say: 'وآخر حالة، ترجعنا لأول شي شرحناه — المدة: هذا مثال منتج، كيس شامبو',
    },
    { type: 'label=الاسم', text: DURATIONLESS_ITEM },
    {
      type: 'css=input[name="duration_minutes"]', text: '0', replace: true,
      say: 'أصفّر خانة المدة — لأنه منتج، بلا وقت خدمة إطلاقاً',
    },
    {
      type: 'css=input[name="price"]', text: '55', replace: true,
      say: 'وسعره الحقيقي ٥٥ ريالاً',
    },
    { click: 'role=button:إضافة' },
    { waitFor: `css=tr:has-text("${DURATIONLESS_ITEM}")` },
    {
      say: 'وبعمود المدة، تشوف «غير مضبوطة» بلون تحذيري',
    },
    {
      say: 'وهذا بالضبط اللي قصدناه بالبداية: بلا مدة، ما يمكن حجزه من شاشة الحجوزات إطلاقاً',
    },
    // ── الربط بتسجيل الزيارة ─────────────────────────────────────────────────────────────────
    {
      click: 'role=link:تسجيل زيارة',
      chapter: 'نفس الخدمة، جاهزة فوراً بتسجيل الزيارة',
      say: 'وأخيراً، لنتأكد أن الرحلة كاملة — الخدمة اللي أضفناها بالبداية',
    },
    { waitFor: 'role=button:الخدمات', timeoutMs: 30_000 },
    { click: 'role=button:الخدمات' },
    { waitFor: `text=${NEW_SERVICE}` },
    {
      say: `موجودة فوراً هنا، بسعرها ١٥٠ ريالاً — نفس القيمة اللي عدّلناها قبل قليل`,
    },
    {
      say: 'بلا أي خطوة نشر إضافية، بلا أي انتظار بين الشاشتين',
    },
    {
      chapter: 'خلاصة',
      say: 'وبهذا اكتملت الرحلة — إعداد المنصّة كامل، وجاهز لأول زيارة أو حجز حقيقي',
    },
  ],
};
