"""loyalty — admin actions declared for the platform admin panel (Phase 33).

The panel aggregates what every service declares HERE (served on /internal/manifest, so the code is
the source and the panel cannot drift). Each action is a PURE literal dict — the safety:admin CI
gate reads it with ast.literal_eval, so no variables and no f-strings.

Rules the gate enforces: the path must exist in this service's manifest `endpoints`, and the
capability must be advertised in the manifest's `capabilities`. The panel is a MAP, never the
AUTHORITY — every action is re-checked and re-scoped to the caller's own establishment at its own
route, on every call.

WHAT IS DELIBERATELY ABSENT: redeeming. That is the field screen's action, declared in
`user_actions`, and putting it here as well would make it a panel button — a manager spending a
customer's balance from a desk, with no customer standing there to receive the receipt that is the
only control on it (spec §9.6).
"""
from __future__ import annotations

from typing import Any


ADMIN_ACTIONS: list[dict[str, Any]] = [
    # ── the platform's own operator surface, inherited from _template ─────────────────────────
    # OURS, not the establishment's: these are the credentials and knobs our operators manage for
    # this service. Declared because a user-facing route with no action is a route the console
    # cannot render — and nothing anywhere fails to say so.
    {
        "id": "loyalty.operator_secrets", "label": "اعتمادات التشغيل", "method": "GET",
        "path": "/api/v1/loyalty/operator/secrets", "capability": "platform.secrets", "group": "المنصة",
    },
    {
        "id": "loyalty.operator_secret_set", "label": "تعيين اعتماد", "method": "PUT",
        "path": "/api/v1/loyalty/operator/secrets", "capability": "platform.secrets",
        "confirm": True, "group": "المنصة",
    },
    {
        "id": "loyalty.operator_secret_clear", "label": "مسح اعتماد", "method": "DELETE",
        "path": "/api/v1/loyalty/operator/secrets/{name}", "capability": "platform.secrets",
        "params": [{"name": "name", "in": "path", "type": "string", "required": True}],
        "confirm": True, "danger": True, "group": "المنصة",
    },
    {
        "id": "loyalty.operator_config", "label": "إعدادات التشغيل", "method": "GET",
        "path": "/api/v1/loyalty/operator/config", "capability": "platform.config", "group": "المنصة",
    },
    {
        "id": "loyalty.operator_config_set", "label": "تعديل إعداد تشغيلي", "method": "PUT",
        "path": "/api/v1/loyalty/operator/config", "capability": "platform.config",
        "confirm": True, "group": "المنصة",
    },
    {
        "id": "loyalty.operator_config_clear", "label": "إرجاع إعداد لقيمته", "method": "DELETE",
        "path": "/api/v1/loyalty/operator/config/{key}", "capability": "platform.config",
        "params": [{"name": "key", "in": "path", "type": "string", "required": True}],
        "confirm": True, "group": "المنصة",
    },
    # ── the programme's settings (spec §9.2, §9.3) ─────────────────────────────────────────────

    # ── the rewards catalogue (spec §9.4) ──────────────────────────────────────────────────────

    # ── what the owner reads (spec §9.10) ──────────────────────────────────────────────────────
    {
        "id": "loyalty.platform_reconcile", "label": "إصلاح رصيد عميل", "method": "POST",
        "path": "/api/v1/loyalty/platform/reconcile", "capability": "platform.loyalty",
        "confirm": True, "group": "المنصة",
        # The answer to "where did my points go?" — the only question this programme generates.
        # Recomputes the total from the ledger, which is the truth, and repairs a disagreement.
    },
    {
        "id": "loyalty.ping", "label": "فحص الاتصال", "method": "GET",
        "path": "/api/v1/admin/ping", "capability": "platform.secrets", "group": "المنصة",
        # From the generated scaffold and kept: what a client calls to confirm its token is accepted
        # at all, which is the first question asked when something else is failing. Undeclared in
        # every service until a guard compared the manifest with the app.
        "help": "يؤكّد أن الخدمة تستقبل رمزك وتردّ.",
    },
]
