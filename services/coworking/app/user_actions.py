"""coworking — end-user (shop-owner self-service) actions for the platform app catalog.

See `services/affiliate-service/app/user_actions.py`'s own module doc for the full contract. Every
action below carries `"capability": "coworking.manage"` — the one capability a shop's own admin
token holds to run this app; WHICH rows belong to that shop is still, and only, the tenant-scoping
each route in `api/v1/admin.py` does for itself (`principal.tenant`), never expressed here.
"""
from __future__ import annotations

from typing import Any

USER_ACTIONS: list[dict[str, Any]] = [
    # ── resources (spec §1/§7) ──────────────────────────────────────────────────────────────
    {
        "id": "coworking.create_resource", "label": "أضف مورداً قابلاً للتأجير", "method": "POST",
        "path": "/api/v1/coworking/resources", "capability": "coworking.manage", "group": "الموارد",
        "help": "كرسي، محطة، أو أي شيء مادي وقابل للجدولة تريد تأجيره بالساعة.",
    },
    {
        "id": "coworking.list_resources", "label": "مواردي", "method": "GET",
        "path": "/api/v1/coworking/resources", "capability": "coworking.manage", "group": "الموارد",
        "help": "كل الموارد المسجَّلة، النشطة والمُعطَّلة معاً.",
    },
    {
        "id": "coworking.update_resource", "label": "عدّل مورداً", "method": "PATCH",
        "path": "/api/v1/coworking/resources/{resource_id}", "capability": "coworking.manage",
        "group": "الموارد",
        "params": [{"name": "resource_id", "in": "path", "type": "string", "required": True}],
        "help": "يغيّر الاسم أو يفعّل/يعطّل المورد — التعطيل لا يمسّ أي حجز مؤكَّد عليه سابقاً.",
    },
    {
        "id": "coworking.set_availability", "label": "اضبط أوقات التأجير والسعر", "method": "PUT",
        "path": "/api/v1/coworking/resources/{resource_id}/availability",
        "capability": "coworking.manage", "group": "الموارد",
        "params": [{"name": "resource_id", "in": "path", "type": "string", "required": True}],
        "help": "أيام الأسبوع وساعات كل يوم اللي يُتاح فيها هذا المورد للتأجير، وسعر الساعة.",
    },
    # GENUINE GAP CLOSED (console build, 2026-09-27): admin.py already served both routes below —
    # `upload_resource_image`/`get_resource_image` — but neither was declared here, so the
    # catalogue-driven console (catalog.ts's own rule: "no screen composes a URL") had no action id
    # to call them through and the resource photo feature could never work at all. Same shape as
    # operations' own `upload_service_image`/`get_service_image` pair.
    {
        "id": "coworking.upload_resource_image", "label": "ارفع صورة المورد", "method": "POST",
        "path": "/api/v1/coworking/resources/{resource_id}/image",
        "capability": "coworking.manage", "group": "الموارد",
        "params": [{"name": "resource_id", "in": "path", "type": "string", "required": True}],
        "help": "صورة واحدة فقط لكل مورد — رفع صورة جديدة يستبدل القديمة.",
    },
    {
        "id": "coworking.get_resource_image", "label": "صورة المورد", "method": "GET",
        "path": "/api/v1/coworking/resources/{resource_id}/image",
        "capability": "coworking.manage", "group": "الموارد",
        "params": [{"name": "resource_id", "in": "path", "type": "string", "required": True}],
        "help": "صورة المورد نفسها، إن وُجدت.",
    },
    # ── join requests / block list (spec §6/§7) ─────────────────────────────────────────────
    {
        "id": "coworking.list_joins", "label": "طلبات الانضمام", "method": "GET",
        "path": "/api/v1/coworking/joins", "capability": "coworking.manage", "group": "المستقلّون",
        "params": [{"name": "status", "in": "query", "type": "string", "required": False}],
        "help": "كل مستقلّ حاول الحجز عندك ولو مرة، بحالته الحالية: معلّق، مقبول، أو محظور.",
    },
    {
        "id": "coworking.approve_join", "label": "اقبل مستقلّاً", "method": "POST",
        "path": "/api/v1/coworking/joins/{phone}/approve", "capability": "coworking.manage",
        "group": "المستقلّون",
        "params": [{"name": "phone", "in": "path", "type": "string", "required": True}],
        "confirm": True,
        "help": "بعدها يقدر يحجز عندك مباشرة بلا أي موافقة إضافية — حتى تلغي ذلك أو تحظره.",
    },
    {
        "id": "coworking.reject_join", "label": "ارفض طلب انضمام", "method": "POST",
        "path": "/api/v1/coworking/joins/{phone}/reject", "capability": "coworking.manage",
        "group": "المستقلّون",
        "params": [{"name": "phone", "in": "path", "type": "string", "required": True}],
        "confirm": True,
        "help": "لا يحظره نهائياً — يقدر يحاول الحجز مرة ثانية لاحقاً ويرجع طلباً جديداً.",
    },
    {
        "id": "coworking.block_phone", "label": "احظر رقماً", "method": "POST",
        "path": "/api/v1/coworking/joins/{phone}/block", "capability": "coworking.manage",
        "group": "المستقلّون",
        "params": [{"name": "phone", "in": "path", "type": "string", "required": True}],
        "confirm": True, "danger": True,
        "help": "يمنعه من أي حجز جديد نهائياً — حجوزاته المؤكَّدة سابقاً تبقى إلا إن ألغيتها بنفسك.",
    },
    {
        "id": "coworking.unblock_phone", "label": "ألغِ حظر رقم", "method": "POST",
        "path": "/api/v1/coworking/joins/{phone}/unblock", "capability": "coworking.manage",
        "group": "المستقلّون",
        "params": [{"name": "phone", "in": "path", "type": "string", "required": True}],
        "confirm": True,
        "help": "يرفع الحظر — لكن يحتاج يقدّم طلب انضمام جديداً قبل أي حجز، لا يعود مقبولاً تلقائياً.",
    },
    # ── bookings (spec §7) ───────────────────────────────────────────────────────────────────
    {
        "id": "coworking.list_bookings", "label": "كل الحجوزات", "method": "GET",
        "path": "/api/v1/coworking/bookings", "capability": "coworking.manage", "group": "الحجوزات",
        "params": [{"name": "resource_id", "in": "query", "type": "string", "required": False},
                  {"name": "status", "in": "query", "type": "string", "required": False}],
        "help": "كل الحجوزات — الماضية والحالية والمستقبلية معاً.",
    },
    {
        "id": "coworking.cancel_booking", "label": "ألغِ حجزاً", "method": "POST",
        "path": "/api/v1/coworking/bookings/{booking_id}/cancel", "capability": "coworking.manage",
        "group": "الحجوزات",
        "params": [{"name": "booking_id", "in": "path", "type": "string", "required": True}],
        "confirm": True, "danger": True,
        "help": "يلغي الحجز فيصير وقته متاحاً من جديد لأي مستقلّ آخر.",
    },
    # ── memberships (owner decision, 2026-10-06) — «month»/«year» seats ─────────────────────
    {
        "id": "coworking.list_memberships", "label": "الأعضاء", "method": "GET",
        "path": "/api/v1/coworking/memberships", "capability": "coworking.manage",
        "group": "العضويات",
        "params": [{"name": "resource_id", "in": "query", "type": "string", "required": False},
                  {"name": "status", "in": "query", "type": "string", "required": False}],
        "help": "كل من اشترك بأي مورد عضوية — نشطاً كان أو منتهياً.",
    },
    {
        "id": "coworking.stop_membership_renewal", "label": "أوقف تجديد عضوية", "method": "POST",
        "path": "/api/v1/coworking/memberships/{membership_id}/stop-renewal",
        "capability": "coworking.manage", "group": "العضويات",
        "params": [{"name": "membership_id", "in": "path", "type": "string", "required": True}],
        "confirm": True,
        "help": "تسري بنهاية الفترة الحالية — لا تُنهي العضوية اليوم، وما تحتاج أي إقرار.",
    },
    {
        "id": "coworking.resume_membership_renewal", "label": "استأنف تجديد عضوية",
        "method": "POST",
        "path": "/api/v1/coworking/memberships/{membership_id}/resume-renewal",
        "capability": "coworking.manage", "group": "العضويات",
        "params": [{"name": "membership_id", "in": "path", "type": "string", "required": True}],
        "help": "يتراجع عن إيقاف تجديد سابق — طالما العضوية لا تزال نشطة.",
    },
    {
        "id": "coworking.force_end_membership", "label": "أنهِ عضوية فوراً", "method": "POST",
        "path": "/api/v1/coworking/memberships/{membership_id}/force-end",
        "capability": "coworking.manage", "group": "العضويات",
        "params": [{"name": "membership_id", "in": "path", "type": "string", "required": True}],
        "confirm": True, "danger": True,
        "help": "إنهاء فوري بمنتصف المدة — يتطلب إقراراً صريحاً إن الطرفين متفقان، بلا أي مبلغ "
               "مسترجع. غير هذا، استخدم «أوقف تجديد عضوية».",
    },
    # ── tenant-level pause (spec §5) ─────────────────────────────────────────────────────────
    {
        "id": "coworking.get_pause", "label": "حالة إيقاف الحجوزات الجديدة", "method": "GET",
        "path": "/api/v1/coworking/pause", "capability": "coworking.manage", "group": "الإعدادات",
        "help": "هل الحجوزات الجديدة موقوفة مؤقتاً الآن أم لا.",
    },
    {
        "id": "coworking.set_pause", "label": "أوقف/استأنف الحجوزات الجديدة", "method": "PUT",
        "path": "/api/v1/coworking/pause", "capability": "coworking.manage", "group": "الإعدادات",
        "confirm": True,
        "help": "يوقف كل الحجوزات الجديدة مؤقتاً أو دائماً — الحجوزات المؤكَّدة سابقاً لا تتأثر أبداً.",
    },
]

# THE PLATFORM'S OWN MECHANISM (see operations/app/user_actions.py, the first to use it). The
# `/p/coworking/{tenant}/*` routes are the freelancer's own public door (api/public.py's own
# docstring) — reached with NO token at all (that is the whole point: a freelancer's first ever
# booking attempt is what CREATES their join request), so none of them can appear in a catalog of
# what a caller's OWN token lets them do. They are real, wired, and tested; they simply belong to
# nobody's action list, the same reason affiliate-service's `/apply` and `/apply/request-otp`
# routes stay out of its own USER_ACTIONS.
UNDECLARED_ROUTES: list[dict[str, str]] = [
    {"method": "GET", "path": "/p/coworking/{tenant}",
     "why": "the portal page itself — the freelancer's shareable link, opened with no token at "
            "all before any of the reads below it are even called"},
    {"method": "GET", "path": "/p/coworking/{tenant}/shop",
     "why": "the portal page's own header read (shop name/logo/accent/pause) — same reason as "
            "/resources: browsed before any join request or token exists"},
    {"method": "GET", "path": "/p/coworking/{tenant}/resources",
     "why": "the freelancer's public catalogue of a shop's rentable resources — read before any "
            "join request or token exists"},
    {"method": "GET", "path": "/p/coworking/{tenant}/slots",
     "why": "same reason as /resources: browsed before any join request or token exists"},
    {"method": "GET", "path": "/p/coworking/{tenant}/status",
     "why": "same reason as /resources: browsed before any join request or token exists"},
    {"method": "POST", "path": "/p/coworking/{tenant}/join",
     "why": "it creates the join request an approval would later be granted against — the "
            "catalogue is fetched WITH a token, so a route that exists precisely because there is "
            "no token yet cannot appear in a list of what its holder may do"},
    {"method": "POST", "path": "/p/coworking/{tenant}/bookings",
     "why": "the freelancer books by phone number alone, once approved — still no platform token, "
            "same reason as /join"},
    {"method": "GET", "path": "/p/coworking/{tenant}/my-bookings",
     "why": "the freelancer's own view of their bookings, looked up by phone — same reason as "
            "/bookings: no platform token is ever issued to a freelancer"},
    {"method": "POST", "path": "/p/coworking/{tenant}/memberships",
     "why": "the freelancer's own membership join door — same reason as /bookings: no platform "
            "token, approved (or asked to join) by phone number alone"},
    {"method": "GET", "path": "/p/coworking/{tenant}/my-memberships",
     "why": "the freelancer's own view of their memberships, looked up by phone — same reason as "
            "/my-bookings"},
    {"method": "POST", "path": "/p/coworking/{tenant}/memberships/{membership_id}/stop-renewal",
     "why": "the member's own «لو خرج يقدر يوقف التجديد» door — scoped to his own phone inside "
            "the handler itself, same reason as every other route in this list"},
    {"method": "POST", "path": "/p/coworking/{tenant}/memberships/{membership_id}/resume-renewal",
     "why": "the undo of the row immediately above — same reasoning"},
    {"method": "POST", "path": "/p/coworking/{tenant}/memberships/{membership_id}/force-end",
     "why": "the member's own immediate-exit door, same acknowledgment contract as the shop's "
            "own admin route — still no platform token, scoped to his own phone"},
]
