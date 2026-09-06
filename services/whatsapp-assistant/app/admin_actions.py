"""whatsapp-assistant — admin actions declared for the platform admin panel.

The panel aggregates what every service declares HERE (it is served on /internal/manifest, so the
code is the source and the panel can never drift). See services/reminders/app/admin_actions.py for
the full shape contract (docs/contracts/admin-actions.schema.json) — this file only ever needed
the credential subset of it, because ASSISTANT_MODEL_PROJECT/ASSISTANT_MODEL_CREDENTIAL are the
runtime-tunable things this service has (see app/api/v1/assistant/operator.py's own note on why).

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
]
