/**
 * «أدواتي» (AffiliateTools.tsx) — full coverage of the menu and all five sub-screens in ONE clip:
 * مكتبة الرسائل, مكتبة الأدلة, أداة البحث عن عملاء محتملين, إحصائيات القطاعات, تذاكر المحلات. Read
 * AffiliateTools.tsx, TicketCarousel.tsx, AffiliatePortal.tsx and AffiliateNav.tsx in full before
 * writing a single selector here — this project's own standing rule. That file's own header
 * comment is the one fact this whole tour is built to teach: a HUB, not one flat screen — template
 * curation and the lead-search tool have incompatible refresh cadences and mental models, so this
 * is a landing menu into five focused sub-screens, each owning its own back button.
 *
 * WHY THIS SCRIPT LOGS IN FOR REAL (`skipAutoSignIn: true`), same reasoning as
 * affiliate-earnings-1-overview.mjs's own header: record-tour.mjs's demo-session machinery only
 * ever writes into `raje3.session`, the SHOP's own key — the affiliate portal keeps its own store
 * (`session.ts`: `raje3.affiliate.session`), so the honest way in is the same door a real marketer
 * uses, on camera.
 *
 * A FOURTH DEDICATED ACCOUNT, NOT A REUSE OF ANY EARLIER ONE. affiliate-earnings-1-overview.mjs's
 * own account (0549900110) is deliberately kept at zero forever — its whole point is the honest
 * empty state. seed-affiliate-team.mjs's manager (0555020202) exists for «فريقي» specifically.
 * «أدواتي» needs the opposite of an empty account: real templates, real citations, a saved Places
 * key and a real referred shop — nothing here teaches anything on a blank screen. So
 * seed-affiliate-tools.mjs mints its OWN manager (0501234567), applied and approved the same real
 * way every account in this family is, never a database shortcut.
 *
 * WHAT IS A REAL, PERSISTENT WRITE IN THIS RECORDING, AND WHY EACH ONE IS LEFT AS-IS AFTERWARDS:
 *   - Message templates/citations are a SHARED library across every manager on this tenant (seed
 *     script found 12 templates and 31 citations already there before adding its own two of each)
 *     — every add/edit form in this tour is filled and then exited via «رجوع» WITHOUT saving, and
 *     every deactivate button is either never pressed (citations — no confirm step at all in the
 *     code) or pressed only as far as its own confirm ROW, never the "تأكيد التعطيل" button itself
 *     (templates) — nothing shared is ever actually removed from the library by this clip.
 *   - The Places API key is re-saved with the exact same demo value it already held — an idempotent
 *     write, not a real credential change.
 *   - A real lead-search job IS submitted with the demo key (never a genuine Google key — see
 *     seed-affiliate-tools.mjs's own note on why that key never validates at save time). It will
 *     fail against Google's real API sometime after this recording ends; that failure is the
 *     honest fate of a demo key and needs no cleanup — JobRow already renders a `failed` badge.
 *   - A real ticket OPEN is attempted on the referred demo shop and genuinely refused
 *     (`write_not_granted` — confirmed live, this shop's own consent grant never carried write;
 *     see this file's own note further down). The refusal itself is what this clip shows, not a
 *     faked success — no ticket, no reply, nothing to revert.
 */
const PHONE = '0501234567';
const PASSWORD = 'ToolsTour2026Demo!';
const PLACES_DEMO_KEY = 'AIzaSyDEMO0000000000000000000000000';

export default {
  id: 'affiliate-tools-1-overview',
  title: 'أدواتي — كل الأدوات الخمس كاملة',
  // UNIFIED ACROSS EVERY affiliate-*.mjs SCRIPT — see affiliate-account-1-overview.mjs's own note.
  section: 'منصة المسوّقين',
  skipAutoSignIn: true,
  secondsCap: 480,
  steps: [
    // ── تسجيل الدخول ────────────────────────────────────────────────────────────────────────
    {
      goto: '/affiliates',
      chapter: 'تسجيل الدخول',
      say: 'بوابة المسوّقين — بنشوف «أدواتي» كاملة',
    },
    {
      type: 'label=رقم الجوال',
      text: PHONE,
      say: 'رقم جوالك',
    },
    {
      type: 'label=كلمة المرور',
      text: PASSWORD,
      say: 'وكلمة مرورك',
    },
    {
      click: 'role=button:تسجيل الدخول',
      say: 'وتسجّل دخولك',
    },
    { waitFor: 'role=button:أدواتي', timeoutMs: 45_000 },
    {
      click: 'role=button:أدواتي',
      chapter: 'أدواتي — القائمة',
      say: 'وندخل «أدواتي» — مو شاشة وحدة',
    },
    { waitFor: 'text=مكتبة الرسائل' },
    {
      say: 'قائمة تفتح خمس شاشات، كل وحدة بزر رجوع خاص فيها',
    },
    {
      say: 'المسوّق العادي يشوف بطاقتين بس',
    },
    {
      say: 'ومدير التسويق — زي حسابي الآن — يشوف الخمس كاملة',
    },
    {
      say: 'مكتبة القوالب تتصفّح كل يوم',
    },
    {
      say: 'وأداة البحث عمل خلفي نادر — طبيعتان مختلفتان',
    },

    // ── مكتبة الرسائل ───────────────────────────────────────────────────────────────────────
    {
      click: 'role=button:مكتبة الرسائل',
      chapter: 'مكتبة الرسائل',
      say: 'أول أداة: مكتبة قوالب واتساب',
    },
    { waitFor: 'role=button:قالب جديد لهذه المرحلة' },
    {
      say: 'لكل مرحلة من رحلة العميل مرحلتها الخاصة',
    },
    {
      say: 'الشرائح فوق: كل وحدة مرحلة من رحلة العميل',
    },
    {
      click: 'role=button:الخطاف',
      say: 'اضغط أي مرحلة تشوف قوالبها هي بس',
    },
    {
      click: 'role=button:تجاوز حارس البوابة',
      say: 'ورجعنا لأول مرحلة',
    },
    {
      say: 'كل قالب يطلع كفقاعة واتساب حقيقية',
    },
    {
      say: 'نفس شكل الرسالة اللي بترسلها بالضبط',
    },
    {
      say: 'ولو قالب استُخدم قبل، يطلع جنبه شارة',
    },
    {
      say: 'نسبة تقدّم العميل بعده، وعدد مرّات استخدامه',
    },
    {
      click: 'role=button:نسخ نص القالب',
      say: 'زر النسخ ينسخ نص القالب كامل بضغطة',
    },
    {
      click: 'role=button:تعديل',
      say: 'وبما إني مدير، أقدر أعدّل أي قالب',
    },
    {
      say: 'زر القلم يفتح نموذج التعديل كامل',
    },
    {
      say: 'المرحلة، العنوان، النوع، ونص الرسالة',
    },
    {
      click: 'role=button:رجوع',
      say: 'ورجوع من هنا يلغي بلا حفظ',
    },
    {
      click: 'role=button:تعطيل',
      say: 'وزر التعطيل يطلب تأكيد أولًا',
    },
    {
      say: 'خطوتين، لا ضغطة وحدة تمسح قالب من المكتبة',
    },
    {
      click: 'role=button:إلغاء',
      say: 'وإلغاء يرجّعنا بلا أي تغيير',
    },
    {
      click: 'role=button:قالب جديد لهذه المرحلة',
      chapter: 'إضافة قالب جديد',
      say: 'وزر «قالب جديد» يفتح نموذج إضافة',
    },
    {
      click: 'css=input[placeholder="عنوان القالب"]',
      say: 'عنوان قصير يميّزه',
    },
    {
      click: 'css=textarea[placeholder="نص الرسالة كما تُرسَل بالضبط"]',
      say: 'ونص الرسالة بالضبط كما يوصل العميل',
    },
    {
      click: 'role=button:رجوع',
      say: 'ورجوع بلا حفظ يلغي الإضافة',
    },

    // ── مكتبة الأدلة ────────────────────────────────────────────────────────────────────────
    // TWO «رجوع» CLICKS ABOVE ONLY REACH THE HUB — the first exits the add-template FORM back to
    // the templates LIST, the second exits that LIST back to «أدواتي»'s own hub (line 75's own
    // click into «مكتبة الرسائل» never left it until now). A real recording caught this: the
    // script waited on «دليل جديد» right after, with no click into «مكتبة الأدلة» itself in
    // between — timed out on the hub screen forever. This click was missing, not optional.
    {
      click: 'role=button:رجوع',
      say: 'رجوع من قائمة القوالب يرجّعنا لقائمة الأدوات',
    },
    { waitFor: 'text=مكتبة الرسائل' },
    {
      click: 'role=button:مكتبة الأدلة',
      chapter: 'مكتبة الأدلة',
      say: 'وندخل الأداة الثانية: مكتبة الأدلة',
    },
    { waitFor: 'role=button:دليل جديد' },
    {
      say: 'حقائق مالية موثَّقة تستشهد بها',
    },
    {
      say: 'وأنت تكلّم صاحب المحل — لا رقم من عندك',
    },
    {
      say: 'كل دليل: عنوانه، نصه، ومصدره',
    },
    {
      say: 'مصدر برابط حقيقي يطلع كرابط أزرق',
    },
    {
      say: 'وحساب داخلي بلا رابط يطلع نص عادي، لا رابط مكسور',
    },
    {
      click: 'role=button:نسخ نص الدليل',
      say: 'ونفس زر النسخ هنا كمان',
    },
    {
      click: 'role=button:دليل جديد',
      chapter: 'إضافة دليل جديد',
      say: 'وزر «دليل جديد» لمدير التسويق فقط',
    },
    {
      click: 'css=input[placeholder="عنوان قصير"]',
      say: 'عنوان قصير للدليل',
    },
    {
      click: 'css=textarea[placeholder="النص الكامل بصيغة رقمية واقعية"]',
      say: 'ونصه الكامل — رقم واقعي، لا مبالغة',
    },
    {
      click: 'css=input[placeholder="اسم المصدر المختصر (يظهر بالمنصة)"]',
      say: 'واسم مصدر مختصر يظهر مع الدليل',
    },
    {
      click: 'role=button:رجوع',
      say: 'ورجوع بلا حفظ يلغي هذي الإضافة أيضًا',
    },

    // ── أداة البحث عن عملاء محتملين ────────────────────────────────────────────────────────
    // SAME MISSING STEP AS «مكتبة الأدلة» ABOVE — the «رجوع» right before this only exits the
    // add-guide FORM back to the guides LIST, still inside «مكتبة الأدلة», never the hub itself.
    {
      click: 'role=button:رجوع',
      say: 'ورجوع من قائمة الأدلة يرجّعنا لقائمة الأدوات',
    },
    { waitFor: 'text=مكتبة الرسائل' },
    {
      click: 'role=button:أداة البحث عن عملاء محتملين',
      chapter: 'أداة البحث عن عملاء محتملين',
      say: 'وثالث أداة — لمدير التسويق بس',
    },
    { waitFor: 'text=مفتاح خرائط جوجل' },
    {
      say: 'البحث عن محلات جديدة عبر خرائط جوجل',
    },
    {
      say: 'أول شي تحتاجه: مفتاح خرائط جوجل الخاص بك',
    },
    {
      click: 'role=button:تغيير',
      say: 'زر «تغيير» يفتح نموذج تحديث المفتاح',
    },
    // A REAL RECORDING CAUGHT «حفظ» STAYING DISABLED HERE — the form's own re-render after
    // «تغيير» wasn't necessarily settled yet when the very next step tried to type; an explicit
    // wait on the input actually being there closes that race.
    { waitFor: 'css=input[placeholder="AIza..."]' },
    {
      type: 'css=input[placeholder="AIza..."]',
      text: PLACES_DEMO_KEY,
      say: 'يُخزَّن مشفَّرًا على السيرفر',
    },
    {
      say: 'ولا يعرضه أحد كامل بعدها، فقط آخر أرقامه',
    },
    {
      click: 'role=button:حفظ',
      say: 'واضغط حفظ',
    },
    { waitFor: 'role=button:ابدأ بحثًا جديدًا' },
    {
      click: 'role=button:ابدأ بحثًا جديدًا',
      chapter: 'بدء بحث جديد',
      say: 'وزر «ابدأ بحثًا جديدًا» يفتح نموذج البحث الكامل',
    },
    {
      type: 'css=input[placeholder="رمز القطاع (مثال: salons)"]',
      text: 'صالونات',
      say: 'رمز القطاع اللي تدوّر عليه',
    },
    {
      type: 'css=input[placeholder="كلمات البحث، مفصولة بفاصلة"]',
      text: 'صالون تجميل، صالون نسائي',
      say: 'وكلمات البحث، أكثر من وحدة مفصولة بفاصلة',
    },
    {
      type: 'css=input[placeholder="اسم المدينة"]',
      text: 'الرياض',
      say: 'واسم المدينة',
    },
    {
      type: 'css=input[placeholder="خط العرض"]',
      text: '24.7136',
      say: 'وإحداثياتها بالضبط — خط العرض',
    },
    {
      type: 'css=input[placeholder="خط الطول"]',
      text: '46.6753',
      say: 'وخط الطول',
    },
    {
      say: 'ونطاق البحث بالكيلومتر — مقترح ٥ افتراضيًا',
    },
    // A REAL SUBMIT, A REAL REFUSAL — no sector is active on this platform at all
    // (`GET /me/sectors` answers `{"sectors":[]}`, confirmed live), so «صالونات» is refused as
    // `unknown_sector` by the real backend before any job is ever created. Same discipline as the
    // ticket refusal further down: the real refusal is shown, never a staged success.
    {
      click: 'role=button:ابدأ البحث',
      say: 'واضغط ابدأ',
    },
    { waitFor: 'text=القطاع غير معروف' },
    {
      say: 'ولا قطاع مفعّل على المنصة حاليًا — رفض حقيقي، لا نتيجة',
    },
    {
      say: 'لو كان القطاع مفعّلاً، كان يطلع سطر جديد بحالته الحيّة',
    },
    {
      say: 'بالانتظار، يعمل الآن، اكتمل، أو فشل',
    },
    {
      say: 'وشريط تقدّم أثناء العمل، وتحته كم محل وُجد وكم منه مكرر',
    },
    {
      click: 'role=button:إلغاء',
      say: 'نرجع — لا شي لنكمله هنا الآن',
    },

    // ── إحصائيات القطاعات ──────────────────────────────────────────────────────────────────
    // SAME MISSING STEP — this «رجوع» exits the search tool straight to the hub (one level, not
    // two, unlike the templates/guides lists above), so a click on the hub card itself still has
    // to follow before this next sub-screen's own content appears.
    {
      click: 'role=button:رجوع',
      say: 'ورجوع من أداة البحث يرجّعنا لقائمة الأدوات',
    },
    { waitFor: 'text=مكتبة الرسائل' },
    {
      click: 'role=button:إحصائيات القطاعات',
      chapter: 'إحصائيات القطاعات',
      say: 'ورابع أداة، لمدير التسويق بس أيضًا',
    },
    { waitFor: 'role=button:رجوع' },
    {
      say: 'إحصائيات القطاعات — تلخّص نتائج بحثك السابقة',
    },
    {
      say: 'أي قطاع، وأي مدينة، يعطيك محلات أكثر فعليًا',
    },
    {
      say: 'والبحث اللي بدأناه للتو لسه ما اكتملت نتائجه',
    },
    {
      say: 'فالقائمة هنا صادقة: فاضية لين تكتمل',
    },

    // ── تذاكر المحلات ───────────────────────────────────────────────────────────────────────
    // SAME MISSING STEP — «إحصائيات القطاعات» is itself a single flat screen (one «رجوع» level),
    // so this one exits straight to the hub too, and still needs its own hub-card click after.
    {
      click: 'role=button:رجوع',
      say: 'ورجوع من الإحصائيات يرجّعنا لقائمة الأدوات',
    },
    { waitFor: 'text=مكتبة الرسائل' },
    {
      click: 'role=button:تذاكر المحلات',
      chapter: 'تذاكر المحلات',
      say: 'وخامس وآخر أداة — يشوفها كل مسوّق، مو المدير بس',
    },
    { waitFor: 'text=صالون تجريبي' },
    {
      say: 'تذاكر المحلات',
    },
    {
      say: 'قائمة كل محل أحلته وله تذاكر — كل محل بصفّه الخاص',
    },
    {
      // NOT a chapter mark — a real recording landed it 9.8s after «تذاكر المحلات» above, and
      // YouTube drops the WHOLE chapter list if any two are under 10s apart (same rule
      // affiliate-home-1-overview.mjs's own comment already documents).
      click: 'css=ul li button',
      say: 'افتح أي محل تشوف كل تذاكره هو تحديدًا',
    },
    { waitFor: 'role=button:تذكرة جديدة' },
    {
      say: 'وهذا المحل ما فتح تذكرة بعد — قائمة فاضية بصراحة',
    },
    {
      click: 'role=button:تذكرة جديدة',
      chapter: 'فتح تذكرة جديدة',
      say: 'وزر «تذكرة جديدة» يفتحها نيابة عن المحل',
    },
    {
      say: 'أو لتسجّل مشكلة تواجهها معه أنت',
    },
    {
      type: 'css=input[placeholder="نوع المشكلة"]',
      text: 'استفسار عن الحساب',
      say: 'نوع المشكلة — الحقل الوحيد المطلوب',
    },
    {
      type: 'css=input[placeholder="عنوان (اختياري)"]',
      text: 'صعوبة بربط واتساب',
      say: 'وعنوان مختصر، اختياري',
    },
    {
      type: 'css=textarea[placeholder="تفاصيل المشكلة"]',
      text: 'صاحب المحل يقول رقم الواتساب ما يقبل الربط من أول محاولة — يحتاج مساعدة.',
      say: 'وتفاصيلها كاملة',
    },
    // A REAL SUBMIT, A REAL REFUSAL — this exact shop's own consent grant never carried WRITE
    // permission (operations' own `open_shop`'s ticket-share call is best-effort, nested inside
    // the referral-stamp branch; confirmed live against this account: the read grant exists, the
    // write grant does not). Faking a successful ticket here would be exactly the invented-data
    // shortcut this whole tour family refuses, so this clip shows the REAL refusal instead — a
    // marketer without write consent is itself a real, worth-knowing shape of this screen.
    {
      click: 'role=button:فتح التذكرة',
      say: 'واضغط فتح التذكرة',
    },
    { waitFor: 'text=المحل لم يمنحك صلاحية' },
    {
      chapter: 'رفض حقيقي: بلا صلاحية كتابة',
      say: 'وهذا محل ما منحه إذن الكتابة — فقط المشاهدة',
    },
    {
      say: 'رسالة الخادم الحقيقية توضّح السبب مباشرة',
    },
    {
      say: 'ليست كل محلاته تمنحه هذا الإذن تلقائيًا',
    },
    {
      chapter: 'خلاصة أدواتي',
      say: 'وبكذا خلصنا «أدواتي» كاملة',
    },
    {
      say: 'مكتبة الرسائل، مكتبة الأدلة، البحث عن عملاء',
    },
    {
      say: 'إحصائيات القطاعات، وتذاكر المحلات',
    },
    {
      say: 'خمس أدوات مختلفة، كل وحدة بشاشتها الخاصة',
    },
    {
      say: 'لا زحمة، ولا شي مخفي عن اللي يحتاجه',
    },
  ],
};
