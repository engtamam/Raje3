/**
 * «نقاطي» — PART 1 OF 2. Read Points.tsx directly (this project's own standing rule) before
 * writing a single selector — done in full: every KPI label, every aria-label, every real error
 * sentence quoted here comes from that file and from services/loyalty/app/core/{earn,earning,
 * rewards,redeem,models}.py, not from any summary or plan document (which is deprecated and was
 * not consulted for this content).
 *
 * TWO TABS ON ONE SCREEN, AND THIS CLIP WALKS BOTH READ-ONLY. Part 1 is «كيف تفهم برنامجك» — the
 * four KPIs, the rewards table as it already stands, and the earning tree exactly as it resolves
 * today (mode, general, groups, per-service). Part 2 (points-2-edit-and-edge-cases.mjs) is «كيف
 * تعدّله» — the same controls, but pressed: a new reward, a retired one, a changed rate, and the
 * real refusals the backend gives when a number is wrong.
 *
 * WHY THE KPI ROW OPENS THE CLIP, NOT THE REWARDS TABLE. Points.tsx's own module comment calls
 * «نقطة لم تُستبدل بعد» a debt already promised (§9.1), and its report.py source calls
 * `expired_share` "the one indicator that is a warning" — an owner who never opens this screen
 * has no other way to see either. Leading with what he owes is the honest opening for a loyalty
 * programme tour, not a KPI-dashboard habit.
 *
 * THE DEMO SHOP'S REAL STATE (verified against seed-demo-account.mjs's seedHeroCustomer, not
 * assumed): three real rewards — قهوة مجانية (100, هدية), قص شعر مجاناً (300, من خدماتي),
 * جلسة مجانية VIP (600, هدية) — and a manager-approval threshold of 500, so the VIP session is the
 * one reward on this shop that genuinely needs the manager badge/threshold explained. Every
 * service in the catalogue was seeded with ITS OWN points value (loyalty.settings.service called
 * per service), so «إعداد خاص» badges are the expected, real state of this shop's services list —
 * not a fabricated example.
 */
export default {
  id: 'points-1-programme-explained',
  title: 'نقاطي 1 — افهم برنامج نقاطك بالكامل',
  section: 'نقاطي', // nav.ts's own label
  useDemoSession: true,
  steps: [
    {
      goto: '/points',
      chapter: 'أرقام برنامجك',
      say: 'برنامج نقاطك يرجّع عملاءك — تعال أوريك كل تفصيلة فيه',
    },
    {
      click: 'text=عميل يجمع نقاطاً',
      say: 'أول رقم: كم عميل عندك يجمع نقاطاً الحين',
    },
    {
      click: 'text=استبدال',
      say: 'وكم مرة استُبدلت نقاط بمكافآت فعلاً',
    },
    {
      click: 'text=نقطة لم تُستبدل بعد',
      say: 'وهذا أهمهم: نقاط وعدت بها ولم تُصرف',
    },
    {
      say: 'التزامٌ عليك، لا رقم عادي',
    },
    {
      click: 'text=من كل نقطة مُنحت، انتهت بلا استبدال',
      say: 'ونسبة النقاط اللي انتهت بلا استبدال',
    },
    {
      say: 'نسبة عالية تعني إن مكافآتك بعيدة عن متناول عملائك',
    },
    {
      waitFor: 'text=أكثر ما يُستبدل',
      click: 'text=أكثر ما يُستبدل',
      say: 'وتحتها: أكثر المكافآت طلباً عند عملائك',
    },
    {
      click: 'text=جدول المكافآت',
      chapter: 'جدول المكافآت',
      say: 'هذا جدول مكافآتك — يوصل معبّأً، وتقدر تعدّله',
    },
    {
      click: 'text=قهوة مجانية',
      say: 'هذي أرخص مكافأة — أول شي يستبدله عميلك',
    },
    {
      click: 'text=قص شعر مجاناً',
      say: 'وهذي من خدماتك — مربوطة بخدمة حقيقية بكتالوجك',
    },
    {
      click: 'text=جلسة مجانية VIP',
      say: 'وهذي الأغلى — 600 نقطة',
    },
    {
      say: 'وسيوصلها بادج «باعتماد المدير»',
    },
    {
      say: 'لأنها فوق حد اعتماد ضبطته إنت بنفسك',
    },
    {
      // The Segmented options are «المكافآت» and «الكسب» — verified against Points.tsx's own
      // Segmented options array.
      click: 'role=button:الكسب',
      chapter: 'كيف تُكتسب النقاط',
      say: 'وهذا التبويب الثاني — «الكسب»',
    },
    {
      say: 'كيف يجمع عميلك النقاط أصلاً',
    },
    {
      click: 'text=طريقة الاحتساب',
      say: 'أول قرار: طريقة الاحتساب',
    },
    {
      say: 'ومفتاحٌ واحد — لا خانتا اختيار',
    },
    {
      say: 'بالخدمات: كل خدمة نقاطها الخاصة',
    },
    {
      say: 'بقيمة الفاتورة: نقطة عن كل ريال',
    },
    {
      say: 'ولا يجتمعان — لأخذ عميلك ضِعف النقاط عن نفس الزيارة',
    },
    {
      click: 'label=نقاط لكل زيارة (عام)',
      say: 'وهذا الرقم العام — لأي خدمة بلا رقم خاص',
    },
    {
      click: 'label=مكافأة تحتاج اعتماد المدير من',
      say: 'وهذا حد اعتماد المدير اللي ذكرته قبل شوي',
    },
    {
      say: 'أي مكافأة بهذي النقاط فأكثر تحتاج اسم مدير',
    },
    {
      say: '0 يعني بلا اعتماد — وهذا المحل ضبطه 500',
    },
    {
      waitFor: 'text=نقاط مجموعة',
      click: 'text=نقاط مجموعة',
      chapter: 'ثلاث طبقات: خدمة، مجموعة، عام',
      say: 'والمستوى الوسط: نقاط لكل مجموعة دفعة وحدة',
    },
    {
      say: 'مجموعاتك جاية من «خدماتي» مباشرة',
    },
    {
      click: 'text=نقاط خدمة بعينها',
      say: 'وآخر طبقة: رقمٌ خاص بخدمة وحدة',
    },
    {
      say: 'يتقدّم على المجموعة، والمجموعة على العام',
    },
    {
      say: 'بادج «إعداد خاص» يقول أي خدمة عندها رقمها',
    },
    {
      say: 'كل خدماتك هنا عندها رقم مخصّص فعلاً',
    },
    {
      say: 'كذا تفهم برنامجك كامل',
    },
    {
      say: 'وبالجزء الثاني نعدّل رقماً ونشوف رسائل الخطأ',
    },
  ],
};
