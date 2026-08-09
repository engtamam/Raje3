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
    {
        "id": "reminders.list_schedule", "label": "التذكيرات القادمة", "method": "GET",
        "path": "/api/v1/reminders/schedule", "capability": "reminders.read",
        "group": "التذكيرات",
        # SEEING COMES BEFORE ACTING. An owner asked "why did my customer get this?" cannot be
        # answered by a button; it is answered by a list. A panel that can only act is half a panel.
        "help": "من سيصله تذكير، ومتى، وعن أي خدمة.",
    },
    {
        "id": "reminders.cancel", "label": "إلغاء تذكير", "method": "DELETE",
        "path": "/api/v1/reminders/schedule/{id}", "capability": "reminders.manage",
        "params": [{"name": "id", "in": "path", "type": "string", "required": True}],
        "confirm": True, "danger": True, "group": "التذكيرات",
        "help": "يلغي تذكيراً واحداً. لا يوقف الخدمة، ولا يمنع تذكيراً قادماً عن زيارة جديدة.",
    },
    {
        "id": "reminders.list_rules", "label": "قواعد الخدمات", "method": "GET",
        "path": "/api/v1/reminders/rules", "capability": "reminders.read", "group": "القواعد",
        "help": "الفترة الحالية لكل خدمة، وكم تعلّمها النظام من سلوك العملاء.",
    },
    {
        "id": "reminders.set_rule", "label": "تعديل قاعدة خدمة", "method": "PUT",
        "path": "/api/v1/reminders/rules/{service_id}", "capability": "reminders.manage",
        "params": [{"name": "service_id", "in": "path", "type": "string", "required": True}],
        "confirm": True, "group": "القواعد",
        # Changing a rule changes what EVERY future customer of that service receives. It is the
        # highest-leverage edit an owner can make here, and the reason this one is confirmed.
        "help": "يغيّر الفترة الافتراضية وأيام الإشعار المسبق لخدمة واحدة.",
    },
    {
        "id": "reminders.log", "label": "سجل الإرسال", "method": "GET",
        "path": "/api/v1/reminders/log", "capability": "reminders.read", "group": "التذكيرات",
        # Suppressions are in this log too, WITH THEIR REASON. A message that was not sent and
        # cannot be explained is indistinguishable from a broken service (spec 8.4.2).
        "help": "ما أُرسل وما امتنع، ولماذا امتنع.",
    },
    # OURS, NOT AN ESTABLISHMENT'S. The caps in spec 8.4.2 protect every number on the product,
    # so a shop cannot raise its own — the damage from a blocked number is not the shop's alone.
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
]
