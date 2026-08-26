/**
 * «رسائلي» — MERGED 2 OF 2: «حملاتي» in full. Was three separate clips
 * (messages-3-campaigns, messages-4-campaign-anatomy, messages-5-campaign-strategy — each its
 * own recording/verification pass); merged into one continuous journey per the same decision
 * already made for تسجيل الزيارة and خدماتي ومنتجاتي: what «حملاتي» is → all eight real goals and
 * each one's actual audience → the four questions worth asking before you ever press launch —
 * one story, not three disconnected beats. The three original files are deleted; every real fact
 * and selector below is carried over from them unchanged, only the voice and the connective
 * tissue between beats are new.
 *
 * Read Messages.tsx, Launch.tsx and campaigns-service's core/audience.py directly before writing
 * a single selector — this project's own standing rule.
 *
 * A REAL, LIVE CONSTRAINT THIS SCRIPT IS BUILT AROUND, CONFIRMED NOT ASSUMED: a direct read of
 * `campaigns.goals` on this demo tenant, right before writing this file, showed all EIGHT goals
 * with `available: false` — "قوالب … ما زالت قيد مراجعة واتساب — سترسل تلقائياً عند اعتمادها."
 * Every goal card is genuinely disabled right now (Launch.tsx: `disabled={g.available === false}`),
 * so no real launch can be performed or verified today. That is not a demo-account defect to work
 * around — it is the EXACT state a real shop sees in its first days on the platform, before Meta
 * has approved its message templates, and it is worth teaching honestly rather than faked. NOTHING
 * HERE EVER CLICKS A LOCKED CARD OR PRESSES A REAL LAUNCH — every goal walkthrough below uses
 * `hover`, never `click`, on the goal cards themselves.
 *
 * THE EIGHT GOALS (not six — `seasonal_care` and `safety` are real, current goals; a real gap this
 * project's own earlier pass fixed in Messages.tsx's GOAL_TITLE map, in its own commit).
 *
 * WHY THE AUDIENCE RULES ARE SAID IN WORDS, NOT DEMONSTRATED WITH A LIVE PREVIEW: `ask()` (the
 * "اعرض ما سيصل" button) only ever renders once a goal is `picked`, and every card is disabled —
 * Playwright cannot click through that any more than a real finger could. Saying what audience.py
 * actually computes, sourced from that file rather than guessed from the card's summary line, is
 * the honest way to teach it without pretending a locked card is not locked.
 */
export default {
  id: 'messages-2-campaigns',
  title: 'حملاتي — ثمانية أهداف تسويقية جاهزة، تختار متى تُطلقها',
  section: 'رسائلي',
  useDemoSession: true,
  sfx: true, // real clicks (tabs, launch button) — earns a click sound
  preload: true,
  // Dense clip: 8 goals walked one by one plus a 4-question strategy pass, ~75 steps of mostly
  // short hovers — the 180s default cap isn't enough room; same reasoning services-1-overview's
  // own secondsCap comment already gives for its own longer walkthrough.
  secondsCap: 300,
  steps: [
    {
      goto: '/messages',
      chapter: 'حملاتي — أنت من يقرر',
      say: 'وأخيرًا — «حملاتي»، القسم الوحيد اللي أنت',
    },
    {
      say: 'من يطلقه بنفسك',
    },
    {
      click: 'role=radio:حملاتي',
      say: 'اضغط تبويب «حملاتي»',
    },
    {
      say: 'هذي وحدها لا ترسل إلا عندما تضغط أنت شخصياً',
    },
    {
      click: 'role=button:أطلق حملة',
      say: 'اضغط «أطلق حملة» — ثمانية أهداف تسويقية جاهزة',
    },
    {
      say: 'بانتظارك',
    },
    {
      chapter: 'الأهداف الستة الأساسية',
      hover: 'role=button:رجّع اللي غابوا',
      say: '«رجّع اللي غابوا»: يعمل وحده',
    },
    {
      say: 'وليس بعد عدد ثابت من الأيام',
    },
    {
      hover: 'role=button:رجّع اللي غابوا',
      say: 'بل بعد ضعف ونص دورة العميل نفسه',
    },
    {
      say: 'منطق مخصص لكل عميل',
    },
    {
      hover: 'role=button:رجّع اللي غابوا',
      say: 'كل عميل بدورته هو — لا دورة واحدة تُفرض على الكل',
    },
    {
      hover: 'role=button:رجّع اللي غابوا',
      say: 'اللي يجيك كل أسبوع يُعتبر غايباً أسرع من غيره',
    },
    {
      say: 'تلقائياً',
    },
    {
      hover: 'role=button:كافئ المخلصين',
      say: '«كافئ المخلصين»: يستهدف أكثرهم زيارة',
    },
    {
      say: 'خلال فترة معيّنة',
    },
    {
      hover: 'role=button:كافئ المخلصين',
      say: 'وليس الأقدم عندك من حيث التاريخ — الأنشط زيارة',
    },
    {
      say: 'فعلياً',
    },
    {
      hover: 'role=button:أعلن جديدك',
      say: '«أعلن جديدك»: يوصل كل من وافق على التواصل',
    },
    {
      say: 'التسويقي',
    },
    {
      hover: 'role=button:أعلن جديدك',
      say: 'على مستوى محلك كله — لا فرع واحد فقط',
    },
    {
      hover: 'role=button:أعلن جديدك',
      say: 'إلا لو اخترت فرعاً معيناً بنفسك عند الإطلاق',
    },
    {
      hover: 'role=button:هنّئ في مناسبة',
      say: '«هنّئ في مناسبة»: أنت تحدد اليوم بنفسك',
    },
    {
      say: 'تخرج صباحه',
    },
    {
      hover: 'role=button:وعِّ عملاءك',
      say: '«وعِّ عملاءك»: نصيحة ذكية تخص فقط من أخذوا',
    },
    {
      say: 'هذي الخدمة',
    },
    {
      hover: 'role=button:وعِّ عملاءك',
      say: 'تصله مرة واحدة، ثم تُقفَل تلقائياً شهراً كاملاً',
    },
    {
      chapter: 'وهدفان إضافيان لكل احتياج',
      hover: 'role=button:نصيحة موسمية',
      say: 'و«نصيحة موسمية» و«نبّه عن خطر»',
    },
    {
      say: 'نفس الذكاء بتوقيت مختلف',
    },
    {
      say: 'لمناسبة الموسم، أو لاستدعاء عيب حقيقي بخدمة',
    },
    {
      hover: 'role=button:عرض على خدمة',
      say: '«عرض على خدمة»: يوصل فقط لمن قارب موعد',
    },
    {
      say: 'هذي الخدمة',
    },
    {
      hover: 'role=button:عرض على خدمة',
      say: 'ومن أخذها قريباً يُستثنى تلقائياً من العرض',
    },
    {
      say: 'دقة كاملة',
    },
    {
      say: 'كل بطاقة اليوم مقفلة مؤقتاً لأن قوالبها عند واتساب',
    },
    {
      say: 'للمراجعة',
    },
    {
      say: 'تفتح وحدها تلقائياً بلا أي إجراء منك',
    },
    {
      say: 'أول ما تُعتمد',
    },
    {
      chapter: 'قبل ما تطلق — أربع أسئلة تجاوبها',
      hover: 'role=button:رجّع اللي غابوا',
      say: 'وقبل أي إطلاق، المنصّة تعلّمك تفكّر بذكاء',
    },
    {
      say: 'بأربع أسئلة',
    },
    {
      say: 'أول سؤال: لماذا تطلقها الآن؟',
    },
    {
      say: 'اختر الهدف المناسب لا المناسبة',
    },
    {
      hover: 'role=button:أعلن جديدك',
      say: '«أعلن جديدك» وحده يوصل الكل بلا أي شرط',
    },
    {
      say: 'خصصه لخبر حقيقي يهم الجميع',
    },
    {
      say: 'عرض أسبوعي عادي فيه يحرقه',
    },
    {
      say: 'تصير كل رسالة عادية «إعلان»، وتفقد قيمته الحقيقية',
    },
    {
      hover: 'role=button:عرض على خدمة',
      say: 'عرضك على خدمة واحدة؟',
    },
    {
      say: 'استخدم «عرض على خدمة» تحديداً',
    },
    {
      hover: 'role=button:هنّئ في مناسبة',
      say: 'مناسبة بتاريخ معروف؟ «هنّئ في مناسبة» يحدد يومها',
    },
    {
      say: 'ويخرج صباحه',
    },
    {
      chapter: 'الجمهور — قرار المنصّة، لا قرارك',
      say: 'ثاني سؤال: من يصله؟',
    },
    {
      say: 'وهذا يقرره الهدف نفسه، لا أنت',
    },
    {
      say: 'كل هدف عنده شرطه الذكي',
    },
    {
      say: 'بعضهم يستثني من أخذها قريباً تلقائياً',
    },
    {
      say: 'وكل حملة تبدأ على مستوى محلك كله، بكل فروعه',
    },
    {
      say: 'فرع واحد فقط، لو اخترته أنت بنفسك عند الإطلاق',
    },
    {
      // NOT A CLICK. Every goal on this tenant is still template-locked (`available: false`),
      // so a click here just times out on a disabled button — hover marks the card safely.
      chapter: 'رسالة جيدة مقابل رسالة ضعيفة',
      hover: 'role=button:أعلن جديدك',
      say: 'ثالث سؤال: ماذا تكتب؟',
    },
    {
      say: 'سطرك الحر محدود بستين حرفاً بدقة',
    },
    {
      say: 'ضعيفة: «عروض جميلة عندنا، زورونا»',
    },
    {
      say: 'بلا فعل ولا سبب واضح',
    },
    {
      say: 'جيدة: «افتتحنا فرعاً بحي الياسمين»',
    },
    {
      say: 'خبر محدد، فعل واحد',
    },
    {
      say: 'والخصم والتاريخ رقم وتاريخ منفصلان',
    },
    {
      say: 'تتحقق منهما المنصّة قبل الإرسال',
    },
    {
      chapter: 'التوقيت والسقف — حماية تلقائية لسمعتك',
      click: 'role=radio:متى نرسل',
      say: 'رابع سؤال: أي وقت؟ نرجع لـ«متى نرسل» نتأكد',
    },
    {
      say: 'رسائلك التسويقية تحترم نافذة هدوء الليل',
    },
    {
      say: 'تلقائياً',
    },
    {
      say: 'من عشرة مساءً لسبعة صباحاً',
    },
    {
      say: 'ما ترسل رسالة تسويقية مهما ضغطت',
    },
    {
      say: 'وسقف واتساب اليومي يشاركه كل شيء يرسله محلك',
    },
    {
      say: 'الحملة وغيرها — سقف واحد للكل',
    },
    {
      say: 'اسأل نفسك هذي الأربعة',
    },
    {
      say: 'وحملتك التسويقية توصل بدقة وذكاء',
    },
  ],
};
