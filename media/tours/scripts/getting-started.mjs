/**
 * The overview tour — signup, the free trial, and a first glance at the shop. The one asked
 * for explicitly: "كيف يسوي حساب وفترة التجربة... يعني overview" — short, smart, the
 * moment a new owner actually lives through, not a feature tour.
 *
 * WHY THE SIGNUP ITSELF IS RECORDED, NOT SKIPPED. Every other tour uses `ensureSignedIn()`'s
 * silent signup — correct there, since those tours are about a SCREEN, and a viewer watching
 * "how do I stop a service" has no reason to sit through account creation first. This tour's own
 * subject IS that moment, so `skipAutoSignIn: true` leaves the door on screen as this tour's own
 * first frame — the door.spec.ts / e2e/fixtures.ts flow, this time actually on camera.
 *
 * WHY IT ENDS AT THE STORE, NOT A FULL TOUR OF EVERY TAB. The brief: mention a few things
 * generally and stop — "كل شي مفعل تجريبي" is the one fact worth landing on, not a full catalogue
 * walk (that's what the individual per-screen tours are for, once written).
 */
export default {
  id: 'getting-started',
  title: 'فتح حساب وفترة التجربة',
  // NOT ONE OF nav.ts's SECTIONS — signup happens before any sidebar tab exists to open, so it
  // gets its own top-level folder rather than being forced into a tab it isn't about.
  section: 'فتح حساب',
  skipAutoSignIn: true,
  sfx: true,
  steps: [
    {
      goto: '/',
      chapter: 'فتح الحساب',
      // HOOK-STYLE OPENER — a question, not a greeting. Capability-marketing voice throughout,
      // same decision already made for تسجيل الزيارة and خدماتي ومنتجاتي: the platform's own value,
      // not a dry click-by-click walkthrough — and every line picks up from the one before it.
      say: 'محلّك، على راجِع، بأقل من دقيقة — تعال أوريك',
    },
    {
      say: 'نفتح حساباً جديداً براجِع',
    },
    // Door.tsx defaults to «تسجيل الدخول» (sign in) — «تسجيل جديد» switches to the sign-up pane.
    // See e2e/fixtures.ts's openShop() for the fuller account of this exact control.
    {
      click: 'role=radio:تسجيل جديد',
      say: 'أول شي، اضغط «تسجيل جديد»',
    },
    {
      type: 'label=رقم الجوال',
      // A FRESH NUMBER EVERY RUN — the real backend refuses a second signup on one already
      // registered, so a fixed string here would make this tour un-recordable a second time.
      // Same shape e2e/fixtures.ts's own newPhone() uses: 05 then eight digits.
      text: () => `05${Math.floor(Math.random() * 90_000_000) + 10_000_000}`,
      say: 'رقم جوالك — هو نفسه دخولك لاحقاً، بلا إيميل ولا تعقيد',
    },
    // BY ROLE, NOT BY LABEL — see e2e/fixtures.ts's openShop() for why: the password field's
    // show/hide toggle button's own aria-label also contains «كلمة المرور».
    {
      type: 'role=textbox:كلمة المرور',
      text: 'Kobo2026$Demo',
      say: 'كلمة مرور تحميه — ١٢ حرفاً على الأقل',
    },
    {
      type: 'label=اسم المحل',
      text: 'محل تجريبي',
      say: 'واسم محلك — أول شي يشوفه عملاؤك عنك',
    },
    {
      click: 'role=checkbox',
      say: 'موافقتك على الشروط، وخلصنا التسجيل',
    },
    {
      click: 'role=button:ابدأ',
      say: 'ضغطة «ابدأ»، وحسابك جاهز — بهذي البساطة',
    },
    // WelcomeTrial.tsx: a full-screen dialog, no click-outside, only «لنبدأ». It carries the
    // REAL trial end date on screen — not scripted here as text, since the actual dialog already
    // shows it and a caption repeating a date risks drifting from whatever trial_days is set to.
    // NO CHAPTER MARK — a 40s video can't fit YouTube's 10s-minimum spacing between more than
    // two or three of these beats; see the note below on «متجر التطبيقات» for which two won out.
    {
      waitFor: 'role=button:لنبدأ',
      say: 'وهذي الهدية — تجربة مجانية، شهر كامل، من غير أي بطاقة',
    },
    {
      say: 'كل إمكانيات المنصّة مفتوحة لك من اليوم الأول، بلا استثناء',
    },
    {
      click: 'role=button:لنبدأ',
      say: 'اضغط «لنبدأ»، ونشوف محلك',
    },
    // NO CHAPTER MARK HERE — it would land under 10s after «تجربتك المجانية» (the welcome dialog
    // + this glimpse both happen in quick succession), and YouTube silently drops the ENTIRE
    // chapter list if any two are closer than that. Folded into the same chapter instead of
    // getting its own; the caption itself is unaffected.
    {
      say: 'هذا محلك — فاضي الآن، وهذا طبيعي تماماً أول يوم',
    },
    {
      click: 'role=button:فتح القائمة',
      say: 'وكل قسم من محلك، على بعد ضغطة وحدة من هنا',
    },
    // THE ONE OTHER CHAPTER — this video's total length only supports two or three of these
    // marks at YouTube's 10s minimum; «متجر التطبيقات» is the fact the brief singled
    // out ("كل شي مفعل تجريبي"), so it's the one that earns the second mark. «وباقي محلك»
    // dropped its own mark too — a handful of seconds later is still under the floor.
    {
      click: 'role=link:متجر التطبيقات',
      chapter: 'متجر التطبيقات',
      say: 'وهذا متجر التطبيقات — كل إمكانية بمكانها',
    },
    {
      say: 'كل التطبيقات مفعّلة تجريبياً من الآن — بلا أي دفع مسبق',
    },
    {
      say: 'جرّبها كلها، ووسّع أو أوقف أي واحدة وقتها',
    },
    // A GENERAL POINTER, NOT A FULL TOUR — the brief: mention what exists and stop. The
    // rest of the console gets its own tours, one screen at a time, once each is studied deeply.
    {
      click: 'role=button:فتح القائمة',
      say: 'وباقي محلك — زيارتك وعملاؤك ورسائلك، كل شي جاهز ينتظرك',
    },
  ],
};
