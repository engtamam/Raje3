/**
 * «عملائي» — ONE complete journey: the list, the search, a customer's full page read top to
 * bottom, then the real write actions (rename, adjust points, erase) and the search screen's edge
 * cases. Was two separate clips (customer-file-1-overview: read-only tour; customer-file-2-actions:
 * write actions + edge cases) — merged into one continuous story per the same decision already made
 * for تسجيل الزيارة/خدماتي ومنتجاتي/رسائلي: one connected journey an owner actually lives through,
 * not two clips that reopen the same screen from scratch. Captions written to flow as one
 * narrative, each line picking up from the one before it, in a capability-marketing voice — what
 * the platform gives an owner, not a dry click-by-click walkthrough. Read Customers.tsx and
 * Customer.tsx in full before writing a single selector here — this project's own standing rule.
 *
 * A REAL PRODUCT QUIRK, STATED HONESTLY RATHER THAN SMOOTHED OVER: the "متأخر" badge on the list
 * and the overdue banner on the customer's own page are two DIFFERENT computations (list:
 * `reminders.list_schedule`, resolved by the engine; detail: `sinceDays > everyDays * 1.5`,
 * computed locally from his own visits) — a real product quirk, not a recording slip, so the
 * caption says so rather than pretending they're one thing.
 *
 * CAPTIONS ARE SHORT ON PURPOSE, NOT BY TASTE. overlay.mjs's caption bar fits roughly 40-45 Arabic
 * characters across its two lines at this frame's real width — every longer explanation is split
 * into several short caption-only steps instead of one long sentence.
 *
 * THE SEARCH BOX HAS NO aria-label AND NO TESTID — checked in Customers.tsx: only a `placeholder`.
 * `label=` (Playwright's getByLabel) never matches a placeholder, so this uses the `css=` escape
 * hatch on purpose — a documented last resort, not a shortcut.
 *
 * TWO DIFFERENT CUSTOMERS, ON PURPOSE. The read-only first half tours the HERO customer
 * (0555010101) — seed-demo-account.mjs gives her a real name, 40 real visits on «بروتين شعر» (so
 * «دورته عندك» has learned a real rhythm to show), a real points balance, and two real rewards.
 * Nothing in that half mutates her. The write-actions second half deliberately switches to
 * whichever customer sits first in the plain recent list — one of seedOneCustomer()'s ~1000
 * random regulars — because a real `loyalty.adjust` call is not reversible (same fact
 * visit-1-search-perks.mjs's own header notes about `loyalty.redeem`), and spending the hero's
 * balance on every re-recording of this tour would slowly break the other tours that depend on
 * her seeded state (visit-1, this one's own first half). His exact name/phone are never
 * hardcoded — every step locates him structurally (first row, then whatever's on his own page)
 * rather than by a name that would break the moment the account is reseeded.
 *
 * THE ERASE STEP IS SHOWN BUT NEVER CONFIRMED. `operations.erase_customer` is real and
 * irreversible (Customer.tsx's own hint: "لا يمكن التراجع") — recording a real erase would
 * permanently remove a seeded customer from the demo account for no narrative gain over showing
 * the two-step confirmation and backing out of it with «تراجع», which is itself the honest,
 * safety-first thing this screen was built to require.
 */
const HERO_PHONE = '0555010101';
const HERO_SERVICE = 'بروتين شعر';

export default {
  id: 'customer-file-1-overview',
  title: 'عملائي — من البحث إلى ملف العميل الكامل، تعديلاً وحذفاً',
  section: 'عملائي', // nav.ts's own label
  useDemoSession: true,
  // See visit-1-search-perks.mjs's own note: without this, the opening `goto` records several
  // seconds of blank/white frame before the page actually finishes loading.
  preload: true,
  steps: [
    {
      goto: '/customers',
      chapter: 'قائمة عملائي',
      say: 'هنا كل من زارك — قائمة واحدة تجمعهم كلهم',
    },
    {
      click: 'role=radio:من تأخّر',
      say: '«من تأخّر»: من فات موعد عودته المعتاد',
    },
    {
      say: 'من نفس محرّك التذكيرات، لا حساب منفصل',
    },
    {
      click: 'role=radio:عملائي',
      say: 'ونرجع للقائمة الكاملة',
    },
    {
      say: 'ووسام «متأخر» هنا هو نفسه ذاك التبويب',
    },
    {
      click: 'css=input[placeholder="ابحث برقم الجوال أو الاسم"]',
      chapter: 'البحث',
      say: 'وللبحث السريع، برقم الجوال أو الاسم',
    },
    {
      type: 'css=input[placeholder="ابحث برقم الجوال أو الاسم"]',
      text: HERO_PHONE,
      say: `نكتب رقمها ${HERO_PHONE}`,
    },
    {
      // WAITING ON THE PHONE, NOT THE NAME — the row always carries the phone (it's what was
      // typed and matched); the name is a separate field that a search index can lag behind on a
      // busy shared demo account, confirmed live when a name-based wait timed out with the row
      // itself already on screen.
      waitFor: `text=${HERO_PHONE}`,
      timeoutMs: 45_000,
    },
    {
      say: 'ولقيناها فوراً، حتى لو عندك آلاف العملاء',
    },
    {
      click: `text=${HERO_PHONE}`,
      chapter: 'ملف العميل',
      say: 'نفتح ملفها كاملاً',
    },
    {
      say: 'فوق: اسمها ورقمها، وثلاث بطاقات',
    },
    {
      say: 'زياراتها، آخر زيارة، وكل كم يوم تعود عادة',
    },
    {
      say: 'وأربعة تبويبات: نظرة عامة، نقاطه، رسائله، وتعديل',
    },
    {
      say: '«عروضه»: ما وصلها، الساري والمنتهي معاً',
    },
    {
      say: 'ولا نُخفي المنتهي — سؤال يتكرر عنه كثيراً',
    },
    {
      say: '«زياراته»: كل زيارة، بخدماتها وتاريخها الحقيقي',
    },
    {
      // «دورته عندك» ONLY RENDERS ONCE `reminders.list_rules` HAS LEARNED AT LEAST ONE RULE FOR
      // this customer — a background computation, not guaranteed to have run yet at recording
      // time even for a 40-visit seeded hero (confirmed live: a 30s wait for
      // `label=دورة ${HERO_SERVICE}` timed out on a real run). Narrated without a hard `waitFor`
      // gate on it so this tour never depends on timing it can't control.
      say: 'ولو تعلّم النظام إيقاع زيارتها، يظهر تحت «دورته عندك»',
    },
    {
      say: 'وهو رقم قابل للتعديل بيدك — لو تعرفه أفضل من النظام',
    },
    {
      click: 'role=radio:نقاطه',
      chapter: 'نقاطه ورسائله',
      say: 'وتبويب نقاطه: رصيدها ومكافآتها كاملة',
    },
    {
      say: 'وتحتها «حركة النقاط» — من أين جاءت ومتى صُرفت',
    },
    {
      click: 'role=radio:رسائله',
      say: 'ورسائله: كل رسالة خرجت أو لم تخرج',
    },
    {
      say: 'مع سببها لو امتنعت — لا شيء يُمنع بصمت',
    },
    {
      click: 'role=button:رجوع',
      say: 'وبعد ما أخذنا جولة كاملة على ملف عميل، نرجع للقائمة',
    },
    // ── الآن نتحول لعميل آخر لإجراءات الكتابة الحقيقية ──────────────────────────────────────────
    {
      say: 'وهذا كله ما شفناه لحد الآن — بس شوف وش تقدر تسوي أكثر',
    },
    {
      say: 'تعال نعدّل بيانات عميل بأيدينا الآن',
    },
    {
      // Position-targeted (css) on purpose: the first row is whichever real regular sits there
      // on this reseed, never the hero above — same reasoning the header comment explains: her
      // seeded balance stays intact for every other tour that depends on it.
      waitFor: 'css=ul > li:first-child button',
      timeoutMs: 15_000,
    },
    {
      click: 'css=ul > li:first-child button',
      chapter: 'تعديل بياناته',
      say: 'نفتح ملف أحد عملائك، ونشوف وش تقدر تعدّل فيه',
    },
    {
      click: 'role=radio:تعديل',
      say: 'من تبويب «تعديل» تتحكم بكل شي يخص هذا العميل',
    },
    {
      type: 'label=اسم العميل',
      text: () => `عميل تجريبي ${Date.now() % 1000}`,
      replace: true,
      say: 'كثير من عملائك يُسجَّلون بلا اسم من أول زيارة',
    },
    {
      click: 'role=button:حفظ!',
      say: 'نحفظ — ورقم جواله وحده غير قابل للتعديل من هنا',
    },
    {
      waitFor: 'text=تم حفظ الاسم',
    },
    {
      say: 'تأكيد فوري: تم حفظ الاسم',
    },
    {
      chapter: 'تعديل الرصيد يدوياً',
      say: 'وتحته، تعديل رصيد نقاطه يدوياً بنفس السهولة',
    },
    {
      type: 'label=عدد النقاط', text: '20',
      say: 'رقم موجب يمنح نقاطاً، وسالب يخصم — نفس الحقل بالضبط',
    },
    {
      // THE BUTTON NEVER SHOWS "اختر السبب" — checked live in Customer.tsx: `adjustNote` starts
      // as `ADJUST_REASONS[0]`, not empty, so the reason button already carries the first fixed
      // reason's own text the instant the tab mounts. "اختر السبب" is only ever the placeholder
      // for the empty string (chosen via "أخرى…"), which nothing on this path sets. Selector
      // matches what the button actually shows on mount.
      click: `role=button:تعويض عن خطأ في تسجيل الزيارة`,
      say: 'والسبب إلزامي دائماً، ومن قائمة جاهزة مسبقاً',
    },
    {
      waitFor: 'text=سبب التعديل',
      captionTop: true,
      say: 'لا نص حر افتراضياً — كي لا يصير كلمات لا تفسّر شيئاً',
    },
    {
      click: 'text=نقاط ترحيبية',
      say: 'نختار «نقاط ترحيبية»',
    },
    {
      say: 'وزر الحفظ معطّل حتى يوجد رقم وسبب لا يقل عن ٣ أحرف',
    },
    {
      click: 'role=button:حفظ التعديل',
      say: 'نحفظ',
    },
    {
      say: 'وحتى لو ضغطت الزر مرتين بالغلط',
    },
    {
      say: 'ما تتضاعف النقاط أبداً',
    },
    {
      waitFor: 'text=وسُجّل السبب مع الحركة',
    },
    {
      say: 'تم — والسبب سُجّل مع الحركة',
    },
    {
      chapter: 'حذف بيانات العميل',
      say: 'وآخر ما بهذا التبويب: حذف بياناته — حق أصيل للعميل',
    },
    {
      click: 'role=button:حذف بياناته',
      say: 'والضغطة الأولى لا تحذف شيئاً — تفتح تأكيداً فقط',
    },
    {
      waitFor: 'text=بلا رجعة',
    },
    {
      say: 'والتأكيد يسمّي العميل بوضوح، ويقول: بلا رجعة',
    },
    {
      say: 'حماية حقيقية — القرار يبقى بيدك دايماً، ما ينفّذ نفسه',
    },
    {
      click: 'role=button:تراجع',
      chapter: 'خلاصة',
      say: 'نتراجع، والعميل يبقى كما هو — والرحلة اكتملت',
    },
    {
      say: 'من قراءة أول زيارة، إلى تعديل وحماية بياناته بثقة كاملة',
    },
  ],
};
