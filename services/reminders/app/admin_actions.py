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
    # ── settings, three levels deep, and the owner never picks one (spec 10.8.1) ──────────
    {
        "id": "reminders.get_settings", "label": "إعدادات التذكير", "method": "GET",
        "path": "/api/v1/reminders/settings", "capability": "reminders.read",
        "group": "الإعدادات",
        # Carries WHERE each value came from — the screen cannot say "this one is customised, tap
        # to go back" unless the API says which level answered.
        "help": "القيم السارية، ومن أين جاءت: عام، أم مجموعة، أم خاصة بالخدمة.",
    },
    {
        "id": "reminders.set_general", "label": "الإعداد العام", "method": "PUT",
        "path": "/api/v1/reminders/settings", "capability": "reminders.manage",
        "confirm": True, "group": "الإعدادات",
        # Reaches every follower and leaves every customisation alone. An owner who spent a minute
        # setting the oil change to 60 days has not asked us to undo that minute.
        "help": "يسري على كل خدمة تتبعه. المخصّصة تبقى كما هي.",
    },
    {
        "id": "reminders.set_service_settings", "label": "تخصيص خدمة", "method": "PUT",
        "path": "/api/v1/reminders/settings/service/{service_id}",
        "capability": "reminders.manage",
        "params": [{"name": "service_id", "in": "path", "type": "string", "required": True}],
        "group": "الإعدادات",
        "help": "تعطي هذه الخدمة إعدادها الخاص، فتتوقّف عن اتّباع العام.",
    },
    {
        "id": "reminders.follow_general", "label": "العودة للعام", "method": "DELETE",
        "path": "/api/v1/reminders/settings/service/{service_id}",
        "capability": "reminders.manage",
        "params": [{"name": "service_id", "in": "path", "type": "string", "required": True}],
        "group": "الإعدادات",
        # Deletes rather than copying the general value in — copying looks identical today and
        # diverges tomorrow, when the next general edit skips this service.
        "help": "تحذف تخصيصها فتعود تتبع الإعداد العام.",
    },
    {
        "id": "reminders.set_group", "label": "مجموعة خدمات", "method": "PUT",
        "path": "/api/v1/reminders/settings/group/{name}", "capability": "reminders.manage",
        "params": [{"name": "name", "in": "path", "type": "string", "required": True}],
        "group": "الإعدادات",
        "help": "إعداد واحد لعدة خدمات متشابهة.",
    },
    {
        "id": "reminders.suggest_group", "label": "اقتراح مجموعة", "method": "GET",
        "path": "/api/v1/reminders/settings/suggest-group", "capability": "reminders.read",
        "group": "الإعدادات",
        # Proposes only. A system rearranging an owner's settings without being asked is the
        # fastest way to lose their trust in a screen.
        "help": "هل تكرّر المالك؟ نقترح، ولا نغيّر شيئاً بأنفسنا.",
    },
    {
        "id": "reminders.clear_limits", "label": "إلغاء استثناء الحدود", "method": "DELETE",
        "path": "/api/v1/platform/limits", "capability": "platform.reminders",
        "confirm": True, "danger": True, "group": "المنصة",
        "help": "يعيد المنشأة إلى حدود المنصة الافتراضية.",
    },
    # ── the operator surface, and it is declared in every service or in none ──────────────
    {
        "id": "reminders.operator_secrets", "label": "اعتمادات التشغيل", "method": "GET",
        "path": "/api/v1/operator/secrets", "capability": "platform.reminders", "group": "المنصة",
        # The NAMES only — a route that returned a value would put a credential in a screenshot.
        "help": "أي اعتمادات مضبوطة لهذه الخدمة، بأسمائها لا بقيمها.",
    },
    {
        "id": "reminders.set_operator_secret", "label": "تعديل اعتماد", "method": "PUT",
        "path": "/api/v1/operator/secrets", "capability": "platform.reminders",
        "confirm": True, "danger": True, "group": "المنصة",
        # The previous value is gone the moment this runs, so an unrecorded rotation cannot be
        # reconstructed and an unattributable one is indistinguishable from an attacker's.
        "help": "القيمة السابقة تختفي فوراً — لا رجعة ولا نسخة.",
    },
    {
        "id": "reminders.clear_operator_secret", "label": "حذف اعتماد", "method": "DELETE",
        "path": "/api/v1/operator/secrets/{name}", "capability": "platform.reminders",
        "params": [{"name": "name", "in": "path", "type": "string", "required": True}],
        "confirm": True, "danger": True, "group": "المنصة",
        "help": "يعيد الخدمة صامتاً إلى ما تحمله البيئة — تغيّر سلوك لا يراه أحد.",
    },
    {
        "id": "reminders.operator_config", "label": "إعدادات التشغيل", "method": "GET",
        "path": "/api/v1/operator/config", "capability": "platform.reminders", "group": "المنصة",
        "help": "السياسات التي تشرح سلوك الخدمة لاحقاً.",
    },
    {
        "id": "reminders.set_operator_config", "label": "تعديل إعداد تشغيل", "method": "PUT",
        "path": "/api/v1/operator/config", "capability": "platform.reminders",
        "confirm": True, "group": "المنصة",
        "help": "يغيّر سلوك الخدمة من الآن فصاعداً.",
    },
    {
        "id": "reminders.clear_operator_config", "label": "حذف إعداد تشغيل", "method": "DELETE",
        "path": "/api/v1/operator/config/{key}", "capability": "platform.reminders",
        "params": [{"name": "key", "in": "path", "type": "string", "required": True}],
        "confirm": True, "group": "المنصة",
        "help": "يعود للافتراضي المبنيّ في الخدمة.",
    },
]
