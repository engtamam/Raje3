/**
 * «الحجوزات» — PART 2 OF 3: the whole board on a desktop browser, and everything you actually DO
 * on it. The longest of the three on purpose: this is the layout a shop runs its day from, and
 * every act that only exists at this width lives here.
 *
 *   1 — a phone: the list, the grid, day/week, working hours, filters.
 *   2 (this file) — a desktop browser: the grid at full width, the fifteen-minute cell, a real
 *       drag-and-drop reschedule with its conflict warning, the whole new-booking flow, the phone
 *       lookup, the filters, editing an existing booking, and a real reward being spent at «حضر».
 *   3 — a phone again: managing a booking that already exists.
 *
 * LANDSCAPE MEANS A MOUSE, AND THE SCREEN KNOWS IT. Bookings.tsx reads
 * `matchMedia('(pointer: coarse)')` ONCE at mount to pick its default layout — a phone opens on
 * the list, a browser on the grid. record-tour.mjs leaves `hasTouch` false for an
 * `orientation: 'landscape'` tour precisely so that check answers the way a real desktop answers;
 * nothing here switches the layout by hand, because nothing should have to.
 *
 * THE FIFTEEN-MINUTE CELL IS NOT A ROUNDING, IT IS THE GRAIN OF THE WHOLE SCREEN.
 * `SNAP_MINUTES = 15` (Bookings.tsx:42) is what every drop snaps to, the grid draws exactly
 * `WINDOW_LEN / 15` clickable cells per column from it, and the server's own double-booking lock
 * buckets on the same fifteen minutes (services/bookings/app/core/availability.py's
 * `DEFAULT_GRANULARITY_MINUTES`). One number, three layers, so the clip says it once and plainly.
 *
 * THE DRAG IS THE REAL ONE. `dragFrom`/`dragOver`/`dragDrop` (record-tour.mjs) carry one real
 * `DataTransfer` through the screen's own `onDragStart`/`onDragOver`/`onDrop`, which is what makes
 * the live conflict colouring, the snapped arrival time on the preview, the optimistic move, the
 * real `PATCH /api/v1/bookings/{id}/reschedule` and the five-second undo bar all happen for real
 * on camera. Split into three steps rather than one so the clip can HOLD the card over an occupied
 * quarter-hour long enough to read why it went red.
 *
 * THE REWARD IS REALLY SPENT. 0555010101 («عميلة العرض») carries thousands of real points and a
 * real reward tied to a real service («قص شعر مجاناً», 300 نقطة — seed-demo-account.mjs). The
 * booking made on camera attaches it as INTENT only; the spend happens at «حضر», where
 * `BookingOperations.attend` calls operations' loyalty desk and clears `intended_reward_id`
 * (services/bookings/app/core/operations.py). Verified end to end against the live cluster before
 * this was scripted: a `-300 redeem` row lands in her ledger and the ⭐ leaves the card.
 *
 * SELECTORS READ OFF THE LIVE PAGE AT THIS EXACT VIEWPORT, never off the source. What that
 * settled here:
 *   · COLUMN ORDER IS DOM ORDER, NOT SCREEN ORDER. The page is RTL, so the first column in the
 *     markup is the RIGHTMOST one. `>> nth=0` is «أخصائية الأظافر», `nth=1` «أخصائية الشعر»,
 *     `nth=2` «موظفة الاستقبال» — confirmed by reading every header's real bounding box.
 *   · A QUARTER-HOUR CELL HAS NO ACCESSIBLE NAME. Its only text is a `hidden group-hover:block`
 *     time pill, so it is reached by that pill's exact text and the column index.
 *   · THE PHONE FILTER EXISTS ONCE HERE, unlike on a phone: the `sm:hidden` panel that duplicates
 *     it is not rendered at all until its chip is tapped, which never happens at this width.
 *   · «حضر» IS A PREFIX OF «لم يحضر», and «عربون» of «بدون عربون» — both need exact matching.
 */
export default {
  id: 'bookings-2-desktop-board',
  title: 'الحجوزات ٢ — لوحة المحل كاملة على الشاشة',
  section: 'الحجوزات',
  useDemoSession: true,
  orientation: 'landscape',
  preload: true,
  // EIGHT STATIONS DEEP, AND LONG BECAUSE THE SCREEN IS. The 180s default is a runaway detector
  // for a five-step clip, not a length this one could ever fit inside — see record-tour.mjs's own
  // note on `secondsCap`.
  secondsCap: 480,
  steps: [
    // ── لوحة يومك كاملة ─────────────────────────────────────────────────────────────────────
    {
      goto: '/bookings',
      chapter: 'لوحة يومك كاملة',
      say: 'على شاشة كبيرة تفتح الحجوزات شبكة — يومك كامل بضربة عين',
    },
    { waitFor: 'testid=rj-grid' },
    {
      hover: 'text=أخصائية الشعر',
      say: 'كل موظفة عمود، من فتح المحل إلى إغلاقه',
    },
    {
      say: 'والوقت ينزل من فوق لتحت، وكل بطاقة بمكان ساعتها الحقيقي',
    },
    {
      hover: 'css=[data-testid="rj-grid"] div[draggable="true"]:has-text("صبغة شعر كاملة")',
      say: 'وطول البطاقة هو طول الخدمة — ساعتان تاخذ ضعف الساعة الواحدة',
    },
    // ── الخانة ربع ساعة ─────────────────────────────────────────────────────────────────────
    {
      hover: 'css=[data-testid="rj-grid"] button:has(> span:text-is("5:30 م")) >> nth=1',
      chapter: 'الخانة ربع ساعة',
      say: 'مرّر على أي فراغ: يضيء ويقول وقته',
    },
    {
      say: 'كل خانة ربع ساعة بالضبط — وعليها يستوي كل حجز وكل نقل',
    },
    {
      // ALSO WHAT KEEPS THIS CHAPTER TEN SECONDS CLEAR OF THE NEXT ONE — YouTube drops a whole
      // chapter list when any two marks are closer than that, and a two-step station is not
      // reliably longer than that on its own.
      say: 'ونفس الربع ساعة هو اللي يمنع موعدين يتصادمون على موظفة وحدة',
    },
    // ── حجز جديد من نفس الخانة ──────────────────────────────────────────────────────────────
    {
      click: 'css=[data-testid="rj-grid"] button:has(> span:text-is("5:30 م")) >> nth=1',
      chapter: 'حجز جديد من نفس الخانة',
      say: 'واضغطها يفتح الحجز وقد عرف الموظفة والوقت',
    },
    {
      type: 'label=جوّال العميل',
      text: '0555010101',
      say: 'ابدأ بجوال العميلة',
    },
    // THE SUGGESTION IS A ROUND TRIP, NOT A RENDER. `waitForDomQuiet` goes quiet the instant
    // typing stops — 180ms of debounce and a real request still to come — and under the
    // capture loop's own load that answer can land after the next step has already given up
    // (it did, on the first take). Every asynchronous arrival in this clip is waited for by
    // name rather than by hoping the pacing covers it.
    { waitFor: 'role=button:عميلة العرض' },
    {
      click: 'role=button:عميلة العرض',
      say: 'تطلع من عملائك وأنت تكتب — اضغطها',
    },
    {
      hover: 'text=عميل معروف',
      say: 'عرفها، فما تحتاج تكتب اسمها من جديد',
    },
    {
      click: 'role=button:قص شعر',
      say: 'اختر الخدمة — و⭐ عليها معناها نقاطها تكفي مكافأة عليها',
    },
    // THE SLOT CHIPS ARE SEVERAL `nearest-slot` CALLS DEEP — one per round, sequentially.
    { waitFor: 'role=button:17:30' },
    {
      hover: 'label=الموظف',
      say: 'الموظفة جاهزة من الخانة اللي ضغطتها، وتقدر تغيّرها',
    },
    {
      click: 'role=button:17:30',
      say: 'والوقت رقاقات — كل رقاقة فتحة فاضية فعلاً عند هذي الموظفة',
    },
    {
      click: 'text=تفاصيل الدفع',
      say: 'وتحت «تفاصيل الدفع» سعر هذا الموعد وحالة دفعه',
    },
    { waitFor: 'role=radio:عربون!' },
    {
      // A RADIO, NOT A BUTTON — rj-ui/Segmented renders its options as `role="radio"` inside a
      // `role="radiogroup"`. Exact, because «بدون عربون» beside it contains this whole word.
      click: 'role=radio:عربون!',
      say: 'اطلب عربون لو تبغى تأكيد الموعد',
    },
    {
      type: 'label=مبلغ العربون (ريال)',
      text: '50',
      say: 'والمبلغ إجباري — عشان يبقى رقمٌ يُرجع له بعد شهر',
    },
    // HER BALANCE IS TWO CHAINED READS (by-phone → balance), so the reward picker mounts well
    // after the customer was chosen — and only if she can actually afford something.
    { waitFor: 'label=جائزة يريد استبدالها' },
    {
      select: 'label=جائزة يريد استبدالها (اختياري)',
      option: 'قص شعر مجاناً (300)',
      say: 'واختر جائزتها — تُصرف عند حضورها، لا الآن',
    },
    {
      click: 'role=button:احجز!',
      say: 'واحجز',
    },
    { waitFor: 'css=[data-testid="rj-grid"] div[draggable="true"]:has(span[title="جائزة بانتظار الاستبدال عند الحضور"])' },
    {
      say: 'وطلعت بطاقتها بمكان وقتها، وعليها «عربون 50» و⭐ الجائزة',
    },
    // ── انقل موعد بالسحب ────────────────────────────────────────────────────────────────────
    {
      dragFrom: 'css=[data-testid="rj-grid"] div[draggable="true"]:has(span[title="جائزة بانتظار الاستبدال عند الحضور"])',
      chapter: 'انقل موعد بالسحب',
      say: 'تأجّل الموعد؟ امسك البطاقة نفسها',
    },
    {
      dragOver: 'css=[data-testid="rj-grid"] button:has(> span:text-is("4:00 م")) >> nth=1',
      say: 'ومرّها على خانة عليها موعد',
    },
    {
      say: 'أحمر: متعارض — موظفة واحدة ما تاخذ موعدين بنفس الوقت',
    },
    {
      dragOver: 'css=[data-testid="rj-grid"] button:has(> span:text-is("6:00 م")) >> nth=2',
      say: 'ومرّها على فراغ، ولو عند موظفة ثانية',
    },
    {
      say: 'أخضر، ومكتوب عليه وقت وصولها بالضبط قبل ما ترميها',
    },
    {
      dragDrop: 'css=[data-testid="rj-grid"] button:has(> span:text-is("6:00 م")) >> nth=2',
      say: 'وارمها',
    },
    {
      say: 'انتقلت للموظفة الجديدة، و«تراجع» تحت يرجّعها لو غلطت',
    },
    // ── ابحث بجوال العميل ───────────────────────────────────────────────────────────────────
    {
      type: 'label=ابحث عن حجز عميل بجواله',
      text: '0555010101',
      chapter: 'ابحث بجوال العميل',
      say: 'عميلة واقفة عندك تسأل عن موعدها؟ اكتب جوالها',
    },
    { waitFor: 'role=button:عميلة العرض' },
    {
      click: 'role=button:عميلة العرض',
      say: 'اضغط اسمها',
    },
    // A DIFFERENT READ FROM THE GRID'S — `bookings.for-customer`, across every date and branch.
    { waitFor: 'role=button:السابقة' },
    {
      say: 'وتطلع مواعيدها القادمة كلها — أي يوم وأي فرع، مو يومك هذا',
    },
    {
      click: 'role=button:السابقة',
      say: 'و«السابقة» تجمع مواعيدها وزياراتها القديمة بصف واحد',
    },
    {
      click: 'role=button:إلغاء!',
      say: 'وتشيل بحثها فترجع لوحتك مثل ما كانت',
    },
    // ── الفلاتر ─────────────────────────────────────────────────────────────────────────────
    {
      click: 'role=button:الخدمة',
      chapter: 'الفلاتر',
      say: 'والفلاتر تضيّق اللوحة على خدمة بعينها',
    },
    { waitFor: 'css=[role="listbox"] input' },
    {
      type: 'css=[role="listbox"] input',
      text: 'مانيكير',
      say: 'وفيها بحث لو خدماتك كثيرة',
    },
    {
      click: 'role=option:مانيكير',
      say: 'اختر «مانيكير» — وتقدر تختار أكثر من وحدة',
    },
    {
      say: 'وما بقي على اللوحة إلا مواعيد هذي الخدمة',
    },
    {
      // «عربون», NOT «مدفوع» — the two filters COMBINE, so this one has to be a state the
      // already-narrowed board actually contains, or the chapter demonstrates its own
      // combination by emptying the screen (which is what «مدفوع» + «مانيكير» did).
      click: 'role=button:عربون!',
      say: 'وحالة الدفع فلتر ثانٍ يجتمع معه',
    },
    {
      click: 'role=button:إزالة كل الفلاتر',
      say: 'وضغطة وحدة تشيلها كلها',
    },
    // ── إدارة موعد قائم ─────────────────────────────────────────────────────────────────────
    {
      click: 'css=[data-testid="rj-grid"] div[draggable="true"]:has-text("صبغة شعر كاملة")',
      chapter: 'إدارة موعد قائم',
      say: 'واضغط أي بطاقة تفتح ورقتها',
    },
    { waitFor: 'role=button:تعديل الحجز' },
    {
      say: 'خدمتها ووقتها ومدتها وموظفتها وسعرها — قبل ما تقرر شي',
    },
    {
      hover: 'role=button:حضر!',
      say: '«حضر» تسجّل زيارتها فعلاً، و«لم يحضر» و«إلغاء» يقفلانه بلا زيارة',
    },
    {
      click: 'role=button:تعديل الحجز',
      say: 'و«تعديل» يفتح نفس شاشة الحجز على هذا الموعد',
    },
    {
      type: 'label=ملاحظة (اختياري)',
      // OVER WHATEVER IS THERE — this booking is a real row on a real demo shop, and a re-recorded
      // take must not stack its line on top of the last take's.
      replace: true,
      text: 'أكدت بالواتساب',
      say: 'غيّر خدمتها أو وقتها أو اكتب ملاحظة تقرأها بكرة',
    },
    {
      click: 'role=button:حفظ التعديل',
      say: 'واحفظ — نفس الموعد يتعدّل، ما ينفتح حجزٌ ثانٍ',
    },
    // ── المكافأة تُصرف عند الحضور ────────────────────────────────────────────────────────────
    {
      click: 'css=[data-testid="rj-grid"] div[draggable="true"]:has(span[title="جائزة بانتظار الاستبدال عند الحضور"])',
      chapter: 'المكافأة تُصرف عند الحضور',
      say: 'ونرجع لموعد عميلتنا صاحبة الجائزة',
    },
    {
      say: '⭐ معناها جائزة محجوزة لها، ونقاطها لسه ما انخصمت',
    },
    {
      click: 'role=button:حضر!',
      say: 'وأول ما تجي وتخلص، اضغط «حضر»',
    },
    // ATTEND IS THREE SERVICES DEEP — a real Visit through operations, then the loyalty spend.
    { waitFor: 'text=سُجّل الحضور' },
    {
      say: 'سُجّلت زيارتها، وانخصمت نقاط جائزتها بنفس اللحظة — لا قبلها',
    },
    {
      click: 'role=button:إغلاق!',
      say: 'ومن نفس المكان تحجز جلستها الجاية',
    },
    {
      say: 'وصارت بطاقتها «حضر»، والنجمة راحت: الجائزة انصرفت فعلاً',
    },
  ],
};
