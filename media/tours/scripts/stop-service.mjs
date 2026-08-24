/**
 * A first, small, VERIFIED tour — proof that the recorder actually works end to end before any
 * bigger tour is written against it.
 *
 * WHY THIS ONE FIRST. It has a real reverse action in the same screen (إيقاف ↔ تفعيل, both
 * already confirmed live by apps/console/e2e/services.spec.ts's own `getByRole('button', {name})`
 * queries — see media/tours/PLAN.md's catalog entry for §12 Services), it touches nothing
 * financial or irreversible, and it demonstrates a SILENT effect worth calling out on screen: the
 * service disappears from the Visit screen and its reminders go quiet, neither of which is
 * visible from this screen itself — exactly the class of action the catalog flagged as needing
 * an explicit caption rather than being left to speak for itself.
 *
 * Selectors here are role+name strings, not raw Playwright calls — see tours/lib/locate.mjs for
 * why. Nothing in this file is specific to HOW a browser is driven or HOW an overlay is drawn;
 * changing either only ever means editing record-tour.mjs, never a tour script.
 */
export default {
  id: 'stop-service',
  title: 'إيقاف خدمة وإعادة تفعيلها',
  steps: [
    // NAVIGATED, NOT LOADED — a `goto` step is a full page reload, which wipes the overlay
    // entirely until the new document re-installs it (Playwright's addInitScript re-fires, but
    // only once the new page has a <body> again). That gap is exactly the several seconds of
    // nothing-on-screen a real viewer flagged watching the first working recording. Real client-
    // side SPA navigation never reloads at all, so the overlay — and the ring/caption on it —
    // stays alive continuously. At this viewport (430×932, below AppShell.tsx's `md` breakpoint)
    // the nav lives in a drawer behind a hamburger button, not directly on screen; opening it is
    // itself the tour's first real beat, not a step to hide.
    {
      click: 'role=button:فتح القائمة',
      say: 'شاشة «خدماتي ومنتجاتي»',
    },
    {
      click: 'role=link:خدماتي ومنتجاتي',
    },
    // A goto step's own waitForLoadState('networkidle') used to give the destination screen's
    // async data fetch time to land before the next step acted on it — client-side navigation has
    // no equivalent free wait, so this names the actual thing the tour needs to exist before it
    // touches anything on the new screen.
    { waitFor: 'role=button:أضف خدمتك الأولى', timeoutMs: 30_000 },
    // A BRAND-NEW SHOP HAS NO SERVICES YET — confirmed live, not assumed: the starter catalogue
    // some shops seed in the background is soft-fail by design (door.spec.ts's own comment) and,
    // on the account this tour opens for itself, never arrives at all. Rather than wait on a
    // background process this tour has no control over, it creates one real service itself —
    // making the tour self-sufficient regardless of whether seeding ever runs. Selectors and
    // field names read directly from Services.tsx's own empty-state button and add-form.
    {
      click: 'role=button:أضف خدمتك الأولى',
      say: 'أول خدمة؟ اضغط «أضف خدمتك الأولى»',
    },
    {
      type: 'label=الاسم',
      text: 'قص شعر',
      say: 'اكتب اسمها — الباقي اختياري، يُملأ لاحقاً وقته',
    },
    {
      click: 'role=button:إضافة',
      say: 'اضغط «إضافة» — والباقي افتراضي',
    },
    {
      click: 'role=button:إيقاف',
      say: 'اضغط «إيقاف» — الخدمة تتوقف، ما تُحذف',
    },
    // ONE TWO-LINE CAPTION, NOT TWO SEQUENTIAL ONES — CAPTION.maxLines is 2 for exactly this: a
    // single thought that needs a beat longer than one line shouldn't cost a second full
    // read-and-hold cycle. Merging these two cut real, needless dead time between stop and
    // reactivate — the first thing a viewer flagged watching the actual recording.
    {
      say: 'اختفت من «تسجيل زيارة» — وتاريخها باقٍ',
    },
    // SHE MOVED, NOT DISAPPEARED — stopping a service takes it off the «المفعّلة» (active) tab
    // entirely and onto a separate «الموقوفة» (stopped) one, which only appears once at least one
    // service is stopped. Confirmed live at this exact viewport (430×932): the row's «تفعيل»
    // button is directly on screen once this tab is open, no row-expand step needed.
    {
      click: 'role=radio:الموقوفة',
      say: 'خدماتك الموقوفة تحت تبويب «الموقوفة»',
    },
    {
      click: 'role=button:تفعيل',
      say: 'حابب ترجعها؟ اضغط «تفعيل»',
    },
  ],
};
