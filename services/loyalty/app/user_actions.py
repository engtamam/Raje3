"""loyalty — end-user (self-service) actions for the platform app catalog (Phase 36).

The app (GET /api/v1/app/catalog) aggregates what every service declares HERE. Each action is a
PURE literal dict — the safety:user-actions CI gate reads it with ast.literal_eval.

WHO "THE USER" IS ON THIS SURFACE. It is the person holding the field screen: the operator looking
a customer up and spending his points. That is why the balance, the affordable rewards, the history
and the redemption are all declared here rather than in `admin_actions` — they are one screen's
worth of work, performed in front of the customer, and the console renders exactly what is listed.

REDEMPTION IS AN OPERATOR ACTION AND NOT A MANAGER'S (spec §9.5). A manager approving every
redemption is a bottleneck in a busy shop, and the outcome is a programme nobody uses. The control
is the receipt the customer receives within seconds, plus a threshold above which the owner does
require a manager.
"""
from __future__ import annotations

from typing import Any


USER_ACTIONS: list[dict[str, Any]] = [
    {
        "id": "loyalty.balance", "label": "رصيد النقاط", "method": "GET",
        "path": "/api/v1/loyalty/balance/{subject_ref}", "capability": "loyalty.read",
        "params": [{"name": "subject_ref", "in": "path", "type": "string", "required": True}],
        "group": "الولاء",
        "help": "رصيد نقاط العميل، والمكافآت التي يقدر عليها الآن فقط — لا القائمة كاملة.",
        # Read on every customer lookup inside the five-second journey (spec §4.7), which is why
        # it returns a materialised total and only the rewards this balance can afford.
    },
    {
        "id": "loyalty.redeem", "label": "استبدال", "method": "POST",
        "path": "/api/v1/loyalty/redeem", "capability": "loyalty.redeem",
        "confirm": True, "group": "الولاء",
        "help": "يصرف المكافأة ويخصم ثمنها من رصيد العميل فوراً.",
        # Confirmed, because it spends something the customer owns. The idempotency key is
        # REQUIRED by the route: a phone in a service lane retries, and a retry without a key is
        # a second spend the customer holds a receipt for.
    },
    {
        # THE APOLOGY THE PRODUCT COULD NOT MAKE. A machine ate a card, an operator recorded the
        # wrong service, a customer was shorted — and until this existed the only repair an owner
        # had was to invent a visit that never happened, which corrupts the very data his
        # indicators are built on.
        "id": "loyalty.adjust", "label": "تعديل نقاط العميل", "method": "POST",
        "path": "/api/v1/loyalty/adjust", "capability": "loyalty.manage", "group": "الولاء",
        "confirm": True,
        "help": "منحٌ أو خصمٌ يدوي بسبب مكتوب — لا يُعيد تشغيل مدة انتهاء النقاط.",
    },
    {
        "id": "loyalty.history", "label": "حركة النقاط", "method": "GET",
        "path": "/api/v1/loyalty/history/{subject_ref}", "capability": "loyalty.read",
        "params": [{"name": "subject_ref", "in": "path", "type": "string", "required": True}],
        "group": "الولاء",
        "help": "كل حركة على رصيد هذا العميل: ما كسبه، وما صرفه، ومتى.",
        # The answer to "where did my points go?" — asked at the counter, by the person whose
        # points they were, which is the moment the whole ledger design exists to serve.
    },
    # ── the owner's own surface, moved here from admin_actions ─────────────────────────
    # api-gateway builds the establishment's app from THIS file and no other
    # (app_catalog.py, field="user_actions"). These sat in the platform console's catalogue,
    # so the owner's app would have rendered a nav with almost nothing in it — and the reflex
    # fix is to call the paths directly, which is exactly the rule the UI is built on. The
    # test for which file a route belongs in is whose data it is: `platform.*` is ours;
    # everything else belongs to the establishment.
    {
        "id": "loyalty.settings.read", "label": "إعدادات النقاط", "method": "GET",
        "path": "/api/v1/loyalty/settings", "capability": "loyalty.read", "group": "الولاء",
        "help": "كم نقطة تُمنح لكل زيارة، عاماً أو لمجموعة أو لخدمة بعينها — ومن أين جاء كل رقم.",
        # Returns every level AND the source of each number, because the screen cannot say
        # "customised — tap to follow again" unless the API says where the value came from.
    },
    {
        "id": "loyalty.settings.general", "label": "نقاط لكل زيارة (عام)", "method": "PUT",
        "path": "/api/v1/loyalty/settings/general", "capability": "loyalty.manage",
        "group": "الولاء",
        "help": "الرقم الذي تكسبه كل زيارة لا تخصّص لها إعداداً خاصاً.",
        # The one number a shop needs to start. Reaches every service that follows it and leaves
        # every service the owner customised exactly as he left it.
    },
    {
        "id": "loyalty.settings.group", "label": "نقاط لمجموعة خدمات", "method": "PUT",
        "path": "/api/v1/loyalty/settings/group", "capability": "loyalty.manage",
        "group": "الولاء",
        "help": "نقاط واحدة لعدة خدمات متشابهة دفعة واحدة.",
    },
    {
        "id": "loyalty.settings.service", "label": "نقاط خدمة بعينها", "method": "PUT",
        "path": "/api/v1/loyalty/settings/service/{service_id}", "capability": "loyalty.manage",
        "params": [{"name": "service_id", "in": "path", "type": "string", "required": True}],
        "group": "الولاء",
        "help": "نقاط لخدمة واحدة تختلف عن الإعداد العام.",
    },
    {
        "id": "loyalty.settings.follow", "label": "إرجاعها للإعداد العام", "method": "DELETE",
        "path": "/api/v1/loyalty/settings/service/{service_id}", "capability": "loyalty.manage",
        "params": [{"name": "service_id", "in": "path", "type": "string", "required": True}],
        "confirm": True, "group": "الولاء",
        "help": "تُلغي تخصيص هذه الخدمة فتعود تتبع الإعداد العام تلقائياً.",
        # DELETE and not "set to the general value": writing today's general number would look
        # identical now and silently stop following the next time the general one changes.
    },
    {
        "id": "loyalty.settings.package", "label": "نقاط باقة بعينها", "method": "PUT",
        "path": "/api/v1/loyalty/settings/package/{package_id}", "capability": "loyalty.manage",
        "params": [{"name": "package_id", "in": "path", "type": "string", "required": True}],
        "group": "الولاء",
        "help": "لا إعداد عام تتبعه الباقة — رقم صريح دائماً، مثل سعرها بالضبط.",
    },
    {
        "id": "loyalty.settings.mode", "label": "طريقة الاحتساب", "method": "PUT",
        "path": "/api/v1/loyalty/settings/mode", "capability": "loyalty.manage",
        "confirm": True, "group": "الولاء",
        "help": "بالزيارة أم بمبلغ الفاتورة — طريقة واحدة للمحل، لا الاثنتان معاً.",
        # A SWITCH: by invoice value or by services, never both (spec §9.3). Confirmed because
        # changing it changes what every future visit is worth.
    },
    {
        "id": "loyalty.rewards.list", "label": "المكافآت", "method": "GET",
        "path": "/api/v1/loyalty/rewards", "capability": "loyalty.read", "group": "المكافآت",
        "help": "كل مكافأة في القائمة، الفعّالة والمتوقفة.",
    },
    {
        "id": "loyalty.rewards.create", "label": "إضافة مكافأة", "method": "POST",
        "path": "/api/v1/loyalty/rewards", "capability": "loyalty.manage", "group": "المكافآت",
        "help": "مكافأة جديدة في القائمة، بثمنها بالنقاط.",
        # The name reaches a customer's WhatsApp message, so it is bounded at save with the actual
        # limit named — an owner told only "invalid" tries again, fails again, and calls support.
    },
    {
        "id": "loyalty.rewards.update", "label": "تعديل مكافأة", "method": "PATCH",
        "path": "/api/v1/loyalty/rewards/{reward_id}", "capability": "loyalty.manage",
        "params": [{"name": "reward_id", "in": "path", "type": "string", "required": True}],
        "group": "المكافآت",
        "help": "التوقيف بلا حذف — كل استبدال سابق يبقى في السجل كما حدث.",
        # Retiring is `active: false` — there is no delete, because every redemption in history
        # references a reward and a receipt must not restate itself when the menu changes.
    },
    {
        "id": "loyalty.report", "label": "تقرير البرنامج", "method": "GET",
        "path": "/api/v1/loyalty/report", "capability": "loyalty.read", "group": "الولاء",
        "help": "ما تدين به المنشأة من نقاط، ونسبة ما انتهى صلاحيته دون أن يُستبدل.",
        # Carries the outstanding obligation and the share of points that expired unredeemed —
        # the second is the warning indicator, and no other number reveals it.
    },
]
