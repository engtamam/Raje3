/**
 * «محلّي» — PART 2 OF 2 (see shop-dashboard.mjs's own header for why this is split in two).
 * Continues exactly where part 1 leaves off in Shop.tsx's own reading order: خدمات لكل زيارة
 * through آخر الزيارات, the bottom half of IndicatorsPanel.
 *
 * SELECTORS ARE text= MATCHES READ DIRECTLY FROM Shop.tsx's OWN JSX — Tile labels and h2/h3
 * headings (SurroundingKpis-style tiles, BranchCompare, StaffCompare, ServicePopularity,
 * WeakServices, PeakHeatmap, EntityDayHeatmap ×2, NextStepView's own «الخطوة التالية» Section,
 * MissedOpportunities, RecentVisits), quoted exactly as this file renders them today —
 * cross-checked live against the seeded demo account before recording.
 *
 * BranchCompare/StaffCompare RENDER EVEN WHEN THIN — Shop.tsx's own comment: «always render …
 * لازم ما تجلس تخفي شي ابدا». The seeded demo account has one branch and one operator, so both
 * cards are expected to show live in their honest "needs a second one to compare" state, not
 * hidden — that state IS the real product, worth a caption of its own, not skipped as if it
 * were a recording gap.
 */
export default {
  id: 'shop-dashboard-more',
  title: 'محلّي ٢ — خدماتك وفروعك وموظفيك',
  useDemoSession: true,
  // NO SFX — same reasoning as part 1: every step here spotlights a read-only card, never a
  // real button.
  steps: [
    {
      goto: '/',
      chapter: 'خدماتك بالأرقام',
      say: 'تكملة «محلّي» — خدماتك، فروعك، وموظفينك',
    },
    {
      click: 'text=خدمات لكل زيارة',
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
      say: 'أي يوم وساعة محلك أكثر زحمة',
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
