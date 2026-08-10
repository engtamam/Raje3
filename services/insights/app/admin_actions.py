"""insights — admin actions for the platform admin panel (Phase 33).

Each action is a PURE literal dict — the safety:admin gate reads it with ast.literal_eval.

WHAT IS DELIBERATELY ABSENT: anything that configures an indicator. There is nothing to configure.
Every knob this service might have had — which services complement which, what counts as weak, how
long a cycle is — is either learned from the data or already known from the catalogue (spec
§10.6.1). A settings screen here would be a screen with nothing on it.
"""
from __future__ import annotations

from typing import Any


ADMIN_ACTIONS: list[dict[str, Any]] = [
    {
        "id": "insights.operator_secrets", "label": "اعتمادات التشغيل", "method": "GET",
        "path": "/api/v1/operator/secrets", "capability": "platform.secrets", "group": "المنصة",
    },
    {
        "id": "insights.operator_secret_set", "label": "تعيين اعتماد", "method": "PUT",
        "path": "/api/v1/operator/secrets", "capability": "platform.secrets",
        "confirm": True, "group": "المنصة",
    },
    {
        "id": "insights.operator_secret_clear", "label": "مسح اعتماد", "method": "DELETE",
        "path": "/api/v1/operator/secrets/{name}", "capability": "platform.secrets",
        "params": [{"name": "name", "in": "path", "type": "string", "required": True}],
        "confirm": True, "danger": True, "group": "المنصة",
    },
    {
        "id": "insights.operator_config", "label": "إعدادات التشغيل", "method": "GET",
        "path": "/api/v1/operator/config", "capability": "platform.config", "group": "المنصة",
    },
    {
        "id": "insights.operator_config_set", "label": "تعديل إعداد تشغيلي", "method": "PUT",
        "path": "/api/v1/operator/config", "capability": "platform.config",
        "confirm": True, "group": "المنصة",
    },
    {
        "id": "insights.operator_config_clear", "label": "إرجاع إعداد لقيمته", "method": "DELETE",
        "path": "/api/v1/operator/config/{key}", "capability": "platform.config",
        "params": [{"name": "key", "in": "path", "type": "string", "required": True}],
        "confirm": True, "group": "المنصة",
    },
    # ── the owner's dashboard (spec §10) ──────────────────────────────────────────────────────
    {
        "id": "insights.platform_recompute", "label": "إعادة حساب لوحة منشأة", "method": "POST",
        "path": "/api/v1/insights/platform/recompute", "capability": "platform.insights",
        "confirm": True, "group": "المنصة",
        # OURS. Support answering "why does my dashboard say that?" for a shop not theirs.
    },
    {
        "id": "insights.ping", "label": "فحص الاتصال", "method": "GET",
        "path": "/api/v1/admin/ping", "capability": "platform.secrets", "group": "المنصة",
        # From the generated scaffold and kept: what a client calls to confirm its token is accepted
        # at all, which is the first question asked when something else is failing. Undeclared in
        # every service until a guard compared the manifest with the app.
        "help": "يؤكّد أن الخدمة تستقبل رمزك وتردّ.",
    },
]
