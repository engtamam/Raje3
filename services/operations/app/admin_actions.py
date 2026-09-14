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
    # ── COMPLIANCE: THE EVIDENCE FILE ─────────────────────────────────────────────────────────
    # The one control that turns «show me what happened» into an answer instead of a week of
    # cross-service archaeology. Declared here so the panel renders it — the panel is a MAP and the
    # route re-checks the capability on every call.
    {
        "id": "operations.evidence_file",
        "label": "ملف الأدلة",
        "method": "POST",
        "path": "/api/v1/platform/evidence",
        "capability": "platform.operations",
        "help": "كل ما تحتفظ به المنصة عن منشأة معيّنة في فترة معيّنة، لدعم شكوى — الطلب وسحبه يُسجَّل باسمك.",
        "params": [
            {"name": "tenant", "in": "body", "type": "string", "required": True},
            # A WINDOW, and both ends optional: the first question is usually «everything about
            # this shop», and narrowing comes after.
            {"name": "since", "in": "body", "type": "integer", "required": False},
            {"name": "until", "in": "body", "type": "integer", "required": False},
        ],
        # NOT DANGEROUS, BUT CONFIRMED. Producing it is a disclosure that is recorded against the
        # person who asked, and a control that discloses should never fire on a stray click.
        "confirm": True,
        "danger": False,
        "group": "الامتثال",
    },
    # ── THE WALLET TOP-UP RECONCILE POLL — a manual run of the CronJob, for the one moment
    # somebody is staring at a stuck top-up (see app/core/wallet_topup_reconcile.py's own header).
    {
        "id": "operations.wallet_topups_reconcile_now",
        "label": "تحديث شحنات المحفظة المعلّقة",
        "method": "POST",
        "path": "/api/v1/platform/wallet-topups/reconcile-now",
        "capability": "platform.operations",
        "help": "يسأل بوابة الدفع عن حالة كل شحنة معلّقة الآن ويضيف رصيد المكتمل منها فوراً، بدل انتظار الجولة القادمة (كل 5 دقائق تلقائياً).",
        "confirm": True,
        "danger": False,
        "group": "المالية",
    },
    # THE BACK OFFICE. Everything here is the owner's, not the operator's — which is why it sits
    # behind operations.manage and not behind operations.record.

    # ── THE PLATFORM CONSOLE — ours, not an establishment's ───────────────────────────────────
    # Gated by platform.operations, which no tenant token carries. What we curate here is the
    # MESSAGE LIBRARY and nothing else: a shop's own services and rewards are its owner's to write,
    # and the trade-shaped catalogue we used to seed from is gone (see core/vehicles.py).
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
    {
        "id": "operations.branch_locations", "label": "خريطة المحلات", "method": "GET",
        "path": "/api/v1/platform/branches/locations", "capability": "platform.operations",
        "group": "المنصة",
        "help": "كل فرع فعّال حدّد موقعه بنفسه عبر أي تينانت — الفروع بلا موقع محدَّد لا تظهر.",
    },
    {
        "id": "operations.tenant_capacity", "label": "عدد الفروع والموظفين لمنشأة", "method": "GET",
        "path": "/api/v1/platform/tenants/{tenant_id}/capacity", "capability": "platform.operations",
        "group": "المنصة",
        "params": [{"name": "tenant_id", "in": "path", "type": "string", "required": True}],
        "help": "العدد الفعلي فقط — لا الحد المسموح (ذاك من billing-service).",
    },
    {
        "id": "operations.whatsapp_diagnostics", "label": "تشخيص واتساب لمحل", "method": "GET",
        "path": "/api/v1/platform/whatsapp/diagnostics", "capability": "platform.operations",
        "group": "المنصة",
        "params": [
            {"name": "tenant", "in": "query", "type": "string", "required": False},
            {"name": "phone_number_id", "in": "query", "type": "string", "required": False,
             "help": "بديل عن tenant — رقم ميتا نفسه"},
        ],
        "help": "سجلّ إرسال واتساب لمحل واحد بسببه — أحد الحقلين مطلوب.",
    },
    {
        "id": "operations.whatsapp_flow_json", "label": "معاينة فلو واتساب", "method": "GET",
        "path": "/api/v1/platform/whatsapp/flow-json", "capability": "platform.operations",
        "group": "المنصة",
        "params": [{"name": "name", "in": "query", "type": "string", "required": True}],
        "help": "شاشات الفلو الحقيقية كما توّلدها notification-service — نفس ما يعرضه واتساب "
                "بالضبط، لمعاينة القالب.",
    },
    {
        "id": "operations.whatsapp_platform_status", "label": "حالة واتساب المنصة", "method": "GET",
        "path": "/api/v1/platform/whatsapp/platform-status", "capability": "platform.operations",
        "group": "المنصة",
        # No params — the peer's own figures are a capped count over its most-recent rows
        # (platform v0.19.6), never a clock window, so there is nothing to parameterise here.
        "help": "حالة اتصال كل رقم، ومعدّل نجاح/فشل الإرسال الحقيقي، وعدد الأرقام المربوطة، وعدد "
                "من ألغى اشتراكه التسويقي — أسرار المنصة نفسها لا أي محل.",
    },
    # ── one shop's own connected WhatsApp number (platform v0.19.9) — next to whatsapp_diagnostics
    # above, same per-shop scope, never the platform's own Meta identity ──────────────────────
    {
        "id": "operations.whatsapp_messaging_limit", "label": "سقف الإرسال اليومي لمحل", "method": "GET",
        "path": "/api/v1/platform/whatsapp/messaging-limit", "capability": "platform.operations",
        "group": "المنصة",
        "params": [{"name": "tenant", "in": "query", "type": "string", "required": True}],
        "help": "درجة السقف اليومي (tier) وتقييم الجودة عند ميتا لرقم هذا المحل.",
    },
    {
        "id": "operations.whatsapp_subscribed_fields", "label": "أحداث الواتساب المشترَكة لمحل",
        "method": "GET", "path": "/api/v1/platform/whatsapp/subscribed-fields",
        "capability": "platform.operations", "group": "المنصة",
        "params": [{"name": "tenant", "in": "query", "type": "string", "required": True}],
        "help": "أي أحداث فعلياً يرسلها ميتا لهذا المحل — عرض فقط، تعديلها يصير من لوحة مطوّري ميتا لا هنا.",
    },
    {
        "id": "operations.whatsapp_business_verification", "label": "تحقّق النشاط التجاري لمحل",
        "method": "GET", "path": "/api/v1/platform/whatsapp/business-verification",
        "capability": "platform.operations", "group": "المنصة",
        "params": [{"name": "tenant", "in": "query", "type": "string", "required": True}],
        "help": "حالة تحقّق ميتا من النشاط التجاري لهذا المحل — تتحكّم بسرعة مراجعة القوالب وسقف الإرسال.",
    },
    {
        "id": "operations.whatsapp_set_two_step_pin", "label": "تعيين رمز التحقّق بخطوتين لمحل",
        "method": "POST", "path": "/api/v1/platform/whatsapp/two-step-pin",
        "capability": "platform.operations", "group": "المنصة", "confirm": True, "danger": True,
        "params": [
            {"name": "tenant", "in": "body", "type": "string", "required": True},
            {"name": "phone_number_id", "in": "body", "type": "string", "required": False},
            {"name": "pin", "in": "body", "type": "string", "required": True,
             "help": "6 أرقام بالضبط — لا يُعرَض بعد الحفظ أبداً."},
        ],
        "help": "يغيّر رمز التحقّق بخطوتين لرقم واتساب هذا المحل عند ميتا مباشرة — تغيير حي بلا رجعة.",
    },
    {
        "id": "operations.customer_by_phone", "label": "ابحث عن عميل برقم جواله", "method": "GET",
        "path": "/api/v1/platform/customers/by-phone", "capability": "platform.operations",
        "group": "المنصة",
        "params": [
            {"name": "tenant", "in": "query", "type": "string", "required": True,
             "help": "المنشأة — يُختار صراحة، لا بحث عبر كل المحلات دفعة واحدة"},
            {"name": "phone", "in": "query", "type": "string", "required": True},
        ],
        "help": "مطابقة تامة فقط — يكتب موظف الدعم رقم الجوال كاملاً، لا بحث تقريبي.",
    },
    {
        "id": "operations.customer_success_scan", "label": "نجاح العملاء — فحص المحلات المتعثّرة",
        "method": "POST", "path": "/api/v1/platform/customers/success-scan",
        "capability": "platform.operations", "group": "المنصة",
        "params": [
            {"name": "tenants", "in": "body", "type": "string", "required": True,
             "help": "قائمة المنشآت (id + created_at) — من tenant.list نفسه، لا مسار جديد للقائمة"},
            {"name": "stall_days", "in": "body", "type": "number", "required": False,
             "help": "كم يوم بلا خدمة تُعتبر «تعثّر» — افتراضي 3"},
        ],
        "help": "محلات سجّلت ولم تضِف خدمة خلال المدة، أو أضافت خدمات ولا زيارة واحدة سُجّلت لها — "
                "من بيانات هذه الخدمة الفعلية، لا تخمين.",
    },
    {
        "id": "operations.seed_subscription_renewal_flow", "label": "تجهيز فلو التجديد",
        "method": "POST", "path": "/api/v1/platform/flows/subscription-renewal/seed",
        "capability": "platform.operations", "group": "المنصة", "confirm": True,
        "help": "يصنع شاشة تجديد الاشتراك التفاعلية عند ميتا، مرة واحدة على حساب المنصة — "
                "يدوي بالكامل، لا يتكرر لكل محل. آمن لإعادة الضغط: لو موجودة أصلاً، يقول ذلك ولا "
                "يعيد إنشاءها.",
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
    {
        "id": "operations.mark_sandbox", "label": "محل تجريبي لشركة كاشير", "method": "POST",
        "path": "/api/v1/platform/sandbox", "capability": "platform.operations",
        "group": "الشركاء", "confirm": True,
        "params": [
            {"name": "tenant", "in": "body", "type": "string", "required": True},
            {"name": "days", "in": "body", "type": "integer", "required": False,
             "help": "بعدها ينتهي وصفه تجريبياً — محل تجربة بلا تاريخ يبقى سنتين"},
        ],
        "help": "نفس المسارات ونفس القواعد بلا مال: لا عمولة عليه ولا يُحسب عميلاً. "
                "ومسارٌ تجريبي منفصل يُثبت طريقاً لا تسلكه المنصة الحقيقية.",
    },
    {
        "id": "operations.partner_health", "label": "صحة الربط", "method": "GET",
        "path": "/api/v1/platform/partners/{partner_id}/health",
        "capability": "platform.operations", "group": "الشركاء",
        "params": [
            {"name": "partner_id", "in": "path", "type": "string", "required": True},
            {"name": "quiet_days", "in": "query", "type": "integer", "required": False,
             "help": "بعد كم يوم صمت يُعدّ المحل متوقفاً — 7 افتراضاً"},
        ],
        "help": "ثلاث حالات وثلاث مكالمات مختلفة: لم يبدأ · توقّف · يرسل. "
                "و«لم يبدأ» لا يظهر في أي شاشة أخرى لأنه لا يملك صفاً من الأساس.",
    },
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
        "id": "operations.operator_config", "label": "إعدادات التشغيل", "method": "GET",
        "path": "/api/v1/operations/operator/config", "capability": "platform.config", "group": "المنصة",
        "help": "السياسات التي تشرح سلوك الخدمة لاحقاً.",
    },
    {
        "id": "operations.set_operator_config", "label": "تعديل إعداد تشغيل", "method": "PUT",
        "path": "/api/v1/operations/operator/config", "capability": "platform.config",
        "confirm": True, "group": "المنصة",
        "help": "يغيّر سلوك الخدمة من الآن فصاعداً.",
    },
    {
        "id": "operations.clear_operator_config", "label": "حذف إعداد تشغيل", "method": "DELETE",
        "path": "/api/v1/operations/operator/config/{key}", "capability": "platform.config",
        "params": [{"name": "key", "in": "path", "type": "string", "required": True}],
        "confirm": True, "group": "المنصة",
        "help": "يعود للافتراضي المبنيّ في الخدمة.",
    },
    # `operations.ping` USED TO BE HERE, pointing at GET /api/v1/admin/ping — a route this service
    # has never served. The console would have rendered a button that 404s, and the reason it
    # survived review is that it reads like scaffolding nobody would question. /whoami answers the
    # same question — is my token accepted, and as whom — and it exists. Declared here now too:
    # the route existed and answered fine, but nothing ever put a button in front of it.
    {
        "id": "operations.whoami", "label": "من أنا", "method": "GET",
        # The route itself enforces no capability (any authenticated token may call it — see
        # api/v1/__init__.py's own whoami). Grouped under platform.config here only so it shows up
        # alongside the operator screens an admin already reaches, not because it is actually
        # gated on it — was platform.secrets until that capability's own routes were removed.
        "path": "/api/v1/operations/whoami", "capability": "platform.config", "group": "المنصة",
        "help": "المنشأة والصلاحيات التي يحملها رمزك الآن.",
    },
    {
        "id": "operations.coupon_settings_get",
        "label": "إعدادات الكوبونات — قراءة",
        "method": "GET",
        "path": "/api/v1/platform/coupons/settings",
        "capability": "platform.operations",
        "group": "كوبونات (محل لمحل)",
    },
    {
        "id": "operations.coupon_settings_set",
        "label": "إعدادات الكوبونات — تعديل (السقف والشرائح)",
        "method": "PATCH",
        "path": "/api/v1/platform/coupons/settings",
        "capability": "platform.operations",
        "confirm": True,
        "group": "كوبونات (محل لمحل)",
    },
    {
        "id": "operations.coupon_override_get",
        "label": "سقف خاص لمحل — قراءة",
        "method": "GET",
        "path": "/api/v1/platform/coupons/tenants/{tenant_id}",
        "capability": "platform.operations",
        "params": [{"name": "tenant_id", "in": "path", "type": "string", "required": True}],
        "group": "كوبونات (محل لمحل)",
    },
    {
        "id": "operations.coupon_override_set",
        "label": "سقف خاص لمحل — تعديل",
        "method": "PATCH",
        "path": "/api/v1/platform/coupons/tenants/{tenant_id}",
        "capability": "platform.operations",
        "params": [{"name": "tenant_id", "in": "path", "type": "string", "required": True}],
        "confirm": True,
        "group": "كوبونات (محل لمحل)",
    },
]
