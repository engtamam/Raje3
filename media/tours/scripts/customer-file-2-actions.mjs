/**
 * «عملائي» — PART 2 OF 2: the write actions on the «تعديل» tab, and the search screen's edge
 * cases. Read Customer.tsx and Customers.tsx in full before writing a single selector here —
 * this project's own standing rule.
 *
 * CAPTIONS ARE SHORT ON PURPOSE — see customer-file-1-overview.mjs's own header: overlay.mjs's
 * caption bar measured live fits roughly 40-45 Arabic characters across its two lines at this
 * frame's real width; every longer explanation here is split across several short caption-only
 * steps instead of one long sentence.
 *
 * DELIBERATELY NOT ON THE HERO CUSTOMER (0555010101). She is the one visit-1/2 and part 1 of
 * this tour re-record against, seeded with a specific points balance and 40 real visits — a real
 * `loyalty.adjust` call here is not reversible (same fact visit-2-services-save.mjs's own header
 * notes about `loyalty.redeem`), so spending her balance on every re-recording of THIS tour would
 * slowly break the others. This tour instead opens whichever customer sits first in the plain
 * recent list — one of seedOneCustomer()'s ~1000 random regulars — and acts on him instead. His
 * exact name/phone are never hardcoded (they're minted fresh per demo seed), so every step here
 * locates him structurally (first row, then whatever's on his own page) rather than by a name
 * that would break the moment the account is reseeded.
 *
 * THE ERASE STEP IS SHOWN BUT NEVER CONFIRMED. `operations.erase_customer` is real and
 * irreversible (Customer.tsx's own Hint: "لا يمكن التراجع") — recording a real erase would
 * permanently remove a seeded customer from the demo account for no narrative gain over showing
 * the two-step confirmation and backing out of it with «تراجع», which is itself the honest,
 * safety-first thing this screen was built to require.
 */
export default {
  id: 'customer-file-2-actions',
  title: 'عملائي 2 — تعديل بيانات العميل وحالات حافة',
  section: 'عملائي',
  useDemoSession: true,
  // See visit-1-search-perks.mjs's own note: without this, the opening `goto` records several
  // seconds of blank/white frame before the page actually finishes loading.
  preload: true,
  steps: [
    {
      goto: '/customers',
      chapter: 'حافة البحث',
      say: 'حالة حافة: نبحث برقم ما له وجود',
    },
    {
      type: 'css=input[placeholder="ابحث برقم الجوال أو الاسم"]', text: '0599999999',
      say: 'رقم مو مسجّل عندك أبداً',
    },
    {
      waitFor: 'text=لا نتائج',
    },
    {
      say: '«لا نتائج» — مو تسجيل خطأ',
    },
    {
      say: 'واقتراح مباشر: سجّل زيارة جديدة له',
    },
    {
      say: 'العميل يُنشأ بزيارته الأولى، لا بنموذج تسجيل',
    },
    {
      type: 'css=input[placeholder="ابحث برقم الجوال أو الاسم"]', text: '', replace: true,
      say: 'نمسح البحث ونرجع للقائمة',
    },
    {
      // AN EXPLICIT WAIT BEFORE THE CLICK — after clearing a search that just showed "لا نتائج",
      // the list re-renders from "no `<ul>` at all" back to the full recent list; the click
      // handler's own 5s stableBoundingBox() timeout wasn't always enough for that transition on
      // a real run (confirmed live: "resolved to nothing visible" right after this exact step).
      waitFor: 'css=ul > li:first-child button',
      timeoutMs: 15_000,
    },
    {
      click: 'css=ul > li:first-child button',
      chapter: 'تعديل بياناته',
      say: 'نفتح أول عميل — لنجرّب إجراءات كتابة حقيقية',
    },
    {
      click: 'role=radio:تعديل',
      say: 'تبويب «تعديل» — الوحيد اللي فيه كتابة',
    },
    {
      say: 'منفصل عمداً عن تبويبات القراءة فقط',
    },
    {
      type: 'label=اسم العميل',
      text: () => `عميل تجريبي ${Date.now() % 1000}`,
      replace: true,
      say: 'كثير من العملاء يُسجَّلون بلا اسم أول زيارة',
    },
    {
      click: 'role=button:حفظ!',
      say: 'حفظ — رقمه غير قابل للتعديل من هنا',
    },
    {
      waitFor: 'text=تم حفظ الاسم',
    },
    {
      say: 'تأكيد فوري: تم حفظ الاسم',
    },
    {
      chapter: 'تعديل الرصيد يدوياً',
      say: 'تحته تعديل رصيد نقاطه يدوياً',
    },
    {
      type: 'label=عدد النقاط', text: '20',
      say: 'موجب يمنح نقاطاً، وسالب يخصم — نفس الحقل',
    },
    {
      // THE BUTTON NEVER SHOWS "اختر السبب" — checked live in Customer.tsx: `adjustNote` starts
      // as `ADJUST_REASONS[0]`, not empty, so the reason button already carries the first fixed
      // reason's own text the instant the tab mounts. "اختر السبب" is only ever the placeholder
      // for the empty string (chosen via "أخرى…"), which nothing on this path sets. Selector
      // matches what the button actually shows on mount.
      click: `role=button:تعويض عن خطأ في تسجيل الزيارة`,
      say: 'السبب إلزامي، ومن قائمة جاهزة',
    },
    {
      waitFor: 'text=سبب التعديل',
      captionTop: true,
      say: 'لا نص حر افتراضياً — يصير كلمات لا تفسّر شيء',
    },
    {
      click: 'text=نقاط ترحيبية',
      say: 'نختار «نقاط ترحيبية»',
    },
    {
      say: 'زر الحفظ معطّل حتى يوجد رقم وسبب ≥3 أحرف',
    },
    {
      click: 'role=button:حفظ التعديل',
      say: 'حفظ التعديل — بمفتاح فريد لكل عملية',
    },
    {
      say: 'ضغط مكرّر بسبب شبكة بطيئة لا يضاعف النقاط',
    },
    {
      waitFor: 'text=وسُجّل السبب مع الحركة',
    },
    {
      say: 'تم — والسبب سُجّل مع الحركة',
    },
    {
      chapter: 'حذف بيانات العميل',
      say: 'آخر التبويب: حذف بياناته — حق العميل',
    },
    {
      click: 'role=button:حذف بياناته',
      say: 'الضغطة الأولى لا تحذف — تفتح تأكيداً',
    },
    {
      waitFor: 'text=بلا رجعة',
    },
    {
      say: 'التأكيد يسمّي العميل ويقول: بلا رجعة',
    },
    {
      say: 'حذف حقيقي ونهائي — ما نسجّله على حساب تجريبي',
    },
    {
      click: 'role=button:تراجع',
      say: 'نتراجع — والعميل يبقى كما هو',
    },
  ],
};
