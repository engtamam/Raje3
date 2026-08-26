/**
 * «محلّي» — REDESIGNED, capability-marketing voice, per an explicit call: this screen is the
 * platform's FIRST marketing gate — the first thing a prospective owner sees, and the one screen
 * that has to convince him the subscription pays for itself. The previous cut narrated it as a
 * dry "learn to read your numbers" tutorial; this rewrite keeps every real selector and every real
 * fact, but reframes each one as a capability the platform gives him, in one continuous story —
 * same decision already made for تسجيل الزيارة/خدماتي ومنتجاتي/رسائلي/عملائي/نقاطي.
 *
 * ONE CLIP, FULL COVERAGE, UNCHANGED FROM THE ORIGINAL DECISION. Shop.tsx's IndicatorsPanel
 * renders well over a dozen real cards, not four — محلّي is dense enough that one long, complete
 * walkthrough beats several short ones a viewer has to find and watch in order. Order follows the
 * page's own DOM order top to bottom — never an invented sequence.
 *
 * SIMPLE LANGUAGE STAYS THE RULE, NOW IN SERVICE OF PERSUASION RATHER THAN EXPLANATION. The
 * original brief («صاحب المحل بسيط، ما يفهم في أمور زي كذا») still holds — the harder analytics
 * indicators (return rate, churn, holdout) are exactly the ones a non-technical owner glazes over.
 * Every caption translates the METRIC into the QUESTION it answers AND the reason having that
 * answer is worth paying for, in plain words — not the label Shop.tsx prints on screen (which this
 * tour still points at), and not a features list either.
 *
 * SELECTORS ARE text= MATCHES READ DIRECTLY FROM Shop.tsx's OWN JSX (never guessed), unchanged
 * from the version already verified live against the seeded demo account — this rewrite only
 * changes what is SAID, never what is clicked.
 *
 * BranchCompare/StaffCompare RENDER EVEN WHEN THIN — Shop.tsx's own comment: «always render …
 * لازم ما تجلس تخفي شي ابدا». The seeded demo account has one branch and one operator, so both
 * cards are expected to show live in their honest "needs a second one to compare" state — that
 * state IS the real product, narrated as a promise of what unlocks the moment he grows, not a gap.
 *
 * FIVE CHAPTERS, EACH WELL PAST YOUTUBE'S 10s-APART FLOOR — same five natural sections as before.
 */
export default {
  id: 'shop-dashboard',
  title: 'محلّي — كل قرار محلك، بأرقام حقيقية أمامك',
  section: 'محلّي', // nav.ts's own label — this is the index route, sections[0]
  useDemoSession: true,
  // ESSENTIAL HERE, NOT COSMETIC — root-caused live: this screen's own mount fires ~15 concurrent
  // reads (catalog, compliance, reminders.today, whatsapp.connect, insights.branches/dashboard/
  // associations/bundles, subscription.apps, staff.branches, field.customers.resolve×4...). A
  // debug run confirmed the exact same page loads cleanly in 2.5s with no capture loop running,
  // yet reliably failed (`تعذّر الوصول إلى المنصة` / `تعذّر قراءة المؤشرات`) when the recorder's
  // own 30fps screenshot loop ran concurrently with that mount — real contention, not a product
  // bug. `preload` performs this navigation and lets it fully settle BEFORE a single frame is
  // captured, which is exactly the scenario it exists for.
  preload: true,
  // NO SFX ON THIS TOUR, DELIBERATELY — every "click" step here spotlights a read-only number or
  // chart, never a real button a viewer could actually press. A click sound on something that
  // isn't clickable teaches the wrong lesson.
  sfx: false,
  secondsCap: 420,
  steps: [
    {
      goto: '/',
      chapter: 'أرقامك اليومية',
      say: 'ماذا لو عرفت بالضبط كل ما يحدث بمحلك، كل يوم؟',
    },
    {
      say: 'هذي شاشة «محلّي» — أول شيء تراه كل صباح',
    },
    { waitFor: 'text=رسائل خرجت اليوم', timeoutMs: 60_000 },
    {
      click: 'text=رسائل خرجت اليوم',
      say: 'أول رقم: كم رسالة وصلت عملاءك اليوم',
    },
    {
      say: 'بدون أي جهد منك',
    },
    {
      click: 'text=بانتظار الإرسال',
      say: 'وكم لا يزال بالطريق — يخرج تلقائيًا بوقته',
    },
    {
      // The IndicatorsPanel's own insights.dashboard read can lag a beat behind the today card
      // above it on a freshly seeded tenant — a defensive wait, not a fixed assumption.
      waitFor: 'text=نسبة عودة', timeoutMs: 90_000,
      click: 'text=نسبة عودة',
      say: 'ومن كل عميل جاءك، كم يرجع لك مرة أخرى؟',
    },
    {
      say: 'رقم كبير يعني عملاؤك راضون، ويرجعون من تلقاء أنفسهم',
    },
    {
      click: 'text=عملاء نشطون',
      say: 'وكم عميل تعامل معك فعلاً خلال المدة الأخيرة',
    },
    {
      click: 'text=دورة العودة',
      say: 'وكل كم يوم يرجع عميلك عادةً — إيقاعه الحقيقي',
    },
    {
      click: 'text=التسرّب',
      say: 'وهذا الأهم: عملاء تأخروا عن موعدهم المعتاد',
    },
    {
      say: 'ولو ما تواصلت معهم الآن، قد لا يرجعون أبداً',
    },
    {
      click: 'text=متابعتك الآن',
      chapter: 'عملاؤك يحتاجون منك خطوة',
      say: 'وهذي أسماؤهم بالضبط — لا مجرد نسبة مجردة',
    },
    {
      say: 'اضغط «أرسل رسالة رجوع» فتراسلهم بضغطة واحدة',
    },
    {
      click: 'text=زياراتك آخر',
      say: 'وهنا رسمة واضحة — زياراتك تزيد أم تنقص؟',
    },
    {
      click: 'text=عملاء جدد هذا الشهر',
      say: 'وأين عملاؤك حقيقة — جدد، أم عملاء يرجعون لك دائماً؟',
    },
    {
      click: 'text=أثر رسائلك',
      say: 'وهل رسائلك فعلاً ترجّع عملاء؟ هذا دليلك المباشر',
    },
    {
      // "text=أثر الرسائل" ONLY, NOT ", مقيساً" — HoldoutCard renders three real states with
      // three different sentences (off, still-measuring, ready), only one of which carries the
      // ", مقيساً" title at all. "أثر الرسائل" is the one substring common to all three — verified
      // live against the seeded demo account, which sits in the "off" state (Holdout.py's own
      // `holdout_off` reason) and shows the plain paragraph, no title. This selector keeps
      // working the day someone turns holdout measurement on for this account too.
      click: 'text=أثر الرسائل',
      say: 'تقارنها مباشرة بمن لم تصله رسالة أصلاً — مقارنة عادلة',
    },
    {
      click: 'text=خدمات لكل زيارة',
      chapter: 'خدماتك بالأرقام',
      say: 'وأنتقل الآن لخدماتك',
    },
    {
      say: 'كم خدمة يأخذ عميلك بالزيارة الواحدة',
    },
    {
      click: 'text=متوقّع الأسبوع الجاي',
      say: 'وكم زيارة متوقّعة الأسبوع القادم',
    },
    {
      say: 'تخطيط مسبق حقيقي',
    },
    {
      click: 'text=التزام الدورة الدورية',
      say: 'وكم عميل ملتزم يرجع بموعده المعتاد فعلاً',
    },
    {
      click: 'text=مقارنة الفروع',
      say: 'وأي فرع أنشط — لحظة يكون عندك أكثر من فرع',
    },
    {
      click: 'text=مقارنة الموظفين',
      say: 'وأي موظف يرجّع له العملاء أكثر من غيره',
    },
    {
      click: 'text=الأكثر طلبًا عندك',
      chapter: 'أوقاتك وفرصك',
      say: 'وخدماتك الأكثر طلبًا — يرتّبها المحرك لك تلقائيًا',
    },
    {
      click: 'text=خدمات ما تُطلب كثيرًا',
      say: 'وهذي الأقل طلباً — فرصتك تروّج لها أو تعيد تسعيرها',
    },
    {
      click: 'text=أكثر أوقاتك ازدحامًا',
      say: 'وأي يوم وساعة محلك فيها أكثر ازدحاماً بالضبط',
    },
    {
      click: 'text=خدماتك حسب يوم الأسبوع',
      say: 'وأي خدمة تُطلب أكثر بيوم معيّن من الأسبوع',
    },
    {
      click: 'text=فروعك حسب يوم الأسبوع',
      say: 'ولو عندك أكثر من فرع، نفس الدقة لكل فرع على حدة',
    },
    {
      click: 'text=عملاء ما جرّبوا كل اللي يناسبهم',
      say: 'وعملاء جرّبوا خدمة، وتنقصهم أخرى تناسبهم تماماً',
    },
    {
      click: 'text=الخطوة التالية',
      chapter: 'ماذا تفعل الآن؟',
      say: 'والمنصّة نفسها تقترح عليك أسهل خطوة تبدأ بها',
    },
    {
      click: 'text=آخر الزيارات',
      say: 'وأخيراً، إثبات حي: كل زيارة تُسجَّل فعلاً، لحظة بلحظة',
    },
    {
      say: 'هذي شاشة واحدة، تجمع كل ما تحتاج معرفته عن محلك',
    },
    {
      say: 'بلا جداول معقّدة، وبلا حساب يدوي واحد',
    },
  ],
};
