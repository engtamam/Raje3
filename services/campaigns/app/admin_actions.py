"""campaigns — admin actions declared for the platform admin panel (Phase 33).

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
    # THE OWNER'S SCREENS (spec 10.9). Every one is a card or a button they actually press — the
    # panel renders exactly what is declared here, so an action missing from this list is a
    # feature that does not exist as far as the console is concerned.
    {
        "id": "campaigns.goals", "label": "أهداف الحملات", "method": "GET",
        "path": "/api/v1/campaigns/goals", "capability": "campaigns.read", "group": "الحملات",
        # The five cards, with their locks and their reasons. The screen renders what this returns
        # rather than computing availability itself — two answers that disagree is worse than one.
        "help": "ماذا تريد أن تحقّق؟ خمس بطاقات، وكل واحدة تقول متى تتاح.",
    },
    {
        "id": "campaigns.preview", "label": "معاينة قبل الإرسال", "method": "POST",
        "path": "/api/v1/campaigns/preview", "capability": "campaigns.read", "group": "الحملات",
        # The middle screen and the one the whole feature rests on: the real message, and a count
        # of PEOPLE.
        "help": "الرسالة كما ستصل، وكم عميلاً تصلهم.",
    },
    {
        "id": "campaigns.create", "label": "أطلق الحملة", "method": "POST",
        "path": "/api/v1/campaigns", "capability": "campaigns.manage",
        "confirm": True, "group": "الحملات",
        "help": "يرسل الآن، أو يجدول، أو يشغّل قاعدة دائمة — بحسب الهدف.",
    },
    {
        "id": "campaigns.list", "label": "حملاتي", "method": "GET",
        "path": "/api/v1/campaigns", "capability": "campaigns.read", "group": "الحملات",
        "help": "ما يعمل الآن، وما انتهى، وما هو متوقف.",
    },
    {
        "id": "campaigns.runs", "label": "ماذا حدث", "method": "GET",
        "path": "/api/v1/campaigns/{campaign_id}/runs", "capability": "campaigns.read",
        "params": [{"name": "campaign_id", "in": "path", "type": "string", "required": True}],
        "group": "الحملات",
        # THE MOST IMPORTANT ONE. "It didn't arrive" is the only complaint this product generates,
        # and this is the only screen that answers it.
        "help": "كل إرسالة: كم وصلت، وكم امتنعت، ولماذا.",
    },
    {
        "id": "campaigns.pause", "label": "إيقاف حملة", "method": "POST",
        "path": "/api/v1/campaigns/{campaign_id}/pause", "capability": "campaigns.manage",
        "params": [{"name": "campaign_id", "in": "path", "type": "string", "required": True}],
        "confirm": True, "group": "الحملات",
        "help": "توقف القاعدة الدائمة. سجلّها يبقى.",
    },
    # OURS, NOT AN ESTABLISHMENT'S.
    {
        "id": "campaigns.get_audience_cap", "label": "سقف الجمهور", "method": "GET",
        "path": "/api/v1/campaigns/platform/audience-cap", "capability": "platform.campaigns",
        "group": "المنصة",
        "help": "أقصى عدد يصله إرسال واحد — عالمياً أو لمنشأة.",
    },
    {
        "id": "campaigns.set_audience_cap", "label": "تعديل سقف الجمهور", "method": "PUT",
        "path": "/api/v1/campaigns/platform/audience-cap", "capability": "platform.campaigns",
        "confirm": True, "danger": True, "group": "المنصة",
        "help": "دفعة من عشرين ألفاً إشارة حجم تقرؤها ميتا على كل أرقامنا، لا على المحل وحده.",
    },
    # ── the operator surface, and it is declared in every service or in none ──────────────
    {
        "id": "campaigns.operator_secrets", "label": "اعتمادات التشغيل", "method": "GET",
        "path": "/api/v1/operator/secrets", "capability": "platform.secrets", "group": "المنصة",
        # The NAMES only — a route that returned a value would put a credential in a screenshot.
        "help": "أي اعتمادات مضبوطة لهذه الخدمة، بأسمائها لا بقيمها.",
    },
    {
        "id": "campaigns.set_operator_secret", "label": "تعديل اعتماد", "method": "PUT",
        "path": "/api/v1/operator/secrets", "capability": "platform.secrets",
        "confirm": True, "danger": True, "group": "المنصة",
        # The previous value is gone the moment this runs, so an unrecorded rotation cannot be
        # reconstructed and an unattributable one is indistinguishable from an attacker's.
        "help": "القيمة السابقة تختفي فوراً — لا رجعة ولا نسخة.",
    },
    {
        "id": "campaigns.clear_operator_secret", "label": "حذف اعتماد", "method": "DELETE",
        "path": "/api/v1/operator/secrets/{name}", "capability": "platform.secrets",
        "params": [{"name": "name", "in": "path", "type": "string", "required": True}],
        "confirm": True, "danger": True, "group": "المنصة",
        "help": "يعيد الخدمة صامتاً إلى ما تحمله البيئة — تغيّر سلوك لا يراه أحد.",
    },
    {
        "id": "campaigns.operator_config", "label": "إعدادات التشغيل", "method": "GET",
        "path": "/api/v1/operator/config", "capability": "platform.config", "group": "المنصة",
        "help": "السياسات التي تشرح سلوك الخدمة لاحقاً.",
    },
    {
        "id": "campaigns.set_operator_config", "label": "تعديل إعداد تشغيل", "method": "PUT",
        "path": "/api/v1/operator/config", "capability": "platform.config",
        "confirm": True, "group": "المنصة",
        "help": "يغيّر سلوك الخدمة من الآن فصاعداً.",
    },
    {
        "id": "campaigns.clear_operator_config", "label": "حذف إعداد تشغيل", "method": "DELETE",
        "path": "/api/v1/operator/config/{key}", "capability": "platform.config",
        "params": [{"name": "key", "in": "path", "type": "string", "required": True}],
        "confirm": True, "group": "المنصة",
        "help": "يعود للافتراضي المبنيّ في الخدمة.",
    },
    {
        "id": "campaigns.ping", "label": "فحص الاتصال", "method": "GET",
        "path": "/api/v1/admin/ping", "capability": "platform.secrets", "group": "المنصة",
        # From the generated scaffold and kept: what a client calls to confirm its token is accepted
        # at all, which is the first question asked when something else is failing. Undeclared in
        # every service until a guard compared the manifest with the app.
        "help": "يؤكّد أن الخدمة تستقبل رمزك وتردّ.",
    },
]
