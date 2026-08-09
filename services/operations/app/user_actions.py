"""<service> — end-user (self-service) actions for the platform app catalog (Phase 36).

The end-user app (GET /api/v1/app/catalog) aggregates what every service declares HERE — the twin of
`admin_actions`, but for a USER acting on their OWN data (their files, their profile, their
subscription), never platform-operator routes. The code is the source, so the app can never drift.

Declaring nothing is fine — keep the list empty and reviewed rather than forgotten. Each action is a
PURE literal dict (the safety:user-actions CI gate reads it with ast.literal_eval — no variables, no
f-strings). Shape (docs/contracts/user-actions.schema.json):

    {
        "id": "svc.do_thing",              # stable, kebab/dot, unique
        "label": "Do the thing",           # what the control says
        "method": "POST",                  # GET|POST|PUT|PATCH|DELETE (allow-listed)
        "path": "/api/v1/things/{id}",     # RELATIVE — no scheme/host; must be a real manifest route
        "capability": "things.write",      # the cap the route ENFORCES; must be advertised in the manifest
        "params": [{"name": "id", "in": "path", "type": "string", "required": True}],
        "confirm": True,                   # UX: ask before firing (auto-true when danger)
        "danger": True,                    # UX: destructive for the user (e.g. delete my account)
        "group": "Things",                 # UX: section
    }

Rules the gate enforces: the path must exist in this service's manifest `endpoints`; the capability
must be in the manifest's advertised `capabilities`. The app is a MAP, never the AUTHORITY — every
action is re-checked AND re-scoped to the caller's own tenant/identity at its route. Only declare the
user's OWN self-service (`_SELF` / ordinary user-cap) routes; operator (platform.*) and internal-token
routes belong in admin_actions or nowhere.
"""
from __future__ import annotations

from typing import Any


USER_ACTIONS: list[dict[str, Any]] = [
    # THE FIELD SCREEN. These four are the establishment app, and the order is the order an
    # operator meets them: the grid, the keypad, the save, the customer's record.
    {
        "id": "operations.catalogue", "label": "الخدمات", "method": "GET",
        "path": "/api/v1/field/catalogue", "capability": "operations.read", "group": "الشاشة",
        "help": "شبكة الخدمات. تُعبَّأ من افتراضيات القطاع عند إنشاء المنشأة.",
    },
    {
        "id": "operations.recent", "label": "آخر العملاء", "method": "GET",
        "path": "/api/v1/field/customers/recent", "capability": "operations.read",
        "group": "الشاشة",
        "params": [{"name": "limit", "in": "query", "type": "integer", "required": False}],
        "help": "الشريط العلوي — عملاء اليوم بنقرة واحدة.",
    },
    {
        "id": "operations.record_visit", "label": "تسجيل زيارة", "method": "POST",
        "path": "/api/v1/field/visits", "capability": "operations.record", "group": "الشاشة",
        "help": "أهم مسار في المنتج. مفتاح التكرار من الواجهة: ضغطتان تُنتجان زيارة واحدة.",
    },
    {
        "id": "operations.customer", "label": "سجل العميل", "method": "GET",
        "path": "/api/v1/field/customers/{id}", "capability": "operations.read",
        "group": "الشاشة",
        "params": [{"name": "id", "in": "path", "type": "string", "required": True}],
    },
    {
        "id": "operations.customer_by_phone", "label": "بحث برقم كامل", "method": "GET",
        "path": "/api/v1/field/customers/by-phone", "capability": "operations.read",
        "group": "الشاشة",
        "params": [{"name": "phone", "in": "query", "type": "string", "required": True}],
        # The distinction that decides how the keypad is built, and it is measured rather than
        # assumed: this route is EXACT. Partial digits go to search-service's /suggest, because
        # its /search matches whole tokens and `96650` finds nothing against `966501234567`.
        "help": "مطابقة تامة للرقم الكامل. البحث بأول الأرقام من لوحة المفاتيح يذهب إلى "
                "search-service عبر suggest لا عبر هذا المسار.",
    },
    {
        "id": "operations.verify_pin", "label": "تأكيد رمز العامل", "method": "POST",
        "path": "/api/v1/staff/operators/verify-pin", "capability": "operations.read",
        "group": "الشاشة",
        "help": "نسبة لا تسجيل دخول: يُسأل عند الحفظ فقط، والشاشة تبقى مفتوحة طوال الوردية.",
    },
]
