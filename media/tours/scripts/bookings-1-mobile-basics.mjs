/**
 * «الحجوزات» — PART 1 OF 3: the board on a phone. What the screen shows and how you read it,
 * before anything is created or changed on it.
 *
 * THREE CLIPS FOR ONE TAB, DELIBERATELY — tours/PLAN.md's own "one clip per tab" rule does not
 * survive this screen and was overridden for it directly. الحجوزات is not a tab with a few
 * controls: it is two full layouts (a list and a real time-of-day grid), two ranges (day and
 * week), a working-hours policy, filters, a whole booking dialog, drag-and-drop rescheduling and
 * an action sheet. One clip covering all of it is the "two clips nobody split yet" the plan's own
 * length note warns about.
 *   1 (this file) — a phone: the list, the grid, day/week, working hours, filters.
 *   2            — a desktop browser: the same board at full width, where the grid is the default.
 *   3            — a phone again: managing a booking that already exists.
 *
 * EVERY SELECTOR HERE WAS READ OFF THE LIVE PAGE, NOT OFF THE SOURCE. Two traps on this screen
 * specifically, both confirmed by querying the real DOM at this exact viewport:
 *
 *   «اليوم» IS AMBIGUOUS BY ROLE. The day/week toggle's button is named «اليوم», and so is every
 *   row of today's list — each row is a `<tr role="button">` whose accessible name STARTS with the
 *   word «اليوم» from its own date cell (13 matches on a normal day). Only an EXACT match
 *   (`role=button:اليوم!`) resolves the toggle rather than whichever row happens to come first.
 *
 *   THE FILTER CONTROLS EXIST TWICE. Bookings.tsx renders a `hidden sm:flex` desktop filter row
 *   and an `sm:hidden` mobile panel with the same names in both. At 430px the desktop copy is
 *   genuinely `display:none`, so it is out of the accessibility tree and `role=` queries never see
 *   it — verified live, not assumed. Its phone INPUT is a different matter: `getByLabel` DOES
 *   match a hidden input, and the hidden desktop one comes first in DOM order, so that one field
 *   is reached by a css selector scoped to the panel instead.
 *
 * «مدفوع» AND «عربون» ALSO NEED EXACT MATCHING — «بدون عربون» contains «عربون», and a card's own
 * paid pill reads «مدفوع 120».
 *
 * THE BOARD IT FILMS IS REAL. seed-demo-account.mjs's own `seedWeekBoard` lays a genuine working
 * week over the demo shop through the real API — three staff, their own specialities, real
 * deposits and real attendance. Nothing here depends on a card being at a particular minute.
 */
export default {
  id: 'bookings-1-mobile-basics',
  title: 'الحجوزات 1 — لوحة يومك على جوالك',
  section: 'الحجوزات', // nav.ts's own sidebar label — out/ groups every clip of a tab together
  useDemoSession: true,
  // THE BOARD IS ALREADY DRAWN AT FRAME ZERO. This screen fires four reads before it can render
  // anything, and without the pre-roll the clip opened on five and a half seconds of skeleton —
  // see record-tour.mjs's own note on `preload`.
  preload: true,
  steps: [
    // ── لوحة يومك ────────────────────────────────────────────────────────────────────────────
    {
      goto: '/bookings',
      chapter: 'لوحة يومك',
      say: 'كل مواعيد اليوم بمكان واحد',
    },
    {
      // THE LIST IS THE DEVICE'S OWN DEFAULT, NOT A CHOICE THIS SCRIPT MAKES — Bookings.tsx reads
      // `matchMedia('(pointer: coarse)')` once at mount and opens a touch device on the list. The
      // recorder sets `hasTouch` for a portrait tour precisely so that check answers the way a real
      // phone makes it answer; this waits for the answer rather than assuming it arrived.
      waitFor: 'testid=rj-list',
    },
    {
      say: 'على الجوال تفتح قائمة — أسهل قراءة بشاشة صغيرة',
    },
    {
      say: 'كل صف موعد: تاريخه ووقته وخدمته',
    },
    {
      // A HORIZONTAL SWIPE, and the reason record-tour.mjs learned to draw one: this header sits
      // ~285px outside the frame inside the table's own sideways scroll, and nothing on the Y axis
      // is wrong with it. Before, the ring was simply drawn off-screen.
      click: 'css=[data-testid="rj-list"] thead th:nth-child(6)',
      say: 'واسحب الجدول جنب: الموظفة والدفع والحالة',
      // A `click` on a table header does nothing at all — it is not a control. Used here only
      // because it is what makes the recorder scroll to it and frame it; the tap has no effect,
      // which is exactly what a viewer sees.
    },
    // ── شبكة الوقت ───────────────────────────────────────────────────────────────────────────
    {
      click: 'role=button:عرض الشبكة',
      chapter: 'شبكة الوقت',
      say: 'وهذي نفس المواعيد بشكل ثاني — الشبكة',
    },
    {
      say: 'كل موظفة عمود، والوقت ينزل من فوق لتحت',
    },
    {
      say: 'وكل بطاقة بمكان وقتها الحقيقي، بلونها',
    },
    {
      click: 'text=موظفة الاستقبال',
      say: 'واسحب جنب لبقية الموظفات',
    },
    {
      // ANTICIPATORY, NEVER PAST TENSE — a caption is shown BEFORE its own click fires (the ring
      // marks what is about to be pressed), so a line reading "we switched it back" sat over a
      // screen that had not switched yet. Every caption on a `click` step here says what the press
      // is for; the result gets its own caption-only step after it when it needs one.
      click: 'role=button:عرض القائمة',
      say: 'والقائمة أوضح على الجوال — نرجع لها',
    },
    // ── يومك أو أسبوعك ───────────────────────────────────────────────────────────────────────
    {
      click: 'role=button:الأسبوع',
      chapter: 'يومك أو أسبوعك',
      say: 'و«الأسبوع» يوريك أسبوعك كامل بصف واحد',
    },
    {
      // THE WEEK IS SEVEN SEPARATE READS — one per day — so the list genuinely unmounts and shows
      // «يُحمَّل الجدول…» for a beat after the switch. Without this wait the next caption described
      // a list that was not on screen yet (seen in the frame-by-frame review of the first take).
      waitFor: 'testid=rj-list',
    },
    {
      say: 'مرتّب بالأيام، كل يوم تحت عنوانه',
    },
    {
      // WHAT IS ACTUALLY ON SCREEN, NOT WHAT IS TRUE FURTHER DOWN IT. This line first read "your
      // own day is tinted among them" — true, and invisible: today's rows sit several screens
      // below the top of a week's list, so the caption described something the frame did not show.
      // The week range in the header is the fact this view is actually displaying right now.
      say: 'والعنوان فوق يقول أي أسبوع تشوف',
    },
    {
      click: 'role=button:اليوم!',
      say: 'وترجع ليومك بضغطة',
    },
    // ── أوقات دوامك ──────────────────────────────────────────────────────────────────────────
    {
      click: 'role=button:أوقات الدوام',
      chapter: 'أوقات دوامك',
      say: 'ومن هنا تضبط أوقات دوامك',
    },
    {
      say: 'كل يوم له فتح وإغلاق، أو تقفله كامل',
    },
    {
      say: 'وهي سياسة واحدة لكل فروعك',
    },
    {
      // WorkingHoursDialog uses the @base-ui design-system Modal, whose close button carries
      // aria-label="Close" (English) — checked live, recorded as it actually is.
      click: 'role=button:Close',
      say: 'وتطلع منها بلا حفظ لو ما غيّرت شي',
    },
    // ── الفلاتر ──────────────────────────────────────────────────────────────────────────────
    {
      click: 'role=button:فلاتر',
      chapter: 'الفلاتر',
      say: 'و«فلاتر» تضيّق اللوحة على اللي تدوّره',
    },
    {
      // The panel's own field — the desktop copy of this same input is hidden but still matches
      // getByLabel, and comes first in DOM order (see this file's header).
      click: 'css=div[class*="w-64"] input[aria-label="ابحث عن حجز عميل بجواله"]',
      say: 'عميل واقف عندك؟ اكتب جواله يطلع موعده',
    },
    {
      click: 'role=button:مدفوع!',
      say: 'أو رقّم على حالة الدفع — «مدفوع» مثلاً',
    },
    {
      say: 'واللوحة ضاقت على المدفوعة وحدها',
    },
    {
      click: 'role=button:الكل!',
      say: 'و«الكل» ترجّعها كلها',
    },
    {
      // THE SCRIM, FRAMED BY NOTHING. «إغلاق الفلاتر» is the panel's own full-screen
      // dismiss-on-tap-outside backdrop (`fixed inset-0`) — the honest element to click, and one
      // that must not be RINGED: the frame then spans the whole viewport and points at everything
      // at once. Clicking the «فلاتر» chip again would toggle the same state, but that scrim sits
      // over it and intercepts the press (Playwright refused it outright, which is exactly what a
      // real finger would hit too).
      click: 'role=button:إغلاق الفلاتر',
      noFrame: true,
      say: 'واضغط برّا القائمة تسكّرها',
    },
  ],
};
