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

from app.core.outreach import OutreachStageService, TemplateService

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


async def seed(*, stages: OutreachStageService, templates: TemplateService) -> None:
    for row in SEED_STAGES:
        if await stages.get(row["code"]) is None:
            await stages.create(**row)

    existing = {(t.stage_code, t.title) for t in await templates.list(active_only=False)}
    for row in SEED_TEMPLATES:
        if (row["stage_code"], row["title"]) not in existing:
            await templates.create(**row, created_by="system:seed")
