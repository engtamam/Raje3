/**
 * «رسائلي» — PART 3 OF 3, «حملاتي». Read Messages.tsx and Launch.tsx directly before writing a
 * single selector — this project's own standing rule (see messages-1-today-reasons.mjs's own
 * header for the full context: the backend study, the three-part split, the record→verify
 * discipline this file follows exactly).
 *
 * «حملاتي» is the one tab an owner deliberately PRESSES rather than watches happen automatically
 * — six real goals (win-back, reward loyal customers, announce, occasion, awareness, service
 * offer), each a real audience of real phone numbers once its template clears Meta's review.
 *
 * A REAL, LIVE CONSTRAINT THIS SCRIPT WAS BUILT AROUND, CONFIRMED NOT ASSUMED: a direct read of
 * `campaigns.goals` on this demo tenant, minutes before writing a single step, showed EVERY goal
 * with `available: false` — "قوالب … ما زالت قيد مراجعة واتساب — سترسل تلقائياً عند اعتمادها."
 * Every goal card is genuinely disabled right now (Launch.tsx: `disabled={g.available === false}`),
 * so the real "pick a goal → fill it in → preview who it reaches → launch" walkthrough cannot be
 * performed live on this account today. That is not a demo-account defect to work around — it is
 * the EXACT state a real shop sees in its first days on the platform, before Meta has approved its
 * message templates, and it is worth teaching honestly rather than faked with an unavailable goal
 * clicked anyway (which Launch.tsx's own `disabled` attribute would simply refuse).
 *
 * SO THIS CLIP TEACHES THE LOCKED STATE ITSELF — what «حملاتي» looks like on day one, why every
 * card says the same thing, and what an owner should expect once review clears (SlotColorRules
 * — the card starts working with no other action from him). The moment this demo tenant's
 * templates clear review, a FOLLOW-UP clip covering an actual launch is real, useful future work
 * — not written here, because it cannot be tested and verified today (this project's own rule:
 * never record what cannot be verified).
 *
 * NOTHING HERE EVER PRESSES A REAL LAUNCH, even hypothetically — every goal being locked makes
 * that moot today, but the same caution messages-1/2's own notes already establish (never send a
 * real WhatsApp campaign, never rely on marketing consent this demo account's customers were
 * never asked for) would have applied regardless.
 */
export default {
  id: 'messages-3-campaigns',
  title: 'رسائلي 3 — حملاتي',
  section: 'رسائلي', // nav.ts's own label
  useDemoSession: true,
  sfx: true, // real clicks (tab, launch button) — earns a click sound
  steps: [
    {
      goto: '/messages',
      chapter: 'حملاتي',
      say: 'وأخيرًا — تبويب «حملاتي»، اللي تبدأها أنت بنفسك',
    },
    {
      click: 'role=radio:حملاتي',
      say: 'اضغط تبويب «حملاتي»',
    },
    {
      say: 'هذي وحدها ما ترسل إلا لما تضغط أنت',
    },
    {
      click: 'role=button:أطلق حملة',
      say: 'اضغط «أطلق حملة» تشوف كل أهدافها الستة',
    },
    {
      say: 'ست أهداف جاهزة لك',
    },
    {
      say: 'أول أيامك، البطاقات مقفلة مؤقتًا',
    },
    {
      say: 'ما تسوي شي — تفتح وحدها لما تُعتمد',
    },
    {
      say: 'وبعدها تضغط البطاقة وتطلق حملتك مباشرة',
    },
  ],
};
