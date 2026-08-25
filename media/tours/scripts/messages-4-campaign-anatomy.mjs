/**
 * «رسائلي» — PART 4, «حملاتي» IN FULL — the eight real goals, one by one, and what each one's
 * audience actually is under the hood. Read Messages.tsx, Launch.tsx and campaigns-service's
 * core/audience.py directly before writing a single selector — this project's own standing rule.
 *
 * WHY A FOURTH CLIP RATHER THAN RE-RECORDING THE THIRD. messages-3-campaigns.mjs already exists
 * and is honest about the one real constraint on this demo tenant: every goal's WhatsApp template
 * is still under Meta review (confirmed live, again, right before writing this — `campaigns.goals`
 * answers all eight with `available: false`), so no real launch can be performed or verified today.
 * That clip correctly stopped there. What it never had time to do — because the picker was the
 * whole story at three cards' depth — is walk EVERY goal and say what each one's audience actually
 * IS, which is real, verifiable, and does not require a single card to be clickable: it lives in
 * the server's own `line`/`behaviour`/`unavailable_reason` strings rendered on screen, backed by
 * this project's own reading of audience.py's `_matches()`.
 *
 * A REAL, LIVE CONSTRAINT CONFIRMED AGAIN: `campaigns.goals` on this tenant answers EIGHT goals,
 * not six — `seasonal_care` and `safety` joined the six Messages.tsx's own GOAL_TITLE map still
 * named (a real gap this same pass fixed in Messages.tsx, in its own commit). This clip is what
 * makes those two goals visible on screen at all, alongside the original six.
 *
 * WHY THE AUDIENCE RULE IS SAID IN WORDS AND NOT DEMONSTRATED WITH A REAL PREVIEW. `ask()` (the
 * "اعرض ما سيصل" button) only ever renders once a goal is `picked`, and every card here is
 * `disabled` — Launch.tsx's own `disabled={g.available === false}`, which Playwright cannot click
 * through any more than a real finger could. Saying what audience.py actually computes, sourced
 * from that file rather than guessed from the card's one-line summary, is the honest way to teach
 * it without pretending a locked card is not locked.
 */
export default {
  id: 'messages-4-campaign-anatomy',
  title: 'رسائلي 4 — تشريح حملاتي: الأهداف الثمانية وجمهور كل واحد',
  section: 'رسائلي',
  useDemoSession: true,
  sfx: true,
  steps: [
    {
      goto: '/messages',
      chapter: 'حملاتي',
      say: 'رجعنا لـ«حملاتي» — نفتح كل هدف ونشوف جمهوره',
    },
    {
      click: 'role=radio:حملاتي',
      say: 'حملاتي',
    },
    {
      click: 'role=button:أطلق حملة',
      say: 'اضغط «أطلق حملة» — قائمة الأهداف الثمانية',
    },
    {
      chapter: 'الأهداف الستة الأولى',
      hover: 'role=button:رجّع اللي غابوا',
      say: 'رجّع اللي غابوا: مو بعد عدد ثابت من الأيام',
    },
    {
      hover: 'role=button:رجّع اللي غابوا',
      say: 'بعد ضعف ونص دورة العميل نفسه',
    },
    {
      hover: 'role=button:رجّع اللي غابوا',
      say: 'كل عميل بدورته هو — لا دورة واحدة للكل',
    },
    {
      hover: 'role=button:رجّع اللي غابوا',
      say: 'اللي يجي كل أسبوع يُعتبر غايب أسرع من الآخر',
    },
    {
      hover: 'role=button:كافئ المخلصين',
      say: 'كافئ المخلصين: أكثرهم زيارة خلال فترة معيّنة',
    },
    {
      hover: 'role=button:كافئ المخلصين',
      say: 'مو الأقدم عندك — الأنشط زيارة',
    },
    {
      hover: 'role=button:أعلن جديدك',
      say: 'أعلن جديدك: يوصل كل من وافق على التسويق',
    },
    {
      hover: 'role=button:أعلن جديدك',
      say: 'على مستوى المحل كله — لا فرع واحد فقط',
    },
    {
      hover: 'role=button:أعلن جديدك',
      say: 'إلا لو اخترت فرعاً بنفسك عند الإطلاق',
    },
    {
      hover: 'role=button:هنّئ في مناسبة',
      say: 'هنّئ في مناسبة: أنت تحدد اليوم — يخرج صباحه',
    },
    {
      hover: 'role=button:وعِّ عملاءك',
      say: 'وعِّ عملاءك: نصيحة تخص اللي أخذوه',
    },
    {
      hover: 'role=button:وعِّ عملاءك',
      say: 'مرة وحدة، ثم تُقفَل شهراً',
    },
    {
      chapter: 'الأهداف المضافة، والمقفلة اليوم',
      hover: 'role=button:نصيحة موسمية',
      say: 'ونصيحة موسمية، ونبّه عن خطر — نفس الفكرة',
    },
    {
      say: 'لمناسبة الموسم، أو استدعاء عيب بخدمة',
    },
    {
      hover: 'role=button:عرض على خدمة',
      say: 'وعرض على خدمة: يوصل لمن قارب موعده',
    },
    {
      hover: 'role=button:عرض على خدمة',
      say: 'ومن أخذها قريباً يُستثنى من العرض',
    },
    {
      say: 'كل بطاقة مقفلة لأن قوالبها عند واتساب للمراجعة',
    },
    {
      say: 'تفتح وحدها بلا أي شي منك — أول ما تُعتمد',
    },
  ],
};
