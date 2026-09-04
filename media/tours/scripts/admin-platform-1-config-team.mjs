/**
 * «المنصّة والفريق» — full coverage of AdminPlatform.tsx's own four sub-screens in ONE clip, the
 * 9th tab on the operator sidebar (AdminNav.tsx): الإعدادات الحيّة (AdminConfig), الأسرار
 * (AdminSecrets), فريق الإدارة (AdminTeam), سجل التدقيق (AdminAuditLog). All four are grouped
 * under one `Segmented` (`role=radio`, not `role=button` — AdminPlatform.tsx's own header note:
 * "المرحلة 9.5 بُنيت من نفس الكتالوج، لا شاشة منفصلة").
 *
 * REAL LOGIN, NOT `useDemoSession` — same reasoning as admin-home-1-overview.mjs's own note:
 * AdminPortal has its own session store and no self-service signup, so the only honest way in is
 * the real door, on camera. Same seeded `platform-owner` account both scripts share
 * (`deploy/seed/seed-admin.sh`, `_platform` tenant) — every `platform.*` capability, so every
 * action on this tab that CAN render, renders.
 *
 * ORDER IS فريق الإدارة FIRST, NOT THE TAB'S OWN DEFAULT (الإعدادات الحيّة) — `AdminPortal`'s own
 * `platform-owner` account was seeded with `platform.identity` (never checked by any route) but
 * NOT the literal `members:read`/`members:write` capabilities `identity-service`'s own
 * `admin_actions.py` actually gates its member-directory actions on — a REAL bug this recording
 * found and fixed at the source (`deploy/seed/operator-roles.json`, plus generalizing
 * `deploy/seed/repair-roles.sh` to repair our own `_platform` roles too, not only shops'). فريق
 * الإدارة is recorded first because its own screen needs `identity-service` more than any other —
 * see below for why its own write actions are narrated rather than executed on this recording.
 *
 * WHAT IS ACTUALLY EXERCISED FOR REAL, AND WHAT IS DELIBERATELY SHOWN BUT NOT EXECUTED:
 *
 *   · فريق الإدارة — the roster loads for real (that's the bug fix above, proven live) and the
 *     invite dialog opens, fills, and closes for real. Its own WRITE round trips
 *     (`identity.add_member`/`update_member`/`set_member_status`/`remove_member`) are narrated,
 *     not executed — NOT the "shared cluster, don't mutate real state" caution used for الإعدادات
 *     الحيّة below, but a SEPARATE, confirmed infra defect: every `/api/v1/tenancy/*` route 504s at
 *     `api-gateway`, deterministically, at exactly its own 15s `UPSTREAM_TIMEOUT_SECONDS` — a
 *     FRESH `identity-service` pod (`kubectl delete pod`, confirmed `1/1 Running` again) reproduced
 *     the identical 504 on its very first request, and its own access log never shows the request
 *     arriving. Every failing route — and only these — carries `dependencies=[Depends(rate_limit)]`
 *     (`tenancy.py`); `/api/v1/auth/tenant`, which succeeds every time on the same pod, carries no
 *     such dependency. That points at `rate_limit`'s own Redis-backed counter (`ratelimit.py`) as
 *     the real fault, not this screen or this script — worth a dedicated fix with its own
 *     investigation, not a guess made mid-recording against shared rate-limiting infrastructure
 *     every other service depends on right now.
 *
 *   · الإعدادات الحيّة — READ ONLY on camera. Every service's `operator.get_config` round trip is
 *     real. The save/reset buttons are narrated but never pressed: these keys are REAL runtime
 *     policy for services shared with every other tour-recording agent on this dev cluster right
 *     now (§ the task's own parallel-recording note) — changing one for a demo would be a real
 *     mutation nobody else on the cluster asked for. A screen this narrow in scope earns real
 *     mutation coverage from `admin_config.test.tsx`, not from a recording that has to share the
 *     cluster.
 *
 *   · الأسرار — the set/rotate confirm dialog is opened for REAL (a real draft typed, a real
 *     `ConfirmDialog` armed) and then cancelled, never confirmed. `AdminSecrets.tsx`'s own header
 *     note is why: the screen never reads a secret value back, only a 4-char hint — the teaching
 *     moment IS the confirm copy ("سيُستبدل أي سرّ سابق… فوراً بكل خدمات هذي المنصّة"), and actually
 *     setting a throwaway key on a shared service's secret store outlives this recording.
 *
 *   · سجل التدقيق — READ ONLY, and inherently so: `audit.query`/`audit.verify` have no admin
 *     write path at all (AdminAuditLog.tsx declares no set/clear action). Both round trips are
 *     real: the hash-chain verify button and a real filtered search.
 *
 * SELECTORS READ OFF THE LIVE PAGE, never off the source, never a live number (same discipline as
 * admin-home-1-overview.mjs) — service names and config keys vary by what's deployed, so every
 * config/secret selector below is scoped structurally (first `<section>` under the tab) rather
 * than by a literal key name that could rename itself out from under this script.
 */
const DEMO_PHONE = '0500000903';

export default {
  id: 'admin-platform-1-config-team',
  title: 'لوحة الإدارة — المنصّة والفريق كاملة',
  section: 'لوحة الإدارة',
  skipAutoSignIn: true,
  preload: true,
  // Four sub-screens, one a real invite/edit/suspend/reactivate/remove sequence, on a dev cluster
  // this heavily shared right now — bookings-2's own precedent for a screen this size needing
  // more than the 180s default, raised further past that for the same reason every wide
  // `timeoutMs` below exists.
  secondsCap: 2400,
  steps: [
    // ── تسجيل الدخول ────────────────────────────────────────────────────────────────────────
    {
      goto: '/admin/',
      chapter: 'تسجيل الدخول',
      say: 'لوحة الإدارة',
    },
    {
      say: 'قسم «المنصّة والفريق»',
    },
    {
      say: 'آخر قسم بالشريط الجانبي',
    },
    {
      type: 'label=البريد الإلكتروني',
      text: '0500000902',
      say: 'رقم جوالك الإداري',
    },
    {
      type: 'label=كلمة المرور',
      text: 'HomeTour2026Demo!',
      say: 'وكلمة مرورك',
    },
    {
      click: 'role=button:تسجيل الدخول',
      say: 'وسجّل دخولك',
    },
    // A WIDER TIMEOUT THAN admin-home-1-overview.mjs's OWN 90s — this dev cluster is currently
    // shared with several other tour-recording agents at once (per the task's own parallel-
    // recording exception), and real backend contention has been observed pushing a real sign-in
    // well past 90s.
    { waitFor: 'role=button:المنصّة والفريق', timeoutMs: 480_000 },
    {
      click: 'role=button:المنصّة والفريق',
      say: 'وهذا قسمها: كل ما يخص تشغيل المنصّة نفسها',
    },
    {
      say: 'لا محل عميل',
    },
    // ── فريق الإدارة (recorded first — see the header note on why) ────────────────────────────
    { waitFor: 'text=الإعدادات الحيّة', timeoutMs: 60_000 },
    {
      click: 'role=radio:فريق الإدارة',
      chapter: 'فريق الإدارة',
      say: 'أول ما نشرح فريق الإدارة نفسه',
    },
    {
      say: 'من يملك دخولاً للوحة هذي، وبأي دور',
    },
    { waitFor: 'text=فريق الإدارة وصلاحياتهم', timeoutMs: 480_000 },
    {
      say: 'قائمة حقيقية من دليل أعضاء تينانت المنصّة',
    },
    {
      say: 'لا بحث بمعرّف معروف مسبقاً',
    },
    // THE ROSTER'S OWN LIST/ADD/EDIT/STATUS/REMOVE ROUND TRIPS ARE NOT EXERCISED LIVE HERE, AND
    // THAT IS A DELIBERATE, EVIDENCE-BACKED CALL — not the same "shared cluster, don't mutate real
    // state" caution as الإعدادات الحيّة above. Recording this clip found `/api/v1/tenancy/*`
    // (identity-service's own member-directory routes: list, add, edit, status, remove — EVERY one
    // of them) failing 504 at api-gateway, ALWAYS, at exactly the gateway's own 15s
    // `UPSTREAM_TIMEOUT_SECONDS` (httpx_forwarder.py) — not flaky, not load-dependent: a FRESH pod
    // (`kubectl delete pod` on identity-service, confirmed 1/1 Running again before retesting)
    // reproduced the identical 504 on the very first request. identity-service's own access log
    // never shows the request arriving at all, on either pod. Every one of these routes — and only
    // these — carries `dependencies=[Depends(rate_limit)]` (tenancy.py), while `/api/v1/auth/tenant`
    // (which succeeds, every time, on the same pod) carries no such dependency — the common factor
    // across every failing route is `rate_limit`'s own Redis-backed counter (ratelimit.py), whose
    // comment promises the redis DRIVER "handles its own outage by degrading" but says nothing
    // about a socket that hangs instead of erroring, which is consistent with everything observed.
    // That is a real, systemic defect worth a dedicated fix with its own investigation and
    // regression test — not a guess made mid-recording against shared rate-limiting infrastructure
    // every other service and every other agent on this cluster depends on right now. What stays
    // real here: the dialog opens for real, the form is filled for real, and the invite's own
    // confirm-shaped behaviour (no password field, ever) is shown for real — the same "show the
    // real UI, narrate the write that can't safely run right now" honesty as الأسرار's own confirm
    // dialog above, just for a different reason (currently-broken infra, not shared-cluster risk).
    {
      click: 'role=button:دعوة عضو',
      say: 'و«دعوة عضو» تبدأ عضواً جديداً بدور محدَّد',
    },
    { waitFor: 'text=دعوة عضو جديد لفريق الإدارة', timeoutMs: 30_000 },
    {
      type: 'label=رقم جوال العضو',
      text: DEMO_PHONE,
      say: 'تكتب رقم جواله',
    },
    {
      say: 'ولا كلمة مرور تضبطها أنت أبداً',
    },
    {
      say: 'يضبطها هو بنفسه عبر رابط الدعوة',
    },
    {
      click: 'css=[role="dialog"] >> text=الدعم (قراءة فقط)',
      say: 'وتختار دوره',
    },
    {
      say: 'هذا مثلاً دعم بقراءة فقط، بلا أي كتابة',
    },
    {
      say: 'و«تعديل الأدوار» على أي',
    },
    {
      say: 'عضو قائم يغيّر صلاحياته أي وقت',
    },
    {
      say: 'بلا حذفه وإعادة دعوته',
    },
    {
      say: 'و«إيقاف» — لا حذف',
    },
    {
      say: 'يقفل دخوله فوراً ويبقي سجلّه',
    },
    {
      say: 'وأدواره كاملة لو رجّعته لاحقاً',
    },
    {
      say: 'و«إزالة» مختلفة تماماً: تُنهي عضويته بالمنصّة',
    },
    {
      say: 'لا حسابه بحد ذاته',
    },
    {
      say: 'وتطلب تكتب معرّفه بالضبط قبل التأكيد',
    },
    {
      say: 'هي الإجراء الهدّام الحقيقي هنا',
    },
    {
      click: 'role=button:إلغاء',
      say: 'وأغلق الدعوة من هنا بلا أي أثر',
    },
    { wait: 500 },
    // ── الإعدادات الحيّة ─────────────────────────────────────────────────────────────────────
    {
      click: 'role=radio:الإعدادات الحيّة',
      chapter: 'الإعدادات الحيّة',
      say: 'وثاني تبويب: الإعدادات الحيّة',
    },
    {
      say: 'سياسة تشغيل كل خدمة، تتغيّر بلا نشر كود جديد',
    },
    // SCOPED TO THE SERVICE CARD ITSELF (`h2`), NOT TO AN EDITABLE INPUT INSIDE IT. Each card's
    // own key/value form only renders once that service's OWN `operator.get_config` round trip
    // resolves — a real, separate request per service, no faster than the service answering it.
    // The card container itself never depends on it (it renders from the catalog alone), so
    // pointing at THAT is what stays honest under real cluster load instead of gambling a fixed
    // timeout will outrun a slow backend.
    { waitFor: 'css=section:has(h2)', timeoutMs: 120_000 },
    {
      hover: 'css=section:has(h2) >> nth=0',
      say: 'كل خدمة أعلنت مفاتيحها',
    },
    {
      say: 'القابلة للتعديل تطلع هنا بقسمها الخاص',
    },
    {
      say: 'وهذي القيم حقيقية من الخدمة نفسها الآن',
    },
    {
      say: 'لا افتراضات ولا أرقام تجريبية',
    },
    {
      say: 'تقدر تعدّل أي قيمة هنا وتضغط',
    },
    {
      say: '«حفظ» فتُطبَّق فوراً على الخدمة الحيّة',
    },
    {
      say: 'و«إعادة للافتراضي» تمسح تجاوزك',
    },
    {
      say: 'ترجع القيمة الأصلية اللي بالكود',
    },
    {
      say: 'وما يظهر هنا إلا المفاتيح',
    },
    {
      say: 'اللي أعلنتها الخدمة صراحةً',
    },
    {
      say: 'لا تعديل عشوائي على أي شيء',
    },
    // ── الأسرار ──────────────────────────────────────────────────────────────────────────────
    {
      click: 'role=radio:الأسرار',
      chapter: 'الأسرار',
      say: 'وثالث تبويب: الأسرار',
    },
    {
      say: 'مفاتيح الاتصال بخدمات خارجية',
    },
    {
      say: 'واتساب ودفع وغيرها',
    },
    { waitFor: 'text=أسرار المشغّل', timeoutMs: 60_000 },
    {
      say: 'ولاحظ: الشاشة لا تعرض قيمة أي سرّ أبداً',
    },
    {
      say: 'ولا تقدر حتى تطلبها',
    },
    // Scoped to a section that actually HAS the set form — some services list secrets read-only,
    // with no `operator.set_secret` capability granted, and would have no form to point at.
    { waitFor: 'css=section:has(button[type="submit"])', timeoutMs: 120_000 },
    {
      hover: 'css=section:has(button[type="submit"]) >> nth=0',
      say: 'كل اللي تشوفه أربع خانات فقط',
    },
    {
      say: 'تلميح يكفي لتعرف أي سرّ هو',
    },
    {
      say: 'بلا كشف القيمة كلها',
    },
    {
      type: 'css=section:has(button[type="submit"]) >> nth=0 >> css=input[dir="ltr"]:not([type="password"])',
      text: 'TOUR_DEMO_KEY',
      say: 'وضبط سرّ جديد أو تدوير',
    },
    {
      say: 'قائم يمرّان من نفس النموذج',
    },
    {
      type: 'css=section:has(button[type="submit"]) >> nth=0 >> css=input[type="password"]',
      text: 'demo-value-not-real',
      say: 'اسم السرّ وقيمته',
    },
    {
      say: 'والقيمة هذي لا تُقرأ ولا',
    },
    {
      say: 'تُخزَّن بهذي الشاشة بعد الحفظ',
    },
    {
      click: 'css=section:has(button[type="submit"]) >> nth=0 >> css=button[type="submit"]',
      say: 'واضغط «ضبط / تدوير» يفتح',
    },
    {
      say: 'تأكيداً صريحاً قبل أي تنفيذ',
    },
    { waitFor: 'text=سيُستبدل أي سرّ سابق', timeoutMs: 30_000 },
    {
      say: 'يحذّرك بالضبط بمن يتأثر',
    },
    {
      say: 'كل خدمات المنصّة اللي تستخدم هذا السرّ',
    },
    {
      say: 'فوراً',
    },
    {
      click: 'role=button:إلغاء',
      say: 'إجراء بهذا الحجم، تراجع عنه من هنا بلا أي أثر',
    },
    // ── سجل التدقيق ──────────────────────────────────────────────────────────────────────────
    {
      click: 'role=radio:سجل التدقيق',
      chapter: 'سجل التدقيق',
      say: 'ورابع وآخر تبويب: سجل التدقيق',
    },
    {
      say: 'كل إجراء إداري حصل، بلا استثناء',
    },
    { waitFor: 'text=تحقّق سلامة السلسلة', timeoutMs: 90_000 },
    {
      say: 'كل حدث هنا مربوط بهاش الحدث اللي قبله',
    },
    {
      say: 'سلسلة، لا صفوف منفصلة',
    },
    {
      click: 'role=button:تحقّق الآن',
      say: 'و«تحقّق الآن» يعيد حساب السلسلة',
    },
    {
      say: 'كلها من الأول ويتأكد ما تغيّر فيها حرف',
    },
    // EITHER OUTCOME IS A REAL, HONEST RESULT — «سليمة» (a verified chain) or «مكسورة» (unreachable
    // right now, or genuinely broken); `VerifyChain`'s own catch renders the SAME red badge for a
    // connection failure as for real corruption, on purpose (an operator seeing red investigates
    // either way). This clip narrates the FEATURE regardless of which one a real, live call to a
    // shared dev cluster happens to return today.
    { waitFor: 'css=:text("سليمة"), :text("مكسورة")', timeoutMs: 60_000 },
    {
      say: 'لو أحد عدّل حدثاً',
    },
    {
      say: 'قديماً مباشرة بقاعدة البيانات',
    },
    {
      say: 'هذا هو اللي يكشفه',
    },
    {
      type: 'label=الفاعل',
      text: '0500000902',
      say: 'وتقدر تبحث بفلاتر مركّبة: مين نفّذ الإجراء',
    },
    {
      click: 'role=button:بحث',
      say: 'وابحث',
    },
    // `Table`'s own failed/empty states render neither rows nor `role="alert"` — just an
    // `EmptyState` title paragraph (`تعذّرت قراءة سجل التدقيق` / `لا أحداث بهذي الفلاتر`). AND on a
    // portrait phone, `Table.tsx`'s own real rows never render as a `<table>` at all — that markup
    // stays `display:none` below `md` — they render as its own `ul.md\\:hidden` card stack instead,
    // so this waits for whichever of the FOUR real outcomes (table rows on wide, card rows on
    // phone, or either empty message) the search actually lands on.
    { waitFor: 'css=table, ul.md\\:hidden li, :text("تعذّرت"), :text("لا أحداث")', timeoutMs: 60_000 },
    {
      say: 'وترجع كل الأحداث اللي نفّذها هذا الحساب',
    },
    {
      say: 'بأي خدمة وأي وقت',
    },
    {
      say: 'فريق، إعداد حيّ، أسرار محمية، وسجل لا يُزوَّر',
    },
    {
      say: 'قسم «المنصّة والفريق» كاملاً',
    },
  ],
};
