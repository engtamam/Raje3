"""<service> — admin actions declared for the platform admin panel (Phase 33).

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
    # THE BACK OFFICE. Everything here is the owner's, not the operator's — which is why it sits
    # behind operations.manage and not behind operations.record.

    # ── THE PLATFORM CONSOLE — ours, not an establishment's ───────────────────────────────────
    # Gated by platform.operations, which no tenant token carries. This is the surface where WE
    # curate the content every establishment is built from, and it is the highest-leverage set of
    # edits in the product: a wrong cycle here propagates to every tenant created afterwards.
    {
        "id": "operations.list_sectors", "label": "القطاعات", "method": "GET",
        "path": "/api/v1/platform/sectors", "capability": "platform.operations",
        "group": "المنصة — القطاعات",
        "help": "كل القطاعات، الفعّال والمتوقف. لوحة تعرض الحيّ وحده لا تُظهر ما أُوقف الشهر الماضي.",
    },
    {
        "id": "operations.upsert_sector", "label": "إضافة أو تعديل قطاع", "method": "PUT",
        "path": "/api/v1/platform/sectors/{key}", "capability": "platform.operations",
        "group": "المنصة — القطاعات", "confirm": True,
        "params": [{"name": "key", "in": "path", "type": "string", "required": True,
                    "help": "أحرف صغيرة وشرطة سفلية، ولا يبدأ بشرطة"}],
        "help": "يسري على المنشآت التي تُنشأ بعده. لا يُعاد على القائمة — المالك عدّل خدماته، "
                "والكتابة فوقها تُتلف عملاً حقيقياً.",
    },
    {
        "id": "operations.deactivate_sector", "label": "إيقاف قطاع", "method": "DELETE",
        "path": "/api/v1/platform/sectors/{key}", "capability": "platform.operations",
        "group": "المنصة — القطاعات", "confirm": True, "danger": True,
        "params": [{"name": "key", "in": "path", "type": "string", "required": True}],
        "help": "إيقاف لا حذف: منشآت قائمة تشير إليه، وحذفه يتركها تشير إلى ما لم يعد موجوداً.",
    },
    {
        "id": "operations.set_sector_fields", "label": "حقول القطاعات", "method": "PUT",
        "path": "/api/v1/platform/sector-fields", "capability": "platform.operations",
        "group": "المنصة — القطاعات", "confirm": True,
        "help": "تعريف كل حقل مرة واحدة يُشار إليه بالاسم — فـplate يعني الشيء نفسه في كل قطاع مركبات.",
    },
    # ── the message library, edited by US at runtime (spec 8.4.1) ─────────────────────────
    {
        "id": "operations.list_templates", "label": "مكتبة الرسائل", "method": "GET",
        "path": "/api/v1/platform/templates", "capability": "platform.operations",
        "group": "المنصة",
        # 66 templates across five classes. Content our own people revise, which is why it lives
        # in the datastore and not in an image.
        "help": "كل القوالب بأصنافها ونبراتها، المفعّل منها والمتوقف.",
    },
    {
        "id": "operations.set_template", "label": "تعديل قالب", "method": "PUT",
        "path": "/api/v1/platform/templates/{name}", "capability": "platform.operations",
        "params": [{"name": "name", "in": "path", "type": "string", "required": True}],
        "confirm": True, "danger": True, "group": "المنصة",
        # The text every establishment sends afterwards. A wrong edit reaches thousands of
        # customers under an establishment's name, not ours.
        "help": "يسري على المنشآت التي تُربط بعده. ونصٌّ فيه سعر داخل قالب توعوي يُرفض.",
    },
    {
        "id": "operations.deactivate_template", "label": "إيقاف قالب", "method": "DELETE",
        "path": "/api/v1/platform/templates/{name}", "capability": "platform.operations",
        "params": [{"name": "name", "in": "path", "type": "string", "required": True}],
        "confirm": True, "danger": True, "group": "المنصة",
        "help": "يوقف صنف رسائل، وعَرَضه صمت لا خطأ.",
    },
    # ── partners: who resells us, and what we owe them (spec 16.6.3) ──────────────────────
    {
        "id": "operations.list_partners", "label": "الشركاء", "method": "GET",
        "path": "/api/v1/platform/partners", "capability": "platform.operations",
        "group": "الشركاء",
        "help": "شركات الكاشير، ونسبة كل واحدة، ومفتاحها بمقدّمته لا بقيمته.",
    },
    {
        "id": "operations.create_partner", "label": "إضافة شريك", "method": "POST",
        "path": "/api/v1/platform/partners", "capability": "platform.operations",
        "confirm": True, "group": "الشركاء",
        # The key is shown once. A console that could re-read it is a console whose screenshot is
        # a payout.
        "help": "المفتاح يظهر مرة واحدة فقط — احفظه ساعتها.",
    },
    {
        "id": "operations.rotate_partner_key", "label": "تدوير مفتاح شريك", "method": "POST",
        "path": "/api/v1/platform/partners/{partner_id}/rotate",
        "capability": "platform.operations",
        "params": [{"name": "partner_id", "in": "path", "type": "string", "required": True}],
        "confirm": True, "danger": True, "group": "الشركاء",
        # An overlap an operator must end by hand is an overlap nobody ends.
        "help": "المفتاح القديم يعمل حتى تنتهي النافذة ثم يتوقف تلقائياً. وللتسرّب: صفر.",
    },
    {
        "id": "operations.deactivate_partner", "label": "إيقاف شريك", "method": "DELETE",
        "path": "/api/v1/platform/partners/{partner_id}", "capability": "platform.operations",
        "params": [{"name": "partner_id", "in": "path", "type": "string", "required": True}],
        "confirm": True, "danger": True, "group": "الشركاء",
        "help": "يوقف الأختام الجديدة. محلاته تبقى مختومة ومستحقاته قائمة.",
    },
    # ── the operator surface, and it is declared in every service or in none ──────────────
    # ── what we owe the partners, and whether we paid it (§7) ────────────────────────────
    {
        "id": "operations.list_statements", "label": "كشوف العمولات", "method": "GET",
        "path": "/api/v1/platform/statements", "capability": "platform.operations",
        "group": "الشركاء",
        "params": [
            {"name": "status", "in": "query", "type": "enum", "required": False,
             "help": "issued | paid | disputed — والسؤال الذي تُفتح له الشاشة: أيّها لم يُدفع؟"},
            {"name": "limit", "in": "query", "type": "integer", "required": False},
        ],
        "help": "تُصدَر شهرياً بالجدولة على الشهر المنقضي، وتُقرأ هنا بحالتها لا بمبلغها وحده.",
    },
    {
        "id": "operations.statement_paid", "label": "تسجيل دفع كشف", "method": "POST",
        "path": "/api/v1/platform/statements/{partner_id}/{period_start}/paid",
        "capability": "platform.operations", "group": "الشركاء", "confirm": True,
        "params": [
            {"name": "partner_id", "in": "path", "type": "string", "required": True},
            {"name": "period_start", "in": "path", "type": "integer", "required": True},
            {"name": "reference", "in": "body", "type": "string", "required": True,
             "help": "مرجع الحوالة — بلا مرجع لا يمكن إثبات الدفع بعد أشهر"},
            {"name": "paid_at", "in": "body", "type": "number", "required": False,
             "help": "تاريخ القيمة عند البنك، لا وقت الإدخال"},
            {"name": "note", "in": "body", "type": "string", "required": False},
        ],
        "help": "والمدفوع لا يُعاد حسابه: إعادة تشغيل شهر سُدّد تعيده «غير مدفوع» فيُدفع مرتين.",
    },
    {
        "id": "operations.statement_dispute", "label": "تسجيل اعتراض على كشف", "method": "POST",
        "path": "/api/v1/platform/statements/{partner_id}/{period_start}/dispute",
        "capability": "platform.operations", "group": "الشركاء", "confirm": True,
        "params": [
            {"name": "partner_id", "in": "path", "type": "string", "required": True},
            {"name": "period_start", "in": "path", "type": "integer", "required": True},
            {"name": "note", "in": "body", "type": "string", "required": True,
             "help": "سبب الاعتراض — «متنازَع عليه» بلا سبب لا يقود إلى إجراء"},
        ],
        "help": "الاعتراض يبقى بعد إعادة الحساب، لأنه سببُ إعادته.",
    },
    {
        "id": "operations.operator_secrets", "label": "اعتمادات التشغيل", "method": "GET",
        "path": "/api/v1/operator/secrets", "capability": "platform.secrets", "group": "المنصة",
        # The NAMES only — a route that returned a value would put a credential in a screenshot.
        "help": "أي اعتمادات مضبوطة لهذه الخدمة، بأسمائها لا بقيمها.",
    },
    {
        "id": "operations.set_operator_secret", "label": "تعديل اعتماد", "method": "PUT",
        "path": "/api/v1/operator/secrets", "capability": "platform.secrets",
        "confirm": True, "danger": True, "group": "المنصة",
        # The previous value is gone the moment this runs, so an unrecorded rotation cannot be
        # reconstructed and an unattributable one is indistinguishable from an attacker's.
        "help": "القيمة السابقة تختفي فوراً — لا رجعة ولا نسخة.",
    },
    {
        "id": "operations.clear_operator_secret", "label": "حذف اعتماد", "method": "DELETE",
        "path": "/api/v1/operator/secrets/{name}", "capability": "platform.secrets",
        "params": [{"name": "name", "in": "path", "type": "string", "required": True}],
        "confirm": True, "danger": True, "group": "المنصة",
        "help": "يعيد الخدمة صامتاً إلى ما تحمله البيئة — تغيّر سلوك لا يراه أحد.",
    },
    {
        "id": "operations.operator_config", "label": "إعدادات التشغيل", "method": "GET",
        "path": "/api/v1/operator/config", "capability": "platform.config", "group": "المنصة",
        "help": "السياسات التي تشرح سلوك الخدمة لاحقاً.",
    },
    {
        "id": "operations.set_operator_config", "label": "تعديل إعداد تشغيل", "method": "PUT",
        "path": "/api/v1/operator/config", "capability": "platform.config",
        "confirm": True, "group": "المنصة",
        "help": "يغيّر سلوك الخدمة من الآن فصاعداً.",
    },
    {
        "id": "operations.clear_operator_config", "label": "حذف إعداد تشغيل", "method": "DELETE",
        "path": "/api/v1/operator/config/{key}", "capability": "platform.config",
        "params": [{"name": "key", "in": "path", "type": "string", "required": True}],
        "confirm": True, "group": "المنصة",
        "help": "يعود للافتراضي المبنيّ في الخدمة.",
    },
    # `operations.ping` USED TO BE HERE, pointing at GET /api/v1/admin/ping — a route this service
    # has never served. The console would have rendered a button that 404s, and the reason it
    # survived review is that it reads like scaffolding nobody would question. /whoami answers the
    # same question — is my token accepted, and as whom — and it exists.
]
