/**
 * «خدماتي ومنتجاتي» — PART 2 OF 2: practical, real-money use — a real service added with a real
 * price and duration, edited, retired and brought back, its actual link to «تسجيل زيارة», and the
 * REAL edge cases the form actually produces on screen (not invented ones). Read
 * apps/console/src/screens/Services.tsx and money.ts's `halalas()` before writing a selector here —
 * this project's own standing rule.
 *
 * THE TWO ERROR MESSAGES SHOWN HERE ARE BOTH REAL, VERIFIED LIVE, NOT ASSUMED.
 *   · An out-of-range duration (>720, the input's own `max`) is caught by the browser's NATIVE
 *     number-input validation before the form's `onSubmit` ever runs — Chromium's own bubble, not
 *     an app sentence. `type="number" min={0} max={720}` on `duration_minutes` is the only
 *     validation this field has; the app writes no message of its own for it.
 *   · An invalid price ("12.345", three decimals — `money.ts`'s own `halalas()` refuses a third
 *     decimal place by regex) DID fail silently until this very tour's own investigation caught it:
 *     `halalas()` returning null fell into the exact same branch as an empty box, so a garbage
 *     price was dropped with no write and no word said. Fixed in Services.tsx (see this branch's
 *     own commit) to `setError('السعر غير صحيح — رقم بخانتين عشريتين على الأكثر.')` instead — the
 *     sentence this clip shows is the fix, exercised for real, not a mockup of one.
 *
 * ZERO PRICE IS NOT AN ERROR — it is a real, valid instruction (`halalas('0') === 0`, sent as a
 * real `price_minor: 0`) and the form accepts it silently. What this clip shows instead is the
 * honest CONSEQUENCE: `svc.price_minor ? riyals(...) : '—'` treats a real zero exactly like "no
 * price entered" on screen — the two are visually indistinguishable in the table, by design
 * (falsy check), and that is worth knowing rather than assuming a zero price is announced somehow.
 *
 * THE LINK TO A REAL VISIT — ServiceGrid.tsx (rendered from Visit.tsx) reads the very same
 * `operations.list_services` this screen writes to, so a service added here is immediately
 * choosable at «تسجيل زيارة» with no separate publish step; confirmed by actually opening that
 * screen at the end of this clip and finding the service this clip just created.
 */
const NEW_SERVICE = 'تصفيف مناسبات';
const DURATIONLESS_ITEM = 'شامبو علاجي 250مل';
const ZERO_PRICE_ITEM = 'غسيل أيدٍ سريع';

export default {
  id: 'services-2-manage-examples',
  title: 'خدماتي ومنتجاتي ٢ — أمثلة عملية وحالات حافة',
  section: 'خدماتي ومنتجاتي',
  useDemoSession: true,
  orientation: 'landscape',
  preload: true,
  secondsCap: 300,
  steps: [
    // ── إضافة خدمة حقيقية بسعر ومدة حقيقيين ─────────────────────────────────────────────────
    {
      goto: '/services',
      chapter: 'إضافة خدمة بسعر ومدة حقيقيين',
      say: 'مثال عملي كامل — أضيف خدمة جديدة فعلاً بسعر ومدة حقيقيين، ونشوف نتيجتها في الجدول',
    },
    { waitFor: 'role=button:إضافة خدمة أو منتج', timeoutMs: 30_000 },
    { click: 'role=button:إضافة خدمة أو منتج' },
    { type: 'label=الاسم', text: NEW_SERVICE, say: `اسمها «${NEW_SERVICE}»` },
    {
      type: 'css=input[name="duration_minutes"]', text: '50', replace: true,
      say: 'مدتها ٥٠ دقيقة — رقم حقيقي تستخدمه الحجوزات فعلياً لحساب فتحة الوقت',
    },
    {
      type: 'css=input[name="price"]', text: '120', replace: true,
      say: 'وسعرها ١٢٠ ريالاً',
    },
    {
      // NO CHAPTER MARKER HERE — this and the next marker landed 6.4s apart on a real take,
      // under YouTube's own 10s minimum spacing (same issue caught in services-1-overview.mjs;
      // YouTube drops the WHOLE chapter list rather than just the close pair).
      click: 'role=button:إضافة',
      say: 'أضغط «إضافة»، وتظهر مباشرة في الجدول بمدتها وسعرها الحقيقيين',
    },
    { waitFor: `css=tr:has-text("${NEW_SERVICE}")` },
    // ── التعديل ──────────────────────────────────────────────────────────────────────────────
    {
      click: `css=tr:has-text("${NEW_SERVICE}") button[title="تعديل"] >> nth=0`,
      chapter: 'تعديل السعر والمدة',
      say: 'الأسعار تتغيّر — أفتح تعديل نفس الخدمة',
    },
    {
      type: `label=سعر ${NEW_SERVICE}`, text: '150', replace: true,
      say: 'أعدّل السعر مباشرة في الجدول إلى ١٥٠ ريالاً، بلا فتح نموذج منفصل',
    },
    {
      // GLOBAL, NOT TR-SCOPED — only one row is ever in edit state at a time (Services.tsx's
      // `open` holds one id), and the tr-scoped chain proved fragile live in services-1-overview.
      click: 'css=button[title="إنهاء التعديل"]',
      say: 'يُحفظ فور الخروج من الخانة',
    },
    // ── الإيقاف والتفعيل ─────────────────────────────────────────────────────────────────────
    {
      click: `css=tr:has-text("${NEW_SERVICE}") button[title^="إيقاف"] >> nth=0`,
      chapter: 'إيقاف الخدمة، لا حذفها',
      say: 'أوقفها — تختفي فوراً من شاشة تسجيل الزيارة، وتسكت تذكيراتها، لكنها لا تُحذف',
    },
    {
      click: 'role=radio:الموقوفة',
      say: 'تنتقل لتبويب «الموقوفة» — لا يوجد زر حذف على أي خدمة في هذه الشاشة إطلاقاً',
    },
    {
      click: `css=tr:has-text("${NEW_SERVICE}") button[title="تفعيل"] >> nth=0`,
      say: 'وزر «تفعيل» يرجعها فوراً كما كانت، بنفس سعرها ومدتها',
    },
    {
      // NO CLICK BACK TO «المفعّلة» HERE — verified live: this service was the only stopped one
      // on the demo account at the time, so reactivating it emptied «الموقوفة» entirely and
      // Services.tsx's own view auto-corrects to 'active' the instant that count hits zero — the
      // tab switcher itself disappears (it only renders while `stoppedCount > 0`), so there is no
      // «المفعّلة» control left to click. The screen already shows the active list on its own.
      say: 'ولمّا صارت هذي آخر خدمة موقوفة، اختفى تبويب «الموقوفة» تلقائياً',
    },
    {
      say: 'ورجعت الشاشة للقائمة المفعّلة وحدها',
    },
    // ── حالة حافة ١: مدة غير صالحة ───────────────────────────────────────────────────────────
    {
      click: 'role=button:إضافة خدمة أو منتج',
      chapter: 'حالة حافة — مدة غير صالحة',
      say: 'ماذا لو كتبت مدة أكبر من الحد المسموح؟ حقل المدة محدود بـ٧٢٠ دقيقة — أي ١٢ ساعة',
    },
    { type: 'label=الاسم', text: 'محاولة مدة خاطئة' },
    {
      type: 'css=input[name="duration_minutes"]', text: '900', replace: true,
      say: 'أكتب ٩٠٠ دقيقة — أكبر من الحد',
    },
    {
      click: 'role=button:إضافة',
      say: 'أضغط «إضافة»، والمتصفح نفسه يرفض الإرسال ويعرض تنبيهه الأصلي',
    },
    {
      say: 'لا رسالة من التطبيق هنا، بل قيد الحقل نفسه',
    },
    { click: 'role=button:إلغاء' },
    // ── حالة حافة ٢: سعر غير صالح ─────────────────────────────────────────────────────────────
    {
      click: 'role=button:إضافة خدمة أو منتج',
      chapter: 'حالة حافة — سعر غير صالح',
      say: 'وماذا لو كتبت سعراً بثلاث خانات عشرية؟ السعر نص، لا رقم، وله قاعدة صارمة: خانتان عشريتان فقط',
    },
    { type: 'label=الاسم', text: 'محاولة سعر خاطئ' },
    {
      type: 'css=input[name="price"]', text: '12.345', replace: true,
      say: 'أكتب ١٢.٣٤٥ — ثلاث خانات عشرية',
    },
    {
      click: 'role=button:إضافة',
      say: 'أضغط «إضافة»، وتظهر رسالة خطأ فعلية أعلى الشاشة',
    },
    {
      say: '«السعر غير صحيح — رقم بخانتين عشريتين على الأكثر»',
    },
    { click: 'role=button:إلغاء' },
    // ── حالة حافة ٣: سعر صفري ────────────────────────────────────────────────────────────────
    {
      click: 'role=button:إضافة خدمة أو منتج',
      chapter: 'حالة حافة — سعر صفري',
      say: 'وسعر صفري؟ هذا مختلف تماماً — صفرٌ رقمٌ صحيح، وليس خطأً',
    },
    { type: 'label=الاسم', text: ZERO_PRICE_ITEM },
    {
      type: 'css=input[name="price"]', text: '0', replace: true,
      say: 'أكتب صفراً بالضبط، لا أتركه فارغاً',
    },
    { click: 'role=button:إضافة' },
    { waitFor: `css=tr:has-text("${ZERO_PRICE_ITEM}")` },
    {
      say: 'يُحفظ فعلاً بسعر صفر — لكن الجدول يعرضه بنفس شكل «بلا سعر»؛ لا فرق بصرياً بين الاثنين هنا',
    },
    // ── حالة حافة ٤: منتج بلا مدة ─────────────────────────────────────────────────────────────
    {
      click: 'role=button:إضافة خدمة أو منتج',
      chapter: 'منتج بلا مدة',
      say: 'وهذا مثال منتج لا يُنجَز بمدة — كيس شامبو، ما فيه وقت خدمة',
    },
    { type: 'label=الاسم', text: DURATIONLESS_ITEM },
    {
      type: 'css=input[name="duration_minutes"]', text: '0', replace: true,
      say: 'أصفّر خانة المدة',
    },
    {
      type: 'css=input[name="price"]', text: '55', replace: true,
      say: 'وسعره الحقيقي ٥٥ ريالاً',
    },
    { click: 'role=button:إضافة' },
    { waitFor: `css=tr:has-text("${DURATIONLESS_ITEM}")` },
    {
      say: 'وفي عمود المدة، يظهر «غير مضبوطة» بلون تحذيري',
    },
    {
      say: 'هذا المنتج، بلا مدة، لا يمكن حجزه من شاشة الحجوزات',
    },
    // ── الربط بتسجيل الزيارة ─────────────────────────────────────────────────────────────────
    {
      click: 'role=link:تسجيل زيارة',
      chapter: 'نفس الخدمة، في تسجيل الزيارة',
      say: 'وأخيراً — الخدمة اللي أضفناها الآن، بسعرها ومدتها، موجودة فوراً في شاشة تسجيل الزيارة',
    },
    { waitFor: 'role=button:الخدمات', timeoutMs: 30_000 },
    { click: 'role=button:الخدمات' },
    { waitFor: `text=${NEW_SERVICE}` },
    {
      say: `«${NEW_SERVICE}» بسعرها ١٥٠ ريالاً — نفس القيمة اللي عدّلناها قبل قليل، بلا أي خطوة نشر إضافية`,
    },
  ],
};
