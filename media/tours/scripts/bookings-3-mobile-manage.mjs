/**
 * «الحجوزات» — PART 3 OF 3: a phone again, and this time nothing is being read or created — an
 * appointment that already exists is being MANAGED. The three clips together are one tab:
 *
 *   1 — a phone: the list, the grid, day/week, working hours, filters.
 *   2 — a desktop browser: the whole board, a real drag-and-drop reschedule, the booking flow.
 *   3 (this file) — a phone: the action sheet, editing, the phone lookup, and the reschedule
 *       gesture that exists ONLY on touch — a long press, then a tap on the destination.
 *
 * THE GESTURE HERE IS NOT CLIP 2'S GESTURE. That one was HTML5 drag-and-drop
 * (`dragstart`/`dragover`/`drop`), which is a mouse's way of moving a card and does not exist on a
 * finger. Bookings.tsx answers touch with something else entirely: `onCardPointerDown` arms a
 * timer only when `e.pointerType === 'touch'`, and a hold that survives 450ms
 * (Bookings.tsx:568) opens «move mode» — a banner, then ONE tap on the destination quarter-hour,
 * which is what `commitMove` is called from (Bookings.tsx:1047). A drag on a touch screen fights
 * the page's own scrolling, which is why the screen was built this way; this clip films that path
 * and no other. record-tour.mjs's `longPress` step is the only thing that reaches it — a `.tap()`
 * is far too fast to arm the timer and a `.click()` arrives as pointerType "mouse", which the
 * screen ignores by design.
 *
 * THE GRID IS OPENED BY HAND HERE, UNLIKE CLIP 1 — and it has to be. A phone opens on the LIST
 * (`matchMedia('(pointer: coarse)')`, read once at mount), and the touch move lives on grid CARDS
 * only: a list row has no `onPointerDown` at all, because a flat list has no time axis to move a
 * booking along. So «عرض الشبكة» is a real step of this clip, not a workaround.
 *
 * SELECTORS READ OFF THE LIVE PAGE AT 430×932, never off the source:
 *   · «حضر» IS A PREFIX OF «لم يحضر» — exact matching, as in clip 2.
 *   · THE PHONE FIELD EXISTS TWICE. The `hidden sm:flex` desktop row is display:none at this
 *     width, but `getByLabel` still matches its input and it comes first in DOM order, so the
 *     phone panel's own copy is reached by a css selector scoped to the panel (clip 1's finding).
 *   · A BOOKED LIST ROW is matched by its own status pill (`محجوز`), not by position: the action
 *     sheet only offers تعديل/حضر/لم يحضر/إلغاء while the booking is still «محجوز», and the first
 *     row of a real day is as likely to be one already closed out.
 *   · THE CARD AND ITS DESTINATION ARE SEEDED AS A PAIR, not found by luck. seed-demo-account.mjs
 *     keeps the last ninety minutes of موظفة الاستقبال's day clear and puts one thirty-minute «قص
 *     شعر» at the head of it, so the clip always has a card that is still «محجوز» (a passed one is
 *     `draggable="false"` and cannot be moved at all — found by recording, not by reading) with a
 *     real empty hour behind it. The card is matched by BOTH its time and its service, because
 *     another column holds an 8:30 م card too; the destination cell is named by its own hover-time
 *     pill and its column index. Column order is DOM order and the page is RTL, so `nth=2` is the
 *     LEFTMOST column (موظفة الاستقبال) — the same rule clip 2 established.
 *
 * AND THE MOVE IS UNDONE ON CAMERA. «تراجع» is a real part of this act (a five-second bar, never
 * a confirm dialog), so pressing it teaches the undo AND leaves the demo board exactly as it was
 * — this clip can be re-recorded any number of times without walking the same booking further
 * down the day each run.
 */
export default {
  id: 'bookings-3-mobile-manage',
  title: 'الحجوزات ٣ — تدير موعدك من جوالك',
  section: 'الحجوزات',
  useDemoSession: true,
  preload: true,
  secondsCap: 360,
  steps: [
    // ── ورقة الموعد ──────────────────────────────────────────────────────────────────────────
    {
      goto: '/bookings',
      chapter: 'ورقة الموعد',
      say: 'موعد قائم عندك؟ من هنا تديره كله',
    },
    { waitFor: 'testid=rj-list' },
    {
      click: 'css=[data-testid="rj-list"] tr[role="button"]:has(span:text-is("محجوز"))',
      say: 'اضغط أي موعد «محجوز» من قائمتك',
    },
    { waitFor: 'role=button:تعديل الحجز' },
    {
      // THE CAPTION MOVES TO THE TOP FOR THE WHOLE SHEET. This sheet rises from the bottom edge of
      // the phone — the exact strip the caption bar occupies — so every one of these three lines
      // was printed over the details it was describing, leaving a dark box on a grey scrim (seen
      // frame-by-frame). Above, the scrim is empty and the sheet reads in full underneath.
      captionTop: true,
      say: 'تطلع ورقته: خدمته ووقته ومدته وموظفته',
    },
    {
      hover: 'role=button:حضر!',
      captionTop: true,
      say: '«حضر» تسجّل زيارته زيارةً حقيقية',
    },
    {
      // EXACT, LIKE «حضر» BESIDE IT — and for a second reason of its own: «لم يحضر» is also the
      // STATUS PILL a closed list row carries, and those rows sit earlier in the DOM than the
      // sheet floating over them. Without `!` the ring was drawn around a table row hidden behind
      // the scrim, off the top of the frame (a real frame from the first take).
      hover: 'role=button:لم يحضر!',
      captionTop: true,
      say: 'و«لم يحضر» و«إلغاء» يقفلانه بلا زيارة',
    },
    // ── عدّل موعده ───────────────────────────────────────────────────────────────────────────
    {
      click: 'role=button:تعديل الحجز',
      chapter: 'عدّل موعده',
      say: 'و«تعديل» يفتح نفس شاشة الحجز على موعده',
    },
    {
      say: 'تغيّر خدمته أو وقته أو موظفته من هنا',
    },
    {
      type: 'label=ملاحظة (اختياري)',
      // OVER WHATEVER IS THERE — a re-recorded take must not stack its line on the last one's.
      replace: true,
      text: 'أكدت بالواتساب',
      say: 'واكتب ملاحظة تقرأها بكرة عند استقباله',
    },
    {
      click: 'role=button:حفظ التعديل',
      say: 'واحفظ — نفس الموعد يتعدّل، ما ينفتح ثانٍ',
    },
    { waitFor: 'text=حُفظ التعديل' },
    // ── ابحث بجواله ─────────────────────────────────────────────────────────────────────────
    {
      click: 'role=button:فلاتر',
      chapter: 'ابحث بجواله',
      say: 'وعميل واقف يسأل عن موعده؟ افتح «فلاتر»',
    },
    {
      // The panel's own field — the desktop copy is hidden but still matches getByLabel and comes
      // first in DOM order (clip 1's own note).
      type: 'css=div[class*="w-64"] input[aria-label="ابحث عن حجز عميل بجواله"]',
      text: '0555010101',
      say: 'واكتب جواله',
    },
    // THE SUGGESTION IS A ROUND TRIP, not a render — 180ms of debounce and a real request after it.
    { waitFor: 'role=button:عميلة العرض' },
    {
      click: 'role=button:عميلة العرض',
      say: 'واضغط اسمه أول ما يطلع',
    },
    // A DIFFERENT READ FROM THE BOARD'S — `bookings.for-customer`, every date and every branch.
    { waitFor: 'role=button:السابقة' },
    {
      say: 'وتطلع مواعيده القادمة كلها، أي يوم وأي فرع',
    },
    {
      click: 'role=button:السابقة',
      say: 'و«السابقة» سجلّه كله: مواعيده وزياراته',
    },
    {
      click: 'role=button:فلاتر',
      say: 'ولمّا تخلص، افتح «فلاتر» مرة ثانية',
    },
    {
      click: 'role=button:إلغاء!',
      say: 'وشيل بحثه، ترجع لوحتك مثل ما كانت',
    },
    {
      // THE SCRIM, FRAMED BY NOTHING — a `fixed inset-0` dismiss button; ringing it would draw the
      // frame around the whole viewport (clip 1's own finding).
      click: 'role=button:إغلاق الفلاتر',
      noFrame: true,
      say: 'واضغط برّا القائمة تسكّرها',
    },
    // ── انقل موعده بإصبعك ───────────────────────────────────────────────────────────────────
    {
      click: 'role=button:عرض الشبكة',
      chapter: 'انقل موعده بإصبعك',
      say: 'وللنقل، افتح الشبكة: الوقت ينزل من فوق لتحت',
    },
    { waitFor: 'testid=rj-grid' },
    {
      longPress: 'css=[data-testid="rj-grid"] div[draggable="true"]:has-text("8:30 م"):has-text("قص شعر")',
      say: 'امسك بطاقة الموعد بإصبعك، واستمر ضاغطاً',
    },
    {
      say: 'انفتح وضع النقل: «انقري على الخانة الجديدة»',
    },
    {
      click: 'css=[data-testid="rj-grid"] button:has(> span:text-is("9:30 م")) >> nth=2',
      // THE DESTINATION IS LOW ON THE SCREEN — the grid scrolled to it, and the caption bar sat
      // over the ring marking it.
      captionTop: true,
      say: 'وانقر الخانة اللي تبغى تنقله لها',
    },
    { waitFor: 'text=نُقل الموعد' },
    {
      // THE UNDO BAR LIVES FIVE SECONDS, AND THAT IS THE WHOLE STEP BUDGET HERE. A caption is held
      // for its own reading time BEFORE its click fires (roughly a second per fourteen Arabic
      // letters), so the explanatory sentence this press deserves would have outlived the button
      // it points at — the first take reached «تراجع» after it had already gone. The short line
      // gets the press in on time; the sentence it earned comes right after, over the result.
      click: 'role=button:تراجع',
      // THE UNDO BAR IS A BOTTOM BAR, and the caption bar covered it whole — button, ring and all.
      captionTop: true,
      say: 'غلطت؟ «تراجع»',
    },
    { waitFor: 'text=تراجعنا عن النقل' },
    {
      say: 'انتقل بضغطة، ورجع بضغطة — بلا نوافذ تأكيد',
    },
    {
      say: 'وكل هذا من جوالك وأنت واقف مع عميلك',
    },
  ],
};
