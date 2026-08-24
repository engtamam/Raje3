/**
 * «محلّي» — the merged اليوم+محلّي screen (Shop.tsx's own header comment confirms the merge;
 * there is no separate «اليوم» anymore, corrected live after first assuming otherwise).
 *
 * PART 1 OF 2. Tamam's own review of the first cut («محلي ما غطى كل شي») was correct — Shop.tsx's
 * IndicatorsPanel renders well over a dozen real cards, not four. Splitting the FULL coverage into
 * two clips (this one: the top of the page, daily tiles through أثر الرسائل مقيساً; part 2 —
 * shop-dashboard-more.mjs — everything from خدمات لكل زيارة down to آخر الزيارات) keeps each clip
 * inside this project's own established pacing rather than one long silent-narration marathon,
 * while still walking every real card on the screen across the pair. Order here follows the page's
 * own DOM order top to bottom — never an invented sequence.
 *
 * WHY SIMPLE LANGUAGE IS THE WHOLE POINT HERE, EXPLICITLY. Tamam's own brief: «صاحب المحل بسيط،
 * ما يفهم في أمور زي كذا» — the harder analytics indicators (return rate, churn, holdout) are
 * exactly the ones a non-technical owner glazes over without ever using. Every caption below
 * translates the METRIC into the QUESTION it actually answers, in plain words, not the label
 * Shop.tsx prints on screen (which this tour still points at — the plain-language caption is a
 * translation OF it, not a replacement for reading it).
 *
 * SELECTORS ARE text= MATCHES READ DIRECTLY FROM Shop.tsx's OWN JSX (never guessed) — the h3/h2/
 * Tile label strings, quoted exactly as this file's IndicatorsPanel/SurroundingKpis/MessageFlow/
 * HoldoutCard/WeekPulse/NewVsReturning/AtRiskCard render them today — cross-checked live against
 * the seeded demo account (media/tours/seed-demo-account.mjs) before recording.
 */
export default {
  id: 'shop-dashboard',
  title: 'محلّي ١ — أرقامك اليومية وعملاؤك',
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
    {
      click: 'text=نسبة عودة',
      say: 'من كل عميل جاك، كم يرجع لك تاني؟',
    },
    {
      say: 'رقم كبير = عملاؤك راضين ويرجعون وحدهم',
    },
    {
      click: 'text=عملاء نشطون',
      say: 'كم عميل تعامل معك خلال المدة الأخيرة',
    },
    {
      click: 'text=دورة العودة',
      say: 'وكل كم يوم يرجع عميلك عادةً',
    },
    // NO CHAPTER MARK HERE — spacing under YouTube's 10s floor at this tour's real length
    // (the same lesson learned live in getting-started.mjs and the first cut of this tour).
    {
      click: 'text=التسرّب',
      say: 'عملاء تأخروا عن وقتهم المعتاد',
    },
    {
      say: 'لو ما تواصلت معهم، ممكن ما يرجعون',
    },
    {
      click: 'text=متابعتك الآن',
      chapter: 'عملاؤك يحتاجون منك خطوة',
      say: 'وهذي أسماؤهم بالضبط — مو مجرد نسبة',
    },
    {
      say: 'اضغط «أرسل رسالة رجوع» تراسلهم بضغطة',
    },
    {
      click: 'text=زياراتك آخر',
      say: 'رسمة بسيطة — زياراتك تزيد ولا تنقص؟',
    },
    {
      click: 'text=عملاء جدد هذا الشهر',
      say: 'وين عملاؤك — جداد ولا يرجعون لك؟',
    },
    {
      click: 'text=أثر رسائلك',
      say: 'رسائلك فعلاً ترجّع عملاء؟ هذا دليلك',
    },
    {
      // "text=أثر الرسائل" ONLY, NOT ", مقيساً" — HoldoutCard renders three real states with
      // three different sentences (off, still-measuring, ready), only one of which carries the
      // ", مقيساً" title at all. "أثر الرسائل" is the one substring common to all three — verified
      // live against the seeded demo account, which sits in the "off" state (Holdout.py's own
      // `holdout_off` reason) and shows the plain paragraph, no title. This selector keeps
      // working the day someone turns holdout measurement on for this account too.
      click: 'text=أثر الرسائل',
      say: 'ونقارنها بمن ما وصلته رسالة أصلاً — بالعدل',
    },
  ],
};
