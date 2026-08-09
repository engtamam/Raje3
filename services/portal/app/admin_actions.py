"""portal — admin actions declared for the platform admin panel (Phase 33).

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
    # THIS SERVICE HAS NO OWNER-FACING PANEL, and that is a decision rather than an omission: it
    # renders one customer's page and stores nothing. What it DOES have is the operator surface it
    # inherits — the credentials it uses to read its three peers — and a route table built from
    # manifests that omits where credentials are set is one that hides the highest-privilege
    # surface the service has.
    {
        "id": "portal.operator_config", "label": "إعدادات التشغيل", "method": "GET",
        "path": "/api/v1/operator/config", "capability": "platform.operations",
        "group": "المنصة",
        "help": "مهلة النظراء ومدة التخزين المؤقت لهوية المحل.",
    },
    {
        "id": "portal.set_operator_config", "label": "تعديل إعدادات التشغيل", "method": "PUT",
        "path": "/api/v1/operator/config", "capability": "platform.operations",
        "confirm": True, "group": "المنصة",
        # A deadline raised past a person's patience turns a fast page into a slow one, and the
        # symptom is a customer closing the tab rather than an error anybody sees.
        "help": "مهلة الصفحة كاملة ثلاث ثوانٍ — رفعها يعني صفحة لا تُقرأ.",
    },
    # ── the operator surface, and it is declared in every service or in none ──────────────
    {
        "id": "portal.operator_secrets", "label": "اعتمادات التشغيل", "method": "GET",
        "path": "/api/v1/operator/secrets", "capability": "platform.operations", "group": "المنصة",
        # The NAMES only — a route that returned a value would put a credential in a screenshot.
        "help": "أي اعتمادات مضبوطة لهذه الخدمة، بأسمائها لا بقيمها.",
    },
    {
        "id": "portal.set_operator_secret", "label": "تعديل اعتماد", "method": "PUT",
        "path": "/api/v1/operator/secrets", "capability": "platform.operations",
        "confirm": True, "danger": True, "group": "المنصة",
        # The previous value is gone the moment this runs, so an unrecorded rotation cannot be
        # reconstructed and an unattributable one is indistinguishable from an attacker's.
        "help": "القيمة السابقة تختفي فوراً — لا رجعة ولا نسخة.",
    },
    {
        "id": "portal.clear_operator_secret", "label": "حذف اعتماد", "method": "DELETE",
        "path": "/api/v1/operator/secrets/{name}", "capability": "platform.operations",
        "params": [{"name": "name", "in": "path", "type": "string", "required": True}],
        "confirm": True, "danger": True, "group": "المنصة",
        "help": "يعيد الخدمة صامتاً إلى ما تحمله البيئة — تغيّر سلوك لا يراه أحد.",
    },
    {
        "id": "portal.operator_config", "label": "إعدادات التشغيل", "method": "GET",
        "path": "/api/v1/operator/config", "capability": "platform.operations", "group": "المنصة",
        "help": "السياسات التي تشرح سلوك الخدمة لاحقاً.",
    },
    {
        "id": "portal.set_operator_config", "label": "تعديل إعداد تشغيل", "method": "PUT",
        "path": "/api/v1/operator/config", "capability": "platform.operations",
        "confirm": True, "group": "المنصة",
        "help": "يغيّر سلوك الخدمة من الآن فصاعداً.",
    },
    {
        "id": "portal.clear_operator_config", "label": "حذف إعداد تشغيل", "method": "DELETE",
        "path": "/api/v1/operator/config/{key}", "capability": "platform.operations",
        "params": [{"name": "key", "in": "path", "type": "string", "required": True}],
        "confirm": True, "group": "المنصة",
        "help": "يعود للافتراضي المبنيّ في الخدمة.",
    },
]
