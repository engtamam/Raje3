"""coworking — admin actions declared for the platform admin panel.

See `services/affiliate-service/app/admin_actions.py`'s own module doc for the full contract
(shape, what the CI gate enforces). This service's own shop-level controls (resources, join
requests, bookings, pause) are ordinary tier="user" routes a SHOP OWNER holds, not a platform
operator — so they belong in `user_actions.py`, not here. What IS here is only the platform's own
inherited operator surface (credentials/policy this service exposes to OUR OWN ops team).
"""
from __future__ import annotations

from typing import Any

ADMIN_ACTIONS: list[dict[str, Any]] = [
    {
        "id": "coworking.operator_secrets", "label": "اعتمادات التشغيل", "method": "GET",
        "path": "/api/v1/coworking/operator/secrets", "capability": "platform.secrets", "group": "المنصة",
        "help": "أسماء الاعتمادات المُخزَّنة لهذه الخدمة مع تلميح قصير لكل واحد، بلا عرض القيمة نفسها.",
    },
    {
        "id": "coworking.operator_secret_set", "label": "تعيين اعتماد", "method": "PUT",
        "path": "/api/v1/coworking/operator/secrets", "capability": "platform.secrets",
        "confirm": True, "group": "المنصة",
        "help": "يضبط أو يستبدل اعتماداً تستخدمه الخدمة — القيمة القديمة تبقى صالحة لفترة انتقالية قصيرة.",
    },
    {
        "id": "coworking.operator_secret_clear", "label": "مسح اعتماد", "method": "DELETE",
        "path": "/api/v1/coworking/operator/secrets/{name}", "capability": "platform.secrets",
        "params": [{"name": "name", "in": "path", "type": "string", "required": True}],
        "confirm": True, "danger": True, "group": "المنصة",
        "help": "يحذف اعتماداً مضبوطاً يدوياً، فترجع الخدمة لاستخدام القيمة الافتراضية.",
    },
    {
        "id": "coworking.operator_config", "label": "إعدادات التشغيل", "method": "GET",
        "path": "/api/v1/coworking/operator/config", "capability": "platform.config", "group": "المنصة",
        "help": "الإعدادات القابلة للتعديل في هذه الخدمة، بقيمتها الحالية الفعلية.",
    },
    {
        "id": "coworking.operator_config_set", "label": "تعديل إعداد تشغيلي", "method": "PUT",
        "path": "/api/v1/coworking/operator/config", "capability": "platform.config",
        "confirm": True, "group": "المنصة",
        "help": "يغيّر قيمة أحد إعدادات تشغيل هذه الخدمة.",
    },
    {
        "id": "coworking.operator_config_clear", "label": "إرجاع إعداد لقيمته", "method": "DELETE",
        "path": "/api/v1/coworking/operator/config/{key}", "capability": "platform.config",
        "params": [{"name": "key", "in": "path", "type": "string", "required": True}],
        "confirm": True, "danger": True, "group": "المنصة",
        "help": "يلغي تعديلاً سابقاً على إعداد، فترجع القيمة الافتراضية.",
    },
    {
        "id": "coworking.ping", "label": "فحص الاتصال", "method": "GET",
        "path": "/api/v1/coworking/admin/ping", "capability": "platform.secrets", "group": "المنصة",
        "help": "يؤكّد أن الخدمة تستقبل رمزك وتردّ.",
    },
    {
        "id": "coworking.whoami", "label": "من أنا", "method": "GET",
        "path": "/api/v1/coworking/whoami", "capability": "platform.config", "group": "المنصة",
        "help": "يؤكّد هوية المستدعي والصلاحيات التي يحملها رمزه الحالي تجاه هذه الخدمة.",
    },
]
