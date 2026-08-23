# =============================================================================
# affiliate-service — the outbound conversion playbook's SEED data (2026-08-22)
# -----------------------------------------------------------------------------
# NOT HARDCODED BUSINESS LOGIC — these are the INITIAL rows a fresh install gets, through the
# exact same create() calls a manager's own PUT/POST would make. Once seeded, a manager owns them
# completely: edits, deactivates, or adds more, all through the ordinary API.
#
# WHY THIS RUNS ON EVERY BOOT, AND WHY THAT IS SAFE. `seed()` below checks for EXISTENCE first —
# `stages.get(code)`/matching (stage_code, title) for templates — and only creates what is
# genuinely missing. It NEVER calls create() on a stage or template that already exists, even a
# deactivated one: OutreachStageService.create()/TemplateService.create() are upserts that also
# flip `active` back to True, and calling either on every restart would silently UN-deactivate a
# stage or template a manager deliberately turned off. That would be exactly the kind of silent
# rewrite of a human's own decision this whole codebase refuses to do anywhere else.
#
# STAGE 1 ONLY, FOR NOW (gatekeeper) — five templates, researched and approved on 2026-08-22 (see
# the conversation that produced them: foot-in-the-door, ally framing, reciprocity, pattern
# interrupt, negative-reverse/Sandler). The other seven stages are seeded with NO templates yet;
# more are added the same way, later, by editing SEED_TEMPLATES here or — just as validly — by a
# manager typing them straight into the console once it exists.
# =============================================================================
from __future__ import annotations

from typing import Any

from app.core.outreach import OutreachStageService, StatCitationService, TemplateService

SEED_STAGES: list[dict[str, Any]] = [
    {"code": "gatekeeper", "name": "تجاوز حارس البوابة", "order": 1},
    {"code": "hook", "name": "الخطاف", "order": 2},
    {"code": "offer", "name": "عرض التجربة بلا احتكاك", "order": 3},
    {"code": "follow_up", "name": "مصفوفة المتابعة المتدرّجة", "order": 4},
    {"code": "onboarding", "name": "التهيئة وبناء الثقة السريعة", "order": 5},
    {"code": "paid_conversion", "name": "الإغلاق والتحويل المدفوع", "order": 6},
    {"code": "cold_revival", "name": "إحياء البارد", "order": 7},
    {"code": "referral", "name": "إحالة ما بعد التحويل", "order": 8},
]

# `{{1}}` = اسم المحل — نفس ترقيم واتساب المعتمد (Meta)، لا فراغات حرة بلا ترقيم.
SEED_TEMPLATES: list[dict[str, Any]] = [
    {
        "stage_code": "gatekeeper", "kind": "رسالة", "title": "الابتسامة الأولى",
        "body": "هلا والله 🌟 كيفك اليوم؟ عندي سؤال بسيط: مين أقدر أكلمه بخصوص فكرة تفيد {{1}}؟",
    },
    {
        "stage_code": "gatekeeper", "kind": "رسالة", "title": "رأيها يهمّني",
        "body": "يا الغالية وش رايك، لو وصلت فكرة تفيد {{1}}، لمين تشوفينه أنسب واحد يسمعها؟",
    },
    {
        "stage_code": "gatekeeper", "kind": "رسالة", "title": "العطاء أولاً",
        "objection_type": "reciprocity",
        "body": "هلا 🌿 خطر ببالي شي يفيد {{1}}: أغلب الصالونات تخسر عميلات بدون ما تدري ليش. "
               "حبيت أشاركك الملاحظة — تشوفين مين يفيد نتكلم معه فيها؟",
    },
    {
        "stage_code": "gatekeeper", "kind": "رسالة", "title": "الصراحة المفاجئة",
        "objection_type": "pattern_interrupt",
        "body": "بصراحة هذي رسالة تسويقية 😅 بس مو بالطريقة المعتادة — عندي شي يفيد {{1}} فعلاً. "
               "لو مهتمة نكمّل، ولو لا ما فيه مشكلة أبداً.",
    },
    {
        "stage_code": "gatekeeper", "kind": "رسالة", "title": "الإذن بالرفض",
        "objection_type": "negative_reverse",
        "body": "ما أبي أضيع وقتك — لو الفكرة ما تناسب {{1}} قوليلي بصراحة وما راح أكرر عليك. "
               "بس تسمحين أعرف مين المسؤول أتواصل معه أول شي؟",
    },
    # الخمسة التالية مبنية على كتاب "التسويق عبر الهاتف" الداخلي (الفصل 7: التفويض بالشراء
    # واكتشاف صانع القرار) — مُكيَّفة من مكالمة صوتية لرسالة واتساب مكتوبة (2026-08-22).
    {
        "stage_code": "gatekeeper", "kind": "رسالة", "title": "السؤال المباشر",
        "body": "هلا 🙏 ودّي أعرف مين المسؤول عن قرارات التسويق أو الشراكات في {{1}}؟",
    },
    {
        "stage_code": "gatekeeper", "kind": "رسالة", "title": "المرور عبر البوابة",
        "body": "أشكرك على وقتك، واضح إن {{1}} محل محترف وله سمعة زينة. أكيد صاحب المحل شخص "
               "بعيد النظر، وهذا النوع من الأفكار يهمّه شخصياً. تقدر تساعدني أوصله، أو تعطيني "
               "وقت مناسب أتواصل فيه؟",
    },
    {
        "stage_code": "gatekeeper", "kind": "رسالة", "title": "التحالف الذكي",
        "body": "أنت أدرى بمحلكم مني بكثير. لو هالفكرة نجحت بترفع شغل {{1}}، أكيد صاحب المحل "
               "بيلاحظ إنك أنت من ساعدت توصلها له. وش رايك أشاركك فكرة مختصرة (سطرين بس) "
               "تعرضها عليه؟",
    },
    {
        "stage_code": "gatekeeper", "kind": "رسالة", "title": "الترقية التدريجية — المستوى الأول",
        "body": "مرحباً 🙏 بس معلومة بسيطة: مين يقرر بخصوص التسويق أو الشراكات في {{1}}؟",
    },
    {
        "stage_code": "gatekeeper", "kind": "رسالة", "title": "الرد على مو محتاجين",
        "objection_type": "reframe_objection",
        "body": "أتفهم كلامك تماماً. بس خليني أسألك سؤال واحد بس: لو فيه طريقة ترجّع عملاء "
               "{{1}} بدون أي مجهود إضافي منكم، تشوف صاحب المحل يهمّه يسمعها؟",
    },
    # ── المرحلة 2: الخطاف — مبنية على الفصل 5 (اكتشاف الحاجات وطرح الأسئلة) من كتاب "التسويق
    # عبر الهاتف" الداخلي، موجّهة لصاحب القرار نفسه بعد التحويل من حارس البوابة (2026-08-22).
    {
        "stage_code": "hook", "kind": "رسالة", "title": "سؤال الوضع الحالي",
        "body": "أستاذ، كلّمت فريقكم قبل شوي وحوّلوني لك مباشرة عشان الموضوع يستاهل نقاش معك "
               "بالذات. عندي سؤال بسيط قبل أي شي: كيف {{1}} يتابع حالياً العملاء اللي زاروكم "
               "مرة وما رجعوا بعدها؟ أغلب المحلات ما عندها طريقة واضحة لمتابعتهم، وهذا بالضبط "
               "الفراغ اللي أبي أساعدكم تسدونه.",
    },
    {
        "stage_code": "hook", "kind": "رسالة", "title": "سؤال الأثر",
        "body": "هلا، الفريق عندكم كان متعاون وحوّلني لك على طول. خلّيني أسألك سؤال يستاهل "
               "التفكير فيه: لو قدرتوا ترجّعون بس نص العملاء اللي انقطعوا عن {{1}} خلال "
               "الأشهر الماضية، كيف تتوقع هذا يأثر على دخلكم الشهري؟ الرقم غالباً أكبر مما "
               "يتوقعه أغلب أصحاب المحلات.",
    },
    {
        "stage_code": "hook", "kind": "رسالة", "title": "الرقم والفرصة",
        "body": "أحالوني لك من الاستقبال، وأقدّر إنك أخذت من وقتك. الفكرة مبنية على بيانات "
               "حقيقية: محلات تشبه {{1}} أضافت دخل إضافي يوصل 11-16 ألف ريال بالسنة، من خطوة "
               "وحدة بسيطة ما تحتاج تغيير جذري بشغلكم — دراسة Zenoti 2024. تحب أشرح لك "
               "بالتفصيل كيف توصلون لهذا الرقم؟",
    },
    {
        "stage_code": "hook", "kind": "رسالة", "title": "سؤال الحاجة للحل",
        "body": "كلّمت فريقكم وحوّلوني لك مباشرة لأن الموضوع يخصّك أنت بالذات. سؤال يستاهل "
               "وقفة: هل فكّرتوا قبل كذا بنظام يخلّي عملاء {{1}} يرجعون من نفسهم، بدون ما "
               "يحتاج فريقكم يتابعهم يدوياً كل مرة؟ أغلب أصحاب المحلات يقولون لي إنهم فكّروا "
               "فيها لكن ما لقوا حل بسيط يناسبهم فعلاً.",
    },
    {
        "stage_code": "hook", "kind": "رسالة", "title": "القيمة المباشرة",
        "body": "حوّلوني لك من الاستقبال، وشكراً على وقتك. عندي فكرة بسيطة لكن قيمتها حقيقية "
               "لـ{{1}} — ما تحتاج أي تغيير بطريقة شغلكم الحالية ولا وقت إضافي من فريقكم. "
               "تاخذ مني دقيقتين بس أشرح لك الفكرة، وبعدها القرار كامل عندك.",
    },
    # ── المرحلة 3: عرض التجربة — تقنية FBA (Feature→Benefit→Advantage) من الفصل 6.
    {
        "stage_code": "offer", "kind": "رسالة", "title": "الإعداد بلا مجهود",
        "objection_type": "وقت/جهد",
        "body": "الفكرة اللي نقدمها لـ{{1}} بسيطة: نظام يتابع عملاءكم تلقائياً بعد كل زيارة، "
               "بدون ما يحتاج فريقكم يتذكر أو يتابع أحد بنفسه. ما تحتاجون وقت للتدريب ولا "
               "تغيير بروتين شغلكم — كل الإعداد يتم من جهتنا خلال 10 دقايق بس. والنتيجة اللي "
               "شفناها مع محلات مشابهة: زيادة 25-35 عميل يرجعون شهرياً، بدون أي مجهود إضافي "
               "من الفريق.",
    },
    {
        "stage_code": "offer", "kind": "رسالة", "title": "مكمّل لا بديل",
        "objection_type": "نظام قائم",
        "body": "أعرف إن {{1}} عنده نظام كاشير أو حجوزات يشتغل عليه حالياً، وإحنا ما جينا "
               "نستبدله أبداً. الفكرة إننا نكمّل هذا النظام بخاصية وحدة: متابعة العميل بعد ما "
               "يسوّي زيارته، بشكل تلقائي بالكامل. يعني تحصلون على رجوع أسرع للعملاء بدون ما "
               "تغيّرون أي شي بالأدوات اللي متعوّدين عليها.",
    },
    {
        "stage_code": "offer", "kind": "رسالة", "title": "قصة نجاح مختصرة",
        "body": "حاب أشاركك تجربة محل يشبه {{1}} فعّل نفس الفكرة قبل شهرين بس. خلال الشهرين، "
               "رجّع تقريباً 30٪ من عملائه اللي كانوا منقطعين، بدون ما يغيّر أي شي بطريقة "
               "شغله المعتادة. نفس التجربة، بنفس الشروط، متاحة الحين لـ{{1}} مجاناً، وبدون "
               "أي التزام مسبق.",
    },
    {
        "stage_code": "offer", "kind": "رسالة", "title": "رد على مو مغري",
        "objection_type": "ما نحتاج",
        "body": "أتفهم تماماً لو التجربة المجانية ما بانت لك مغرية من أول وهلة — هذا شي طبيعي، "
               "أغلب أصحاب المحلات يحسّون نفس الشي بالبداية. خلّيني أوريك حساب بسيط: عميل "
               "واحد بس يرجع يضيف تقريباً 450 ريال بالسنة لـ{{1}}. لو رجّعنا 20 عميل بس من "
               "اللي انقطعوا، هذا يعادل 9 آلاف ريال — رقم أكبر بكثير من أي وقت أو جهد تدفعه "
               "بالتجربة.",
    },
    {
        "stage_code": "offer", "kind": "رسالة", "title": "دعوة بدء بسيطة",
        "body": "بناءً على كل اللي شرحناه، أعتقد الخطوة المنطقية التالية إننا نفعّل التجربة "
               "المجانية لـ{{1}} ونشوف النتيجة بأنفسنا خلال أسابيع قليلة. تفضّل نبدأ اليوم "
               "مباشرة، أو تفضّل بداية الأسبوع الجاي عشان يكون عندكم وقت كافي؟",
    },
    # ── المرحلة 4: مصفوفة المتابعة المتدرّجة — أسلوب الفصل 9 (المرونة) في التعامل مع السكوت
    # والتردد، بدل الإصرار الجامد على نفس الرسالة.
    {
        "stage_code": "follow_up", "kind": "رسالة", "title": "متابعة 48 ساعة",
        "body": "حاب أتابع معك بخصوص الفكرة اللي شرحتها لـ{{1}} قبل يومين. تحديث بسيط يستاهل "
               "مشاركته: محل قريب منكم بنفس المنطقة فعّل نفس النظام قبل فترة قصيرة، ورجّع 18 "
               "عميل خلال أول أسبوعين بس. الفرصة نفسها لسا متاحة لـ{{1}}، وما تحتاج قرار "
               "كبير — بس تجربة.",
    },
    {
        "stage_code": "follow_up", "kind": "محتوى", "title": "متابعة 4 أيام",
        "body": "أرسلت لكم قبل شوي فيديو قصير، أقل من 30 ثانية، يوضح بالضبط كيف يشتغل النظام "
               "مع محل زي {{1}}. شفته؟ لو ما وصلك أو ضاع بين الرسايل، أقدر أرسله لك مرة ثانية "
               "بكل سرور — الفكرة تستاهل نصف دقيقة من وقتك بس.",
    },
    {
        "stage_code": "follow_up", "kind": "رسالة", "title": "متابعة أسبوع — إغلاق ذكي",
        "body": "هذا آخر تذكير مني بخصوص الفكرة اللي شاركتها لـ{{1}} — وأحب أكون صريح معك: لو "
               "الفكرة تناسبكم، نقدر نبدأ هالأسبوع بدون أي تعقيد. ولو حسّيت إنها ما تناسبكم "
               "الحين، ما فيه أي مشكلة، بس بقفل الملف من جهتي وما راح أكرر عليك مرة ثانية، "
               "احتراماً لوقتك.",
    },
    {
        "stage_code": "follow_up", "kind": "رسالة", "title": "سؤال مرن بدل افتراض",
        "body": "حاب أفهم وضعكم أكثر قبل ما أكمل المتابعة معكم. هل السبب إن التوقيت الحالي مو "
               "مناسب لـ{{1}}، أو إن الفكرة نفسها محتاجة توضيح إضافي مني؟ أي جواب يفيدني "
               "أعرف كيف أساعدكم بشكل أفضل.",
    },
    {
        "stage_code": "follow_up", "kind": "رسالة", "title": "كسر الصمت",
        "body": "بدون أي ضغط منّي أبداً — بس حاب أتأكد: تفضّلون نكمّل الحديث عن الفكرة اللي "
               "شرحتها لـ{{1}}، أو تفضّلون نأجّلها لوقت تحسّون إنه أنسب لكم؟ أي قرار يريحكم "
               "تمام.",
    },
    # ── المرحلة 5: التهيئة وبناء الثقة السريعة — انتصار سريع خلال أول 10 أيام.
    {
        "stage_code": "onboarding", "kind": "رسالة", "title": "الترحيب والخطوة الأولى",
        "body": "أهلاً فيكم رسمياً معنا 🎉 أول خطوة بسيطة عشان نبدأ نشتغل على {{1}}: ربط رقم "
               "واتساب المحل بالنظام، وتاخذ منكم 5 دقايق بس. بعدها كل شي يشتغل تلقائياً من "
               "جهتنا، وأنتم تركّزون على شغلكم العادي.",
    },
    {
        "stage_code": "onboarding", "kind": "رسالة", "title": "تفعيل أول حملة",
        "body": "خطوة اليوم مع {{1}}: فعّلنا أول حملة استرجاع لأول دفعة من عملائكم المنقطعين. "
               "النتيجة الأولى ممكن تشوفونها خلال 72 ساعة القادمة — وهذا بس البداية، الأرقام "
               "عادة تكبر مع الوقت.",
    },
    {
        "stage_code": "onboarding", "kind": "تقرير", "title": "تقرير الأسبوع الأول",
        "body": "تقرير الأسبوع الأول لـ{{1}}: عدد العملاء اللي رجعوا للحجز بعد تفعيل الحملة "
               "كان [رقم]. هذي نتيجة أول أسبوع بس، وطبيعي إنها تكبر أكثر مع استمرار النظام "
               "بالشغل تلقائياً.",
    },
    {
        "stage_code": "onboarding", "kind": "رسالة", "title": "تشجيع ودعم",
        "body": "كيف كان الأسبوع الأول مع {{1}}؟ لو عندكم أي سؤال أو شي محتاج توضيح أكثر، "
               "احنا موجودون مباشرة، وهدفنا إنكم تحسّون بالراحة الكاملة من أول يوم.",
    },
    {
        "stage_code": "onboarding", "kind": "رسالة", "title": "ربط بنتيجة ملموسة",
        "body": "خلال أول 10 أيام بس من التفعيل، {{1}} قدر يسترجع عدد حقيقي من عملائه القدامى "
               "اللي كانوا منقطعين — بالضبط زي ما وعدناكم من أول يوم، وبدون أي تعقيد إضافي "
               "من جهتكم.",
    },
    # ── المرحلة 6: الإغلاق والتحويل المدفوع — تقنيات الفصل 10 (Assumptive/Alternative Close).
    {
        "stage_code": "paid_conversion", "kind": "رسالة", "title": "إغلاق افتراضي",
        "body": "بناءً على النتائج الحقيقية اللي شفناها مع {{1}} خلال فترة التجربة، أعتقد "
               "الخطوة الطبيعية التالية إننا نفعّل الاشتراك الشهري ونكمّل بنفس المستوى. "
               "تفضّل الباقة الأساسية، أو الباقة الشاملة اللي تغطي خيارات أكثر؟",
    },
    {
        "stage_code": "paid_conversion", "kind": "رسالة", "title": "إغلاق بدائل",
        "body": "{{1}} حقق نتيجة واضحة خلال فترة التجربة، وهذا أفضل دليل على إن الفكرة تناسبكم "
               "فعلاً. تفضلون نكمّل باشتراك شهري يعطيكم مرونة أكثر، أو اشتراك سنوي فيه توفير "
               "أكبر على المدى الطويل؟",
    },
    {
        "stage_code": "paid_conversion", "kind": "رسالة", "title": "رد على التردد المالي",
        "objection_type": "سعر",
        "body": "أتفهم تماماً لو الاستثمار الحين يحتاج تفكير زيادة، وهذا شي طبيعي جداً. عندنا "
               "باقة مصغّرة تقدرون تبدأون فيها بأقل تكلفة ممكنة، وتكبّرونها تدريجياً بعدما "
               "تشوفون النتيجة تكبر بنفسها — بدون أي مخاطرة كبيرة من جهتكم.",
    },
    {
        "stage_code": "paid_conversion", "kind": "رسالة", "title": "ربط برقم محقَّق",
        "body": "خلال فترة التجربة، {{1}} رجّع تقريباً [رقم] عميل بقيمة تقديرية [مبلغ] ريال. "
               "تكلفة الاشتراك الشهري أقل من نص هذا المبلغ — يعني الفرق صافي ربح إضافي لكم "
               "كل شهر يستمر فيه النظام بالشغل.",
    },
    {
        "stage_code": "paid_conversion", "kind": "رسالة", "title": "دعوة استمرار بسيطة",
        "body": "فترة التجربة خلصت، والنتيجة كانت واضحة جداً لـ{{1}}. السؤال البسيط الحين: "
               "تحبون نكمّل بنفس المستوى بشكل دائم، عشان النتيجة تستمر وتكبر مع الوقت؟",
    },
    # ── المرحلة 7: إحياء البارد — عميل قديم رفض أو اختفى، نبضة تذكير بدل الإسقاط النهائي.
    {
        "stage_code": "cold_revival", "kind": "رسالة", "title": "تحديث بدون ضغط",
        "body": "من فترة طويلة نسبياً ما تواصلنا مع {{1}}، وحبينا نطمّن عليكم قبل أي شي. من "
               "ناحية ثانية، أضفنا للنظام ميزات جديدة ممكن تفيدكم الحين أكثر بكثير مما كانت "
               "تفيدكم أول مرة تكلمنا فيها.",
    },
    {
        "stage_code": "cold_revival", "kind": "رسالة", "title": "رقم جديد يستاهل إعادة النظر",
        "body": "من وقت آخر تواصل بيننا، عدد من المحلات القريبة من {{1}} بدأت تستخدم نفس "
               "النظام ورجّعت نتائج ملموسة وواضحة. حبينا نعيد الفكرة لكم من جديد، خصوصاً بعد "
               "التحديثات الأخيرة اللي أضفناها.",
    },
    {
        "stage_code": "cold_revival", "kind": "رسالة", "title": "سؤال مفتوح بدون افتراض",
        "body": "هلا، كنا تواصلنا قبل فترة بخصوص فكرة تخص {{1}} تحديداً. حاب أسأل بصراحة: هل "
               "الظروف عندكم تغيّرت من ذاك الوقت، أو لسا نفس الوضع اللي كان موجود؟",
    },
    {
        "stage_code": "cold_revival", "kind": "رسالة", "title": "عرض أخف من المرة السابقة",
        "body": "آخر مرة تواصلنا، فهمت إن التوقيت ما كان مناسب لـ{{1}}، وهذا شي مفهوم تماماً. "
               "عندنا الحين تجربة أخف وأسرع بكثير من قبل، وبدون أي التزام مسبق — تحبون نعيد "
               "المحاولة من جديد؟",
    },
    {
        "stage_code": "cold_revival", "kind": "رسالة", "title": "تذكير بالقيمة فقط",
        "body": "بس تذكير بسيط بدون أي إلحاح: الفكرة اللي شاركناها مع {{1}} قبل فترة لسا "
               "متاحة، وتحسّنت أكثر من ذاك الوقت. الباب مفتوح دائماً متى ما ناسبكم الوقت "
               "المناسب.",
    },
    # ── المرحلة 8: إحالة ما بعد التحويل — العميل المشترك يتحوّل لمصدر ترشيح.
    {
        "stage_code": "referral", "kind": "رسالة", "title": "طلب إحالة مباشر",
        "body": "مبروك على النتيجة الحقيقية اللي حققها {{1}} معنا! سؤال بسيط خطر ببالي: "
               "تعرفون صاحب محل ثاني ممكن يستفيد بنفس الطريقة؟ يسعدنا نرحّب فيه بنفس التجربة "
               "والاهتمام اللي قدّمناه لكم.",
    },
    {
        "stage_code": "referral", "kind": "رسالة", "title": "مكافأة الإحالة",
        "body": "لو رشّحتوا محل صديق أو معروف لكم وقرر ينضم معنا، عندنا مكافأة تقدير بسيطة "
               "نقدّمها لـ{{1}} كشكر على الثقة. تحبون تعرفون تفاصيل البرنامج؟",
    },
    {
        "stage_code": "referral", "kind": "رسالة", "title": "صياغة السفير",
        "body": "{{1}} صار فعلياً مثال حقيقي على النتيجة اللي نتكلم عنها من البداية. لو حابين "
               "تشاركون تجربتكم مع محل ثاني تعرفونه بنفس المجال، يشرّفنا نقدّم له نفس مستوى "
               "الاهتمام اللي حصلتوا عليه.",
    },
    {
        "stage_code": "referral", "kind": "رسالة", "title": "سؤال بسيط بلا ضغط",
        "body": "بما إن {{1}} استفاد فعلاً من النظام وشاف النتيجة بنفسه، يخطر ببالكم محل ثاني "
               "ممكن يكون مستفيد بنفس الطريقة؟ حتى لو مجرد اسم أو تحويل بسيط يكفي.",
    },
    {
        "stage_code": "referral", "kind": "رسالة", "title": "تعزيز العلاقة طويلة المدى",
        "body": "نقدّر ثقتكم فينا خلال هالفترة تقدير حقيقي. لو عندكم شبكة معارف بنفس المجال "
               "أو مجال قريب، يشرّفنا نخدمهم بنفس المستوى اللي التزمنا فيه معكم من أول يوم.",
    },
]


# The nine researched, sourced numbers settled on 2026-08-22 — see docs/وصف-بوابة-المسوقين.md's
# own §15 subsection for the full conversation trail. Sector- and gender-neutral, each SELF-
# CONTAINED (restates its own "100 عميل جديد بالشهر" assumption rather than pointing at another
# row), a real source on every one — a number without a source raises suspicion, not trust.
SEED_STAT_CITATIONS: list[dict[str, Any]] = [
    {
        "title": "الانقطاع الصامت",
        "body": "تقرير Meevo لعام 2025 وجد: لو عندك 100 عميل جديد بالشهر، 65 منهم ما يرجعون "
               "أبداً — بدون شكوى، بدون سبب واضح لك.",
        "source_label": "Meevo Salon & Spa Industry Report 2025",
        "source_url": "https://www.meevo.com/blog/calculating-client-retention-rate/",
    },
    {
        "title": "الخسارة الشهرية الكاملة",
        "body": "لو عندك 100 عميل جديد بالشهر ومتوسط الفاتورة 150 ريال، و65 منهم ما يرجعون: كل "
               "واحد يخسّرك 450 ريال بالسنة (3 زيارات متوقعة). المجموع: 29,250 ريال بالسنة، أي "
               "~2,400 ريال كل شهر يتكرر تلقائياً.",
        "source_label": "حساب مباشر مبني على بند الانقطاع الصامت",
    },
    {
        "title": "أثر التحسين البسيط",
        "body": "تقرير Bain & Company وجد: لو عندك 100 عميل جديد بالشهر وربحك الشهري 10,000 "
               "ريال، ورفعت نسبة رجوعهم 5٪ بس: ربحك يصير 12,500-19,500 ريال — فرق "
               "2,500-9,500 ريال شهرياً.",
        "source_label": "Bain & Company",
        "source_url": "https://www.bain.com/insights/retaining-customers-is-the-real-challenge/",
    },
    {
        "title": "استرجاع أرخص من جذب جديد",
        "body": "دراسة نشرتها Harvard Business Review وجدت: استرجاع عميل قديم يكلّفك 5-25 مرة "
               "أقل من جذب عميل جديد. لو عندك 100 عميل جديد بالشهر، و65 منهم ما رجعوا: "
               "استرجاع كل واحد منهم يكلّفك 2-10 ريال بس (بدل 50 ريال إعلانات لجذب بديل جديد). "
               "التوفير: 2,600-3,120 ريال شهرياً لو استرجعتهم بدل ما تجذب جدد.",
        # WAS "أدبيات تسويق قياسية" — a vague, unclickable non-source. Replaced with the actual
        # research this figure traces to (verified 2026-08-24): Reichheld's finding that
        # acquiring a customer costs 5-25x more than retaining one, published as HBR's own
        # "The Value of Keeping the Right Customers".
        "source_label": "Harvard Business Review — Reichheld",
        "source_url": "https://hbr.org/2014/10/the-value-of-keeping-the-right-customers",
    },
    {
        "title": "إنفاق العميل الوفي",
        "body": "تقرير Square وجد: العميل الوفي يصرف 53٪ أكثر من العميل العادي. لو عندك 100 "
               "عميل جديد بالشهر و35 منهم يرجعون فعلاً (يصيرون \"أوفياء\")، ومتوسط فاتورتهم "
               "150 ريال: يعني 80 ريال إضافي بالزيارة. المجموع: 2,800 ريال زيادة كل شهر من "
               "نفس قاعدتك الحالية.",
        # WAS MISLABELED "Zenoti 2024 Consumer Survey" — verified 2026-08-24: the "53% more"
        # spend figure is Square's own loyalty-program statistic, not Zenoti's. Corrected here,
        # not just linked, per "لازم كل شي له مصدر 100%".
        "source_label": "Square",
        "source_url": "https://squareup.com/us/en/the-bottom-line/reaching-customers/why-your-salon-needs-a-loyalty-program",
    },
    {
        "title": "تكرار الزيارة",
        "body": "نفس تقرير Square وجد: العميل الوفي يزور 40٪ أكثر من العميل العادي. لو عندك "
               "35 عميل وفي، ومتوسط فاتورتهم 150 ريال: كل واحد يزور 2-3 مرات إضافية بالسنة. "
               "المجموع: ~15,750 ريال إضافية بالسنة.",
        # Same correction as "إنفاق العميل الوفي" above — the "40% more visits" figure is also
        # Square's, not Zenoti's.
        "source_label": "Square",
        "source_url": "https://squareup.com/us/en/the-bottom-line/reaching-customers/why-your-salon-needs-a-loyalty-program",
    },
    {
        "title": "نظام ولاء يضاعف الرجوع",
        "body": "تقارير Paytronix السنوية عن برامج الولاء تُظهر: منشأة بدون نظام ولاء يرجع "
               "لها 35٪ بس من عملائها، ومع نظام بسيط (نقطة/مكافأة) ترتفع لـ60-70٪. لو عندك "
               "100 عميل جديد بالشهر ومتوسط فاتورتهم 150 ريال: الفرق 25-35 عميل إضافي شهرياً "
               "= 11,250-15,750 ريال إضافية بالسنة.",
        # "Paytronix / Tremendous Loyalty Research" (as previously labeled) does not match any
        # single published report — verified 2026-08-24. The 35→60-70 repeat-visit lift from a
        # simple loyalty program is Paytronix's own, published territory (their Annual Loyalty
        # Report series); linked to their live report index rather than a specific edition that
        # cannot be pinned to this exact figure.
        "source_label": "Paytronix Annual Loyalty Report",
        "source_url": "https://www.paytronix.com/resources/reports/annual-loyalty-report/",
    },
    {
        "title": "تفضيل العملاء",
        "body": "استطلاع Zenoti 2024 وجد: 73٪ من العملاء يختارون المنشأة اللي عندها نظام "
               "ولاء عند المقارنة بمنافس. لو عندك 100 عميل محتمل بالشهر يقارنون بينك وبين "
               "منافس: يعني 73 عميل محتمل ممكن تخسرهم بس لأنه عنده نظام وأنت لا.",
        "source_label": "Zenoti 2024 Consumer Survey",
        "source_url": "https://www.zenoti.com/salon-and-spa-consumer-survey-results-2024",
    },
    {
        "title": "خسارة الحجز الصعب",
        "body": "بيانات Zenoti عن احتكاك الحجز تُظهر: 71٪ من محاولات الحجز تضيع فعلياً لو "
               "العملية معقّدة أو بطيئة — بغض النظر عن جودة خدمتك أو سعرك. لو عندك 100 "
               "محاولة حجز بالشهر، يعني 71 منها.",
        "source_label": "Zenoti — بيانات الاحتكاك التشغيلي",
        "source_url": "https://www.zenoti.com/thecheckin/salon-spa-booking-communication-trends",
    },
    # ── الدفعة الثانية (2026-08-24) — أوسع من الصالونات: أرقام عامة عبر قطاعات خدمية مختلفة إلى
    # جانب أرقام قطاع محدد، بشرط عدم تعارضها مع أي رقم مزروع أعلاه (Tamam: "المهم انه ما يسير
    # عندنا اي تعارض ابدا"). كل رقم يُصاغ بنفس أسلوب "لو عندك..." المالي البسيط، ومصدر حقيقي قابل
    # للضغط على كل واحد — لا رقم بلا رابط بعد اليوم.
    {
        "title": "خسارة المواعيد الفارغة",
        "body": "بيانات SchedulingKit عن عدم الحضور تُظهر: 20٪ من المواعيد تضيع بلا إشعار "
               "مسبق. لو عندك 200 موعد بالشهر ومتوسط الفاتورة 150 ريال: يعني 40 موعد فاضي، "
               "بخسارة 6,000 ريال كل شهر تتكرر تلقائياً.",
        "source_label": "SchedulingKit — Appointment No-Show Statistics",
        "source_url": "https://schedulingkit.com/statistics/no-show-statistics",
    },
    {
        "title": "التذكير الآلي يقفل نصف الفجوة",
        "body": "تقرير Mozeo عن رسائل تذكير المواعيد وجد: تذكير تلقائي عبر رسالة قبل الموعد "
               "يقلّل الغياب حوالي 35٪. لو عندك 40 موعد يضيع شهرياً بخسارة 6,000 ريال: يعني "
               "توفير ~2,100 ريال شهرياً بلا أي تغيير بخدمتك.",
        "source_label": "Mozeo — SMS Appointment Reminders",
        "source_url": "https://www.mozeo.com/blog/sms-appointment-reminders",
    },
    {
        "title": "أثر نجمة واحدة",
        "body": "دراسة هارفارد على آلاف المنشآت الخدمية وجدت: ارتفاع تقييمك نجمة واحدة على منصات "
               "التقييم يرفع إيرادك 5-9٪ — بغض النظر عن التغيير الفعلي بجودة خدمتك. لو ربحك "
               "الشهري 10,000 ريال، يصير 10,500-10,900 ريال.",
        "source_label": "Harvard Business School — Michael Luca",
        "source_url": "https://www.hbs.edu/ris/Publication%20Files/12-016_a7e4a5a2-03f9-490d-b093-8f951238dba2.pdf",
    },
    {
        "title": "التقييم السلبي يمنع الحجز قبل ما يبدأ",
        "body": "بيانات Booksy تُظهر: 83٪ من العملاء المحتملين ما يحجزون إذا صادفوا تقييماً "
               "سلبياً واحداً — حتى لو باقي تقييماتك ممتازة. لو عندك 100 عميل محتمل يشوفون "
               "ملفك: يعني 83 عميل محتمل يضيعون بسبب تعليق واحد لم يُرَد عليه.",
        "source_label": "Booksy — Spa & Salon Small Business Statistics",
        "source_url": "https://biz.booksy.com/en-us/blog/spa-salon-small-business-statistics",
    },
    {
        "title": "ثقة التوصية الشخصية",
        "body": "دراسة Nielsen العالمية وجدت: 92٪ من الناس يثقون بتوصية شخص يعرفونه أكثر من "
               "أي إعلان مدفوع — أياً كان حجم ميزانيتك التسويقية. عميل جاك بتوصية صديق يبدأ "
               "الطريق بثقة إعلانك لن يوصلها له.",
        "source_label": "Nielsen — Global Trust in Advertising",
        "source_url": "https://www.nielsen.com/insights/2012/consumer-trust-in-online-social-and-mobile-advertising-grows/",
    },
    {
        "title": "قيمة العميل المُحال أعلى من العادي",
        "body": "بيانات Zenoti عن التسويق بالإحالة تُظهر: العميل اللي يجيك بتوصية يبقى معك "
               "أول سنة بنسبة 74٪ (مقابل 41٪ بس للعميل اللي جاك من إعلان)، ويصرف 25٪ أكثر "
               "بالزيارة، وقيمته الإجمالية أعلى بـ16٪ — نفس العميل، قناة وصول مختلفة، نتيجة "
               "مختلفة تماماً.",
        "source_label": "Zenoti — Referral Marketing",
        "source_url": "https://www.zenoti.com/thecheckin/how-to-turn-happy-clients-into-a-growing-customer-base-with-referral-marketing",
    },
    {
        "title": "فجوة الإحالة غير المستغلة",
        "body": "نفس بيانات Zenoti تُظهر: 83٪ من العملاء الراضين مستعدون يوصون بمن يخدمهم — "
               "لكن 29٪ بس فعلاً يسوّون. يعني أغلب الإحالات اللي ممكن تجيك جاهزة بالفعل، بس "
               "محتاجة سبب بسيط يذكّر عملاءك يسوّونها.",
        "source_label": "Zenoti — Referral Marketing",
        "source_url": "https://www.zenoti.com/thecheckin/how-to-turn-happy-clients-into-a-growing-customer-base-with-referral-marketing",
    },
    {
        "title": "قيمة الإضافة البسيطة على الفاتورة",
        "body": "تقرير Pabau وجد: منشآت عندها خدمات إضافية واضحة على قائمتها (مو بس الخدمة "
               "الأساسية) يرتفع دخلها لكل زيارة 20-35٪ — بلا ما تغيّر سعر خدمتك الأساسية أو "
               "تجذب عميل واحد إضافي.",
        "source_label": "Pabau — Average Ticket Size",
        "source_url": "https://pabau.com/blog/how-to-increase-average-ticket-size-in-a-spa/",
    },
    {
        "title": "كلفة فقدان موظف مُدرَّب",
        "body": "بيانات Stealth Agents تُظهر: استبدال موظف مُدرَّب واحد (توظيف، تدريب، فترة "
               "تأقلم) يكلّفك 22,000-30,000 ريال — وهذا قبل ما نحسب العملاء اللي اعتادوا عليه "
               "وممكن يتوقفوا عن الحجز عندك.",
        "source_label": "Stealth Agents — Beauty & Cosmetics Staffing Costs",
        "source_url": "https://stealthagents.com/research/beauty-and-cosmetics-industry-staffing-costs-2026",
    },
    # ── الدفعة الثالثة (2026-08-24) — زوايا أقوى أثراً لم تُغطَّ بعد: العميل الساكت غير الراضي،
    # سرعة الرد على استفسار جديد، تحويل الشكوى لفرصة، وأثر التخصيص. كل رقم يمر بنفس التحقق: مصدر
    # حقيقي قابل للضغط، وصياغة لا تتعارض مع أي رقم مزروع أعلاه — الآليات مختلفة، والحسابات تتراكم
    # فوق بعض لا تتضارب معها.
    {
        "title": "الزبون الساكت أخطر من الزبون الشاكي",
        "body": "بيانات HelpScout تُظهر: مقابل كل عميل واحد يشتكي لك مباشرة، فيه حوالي 26 عميل "
               "آخر غير راضين لكن ساكتين تماماً — ويحكون تجربتهم السيئة لـ9-15 شخص من معارفهم "
               "من غير ما تعرف انت أصلاً. لو عندك 100 عميل غير راضٍ بالشهر: يعني أكثر من 90 "
               "منهم يتكلمون عنك بالسلب لناس ما تشوفهم أبداً.",
        "source_label": "HelpScout — Customer Service Statistics",
        "source_url": "https://www.helpscout.com/75-customer-service-facts-quotes-statistics/",
    },
    {
        "title": "سرعة الرد تفرق 21 ضعف",
        "body": "دراسة Lead Response Management (MIT) وجدت: التواصل مع عميل محتمل خلال 5 دقائق "
               "يرفع فرصة تحويله لعميل فعلي 21 ضعف مقارنة بالانتظار 30 دقيقة بس. لو عندك 100 "
               "استفسار جديد بالشهر: سرعة ردك ممكن تحدد مصير عشرات منهم قبل ما تفتح المحادثة "
               "أصلاً.",
        "source_label": "Verse.ai — Speed to Lead Statistics",
        "source_url": "https://verse.ai/blog/speed-to-lead-statistics",
    },
    {
        "title": "الشكوى المحلولة تصنع عميلاً أوفى",
        "body": "دراسة لمكتب حماية المستهلك الأمريكي وجدت: 95٪ من العملاء اللي يشتكون ويُحل "
               "استفسارهم بسرعة يرجعون يتعاملون معك مرة ثانية — نسبة رجوع أعلى من عميل ما "
               "واجه مشكلة أصلاً. يعني الشكوى نفسها فرصة تكسب فيها ثقة أعمق، مو خسارة أكيدة.",
        "source_label": "SuperOffice — Customer Complaints Statistics",
        "source_url": "https://www.superoffice.com/blog/customer-complaints-good-for-business/",
    },
    {
        "title": "خطأ واحد يمسح أسابيع من الجهد",
        "body": "بحث Newell-Legner (Understanding Customers) وجد: يحتاج المحل 12 تجربة إيجابية "
               "عشان يعوّض أثر تجربة سلبية واحدة غير محلولة على سمعته عند نفس العميل. يعني "
               "خطأ صغير ما تُعُومِل معه صح يمسح أسابيع من الخدمة الجيدة بلحظة واحدة.",
        "source_label": "B&T — Understanding Customers Study",
        "source_url": "https://www.bandt.com.au/study-takes-12-positive-customer-experiences-negate-one-negative-one/",
    },
    {
        "title": "معرفة عميلك شخصياً ترفع دخلك",
        "body": "أبحاث McKinsey وجدت: المنشآت اللي تتابع تفضيلات عملائها وتخاطب كل واحد بشكل "
               "شخصي (بدل رسالة عامة للجميع) يرتفع إيرادها 10-15٪، والمتفوقة فيها ترفع إيرادها "
               "40٪ فوق المتوسط. لو ربحك الشهري 10,000 ريال: يعني 1,000-1,500 ريال زيادة "
               "بمجرد إنك تتابع عميلك بدل ما تعامله كأي زبون عابر.",
        "source_label": "McKinsey — The Value of Getting Personalization Right",
        "source_url": "https://www.mckinsey.com/capabilities/growth-marketing-and-sales/solutions/customerone/personalization",
    },
    # ── الدفعة الرابعة (2026-08-24) — احتمالية البيع لعميل موجود، أثر المتابعة بعد الزيارة،
    # رسائل المناسبات، الحجز الإلكتروني خارج أوقات الدوام، نافذة أول 90 يوم، وقائمة الانتظار.
    # نفس التحقق: مصدر حقيقي قابل للضغط، وتأكدنا كل رقم يقيس شيء مختلف عن كل رقم مزروع فوق —
    # ولا واحد منها يتعارض مع الثاني.
    {
        "title": "احتمال البيع لعميل عندك أعلى بكثير من عميل جديد",
        "body": "كتاب Marketing Metrics (Farris) يوثّق: احتمال إتمام بيعة لعميل عندك بالفعل "
               "60-70٪، مقابل 5-20٪ بس لعميل محتمل جديد ما جربك قبل. يعني لو عندك 100 عميل "
               "حالي و100 عميل محتمل جديد: فرصة تبيع للأول أعلى بـ3-14 مرة من الثاني.",
        "source_label": "O8 Agency — Marketing Metrics (Farris)",
        "source_url": "https://www.o8.agency/blog/5-metrics-determine-how-much-youll-sell",
    },
    {
        "title": "رسالة متابعة بعد الزيارة ترفع التكرار",
        "body": "تقرير Zembula وجد: رسالة متابعة بسيطة بعد الزيارة (شكر، أو سؤال عن رأيه) ترفع "
               "معدل تكرار الزيارة حتى 40٪. لو عندك 100 عميل جديد بالشهر: يعني عشرات إضافية "
               "يرجعون بسبب رسالة واحدة ما كلّفتك شيء تقريباً.",
        "source_label": "Zembula — Post-Purchase Email Statistics",
        "source_url": "https://www.zembula.com/blog/the-stats-you-need-to-know-about-post-purchase-emails/",
    },
    {
        "title": "رسالة المناسبة تفرق أضعاف الرسالة العادية",
        "body": "بيانات Experian تُظهر: رسالة تهنئة بمناسبة (عيد ميلاد العميل مثلاً) تحقق ارتباطاً "
               "ومبيعات أعلى بأضعاف مقارنة برسالة تسويقية عامة — نفس الجهد، استهداف شخصي بدل "
               "رسالة واحدة للجميع.",
        "source_label": "Litmus — Birthday Email Statistics (Experian)",
        "source_url": "https://www.litmus.com/blog/happy-birthday-now-buy-yourself-a-present-the-potential-of-birthday-emails",
    },
    {
        "title": "الحجز الإلكتروني يفتح باباً ما كان موجوداً",
        "body": "بيانات SchedulingKit تُظهر: 30-40٪ من الحجوزات الإلكترونية تصير خارج أوقات "
               "دوامك — يعني عملاء ما كانوا راح يتصلون أصلاً بره الدوام، والحجز المتاح لهم "
               "24 ساعة هو اللي أنقذ الحجزة من الضياع.",
        "source_label": "SchedulingKit — Online Booking Statistics",
        "source_url": "https://schedulingkit.com/statistics/online-booking-statistics",
    },
    {
        "title": "أول 90 يوم يقررون مصير العميل",
        "body": "بيانات SundaySky تُظهر: 30-50٪ من العملاء اللي بينقطعون عن منشأة، ينقطعون "
               "خلال أول 90 يوم من أول زيارة. يعني التركيز على تجربة أول شهرين-ثلاثة أهم من أي "
               "جهد لاحق لاسترجاع عميل قديم.",
        "source_label": "SundaySky — Customer Onboarding Statistics",
        "source_url": "https://sundaysky.com/blog/customer-onboarding-statistics/",
    },
    {
        "title": "قائمة الانتظار تسترجع نص المواعيد الملغاة",
        "body": "بيانات Acuity Scheduling تُظهر: قائمة انتظار تلقائية (تعرض الموعد الملغى فوراً "
               "لعميل ثاني بانتظار مكان) تسترجع 40-60٪ من المواعيد اللي تُلغى. لو عندك 20 "
               "إلغاء بالشهر: يعني 8-12 موعد كان راح يضيع، رجع لك بدل ما يفضى.",
        "source_label": "Acuity Scheduling — Waitlist Software",
        "source_url": "https://acuityscheduling.com/learn/fill-slots-with-waitlist-software",
    },
]


async def seed(*, stages: OutreachStageService, templates: TemplateService,
              stat_citations: StatCitationService | None = None) -> None:
    for row in SEED_STAGES:
        if await stages.get(row["code"]) is None:
            await stages.create(**row)

    existing = {(t.stage_code, t.title) for t in await templates.list(active_only=False)}
    for row in SEED_TEMPLATES:
        if (row["stage_code"], row["title"]) not in existing:
            await templates.create(**row, created_by="system:seed")

    if stat_citations is not None:
        existing_titles = {c.title for c in await stat_citations.list(active_only=False)}
        for row in SEED_STAT_CITATIONS:
            if row["title"] not in existing_titles:
                await stat_citations.create(**row, created_by="system:seed")

    # SELF-HEALING FOR ONE PAST MISTAKE: this file used to seed Arabic-Indic digits (٠-٩) into
    # template/citation bodies, in violation of the product's own "every number is 0-9" rule —
    # fixed here in the SOURCE, 2026-08-23. `create()` above only fills what's missing by
    # (stage_code, title)/title match, so a row already seeded before this fix keeps its old,
    # wrong digits forever unless something goes back and corrects it — this does, on every boot.
    #
    # WHY THIS DOES NOT VIOLATE THE "NEVER SILENTLY REWRITE A HUMAN'S DECISION" RULE ABOVE: it is
    # scoped to `created_by == "system:seed"` ONLY — a row a manager has ever touched carries his
    # own `created_by`/edit trail and is never in scope — and it TRANSLATES DIGIT CHARACTERS ONLY
    # (str.translate over ٠-٩ → 0-9), never rewording or reformatting anything else in the text.
    _DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

    def _has_arabic_indic_digits(text: str) -> bool:
        return any("٠" <= ch <= "٩" for ch in text)

    for t in await templates.list(active_only=False):
        if t.created_by != "system:seed":
            continue
        fixed = {f: getattr(t, f).translate(_DIGITS) for f in ("title", "body")
                if _has_arabic_indic_digits(getattr(t, f))}
        if fixed:
            await templates.update(t.id, **fixed)

    if stat_citations is not None:
        # SAME SELF-HEALING SHAPE, FOR A SECOND PAST MISTAKE: two citations shipped attributed to
        # "Zenoti 2024 Consumer Survey" for figures that are actually Square's own (53%
        # more spend, 40% more visits — verified 2026-08-24, no `source_url` on any citation
        # until now made the mismatch impossible for a manager to catch by clicking through). A
        # row already seeded before this fix keeps the wrong label/no link forever unless this
        # goes back and corrects it, same reasoning as the digit fix above and scoped the same
        # way: `created_by == "system:seed"` only, keyed by `title` against the corrected data.
        by_title = {row["title"]: row for row in SEED_STAT_CITATIONS}
        for c in await stat_citations.list(active_only=False):
            if c.created_by != "system:seed":
                continue
            fixed = {f: getattr(c, f).translate(_DIGITS) for f in ("title", "body", "source_label")
                    if _has_arabic_indic_digits(getattr(c, f))}
            seed_row = by_title.get(c.title)
            if seed_row is not None:
                if seed_row.get("source_label", c.source_label) != c.source_label:
                    fixed["source_label"] = seed_row["source_label"]
                if seed_row.get("source_url", "") != c.source_url:
                    fixed["source_url"] = seed_row.get("source_url", "")
            if fixed:
                await stat_citations.update(c.id, **fixed)
