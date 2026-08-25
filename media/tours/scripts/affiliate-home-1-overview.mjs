/**
 * «الرئيسية» — the affiliate portal's own home screen, in one full, uncut walk. Read
 * AffiliateHome.tsx, TicketCarousel.tsx, AffiliatePortal.tsx and AffiliateNav.tsx directly before
 * writing a single selector — this project's own standing rule (see services-1-overview.mjs's own
 * header for the same discipline applied to the shop console).
 *
 * ONE REQUEST, SIX-TO-EIGHT WIDGETS — AffiliateHome.tsx's own module comment: `GET /me/home`
 * assembles the whole screen server-side in a single call, and every widget below reads a real
 * field that call returns, never an invented number. The HIERARCHY on screen is deliberate
 * research, not a guess: urgent replies first (loss-aversion is this screen's own strongest
 * trigger for a WhatsApp-led sales flow), then the ticket carousel, then earnings, then the two
 * commission-program meters, then what is actually converting, then — manager only — the team,
 * then his own referral link.
 *
 * A REAL DOOR, NOT `useDemoSession` — this portal keeps its OWN session key
 * (`raje3.affiliate.session`, session.ts), a separate store from the shop console's
 * `raje3.session` that `useDemoSession` writes to. So this clip signs in through AffiliateDoor's
 * real form, the same door any marketer actually uses, rather than borrowing the shop's demo
 * session mechanism, which cannot hold this portal's token shape at all.
 *
 * THE DEMO ACCOUNT — A FRESHLY APPROVED MANAGER, VERIFIED LIVE BY A REAL `/me/home` READ BEFORE
 * THIS SCRIPT WAS FINALIZED, NOT ASSUMED. `سارة المسوّقة` applied and was approved through the
 * real `/api/v1/affiliates/apply` → admin `/approve` path (the same one `onboarding.py` documents
 * — no shortcut, no invented row), with one promoter approved under her referral code so
 * `team.member_count` reads 1, not a fabricated fleet. Every OTHER widget on her home screen reads
 * a genuine, honest zero: no payout method set yet, no lead ever searched, no ticket ever opened,
 * no template ever used, both eligibility meters at their real starting line. AffiliateHome.tsx's
 * own module comment calls this exact shape "the common case, not the edge case" — a day-one
 * screen has to read honestly at zero, and this clip narrates it exactly that way: the widgets
 * that have nothing to show are SPOKEN OVER, never clicked, the same discipline messages-1's own
 * WhatsApp-ceiling line already set for a control that genuinely is not there on its own demo
 * account.
 */
export default {
  id: 'affiliate-home-1-overview',
  title: 'الرئيسية 1 — فهم شاشة بوابة المسوّق كاملة',
  section: 'الرئيسية', // AffiliateNav.tsx's own tab label
  useDemoSession: false, // a separate door, a separate session key — see this file's own header
  skipAutoSignIn: true,  // the sign-in itself is this clip's own first real beat, not hidden setup
  sfx: true, // real clicks throughout (sign-in, every widget) — earns a click sound
  steps: [
    {
      goto: '/affiliates',
      chapter: 'بوابة المسوّق',
      say: 'بوابة كل مسوّق بالعمولة — تعال أوريك شاشته الأولى',
    },
    { waitFor: 'label=رقم الجوال', timeoutMs: 30_000 },
    {
      say: 'أول شي: تسجيل الدخول — رقم جواله',
    },
    {
      say: 'وكلمة مروره، مثل أي حساب',
    },
    {
      type: 'label=رقم الجوال',
      text: '+966555010001',
      say: 'يكتب رقم جواله',
    },
    {
      type: 'label=كلمة المرور',
      text: 'DemoTour2026x!',
      say: 'وكلمة مروره',
    },
    {
      click: 'role=button:تسجيل الدخول',
      say: 'ويدخل',
    },
    { waitFor: 'text=مرحباً', timeoutMs: 60_000 },
    {
      // NOT a chapter mark — it landed only 5.4s after the previous one on a real recording,
      // and YouTube drops the WHOLE chapter list if any two are under 10s apart. The next real
      // chapter ('أول شي يشوفه: من ينتظره') is close enough behind it that giving this its own
      // mark would violate that every time; the intro chapter above already covers this beat.
      say: 'وصل — هذي شاشته الأولى',
    },
    {
      say: 'مبنية من طلب واحد بس للسيرفر',
    },
    {
      say: 'كل ما تحته حقيقي من حسابه',
    },
    // ── العملاء المنتظرون — absent on this fresh account, narrated exactly like the screen's own
    //    empty-state design intends: no click on something that is not there. ────────────────────
    {
      chapter: 'أول شي يشوفه: من ينتظره',
      say: 'أعلى الشاشة: عملاء ما ردّ عليهم من زمان',
    },
    {
      say: 'تطلع بطاقة حمراء تنبّهه',
    },
    {
      say: 'حسابه جديد، ما عنده من ينتظر، فما تظهر',
    },
    {
      say: 'وما تظهر «كله تمام» بدلها — صمتها هو الرسالة',
    },
    // ── تذاكر المحلات — نفس المبدأ، غائبة لأنه ما فتح تذكرة بعد ─────────────────────────────────
    {
      say: 'وتحتها بانر تذاكر المحلات المفتوحة',
    },
    {
      say: 'لو عنده تذكرة — ما فتح واحدة بعد',
    },
    {
      say: 'فالبانر غائب، بلا فراغ يشغل مكانه',
    },
    // ── رصيده ───────────────────────────────────────────────────────────────────────────────────
    {
      click: 'text=رصيدك الجاهز للسحب',
      chapter: 'رصيده',
      say: 'رصيده الجاهز للسحب — أول رقم مالي يشوفه',
    },
    {
      click: 'text=معلَّق',
      say: 'وجنبه: كم معلَّق — عمولة استُحقت ولسه ما تأكدت',
    },
    // (line already short enough, kept)
    {
      click: 'text=مسحوب سابقًا',
      say: 'وكم سحبه من قبل — تاريخه الكامل',
    },
    {
      click: 'text=أضف طريقة استلام أرباحك',
      say: 'يظهر لأنه لسه ما ضبط طريقة استلام أرباحه',
    },
    {
      say: 'خطوة لازمة قبل أول سحب فعلي له',
    },
    // ── برنامجا العمولة ─────────────────────────────────────────────────────────────────────────
    {
      click: 'text=محلات نشِطة',
      chapter: 'برنامجا العمولة',
      say: 'مقياسان — كم قريب من كل برنامج عمولة عندنا',
    },
    {
      say: 'أولهما: محلات نشِطة جابها',
    },
    {
      say: 'أساس دعم «الوفاء» الشهري',
    },
    {
      click: 'text=عملاء مشتركون',
      say: 'وثانيهما: عملاء اشتركوا فعلاً',
    },
    {
      say: 'أساس الترشّح لوظيفة عندنا',
    },
    {
      say: 'حسابه جديد، فالمقياسان على بدايتهما الحقيقية',
    },
    // ── أفضل قالب — غائب لعدم وجود أي استخدام بعد ───────────────────────────────────────────────
    {
      say: 'وكان بينزل هنا أفضل قالب يشتغل معه',
    },
    {
      say: 'لو استخدم قالباً ولو مرة',
    },
    {
      say: 'ما استخدم قالباً بعد، فالبطاقة غائبة',
    },
    // ── فريقه — يظهر فقط للمدير، وعنده فرد واحد فعلي الآن ────────────────────────────────────────
    {
      click: 'text=فريقك',
      chapter: 'فريقه',
      say: 'تظهر لمدير التسويق بس — مسوّقون تحته يتابعهم',
    },
    {
      click: 'text=عدد الفريق',
      say: 'عدد من ضمّهم لفريقه حتى الآن',
    },
    {
      click: 'text=إيراد مؤكَّد',
      say: 'وإيراد فريقه المؤكَّد مجموعاً، لا فرد فرد',
    },
    {
      say: 'ولو عنده قرار وفاء ينتظره، بادج أحمر يذكّره هنا',
    },
    // ── رابطه: الأداة الفعلية للتجنيد ────────────────────────────────────────────────────────────
    {
      click: 'text=رابطك',
      chapter: 'رابطه',
      say: 'وآخر شي: رابطه — رقم حسابه نفسه، بلا كود منفصل يُنشأ',
    },
    {
      say: 'أول رابط: يدعو فيه صاحب محل يفتح حساباً براجع',
    },
    {
      click: 'css=button:has-text("نسخ") >> nth=0',
      say: 'زر «نسخ» ينسخه فوراً — يرسله بواتساب',
    },
    {
      click: 'css=button[aria-label="تنزيل كباركود"] >> nth=0',
      say: 'أو يحمّله باركوداً جاهزاً — للطباعة أو لقصّة',
    },
    {
      say: 'وبما إنه مدير، عنده رابط ثانٍ',
    },
    {
      click: 'css=button:has-text("نسخ") >> nth=1',
      say: 'يدعو فيه مسوّقاً جديداً ينضم تحته هو',
    },
    {
      click: 'css=button[aria-label="تنزيل كباركود"] >> nth=1',
      say: 'وله باركوده الخاص كذلك',
    },
    {
      chapter: 'خلاصة',
      say: 'كذا خلصنا شاشة «الرئيسية» كاملة',
    },
    {
      say: 'من ينتظره، رصيده، برنامجاه، فريقه، ورابطه',
    },
    {
      say: 'شاشة يوم واحد صادقة — كل رقم فيها حقيقي',
    },
  ],
};
