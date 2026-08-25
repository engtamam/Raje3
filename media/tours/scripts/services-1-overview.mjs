/**
 * «خدماتي ومنتجاتي» — PART 1 OF 2: a full, teaching-depth walk of the screen itself. Read
 * apps/console/src/screens/Services.tsx (1500+ lines) and apps/console/src/ServiceGrid.tsx before
 * writing a single selector here — this project's own standing rule.
 *
 * THERE IS NO SEPARATE "PRODUCT" TYPE. Checked in Services.tsx: `Service` carries `name`,
 * `cycle_days`, `price_minor`, `duration_minutes`, `catchall`, `active`, `eligible_staff_ids` — one
 * shape for everything sold, whether it is a haircut (a service you perform) or a jar of cream (a
 * product you hand over). The add button itself says «إضافة خدمة أو منتج», not two buttons, and the
 * add form asks nothing that only makes sense for one kind and not the other. This clip narrates
 * that honestly rather than inventing a distinction the code does not have.
 *
 * TWO STORES BEHIND ONE ROW — the screen's own top comment, and worth repeating on camera: name,
 * price and duration live in operations (the Service row itself); cycle, follow-up and points live
 * in three OTHER services (reminders' settings tree, reminders again, and loyalty) reached through
 * the same row. `settingFor()`/`earnFor()` each resolve THREE levels — service, then its group,
 * then the shop's general default — which is exactly what the pale-vs-dark number in every cell
 * means, and what chapter 4 below stops to explain rather than gloss over.
 *
 * LANDSCAPE ON PURPOSE. At 1920×1080 every `md:table-cell` column renders directly — duration,
 * price, cycle, follow-up, points and group all visible in one row at once — which is the one shape
 * that lets a viewer actually see "six columns, one service" instead of a phone's collapsed three
 * plus a hidden edit drawer. `goto: '/services'` as the very first step is a full reload, which is
 * fine here: this clip's opening beat IS the screen arriving, not a mid-app navigation to hide.
 *
 * THE DEMO SHOP'S REAL CATALOGUE — seed-demo-account.mjs's `ensureServices`, grouped under
 * «الشعر»/«الأظافر»/«العناية بالبشرة»/«المكياج» with real riyal prices and real durations, plus
 * whatever stop-service.mjs's own recordings left behind (a «قص شعر» service, retired and
 * reactivated at least once). Nothing here is invented data — every number named in a caption is
 * read straight off what is actually on screen when this runs.
 */
export default {
  id: 'services-1-overview',
  title: 'خدماتي ومنتجاتي ١ — فهم الشاشة كاملة',
  section: 'خدماتي ومنتجاتي',
  useDemoSession: true,
  orientation: 'landscape',
  preload: true,
  secondsCap: 300,
  steps: [
    // ── الوصول والجدول ──────────────────────────────────────────────────────────────────────
    {
      goto: '/services',
      chapter: 'خدماتي ومنتجاتي',
      say: 'هذي شاشة كل ما تبيعه — خدمة تسويها بنفسك أو منتج تسلّمه، بلا فرق بينهما هنا',
    },
    { waitFor: 'role=button:إضافة خدمة أو منتج', timeoutMs: 30_000 },
    {
      say: 'صفٌّ لكل خدمة، وستة أعمدة تقارن بينها كلها دفعة وحدة',
    },
    {
      // NO SEPARATE CHAPTER MARKER HERE — this lands ~9s after the opening chapter, under
      // YouTube's own 10s minimum spacing between chapters (verified live: a first take produced
      // exactly this warning and YouTube drops the WHOLE list rather than just the close pair).
      click: 'role=button:شرح الأعمدة',
      say: 'زر «شرح الأعمدة» يفتح جملة لكل عمود — تُقرأ مرة وتكفي',
    },
    {
      say: 'الدورة والاطمئنان والنقاط، كل واحد بجملته الخاصة تحت الجدول',
    },
    { click: 'role=button:إخفاء الشرح' },
    // ── المدة والسعر ─────────────────────────────────────────────────────────────────────────
    {
      say: 'المدة بالدقائق — الحجوزات تحتاجها فعلياً لحساب فتحات الوقت؛ بلا مدة لا يمكن حجز الخدمة',
    },
    {
      say: 'والسعر بالريال، واختياري تماماً — خانة فاضية لا تعني صفراً، تعني أنك لا تسعّر من هنا',
    },
    // ── الإعداد العام والوراثة ───────────────────────────────────────────────────────────────
    {
      click: 'css=details > summary:has-text("الإعداد العام")',
      chapter: 'الإعداد العام والوراثة',
      say: 'الإعداد العام رقمان يسريان على كل خدمة لم تُخصَّص بنفسها',
    },
    {
      say: 'دورة التذكير العامة، والاطمئنان العام — غيّرهما هنا يغيّر كل خدمة تابعة، وما خصّصته يبقى كما هو',
    },
    { click: 'css=details > summary:has-text("الإعداد العام")' },
    {
      say: 'وفي الجدول، الرقم الباهت يعني أن الخدمة تتبع الإعداد العام — والغامق يعني أنها مخصَّصة بنفسها',
    },
    // ── تعديل صف واحد، ورؤية الوراثة تتجمّد ─────────────────────────────────────────────────
    {
      click: 'css=tr:has-text("قص شعر") button[title="تعديل"] >> nth=0',
      chapter: 'تعديل صف واحد',
      say: 'اضغط قلم التعديل على أي خدمة — تفتح كل أعمدتها للتحرير المباشر داخل الصف',
    },
    {
      type: 'label=دورة قص شعر',
      text: '45',
      replace: true,
      say: 'اكتب رقماً جديداً لدورة هذه الخدمة وحدها — الآن صارت مخصَّصة، لا تتبع العام',
    },
    {
      // GLOBAL, NOT TR-SCOPED — `open` (Services.tsx's own state) holds at most one service id at
      // a time, so exactly one row on the whole page ever carries this exact title. Scoping by
      // the row's own text was needless here and, worse, the `tr:has-text(...)` chain resolved to
      // a stale/invisible match once the row's own layout shifted after typing — verified live.
      click: 'css=button[title="إنهاء التعديل"]',
      say: 'واضغط ✓ لإنهاء التعديل — كل تغيير يُحفظ فور الخروج من الخانة، بلا زر حفظ منفصل',
    },
    {
      click: 'css=button[title="العودة إلى الإعداد العام"]',
      say: 'وزر العودة ↺ يظهر فقط على الخانات المخصَّصة — اضغطه فترجع الخدمة لتتبع الإعداد العام من جديد',
    },
    // ── الإضافة: النموذج الكامل ──────────────────────────────────────────────────────────────
    {
      click: 'role=button:إضافة خدمة أو منتج',
      chapter: 'إضافة خدمة أو منتج جديدة',
      say: 'زر واحد للاثنين — الاسم وحده كافٍ، وكل حقل تحته اختياري وله معنى واضح',
    },
    {
      click: 'label=الاسم',
      say: 'الاسم — الحقل الوحيد المطلوب فعلياً',
    },
    {
      click: 'css=input[name="cycle_days"]',
      say: 'دورة التذكير: كل كم يوماً يحتاج العميل هذه الخدمة؟ اتركها صفراً إن كانت لمرة واحدة فقط',
    },
    {
      click: 'css=input[name="duration_minutes"]',
      say: 'المدة بالدقائق — مقترحة ١٥ دقيقة افتراضياً، وحدّها الأقصى ٧٢٠ دقيقة أي ١٢ ساعة',
    },
    {
      click: 'css=input[name="price"]',
      say: 'السعر بالريال، نص وليس رقماً — يقبل الفاصلة العشرية بخانتين فقط',
    },
    {
      click: 'css=input[name="follow_up_days"]',
      say: 'الاطمئنان: رسالة قصيرة بعد الزيارة تسأل إن كان كل شيء تمام، وتُلغى تلقائياً إن عاد قبل موعدها',
    },
    {
      click: 'css=input[name="points"]',
      say: 'نقاطها من ولائك — فاضية تعني أنها تتبع نقاط الإعداد العام تلقائياً',
    },
    {
      say: 'والمجموعة اختيارية — تجمع خدمات متشابهة تحت إعداد دورة واحد، تغيّره مرة يكفي عن الكل',
    },
    { click: 'role=button:إلغاء' },
    // ── من يقدر يسوّيها ──────────────────────────────────────────────────────────────────────
    {
      say: 'ولو عندك أكثر من موظف نشط، كل خدمة تفتح صفَّ «من يقدر يسوّيها» عند التعديل',
    },
    {
      say: 'قائمة الموظفين المؤهَّلين لأداء هذه الخدمة بالذات',
    },
    // ── الإيقاف بدل الحذف ────────────────────────────────────────────────────────────────────
    {
      say: 'لاحظ: لا يوجد زر حذف على أي خدمة — كل زيارة سُجِّلت تشير إلى خدمتها، وحذفها يكسر ذلك السجل',
    },
    {
      say: 'البديل هو زر الإيقاف — يوقف الخدمة عن الظهور في تسجيل الزيارة ويسكت تذكيراتها',
    },
    {
      say: 'وتاريخها يبقى كاملاً، بلا أي فقدان',
    },
    {
      chapter: 'خلاصة الشاشة',
      say: 'بهذا خلصنا فهم شاشة «خدماتي ومنتجاتي» كاملة — الأعمدة، الوراثة، الإضافة، والإيقاف بدل الحذف',
    },
  ],
};
