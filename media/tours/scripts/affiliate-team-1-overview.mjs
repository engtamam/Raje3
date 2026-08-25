/**
 * «فريقي» (AffiliateTeam.tsx) — full coverage in one clip: the referral-link section, the Wafa
 * support queue, and the team roster with its per-member performance drawer, read top to bottom
 * exactly the order the component renders them. Read that file in full — every comment in it,
 * including AffiliateNav.tsx's own header on WHY this is a sixth nav slot rather than a seventh
 * screen bolted onto «أرباحي» — before writing a single selector here, this project's own
 * standing rule.
 *
 * WHY THIS ONLY EVER SHOWS A MANAGER SIGNING IN, NEVER A PROMOTER. AffiliatePortal.tsx's own
 * route guard is explicit: `effectiveTab` silently redirects `'team'` back to `'home'` for
 * anyone whose `role !== 'affiliate_manager'` — the tab does not exist in the nav for a
 * promoter, and the screen refuses to render even if `tab` state somehow still names it. There
 * is no promoter-side version of this tour to make; the account this script signs into MUST be
 * a manager or the very first step after sign-in (waiting on «فريقي» itself) fails loudly.
 *
 * WHY THIS SCRIPT LOGS IN FOR REAL (`skipAutoSignIn: true`), SAME REASONING AS EVERY OTHER
 * AFFILIATE TOUR. The portal keeps its own session store (`session.ts`: `raje3.affiliate.session`,
 * minted only by `/api/v1/affiliates/signin`) — there is no shop-side `useDemoSession` shortcut
 * into it, so the honest way in is the real door, on camera.
 *
 * THE ACCOUNT ITSELF: minted by seed-affiliate-team.mjs — the exact two-step path
 * onboarding.py's own module docstring describes (apply(), then the same platform-owner admin
 * account admin-home-1-overview.mjs's own tour uses to approve()), never a database shortcut.
 * `0555020202` / `Kobo2026$Mgr!` is a manager with NO referrer (onboarding.py::approve:
 * `role = promoter if app_row.parent_id else manager` — an applicant with an empty referral code
 * becomes a manager), and TWO real promoters (`سلطان`, `هند`) applied under HIS OWN referral
 * code, approved the same way. Nothing here is a database fixture; every row exists because the
 * real apply→approve path actually ran.
 *
 * WHY THE TEAM'S OWN MONEY IS HONESTLY ZERO, AND WHY THAT IS NOT A GAP IN THE SEED. «مؤكَّد» /
 * «قيد المراجعة» sum real `Commission` rows (core/commission.py), which only exist once a
 * referred SHOP actually signs up and pays — seeding that here would mean either faking a
 * commission with no real referral behind it (the one shortcut this whole family of scripts
 * refuses) or standing up real paying shops under two brand-new promoters, for a screen whose
 * subject is the ROSTER, not the money. So the roster is real and the money is real too — really
 * zero — narrated the same honest-empty-state way affiliate-earnings-1-overview.mjs already
 * narrates a first-day balance.
 *
 * WHY «طلبات دعم الوفاء بانتظارك» NEVER APPEARS IN THIS RECORDING. TeamWafaQueue.tsx's own code
 * renders NOTHING at all when the queue is empty (`if (rows.length === 0) return null`) — not a
 * greyed-out card, not a zero, an absent section, the same honest-empty-state discipline this
 * whole product follows. core/wafa.py's own request() refuses below 50 active shops, a threshold
 * this script cannot honestly reach for a demo team without real paying shops behind it — so
 * this chapter is narrated from the SCREEN'S OWN ABSENCE and the code's own words, with no
 * selector pointed at anything, exactly the way a viewer watching a real new manager's account
 * would actually experience it.
 *
 * SELECTORS ARE STABLE LABELS, NEVER A LIVE HALALAS FIGURE — «أرباح فريقك», «أضف عضواً لفريقك»,
 * each member's own fixed seeded NAME. A team's confirmed/pending totals are spoken over in the
 * caption, never matched by a selector, for the same reason affiliate-earnings-1-overview.mjs's
 * own header gives: a later seed adding a real commission must not break this script.
 */
const MANAGER_PHONE = '0555020202';
const MANAGER_PASSWORD = 'Kobo2026$Mgr!';
const PROMOTER_1_NAME = 'سلطان — مسوّق';
const PROMOTER_2_NAME = 'هند — مسوّقة';

export default {
  id: 'affiliate-team-1-overview',
  title: 'فريقي — رابط الدعوة وفريقك وطلبات دعم الوفاء كاملة',
  // UNIFIED ACROSS EVERY affiliate-*.mjs SCRIPT — see affiliate-account-1-overview.mjs's own note.
  section: 'منصة المسوّقين',
  skipAutoSignIn: true,
  // A REAL RECORDING CAUGHT FRAME 1 AS BLANK WHITE — the bundle loading before React's first
  // paint, the exact bug affiliate-earnings-1-overview.mjs's own `preload` comment already
  // documents. `preload: true` performs step 0's own `goto` before capture starts and waits for
  // the page to settle, so frame 1 is the door already drawn, never a blank white paint.
  preload: true,
  secondsCap: 240,
  steps: [
    // ── تسجيل الدخول ────────────────────────────────────────────────────────────────────────
    {
      goto: '/affiliates',
      chapter: 'تسجيل الدخول',
      say: 'بوابة المسوّقين — هذي المرة ندخل بحساب مدير تسويق',
    },
    {
      type: 'label=رقم الجوال',
      text: MANAGER_PHONE,
      say: 'رقم جواله',
    },
    {
      type: 'label=كلمة المرور',
      text: MANAGER_PASSWORD,
      say: 'وكلمة مروره',
    },
    {
      click: 'role=button:تسجيل الدخول',
      say: 'ويسجّل دخوله',
    },
    // «فريقي» ITSELF IS THE PROOF THIS ACCOUNT IS A MANAGER — a promoter's own nav never renders
    // this button at all (AffiliateNav.tsx's own `tabsFor(isManager)`), so waiting on it here
    // doubles as confirming the sign-in landed on the right kind of account.
    { waitFor: 'role=button:فريقي', timeoutMs: 45_000 },
    {
      hover: 'role=button:فريقي',
      chapter: 'فريقي — لمدير التسويق فقط',
      say: 'زر «فريقي» ما يظهر إلا لمدير تسويق',
    },
    {
      say: 'مسوّق عادي ما يشوفه إطلاقًا',
    },
    {
      say: 'لأن مدير التسويق مسوّق هو نفسه',
    },
    {
      say: 'وله كل ما للمسوّق العادي',
    },
    {
      say: 'وهذا التبويب هو الإضافي اللي فوقه: تتبّع فريقه وإدارتهم',
    },
    {
      click: 'role=button:فريقي',
      say: 'ندخله',
    },
    { waitFor: 'text=أضف عضواً لفريقك' },

    // ── رابط الدعوة ─────────────────────────────────────────────────────────────────────────
    {
      hover: 'text=أضف عضواً لفريقك',
      chapter: 'رابط الدعوة',
      say: 'أول قسم: «أضف عضواً لفريقك»',
    },
    {
      say: 'ولا يوجد دعوة تُرسَل من عندنا بعد الآن',
    },
    {
      say: 'المدير يشارك رابطه الخاص بنفسه — واتساب، شخصيًا',
    },
    {
      hover: 'css=input[dir="ltr"][readonly]',
      say: 'هذا رابطه — يحمل كود إحالته، وهو نفسه معرّف حسابه',
    },
    {
      click: 'role=button:نسخ',
      say: 'زر نسخ واحد — يأخذ الرابط كامل للحافظة فورًا',
    },
    {
      click: 'role=button:تنزيل كباركود',
      say: 'وزر ثانٍ يحوّل نفس الرابط لباركود PNG جاهز للتنزيل',
    },
    {
      say: 'تسهيل إضافي، لا بديل عن النسخ',
    },
    {
      say: 'ومن يستخدم الرابط يقدّم طلبه العادي، تحت مراجعة الإدارة',
    },
    {
      say: 'ثم يُربَط تحت هذا المدير تلقائيًا بمجرد الموافقة',
    },

    // ── طلبات دعم الوفاء (غائبة الآن، بصدق) ────────────────────────────────────────────────
    {
      chapter: 'طلبات دعم الوفاء',
      say: 'وبينه وبين الفريق تحته مكان لقسم ثالث: طلبات دعم الوفاء',
    },
    {
      say: 'ما تظهر الآن إطلاقًا — بصراحة، لا بطاقة فاضية مكانها',
    },
    {
      say: 'القسم كله يختفي إذا ما فيه طلب معلَّق بانتظار قرارك',
    },
    {
      say: 'دعم الوفاء راتب شهري لمسوّق حافظ على محلات نشطة',
    },
    {
      say: 'يحتاج فريقه يوصل خمسين محلاً فعليًا ليقدر يطلبه',
    },
    {
      say: 'ولمّا يطلب أحد فريقك، تطلع بطاقته هنا مباشرة',
    },
    {
      say: 'وموافقتك أو رفضك استشاري فقط — القرار الملزم للإدارة',
    },

    // ── فريقك ───────────────────────────────────────────────────────────────────────────────
    { waitFor: 'text=أرباح فريقك' },
    {
      hover: 'text=أرباح فريقك',
      chapter: 'أرباح فريقك',
      say: 'وآخر قسم: فريقه الفعلي',
    },
    {
      say: 'اثنان انضمّا تحته عبر رابطه بالضبط',
    },
    {
      say: 'فوق: مجموع أرباح الفريق — مؤكَّد وقيد المراجعة',
    },
    {
      say: 'بطاقتان منفصلتان، لا رقم واحد يخلطهما',
    },
    {
      say: 'وحساب جديد بلا محلات محالة بعد، فالمجموعان صفر بصدق',
    },
    {
      say: 'لا رقم مصطنع مكانهما',
    },
    {
      click: `role=button:${PROMOTER_1_NAME}`,
      chapter: 'عضو فريق واحد',
      say: 'وتحتها صفّ لكل عضو — اسمه وأرباحه المؤكَّدة',
    },
    {
      say: 'وعدد المحلات اللي جابها',
    },
    {
      say: 'اضغط على أي عضو يفتح أداءه بالتفصيل',
    },
    {
      say: 'بالضبط نفس البطاقة اللي يشوفها هو عن نفسه',
    },
    {
      say: 'معدّل الاحتفاظ ومعدّل الاسترجاع',
    },
    {
      say: 'وبما إنه لسه ما أحال محلاً، تطلع شرطة بدل نسبة',
    },
    {
      say: 'وجملة تحتها توضّح ليش بالضبط',
    },
    {
      click: `role=button:${PROMOTER_1_NAME}`,
      say: 'واضغط عليه مرة ثانية يطويه من جديد',
    },
    {
      click: `role=button:${PROMOTER_2_NAME}`,
      say: 'وكل عضو بفريقه يفتح ويطوي بنفس الطريقة',
    },
    {
      say: 'مستقلاً عن البقية تمامًا',
    },
    {
      say: 'ولو عضو موقوف مؤقتًا، تطلع شارة حالته بجانب اسمه',
    },
    {
      chapter: 'خلاصة الشاشة',
      say: 'بهذا خلصنا فهم «فريقي» كاملة',
    },
    {
      say: 'رابط الدعوة، طلبات دعم الوفاء، وفريقه الفعلي بأدائهم',
    },
  ],
};
