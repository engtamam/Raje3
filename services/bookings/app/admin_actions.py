"""bookings — admin actions declared for the platform admin panel (Phase 33).

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
    # ── the platform's own operator surface, inherited from _template ─────────────────────────
    # OURS, not the establishment's: these are the credentials and knobs our operators manage for
    # this service. Declared because a user-facing route with no action is a route the console
    # cannot render — and nothing anywhere fails to say so.
    {
        "id": "bookings.operator_secrets", "label": "اعتمادات التشغيل", "method": "GET",
        "path": "/api/v1/bookings/operator/secrets", "capability": "platform.secrets", "group": "المنصة",
    },
    {
        "id": "bookings.operator_secret_set", "label": "تعيين اعتماد", "method": "PUT",
        "path": "/api/v1/bookings/operator/secrets", "capability": "platform.secrets",
        "confirm": True, "group": "المنصة",
    },
    {
        "id": "bookings.operator_secret_clear", "label": "مسح اعتماد", "method": "DELETE",
        "path": "/api/v1/bookings/operator/secrets/{name}", "capability": "platform.secrets",
        "params": [{"name": "name", "in": "path", "type": "string", "required": True}],
        "confirm": True, "danger": True, "group": "المنصة",
    },
    {
        "id": "bookings.operator_config", "label": "إعدادات التشغيل", "method": "GET",
        "path": "/api/v1/bookings/operator/config", "capability": "platform.config", "group": "المنصة",
    },
    {
        "id": "bookings.operator_config_set", "label": "تعديل إعداد تشغيلي", "method": "PUT",
        "path": "/api/v1/bookings/operator/config", "capability": "platform.config",
        "confirm": True, "group": "المنصة",
    },
    {
        "id": "bookings.operator_config_clear", "label": "إرجاع إعداد لقيمته", "method": "DELETE",
        "path": "/api/v1/bookings/operator/config/{key}", "capability": "platform.config",
        "params": [{"name": "key", "in": "path", "type": "string", "required": True}],
        "confirm": True, "group": "المنصة",
    },
    {
        "id": "bookings.ping", "label": "فحص الاتصال", "method": "GET",
        "path": "/api/v1/admin/ping", "capability": "platform.secrets", "group": "المنصة",
        # From the generated scaffold and kept: what a client calls to confirm its token is accepted
        # at all, which is the first question asked when something else is failing.
        "help": "يؤكّد أن الخدمة تستقبل رمزك وتردّ.",
    },
]
