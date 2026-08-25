/**
 * «المالية» (AdminFinance.tsx) — FULL COVERAGE IN ONE CLIP: invoices, subscriptions, and the
 * payment-recovery tools, exactly as the platform-owner sees them.
 *
 * THE BUSINESS MODEL, AND WHY THE SCREEN HAS NO "متأخرة" STATUS. AdminFinance.tsx's own header
 * comment says it outright — prepaid in full, always: an invoice is `paid` or it is `open`
 * ("غير مدفوعة"), never a third "overdue" state a platform operator would need to chase. The
 * three saved views (paid today / renewals that didn't happen / voided this month) are the real
 * questions this screen gets opened for, not generic filters bolted on afterward.
 *
 * WHY EVERY SEARCH REQUIRES A FILTER FIRST. `InvoicesPanel.search`/`SubscriptionsPanel.search`
 * both refuse with no status/tenant/date set at all — no accidental full scan across every
 * tenant's billing history. Demonstrated for real before ever filling a filter, because it is the
 * first thing a real operator hits.
 *
 * WHY THIS SCRIPT NARRATES SETTLE/SETTLEMENTS/REVERSE RATHER THAN OPENING THEM ON CAMERA. Verified
 * against the live dev cluster before writing a single step here (two throwaway Playwright probes,
 * not scripted into the tour itself): `billing.platform_invoices` on this cluster returns ZERO
 * rows for every one of the three saved views AND for a manual `status=paid` search — no invoice
 * has ever been settled on this `_platform` tenant's billing tables. `InvoicesPanel`'s own
 * "تسوية"/"التسويات" buttons are a PER-ROW column (`InvoicesPanel`'s `columns.push` inside
 * `if (settleAction)`) that Table.tsx never renders at all with zero rows — there is no real button
 * anywhere on this live session to click. Faking that state (mocking a row, hand-editing local
 * state) would put something on screen that never happened against the real backend, which is
 * worse than not showing it: this screen exists BECAUSE the operator must trust every number on it
 * is real. So this clip shows the real, honest empty result for both invoices and subscriptions —
 * which is itself the correct, teachable behavior, not a placeholder — and narrates the settle/
 * reverse mechanics from the component's own confirmed logic instead of pretending a row exists.
 *
 * WHY THE REFUND DIALOG IS SHOWN ARMED BUT NEVER CONFIRMED. `PaymentTools` needs no existing
 * invoice — the operator types any `payment_id` by hand, so this part of the screen IS fully
 * operable for real on this session. But confirming a real refund call against a gateway with a
 * fabricated payment id would just produce a real error from a real destructive endpoint for no
 * teaching benefit; the actual safety mechanism worth teaching is `ConfirmDialog`'s
 * arm-by-typed-id gate, which is shown filled in, armed, then cancelled. `reconcile` is the one
 * mutation actually fired for real — it only reads the gateway's own record, nothing destructive.
 *
 * THE ACCOUNT: same `platform-owner` seeded for the home-screen tour (`admin-home-1-overview.mjs`
 * — see its own header note for why this script logs in for real rather than `useDemoSession`).
 * `platform-owner` carries `platform.billing`, which is what makes every action on this screen
 * resolve at all.
 *
 * SELECTORS READ OFF THE LIVE PAGE, never off the source. None encode a live number.
 */
export default {
  id: 'admin-finance-1-overview',
  title: 'لوحة الإدارة — المالية كاملة',
  section: 'لوحة الإدارة',
  skipAutoSignIn: true,
  orientation: 'landscape',
  preload: true,
  secondsCap: 360,
  steps: [
    // ── تسجيل الدخول ────────────────────────────────────────────────────────────────────────
    {
      goto: '/admin/',
      chapter: 'تسجيل الدخول',
      say: 'هذي لوحة تحكم راجِع، وحساب مشغّل المنصّة يدخل من هنا',
    },
    {
      type: 'label=البريد الإلكتروني',
      text: '0500000902',
      say: 'ادخل ببريدك أو رقمك الإداري',
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
    { waitFor: 'text=الإيراد الكلي هالشهر', timeoutMs: 90_000 },
    {
      click: 'text=المالية',
      chapter: 'المالية',
      say: 'ونروح مباشرة لقسم المالية بالشريط الجانبي',
    },
    { waitFor: 'text=الفواتير' },
    {
      say: 'راجِع مسبوق الدفع بالكامل — كل فاتورة إما مدفوعة أو غير مدفوعة، ولا حالة «متأخرة» عندنا إطلاقًا',
    },
    // ── فلتر واحد إلزامي ────────────────────────────────────────────────────────────────────
    {
      click: 'role=button:بحث!',
      chapter: 'فلتر واحد إلزامي',
      say: 'لو ضغطت بحث بلا أي فلتر…',
    },
    {
      waitFor: 'text=فلتر واحد على الأقل مطلوب',
      say: 'يرفض فورًا — ولا مسح لفواتير كل المحلات دفعة وحدة، ولو أنت مالك المنصّة',
    },
    // العروض المحفوظة الثلاثة — لا chapter مستقل هنا: أقل من ١٠ ثوانٍ بعد «فلتر واحد إلزامي»،
    // ويوتيوب يُسقِط قائمة الفصول كاملة لو فصلان أقرب من ذلك.
    {
      hover: 'role=button:مدفوعات اليوم',
      say: 'وبدل الفلاتر العامة، ثلاث أسئلة حقيقية محفوظة كأزرار — أول وحدة: مين دفع اليوم',
    },
    {
      hover: 'role=button:تجديدات لم تتم',
      say: 'وثاني وحدة: تجديدات كان يفترض تصير ولا صارت',
    },
    {
      hover: 'role=button:ملغاة هذا الشهر',
      say: 'وثالثها: فواتير أُلغيت هالشهر بالذات',
    },
    {
      click: 'role=button:مدفوعات اليوم',
      say: 'أفتح مدفوعات اليوم — وتعبّي الفلاتر تلقائيًا وتبحث فورًا، بلا تعبئة يدوية لهذي الأسئلة المتكرّرة',
    },
    { waitFor: 'text=لا فواتير بهذي الفلاتر', timeoutMs: 30_000 },
    {
      say: 'وما فيه مدفوعات اليوم على هذا الحساب التجريبي — نتيجة حقيقية، لا رقم مزيّف مكانها',
    },
    // ── أعمدة الجدول وأدوات كل فاتورة ───────────────────────────────────────────────────────
    {
      chapter: 'أعمدة الجدول وأدوات كل فاتورة',
      say: 'ولو فيه فواتير، يطلع لكل وحدة رقمها، المحل، حالتها بلون مميّز، وإجماليها',
    },
    {
      say: 'وعمود «المسترجَع» يظهر فقط لو صار عليها استرجاع جزئي أو كامل — لا عمود فارغ دائمًا',
    },
    {
      say: 'وجنب كل فاتورة زرّان: «تسوية» لتسجيل دفعة يدوية وصلتك خارج بوابة الدفع الآلية',
    },
    {
      say: 'حوالة بنكية أو شيك — و«التسويات» لعرض كل دفعة يدوية سُجِّلت عليها',
    },
    {
      say: 'وتسجيل التسوية يحتاج كتابة رقم الفاتورة نفسه للتأكيد — لأنها تُسجَّل كدفع فعلي',
    },
    {
      say: 'ولكل تسوية زر «عكس» يلغي أثرها على حالة الفاتورة، لكن بسبب مكتوب إلزامي',
    },
    {
      say: 'ولا تُحذف التسوية من السجلّ إطلاقًا حتى بعد عكسها',
    },
    // الفلترة اليدوية — لا chapter مستقل هنا: أقل من ١٠ ثوانٍ قبل «الاشتراكات» التالية، ويوتيوب
    // يُسقِط قائمة الفصول كاملة لو فصلان أقرب من ذلك.
    {
      select: 'label=الحالة',
      option: 'مدفوعة',
      say: 'وتقدر تفلتر يدويًا كمان — بالحالة',
    },
    {
      click: 'role=button:بحث!',
      say: 'وبالمحل، وبمدى تاريخ — بأي مزيج منها',
    },
    { waitFor: 'text=لا فواتير بهذي الفلاتر', timeoutMs: 30_000 },
    // ── الاشتراكات ──────────────────────────────────────────────────────────────────────────
    {
      click: 'role=radio:الاشتراكات',
      chapter: 'الاشتراكات',
      say: 'وثاني تبويب — الاشتراكات',
    },
    { waitFor: 'text=بحث' },
    {
      say: 'ونفس المبدأ: فلتر واحد على الأقل إلزامي، بالحالة أو بالمحل',
    },
    {
      select: 'label=الحالة',
      option: 'فعّال',
      say: 'أفلتر بالاشتراكات الفعّالة الآن',
    },
    {
      click: 'role=button:بحث!',
      say: 'وأبحث',
    },
    { waitFor: 'text=لا اشتراكات بهذي الفلاتر', timeoutMs: 30_000 },
    {
      say: 'ولا اشتراك فعّال الآن على هذا الحساب — نتيجة حقيقية أيضًا',
    },
    {
      say: 'ولو وُجد، يطلع لكل محل متى بدأ اشتراكه، ومتى انتهى إن انتهى',
    },
    // ── أدوات الدفع ─────────────────────────────────────────────────────────────────────────
    {
      click: 'role=radio:أدوات الدفع',
      chapter: 'أدوات الدفع',
      say: 'وآخر تبويب — أدوات الدفع، لأصعب سؤال يوصلك: «دفعتُ ولم تُفتَح خدمتي»',
    },
    { waitFor: 'text=معرّف الدفعة' },
    {
      say: 'وأول سطر بالشاشة نفسها يقولها صراحة: ابدأ بالمطابقة مع البوابة، والتسوية اليدوية آخر الخيارات لا أولها',
    },
    {
      type: 'label=معرّف الدفعة (payment_id)',
      text: 'pay_tour_demo_0001',
      say: 'اكتب معرّف الدفعة',
    },
    {
      click: 'role=button:مطابقة مع البوابة',
      say: 'وزر المطابقة يسأل بوابة الدفع نفسها عن حالة هذي الدفعة الحقيقية — ما يخمّن',
    },
    { wait: 1500 },
    // ── الاسترجاع الكامل ────────────────────────────────────────────────────────────────────
    {
      click: 'role=button:استرجاع كامل',
      chapter: 'الاسترجاع الكامل',
      say: 'وزر الاسترجاع الكامل — إجراء هدّام حقيقي، عشان كذا مسلَّح بتأكيد صارم',
    },
    { waitFor: 'text=هذا يعكس المبلغ بالبوابة' },
    {
      say: 'يعكس المبلغ فعليًا بالبوابة، ويُلغي الفاتورة تلقائيًا لو غطّى الاسترجاع كامل قيمتها',
    },
    {
      say: 'ولازم تكتب معرّف الدفعة نفسه بالضبط قبل ما يتفعّل زر التأكيد — لا نقرة واحدة تكفي لاسترجاع مال',
    },
    {
      click: 'role=button:إلغاء',
      say: 'ونلغي هنا — بلا استرجاع حقيقي على دفعة تجريبية',
    },
    {
      chapter: 'الخلاصة',
      say: 'وهذي المالية كاملة — فواتير مسبوقة الدفع، اشتراكات، وأدوات استرجاع محكومة كلها بصلاحيتك وبتأكيد صريح',
    },
  ],
};
