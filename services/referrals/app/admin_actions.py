"""referrals — admin actions declared for the platform admin panel (Phase 33).

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

PHASE 0 KEEPS THE SCAFFOLD'S OWN OPERATOR SECRET ROUTES, unlike loyalty and campaigns (which each
later removed their own dead SecretStore) — this service has no domain settings yet to make those
routes dead, so they are declared here rather than left undeclared and dark.
"""
from __future__ import annotations

from typing import Any


ADMIN_ACTIONS: list[dict[str, Any]] = [
    # ── the operator surface, and it is declared in every service or in none ──────────────
    {
        "id": "referrals.list_operator_secrets", "label": "قائمة أسرار التشغيل", "method": "GET",
        "path": "/api/v1/referrals/operator/secrets", "capability": "platform.secrets",
        "group": "المنصة",
        "help": "أي بيانات اعتماد مضبوطة، مع تلميح أربعة أحرف لكل واحدة — لا القيمة نفسها.",
    },
    {
        "id": "referrals.set_operator_secret", "label": "ضبط سرّ تشغيل", "method": "PUT",
        "path": "/api/v1/referrals/operator/secrets", "capability": "platform.secrets",
        "confirm": True, "danger": True, "group": "المنصة",
        "help": "يضبط أو يُدوِّر بيانات اعتماد الخدمة.",
    },
    {
        "id": "referrals.clear_operator_secret", "label": "حذف سرّ تشغيل", "method": "DELETE",
        "path": "/api/v1/referrals/operator/secrets/{name}", "capability": "platform.secrets",
        "params": [{"name": "name", "in": "path", "type": "string", "required": True}],
        "confirm": True, "danger": True, "group": "المنصة",
        "help": "يزيل بيانات الاعتماد المضبوطة يدوياً، فتعود القيمة من متغيرات البيئة.",
    },
    {
        "id": "referrals.operator_config", "label": "إعدادات التشغيل", "method": "GET",
        "path": "/api/v1/referrals/operator/config", "capability": "platform.config", "group": "المنصة",
        "help": "السياسات التي تشرح سلوك الخدمة لاحقاً.",
    },
    {
        "id": "referrals.set_operator_config", "label": "تعديل إعداد تشغيل", "method": "PUT",
        "path": "/api/v1/referrals/operator/config", "capability": "platform.config",
        "confirm": True, "group": "المنصة",
        "help": "يغيّر سلوك الخدمة من الآن فصاعداً.",
    },
    {
        "id": "referrals.clear_operator_config", "label": "حذف إعداد تشغيل", "method": "DELETE",
        "path": "/api/v1/referrals/operator/config/{key}", "capability": "platform.config",
        "params": [{"name": "key", "in": "path", "type": "string", "required": True}],
        "confirm": True, "group": "المنصة",
        "help": "يعود للافتراضي المبنيّ في الخدمة.",
    },
    {
        "id": "referrals.ping", "label": "فحص الاتصال", "method": "GET",
        "path": "/api/v1/referrals/admin/ping", "capability": "platform.secrets", "group": "المنصة",
        # From the generated scaffold and kept: what a client calls to confirm its token is accepted
        # at all, which is the first question asked when something else is failing.
        "help": "يؤكّد أن الخدمة تستقبل رمزك وتردّ.",
    },
    {
        "id": "referrals.whoami", "label": "من أنا", "method": "GET",
        "path": "/api/v1/referrals/whoami", "capability": "platform.config", "group": "المنصة",
        "help": "المنشأة والصلاحيات التي يحملها رمزك الآن.",
    },
]
