"""reminders — admin actions declared for the platform admin panel (Phase 33).

The panel aggregates what every service declares HERE (it is served on /internal/manifest, so the
code is the source and the panel can never drift). Declaring nothing is fine — a service with an
empty list simply exposes no controls; keep it empty and reviewed rather than forgotten.

Each action is a PURE literal dict (the safety:admin CI gate reads it with ast.literal_eval — no
variables, no f-strings). Shape (docs/contracts/admin-actions.schema.json):

    {
        "id": "svc.do_thing",              # stable, kebab/dot, unique
        "label": "Do the thing",           # what the button says
        "method": "POST",                  # GET|POST|PUT|PATCH|DELETE (allow-listed)
        "path": "/api/v1/things/{id}/do",  # RELATIVE — no scheme/host; must be a real manifest route
        "capability": "platform.svc",      # the cap the route ENFORCES; must be advertised in the manifest
        "params": [{"name": "id", "in": "path", "type": "string", "required": True}],
        "confirm": True,                   # UX: ask before firing (auto-true when danger)
        "danger": True,                    # UX: destructive/irreversible
        "group": "Things",                 # UX: section
    }

Rules the gate enforces: the path must exist in this service's manifest `endpoints`; the capability
must be in the manifest's advertised `capabilities`; the panel is a MAP, never the AUTHORITY — every
action is re-checked at its own route on every call. Only declare OPERATOR (platform.* / *.manage /
*.read) routes; internal-token and per-user `_SELF` routes are never panel actions.
"""
from __future__ import annotations

from typing import Any


ADMIN_ACTIONS: list[dict[str, Any]] = [
    # THE OWNER'S SURFACE. Not "settings" — these are the four questions an owner actually asks
    # about reminders, and every one of them has a wrong answer that costs a customer.
    # OURS, NOT AN ESTABLISHMENT'S. The caps in spec 8.4.2 protect every number on the product,
    # so a shop cannot raise its own — the damage from a blocked number is not the shop's alone.
    {
        "id": "reminders.silent", "label": "محلات لا ترسل", "method": "GET",
        "path": "/api/v1/platform/silent", "capability": "platform.reminders",
        # ONE ROW PER SHOP THAT HAS WORK WAITING AND CANNOT MOVE IT. «0 أُرسلت اليوم» is also what
        # a quiet Friday looks like; the conjunction is the alarm.
    },
    {
        "id": "reminders.get_limits", "label": "حدود الإرسال", "method": "GET",
        "path": "/api/v1/platform/limits", "capability": "platform.reminders",
        "group": "المنصة",
        "help": "السقوف والنافذة الزمنية وعتبات التفاعل — عالمياً أو لمنشأة بعينها.",
    },
    {
        "id": "reminders.set_limits", "label": "تعديل حدود الإرسال", "method": "PUT",
        "path": "/api/v1/platform/limits", "capability": "platform.reminders",
        "confirm": True, "danger": True, "group": "المنصة",
        "help": "يُوسَّع بسبب مكتوب فقط. رفعُه لمنشأة واحدة يُحمّل الجميع ثمنَ رقمٍ محظور.",
    },
    # ── settings, three levels deep, and the owner never picks one (spec 10.8.1) ──────────
    {
        "id": "reminders.clear_limits", "label": "إلغاء استثناء الحدود", "method": "DELETE",
        "path": "/api/v1/platform/limits", "capability": "platform.reminders",
        "confirm": True, "danger": True, "group": "المنصة",
        "help": "يعيد المنشأة إلى حدود المنصة الافتراضية.",
    },
    # ── the operator surface, and it is declared in every service or in none ──────────────
    {
        "id": "reminders.operator_secrets", "label": "اعتمادات التشغيل", "method": "GET",
        "path": "/api/v1/operator/secrets", "capability": "platform.secrets", "group": "المنصة",
        # The NAMES only — a route that returned a value would put a credential in a screenshot.
        "help": "أي اعتمادات مضبوطة لهذه الخدمة، بأسمائها لا بقيمها.",
    },
    {
        "id": "reminders.set_operator_secret", "label": "تعديل اعتماد", "method": "PUT",
        "path": "/api/v1/operator/secrets", "capability": "platform.secrets",
        "confirm": True, "danger": True, "group": "المنصة",
        # The previous value is gone the moment this runs, so an unrecorded rotation cannot be
        # reconstructed and an unattributable one is indistinguishable from an attacker's.
        "help": "القيمة السابقة تختفي فوراً — لا رجعة ولا نسخة.",
    },
    {
        "id": "reminders.clear_operator_secret", "label": "حذف اعتماد", "method": "DELETE",
        "path": "/api/v1/operator/secrets/{name}", "capability": "platform.secrets",
        "params": [{"name": "name", "in": "path", "type": "string", "required": True}],
        "confirm": True, "danger": True, "group": "المنصة",
        "help": "يعيد الخدمة صامتاً إلى ما تحمله البيئة — تغيّر سلوك لا يراه أحد.",
    },
    {
        "id": "reminders.operator_config", "label": "إعدادات التشغيل", "method": "GET",
        "path": "/api/v1/operator/config", "capability": "platform.config", "group": "المنصة",
        "help": "السياسات التي تشرح سلوك الخدمة لاحقاً.",
    },
    {
        "id": "reminders.set_operator_config", "label": "تعديل إعداد تشغيل", "method": "PUT",
        "path": "/api/v1/operator/config", "capability": "platform.config",
        "confirm": True, "group": "المنصة",
        "help": "يغيّر سلوك الخدمة من الآن فصاعداً.",
    },
    {
        "id": "reminders.clear_operator_config", "label": "حذف إعداد تشغيل", "method": "DELETE",
        "path": "/api/v1/operator/config/{key}", "capability": "platform.config",
        "params": [{"name": "key", "in": "path", "type": "string", "required": True}],
        "confirm": True, "group": "المنصة",
        "help": "يعود للافتراضي المبنيّ في الخدمة.",
    },
    {
        "id": "reminders.ping", "label": "فحص الاتصال", "method": "GET",
        "path": "/api/v1/admin/ping", "capability": "platform.secrets", "group": "المنصة",
        # From the generated scaffold and kept: what a client calls to confirm its token is accepted
        # at all, which is the first question asked when something else is failing. Undeclared in
        # every service until a guard compared the manifest with the app.
        "help": "يؤكّد أن الخدمة تستقبل رمزك وتردّ.",
    },
]
