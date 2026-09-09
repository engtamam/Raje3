"""whatsapp-assistant — admin actions declared for the platform admin panel.

The panel aggregates what every service declares HERE (it is served on /internal/manifest, so the
code is the source and the panel can never drift). See services/reminders/app/admin_actions.py for
the full shape contract (docs/contracts/admin-actions.schema.json).

/operator/config JOINED THIS FILE 2026-09-07 alongside the pre-existing credential routes below —
this used to only need the credential subset because ASSISTANT_MODEL_PROJECT/
ASSISTANT_MODEL_CREDENTIAL were the only runtime-tunable things this service had; app/runtime_policy.py
now also exists (ASSISTANT_MODEL_NAME/SOFT_DECLINE_THRESHOLD/MAX_CAROUSEL_CARDS), reached from the
console's المزوّدين الخارجيين ← الذكاء الاصطناعي ← الإدارة screen. See app/api/v1/operator.py's own
header for why both live in one file.

Each action is a PURE literal dict — safety:admin's CI gate reads it with ast.literal_eval, no
variables, no f-strings.
"""
from __future__ import annotations

from typing import Any


ADMIN_ACTIONS: list[dict[str, Any]] = [
    {
        "id": "whatsapp_assistant.operator_secrets", "label": "اعتمادات التشغيل", "method": "GET",
        "path": "/api/v1/assistant/operator/secrets", "capability": "platform.secrets", "group": "المنصة",
        # The NAMES only — a route that returned a value would put a credential in a screenshot.
        "help": "أي اعتمادات مضبوطة لهذه الخدمة (مشروع/مفتاح خدمة الذكاء الاصطناعي وما يُضاف لاحقاً)، بأسمائها لا بقيمها.",
    },
    {
        "id": "whatsapp_assistant.set_operator_secret", "label": "تعديل اعتماد", "method": "PUT",
        "path": "/api/v1/assistant/operator/secrets", "capability": "platform.secrets",
        "confirm": True, "danger": True, "group": "المنصة",
        # The previous value is gone the moment this runs, so an unrecorded rotation cannot be
        # reconstructed and an unattributable one is indistinguishable from an attacker's.
        "help": "القيمة السابقة تختفي فوراً — لا رجعة ولا نسخة. يسري فوراً بلا إعادة تشغيل.",
        "params": [
            {"name": "name", "in": "body", "type": "string", "required": True,
             "choices": [
                 {"value": "ASSISTANT_MODEL_PROJECT", "label": "مشروع الذكاء الاصطناعي (GCP)",
                  "impact": "المساعد يتوقف عن الرد على رسائل واتساب حتى يسري المشروع الجديد — "
                            "عادة فوراً، بلا إعادة تشغيل."},
                 {"value": "ASSISTANT_MODEL_CREDENTIAL", "label": "مفتاح الذكاء الاصطناعي (GCP)",
                  "impact": "المساعد يتوقف عن الرد على رسائل واتساب حتى يسري المفتاح الجديد — "
                            "عادة فوراً، بلا إعادة تشغيل."},
             ]},
            {"name": "value", "in": "body", "type": "string", "required": True},
        ],
    },
    {
        "id": "whatsapp_assistant.clear_operator_secret", "label": "حذف اعتماد", "method": "DELETE",
        "path": "/api/v1/assistant/operator/secrets/{name}", "capability": "platform.secrets",
        "params": [{"name": "name", "in": "path", "type": "string", "required": True}],
        "confirm": True, "danger": True, "group": "المنصة",
        "help": "يعيد الخدمة صامتاً إلى ما تحمله البيئة (إن وُجد) — مسح مفتاح الذكاء الاصطناعي يوقف البوت.",
    },
    {
        "id": "whatsapp_assistant.operator_config", "label": "إعدادات التشغيل", "method": "GET",
        "path": "/api/v1/assistant/operator/config", "capability": "platform.config", "group": "المنصة",
        "help": "القيم الفعّالة الآن للنموذج وسلوك المساعد — كل واحدة إما افتراضية أو مُعدَّلة يدوياً.",
    },
    {
        "id": "whatsapp_assistant.set_operator_config", "label": "تعديل إعداد تشغيل", "method": "PUT",
        "path": "/api/v1/assistant/operator/config", "capability": "platform.config",
        "confirm": True, "group": "المنصة",
        "help": "يغيّر سلوك المساعد من المحادثة التالية فوراً — بلا إعادة تشغيل.",
        "params": [
            {"name": "key", "in": "body", "type": "string", "required": True,
             "choices": [
                 {"value": "ASSISTANT_MODEL_NAME", "label": "اسم النموذج"},
                 {"value": "SOFT_DECLINE_THRESHOLD", "label": "عتبة التوقف عن الاقتراح بعد الرفض"},
                 {"value": "MAX_CAROUSEL_CARDS", "label": "أقصى عدد بطاقات بالعرض التفاعلي"},
             ]},
            {"name": "value", "in": "body", "type": "string", "required": True},
        ],
    },
    {
        "id": "whatsapp_assistant.clear_operator_config", "label": "حذف إعداد تشغيل", "method": "DELETE",
        "path": "/api/v1/assistant/operator/config/{key}", "capability": "platform.config",
        "params": [{"name": "key", "in": "path", "type": "string", "required": True}],
        "confirm": True, "group": "المنصة",
        "help": "يعود للقيمة الافتراضية المبنيّة في الخدمة.",
    },
    {
        "id": "whatsapp_assistant.persona_preview", "label": "معاينة شخصية المساعد", "method": "GET",
        "path": "/api/v1/assistant/operator/persona-preview", "capability": "platform.config",
        "group": "المنصة",
        # READ-ONLY on purpose — see operator.py's own note on this route: fixed house prose today,
        # nothing stored here yet for an operator to change.
        "help": "النص الكامل المُرسَل للنموذج كشخصية — للاطّلاع فقط، لا يُعدَّل من هنا بعد.",
        "params": [
            {"name": "shop_name", "in": "query", "type": "string", "required": False},
            {"name": "owner_notes", "in": "query", "type": "string", "required": False},
        ],
    },
    {
        "id": "whatsapp_assistant.pricing_report", "label": "استهلاك حقيقي", "method": "GET",
        "path": "/api/v1/assistant/operator/pricing/report", "capability": "platform.config",
        "group": "المنصة",
        "help": "متوسط التوكنات وعدد المحادثات الحقيقي آخر عدة أيام — كل المحلات مجتمعة إن ما "
               "حُدِّد محل، أو محل واحد فقط إن حُدِّد.",
        "params": [
            {"name": "days", "in": "query", "type": "number", "required": False},
            {"name": "tenant", "in": "query", "type": "string", "required": False},
        ],
    },
    {
        "id": "whatsapp_assistant.pricing_pending", "label": "تغييرات تسعير قادمة", "method": "GET",
        "path": "/api/v1/assistant/operator/pricing/pending", "capability": "platform.config",
        "group": "المنصة",
        "help": "كل تعديل سعر جُدوِل ولسا ما سرى.",
    },
    {
        "id": "whatsapp_assistant.schedule_pricing", "label": "جدولة تعديل سعر", "method": "POST",
        "path": "/api/v1/assistant/operator/pricing/schedule", "capability": "platform.config",
        "confirm": True, "group": "المنصة",
        # NEVER "تفعيل" LANGUAGE — see operator.py's own note: this is scheduled, never instant,
        # and the label/help text must not imply otherwise.
        "help": "يسري بعد المدة المحدَّدة، لا فوراً — عشان يُعلَم المحلات قبل ما يتغيّر السعر عليها.",
        "params": [
            {"name": "key", "in": "body", "type": "string", "required": True,
             "choices": [
                 {"value": "PRICING_AI_UNIT_UNITS_PER_HALALA", "label": "وحدات الذكاء لكل هللة"},
                 {"value": "PRICING_AI_UNIT_INPUT_MARGIN_MULTIPLIER", "label": "معامل هامش الإدخال"},
                 {"value": "PRICING_AI_UNIT_OUTPUT_MARGIN_MULTIPLIER", "label": "معامل هامش الإخراج"},
                 {"value": "PRICING_AI_UNIT_USD_TO_SAR", "label": "سعر صرف الدولار بالريال"},
                 {"value": "PRICING_AI_UNIT_MODEL_COSTS_JSON", "label": "تكلفة النماذج (JSON)"},
             ]},
            {"name": "value", "in": "body", "type": "string", "required": True},
            {"name": "effective_in_days", "in": "body", "type": "number", "required": True},
        ],
    },
    {
        "id": "whatsapp_assistant.cancel_pending_pricing", "label": "إلغاء تعديل سعر مجدوَل",
        "method": "DELETE", "path": "/api/v1/assistant/operator/pricing/pending/{key}",
        "capability": "platform.config",
        "params": [{"name": "key", "in": "path", "type": "string", "required": True}],
        "confirm": True, "group": "المنصة",
        "help": "يلغي تعديل السعر قبل ما يسري — يبقى السعر الحالي كما هو.",
    },
    {
        "id": "whatsapp_assistant.upsell_report", "label": "تقرير الترقيات (Upsell)", "method": "GET",
        "path": "/api/v1/assistant/operator/growth/upsell-report", "capability": "platform.config",
        "group": "المنصة",
        "help": "كم مرة اقترح المساعد باقة، وكم وافق العميل — لكل فرع، هذا الأسبوع مقابل اللي قبله، "
               "كل المحلات مجتمعة إن ما حُدِّد محل.",
        "params": [
            {"name": "days", "in": "query", "type": "number", "required": False},
            {"name": "tenant", "in": "query", "type": "string", "required": False},
        ],
    },
    {
        "id": "whatsapp_assistant.invoice_report", "label": "متوسط قيمة الفاتورة",
        "method": "GET", "path": "/api/v1/assistant/operator/growth/invoice-report",
        "capability": "platform.config", "group": "المنصة",
        "help": "متوسط قيمة الفاتورة لكل حجز حضره العميل وحجزه المساعد — لكل فرع، "
               "هذا الأسبوع مقابل اللي قبله. لازم تحديد محل واحد، ما فيه تجميع لكل المحلات هنا بعد.",
        "params": [
            {"name": "days", "in": "query", "type": "number", "required": False},
            {"name": "tenant", "in": "query", "type": "string", "required": True},
        ],
    },
]
