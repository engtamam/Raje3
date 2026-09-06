"""portal — admin actions for the platform admin panel (Phase 33).

NOTHING, and declared empty rather than left unwritten.

This service has three routes and all three are PUBLIC: the customer's page, his five switches, and
the one-tap unsubscribe. There is no operator surface here, no configuration, and no secret — it
holds no database at all (spec §8.6.1). A panel button pointing at this service would be a button
with nowhere to go.

WHAT WAS HERE BEFORE, AND WHY IT MATTERED. Eight actions copied from another service's template:
`/api/v1/portal/operator/config`, `/api/v1/portal/operator/secrets` and the rest, carrying `platform.operations`
— a capability this service does not advertise, for routes it does not serve, with one id declared
twice. The console would have rendered five buttons that 404.

Nothing caught it. The wiring guard checks that every user-facing ROUTE has an action; it did not
check the reverse — that every declared ACTION has a route. Guard 17 now does, and it was added
because of this file.
"""
from __future__ import annotations

from typing import Any


ADMIN_ACTIONS: list[dict[str, Any]] = [
    {
        "id": "portal.operator_config", "label": "إعدادات التشغيل", "method": "GET",
        "path": "/api/v1/portal/operator/config", "capability": "platform.config", "group": "المنصة",
        "help": "السياسات التي تشرح سلوك الخدمة لاحقاً.",
    },
    {
        "id": "portal.set_operator_config", "label": "تعديل إعداد", "method": "PUT",
        "path": "/api/v1/portal/operator/config", "capability": "platform.config",
        "confirm": True, "group": "المنصة",
        "help": "يسري فوراً على هذه الخدمة دون إعادة نشر.",
    },
    {
        "id": "portal.clear_operator_config", "label": "إلغاء إعداد", "method": "DELETE",
        "path": "/api/v1/portal/operator/config/{key}", "capability": "platform.config",
        "params": [{"name": "key", "in": "path", "type": "string", "required": True}],
        "confirm": True, "group": "المنصة",
        "help": "يعيد الإعداد إلى قيمته المنشورة.",
    },
    {
        "id": "portal.ping", "label": "فحص الاتصال", "method": "GET",
        "path": "/api/v1/portal/admin/ping", "capability": "platform.secrets", "group": "المنصة",
        # From the generated scaffold, and kept: it is what a client calls to confirm its token is
        # accepted at all, which is the first question asked when something else is failing.
        "help": "يؤكّد أن الخدمة تستقبل رمزك وتردّ.",
    },
    {
        "id": "portal.whoami", "label": "من أنا", "method": "GET",
        "path": "/api/v1/portal/whoami", "capability": "platform.config", "group": "المنصة",
        "help": "المنشأة والصلاحيات التي يحملها رمزك الآن.",
    },
]
