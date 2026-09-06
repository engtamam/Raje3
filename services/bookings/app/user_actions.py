"""bookings — end-user (self-service) actions for the platform app catalog (Phase 36).

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
    {
        "id": "bookings.list", "label": "جدول الحجوزات", "method": "GET",
        "path": "/api/v1/bookings", "capability": "bookings.read",
        "params": [{"name": "branch_id", "in": "query", "type": "string", "required": True},
                  {"name": "date", "in": "query", "type": "string", "required": True}],
        "group": "الحجوزات",
        "help": "كل حجوزات فرع معيّن في يوم واحد.",
    },
    {
        "id": "bookings.no_show_risk", "label": "مؤشّر عدم الحضور", "method": "GET",
        "path": "/api/v1/bookings/risk", "capability": "bookings.read",
        "params": [{"name": "customer_id", "in": "query", "type": "string", "required": True}],
        "group": "الحجوزات",
        # §2.6: a number beside her name at the moment the dialog opens, never a verdict.
        "help": "من أصل آخر خمس مواعيد له، كم مرة لم يحضر — رقمٌ يُعرض بجانب اسمه ولا يمنع الحجز.",
    },
    {
        "id": "bookings.nearest", "label": "أقرب فتحة", "method": "GET",
        "path": "/api/v1/bookings/nearest", "capability": "bookings.read",
        "params": [{"name": "branch_id", "in": "query", "type": "string", "required": True},
                  {"name": "operator_id", "in": "query", "type": "string", "required": True},
                  {"name": "service_ids", "in": "query", "type": "string", "required": True},
                  {"name": "after", "in": "query", "type": "integer", "required": True}],
        "group": "الحجوزات",
        "help": "أقرب موعد فاضٍ لهذا العامل بعد وقت تحدّده. لا شيء إن لم توجد فتحة.",
    },
    {
        "id": "bookings.create", "label": "حجز جديد", "method": "POST",
        "path": "/api/v1/bookings", "capability": "bookings.write",
        "group": "الحجوزات",
        "help": "يثبّت الموعد في الجدول، بخدمة واحدة أو أكثر أو باقة — لا الاثنين معاً.",
    },
    {
        "id": "bookings.reschedule", "label": "تعديل الموعد", "method": "PATCH",
        "path": "/api/v1/bookings/{booking_id}/reschedule", "capability": "bookings.write",
        "params": [{"name": "booking_id", "in": "path", "type": "string", "required": True}],
        "group": "الحجوزات",
        # THE DRAG-AND-DROP IS THIS CALL (§6.1.1 من مستند القرارات) — لا مسارٌ ثانٍ.
        "help": "ينقل الحجز إلى وقت آخر، ويمكن لعامل آخر — نفس ما يفعله السحب والإفلات في الجدول.",
    },
    {
        "id": "bookings.edit_services", "label": "تعديل الخدمات", "method": "PATCH",
        "path": "/api/v1/bookings/{booking_id}/services", "capability": "bookings.write",
        "params": [{"name": "booking_id", "in": "path", "type": "string", "required": True}],
        "group": "الحجوزات",
        "help": "يبدّل قائمة الخدمات المحجوزة لنفس الموعد.",
    },
    {
        "id": "bookings.edit_note", "label": "تعديل الملاحظة", "method": "PATCH",
        "path": "/api/v1/bookings/{booking_id}/note", "capability": "bookings.write",
        "params": [{"name": "booking_id", "in": "path", "type": "string", "required": True}],
        "group": "الحجوزات",
        "help": "يغيّر ملاحظة الحجز فقط، بلا مساس بالوقت أو الخدمات.",
    },
    {
        "id": "bookings.cancel", "label": "إلغاء الحجز", "method": "PATCH",
        "path": "/api/v1/bookings/{booking_id}/cancel", "capability": "bookings.write",
        "params": [{"name": "booking_id", "in": "path", "type": "string", "required": True}],
        "confirm": True, "group": "الحجوزات",
        "help": "يلغي الحجز ويحرّر الفتحة لغيره. لا رجوع عنه من هنا.",
    },
    {
        "id": "bookings.attend", "label": "تسجيل الحضور", "method": "PATCH",
        "path": "/api/v1/bookings/{booking_id}/attend", "capability": "bookings.write",
        "params": [{"name": "booking_id", "in": "path", "type": "string", "required": True}],
        "group": "الحجوزات",
        # مسموحةٌ حتى على اشتراكٍ منتهٍ (app/core/licence.py) — إغلاق حجزٍ قائم ليس النصف
        # النامي أبداً.
        "help": "يقفل الحجز بوصفه حضر فعلاً. متاح حتى لو انتهى الاشتراك.",
    },
    {
        "id": "bookings.no_show", "label": "تسجيل عدم الحضور", "method": "PATCH",
        "path": "/api/v1/bookings/{booking_id}/no-show", "capability": "bookings.write",
        "params": [{"name": "booking_id", "in": "path", "type": "string", "required": True}],
        "confirm": True, "group": "الحجوزات",
        "help": "يقفل الحجز بوصفه لم يحضر، ويُحسب في مؤشّر عدم حضوره لاحقاً.",
    },
]
