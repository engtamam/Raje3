/**
 * «رسائلي» — كيف تخطط لحملة ناجحة. The clip Tamam actually asked for: not which button does
 * what — messages-3 and messages-4 already cover that honestly — but the THINKING an owner needs
 * before he presses «أطلق حملة» at all. Every claim here is traceable to something real: a field
 * that exists on Launch.tsx, a rule read out of campaigns-service's core/audience.py, or a number
 * this project's own investigation confirmed live against this tenant's `campaigns.goals` and
 * `campaigns.list` (all eight goals still template-locked, zero campaigns launched yet — so this
 * teaches with the goal picker, the same one messages-4 already walked, never with an invented
 * "campaign in progress" this tenant does not have).
 *
 * REWRITTEN FROM ZERO — the first cut opened on ten-plus real seconds of the skeleton drawn by
 * Messages.tsx's own three loading gates (`isLoading(today)`, `isLoading(reasons)`,
 * `isLoading(schedule)`) because its `goto` step ran live inside the capture loop with no
 * `preload`. Frame-by-frame inspection of the recorded file (ffprobe + extracted frames) showed
 * the real screen — the Segmented tabs, the health card, the thirteen reasons — hadn't painted
 * until past twenty seconds into that particular run. record-tour.mjs already carries the fix for
 * exactly this (`preload: true`, see its own "the pre-roll" comment, and every بانتظار/services
 * clip already uses it) — it was simply never turned on here. It is now.
 *
 * AND THE OPENING BEAT ITSELF WAS WEAK EVEN AT ZERO LOAD TIME: the first two lines used to be
 * bare `say` steps with no selector at all, narrating over a screen with nothing new to look at.
 * The rewrite opens on the first real click (switching to «حملاتي») instead, so the very first
 * frame this clip owns is already an action, not a wait.
 *
 * FOUR LESSONS, EACH GROUNDED (unchanged from the first pass — this is a re-cut, not a re-think):
 *
 *   1. متى تُطلق. Every goal here answers a DIFFERENT "when" — win_back fires on its own once a
 *      customer passes 1.5× his own visit rhythm (audience.py's own multiplier and comment: late
 *      enough to be absence, early enough the shop is still who he thinks of); occasion only ever
 *      fires on a day the owner names; announce is for real news, because it is the one goal with
 *      no narrowing rule at all — audience.py's own comment: "the rule is deliberately empty,
 *      narrowing is the owner's job through a different goal". Firing it for an everyday offer
 *      spends the one goal built for genuinely wide news.
 *
 *   2. كيف تختار الجمهور. He never types a query — every goal decides who to reach FOR him, and
 *      the smart choice is picking the goal whose rule already matches his intent (service_offer
 *      for a specific service and nothing else, reward_loyal for the ones worth keeping happy).
 *      AND IT IS COMPANY-WIDE BY DEFAULT — Launch.tsx's own branch `<select>` only renders for a
 *      shop with more than one branch, and starts on «كل الفروع»; picking one branch is a
 *      deliberate narrowing he opts into, never the default a multi-branch owner has to notice.
 *
 *   3. رسالة جيدة مقابل رسالة ضعيفة. The FREE line (`ownerText`, 60 characters, and only where
 *      the goal's template actually has room for one — `hasBlank(picked, 'owner')`) is the one
 *      thing he writes; everything else is Meta's own approved wording plus typed values with a
 *      shape the form checks (a discount as a real number 1-99, an end date that cannot be
 *      omitted where the goal `offers`). A specific line fills that slot; a vague one wastes it.
 *
 *   4. التوقيت والسقف. TodayCard's own three numbers — sent today, waiting, retrying — and the
 *      WhatsApp daily ceiling beside them are real limits a campaign shares with every other
 *      message this shop sends; and ReasonRow's own `cls` comment names the quiet window
 *      (10pm–7am) a marketing message may not enter even if he asks it to.
 */
export default {
  id: 'messages-5-campaign-strategy',
  title: 'رسائلي 5 — كيف تخطط لحملة تسويقية ناجحة',
  section: 'رسائلي',
  useDemoSession: true,
  sfx: true,
  // THE SCREEN IS ALREADY DRAWN AT FRAME ZERO. Messages.tsx fires three independent reads before
  // it can show anything real (`reminders.today`, `reminders.reasons`, `reminders.list_schedule`
  // + `campaigns.list`) — without the pre-roll, this clip opened on a blank shell and a skeleton
  // card for as long as the slowest of those happened to take on the particular run being
  // recorded. See record-tour.mjs's own note on `preload`.
  preload: true,
  steps: [
    {
      goto: '/messages',
      chapter: 'قبل ما تطلق حملة',
      click: 'role=radio:حملاتي',
      say: 'قبل «أطلق حملة» — أربع أسئلة تجاوبها أول',
    },
    {
      click: 'role=button:أطلق حملة',
      say: 'أول سؤال: ليش تطلقها الحين؟',
    },
    {
      chapter: 'اختر الهدف المناسب لا المناسبة',
      hover: 'role=button:رجّع اللي غابوا',
      say: 'رجّع اللي غابوا يشتغل وحده — ما تطلقه أنت',
    },
    {
      hover: 'role=button:أعلن جديدك',
      say: 'أعلن جديدك وحده يوصل الكل بلا شرط',
    },
    {
      hover: 'role=button:أعلن جديدك',
      say: 'خصصه لخبر حقيقي يهم الجميع',
    },
    {
      hover: 'role=button:أعلن جديدك',
      say: 'عرض أسبوعي عادي فيه؟ يحرقه',
    },
    {
      hover: 'role=button:أعلن جديدك',
      say: 'تصير كل رسالة عادية «إعلان»',
    },
    {
      hover: 'role=button:عرض على خدمة',
      say: 'عرضك على خدمة وحدة؟ استخدم «عرض على خدمة»',
    },
    {
      hover: 'role=button:عرض على خدمة',
      say: 'يوصل لمن قارب موعدها فقط',
    },
    {
      hover: 'role=button:هنّئ في مناسبة',
      say: 'مناسبة بتاريخ معروف؟ «هنّئ في مناسبة»',
    },
    {
      hover: 'role=button:هنّئ في مناسبة',
      say: 'تحدد يومها وتخرج صباحه',
    },
    {
      chapter: 'الجمهور — على مستوى المحل كله',
      hover: 'role=button:رجّع اللي غابوا',
      say: 'ثاني سؤال: مين يوصله؟',
    },
    {
      hover: 'role=button:رجّع اللي غابوا',
      say: 'وهذا يقرره الهدف، لا أنت',
    },
    {
      say: 'كل هدف عنده شرطه — بعضهم يستثني من أخذها قريباً',
    },
    {
      say: 'وكل حملة تبدأ على مستوى المحل كله',
    },
    {
      say: 'بكل فروعه — فرع واحد لو اخترته أنت بنفسك',
    },
    {
      // NOT A CLICK. Every goal on this tenant is still template-locked (`available: false` —
      // confirmed live against `campaigns.goals`, same fact the header comment states), so a
      // click here just times out on a disabled button. A hover marks the same card without
      // depending on it being pressable.
      chapter: 'رسالة جيدة مقابل رسالة ضعيفة',
      hover: 'role=button:أعلن جديدك',
      say: 'ثالث سؤال: شو تكتب؟',
    },
    {
      say: 'سطرك الحر محدود بستين حرفاً',
    },
    {
      say: 'ضعيفة: «عروض حلوة عندنا، زورونا»',
    },
    {
      say: 'ما فيها فعل ولا سبب',
    },
    {
      say: 'جيدة: «افتتحنا فرعاً بحي الياسمين»',
    },
    {
      say: 'خبر محدد، فعل واحد',
    },
    {
      say: 'والخصم والتاريخ رقم وتاريخ منفصلين',
    },
    {
      say: 'يتحققان قبل الإرسال — ما تكتبهم كسطر',
    },
    {
      chapter: 'التوقيت والسقف اليومي',
      click: 'role=radio:متى نرسل',
      say: 'رابع سؤال: أي وقت؟',
    },
    {
      say: 'ارجع لـ«متى نرسل» — فيه رسائل تسويقية',
    },
    {
      say: 'تحترم نافذة هدوء الليل',
    },
    {
      say: 'من عشرة مساءً لسبعة صباحاً',
    },
    {
      say: 'ما ترسل رسالة تسويقية مهما ضغطت',
    },
    {
      say: 'وسقف واتساب اليومي يشاركه كل شي يرسله محلك',
    },
    {
      say: 'الحملة وغيرها — سقف واحد للكل',
    },
    {
      say: 'اسأل نفسك الأربعة، وحملتك توصل صح',
    },
  ],
};
