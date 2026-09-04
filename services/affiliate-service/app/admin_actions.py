"""affiliate-service — admin actions declared for the platform admin panel (Phase 33).

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
    {
        "id": "affiliates.list_pending",
        "label": "طلبات التسويق المعلّقة",
        "method": "GET",
        "path": "/api/v1/admin/affiliates",
        "capability": "platform.affiliates",
        "params": [],
        "confirm": False,
        "danger": False,
        "group": "Affiliates",
    },
    {
        "id": "affiliates.platform_stats",
        "label": "إحصائيات المسوّقين الكلية",
        "method": "GET",
        "path": "/api/v1/admin/affiliates/stats",
        "capability": "platform.affiliates",
        "params": [],
        "confirm": False,
        "danger": False,
        "group": "Affiliates",
    },
    {
        "id": "affiliates.leaderboard",
        "label": "أفضل المسوّقين أداءً",
        "method": "GET",
        "path": "/api/v1/admin/affiliates/leaderboard",
        "capability": "platform.affiliates",
        "params": [{"name": "limit", "in": "query", "type": "integer", "required": False}],
        "confirm": False,
        "danger": False,
        "group": "Affiliates",
    },
    {
        "id": "leads.geo_map",
        "label": "خريطة العملاء المحتملين",
        "method": "GET",
        "path": "/api/v1/admin/leads/geo",
        "capability": "platform.affiliates",
        "params": [],
        "confirm": False,
        "danger": False,
        "group": "Leads",
    },
    {
        "id": "affiliates.approve_application",
        "label": "قبول طلب مسوّق",
        "method": "POST",
        "path": "/api/v1/admin/affiliates/{application_id}/approve",
        "capability": "platform.affiliates",
        "params": [{"name": "application_id", "in": "path", "type": "string", "required": True}],
        "confirm": True,
        "danger": False,
        "group": "Affiliates",
    },
    {
        "id": "affiliates.reject_application",
        "label": "رفض طلب مسوّق",
        "method": "POST",
        "path": "/api/v1/admin/affiliates/{application_id}/reject",
        "capability": "platform.affiliates",
        "params": [{"name": "application_id", "in": "path", "type": "string", "required": True}],
        "confirm": True,
        "danger": True,
        "group": "Affiliates",
    },
    {
        "id": "affiliates.suspend",
        "label": "إيقاف مسوّق",
        "method": "POST",
        "path": "/api/v1/admin/affiliates/{affiliate_id}/suspend",
        "capability": "platform.affiliates",
        "params": [{"name": "affiliate_id", "in": "path", "type": "string", "required": True}],
        "confirm": True,
        "danger": True,
        "group": "Affiliates",
    },
    {
        "id": "affiliates.reactivate",
        "label": "إعادة تفعيل مسوّق",
        "method": "POST",
        "path": "/api/v1/admin/affiliates/{affiliate_id}/reactivate",
        "capability": "platform.affiliates",
        "params": [{"name": "affiliate_id", "in": "path", "type": "string", "required": True}],
        "confirm": True,
        "danger": False,
        "group": "Affiliates",
    },
    {
        "id": "affiliates.toggle_platform_revenue",
        "label": "تبديل نسبة أرباح المنصة",
        "method": "POST",
        "path": "/api/v1/admin/affiliates/{affiliate_id}/platform-revenue",
        "capability": "platform.affiliates",
        "params": [
            {"name": "affiliate_id", "in": "path", "type": "string", "required": True},
            {"name": "enabled", "in": "body", "type": "boolean", "required": True},
        ],
        "confirm": True,
        "danger": False,
        "group": "Affiliates",
    },
    {
        "id": "employment.list_pending",
        "label": "طلبات التوظيف المعلّقة",
        "method": "GET",
        "path": "/api/v1/admin/employment-requests",
        "capability": "platform.affiliates",
        "params": [],
        "confirm": False,
        "danger": False,
        "group": "Employment",
    },
    {
        "id": "employment.decide",
        "label": "قرار طلب توظيف",
        "method": "POST",
        "path": "/api/v1/admin/employment-requests/{request_id}/decision",
        "capability": "platform.affiliates",
        "params": [
            {"name": "request_id", "in": "path", "type": "string", "required": True},
            {"name": "decision", "in": "body", "type": "enum", "required": True,
             "enum": ["approved", "rejected"]},
            {"name": "reason", "in": "body", "type": "string", "required": False},
        ],
        "confirm": True,
        "danger": True,
        "group": "Employment",
    },
    {
        "id": "sectors.list",
        "label": "قطاعات الاستهداف",
        "method": "GET",
        "path": "/api/v1/admin/sectors",
        "capability": "platform.affiliates",
        "params": [],
        "confirm": False,
        "danger": False,
        "group": "Sectors",
    },
    {
        "id": "sectors.upsert",
        "label": "إضافة/تعديل قطاع",
        "method": "PUT",
        "path": "/api/v1/admin/sectors",
        "capability": "platform.affiliates",
        "params": [
            {"name": "code", "in": "body", "type": "string", "required": True},
            {"name": "name", "in": "body", "type": "string", "required": True},
        ],
        "confirm": True,
        "danger": False,
        "group": "Sectors",
    },
    {
        "id": "sectors.delete",
        "label": "حذف قطاع",
        "method": "DELETE",
        "path": "/api/v1/admin/sectors/{code}",
        "capability": "platform.affiliates",
        "params": [{"name": "code", "in": "path", "type": "string", "required": True}],
        "confirm": True,
        "danger": True,
        "group": "Sectors",
    },
    {
        "id": "sectors.stats",
        "label": "إحصائيات القطاعات",
        "method": "GET",
        "path": "/api/v1/admin/sectors/stats",
        "capability": "platform.affiliates",
        "params": [],
        "confirm": False,
        "danger": False,
        "group": "Sectors",
    },
    {
        "id": "wafa.list_pending",
        "label": "طلبات برنامج دعم الوفاء المعلّقة",
        "method": "GET",
        "path": "/api/v1/admin/wafa-requests",
        "capability": "platform.affiliates_payouts",
        "params": [],
        "confirm": False,
        "danger": False,
        "group": "Wafa",
    },
    {
        "id": "wafa.decide",
        "label": "قرار طلب دعم الوفاء",
        "method": "POST",
        "path": "/api/v1/admin/wafa-requests/{wafa_id}/decision",
        "capability": "platform.affiliates_payouts",
        "params": [
            {"name": "wafa_id", "in": "path", "type": "string", "required": True},
            {"name": "decision", "in": "body", "type": "enum", "required": True,
             "enum": ["approve", "reject"]},
            {"name": "reason", "in": "body", "type": "string", "required": False},
        ],
        "confirm": True,
        "danger": True,
        "group": "Wafa",
    },
    {
        "id": "withdrawals.list_pending",
        "label": "طلبات السحب المعلّقة",
        "method": "GET",
        "path": "/api/v1/admin/withdrawals",
        "capability": "platform.affiliates_payouts",
        "params": [],
        "confirm": False,
        "danger": False,
        "group": "Withdrawals",
    },
    {
        # Upload (POST .../receipt) is deliberately NOT declared here — it's a multipart file
        # body, a shape this schema's `params` cannot express (string/integer/number/boolean/
        # enum/object/array only, no `file`). Uploading stays API-only until the panel grows a
        # file-input param type; viewing what was already uploaded needs no such thing.
        "id": "withdrawals.view_receipt",
        "label": "عرض إيصال التحويل",
        "method": "GET",
        "path": "/api/v1/admin/withdrawals/{withdrawal_id}/receipt",
        "capability": "platform.affiliates_payouts",
        "params": [{"name": "withdrawal_id", "in": "path", "type": "string", "required": True}],
        "confirm": False,
        "danger": False,
        "group": "Withdrawals",
    },
    {
        "id": "withdrawals.complete",
        "label": "تأكيد تحويل مكتمل",
        "method": "POST",
        "path": "/api/v1/admin/withdrawals/{withdrawal_id}/complete",
        "capability": "platform.affiliates_payouts",
        "params": [{"name": "withdrawal_id", "in": "path", "type": "string", "required": True}],
        "confirm": True,
        "danger": False,
        "group": "Withdrawals",
    },
    {
        "id": "withdrawals.reject",
        "label": "رفض طلب سحب",
        "method": "POST",
        "path": "/api/v1/admin/withdrawals/{withdrawal_id}/reject",
        "capability": "platform.affiliates_payouts",
        "params": [{"name": "withdrawal_id", "in": "path", "type": "string", "required": True}],
        "confirm": True,
        "danger": True,
        "group": "Withdrawals",
    },
    # ── the platform's own operator surface, inherited from _template ─────────────────────────
    # OURS, not the marketer's: these are the credentials (the manager's own §6 BYOK Google
    # Places key, see affiliate-service.values.yaml's existingSecret note) and knobs our
    # operators manage for this service.
    {
        "id": "affiliate_service.operator_secrets", "label": "اعتمادات التشغيل", "method": "GET",
        "path": "/api/v1/affiliates/operator/secrets", "capability": "platform.secrets", "group": "المنصة",
    },
    {
        "id": "affiliate_service.operator_secret_set", "label": "تعيين اعتماد", "method": "PUT",
        "path": "/api/v1/affiliates/operator/secrets", "capability": "platform.secrets",
        "confirm": True, "group": "المنصة",
    },
    {
        "id": "affiliate_service.operator_secret_clear", "label": "مسح اعتماد", "method": "DELETE",
        "path": "/api/v1/affiliates/operator/secrets/{name}", "capability": "platform.secrets",
        "params": [{"name": "name", "in": "path", "type": "string", "required": True}],
        "confirm": True, "danger": True, "group": "المنصة",
    },
    {
        "id": "affiliate_service.operator_config", "label": "إعدادات التشغيل", "method": "GET",
        "path": "/api/v1/affiliates/operator/config", "capability": "platform.config", "group": "المنصة",
    },
    {
        "id": "affiliate_service.operator_config_set", "label": "تعديل إعداد تشغيلي", "method": "PUT",
        "path": "/api/v1/affiliates/operator/config", "capability": "platform.config",
        "confirm": True, "group": "المنصة",
    },
    {
        "id": "affiliate_service.operator_config_clear", "label": "إرجاع إعداد لقيمته", "method": "DELETE",
        "path": "/api/v1/affiliates/operator/config/{key}", "capability": "platform.config",
        "params": [{"name": "key", "in": "path", "type": "string", "required": True}],
        "confirm": True, "danger": True, "group": "المنصة",
    },
    {
        "id": "affiliate_service.ping", "label": "فحص الاتصال", "method": "GET",
        "path": "/api/v1/affiliates/admin/ping", "capability": "platform.secrets", "group": "المنصة",
        "help": "يؤكّد أن الخدمة تستقبل رمزك وتردّ.",
    },
    {
        "id": "affiliate_service.whoami", "label": "من أنا", "method": "GET",
        "path": "/api/v1/affiliates/whoami", "capability": "platform.secrets", "group": "المنصة",
        "help": "المنشأة والصلاحيات التي يحملها رمزك الآن.",
    },
]
