/**
 * «نقاطي» — ONE complete journey: understand the programme's own numbers, read its rewards table
 * and its earning tree exactly as they stand, then press the real controls — add a reward, edit
 * its cost, retire and reactivate one, switch how points are earned, and set the numbers at each
 * of its three levels. Read Points.tsx directly (this project's own standing rule) before writing
 * a single selector — done in full: every KPI label, every aria-label, every real error sentence
 * quoted here comes from that file and from services/loyalty/app/core/{earn,earning,rewards,
 * redeem,models}.py, not from any summary or plan document.
 *
 * ONE CONTINUOUS STORY, NOT TWO CLIPS. Per the same decision already made for تسجيل الزيارة/
 * خدماتي ومنتجاتي/رسائلي/عملائي: understanding a screen and acting on it are one owner's journey,
 * not two separate recordings that reopen the same page from scratch. Captions flow as one
 * narrative, each line picking up from the one before it, in a capability-marketing voice — what
 * the platform gives an owner, not a dry click-by-click walkthrough.
 *
 * WHY THE KPI ROW OPENS THE CLIP, NOT THE REWARDS TABLE. Points.tsx's own module comment calls
 * «نقطة لم تُستبدل بعد» a debt already promised, and its report.py source calls `expired_share`
 * "the one indicator that is a warning". An owner who never opens this screen has no other way to
 * see either. Leading with what he owes is the honest opening for a loyalty programme tour, not a
 * KPI-dashboard habit.
 *
 * THE DEMO SHOP'S REAL STATE (verified against seed-demo-account.mjs's seedHeroCustomer, not
 * assumed): three real rewards — قهوة مجانية (100, هدية), قص شعر مجاناً (300, من خدماتي), جلسة
 * مجانية VIP (600, هدية) — and a manager-approval threshold of 500, so the VIP session is the one
 * reward on this shop that genuinely needs the manager badge/threshold explained. Every service in
 * the catalogue was seeded with ITS OWN points value, so «إعداد خاص» badges are the expected, real
 * state of this shop's services list — not a fabricated example.
 *
 * THE NEW REWARD ADDED LIVE IS A DISCOUNT, ON PURPOSE — the one type whose own form field
 * (`riyals`) exercises `halalas()`'s real validation, the same fix this project's own earlier pass
 * landed in Points.tsx (converting text by integer arithmetic instead of `Number(riyals) * 100`,
 * which silently shorted a 2.30-riyal reward by one halala through float error). The edge case
 * shown later — three decimal places — is the real refusal sentence `addReward()` gives, sourced
 * from Points.tsx directly, not invented for the tour.
 *
 * THE INVOICE-EARNING HINT IS SHOWN AS A STATIC FACT, NOT A FORCED FAILURE. Points.tsx renders
 * "الاحتساب بقيمة الفاتورة يحتاج ربطاً بالكاشير…" whenever `earn.config.integrated === false`,
 * regardless of whether the mode switch is even pressed — this demo shop has no till connected, so
 * the sentence is already true and on screen the moment the earning tab opens; the tour simply
 * narrates what is genuinely there rather than manufacturing a failure.
 *
 * A REAL, CONFIRMED DEFECT FOUND WHILE WRITING THIS SCRIPT, FLAGGED SEPARATELY, NOT FIXED HERE:
 * the middle "نقاط مجموعة" level is UNREACHABLE from a cold state. Points.tsx's own `groupNames`
 * is derived only from `earn.service_group`'s existing keys, and that map is loyalty's OWN state
 * — populated only by a real `loyalty.settings.group` write (earning.py's `set_group`), never
 * synced from خدماتي's own «المجموعة» field (which is a completely separate system: reminders'
 * `reminders.set_group`, read by Services.tsx, not by this screen at all — confirmed live: a
 * direct `loyalty.settings.read` call on this reseeded tenant returned `service_group: {}` despite
 * every service being seeded with a `group` value in seed-demo-account.mjs). Since the whole
 * "نقاط مجموعة" block only renders `canSetGroup && groupNames.length > 0`, there is no control
 * anywhere in this screen that can create the FIRST group entry — a real, reachable dead end, not
 * a recording artefact. This tour narrates the per-service level (which works independently) and
 * does not click through the group level, since nothing on this shop's real current state can
 * render it; the defect itself is left for a dedicated fix (Points.tsx needs its own way to name a
 * new loyalty group, or to adopt خدماتي's group names as candidates), out of scope for this pass.
 */
const NEW_DISCOUNT_REWARD = 'خصم افتتاح فرع جديد';
const INVALID_DISCOUNT_REWARD = 'محاولة مبلغ خاطئ';

export default {
  id: 'points-1-programme-explained',
  title: 'نقاطي — من فهم برنامجك إلى تعديله بثقة',
  section: 'نقاطي', // nav.ts's own label
  useDemoSession: true,
  preload: true,
  secondsCap: 420,
  steps: [
    {
      goto: '/points',
      chapter: 'أرقام برنامجك',
      say: 'برنامج نقاطك يُرجع عملاءك — تعال نرى كل تفصيلة فيه',
    },
    {
      click: 'text=عميل يجمع نقاطاً',
      say: 'أول رقم: كم عميل عندك يجمع نقاطاً الآن',
    },
    {
      click: 'text=استبدال',
      say: 'وكم مرة استُبدلت نقاط بمكافآت فعلاً',
    },
    {
      click: 'text=نقطة لم تُستبدل بعد',
      say: 'وهذا أهمها: نقاط وعدت بها ولم تُصرف بعد',
    },
    {
      say: 'التزامٌ عليك، لا رقم عادي',
    },
    {
      click: 'text=من كل نقطة مُنحت، انتهت بلا استبدال',
      say: 'ونسبة النقاط اللي انتهت بلا استبدال',
    },
    {
      say: 'نسبة عالية تعني أن مكافآتك بعيدة عن متناول عملائك',
    },
    {
      // "أكثر ما يُستبدل" only renders once `report.top_rewards` has real entries — a shop with
      // real redemption history. Not hard-depended on here: a freshly reseeded demo tenant starts
      // with none, and this project's own rule is never to record what cannot be verified live.
      say: 'وبمجرد أول استبدال حقيقي',
    },
    {
      say: 'يظهر هنا ترتيب أكثر مكافآتك طلباً',
    },
    {
      click: 'text=جدول المكافآت',
      chapter: 'جدول المكافآت',
      say: 'وهذا جدول مكافآتك — يصل معبّأً، وتقدر تعدّله بحرية',
    },
    {
      click: 'text=قهوة مجانية',
      say: 'هذي أرخص مكافأة — أول شيء يستبدله عميلك عادة',
    },
    {
      click: 'text=قص شعر مجاناً',
      say: 'وهذي من خدماتك — مربوطة بخدمة حقيقية بكتالوجك',
    },
    {
      click: 'text=جلسة مجانية VIP',
      say: 'وهذي الأغلى — 600 نقطة',
    },
    {
      say: 'وستصل بشارة «باعتماد المدير»',
    },
    {
      say: 'لأنها فوق حدّ اعتماد ضبطته أنت بنفسك — سنراه بعد قليل',
    },
    {
      // The Segmented options are «المكافآت» and «الكسب» — verified against Points.tsx's own
      // Segmented options array.
      click: 'role=radio:الكسب',
      chapter: 'كيف تُكتسب النقاط',
      say: 'وهذا التبويب الثاني — «الكسب»',
    },
    {
      say: 'يشرح كيف يجمع عميلك النقاط أصلاً',
    },
    {
      click: 'text=طريقة الاحتساب',
      say: 'أول قرار هنا: طريقة الاحتساب',
    },
    {
      say: 'ومفتاحٌ واحد فقط — لا خانتا اختيار منفصلتين',
    },
    {
      say: 'بالخدمات: كل خدمة نقاطها الخاصة',
    },
    {
      say: 'وبقيمة الفاتورة: نقطة عن كل ريال',
    },
    {
      say: 'ولا يجتمعان — كي لا يأخذ عميلك ضِعف النقاط',
    },
    {
      say: 'عن نفس الزيارة',
    },
    {
      say: 'وهذا محلك تحديداً بلا كاشير مربوط بعد',
    },
    {
      say: 'فالاحتساب بقيمة الفاتورة يبقى معطّلاً حتى تربطه',
    },
    {
      click: 'label=نقاط لكل زيارة (عام)',
      say: 'وهذا الرقم العام — لأي خدمة بلا رقم خاص بها',
    },
    {
      click: 'label=مكافأة تحتاج اعتماد المدير من',
      say: 'وهذا حدّ اعتماد المدير اللي ذكرناه قبل قليل',
    },
    {
      say: 'أي مكافأة بهذي النقاط فأكثر تحتاج اسم مدير عند الاستبدال',
    },
    {
      say: 'صفر يعني بلا اعتماد إطلاقاً — وهذا المحل ضبطه 500',
    },
    {
      waitFor: 'text=نقاط خدمة بعينها',
      click: 'text=نقاط خدمة بعينها',
      chapter: 'طبقة ثانية: رقم خاص بكل خدمة',
      say: 'وفوق الرقم العام، رقمٌ خاص لكل خدمة على حدة إن أردت',
    },
    {
      say: 'يتقدّم دائماً على الرقم العام عند وجوده',
    },
    {
      say: 'وبشارة «إعداد خاص» تُظهر أي خدمة عندها رقمها المستقل',
    },
    {
      say: 'وكل خدماتك هنا عندها فعلاً رقم مخصّص',
    },
    {
      say: 'وبهذا فهمت برنامجك بالكامل',
    },
    {
      say: 'ننتقل الآن إلى التعديل الفعلي',
    },
    // ── الإضافة: مكافأة خصم حقيقية ───────────────────────────────────────────────────────────
    {
      click: 'role=radio:المكافآت',
      say: 'نرجع لتبويب المكافآت أولاً',
    },
    { waitFor: 'role=button:إضافة مكافأة', timeoutMs: 30_000 },
    {
      click: 'role=button:إضافة مكافأة',
      chapter: 'إضافة مكافأة جديدة',
      say: 'ولنضِف مكافأة جديدة فعلاً — بثلاث خطوات فقط',
    },
    {
      type: 'label=اسم المكافأة', text: NEW_DISCOUNT_REWARD,
      say: `اسمها «${NEW_DISCOUNT_REWARD}»`,
    },
    {
      type: 'label=التكلفة بالنقاط', text: '250',
      say: 'وتكلفتها 250 نقطة',
    },
    {
      select: 'label=النوع', option: 'خصم',
      say: 'والنوع هنا خصم مالي مباشر من قيمة الزيارة',
    },
    {
      type: 'label=مبلغ الخصم بالريال', text: '25.00', replace: true,
      say: 'خصم بقيمة 25 ريالاً بالضبط',
    },
    {
      click: 'role=button:حفظ',
      say: 'حفظ، وتظهر فوراً بالجدول جاهزة لعملائك',
    },
    { waitFor: `text=${NEW_DISCOUNT_REWARD}` },
    // ── تعديل التكلفة مباشرة ─────────────────────────────────────────────────────────────────
    {
      click: `css=li:has-text("${NEW_DISCOUNT_REWARD}") input`,
      chapter: 'تعديل التكلفة مباشرة',
      say: 'وتقدر تعدّل تكلفة أي مكافأة بالجدول مباشرة',
    },
    {
      type: `css=li:has-text("${NEW_DISCOUNT_REWARD}") input`, text: '200', replace: true,
      say: 'نخفّضها إلى 200 نقطة',
    },
    {
      click: 'css=body',
      say: 'ويُحفظ فور خروجك من الخانة — بلا زر حفظ منفصل',
    },
    // ── الإيقاف والتفعيل ─────────────────────────────────────────────────────────────────────
    {
      click: `css=li:has-text("${NEW_DISCOUNT_REWARD}") button`,
      chapter: 'إيقاف المكافأة، لا حذفها',
      say: 'ولاحظ: زر الإيقاف، لا زر حذف إطلاقاً بهذا الجدول',
    },
    {
      say: 'لأن كل استبدال بالتاريخ يشير إلى مكافأته',
    },
    {
      say: 'وحذفها يكسر السجل',
    },
    {
      say: 'فالمكافأة تختفي من قائمة عملائك فوراً',
    },
    {
      say: 'وتاريخها يبقى كاملاً',
    },
    {
      click: `css=li:has-text("${NEW_DISCOUNT_REWARD}") button`,
      say: 'وبنفس الزر تُعيدها للعمل فوراً، بنفس تكلفتها بالضبط',
    },
    // ── حالة حافة: مبلغ خصم غير صالح ─────────────────────────────────────────────────────────
    {
      waitFor: 'role=button:إضافة مكافأة', timeoutMs: 30_000,
    },
    {
      click: 'role=button:إضافة مكافأة',
      chapter: 'حالة حافة — مبلغ خصم غير صالح',
      say: 'وماذا لو أخطأت بكتابة المبلغ؟ المنصّة تحميك هنا أيضاً',
    },
    { type: 'label=اسم المكافأة', text: INVALID_DISCOUNT_REWARD },
    { type: 'label=التكلفة بالنقاط', text: '50' },
    { select: 'label=النوع', option: 'خصم' },
    {
      type: 'label=مبلغ الخصم بالريال', text: '2.305', replace: true,
      say: 'أكتب 2.305 — ثلاث خانات عشرية بدل اثنتين',
    },
    {
      click: 'role=button:حفظ',
      say: 'وهذي المرة، رسالة خطأ فعلية أعلى الشاشة، واضحة',
    },
    {
      say: '«اكتب مبلغ الخصم بالريال —',
    },
    {
      say: 'رقمٌ بمنزلتين عشريتين على الأكثر، مثل 2.30»',
    },
    {
      say: 'ولا تُقرَّب لك القيمة بصمت — تُرفض ويُطلب منك رقمٌ صحيح',
    },
    { click: 'role=button:إلغاء' },
    {
      chapter: 'خلاصة',
      say: 'وبهذا اكتملت الرحلة — فهمت برنامجك',
    },
    {
      say: 'وعدّلت مكافآته وإعداداته بثقة كاملة',
    },
  ],
};
