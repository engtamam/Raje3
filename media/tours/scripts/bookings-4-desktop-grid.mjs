/**
 * «الحجوزات» — DESKTOP BONUS CLIP, not part 4 of the mobile 3-part series (parts 1-3 stay the
 * primary mobile experience per this project's own "الجوال هو الشاشة الحقيقية لعميلنا"
 * philosophy). Requested explicitly: the time-grid genuinely reads better wide — a real
 * time-of-day calendar with a column per staff member (day view) or per day (week view), both
 * squeezed to one narrow lane on a phone.
 *
 * `orientation: 'landscape'` (record-tour.mjs) drives two real, confirmed-in-source differences,
 * not just a wider screenshot:
 *   - `deviceViewport()` returns CONFIG.VIDEO's 1920×1080 instead of the mobile 430×932.
 *   - `hasTouch` becomes false (record-tour.mjs's own contextOpts: landscape is a real browser
 *     window, not a phone) — which flips Bookings.tsx's own `matchMedia('(pointer: coarse)')`
 *     mount-time check to FALSE, so the screen opens directly on the GRID layout, no toggle
 *     click needed. It also means the desktop toolbar (`hidden sm:flex`) is the one actually
 *     visible now — the mobile-only `sm:hidden` selectors bookings-1/3 needed do NOT apply here;
 *     using them here would hit the now-hidden copy instead, the same duplicate-instance bug in
 *     reverse.
 *
 * THE DEMO SHOP HAS ONE OPERATOR (seed-demo-account.mjs's own "operator ready" step) — day view
 * genuinely shows one column even at this width. Week view (seven day-columns) is where the
 * width earns its keep, so this clip leans on week view rather than pretending day view looks
 * different than it does on mobile with only one staff member seeded.
 */
export default {
  id: 'bookings-4-desktop-grid',
  title: 'الحجوزات — منظور الحاسوب',
  section: 'الحجوزات',
  orientation: 'landscape',
  useDemoSession: true,
  steps: [
    {
      goto: '/bookings',
      chapter: 'شبكة أوضح بعرض أوسع',
      say: 'وبشاشة الحاسوب، الحجوزات تفتح مباشرة بعرض الشبكة',
    },
    {
      say: 'وقت اليوم واضح، وكل تفاصيل الحجز على بطاقته',
    },
    {
      click: 'role=button:الأسبوع',
      say: 'وبعرض الأسبوع، سبعة أيام جنباً لجنب دفعة وحدة',
    },
    {
      say: 'قراءة أسبوعك الكامل بلمحة، بلا تمرير',
    },
    {
      click: 'role=button:اليوم',
      chapter: 'كل أدوات الفلترة أمامك',
      say: 'وأدوات الفلترة والبحث كلها ظاهرة مباشرة، بلا طيّها بقائمة',
    },
    {
      say: 'جوّال العميل، الخدمة، وحالة الدفع — بضغطة وحدة',
    },
  ],
};
