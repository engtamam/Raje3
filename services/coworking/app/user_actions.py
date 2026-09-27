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
