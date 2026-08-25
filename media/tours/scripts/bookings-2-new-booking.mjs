/**
 * «الحجوزات» — PART 2 OF 3: making a new booking, BookingDialog.tsx's own flow (read in full
 * before writing a single selector, same standing rule as part 1). Backend logic confirmed live,
 * not assumed: services/bookings/app/core/availability.py's `nearest_slot` searches a 14-day
 * horizon (the dialog's own "لا فتحة قريبة خلال أسبوعين" message matches it exactly), and
 * operations.py's `no_show_risk` computes a real ratio over a config-driven window (default: last
 * 5 CLOSED appointments, 60% threshold) — a number the staff member reads and decides on, never a
 * refusal the system imposes.
 *
 * THE ORDER THE DIALOG ITSELF ENFORCES, NARRATED IN THAT ORDER: customer (phone → resolve-or-
 * create) → services (the same ServiceGrid تبع «زيارة») → staff (eligibility-narrowed, "أي متاح"
 * default) → ONE merged time picker (tap a real free slot, not two raw fields) → confirm. Payment/
 * deposit/reward details stay folded unless something needs attention — narrated as a closing
 * beat, not forced open, since that is genuinely how most bookings are made here.
 *
 * THE DEMO'S HERO CUSTOMER (0555010101, seeded by seed-demo-account.mjs) IS USED ON PURPOSE — she
 * has real visit history, a real reward balance and a real live offer, so booking against her own
 * number shows the dialog's richest real state (badge, reward dropdown) instead of a bare new-
 * customer path. A booking IS actually created against the live demo account by this recording —
 * accepted, same as every other real-write tour in this project; the account is disposable.
 */
export default {
  id: 'bookings-2-new-booking',
  title: 'الحجوزات 2 — حجز جديد',
  section: 'الحجوزات',
  useDemoSession: true,
  steps: [
    {
      goto: '/bookings',
      chapter: 'ابدأ حجزاً جديداً',
      say: 'زر «+» يفتح حجزاً جديداً من أي مكان بالشاشة',
    },
    {
      click: 'role=button:حجز جديد',
      say: 'أول خطوة: جوّال العميل',
    },
    {
      type: 'label=جوّال العميل',
      text: '0555010101',
      say: 'نكتب رقمه — والنظام يدوّر بين عملائك',
    },
    {
      // The suggestion list is the same resolve-while-typing search the visit keypad uses;
      // no aria-label on the row itself, so it is targeted the same way the project's own
      // duplicate-selector fix in bookings-1 targeted controls without one: by its unique
      // container, not by name text a randomly-seeded demo shop can't guarantee.
      click: 'css=.flex.flex-col.gap-1 > button:first-child',
      say: 'عميل معروف عندك — يظهر اسمه فوراً',
    },
    {
      chapter: 'اختر الخدمة والموظف والوقت',
      // The hero customer's own real reward/offer are tied to «بروتين شعر» specifically
      // (seed-demo-account.mjs's HERO_SERVICE_NAME) — an arbitrary "first tile" would highlight
      // a service she has no history with, making the very next caption a false claim.
      click: 'role=button:بروتين شعر',
      say: 'اختر الخدمة من نفس شبكة «زيارة»',
    },
    {
      // Not "her rewards show on the tile itself" — 🏷/⭐ marks depend on live offer/redeemable
      // data this exact demo run may or may not have (the offer needs a separate in-cluster seed
      // step per seed-demo-account.mjs's own log); the reward dropdown further down IS guaranteed
      // whenever she has any balance, so the claim stays honest either way.
      say: 'وجوائزها تظهر لاحقاً — يعرض استبدالها عند التأكيد',
    },
    {
      say: 'ثم الموظف — «أي متاح» افتراضي',
    },
    {
      say: 'وفتحات وقت حقيقية فاضية، رقاقة تضغطها',
    },
    {
      click: 'css=.flex.flex-wrap.gap-2 > button:first-child',
      say: 'تضغط رقاقة، يتعبّى الوقت والموظف معاً',
    },
    {
      // text= collided with this very step's own caption bubble (same phrase, rendered as a real
      // page overlay) — css targets the <summary> itself, the only one in this dialog.
      click: 'css=summary',
      say: 'وتفاصيل الدفع مطويّة، تفتحها لو تحتاجها',
    },
    {
      say: 'سعر الحجز، وحالة الدفع، وحتى استبدال جائزتها',
    },
    {
      // text= collided with this very step's own caption bubble (same phrase, rendered as a real
      // page overlay) — css targets the <summary> itself, the only one in this dialog.
      click: 'css=summary',
      say: 'نقفلها ونكمل',
    },
    {
      chapter: 'تأكيد الحجز',
      click: 'role=button:احجز',
      say: 'وزر «احجز» يثبّته',
    },
    {
      say: 'ويظهر فوراً على شاشة حجوزاتك',
    },
  ],
};
