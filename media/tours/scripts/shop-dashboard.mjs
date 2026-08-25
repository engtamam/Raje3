/**
 * «محلّي» — the merged اليوم+محلّي screen (Shop.tsx's own header comment confirms the merge;
 * there is no separate «اليوم» anymore, corrected live after first assuming otherwise).
 *
 * ONE CLIP, FULL COVERAGE. Tamam's own review of the first cut («محلي ما غطى كل شي») was
 * correct — Shop.tsx's IndicatorsPanel renders well over a dozen real cards, not four. This was
 * briefly split into two clips to stay inside this project's usual pacing, then merged back on
 * Tamam's explicit call («عادي مقطع طويل لهذا») — محلّي is the one screen dense enough that one
 * long, complete walkthrough beats two short ones a viewer has to find and watch in order. Order
 * follows the page's own DOM order top to bottom — never an invented sequence.
 *
 * WHY SIMPLE LANGUAGE IS THE WHOLE POINT HERE, EXPLICITLY. Tamam's own brief: «صاحب المحل بسيط،
 * ما يفهم في أمور زي كذا» — the harder analytics indicators (return rate, churn, holdout) are
 * exactly the ones a non-technical owner glazes over without ever using. Every caption below
 * translates the METRIC into the QUESTION it actually answers, in plain words, not the label
 * Shop.tsx prints on screen (which this tour still points at — the plain-language caption is a
 * translation OF it, not a replacement for reading it).
 *
 * SELECTORS ARE text= MATCHES READ DIRECTLY FROM Shop.tsx's OWN JSX (never guessed) — every h2/
 * h3/Tile label string, quoted exactly as IndicatorsPanel/SurroundingKpis/MessageFlow/
 * HoldoutCard/WeekPulse/NewVsReturning/AtRiskCard/BranchCompare/StaffCompare/ServicePopularity/
 * WeakServices/PeakHeatmap/EntityDayHeatmap/NextStepView/MissedOpportunities/RecentVisits render
 * them today — cross-checked live against the seeded demo account
 * (media/tours/seed-demo-account.mjs) before recording.
 *
 * BranchCompare/StaffCompare RENDER EVEN WHEN THIN — Shop.tsx's own comment: «always render …
 * لازم ما تجلس تخفي شي ابدا». The seeded demo account has one branch and one operator, so both
 * cards are expected to show live in their honest "needs a second one to compare" state, not
 * hidden — that state IS the real product, worth a caption of its own, not skipped as if it
 * were a recording gap.
 *
 * FIVE CHAPTERS, EACH WELL PAST YOUTUBE'S 10s-APART FLOOR — this tour is long enough now (~2
 * minutes) that spacing is no longer the tight constraint it was in the two-part cut; chapters
 * mark the same five natural sections the split used to be, just inside one continuous clip.
 */
export default {
  id: 'shop-dashboard',
  title: 'محلّي — كل مؤشراتك بالتفصيل',
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
      // CURIOSITY-STYLE OPENER, DELIBERATELY DIFFERENT FROM getting-started.mjs's HOOK-STYLE ONE
      // — Tamam's own note: intros shouldn't all use the same formula. A read-only "understand
      // your numbers" tour suits a genuine question about the viewer's own knowledge better than
      // a speed-promise hook (that style fits a task with a real finish line, which this isn't).
      say: 'تعرف تقرأ أرقام محلك صح؟ خلّك معايا',
    },
    {
      say: 'هذي شاشة «محلّي» — أرقامك اليومية أولاً',
    },
    {
      click: 'text=رسائل خرجت اليوم',
      say: 'أول شي، كم رسالة خرجت لعملائك اليوم',
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
      say: 'طيب، كم عميل تعامل معك خلال المدة الأخيرة',
    },
    {
      click: 'text=دورة العودة',
      say: 'وكل كم يوم يرجع عميلك عادةً',
    },
    {
      click: 'text=التسرّب',
      say: 'بس انتبه — عملاء تأخروا عن وقتهم المعتاد',
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
    {
      click: 'text=خدمات لكل زيارة',
      chapter: 'خدماتك بالأرقام',
      say: 'كم خدمة ياخذ العميل بالزيارة الوحدة عادةً',
    },
    {
      click: 'text=متوقّع الأسبوع الجاي',
      say: 'وكم زيارة متوقّعة الأسبوع الجاي',
    },
    {
      click: 'text=التزام الدورة الدورية',
      say: 'وكم عميل ملتزم يرجع بموعده المعتاد',
    },
    {
      click: 'text=مقارنة الفروع',
      say: 'أي فرع أنشط — لو عندك أكثر من فرع',
    },
    {
      click: 'text=مقارنة الموظفين',
      say: 'وأي موظف يرجّع له العملاء أكثر',
    },
    {
      click: 'text=الأكثر طلبًا عندك',
      chapter: 'أوقاتك وفرصك',
      say: 'خدماتك الأكثر طلبًا — رتّبها المحرك تلقائيًا',
    },
    {
      click: 'text=خدمات ما تُطلب كثيرًا',
      say: 'وهذي الأقل — روّج لها أو راجع سعرها',
    },
    {
      click: 'text=أكثر أوقاتك ازدحامًا',
      say: 'وطيب، أي يوم وساعة محلك أكثر زحمة',
    },
    {
      click: 'text=خدماتك حسب يوم الأسبوع',
      say: 'وأي خدمة تُطلب أكثر بيوم معيّن',
    },
    {
      click: 'text=فروعك حسب يوم الأسبوع',
      say: 'ولو عندك أكثر من فرع — نفس الفكرة لكل فرع',
    },
    {
      click: 'text=عملاء ما جرّبوا كل اللي يناسبهم',
      say: 'عملاء جرّبوا خدمة، وناقصهم أخرى تناسبهم',
    },
    {
      click: 'text=الخطوة التالية',
      chapter: 'وش أسوي الحين؟',
      say: 'النظام نفسه يقترح عليك — أسهل مكان تبدأ منه',
    },
    {
      click: 'text=آخر الزيارات',
      say: 'وآخر شي — إثبات إن كل زيارة فعلاً تُسجَّل',
    },
  ],
};
