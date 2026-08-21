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
]


# The nine researched, sourced numbers settled on 2026-08-22 — see docs/وصف-بوابة-المسوقين.md's
# own §١٥ subsection for the full conversation trail. Sector- and gender-neutral, each SELF-
# CONTAINED (restates its own "100 عميل جديد بالشهر" assumption rather than pointing at another
# row), a real source on every one — a number without a source raises suspicion, not trust.
SEED_STAT_CITATIONS: list[dict[str, Any]] = [
    {
        "title": "الانقطاع الصامت",
        "body": "لو عندك ١٠٠ عميل جديد بالشهر، ٦٥ منهم ما يرجعون أبداً — بدون شكوى، بدون سبب "
               "واضح لك.",
        "source_label": "Meevo Salon & Spa Industry Report 2025",
    },
    {
        "title": "الخسارة الشهرية الكاملة",
        "body": "لو عندك ١٠٠ عميل جديد بالشهر ومتوسط الفاتورة ١٥٠ ريال، و٦٥ منهم ما يرجعون: كل "
               "واحد يخسّرك ٤٥٠ ريال بالسنة (٣ زيارات متوقعة). المجموع: ٢٩,٢٥٠ ريال بالسنة، أي "
               "~٢,٤٠٠ ريال كل شهر يتكرر تلقائياً.",
        "source_label": "حساب مباشر مبني على بند الانقطاع الصامت",
    },
    {
        "title": "أثر التحسين البسيط",
        "body": "لو عندك ١٠٠ عميل جديد بالشهر وربحك الشهري ١٠,٠٠٠ ريال، ورفعت نسبة رجوعهم ٥٪ "
               "بس: ربحك يصير ١٢,٥٠٠-١٩,٥٠٠ ريال — فرق ٢,٥٠٠-٩,٥٠٠ ريال شهرياً.",
        "source_label": "Bain & Company",
    },
    {
        "title": "استرجاع أرخص من جذب جديد",
        "body": "لو عندك ١٠٠ عميل جديد بالشهر، و٦٥ منهم ما رجعوا: استرجاع كل واحد منهم يكلّفك "
               "٢-١٠ ريال بس (بدل ٥٠ ريال إعلانات لجذب بديل جديد). التوفير: ٢,٦٠٠-٣,١٢٠ ريال "
               "شهرياً لو استرجعتهم بدل ما تجذب جدد.",
        "source_label": "أدبيات تسويق قياسية (تكلفة اكتساب العميل مقابل الاحتفاظ)",
    },
    {
        "title": "إنفاق العميل الوفي",
        "body": "لو عندك ١٠٠ عميل جديد بالشهر و٣٥ منهم يرجعون فعلاً (يصيرون \"أوفياء\")، "
               "ومتوسط فاتورتهم ١٥٠ ريال: العميل الوفي يصرف ٥٣٪ أكثر = ٨٠ ريال إضافي بالزيارة. "
               "المجموع: ٢,٨٠٠ ريال زيادة كل شهر من نفس قاعدتك الحالية.",
        "source_label": "Zenoti 2024 Consumer Survey",
    },
    {
        "title": "تكرار الزيارة",
        "body": "لو عندك ٣٥ عميل وفي، ومتوسط فاتورتهم ١٥٠ ريال: كل واحد يزور ٢-٣ مرات إضافية "
               "بالسنة (٤٠٪ زيادة). المجموع: ~١٥,٧٥٠ ريال إضافية بالسنة.",
        "source_label": "Zenoti 2024 Consumer Survey",
    },
    {
        "title": "نظام ولاء يضاعف الرجوع",
        "body": "لو عندك ١٠٠ عميل جديد بالشهر، ومتوسط فاتورتهم ١٥٠ ريال: بدون نظام يرجع ٣٥ "
               "منهم، وبنظام بسيط (نقطة/مكافأة) يرجع ٦٠-٧٠. الفرق: ٢٥-٣٥ عميل إضافي شهرياً = "
               "١١,٢٥٠-١٥,٧٥٠ ريال إضافية بالسنة.",
        "source_label": "Paytronix / Tremendous Loyalty Research",
    },
    {
        "title": "تفضيل العملاء",
        "body": "لو عندك ١٠٠ عميل محتمل بالشهر يقارنون بين محلك ومحل منافس: ٧٣ منهم يختارون "
               "المحل اللي عنده نظام ولاء. يعني ٧٣ عميل محتمل ممكن تخسرهم للمنافس بس لأنه عنده "
               "نظام وأنت لا.",
        "source_label": "Zenoti 2024 Consumer Survey",
    },
    {
        "title": "خسارة الحجز الصعب",
        "body": "لو عندك ١٠٠ محاولة حجز بالشهر: ٧١ منها تضيع فعلياً لو العملية معقّدة أو بطيئة "
               "— بغض النظر عن جودة خدمتك أو سعرك.",
        "source_label": "Zenoti — بيانات الاحتكاك التشغيلي",
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
