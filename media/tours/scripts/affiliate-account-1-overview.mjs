/**
 * «حسابي» — the affiliate portal's account screen, AffiliateAccount.tsx, top to bottom in one
 * clip: the profile card, the payout-method card (both its empty and its saved shape), the
 * change-password card, and the sign-out control — everything the file renders, nothing skipped.
 *
 * WHY THIS SIGNS IN FOR REAL (`skipAutoSignIn: true`, real `type`/`click` steps through
 * AffiliateDoor), NOT `useDemoSession`. That flag only ever seeds/restores the SHOP console's own
 * `raje3.session` key (record-tour.mjs's own comment on it says so plainly) — the affiliate
 * portal keeps a completely separate store (`affiliates/session.ts`'s own `raje3.affiliate.session`
 * key, by that file's own header note). There is no affiliate equivalent of `useDemoSession`, so
 * the honest way onto this screen is the same door a real marketer uses, on camera — which also
 * doubles as a look at what signing into the portal looks like.
 *
 * THE ACCOUNT ITSELF: `media/tours/seed-demo-affiliate.mjs`, run once ahead of this recording —
 * apply() → admin approve() → signin() over the real API, the same three round trips a real
 * onboarding takes. `0549900110` / `Raje3-Affiliate-Tour!1` is a fixed, reusable dev-cluster-only
 * login (not a secret), approved with no referrer — which makes it a manager (`ROLE_LABEL`'s own
 * "مدير تسويق"), matched below.
 *
 * REACHED BY PATH, NOT HOSTNAME. main.tsx registers `affiliates/*` on the shop's own router too
 * ("a link sent before the subdomain existed... must keep landing on the portal" — that file's
 * own comment), so `/affiliates` on the plain console origin is enough; no `affiliates.<domain>`
 * hostname trick needed for a dev-cluster recording.
 *
 * PAYOUT METHOD IS ACTUALLY SAVED, ONCE, ON CAMERA — a real `PUT /me/payout-method` round trip,
 * because that is the only way to ever show the view-mode card (the masked account, the "تغيير"
 * button) this component draws once a method is on file; a script that only ever showed the empty
 * state would be showing half the screen. Bank/IBAN is the channel left saved afterward — the
 * account is reused run after run, and a saved payout method does not stop the account signing in
 * again, unlike a changed password (see below) or a real sign-out.
 *
 * CHANGE PASSWORD IS OPENED, FILLED, AND *CANCELLED* — NEVER SUBMITTED. This account's whole
 * value is being a fixed, known login every future re-recording (of this tour or a later one)
 * can sign into without a fresh admin approval. An actual `POST /me/change-password` would spend
 * that guarantee for a demo, so the form is shown filled-in and working, then backed out of with
 * «إلغاء» — the same caution this project applies to a real sign-out below.
 *
 * SIGN-OUT IS NAMED, NEVER CLICKED — for the identical reason: `onSignOut` clears
 * `raje3.affiliate.session` for good (`session.ts`'s own `signOut`), and firing it here would
 * leave the NEXT recording of this exact tour looking at a signed-out door instead of the account
 * screen it exists to show. The button is on screen, described, and left alone.
 */
const AFFILIATE_PHONE = '0549900110';
const AFFILIATE_PASSWORD = 'Raje3-Affiliate-Tour!1';

export default {
  id: 'affiliate-account-1-overview',
  title: 'بوابة المسوّق — حسابي كاملة',
  // UNIFIED ACROSS EVERY affiliate-*.mjs SCRIPT — record-tour.mjs's own `outDir` groups clips by
  // this field, and AffiliateNav.tsx's own tab label ("حسابي") would otherwise scatter every
  // affiliate portal clip into its own single-video folder instead of one shared platform folder,
  // the way admin-*.mjs's own scripts already group under 'لوحة الإدارة'.
  section: 'منصة المسوّقين',
  skipAutoSignIn: true,
  preload: true,
  // A REAL SIGN-IN ROUND TRIP PLUS A SAVED PAYOUT WRITE — both real network calls against a
  // shared dev cluster; the generous cap admin-home-1-overview.mjs already uses for the same
  // reason (a live `/api/v1/affiliates/signin` observed taking real seconds under shared load).
  secondsCap: 180,
  steps: [
    // ── تسجيل الدخول ────────────────────────────────────────────────────────────────────────
    {
      goto: '/affiliates',
      chapter: 'تسجيل الدخول',
      say: 'بوابة المسوّق — بابها منفصل عن محلّك',
    },
    {
      type: 'label=رقم الجوال',
      text: AFFILIATE_PHONE,
      say: 'رقم جوال المسوّق',
    },
    {
      type: 'label=كلمة المرور',
      text: AFFILIATE_PASSWORD,
      say: 'وكلمة مروره',
    },
    {
      click: 'role=button:تسجيل الدخول',
      say: 'وسجّل دخوله',
    },
    // A REAL SIGN-IN, ON A SHARED CLUSTER — the same generous timeout admin-home-1-overview.mjs
    // uses for its own `/api/v1/auth/tenant` wait, for the same reason.
    //
    // WAITING ON THE HOME SCREEN'S OWN <h1> BY ITS RESOLVED NAME, NOT "الرئيسية" AS TEXT — that
    // word also labels the nav's own home button, rendered TWICE (AffiliateSidebar AND
    // AffiliateBottomNav, one hidden by CSS per viewport) and earlier in the DOM than the content
    // column; `.first()` resolved to the hidden one and the wait never passed (confirmed live).
    // AND NOT THE LOADING-STATE "بوابة المسوّق" EITHER — a live confirmed run showed `home()`
    // resolving to this account's own name well inside a couple of seconds, so the transient
    // placeholder never sat on screen long enough for a 90s wait to catch it either. This account
    // is fixed (`seed-demo-affiliate.mjs`'s own `NAME`), so its greeting is a stable target.
    { waitFor: 'text=مرحباً، مسوّق العرض', timeoutMs: 90_000 },
    {
      say: 'دخل — وهذي أول شاشة تفتح له',
    },
    // ── الوصول لـ«حسابي» ────────────────────────────────────────────────────────────────────
    {
      // A `<nav>` BOTTOM BAR, NOT THE `<aside>` SIDEBAR — AffiliateNav.tsx renders both with the
      // SAME label on every tab, one hidden by CSS per viewport (AffiliateSidebar is `aside`,
      // AffiliateBottomNav is `nav`); `role=button:حسابي` alone matches both and the click waits
      // forever on whichever one is hidden at this frame's width (the same ambiguity the sign-in
      // wait above hit). The tag tells them apart unambiguously.
      click: 'css=nav button:has-text("حسابي")',
      chapter: 'حسابي',
      say: 'وهذا قسمه: «حسابي»',
    },
    {
      say: 'كل شي يخص حسابه الشخصي — لا عملاءه ولا أرباحه',
    },
    // ── بطاقة الملف الشخصي ──────────────────────────────────────────────────────────────────
    // NAME LOADS ASYNC (`me()`'s own effect) — this account is «مسوّق العرض» applied with no
    // referrer, so ROLE_LABEL's own "مدير تسويق" is what should render once it resolves.
    { waitFor: 'text=مدير تسويق', timeoutMs: 30_000 },
    {
      say: 'فوق: اسمه وصفته — «مدير تسويق» لأنه انضم بلا مُحيل',
    },
    {
      say: 'مسوّق دخل عن طريق رابط إحالة يظهر له «مسوّق» بدلها',
    },
    // ── طريقة استلام الأرباح: الحالة المحفوظة ───────────────────────────────────────────────
    // AN EARLIER RECORDING OF THIS EXACT SCRIPT ALREADY SAVED A REAL IBAN ON THIS ACCOUNT — this
    // file's own header note on why it is left saved run after run ("the account is reused run
    // after run") means the EMPTY state («إضافة») can never be this account's real first sight
    // again; `role=button:إضافة` simply doesn't exist once a method is on file. This clip opens on
    // the SAVED shape instead, real and current, and reaches the empty FORM only through «تغيير».
    // THE SERVER NEVER ECHOES A FULL ACCOUNT NUMBER BACK — `PayoutMethod`'s own `masked_account_ref`
    // is the last four characters, confirmed in AffiliateAccount.tsx's own header comment; the
    // caption below never claims to show more than that.
    {
      chapter: 'طريقة استلام الأرباح',
      say: 'تحتها: طريقة استلامه لأرباحه',
    },
    { waitFor: 'text=تغيير', timeoutMs: 20_000 },
    {
      say: 'محفوظة من قبل — القناة، وآخر أربع خانات فقط',
    },
    {
      say: 'الرقم الكامل ما يرجع من الخادم أبداً — حتى لصاحبه',
    },
    {
      click: 'role=button:تغيير',
      say: 'زر «تغيير» يفتحها من جديد لو بغى يبدّلها',
    },
    {
      say: 'نموذج فاضي من جديد — لا يعبّي رقم حسابه القديم كامل',
    },
    {
      say: 'وتنبيه: تغييرها قد يؤخّر دفعته القادمة لحين مراجعتها',
    },
    {
      click: 'role=button:إلغاء',
      say: 'يرجع — يكفيه اللي حفظه',
    },
    // ── تغيير كلمة المرور ───────────────────────────────────────────────────────────────────
    {
      click: 'role=button:تغيير كلمة المرور',
      chapter: 'تغيير كلمة المرور',
      say: 'تحتها: تغيير كلمة المرور — مطوية افتراضياً',
    },
    {
      say: 'تحكّم حسّاس ما يُبرز نفسه — يحتاج ضغطة إضافية عمداً',
    },
    {
      say: 'ثلاث خانات: الحالية، الجديدة، وتأكيدها',
    },
    {
      type: 'css=input[placeholder="كلمة المرور الحالية"]',
      text: AFFILIATE_PASSWORD,
      say: 'كلمة مروره الحالية',
    },
    {
      type: 'css=input[placeholder="كلمة المرور الجديدة"]',
      text: 'Raje3-New-Demo!2',
      say: 'وكلمة مرور جديدة',
    },
    {
      type: 'css=input[placeholder="تأكيد كلمة المرور الجديدة"]',
      text: 'Raje3-New-Demo!2',
      say: 'وتأكيدها — نفس الجديدة بالضبط',
    },
    {
      say: 'هذا تغيير وهو داخل حسابه أصلاً',
    },
    {
      say: 'غير رابط «نسيت كلمة المرور» في باب الدخول',
    },
    {
      click: 'role=button:إلغاء',
      say: 'نرجع بلا حفظ — يبقى دخوله كما هو',
    },
    // ── تسجيل الخروج ────────────────────────────────────────────────────────────────────────
    {
      chapter: 'تسجيل الخروج',
      say: 'وآخر شي بالشاشة: تسجيل الخروج',
    },
    {
      hover: 'role=button:تسجيل الخروج',
      say: 'زر واحد واضح — ينهي جلسته على هذا الجهاز فقط',
    },
    {
      say: 'وبهذا خلصنا جولة كاملة على «حسابي»',
    },
  ],
};
