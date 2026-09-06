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
        "id": "reminders.template_help_queue", "label": "طلبات «ساعدوني»", "method": "GET",
        "path": "/api/v1/platform/template-help", "capability": "platform.reminders",
        "group": "القوالب",
        # A QUEUE NOBODY CAN SEE IS A BUTTON THAT DOES NOTHING — the owner presses, a row is
        # written, nothing answers, and he concludes the feature is decoration.
        "help": "نصوص رفضتها واتساب وطلب أصحابها المساعدة — الأحدث أولاً.",
    },
    {
        "id": "reminders.answer_template_help", "label": "أجب طلب مساعدة", "method": "POST",
        "path": "/api/v1/platform/template-help/{name}/answer",
        "capability": "platform.reminders", "group": "القوالب",
        "help": "جوابك يعود إلى الشاشة نفسها التي سأل منها.",
        "params": [{"name": "name", "in": "path", "type": "string", "required": True}],
    },
    {
        "id": "reminders.silent", "label": "محلات لا ترسل", "method": "GET",
        "path": "/api/v1/platform/silent", "capability": "platform.reminders",
        "help": "محلات لديها رسائل بانتظار الإرسال ولا تستطيع، مع سبب التعطّل لكل واحد.",
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
        "id": "reminders.operator_config", "label": "إعدادات التشغيل", "method": "GET",
        "path": "/api/v1/reminders/operator/config", "capability": "platform.config", "group": "المنصة",
        "help": "السياسات التي تشرح سلوك الخدمة لاحقاً.",
    },
    {
        "id": "reminders.set_operator_config", "label": "تعديل إعداد تشغيل", "method": "PUT",
        "path": "/api/v1/reminders/operator/config", "capability": "platform.config",
        "confirm": True, "group": "المنصة",
        "help": "يغيّر سلوك الخدمة من الآن فصاعداً.",
    },
    {
        "id": "reminders.clear_operator_config", "label": "حذف إعداد تشغيل", "method": "DELETE",
        "path": "/api/v1/reminders/operator/config/{key}", "capability": "platform.config",
        "params": [{"name": "key", "in": "path", "type": "string", "required": True}],
        "confirm": True, "group": "المنصة",
        "help": "يعود للافتراضي المبنيّ في الخدمة.",
    },
    {
        "id": "reminders.ping", "label": "فحص الاتصال", "method": "GET",
        "path": "/api/v1/reminders/admin/ping", "capability": "platform.secrets", "group": "المنصة",
        # From the generated scaffold and kept: what a client calls to confirm its token is accepted
        # at all, which is the first question asked when something else is failing. Undeclared in
        # every service until a guard compared the manifest with the app.
        "help": "يؤكّد أن الخدمة تستقبل رمزك وتردّ.",
    },
    {
        "id": "reminders.whoami", "label": "من أنا", "method": "GET",
        # The route itself enforces no capability — grouped under platform.config here only so it
        # shows up alongside the operator screens an admin already reaches. Was platform.secrets
        # until that capability's own credential routes were removed (dead SecretStore).
        "path": "/api/v1/reminders/whoami", "capability": "platform.config", "group": "المنصة",
        "help": "المنشأة والصلاحيات التي يحملها رمزك الآن.",
    },
]
