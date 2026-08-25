/**
 * «الحجوزات» — PART 1 OF 3, the grid itself: day/week, list/grid layout, working hours, filters.
 * Read Bookings.tsx (all 1819 lines), BookingDialog.tsx and WorkingHoursDialog.tsx directly
 * before writing a single selector — this project's own standing rule, and this screen is the
 * densest one this project has covered yet: real time-of-day columns, drag-and-drop reschedule,
 * two full layouts (grid for desktop, list for a phone — the recorder's own 430×932 viewport
 * opens on LIST by default per Bookings.tsx's own `pointer: coarse` check, so this tour opens on
 * the list and switches to the grid deliberately, not by accident).
 *
 * THREE PARTS, BY THE SCREEN'S OWN NATURAL PHASES (same reasoning as messages-1/2/3, visit-1/2):
 * Part 1 (this file) is the board itself — what it shows and how you read it. Part 2 is making a
 * new booking (BookingDialog.tsx's own multi-step flow — service → staff → merged time picker →
 * confirm — dense enough to earn its own clip). Part 3 is managing an EXISTING booking — the
 * action sheet (attend/no-show/cancel/edit), dragging to reschedule, and a customer's own phone
 * lookup/history.
 *
 * EACH PART IS RECORDED, PRODUCED AND VERIFIED BEFORE THE NEXT IS WRITTEN.
 *
 * THE DEMO ACCOUNT'S REAL STATE, CONFIRMED NOT ASSUMED: seed-demo-account.mjs's own bookings
 * step seeds real bookings via the real API, so this account genuinely has rows on the board —
 * not an empty state. Working hours are read live, not assumed configured.
 */
export default {
  id: 'bookings-1-grid-basics',
  title: 'الحجوزات 1 — القائمة والشبكة',
  section: 'الحجوزات', // nav.ts's own label
  useDemoSession: true,
  steps: [
    {
      goto: '/bookings',
      chapter: 'قائمة حجوزاتك',
      say: 'هذي شاشة «الحجوزات» — كل مواعيدك بمكان واحد',
    },
    {
      say: 'على الجوال تفتح بقائمة — أسهل قراءة بشاشة صغيرة',
    },
    {
      say: 'كل صف فيه التاريخ والوقت والخدمة وحالتها',
    },
    {
      click: 'role=button:عرض الشبكة',
      chapter: 'شبكة الوقت',
      say: 'وفيه عرض ثاني — «عرض الشبكة»',
    },
    {
      say: 'كل موظف عموده، والوقت محوره',
    },
    {
      click: 'role=button:عرض القائمة',
      say: 'ورجّعناها قائمة — أوضح على الجوال',
    },
    {
      click: 'role=button:الأسبوع',
      say: 'اضغط «الأسبوع» تشوف أسبوعك كامل',
    },
    {
      click: 'role=button:اليوم',
      say: 'ورجعنا «اليوم» — الافتراضي',
    },
    {
      click: 'role=button:أوقات الدوام',
      chapter: 'أوقات دوامك وفلترتها',
      say: 'زر «أوقات الدوام» — دوام فروعك بمكان واحد',
    },
    {
      say: 'كل يوم له وقت فتح وإغلاق، أو تقفله كامل',
    },
    {
      // WorkingHoursDialog uses the @base-ui design-system Modal — checked live: its close
      // button carries aria-label="Close" (English), not "إغلاق". Recorded as it actually is.
      click: 'role=button:Close',
      say: 'وترجع من هنا',
    },
    {
      // AT THIS VIEWPORT (430×932, below Tailwind's `sm`), the desktop filter row is genuinely
      // `display:none` (Bookings.tsx's own `hidden sm:flex`) while an identical-looking mobile
      // panel (`sm:hidden`) sits right after it in the DOM — same role+name pairs exist twice.
      // Only «فلاتر» itself and the panel's own unique close button are safe to click here; the
      // controls INSIDE the panel are narrated, never clicked, to avoid resolving to the hidden
      // desktop copy by DOM order.
      click: 'role=button:فلاتر',
      say: 'وزر «فلاتر» يفتح لك بحث وتصفية',
    },
    {
      say: 'تقدر تدوّر بجوال عميل معيّن',
    },
    {
      say: 'أو تفلتر بخدمة معيّنة، أو بحالة الدفع',
    },
    {
      click: 'role=button:إغلاق الفلاتر',
      say: 'وتقفلها من هنا',
    },
  ],
};
