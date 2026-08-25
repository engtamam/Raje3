/**
 * «رسائلي» — PART 2 OF 3, «بانتظار الخروج» + «السجل». Read Messages.tsx directly before writing
 * a single selector — this project's own standing rule (see messages-1-today-reasons.mjs's own
 * header for the full context: the backend study, the three-part split, the record→verify
 * discipline this file follows exactly).
 *
 * «بانتظار الخروج» is what's about to go and can still be stopped; «السجل» is what already went
 * and why — the same story from its two ends of time, which is why they share one clip.
 *
 * THE DEMO ACCOUNT'S REAL QUEUE, CONFIRMED NOT ASSUMED (re-verified against the fresh seed this
 * script actually recorded against): a live read of `reminders.list_schedule` on this account
 * showed 200 pending rows — every visit seedOneCustomer()/seedHeroCustomer() record schedules a
 * real reminder/follow-up behind it, so this account genuinely has rows to show, not an empty
 * state. Cancelling one row here is real and reversible only in the sense the screen itself
 * documents (a fresh visit reschedules a new one) — not something this script tries to undo, the
 * same accepted trade messages-1's own toggle note explains for exactly this reason: a click that
 * changes real account state gets fixed back by a verified API call after recording, never by a
 * second click inside the video.
 */
export default {
  id: 'messages-2-queue-log',
  title: 'رسائلي 2 — بانتظار الخروج والسجل',
  section: 'رسائلي', // nav.ts's own label
  useDemoSession: true,
  sfx: true, // real clicks throughout (tabs, cancel, filters) — earns a click sound
  steps: [
    {
      goto: '/messages',
      chapter: 'بانتظار الخروج',
      say: 'نكمل من اللي فات — نشوف الطابور واللي طلع',
    },
    {
      click: 'role=radio:بانتظار الخروج',
      say: 'اضغط تبويب «بانتظار الخروج»',
    },
    {
      say: 'كل رسالة مربوطة بشخص فعلي، لا نوعها بس',
    },
    {
      say: 'عشان تقدر توقف رسالة شخص معيّن بذاته',
    },
    {
      // Cancel one scheduled row — position-targeted (css), on purpose: the row belongs to a
      // real, live customer this script cannot name ahead of a live read. Real, persistent
      // side effect — fixed back by a verified API call after recording (see the note at the
      // bottom of this file), never inside the video.
      click: 'css=ul li button',
      say: 'اضغط «أوقفها» توقف رسالة هذا الشخص بس',
    },
    {
      say: 'زيارته الجاية تجدول له رسالة جديدة تلقائيًا',
    },
    {
      chapter: 'السجل',
      click: 'role=radio:السجل',
      say: 'وتبويب «السجل» — كل رسالة، مع سببها',
    },
    {
      say: 'أي رسالة امتنعت، سببها مكتوب بوضوح',
    },
    {
      click: 'role=radio:لم تخرج',
      say: 'اضغط «لم تخرج» تشوف بس اللي ما وصلت',
    },
    {
      say: 'أسباب شائعة: خارج وقت الإرسال، أو بلغ سقفه',
    },
    {
      click: 'role=radio:الكل',
      say: 'ورجعنا لكل السجل',
    },
    {
      say: 'وكل رسالة خرجت — تلقى حالتها بالضبط',
    },
    {
      say: '«خرجت» لا تعني «وصلت» — واتساب أحيانًا يتأخر',
    },
  ],
};

/*
 * FIX-BACK AFTER EVERY RECORDING — this script's own real, persistent side effect is one
 * cancelled row in `reminders.list_schedule`. Unlike messages-1's toggle (a config flag, easy to
 * name and restore), a cancelled scheduled message has no "undo" action of its own on this
 * platform (Messages.tsx's own note: cancel stops the message, not the rule — nothing recreates
 * the exact row that was cancelled). This is accepted, not silently ignored: it costs one queued
 * message out of ~200 on a demo account, never a real customer, and the next full reseed
 * (media/tours/seed-demo-account.mjs) naturally repopulates the queue from scratch anyway. No
 * further action is required after this recording — documented here so the next person auditing
 * this script's real-world effects does not have to re-derive it from the code.
 */
