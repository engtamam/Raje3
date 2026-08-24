/**
 * «محلّي» — the merged اليوم+محلّي screen (Shop.tsx's own header comment confirms the merge;
 * there is no separate «اليوم» anymore, corrected live after first assuming otherwise).
 *
 * WHY SIMPLE LANGUAGE IS THE WHOLE POINT HERE, EXPLICITLY. Tamam's own brief: «صاحب المحل بسيط،
 * ما يفهم في أمور زي كذا» — the harder analytics indicators (return rate, churn, trend charts)
 * are exactly the ones a non-technical owner glazes over without ever using. Every caption below
 * translates the METRIC into the QUESTION it actually answers, in plain words, not the label
 * Shop.tsx prints on screen (which this tour still points at — the plain-language caption is a
 * translation OF it, not a replacement for reading it).
 *
 * WHY FOUR INDICATORS, NOT ALL FIFTEEN-PLUS ON THIS SCREEN. Shop.tsx's IndicatorsPanel renders a
 * long list (return rate, churn, active customers, 7-day trend, cycle adherence, next week
 * forecast, services per visit, message impact, branch/staff comparison, peak times, missed
 * opportunities...). Walking all of them contradicts the tour's own methodology (short, one
 * objective, no silent-narration marathon) and Tamam's own brief was to simplify, not enumerate.
 * The four chosen are the ones an owner actually needs day to day: is anyone coming back, who's
 * at risk of leaving, is the shop trending up or down, and what should I do about any of it —
 * the last one (النظام يقترح) is the product's OWN plain-language answer to the other three.
 *
 * SELECTORS ARE text= MATCHES CONFIRMED AGAINST A REAL RENDERED SCREENSHOT of the seeded demo
 * account (media/tours/seed-demo-account.mjs), not guessed from source alone — Shop.tsx's own
 * labels for these cards are read here from Shop.tsx directly AND cross-checked against what
 * actually rendered live.
 */
export default {
  id: 'shop-dashboard',
  title: 'محلّي — تقرأ مؤشراتك ببساطة',
  useDemoSession: true,
  // NO SFX ON THIS TOUR, DELIBERATELY — every "click" step here spotlights a read-only number
  // or chart, never a real button a viewer could actually press. A click sound on something that
  // isn't clickable teaches the wrong lesson (real feedback: "ما في ضغطات فعلية… الصوت غير
  // مناسب"). sfx stays opt-in per tour for exactly this reason — a screen that's genuinely all
  // reading, not doing, should sound like one.
  steps: [
    {
      goto: '/',
      chapter: 'أرقامك اليومية',
      say: 'هذي شاشة «محلّي» — أرقامك اليومية أولاً',
    },
    {
      click: 'text=رسائل خرجت اليوم',
      say: 'كم رسالة خرجت لعملائك اليوم',
    },
    {
      click: 'text=بانتظار الإرسال',
      say: 'وكم لسه بالطريق — تخرج تلقائيًا',
    },
    // NO CHAPTER MARK HERE — 9.0s after «أرقامك اليومية» at this tour's real length, under
    // YouTube's 10s floor (confirmed live, the same lesson as getting-started.mjs). The harder
    // indicators still start here in content, just without their own chapter stop.
    {
      click: 'text=نسبة عودة',
      say: 'من كل عميل جاك، كم يرجع لك تاني؟',
    },
    {
      say: 'رقم كبير = عملاؤك راضين ويرجعون وحدهم',
    },
    // NO CHAPTER MARK HERE — this and the previous section land too close together at this
    // tour's length for YouTube's 10s-minimum spacing (the same lesson from getting-started.mjs).
    {
      click: 'text=التسرّب',
      say: 'عملاء تأخروا عن وقتهم المعتاد',
    },
    {
      say: 'لو ما تواصلت معهم، ممكن ما يرجعون',
    },
    {
      click: 'text=زياراتك آخر',
      say: 'رسمة بسيطة — زياراتك تزيد ولا تنقص؟',
    },
    {
      click: 'text=الخطوة التالية',
      chapter: 'وش أسوي الحين؟',
      say: 'النظام نفسه يقترح عليك — أسهل مكان تبدأ منه',
    },
  ],
};
