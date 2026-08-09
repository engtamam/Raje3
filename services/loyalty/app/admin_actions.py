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
        "path": "/api/v1/operator/secrets", "capability": "platform.loyalty", "group": "المنصة",
    },
    {
        "id": "loyalty.operator_secret_set", "label": "تعيين اعتماد", "method": "PUT",
        "path": "/api/v1/operator/secrets", "capability": "platform.loyalty",
        "confirm": True, "group": "المنصة",
    },
    {
        "id": "loyalty.operator_secret_clear", "label": "مسح اعتماد", "method": "DELETE",
        "path": "/api/v1/operator/secrets/{name}", "capability": "platform.loyalty",
        "params": [{"name": "name", "in": "path", "type": "string", "required": True}],
        "confirm": True, "danger": True, "group": "المنصة",
    },
    {
        "id": "loyalty.operator_config", "label": "إعدادات التشغيل", "method": "GET",
        "path": "/api/v1/operator/config", "capability": "platform.loyalty", "group": "المنصة",
    },
    {
        "id": "loyalty.operator_config_set", "label": "تعديل إعداد تشغيلي", "method": "PUT",
        "path": "/api/v1/operator/config", "capability": "platform.loyalty",
        "confirm": True, "group": "المنصة",
    },
    {
        "id": "loyalty.operator_config_clear", "label": "إرجاع إعداد لقيمته", "method": "DELETE",
        "path": "/api/v1/operator/config/{key}", "capability": "platform.loyalty",
        "params": [{"name": "key", "in": "path", "type": "string", "required": True}],
        "confirm": True, "group": "المنصة",
    },
    # ── the programme's settings (spec §9.2, §9.3) ─────────────────────────────────────────────
    {
        "id": "loyalty.settings.read", "label": "إعدادات النقاط", "method": "GET",
        "path": "/api/v1/loyalty/settings", "capability": "loyalty.read", "group": "الولاء",
        # Returns every level AND the source of each number, because the screen cannot say
        # "customised — tap to follow again" unless the API says where the value came from.
    },
    {
        "id": "loyalty.settings.general", "label": "نقاط لكل زيارة (عام)", "method": "PUT",
        "path": "/api/v1/loyalty/settings/general", "capability": "loyalty.manage",
        "group": "الولاء",
        # The one number a shop needs to start. Reaches every service that follows it and leaves
        # every service the owner customised exactly as he left it.
    },
    {
        "id": "loyalty.settings.group", "label": "نقاط لمجموعة خدمات", "method": "PUT",
        "path": "/api/v1/loyalty/settings/group", "capability": "loyalty.manage",
        "group": "الولاء",
    },
    {
        "id": "loyalty.settings.service", "label": "نقاط خدمة بعينها", "method": "PUT",
        "path": "/api/v1/loyalty/settings/service/{service_id}", "capability": "loyalty.manage",
        "params": [{"name": "service_id", "in": "path", "type": "string", "required": True}],
        "group": "الولاء",
    },
    {
        "id": "loyalty.settings.follow", "label": "إرجاعها للإعداد العام", "method": "DELETE",
        "path": "/api/v1/loyalty/settings/service/{service_id}", "capability": "loyalty.manage",
        "params": [{"name": "service_id", "in": "path", "type": "string", "required": True}],
        "confirm": True, "group": "الولاء",
        # DELETE and not "set to the general value": writing today's general number would look
        # identical now and silently stop following the next time the general one changes.
    },
    {
        "id": "loyalty.settings.mode", "label": "طريقة الاحتساب", "method": "PUT",
        "path": "/api/v1/loyalty/settings/mode", "capability": "loyalty.manage",
        "confirm": True, "group": "الولاء",
        # A SWITCH: by invoice value or by services, never both (spec §9.3). Confirmed because
        # changing it changes what every future visit is worth.
    },

    # ── the rewards catalogue (spec §9.4) ──────────────────────────────────────────────────────
    {
        "id": "loyalty.rewards.list", "label": "المكافآت", "method": "GET",
        "path": "/api/v1/loyalty/rewards", "capability": "loyalty.read", "group": "المكافآت",
    },
    {
        "id": "loyalty.rewards.create", "label": "إضافة مكافأة", "method": "POST",
        "path": "/api/v1/loyalty/rewards", "capability": "loyalty.manage", "group": "المكافآت",
        # The name reaches a customer's WhatsApp message, so it is bounded at save with the actual
        # limit named — an owner told only "invalid" tries again, fails again, and calls support.
    },
    {
        "id": "loyalty.rewards.update", "label": "تعديل مكافأة", "method": "PATCH",
        "path": "/api/v1/loyalty/rewards/{reward_id}", "capability": "loyalty.manage",
        "params": [{"name": "reward_id", "in": "path", "type": "string", "required": True}],
        "group": "المكافآت",
        # Retiring is `active: false` — there is no delete, because every redemption in history
        # references a reward and a receipt must not restate itself when the menu changes.
    },

    # ── what the owner reads (spec §9.10) ──────────────────────────────────────────────────────
    {
        "id": "loyalty.report", "label": "تقرير البرنامج", "method": "GET",
        "path": "/api/v1/loyalty/report", "capability": "loyalty.read", "group": "الولاء",
        # Carries the outstanding obligation and the share of points that expired unredeemed —
        # the second is the warning indicator, and no other number reveals it.
    },
    {
        "id": "loyalty.platform_reconcile", "label": "إصلاح رصيد عميل", "method": "POST",
        "path": "/api/v1/loyalty/platform/reconcile", "capability": "platform.loyalty",
        "confirm": True, "group": "المنصة",
        # The answer to "where did my points go?" — the only question this programme generates.
        # Recomputes the total from the ledger, which is the truth, and repairs it if they disagree.
    },
    {
        "id": "loyalty.platform_reconcile", "label": "إصلاح رصيد عميل", "method": "POST",
        "path": "/api/v1/loyalty/platform/reconcile", "capability": "platform.loyalty",
        "confirm": True, "group": "المنصة",
        # The answer to "where did my points go?" — the only question this programme generates.
        # Recomputes the total from the ledger, which is the truth, and repairs a disagreement.
    },
]
