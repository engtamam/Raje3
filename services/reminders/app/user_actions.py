"""reminders — end-user (self-service) actions for the platform app catalog (Phase 36).

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
    # THE CUSTOMER'S OWN SWITCHES. Reached from the link at the end of a message — no token in the
    # URL, because that link is forwardable and anyone who receives it must not see whose it is
    # (spec 8.6.1). The route re-scopes to the signed reference it was opened with.
    {
        "id": "reminders.get_prefs", "label": "إشعاراتي", "method": "GET",
        "path": "/api/v1/prefs/{ref}", "capability": "reminders.read", "group": "إشعاراتي",
        "params": [{"name": "ref", "in": "path", "type": "string", "required": True}],
        "help": "أي أنواع الرسائل تصلك من هذا المحل.",
    },
    {
        "id": "reminders.set_prefs", "label": "تعديل إشعاراتي", "method": "PUT",
        "path": "/api/v1/prefs/{ref}", "capability": "reminders.read", "group": "إشعاراتي",
        "params": [{"name": "ref", "in": "path", "type": "string", "required": True}],
        # FIVE SWITCHES, INCLUDING THE PERSONAL ONE. An earlier draft exempted personal messages
        # because the customer started them — true at the time, and not true forever. Someone who
        # switches everything off has said what they want, and keeping a channel open over their
        # objection is not a service to them (spec 8.4.2 section 5).
        "help": "أوقف أي نوع من الخمسة على حدة، أو أوقفها كلها.",
    },
    # ── the owner's own surface, moved here from admin_actions ─────────────────────────
    # api-gateway builds the establishment's app from THIS file and no other
    # (app_catalog.py, field="user_actions"). These sat in the platform console's catalogue,
    # so the owner's app would have rendered a nav with almost nothing in it — and the reflex
    # fix is to call the paths directly, which is exactly the rule the UI is built on. The
    # test for which file a route belongs in is whose data it is: `platform.*` is ours;
    # everything else belongs to the establishment.
    {
        "id": "reminders.customer_offer", "label": "عرض العميل الساري", "method": "GET",
        "path": "/api/v1/reminders/offer", "capability": "reminders.read", "group": "العروض",
        "params": [{"name": "subject_ref", "in": "query", "type": "string", "required": True}],
        # The line above the field screen's grid (§5.6.2). An offer the man at the counter cannot
        # see becomes a discount argued over in front of the customer.
        "help": "العرض الذي يحمله هذا العميل الآن. المنتهي لا يُعاد إطلاقاً.",
    },
    {
        # THE HALF PDPL WAS MISSING. compliance mints a verification code and holds no channel to
        # deliver it, so it reached nobody and no request could ever be verified. We own the
        # channel; this asks for the delivery.
        "id": "reminders.send_dsar_code", "label": "أرسل رمز تأكيد طلبي", "method": "POST",
        "path": "/api/v1/reminders/dsar-code", "capability": "reminders.read",
        "group": "بياناتي",
        "help": "يصلك على واتساب رقمك، وصالحٌ دقائق معدودة.",
    },
    {
        "id": "reminders.customer_offers", "label": "عروض العميل", "method": "GET",
        "path": "/api/v1/reminders/offers", "capability": "reminders.read", "group": "العروض",
        "params": [{"name": "subject_ref", "in": "query", "type": "string", "required": True},
                   {"name": "include_expired", "in": "query", "type": "boolean",
                    "required": False}],
        "help": "كل عرض وصل هذا العميل ومتى ينتهي — والمنتهية معها، لأن المالك يسأل عن الشهر "
                "الماضي بقدر ما يسأل عن اليوم.",
    },
    {
        "id": "reminders.list_schedule", "label": "التذكيرات القادمة", "method": "GET",
        "path": "/api/v1/reminders/schedule", "capability": "reminders.read",
        "group": "التذكيرات",
        # SEEING COMES BEFORE ACTING. An owner asked "why did my customer get this?" cannot be
        # answered by a button; it is answered by a list. A panel that can only act is half a panel.
        "help": "من سيصله تذكير، ومتى، وعن أي خدمة.",
    },
    {
        "id": "reminders.cancel", "label": "إلغاء تذكير", "method": "DELETE",
        "path": "/api/v1/reminders/schedule/{id}", "capability": "reminders.manage",
        "params": [{"name": "id", "in": "path", "type": "string", "required": True}],
        "confirm": True, "danger": True, "group": "التذكيرات",
        "help": "يلغي تذكيراً واحداً. لا يوقف الخدمة، ولا يمنع تذكيراً قادماً عن زيارة جديدة.",
    },
    {
        "id": "reminders.list_rules", "label": "قواعد الخدمات", "method": "GET",
        "path": "/api/v1/reminders/rules", "capability": "reminders.read", "group": "القواعد",
        "params": [{"name": "subject_ref", "in": "query", "type": "string", "required": False},
                   {"name": "service_id", "in": "query", "type": "string", "required": False}],
        "help": "الفترة الحالية لكل خدمة، وكم تعلّمها النظام من سلوك العملاء. "
                "وبـ subject_ref: دورة هذا العميل هو.",
    },
    {
        "id": "reminders.set_rule", "label": "تعديل قاعدة خدمة", "method": "PUT",
        "path": "/api/v1/reminders/rules/{service_id}", "capability": "reminders.manage",
        "params": [{"name": "service_id", "in": "path", "type": "string", "required": True}],
        "confirm": True, "group": "القواعد",
        # Changing a rule changes what EVERY future customer of that service receives. It is the
        # highest-leverage edit an owner can make here, and the reason this one is confirmed.
        "help": "يغيّر الفترة الافتراضية وأيام الإشعار المسبق لخدمة واحدة.",
    },
    {
        "id": "reminders.log", "label": "سجل الإرسال", "method": "GET",
        "path": "/api/v1/reminders/log", "capability": "reminders.read", "group": "التذكيرات",
        # Suppressions are in this log too, WITH THEIR REASON. A message that was not sent and
        # cannot be explained is indistinguishable from a broken service (spec 8.4.2).
        "help": "ما أُرسل وما امتنع، ولماذا امتنع.",
    },
    {
        "id": "reminders.my_templates", "label": "نصوصي", "method": "GET",
        "path": "/api/v1/reminders/templates", "capability": "reminders.read",
        "group": "الإعدادات",
        "help": "النصوص التي كتبتها بنفسك، وأين وصل كلٌّ منها عند واتساب.",
    },
    {
        "id": "reminders.write_template", "label": "اكتب نصّك", "method": "POST",
        "path": "/api/v1/reminders/templates", "capability": "reminders.manage",
        "group": "الإعدادات",
        # A draft, and nothing reaches Meta until he submits it.
        "help": "نصٌّ من عندك لرسالة بعينها — يُحفظ مسودّة حتى ترفعه.",
    },
    {
        "id": "reminders.submit_template", "label": "ارفعه إلى واتساب", "method": "POST",
        "path": "/api/v1/reminders/templates/{name}/submit", "capability": "reminders.manage",
        "group": "الإعدادات",
        # THE BUTTON THE DRAFT NEVER HAD. Writing was reachable and submitting was not, so «قوالبي»
        # was a notepad: every text an owner wrote sat as a draft for ever with nothing to press.
        "help": "يُرسل نصّك إلى واتساب للمراجعة على رقمك. رسائلك تستمر بنصّنا حتى يُعتمد.",
        "params": [{"name": "name", "in": "path", "type": "string", "required": True}],
    },
    {
        "id": "reminders.template_help", "label": "ساعدوني", "method": "POST",
        "path": "/api/v1/reminders/templates/{name}/help", "capability": "reminders.manage",
        "group": "الإعدادات",
        # THE COST OF HAVING NO REVIEWER OF OURS between him and Meta: the refusal arrives in
        # English, from somebody he cannot reach, about a rule he has never read. One press
        # attaches Meta's sentence and his text to a queue a human answers.
        "help": "ترفض واتساب نصّك؟ اضغط ونصل إليك — يصلنا سبب الرفض ونصّك بلا أن تكتب شيئاً.",
        "params": [{"name": "name", "in": "path", "type": "string", "required": True}],
    },
    {
        "id": "reminders.my_template_help", "label": "طلبات المساعدة", "method": "GET",
        "path": "/api/v1/reminders/templates/help", "capability": "reminders.read",
        "group": "الإعدادات",
        "help": "أين وصل كل طلب مساعدة، وماذا أجبناك.",
    },
    {
        "id": "reminders.reasons", "label": "متى نرسل", "method": "GET",
        "path": "/api/v1/reminders/reasons", "capability": "reminders.read",
        "group": "الإعدادات",
        # THE CATALOGUE AND HIS ANSWERS IN ONE CALL. A screen that fetched the list and the
        # settings separately would hold the defaults itself, and the two would disagree the
        # first time a default changed.
        "help": "دواعي الإرسال: ما الذي يخرج باسمك، ومتى، وهل هو مشغّل، وبأي نص.",
    },
    {
        "id": "reminders.preview_reason", "label": "معاينة الرسالة", "method": "GET",
        "path": "/api/v1/reminders/reasons/{reason_id}/preview",
        "capability": "reminders.read",
        "params": [{"name": "reason_id", "in": "path", "type": "string", "required": True}],
        "group": "الإعدادات",
        # Rendered by the engine with example values, so a wording he cannot send is one he is
        # never offered — and what he reads is what leaves the building.
        "help": "نصّ الرسالة كما تصل عميلك، بالصيغ المتاحة لها.",
    },
    {
        "id": "reminders.set_reason", "label": "تشغيل أو إيقاف رسالة", "method": "PUT",
        "path": "/api/v1/reminders/reasons/{reason_id}", "capability": "reminders.manage",
        "params": [{"name": "reason_id", "in": "path", "type": "string", "required": True}],
        "confirm": True, "group": "الإعدادات",
        "help": "يقرّر هل يخرج هذا النوع من الرسائل، وبنصّك أم بنصّنا.",
    },
    {
        "id": "reminders.get_settings", "label": "إعدادات التذكير", "method": "GET",
        "path": "/api/v1/reminders/settings", "capability": "reminders.read",
        "group": "الإعدادات",
        # Carries WHERE each value came from — the screen cannot say "this one is customised, tap
        # to go back" unless the API says which level answered.
        "help": "القيم السارية، ومن أين جاءت: عام، أم مجموعة، أم خاصة بالخدمة.",
    },
    {
        "id": "reminders.set_general", "label": "الإعداد العام", "method": "PUT",
        "path": "/api/v1/reminders/settings", "capability": "reminders.manage",
        "confirm": True, "group": "الإعدادات",
        # Reaches every follower and leaves every customisation alone. An owner who spent a minute
        # setting the oil change to 60 days has not asked us to undo that minute.
        "help": "يسري على كل خدمة تتبعه. المخصّصة تبقى كما هي.",
    },
    {
        "id": "reminders.set_service_settings", "label": "تخصيص خدمة", "method": "PUT",
        "path": "/api/v1/reminders/settings/service/{service_id}",
        "capability": "reminders.manage",
        "params": [{"name": "service_id", "in": "path", "type": "string", "required": True}],
        "group": "الإعدادات",
        "help": "تعطي هذه الخدمة إعدادها الخاص، فتتوقّف عن اتّباع العام.",
    },
    {
        "id": "reminders.follow_general", "label": "العودة للعام", "method": "DELETE",
        "path": "/api/v1/reminders/settings/service/{service_id}",
        "capability": "reminders.manage",
        "params": [{"name": "service_id", "in": "path", "type": "string", "required": True}],
        "group": "الإعدادات",
        # Deletes rather than copying the general value in — copying looks identical today and
        # diverges tomorrow, when the next general edit skips this service.
        "help": "تحذف تخصيصها فتعود تتبع الإعداد العام.",
    },
    {
        "id": "reminders.set_group", "label": "مجموعة خدمات", "method": "PUT",
        "path": "/api/v1/reminders/settings/group/{name}", "capability": "reminders.manage",
        "params": [{"name": "name", "in": "path", "type": "string", "required": True}],
        "group": "الإعدادات",
        "help": "إعداد واحد لعدة خدمات متشابهة.",
    },
    {
        # THE UNDO THAT DID NOT EXIST. `set_group` writes `service_group[sid]`, and "not in a
        # group" is absence rather than a value — so there was nothing to call, and a screen
        # offering «بلا مجموعة» was offering a choice with no action behind it.
        "id": "reminders.leave_group", "label": "إخراج خدمة من المجموعة", "method": "DELETE",
        "path": "/api/v1/reminders/settings/group/{name}/service/{service_id}",
        "capability": "reminders.manage",
        "params": [{"name": "name", "in": "path", "type": "string", "required": True},
                   {"name": "service_id", "in": "path", "type": "string", "required": True}],
        "group": "الإعدادات",
        "help": "تعود الخدمة إلى الإعداد العام.",
    },
    {
        "id": "reminders.delete_group", "label": "حذف المجموعة", "method": "DELETE",
        "path": "/api/v1/reminders/settings/group/{name}", "capability": "reminders.manage",
        "params": [{"name": "name", "in": "path", "type": "string", "required": True}],
        "group": "الإعدادات", "confirm": True,
        "help": "تُحذف المجموعة وتبقى خدماتها كما هي، بلا مجموعة.",
    },
    {
        "id": "reminders.suggest_group", "label": "اقتراح مجموعة", "method": "GET",
        "path": "/api/v1/reminders/settings/suggest-group", "capability": "reminders.read",
        "group": "الإعدادات",
        # Proposes only. A system rearranging an owner's settings without being asked is the
        # fastest way to lose their trust in a screen.
        "help": "هل تكرّر المالك؟ نقترح، ولا نغيّر شيئاً بأنفسنا.",
    },
    {
        "id": "reminders.today", "label": "حالة اليوم", "method": "GET",
        "path": "/api/v1/reminders/today", "capability": "reminders.read", "group": "اليوم",
        # ONE CALL, because the screen it feeds answers "is everything running" — which is answered
        # by the whole picture or not at all. A ceiling arriving after a send count shows "23 sent"
        # and then, a beat later, "4 left", and the owner has already formed an impression.
        "help": "رسائل اليوم وما ينتظر، وسقفك المتبقي لدى واتساب.",
    },
]
