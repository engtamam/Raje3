/**
 * «عملائي المحتملين» (AffiliateLeads.tsx) — full coverage of the list screen AND the detail
 * screen's real mechanics, in one clip. Read AffiliateLeads.tsx (every comment in it — the module
 * docstring documents WHY each shape was chosen, not just what it renders), AffiliatePortal.tsx and
 * AffiliateNav.tsx in full before writing a single selector here — this project's own standing rule
 * (services-1-overview.mjs's own header sets the same discipline for the shop console).
 *
 * WHY THIS SCRIPT LOGS IN FOR REAL (`skipAutoSignIn: true`) — same reasoning as every other
 * affiliate tour in this family: `session.ts` keeps its own store (`raje3.affiliate.session`),
 * a separate key from the shop's own `raje3.session` that `useDemoSession` writes to, so the
 * honest way in is the same door a real marketer uses, on camera.
 *
 * A DEDICATED ACCOUNT, SEEDED — AND VERIFIED — TO STAY AT A REAL, HONEST ZERO LEADS. Checked
 * directly against the live cluster before writing a single step here: `affiliate_leads` does not
 * exist as a populated collection ANYWHERE on this platform, for any affiliate, on any deploy — a
 * `Lead` row is created in exactly one place, `core/lead_sourcing.py`'s search job, which calls the
 * REAL Google Places API with a manager's own BYOK key (`core/leads.py`'s own module docstring),
 * and no deploy here carries a real key or a platform-wide fallback (`affiliate-service-secrets`
 * and the deployment's own env both checked directly — neither holds one). seed-affiliate-leads.mjs
 * mints this account the same real way every account in this family is — apply() then the
 * platform-owner admin's approve(), never a database shortcut — and does not attempt to fabricate a
 * lead, the same discipline seed-affiliate-tools.mjs's own header states for every write it makes.
 *
 * SO THIS CLIP TEACHES THE DETAIL SCREEN BY READING IT ALOUD OVER THE REAL LIST, NEVER BY FAKING
 * A CLICK INTO SOMETHING THAT IS NOT THERE — the exact same discipline
 * affiliate-home-1-overview.mjs already set for this portal's own empty widgets: absent things are
 * spoken over, never clicked. Every sentence about LeadDetail below is read straight off
 * AffiliateLeads.tsx's own source (quick-action templates, one-tap outcome logging, the manual
 * status row, the decision-maker card, the merged timeline) — nothing here is invented, only
 * unverifiable on screen until a real Google key exists somewhere on this platform.
 *
 * TWO REAL EMPTY STATES, BOTH SHOWN LIVE, NOT JUST DESCRIBED. The screen's own JSX has two
 * different empty states depending on `query || onlyAttention`: "لا عملاء محتملون بعد" (a truly
 * fresh account) vs "لا نتائج" (a filter or search that matched nothing). Both are real, reachable
 * states on THIS account with zero leads — typing any search text, or toggling «تحتاج متابعة»,
 * flips from the first to the second even though the underlying list never changes size. That
 * distinction is worth showing live rather than asserting.
 */
const PHONE = '0502223334';
const PASSWORD = 'LeadsTour2026Demo!';

export default {
  id: 'affiliate-leads-1-overview',
  title: 'عملائي المحتملين — فهم الشاشة كاملة',
  // UNIFIED ACROSS EVERY affiliate-*.mjs SCRIPT — see affiliate-account-1-overview.mjs's own note.
  section: 'منصة المسوّقين',
  useDemoSession: false,
  skipAutoSignIn: true,
  sfx: true,
  secondsCap: 300,
  steps: [
    // ── تسجيل الدخول ────────────────────────────────────────────────────────────────────────
    {
      goto: '/affiliates',
      chapter: 'تسجيل الدخول',
      say: 'بوابة المسوّق — بنشوف «عملائي المحتملين» كاملة، القائمة وبطاقة العميل',
    },
    { waitFor: 'label=رقم الجوال', timeoutMs: 30_000 },
    {
      type: 'label=رقم الجوال',
      text: PHONE,
      say: 'رقم جوال المسوّق',
    },
    {
      type: 'label=كلمة المرور',
      text: PASSWORD,
      say: 'وكلمة مروره',
    },
    {
      click: 'role=button:تسجيل الدخول',
      say: 'ويدخل',
    },
    { waitFor: 'role=button:عملائي', timeoutMs: 45_000 },
    {
      click: 'role=button:عملائي',
      chapter: 'عملائي المحتملين',
      say: 'وهذي شاشة «عملائي المحتملين» — كل محل رشّحه بحث أو أحاله له مديره',
    },
    { waitFor: 'text=ابحث بالاسم أو المدينة' },
    // ── فكرة الشاشة: قائمة مسطّحة، لا كانبان ────────────────────────────────────────────────
    {
      say: 'قائمة واحدة مسطّحة، لا لوحة أعمدة — على الجوال هذا الشكل الوحيد اللي يشتغل بإبهام واحد',
    },
    {
      say: 'وفوقها بس شريط بحث وفلتر واحد — لا لوحة أرقام هنا، لأن كل رقم لازم يقود لفعل، وإلا يشوّش',
    },
    // ── من ينتظره أولاً: تعريف «تحتاج متابعة» ───────────────────────────────────────────────
    {
      chapter: '«تحتاج متابعة» — من يُرتَّب أولاً',
      say: 'أهم قرار بالشاشة: مين يظهر فوق؟ اللي «يحتاج متابعة» — بلا نشاط ثلاثة أيام كاملة',
    },
    {
      say: 'ونفس التعريف بالضبط يستخدمه السيرفر بحساب stale_leads — لا يُطلَب قائمة ثانية، فما يختلف رأي الشارة عن ترتيب القائمة',
    },
    {
      say: 'ويُستثنى من هذا الحساب كل عميل حالته «مسجَّل» أو «غير مهتم» — قصة انتهت لا تحتاج متابعة',
    },
    {
      say: 'وآخر نشاط: أحدث ملاحظة بسجل العميل، أو تاريخ اكتشافه لو ما له ملاحظة بعد',
    },
    // ── البحث الحي ───────────────────────────────────────────────────────────────────────────
    {
      chapter: 'البحث',
      click: 'css=input[placeholder="ابحث بالاسم أو المدينة"]',
      say: 'خانة البحث تبحث بحقلين بس — الاسم والمدينة',
    },
    {
      type: 'css=input[placeholder="ابحث بالاسم أو المدينة"]',
      text: 'صالون تجريبي غير موجود',
      say: 'أكتب اسماً ما له وجود عندي',
    },
    { waitFor: 'text=لا نتائج' },
    {
      say: 'وتطلع «لا نتائج» — جرّب كلمة ثانية أو ألغِ الفلتر، لأن حسابي هذا صفر عملاء حقيقيين حتى الآن',
    },
    {
      click: 'css=input[placeholder="ابحث بالاسم أو المدينة"]',
      type: 'css=input[placeholder="ابحث بالاسم أو المدينة"]',
      text: '',
      replace: true,
      say: 'وأمسح البحث',
    },
    { waitFor: 'text=لا عملاء محتملون بعد' },
    {
      say: 'ترجع الرسالة الأخرى: «لا عملاء محتملون بعد» — يظهرون هنا أول ما يُسنَد لك عميل محتمل',
    },
    // ── الفلتر المُروَّج الوحيد ──────────────────────────────────────────────────────────────
    {
      chapter: 'فلتر «تحتاج متابعة»',
      click: 'role=button:تحتاج متابعة',
      say: 'وفلتر مُروَّج واحد بس — «تحتاج متابعة» — بديل عن لوحة فلاتر كاملة',
    },
    { waitFor: 'text=لا نتائج' },
    {
      say: 'ولاحظ: نفس رسالة «لا نتائج» تطلع هنا كذلك، مو رسالة الحساب الفارغ — لأن فلتراً مفعَّلاً غيّر القصة حتى لو القائمة صفر بالحالتين',
    },
    {
      click: 'role=button:الكل',
      say: 'أرجع لـ«الكل»',
    },
    { waitFor: 'text=لا عملاء محتملون بعد' },
    // ── العنوان الديناميكي وقت وجود من يحتاج متابعة ─────────────────────────────────────────
    {
      say: 'ولو عندي عميل واحد أو أكثر يحتاج متابعة الآن، يطلع سطر تحذير أصفر فوق العنوان مباشرة يعدّهم بالضبط',
    },
    {
      say: 'وكل صف بالقائمة يحمل بادج «تحتاج متابعة» الصفراء بجنب بادج حالته العادية، لو انطبق عليه الشرط',
    },
    // ── الترتيب ──────────────────────────────────────────────────────────────────────────────
    {
      chapter: 'الترتيب',
      say: 'وترتيب القائمة نفسه: من يحتاج متابعة أولاً دائماً، وداخل كل مجموعة الأحدث اكتشافاً فوق',
    },
    // ── بطاقة العميل: ما تعرضه، بدون فتحها فعلياً — الحساب صفر عملاء حقيقيين ───────────────
    {
      chapter: 'لو ضغطت على عميل — بطاقته الكاملة',
      say: 'دعني أشرح لك بطاقة أي عميل لو فتحتها — حسابي هذا للأسف صفر عملاء حقيقيين، ولا قاعدة بيانات وهمية أحطها بدلاً عنه',
    },
    {
      say: 'أعلى البطاقة: اسمه، مدينته، وبادج حالته — وجنبهما رقمه: زر واتساب مباشر لو الرقم سعودي معروف، وزر اتصال عادي',
    },
    {
      say: 'رابط الواتساب يفتح المحادثة مباشرة برقمه، بلا نسخ ولا تبديل تطبيق — أسرع قناة توصل فيها لعميل محتمل',
    },
    // ── الإجراء السريع: القوالب وتسجيل النتيجة ──────────────────────────────────────────────
    {
      chapter: 'الإجراء السريع — أهم قسم بالبطاقة',
      say: 'تحتها مباشرة صندوق «الإجراء السريع» — قوالب رسائل مرحلته الحالية، أول خمسة بس، بلا داعٍ يفتح شاشة ثانية',
    },
    {
      say: 'كل قالب له زرّا نسخ وإرسال — النسخ ينسخ النص للحافظة بلا أي أثر آخر، والإرسال ينسخ الحافظة أولاً ثم يفتح واتساب بالنص جاهزاً بالمحادثة، ثم يسجّل الإرسال',
    },
    {
      say: 'النسخ أولاً والفتح ثانياً مقصود: لو واتساب ما انفتح على جواله لأي سبب، النص يبقى بحافظته يلصقه يدوياً — لا يضيع',
    },
    {
      say: 'وبمجرد ما يُرسَل قالب، تحته سؤال مباشر: «ما نتيجة آخر تواصل؟» — تقدّم، لا رد، أو رفض — ضغطة وحدة بلا نموذج',
    },
    {
      say: 'وهذا القسم كله يختفي تماماً لو كان العميل مغلقاً — مسجَّل أو غير مهتم — لأنه ما بقي شي يُرسَل',
    },
    // ── تحديث الحالة يدوياً ──────────────────────────────────────────────────────────────────
    {
      chapter: 'تحديث الحالة يدوياً',
      say: 'وتحت الإجراء السريع: تحديث الحالة يدوياً — بس أربع حالات يملك المسوّق تغييرها بنفسه: تم التواصل، مهتم، غير مهتم، ومتابعة لاحقة',
    },
    {
      say: 'أما «جديد» و«مُسنَد» و«مسجَّل» فما يقدر يكتبها بيده أبداً — السيرفر وحده يضبطها، لما يُسنَد العميل أو يسجّل فعلياً بالمنصّة',
    },
    // ── صاحب القرار ──────────────────────────────────────────────────────────────────────────
    {
      chapter: 'صاحب القرار',
      say: 'وبطاقة صغيرة: اسم صاحب القرار بالمحل، جواله، وصفته — مالك أو مدير — يحفظها بضغطة وحدة بس لو غيّر أي حقل منها',
    },
    // ── السجل الموحَّد ────────────────────────────────────────────────────────────────────────
    {
      chapter: 'السجل',
      say: 'وآخر قسم: السجل — كل رسالة أُرسلت ونتيجتها، وكل تغيير حالة مع سببه، مدموجين بخط زمني واحد، الأحدث فوق',
    },
    {
      say: 'سجل واحد لا اثنين يقارن بينهما المسوّق بنفسه — هذا بالضبط اللي كانت البحوث تشدد عليه: أقل من ثلاثين ثانية من «مين أتواصل معه» إلى «سُجِّل»',
    },
    // ── من أين يجي العميل أصلاً ──────────────────────────────────────────────────────────────
    {
      chapter: 'من أين يجي العميل أصلاً',
      say: 'وأخيراً: العميل نفسه ما يُكتَب هنا يدوياً أبداً — يجي إما من أداة بحث محلات حقيقية بشاشة «أدواتي»، أو إحالة مديره له',
    },
    {
      chapter: 'خلاصة الشاشة',
      say: 'بهذا خلصنا «عملائي المحتملين» كاملة — القائمة وترتيبها وفلترها، والبطاقة بكل أقسامها الخمسة',
    },
  ],
};
