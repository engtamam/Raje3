/**
 * «الحجوزات» — PART 3 OF 3: managing a booking that already exists — the action sheet, filtering
 * by a customer's own phone, and dragging a card to reschedule (read Bookings.tsx in full before
 * writing a single selector, same standing rule as parts 1-2).
 *
 * THE TOUCH RESCHEDULE IS A DIFFERENT CODE PATH THAN DESKTOP DRAG, CONFIRMED READING THE SOURCE —
 * `draggable`/`onDragStart` is HTML5 drag-and-drop (desktop, mouse); `onCardPointerDown` is this
 * screen's own stand-in for touch: a card armed by a genuine ~450ms hold (`e.pointerType ===
 * 'touch'` AND the hold survives `cancelLongPress`'s own pointerup handler), then a single tap on
 * the destination cell. Neither Playwright's `.click()` (dispatches pointerType "mouse" even in a
 * touch-enabled context — the app explicitly ignores it) nor `.tap()` (touchstart→touchend almost
 * instantly, far short of 450ms) can exercise this — so record-tour.mjs gained a real `longPress`
 * step (manual pointerdown → wait → pointerup, pointerType forced to "touch") rather than this
 * tour narrating a feature it could not actually trigger.
 *
 * THE ACTION SHEET (`BookingActions`) IS THE SAME COMPONENT FROM BOTH ENTRY POINTS — a list row's
 * onClick and a grid card's onClick both just call `setOpenBooking(b)` (`BookingsList`'s own
 * header comment says so explicitly), so this tour opens it once, from the list (mobile's default
 * view), rather than demonstrating the same sheet twice.
 *
 * A CARD IS ACTUALLY MOVED BY THIS RECORDING — a real PATCH, same as every other real-write tour
 * in this project; the demo account is disposable. The destination is the grid's LAST time slot
 * of the day (`.border-s button:last-of-type`) specifically because it is the one cell least
 * likely to already hold one of the ~1-booking/day seeded rows — a deliberate choice, not an
 * arbitrary one, to avoid a silent conflict rejection recorded as if it were a success.
 */
export default {
  id: 'bookings-3-manage-existing',
  title: 'الحجوزات 3 — إدارة حجز موجود',
  section: 'الحجوزات',
  useDemoSession: true,
  steps: [
    {
      goto: '/bookings',
      chapter: 'افتح أي حجز',
      say: 'اضغط أي حجز بالقائمة تفتح تفاصيله',
    },
    {
      click: 'css=[data-testid="rj-list"] tr[role="button"]',
      say: 'تفاصيله، وأزرار أفعاله تحته مباشرة',
    },
    {
      say: 'تعديل، تسجيل حضور، عدم حضور، أو إلغاء',
    },
    {
      click: 'role=button:إغلاق',
      say: 'تقفلها من هنا',
    },
    {
      // PhoneLookup is rendered TWICE — a `hidden sm:flex` desktop copy first in the DOM, and a
      // `sm:hidden` mobile-only copy inside the «فلاتر» panel (same duplicate-instance shape
      // already documented in bookings-1-grid-basics.mjs's own header comment). At this
      // viewport `.first()` resolves to the HIDDEN desktop copy and the recorder itself refuses
      // to click it ("resolved to nothing visible") — caught live on this exact step. Every
      // selector below is scoped under `.sm\:hidden`, the mobile-only wrapper, to reach the
      // real visible one instead.
      chapter: 'دوّر بجوال العميل',
      click: 'role=button:فلاتر',
      say: 'زر «فلاتر» يفتح بحثاً بجوال العميل أيضاً',
    },
    {
      type: 'css=.sm\\:hidden input[placeholder="جوّال العميل"]',
      text: '0555010101',
      say: 'دوّر بجوال أي عميل تشوف حجوزاته هو',
    },
    {
      click: 'css=.sm\\:hidden [class*="top-11"] button:first-child',
      say: 'تختار من النتائج',
    },
    {
      say: 'وتتفلتر القائمة على حجوزاته فقط',
    },
    {
      click: 'css=.sm\\:hidden button[aria-label="إلغاء"]',
      say: 'وتلغي الفلتر من هنا',
    },
    {
      click: 'role=button:إغلاق الفلاتر',
      say: 'وتقفل لوحة الفلاتر',
    },
    {
      chapter: 'اسحب لتحريك حجز',
      click: 'role=button:عرض الشبكة',
      say: 'بعرض الشبكة تقدر تحرّك حجزاً بلمسة مطوّلة',
    },
    {
      longPress: 'css=.rj-card.cursor-grab',
      say: 'اضغط مطوّلاً على الحجز',
    },
    {
      say: 'ثم المس الخانة الجديدة',
    },
    {
      click: 'css=.border-s button:last-of-type',
      say: 'وينتقل لوقته الجديد فوراً',
    },
  ],
};
