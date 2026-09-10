"""whatsapp-assistant — end-user (shop) actions for the platform app catalog.

See services/reminders/app/user_actions.py for the full shape contract
(docs/contracts/user-actions.schema.json) and the "who owns the data" test for which file a route
belongs in. This service's own first entry: the app-store card's own price read
(app/api/v1/__init__.py::pricing_current) — everything else here is still operator-only
(app/admin_actions.py).

Each action is a PURE literal dict — safety:user-actions' CI gate reads it with ast.literal_eval,
no variables, no f-strings.
"""
from __future__ import annotations

from typing import Any


USER_ACTIONS: list[dict[str, Any]] = [
    {
        "id": "whatsapp_assistant.features", "label": "مميزات المساعد الذكي", "method": "GET",
        "path": "/api/v1/assistant/features", "capability": "whatsapp_assistant.pricing_read",
        "group": "التطبيقات",
        "help": "قائمة المميزات الحقيقية اللي يوفّرها المساعد الذكي عبر واتساب، بصياغة تسويقية قصيرة.",
    },
    {
        "id": "whatsapp_assistant.pricing_current", "label": "سعر الذكاء الاصطناعي", "method": "GET",
        "path": "/api/v1/assistant/pricing/current", "capability": "whatsapp_assistant.pricing_read",
        "group": "التطبيقات",
        "help": "السعر الحالي، وأي تعديل مجدوَل مع تاريخ سريانه — لا يتغيّر عليك بلا إشعار مسبق.",
    },
    {
        "id": "whatsapp_assistant.my_impact", "label": "أثر الذكاء الاصطناعي", "method": "GET",
        "path": "/api/v1/assistant/growth/my-impact", "capability": "whatsapp_assistant.pricing_read",
        "group": "التطبيقات",
        "help": "كم محادثة تحوّلت لحجز، ومتوسط قيمة الفاتورة — محلّك أنت فقط، لا تجميع مع محلات ثانية.",
        "params": [{"name": "days", "in": "query", "type": "number", "required": False}],
    },
]
