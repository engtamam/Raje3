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
    # ── the partner's own console — neither a tenant nor us (see api/v1/partner.py) ───────
    # DECLARED AS USER ACTIONS, not admin: a partner acts on its OWN data, exactly like a customer
    # does. Putting them in admin_actions would render them in OUR panel, which is the one place
    # they must never appear.
    {
        "id": "partner.my_shops", "label": "محلاتي", "method": "GET",
        "path": "/api/v1/partner/shops", "capability": "partner.read", "group": "شراكتي",
        # Tenant ids and dates. Not a shop's name, not its owner, not its customers — every field
        # added here is one somebody later argues should include "just a bit more".
        "help": "المحلات التي جلبتها، وتاريخ كل واحد.",
    },
    {
        "id": "partner.my_statements", "label": "كشوفي", "method": "GET",
        "path": "/api/v1/partner/statements", "capability": "partner.read", "group": "شراكتي",
        "help": "عمولتك شهراً بشهر، محسوبة على ما دفعه المحل فعلاً.",
    },
    {
        "id": "partner.one_statement", "label": "كشف شهر", "method": "GET",
        "path": "/api/v1/partner/statements/{period_start}", "capability": "partner.read",
        "params": [{"name": "period_start", "in": "path", "type": "string", "required": True}],
        "group": "شراكتي",
        # Read-only by design: a partner who could recompute a disputed month is a partner who
        # re-runs it until they like the number.
        "help": "تفصيل الشهر بكل محل. للقراءة فقط.",
    },
    {
        "id": "whatsapp.connect", "label": "ربط واتساب", "method": "POST",
        "path": "/api/v1/whatsapp/connect", "capability": "billing.self", "group": "حسابي",
        # The owner's own action, and it is here rather than in admin_actions because nobody at
        # Raje3 takes part in it: Embedded Signup is a conversation between him and Meta, and we
        # receive its result. An action rendered in OUR panel would suggest otherwise.
        "help": "اربط حساب واتساب الأعمال الخاص بك لتبدأ الإرسال باسم محلك.",
    },
    {
        "id": "whatsapp.connect_status", "label": "حالة الربط", "method": "GET",
        "path": "/api/v1/whatsapp/connect", "capability": "billing.self", "group": "حسابي",
        # Read separately from the connect call because the popup can close without us hearing
        # anything — and then this is the only way he learns where he stands.
        "help": "أين وصل ربط واتساب، وما الخطوة الباقية إن توقّف.",
    },
    {
        "id": "billing.subscribe", "label": "تفعيل الاشتراك", "method": "POST",
        "path": "/api/v1/subscription", "capability": "billing.self", "group": "حسابي",
        # It had been live and undeclared since it was written — invisible because the
        # completeness gate reads declared actions, so a route with no action behind it is a route
        # nothing checks. Found by adding the two beside it.
        "help": "اختر باقتك وفعّلها. يشترط ربط واتساب قبل الاشتراك المدفوع، والتجربة معفاة.",
    },
]
