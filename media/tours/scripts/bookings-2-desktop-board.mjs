/**
 * «الحجوزات» — أهم شاشة بالمنصة، بالعرض الأفقي الكامل: كل قدرة حقيقية فيها، بلا استثناء.
 *
 * لماذا هذا المقطع طويل عمداً: هذي الشاشة اللي يدير منها المحل يومه كامل، وطلب صريح ألا يُفوَّت
 * فيها شيء — حتى الحالات الصعبة والنادرة. الطول مو مشكلة هنا، التغطية الناقصة هي المشكلة.
 *
 * العرض الأفقي = فأرة، والشاشة تعرف ذلك. Bookings.tsx يقرأ `matchMedia('(pointer: coarse)')`
 * مرة وحدة عند التحميل ليقرر شكلها الافتراضي — جوال يفتح على القائمة، حاسوب على الشبكة.
 * record-tour.mjs يترك `hasTouch` false لأي تسجيل `orientation: 'landscape'`، فتجاوب الشاشة
 * بالضبط متل ما يجاوب حاسوب حقيقي — بلا أي تدخل يدوي هنا.
 *
 * بيانات العرض الحقيقية المطلوبة (media/tours/seed-demo-account.mjs، BOOKINGS_ONLY=1 قبل التسجيل):
 *   · 0555010101 «عميلة العرض» — نقاط ومكافأة حقيقية جاهزة للاستبدال (seedHeroCustomer).
 *   · 0555020202 «عميل متأخر» — ٤ من ٥ مواعيد ماضية «لم يحضر»، فعلياً عبر /no-show، لا حقل مصطنع
 *     (seedNoShowRiskCustomer) — النسبة (٨٠٪) تتجاوز حد التحذير الافتراضي (٦٠٪) بمسافة مريحة.
 *   · حجز واحد فات وقته ولم يُغلق بعد (seedOverdueBooking) — لبانر التنبيه.
 *
 * ثلاث قدرات حقيقية موجودة بالكود ومذكورة صوتياً هنا، لكن غير مُفعَّلة حياً بهذا التسجيل — تحتاج
 * بيانات تجريبية إضافية لم تُجهَّز بعد (تُذكر صراحة، لا تُخفى):
 *   · «لا يوجد موظف واحد يقدر يسوّي كل هذه الخدمات معاً» — يحتاج قيود تأهيل موظفين حقيقية بين
 *     خدمتين (StaffEligibilityLookup)؛ البيانات الحالية كل موظف مؤهّل للكل، فالحالة لا تظهر أبداً.
 *   · إصلاح «مدة الخدمة الناقصة» المضمّن — يحتاج خدمة حقيقية بمدة صفر بالكتالوج؛ لا توجد حالياً.
 *   · «أقرب يوم فيه فتحة» — يحتاج يوماً بلا أي فراغ إطلاقاً عند موظف بعينه؛ لوحة اليوم مشغولة
 *     ثلثيها عمداً (لا كاملة)، فالزر يظهر لكن لا يُضغَط بثقة أنه سيُفعَّل فعلياً.
 *
 * SELECTORS قُرئت من الصفحة الحية بهذا المقاس تحديداً، لا من التخمين:
 *   · ترتيب الأعمدة = ترتيب الـDOM لا ترتيب الشاشة (الصفحة RTL، فأول عمود بالكود هو الأقصى يميناً).
 *   · خانة ربع الساعة بلا اسم واجهة — تُقرأ عبر رقاقة وقتها (`hidden group-hover:block`).
 *   · «حضر» بادئة لـ«لم يحضر»، و«عربون» بادئة لـ«بدون عربون» — كلاهما يحتاج مطابقة تامّة (`!`).
 *   · أزرار «فعّل العربون الآن»، «أقرب يوم فيه فتحة»، «إدخال يدوي»، «افتح الأقدم» كلها أزرار نص
 *     بسيطة بلا testid — تُقرأ بنصها الحرفي (BookingDialog.tsx، Bookings.tsx، قُرئت مباشرة).
 *   · «احجز الجلسة القادمة — بعد N يوماً» يحوي رقماً متغيراً (`cycleDays`) — مطابقة جزئية بالبادئة
 *     فقط، لا نص كامل.
 */
export default {
  id: 'bookings-2-desktop-board',
  title: 'الحجوزات — كل قدراتها، شاشة كاملة',
  section: 'الحجوزات',
  useDemoSession: true,
  orientation: 'landscape',
  preload: true,
  secondsCap: 900,
  steps: [
    // ── الافتتاحية ──────────────────────────────────────────────────────────────────────────
    {
      goto: '/bookings',
      chapter: 'لوحة يومك كاملة',
      say: 'هذي أهم شاشة بمحلّك — كل موعد اليوم، وكل قرار عليه، بمكان واحد',
    },
    { waitFor: 'testid=rj-grid' },
    {
      hover: 'text=أخصائية الشعر',
      say: 'كل موظفة عمود، من فتح المحل إلى إغلاقه',
    },
    {
      say: 'والوقت ينزل من فوق لتحت، وكل بطاقة بمكان ساعتها الحقيقي',
    },
    {
      hover: 'css=[data-testid="rj-grid"] div[draggable="true"]:has-text("صبغة شعر كاملة")',
      say: 'وطول البطاقة هو طول الخدمة — ساعتان تاخذ ضعف الساعة الواحدة',
    },
    // ── تنبيه المواعيد المتأخرة ─────────────────────────────────────────────────────────────
    // MOVED HERE FROM LATER IN THE SCRIPT, RIGHT AFTER THE GRID LOADS — not a stylistic choice.
    // Live testing found the seeded overdue booking (seedOverdueBooking) reliably flips out of
    // 'booked' within under a minute of being created, for a reason not yet root-caused (checked
    // and ruled out: our own code has no cron/scheduled sweep on bookings at all, no event
    // consumer anywhere touches booking status, and the peer session's own tree has zero
    // bookings-related code). Since the fifty-odd steps that used to run before this chapter
    // reliably burned past that window every single recording, this chapter now runs first,
    // while the seed is still fresh — the actual fix for whatever is closing it early, if it
    // turns out to be ours, is still open.
    {
      waitFor: 'text=فات وقته',
      chapter: 'تنبيه المواعيد المتأخرة',
      say: 'وشريط فوق اللوحة يراقب شي ثاني: مواعيد فاتت ولا أحد أقفلها',
    },
    {
      say: 'موعدٌ حضر عميله ولا أحد سجّله «حضر»؟ يبقى معلّقاً — وهذا الشريط يذكّرك',
    },
    {
      click: 'role=button:افتح الأقدم',
      say: 'وزر واحد يفتحه لك مباشرة — أقدم موعد معلّق، بلا ما تدوّر عليه بنفسك',
    },
    {
      click: 'role=button:إغلاق!',
      say: 'نغلق ونكمل جولتنا على اللوحة',
    },
    // ── الخانة ربع ساعة ─────────────────────────────────────────────────────────────────────
    // NOT a fixed nth= — the seed data intentionally leaves the day two-thirds busy (see header
    // comment), and which column's 5:30 م slot is the free one shifts across reseeds (record-tour
    // .mjs's own array-candidate support picks whichever one is actually clickable this run).
    {
      hover: [
        'css=[data-testid="rj-grid"] button:has(> span:text-is("5:30 م")) >> nth=0',
        'css=[data-testid="rj-grid"] button:has(> span:text-is("5:30 م")) >> nth=1',
        'css=[data-testid="rj-grid"] button:has(> span:text-is("5:30 م")) >> nth=2',
      ],
      chapter: 'الخانة ربع ساعة',
      say: 'مرّر على أي فراغ: يضيء ويقول وقته',
    },
    {
      say: 'كل خانة ربع ساعة بالضبط — وعليها يستوي كل حجز وكل نقل',
    },
    {
      say: 'ونفس الربع ساعة هو اللي يمنع موعدين يتصادمون على موظفة وحدة',
    },
    // ── حجز جديد بذكاء ──────────────────────────────────────────────────────────────────────
    {
      click: [
        'css=[data-testid="rj-grid"] button:has(> span:text-is("5:30 م")) >> nth=0',
        'css=[data-testid="rj-grid"] button:has(> span:text-is("5:30 م")) >> nth=1',
        'css=[data-testid="rj-grid"] button:has(> span:text-is("5:30 م")) >> nth=2',
      ],
      chapter: 'حجز جديد بذكاء',
      say: 'واضغطها يفتح الحجز وقد عرف الموظفة والوقت',
    },
    {
      type: 'label=جوّال العميل',
      text: '0555010101',
      say: 'ابدأ بجوال العميلة',
    },
    { waitFor: 'role=button:عميلة العرض' },
    {
      click: 'role=button:عميلة العرض',
      say: 'تطلع من عملائك وأنت تكتب — اضغطها',
    },
    {
      hover: 'text=عميل معروف',
      say: 'عرفها، فما تحتاج تكتب اسمها من جديد',
    },
    {
      click: 'role=button:قص شعر',
      say: 'اختر الخدمة — و⭐ عليها معناها نقاطها تكفي مكافأة عليها',
    },
    // A SPECIFIC TIME CANNOT BE HARDCODED HERE — the chips are real `nearest_slot` answers
    // against whatever the board's live occupancy happens to be at recording time, so the exact
    // first-available time shifts run to run. A regex accessible-name grabs whichever chip is
    // actually first, matching only the HH:MM shape `timeOfEpoch()` renders (confirmed live:
    // Playwright's own CSS `:text-matches()` silently matches nothing in this build — see
    // lib/locate.mjs's own note on why `role=.../…/` exists).
    { waitFor: 'role=button:/^\\d{2}:\\d{2}/' },
    {
      hover: 'label=الموظف',
      say: 'الموظفة جاهزة من الخانة اللي ضغطتها، وتقدر تغيّرها',
    },
    {
      // THE STAFF FIELD NARROWS TO THE INTERSECTION OF OPERATORS ELIGIBLE FOR EVERY CHOSEN
      // SERVICE — mentioned here rather than forced live: current seed data has no per-operator
      // restriction, so "أي متاح" always resolves; the refusal message only appears against real
      // eligibility rules this demo doesn't carry yet.
      say: 'ولو اخترت خدمتين ما فيه موظفة وحدة تسوّيهما مع بعض، النظام يقولها صراحة بدل ما يخمّن',
    },
    {
      click: 'role=button:/^\\d{2}:\\d{2}/',
      say: 'والوقت رقاقات — كل رقاقة فتحة فاضية فعلاً عند هذي الموظفة',
    },
    {
      say: 'ولو يوم بأكمله ما فيه فتحة، زر «أقرب يوم فيه فتحة» يقفز لك أقرب موعد خلال أسبوعين',
    },
    {
      click: 'text=تفاصيل الدفع',
      say: 'وتحت «تفاصيل الدفع» سعر هذا الموعد وحالة دفعه',
    },
    { waitFor: 'label=السعر (اختياري، ريال)' },
    {
      type: 'label=السعر (اختياري، ريال)',
      text: '90',
      say: 'وتقدر تغيّر سعرها هنا — لهذا الموعد بس، افتراضياً',
    },
    {
      say: 'أو فعّل «احفظه كسعر ثابت لهذه الخدمة» لو تبغى كل الحجوزات الجاية تاخذ نفس السعر تلقائياً',
    },
    { waitFor: 'role=radio:عربون!' },
    {
      click: 'role=radio:عربون!',
      say: 'اطلب عربون لو تبغى تأكيد الموعد',
    },
    {
      type: 'label=مبلغ العربون (ريال)',
      text: '50',
      say: 'والمبلغ إجباري — عشان يبقى رقمٌ يُرجع له بعد شهر',
    },
    { waitFor: 'label=جائزة يريد استبدالها' },
    {
      select: 'label=جائزة يريد استبدالها (اختياري)',
      option: 'قص شعر مجاناً (300)',
      say: 'واختر جائزتها — تُصرف عند حضورها، لا الآن',
    },
    {
      click: 'text=إدخال يدوي',
      say: 'ولو محتاج تاريخاً ماضياً أو حالة ما يغطيها شريط الرقائق، «إدخال يدوي» مسار احتياطي مطويّ',
    },
    {
      click: 'text=إخفاء الإدخال اليدوي',
      say: 'نطويه ونرجع للرقائق الذكية — هي الأسرع بكل الحالات العادية',
    },
    {
      click: 'role=button:احجز!',
      say: 'واحجز',
    },
    { waitFor: 'css=[data-testid="rj-grid"] div[draggable="true"]:has(span[title="جائزة بانتظار الاستبدال عند الحضور"])' },
    {
      say: 'وطلعت بطاقتها بمكان وقتها، وعليها «عربون 50» و⭐ الجائزة',
    },
    // ── عميل يتأخر عن مواعيده ───────────────────────────────────────────────────────────────
    // THE FLOATING «حجز جديد» BUTTON, NOT A GRID CELL — a specific cell's occupancy shifts every
    // recording as the board fills up with whatever this same take already booked, and guessing
    // an empty one is exactly the fragility that broke this take once already. The floating
    // button opens the SAME dialog with nothing pre-filled, so staff/time still come from the
    // real slot search either way — nothing about the scenario changes, only how it opens.
    {
      hover: 'role=button:حجز جديد',
      chapter: 'عميل يتأخر عن مواعيده',
      say: 'وشي ثاني تشوفه بس مع عملاء معيّنين — تنبيه ذكي عن سلوكهم',
    },
    {
      click: 'role=button:حجز جديد',
      say: 'خلنا نحجز لعميل له تاريخ متكرر بالتأخر',
    },
    {
      type: 'label=جوّال العميل',
      text: '0555020202',
      say: 'جواله',
    },
    { waitFor: 'role=button:عميل متأخر' },
    {
      click: 'role=button:عميل متأخر',
      say: 'وهذا هو',
    },
    { waitFor: 'text=نسبة عدم حضوره مرتفعة' },
    {
      say: 'المنصة راقبت تاريخه الحقيقي: غاب عن أغلب مواعيده آخر فترة، فتحذّرك قبل ما تحجز له',
    },
    {
      say: 'الرقم حقيقي محسوب من زياراته الفعلية — مو انطباعاً ولا تخميناً',
    },
    {
      click: 'role=button:فعّل العربون الآن',
      say: 'وضغطة وحدة تفعّل له العربون فوراً — القرار قرارك، والنظام يقترحه بس',
    },
    {
      say: 'ولو ما ضغطتها، ولا شي يمنعك تكمل حجزه عادي — هذا تنبيه، لا رفض',
    },
    {
      click: 'role=button:إلغاء!',
      say: 'نلغي هذا الحجز التجريبي ونرجع للوحة',
    },
    // ── انقل موعد بالسحب ────────────────────────────────────────────────────────────────────
    {
      dragFrom: 'css=[data-testid="rj-grid"] div[draggable="true"]:has(span[title="جائزة بانتظار الاستبدال عند الحضور"])',
      chapter: 'انقل موعد بالسحب',
      say: 'تأجّل الموعد؟ امسك البطاقة نفسها',
    },
    {
      dragOver: 'css=[data-testid="rj-grid"] button:has(> span:text-is("4:00 م")) >> nth=1',
      say: 'ومرّها على خانة عليها موعد',
    },
    {
      say: 'أحمر: متعارض — موظفة واحدة ما تاخذ موعدين بنفس الوقت',
    },
    {
      dragOver: 'css=[data-testid="rj-grid"] button:has(> span:text-is("6:00 م")) >> nth=2',
      say: 'ومرّها على فراغ، ولو عند موظفة ثانية',
    },
    {
      say: 'أخضر، ومكتوب عليه وقت وصولها بالضبط قبل ما ترميها',
    },
    {
      dragDrop: 'css=[data-testid="rj-grid"] button:has(> span:text-is("6:00 م")) >> nth=2',
      say: 'وارمها',
    },
    {
      say: 'انتقلت للموظفة الجديدة، و«تراجع» تحت يرجّعها لو غلطت',
    },
    // ── ابحث بجوال العميل ───────────────────────────────────────────────────────────────────
    // (the overdue-alert chapter itself now runs right after the grid loads — see top of file)
    {
      chapter: 'ابحث بجوال العميل',
      say: 'ونبحث الآن عن عميلة واقفة تسأل عن موعدها',
    },
    {
      type: 'label=ابحث عن حجز عميل بجواله',
      text: '0555010101',
      say: 'اكتب جوالها',
    },
    { waitFor: 'role=button:عميلة العرض' },
    {
      click: 'role=button:عميلة العرض',
      say: 'اضغط اسمها',
    },
    { waitFor: 'role=button:السابقة' },
    {
      say: 'وتطلع مواعيدها القادمة كلها — أي يوم وأي فرع، مو يومك هذا',
    },
    {
      click: 'role=button:السابقة',
      say: 'و«السابقة» تجمع مواعيدها وزياراتها القديمة بصف واحد',
    },
    {
      click: 'role=button:إلغاء!',
      say: 'وتشيل بحثها فترجع لوحتك مثل ما كانت',
    },
    // ── الفلاتر ─────────────────────────────────────────────────────────────────────────────
    {
      click: 'role=button:الخدمة',
      chapter: 'الفلاتر',
      say: 'والفلاتر تضيّق اللوحة على خدمة بعينها',
    },
    { waitFor: 'css=[role="listbox"] input' },
    {
      type: 'css=[role="listbox"] input',
      text: 'مانيكير',
      say: 'وفيها بحث لو خدماتك كثيرة',
    },
    {
      click: 'role=option:مانيكير',
      say: 'اختر «مانيكير» — وتقدر تختار أكثر من وحدة',
    },
    {
      say: 'وما بقي على اللوحة إلا مواعيد هذي الخدمة',
    },
    {
      click: 'role=button:عربون!',
      say: 'وحالة الدفع فلتر ثانٍ يجتمع معه',
    },
    {
      click: 'role=button:إزالة كل الفلاتر',
      say: 'وضغطة وحدة تشيلها كلها',
    },
    // ── أوقات الدوام ────────────────────────────────────────────────────────────────────────
    {
      click: 'role=button:أوقات الدوام',
      chapter: 'أوقات الدوام',
      say: 'ومن هنا تضبط دوامك الأسبوعي — سياسة واحدة تحكم كل فروعك',
    },
    { waitFor: 'text=الجمعة' },
    {
      say: 'كل يوم له فتح وإغلاق، أو تقفله كامل لو عطلة',
    },
    {
      say: 'وعلى هذي الساعات بالضبط تُبنى كل رقاقة وقت تشوفها بالحجز — لا تخمين',
    },
    {
      click: 'role=button:Close',
      say: 'نغلق دون تعديل — دوامك الحالي مضبوط أصلاً',
    },
    // ── الأسبوع كامل ────────────────────────────────────────────────────────────────────────
    {
      click: 'role=button:الأسبوع',
      chapter: 'الأسبوع كامل',
      say: 'و«الأسبوع» يوريك أسبوعك كامل بصف واحد',
    },
    {
      say: 'مرتّب بالأيام، ونفس منطق الشبكة يحكمه',
    },
    {
      click: 'role=button:اليوم!',
      say: 'وترجع ليومك بضغطة',
    },
    // ── إدارة موعد قائم ─────────────────────────────────────────────────────────────────────
    {
      click: 'css=[data-testid="rj-grid"] div[draggable="true"]:has-text("صبغة شعر كاملة")',
      chapter: 'إدارة موعد قائم',
      say: 'واضغط أي بطاقة تفتح ورقتها',
    },
    { waitFor: 'role=button:تعديل الحجز' },
    {
      say: 'خدمتها ووقتها ومدتها وموظفتها وسعرها — قبل ما تقرر شي',
    },
    {
      click: 'role=button:تعديل الحجز',
      say: 'و«تعديل» يفتح نفس شاشة الحجز على هذا الموعد',
    },
    {
      // THE PRICE FIELD IS CREATE-ONLY (`!editing && chosen.length > 0` in BookingDialog.tsx) —
      // already shown and set on the FIRST booking created earlier in this same recording; an
      // edit only touches service/time/note/payment, never the price field itself.
      click: 'text=تفاصيل الدفع',
      say: 'ولو تبغى تغيّر خدمتها أو موظفتها من هنا، نفس الحوار',
    },
    {
      type: 'label=ملاحظة (اختياري)',
      replace: true,
      text: 'أكدت بالواتساب',
      say: 'واكتب ملاحظة تقرأها بكرة',
    },
    {
      click: 'role=button:حفظ التعديل',
      say: 'واحفظ — نفس الموعد يتعدّل، ما ينفتح حجزٌ ثانٍ',
    },
    // ── إلغاء موعد ──────────────────────────────────────────────────────────────────────────
    // «حجز جديد» AGAIN, NOT A GUESSED-EMPTY CELL — same reasoning as the risk-badge chapter above.
    {
      hover: 'role=button:حجز جديد',
      chapter: 'إلغاء موعد',
      say: 'ولو عميل اتصل واعتذر عن موعده',
    },
    {
      click: 'role=button:حجز جديد',
      say: 'نفتح موعداً تجريبياً بسيطاً',
    },
    {
      type: 'label=جوّال العميل',
      text: '0599112233',
      say: 'جوال عميل جديد',
    },
    // A GENUINELY NEW NUMBER — no suggestion to click, so the dialog opens its own inline name
    // field instead (`phone.length >= 3` with no match), exactly as it would for a real walk-in.
    { waitFor: 'label=اسمها (اختياري)' },
    {
      type: 'label=اسمها (اختياري)',
      text: 'عميل تجريبي',
      say: 'وعميل جديد كلياً — الاسم يُكتب مرة وحدة، ما راح يُطلب ثانية',
    },
    {
      click: 'role=button:مانيكير',
      say: 'خدمة سريعة',
    },
    { waitFor: 'role=button:/^\\d{2}:\\d{2}/' },
    {
      click: 'role=button:/^\\d{2}:\\d{2}/',
      say: 'ونؤكد وقتها',
    },
    { waitFor: 'role=button:احجز!' },
    {
      click: 'role=button:احجز!',
      say: 'نحجزه أول',
    },
    {
      click: 'css=[data-testid="rj-grid"] div[draggable="true"]:has-text("مانيكير") >> nth=0',
      say: 'ونفتحه من جديد',
    },
    { waitFor: 'role=button:إلغاء الحجز' },
    {
      click: 'role=button:إلغاء الحجز',
      say: 'زر «إلغاء» يقفله بلا زيارة مسجّلة — وقته يرجع فاضياً فوراً لأي حجز آخر',
    },
    // ── حضر ولم يحضر ────────────────────────────────────────────────────────────────────────
    {
      // `:has-text` MATCHES RENDERED innerText — the "جائزة بانتظار…" string only ever lives in
      // the ⭐ icon's `title` attribute (a hover tooltip, not painted text), so this must match the
      // same way the two earlier steps on this same card already do (`:has(span[title=…])`).
      click: 'css=[data-testid="rj-grid"] div[draggable="true"]:has(span[title="جائزة بانتظار الاستبدال عند الحضور"])',
      chapter: 'حضر أو لم يحضر',
      say: 'ونرجع لموعد عميلتنا صاحبة الجائزة',
    },
    {
      say: '⭐ معناها جائزة محجوزة لها، ونقاطها لسه ما انخصمت',
    },
    {
      hover: 'role=button:لم يحضر!',
      say: 'ولو ما جاء العميل إطلاقاً، «لم يحضر» يقفل الموعد بلا زيارة — وتدخل بياناته بحساب سلوكه لاحقاً',
    },
    {
      click: 'role=button:حضر!',
      say: 'لكن عميلتنا جت وخلصت، فنضغط «حضر»',
    },
    { waitFor: 'text=سُجّل الحضور' },
    {
      say: 'سُجّلت زيارتها، وانخصمت نقاط جائزتها بنفس اللحظة — لا قبلها',
    },
    { waitFor: 'text=احجز الجلسة القادمة' },
    {
      say: 'وفوراً — «احجز الجلسة القادمة» يقترح موعدها الجاي حسب دورتها المعتادة، بضغطة وحدة',
    },
    {
      click: 'role=button:إغلاق!',
      say: 'نكتفي بهذا الآن',
    },
    {
      say: 'وصارت بطاقتها «حضر»، والنجمة راحت: الجائزة انصرفت فعلاً',
    },
  ],
};
