"""affiliate-service — end-user (self-service) actions for the platform app catalog (Phase 36).

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

EVERY ACTION BELOW CARRIES `"capability": "affiliates.self"` — the one capability every APPROVED
affiliate token holds (see app/core/models.py::AFFILIATE_SELF and
app/api/v1/affiliate_self.py's own module docstring on why this exists at all). It answers ONLY "is
this a real, approved affiliate" — WHICH rows he may touch (his own leads, his own team, a manager's
own shared library writes) is still, and only, the ownership/role DATA check each route makes for
itself; that boundary is never expressed here and never could be — this catalog names the door, not
who specifically may walk through carrying what.
"""
from __future__ import annotations

from typing import Any

USER_ACTIONS: list[dict[str, Any]] = [
    # ── who am I ─────────────────────────────────────────────────────────────────────────────
    {
        "id": "affiliates.me", "label": "بياناتي", "method": "GET",
        "path": "/api/v1/affiliates/me", "capability": "affiliates.self", "group": "حسابي",
        "help": "معرّفي، دوري، وحالتي — معرّفي هو رابط إحالتي (?aff= لمحل، ?ref= لمسوّق آخر).",
    },
    {
        "id": "affiliates.home", "label": "الرئيسية", "method": "GET",
        "path": "/api/v1/affiliates/me/home", "capability": "affiliates.self", "group": "الرئيسية",
        "help": "كل ما تحتاجه الشاشة الرئيسية بنداء واحد — الرصيد، العملاء المحتملون المنتظرون، أهلية "
               "دعم الوفاء والترقية، وقسم الفريق إن كنت مديرًا.",
    },
    {
        "id": "affiliates.change_password", "label": "تغيير كلمة المرور", "method": "POST",
        "path": "/api/v1/affiliates/me/change-password", "capability": "affiliates.self",
        "group": "حسابي",
        "help": "يتطلّب كلمة المرور الحالية — لا كلمة مرور تُخزَّن عندنا أبدًا.",
    },
    {
        "id": "affiliates.update_application", "label": "تعديل طلب أحد أفراد فريقي", "method": "PATCH",
        "path": "/api/v1/affiliates/me/applications/{application_id}",
        "capability": "affiliates.self", "group": "فريقي",
        "params": [{"name": "application_id", "in": "path", "type": "string", "required": True}],
        "help": "متاح فقط قبل قرار الإدارة — بعد القبول أو الرفض يُقفل التعديل.",
    },
    # ── الأرباح والسحب ────────────────────────────────────────────────────────────────────────
    {
        "id": "affiliates.commissions", "label": "عمولاتي", "method": "GET",
        "path": "/api/v1/affiliates/me/commissions", "capability": "affiliates.self", "group": "أرباحي",
        "help": "قائمة عمولاتك من كل عملية تحويل نجحت — أي عمولة عدّت مهلة التثبيت تتأكّد تلقائيًا وقت ما تفتح الصفحة.",
    },
    {
        "id": "affiliates.team_revenue", "label": "فريقي وإيراده", "method": "GET",
        "path": "/api/v1/affiliates/me/team", "capability": "affiliates.self", "group": "فريقي",
        "help": "شفافية الإيراد الفعلي — فارغة بلا خطأ لمسوّق لا فريق له.",
    },
    {
        "id": "affiliates.set_payout_method", "label": "طريقة استلام أرباحي", "method": "PUT",
        "path": "/api/v1/affiliates/me/payout-method", "capability": "affiliates.self", "group": "أرباحي",
        "help": "لا يمسّ أي طلب سحب سابق — الطريقة تُنسخ وقت طلب السحب نفسه، لا تُقرأ حيّة.",
    },
    {
        "id": "affiliates.get_payout_method", "label": "طريقة استلامي الحالية", "method": "GET",
        "path": "/api/v1/affiliates/me/payout-method", "capability": "affiliates.self", "group": "أرباحي",
        "help": "طريقة استلام أرباحك المسجّلة حاليًا، برقم الحساب مخفيًا جزئيًا لا كاملًا.",
    },
    {
        "id": "affiliates.balance", "label": "رصيدي", "method": "GET",
        "path": "/api/v1/affiliates/me/balance", "capability": "affiliates.self", "group": "أرباحي",
        "help": "رصيدك القابل للسحب الآن، مع الحد الأدنى المطلوب حتى تقدر تسحب.",
    },
    {
        "id": "affiliates.request_withdrawal", "label": "اطلب سحب رصيدي", "method": "POST",
        "path": "/api/v1/affiliates/me/withdrawals", "capability": "affiliates.self", "group": "أرباحي",
        "confirm": True,
        "help": "يقدّم طلب سحب رصيدك الحالي كاملًا إلى طريقة الاستلام المسجّلة — يُرفض إن كان رصيدك أقل من الحد الأدنى.",
    },
    {
        "id": "affiliates.withdrawals", "label": "طلبات سحبي", "method": "GET",
        "path": "/api/v1/affiliates/me/withdrawals", "capability": "affiliates.self", "group": "أرباحي",
        "help": "قائمة كل طلبات السحب اللي قدّمتها من قبل وحالة كل واحد منها.",
    },
    {
        "id": "affiliates.withdrawal_receipt", "label": "إيصال سحب", "method": "GET",
        "path": "/api/v1/affiliates/me/withdrawals/{}/receipt", "capability": "affiliates.self",
        "group": "أرباحي",
        "params": [{"name": "withdrawal_id", "in": "path", "type": "string", "required": True}],
        "help": "إثبات تحويل طلب سحب سابق — لا يظهر لك إلا إذا كان الطلب طلبك أنت.",
    },
    # ── دعم الوفاء والترقية للوظيفة (spec §8) ────────────────────────────────────────────────────
    {
        "id": "affiliates.request_wafa", "label": "اطلب دعم الوفاء", "method": "POST",
        "path": "/api/v1/affiliates/me/wafa-requests", "capability": "affiliates.self",
        "group": "دعم الوفاء والترقية",
        "help": "يقدّم طلب دعم الوفاء نيابة عنك — القرار الملزِم يبقى للمنصة لا لك.",
    },
    {
        "id": "affiliates.wafa_requests", "label": "طلبات دعم الوفاء", "method": "GET",
        "path": "/api/v1/affiliates/me/wafa-requests", "capability": "affiliates.self",
        "group": "دعم الوفاء والترقية",
        "help": "قائمة طلبات دعم الوفاء اللي قدّمتها وحالة كل واحد منها.",
    },
    {
        "id": "affiliates.wafa_eligibility", "label": "أهليتي لدعم الوفاء", "method": "GET",
        "path": "/api/v1/affiliates/me/wafa-eligibility", "capability": "affiliates.self",
        "group": "دعم الوفاء والترقية",
        "help": "كم محل باقٍ لك للمرحلة التالية — بدون تجربة طلب يُرفض.",
    },
    {
        "id": "affiliates.team_wafa_requests", "label": "طلبات دعم فريقي", "method": "GET",
        "path": "/api/v1/affiliates/me/team/wafa-requests", "capability": "affiliates.self",
        "group": "دعم الوفاء والترقية",
        "help": "طلبات فريقك المباشر المعلَّقة فقط — قرارك هنا استشاري، القرار الملزِم للمنصة.",
    },
    {
        "id": "affiliates.decide_team_wafa_request", "label": "رأيك بطلب دعم لعضو فريقك",
        "method": "POST",
        "path": "/api/v1/affiliates/me/team/wafa-requests/{}/decision", "capability": "affiliates.self",
        "group": "دعم الوفاء والترقية",
        "params": [{"name": "wafa_id", "in": "path", "type": "string", "required": True}],
        "confirm": True,
        "help": "رأيك الاستشاري بطلب دعم وفاء لأحد أفراد فريقك — القرار الملزِم يبقى للمنصة، لا لك.",
    },
    {
        "id": "affiliates.request_employment", "label": "رشّح نفسك لوظيفة", "method": "POST",
        "path": "/api/v1/affiliates/me/employment-requests", "capability": "affiliates.self",
        "group": "دعم الوفاء والترقية",
        "help": "يرسل ترشيحك لوظيفة داخل البرنامج.",
    },
    {
        "id": "affiliates.employment_requests", "label": "طلبات الترشّح للوظيفة", "method": "GET",
        "path": "/api/v1/affiliates/me/employment-requests", "capability": "affiliates.self",
        "group": "دعم الوفاء والترقية",
        "help": "قائمة طلبات ترشّحك للوظيفة وحالة كل واحد منها.",
    },
    {
        "id": "affiliates.employment_eligibility", "label": "أهليتي للترشّح لوظيفة", "method": "GET",
        "path": "/api/v1/affiliates/me/employment-eligibility", "capability": "affiliates.self",
        "group": "دعم الوفاء والترقية",
        "help": "كم عميل مشترك باقٍ لك — بدون تجربة طلب يُرفض.",
    },
    # ── محرك البحث عن عملاء محتملين — §6، للمدير أساسًا لكن الفحص ملكية لا صلاحية ────────────────────────
    {
        "id": "affiliates.set_places_api_key", "label": "مفتاح خرائط جوجل الخاص بي",
        "method": "PUT",
        "path": "/api/v1/affiliates/me/places-api-key", "capability": "affiliates.self",
        "group": "بحث العملاء المحتملين", "danger": True,
        "help": "يسجّل مفتاح خرائط جوجل الخاص بك لتشغيل بحث العملاء المحتملين — للمدير فقط، ويستبدل أي مفتاح سابق فورًا.",
    },
    {
        "id": "affiliates.places_api_key_status", "label": "حالة مفتاح خرائط جوجل", "method": "GET",
        "path": "/api/v1/affiliates/me/places-api-key", "capability": "affiliates.self", "group": "بحث العملاء المحتملين",
        "help": "تلميح فقط، أبدًا القيمة الحقيقية.",
    },
    {
        "id": "affiliates.clear_places_api_key", "label": "احذف مفتاح خرائط جوجل", "method": "DELETE",
        "path": "/api/v1/affiliates/me/places-api-key", "capability": "affiliates.self", "group": "بحث العملاء المحتملين",
        "confirm": True, "danger": True,
        "help": "يحذف مفتاح خرائط جوجل المسجّل — بحث العملاء المحتملين يتوقف حتى تسجّل مفتاحًا جديدًا.",
    },
    {
        "id": "affiliates.start_lead_search", "label": "ابدأ بحث عملاء محتملين جديد", "method": "POST",
        "path": "/api/v1/affiliates/me/leads/search", "capability": "affiliates.self", "group": "بحث العملاء المحتملين",
        "help": "بحث كامل يأخذ ساعات — يتقدّم بالخلفية، تتابعه من نفس الشاشة.",
    },
    {
        "id": "affiliates.lead_searches", "label": "عمليات البحث السابقة", "method": "GET",
        "path": "/api/v1/affiliates/me/leads/search", "capability": "affiliates.self", "group": "بحث العملاء المحتملين",
        "help": "قائمة عمليات بحث العملاء المحتملين اللي بدأتها سابقًا.",
    },
    {
        "id": "affiliates.lead_search_status", "label": "تقدّم بحث العملاء المحتملين", "method": "GET",
        "path": "/api/v1/affiliates/me/leads/search/{}", "capability": "affiliates.self", "group": "بحث العملاء المحتملين",
        "params": [{"name": "job_id", "in": "path", "type": "string", "required": True}],
        "help": "تقدّم عملية بحث محدّدة — تتابعها بدل ما تنتظر انتهاءها، فالبحث الكامل قد يأخذ ساعات.",
    },
    # ── عملائي المحتملين ────────────────────────────────────────────────────────────────
    {
        "id": "affiliates.leads", "label": "عملائي المحتملين", "method": "GET",
        "path": "/api/v1/affiliates/me/leads", "capability": "affiliates.self", "group": "عملائي المحتملين",
        "help": "المسوّق يشوف عملاءه المحتملين المُسنَدين له فقط؛ المدير يشوف ما وجده بحثه هو.",
    },
    {
        "id": "affiliates.assign_lead", "label": "أسنِد عميلًا محتملًا لمسوّق", "method": "POST",
        "path": "/api/v1/affiliates/me/leads/{}/assign", "capability": "affiliates.self",
        "group": "عملائي المحتملين",
        "params": [{"name": "lead_id", "in": "path", "type": "string", "required": True}],
        "help": "يسنِد عميلًا محتملًا من نتائج بحثك لأحد مسوّقي فريقك ليتابعه — للمدير فقط.",
    },
    {
        "id": "affiliates.set_lead_status", "label": "حدّث حالة عميل محتمل", "method": "POST",
        "path": "/api/v1/affiliates/me/leads/{}/status", "capability": "affiliates.self",
        "group": "عملائي المحتملين",
        "params": [{"name": "lead_id", "in": "path", "type": "string", "required": True}],
        "help": "يسجّل آخر تحديث لحالة تواصلك مع عميل محتمل — جزء من متابعة رحلته الحقيقية، لا تخمين.",
    },
    {
        "id": "affiliates.link_lead_registration", "label": "اربط عميلًا محتملًا بمحل مسجَّل",
        "method": "POST",
        "path": "/api/v1/affiliates/me/leads/{}/link-registration", "capability": "affiliates.self",
        "group": "عملائي المحتملين",
        "params": [{"name": "lead_id", "in": "path", "type": "string", "required": True}],
        "help": "ربط يدوي فقط — لا مطابقة تلقائية بالاسم أو الرقم.",
    },
    {
        "id": "affiliates.lead_sector_stats", "label": "إحصاء العملاء المحتملين بالقطاع",
        "method": "GET",
        "path": "/api/v1/affiliates/me/leads/sector-stats", "capability": "affiliates.self",
        "group": "عملائي المحتملين",
        "help": "إحصاء عدد العملاء المحتملين اللي وجدتها بحسب القطاع والمدينة — لبحثك أنت فقط.",
    },
    {
        "id": "affiliates.sectors", "label": "قطاعات النشاط", "method": "GET",
        "path": "/api/v1/affiliates/me/sectors", "capability": "affiliates.self", "group": "عملائي المحتملين",
        "help": "قائمة قطاعات النشاط المعتمدة، تختار منها عند إعداد بحث عملاء محتملين جديد.",
    },
    {
        "id": "affiliates.referred_shops", "label": "المحلات اللي أحلتها", "method": "GET",
        "path": "/api/v1/affiliates/me/referred-shops", "capability": "affiliates.self",
        "group": "تذاكر المحلات",
        "help": "بحاجة لهذي القائمة قبل فتح تذاكر أي محل — تعطيك رقم المحل (tenant) لكل واحد.",
    },
    # ── رحلة التحويل: المراحل والقوالب ومكتبة الأدلة ────────────────────────────────────────────
    {
        "id": "affiliates.outreach_stages", "label": "مراحل رحلة التحويل", "method": "GET",
        "path": "/api/v1/affiliates/me/outreach-stages", "capability": "affiliates.self", "group": "أدواتي",
        "help": "قائمة مراحل رحلة تحويل العميل المحتمل (تواصل أول، متابعة، إقناع...) المعتمدة حاليًا.",
    },
    {
        "id": "affiliates.upsert_outreach_stage", "label": "أضف أو عدّل مرحلة", "method": "PUT",
        "path": "/api/v1/affiliates/me/outreach-stages", "capability": "affiliates.self", "group": "أدواتي",
        "help": "للمدير فقط — فحص ملكية داخل الخدمة، لا صلاحية منفصلة.",
    },
    {
        "id": "affiliates.deactivate_outreach_stage", "label": "عطّل مرحلة", "method": "DELETE",
        "path": "/api/v1/affiliates/me/outreach-stages/{}", "capability": "affiliates.self", "group": "أدواتي",
        "params": [{"name": "code", "in": "path", "type": "string", "required": True}],
        "confirm": True,
        "help": "يعطّل مرحلة من رحلة التحويل فلا تظهر بعدها — للمدير فقط، ولا يحذف أي عميل مرتبط بها.",
    },
    {
        "id": "affiliates.templates", "label": "قوالب الرسائل", "method": "GET",
        "path": "/api/v1/affiliates/me/templates", "capability": "affiliates.self", "group": "أدواتي",
        "params": [{"name": "stage_code", "in": "query", "type": "string", "required": False}],
        "help": "قوالب الرسائل الجاهزة، مصنّفة حسب مرحلة رحلة التحويل.",
    },
    {
        "id": "affiliates.create_template", "label": "أضف قالبًا جديدًا", "method": "POST",
        "path": "/api/v1/affiliates/me/templates", "capability": "affiliates.self", "group": "أدواتي",
        "help": "للمدير فقط. القالب يظهر لكل مسوّقي البرنامج فورًا.",
    },
    {
        "id": "affiliates.update_template", "label": "عدّل قالبًا", "method": "PUT",
        "path": "/api/v1/affiliates/me/templates/{}", "capability": "affiliates.self", "group": "أدواتي",
        "params": [{"name": "template_id", "in": "path", "type": "string", "required": True}],
        "help": "يعدّل محتوى قالب موجود — للمدير فقط، والتعديل ينعكس فورًا لكل مسوّقي البرنامج.",
    },
    {
        "id": "affiliates.deactivate_template", "label": "عطّل قالبًا", "method": "DELETE",
        "path": "/api/v1/affiliates/me/templates/{}", "capability": "affiliates.self", "group": "أدواتي",
        "params": [{"name": "template_id", "in": "path", "type": "string", "required": True}],
        "confirm": True,
        "help": "يعطّل قالبًا فلا يظهر بعدها لأي مسوّق — للمدير فقط.",
    },
    {
        "id": "affiliates.template_stats", "label": "أداء القوالب", "method": "GET",
        "path": "/api/v1/affiliates/me/template-stats", "capability": "affiliates.self", "group": "أدواتي",
        "params": [{"name": "stage_code", "in": "query", "type": "string", "required": False},
                  {"name": "mine", "in": "query", "type": "boolean", "required": False}],
        "help": "أي قالب فعليًا يحرّك عميلًا للمرحلة التالية — mine=true لأدائك أنت وحدك.",
    },
    {
        "id": "affiliates.template_kind_stats", "label": "أداء أنواع المحتوى", "method": "GET",
        "path": "/api/v1/affiliates/me/template-kind-stats", "capability": "affiliates.self", "group": "أدواتي",
        "params": [{"name": "mine", "in": "query", "type": "boolean", "required": False}],
        "help": "أي نوع محتوى (نص، صورة، فيديو...) فعليًا يحرّك العميل المحتمل للمرحلة التالية — mine=true لأدائك أنت وحدك.",
    },
    {
        "id": "affiliates.log_template_use", "label": "سجّل استخدام قالب مع عميل", "method": "POST",
        "path": "/api/v1/affiliates/me/leads/{}/template-uses", "capability": "affiliates.self",
        "group": "عملائي المحتملين",
        "params": [{"name": "lead_id", "in": "path", "type": "string", "required": True}],
        "help": "يسجّل أنك استخدمت قالبًا معينًا مع عميل محتمل محدّد.",
    },
    {
        "id": "affiliates.lead_template_uses", "label": "سجل القوالب المستخدمة مع عميل",
        "method": "GET",
        "path": "/api/v1/affiliates/me/leads/{}/template-uses", "capability": "affiliates.self",
        "group": "عملائي المحتملين",
        "params": [{"name": "lead_id", "in": "path", "type": "string", "required": True}],
        "help": "سجل كل القوالب اللي استُخدمت مع عميل محتمل معيّن ونتيجة كل واحد منها.",
    },
    {
        "id": "affiliates.set_template_use_outcome", "label": "سجّل نتيجة استخدام قالب",
        "method": "PATCH",
        "path": "/api/v1/affiliates/me/template-uses/{}", "capability": "affiliates.self",
        "group": "عملائي المحتملين",
        "params": [{"name": "use_id", "in": "path", "type": "string", "required": True}],
        "help": "النتيجة دائمًا تُسجَّل يدويًا — أبدًا استنتاجًا من الوقت أو رسائل تالية.",
    },
    {
        "id": "affiliates.set_decision_maker", "label": "سجّل رقم صاحب القرار", "method": "PATCH",
        "path": "/api/v1/affiliates/me/leads/{}/decision-maker", "capability": "affiliates.self",
        "group": "عملائي المحتملين",
        "params": [{"name": "lead_id", "in": "path", "type": "string", "required": True}],
        "help": "يسجّل بيانات التواصل الحقيقية لصاحب القرار في المحل، بعد ما تحصل عليها بنفسك — لا تُخمَّن.",
    },
    {
        "id": "affiliates.stat_citations", "label": "مكتبة الأدلة", "method": "GET",
        "path": "/api/v1/affiliates/me/stat-citations", "capability": "affiliates.self", "group": "أدواتي",
        "params": [{"name": "stage_code", "in": "query", "type": "string", "required": False}],
        "help": "مكتبة أرقام وإحصاءات موثّقة المصدر تستخدمها لإقناع عميل محتمل.",
    },
    {
        "id": "affiliates.create_stat_citation", "label": "أضف رقمًا للمكتبة", "method": "POST",
        "path": "/api/v1/affiliates/me/stat-citations", "capability": "affiliates.self", "group": "أدواتي",
        "help": "يضيف رقمًا أو إحصاءً جديدًا لمكتبة الأدلة المشتركة — للمدير فقط، ومصدره يُسجَّل معه.",
    },
    {
        "id": "affiliates.update_stat_citation", "label": "عدّل رقمًا بالمكتبة", "method": "PUT",
        "path": "/api/v1/affiliates/me/stat-citations/{}", "capability": "affiliates.self", "group": "أدواتي",
        "params": [{"name": "citation_id", "in": "path", "type": "string", "required": True}],
        "help": "يعدّل رقمًا موجودًا بمكتبة الأدلة — للمدير فقط.",
    },
    {
        "id": "affiliates.deactivate_stat_citation", "label": "عطّل رقمًا بالمكتبة", "method": "DELETE",
        "path": "/api/v1/affiliates/me/stat-citations/{}", "capability": "affiliates.self", "group": "أدواتي",
        "params": [{"name": "citation_id", "in": "path", "type": "string", "required": True}],
        "confirm": True,
        "help": "يعطّل رقمًا من مكتبة الأدلة فلا يظهر بعدها — للمدير فقط.",
    },
    # ── تذاكر المحلات (spec §13) ─────────────────────────────────────────────────────────────────
    {
        "id": "affiliates.shop_tickets", "label": "تذاكر محل", "method": "GET",
        "path": "/api/v1/affiliates/me/shops/{}/tickets", "capability": "affiliates.self",
        "group": "تذاكر المحلات",
        "params": [{"name": "tenant", "in": "path", "type": "string", "required": True}],
        "help": "تذاكر الدعم لمحل أحلته أنت بنفسك — لا تصل لتذاكر محل لم تُحله.",
    },
    {
        "id": "affiliates.shop_ticket", "label": "تفاصيل تذكرة", "method": "GET",
        "path": "/api/v1/affiliates/me/shops/{}/tickets/{}", "capability": "affiliates.self",
        "group": "تذاكر المحلات",
        "params": [{"name": "tenant", "in": "path", "type": "string", "required": True},
                  {"name": "ticket_id", "in": "path", "type": "string", "required": True}],
        "help": "تفاصيل تذكرة دعم واحدة لمحل أحلته أنت.",
    },
    {
        "id": "affiliates.open_shop_ticket", "label": "افتح تذكرة لمحل", "method": "POST",
        "path": "/api/v1/affiliates/me/shops/{}/tickets", "capability": "affiliates.self",
        "group": "تذاكر المحلات",
        "params": [{"name": "tenant", "in": "path", "type": "string", "required": True}],
        "help": "يفتح تذكرة دعم جديدة باسمك لمحل أحلته أنت.",
    },
    {
        "id": "affiliates.reply_shop_ticket", "label": "ردّ على تذكرة محل", "method": "POST",
        "path": "/api/v1/affiliates/me/shops/{}/tickets/{}/replies", "capability": "affiliates.self",
        "group": "تذاكر المحلات",
        "params": [{"name": "tenant", "in": "path", "type": "string", "required": True},
                  {"name": "ticket_id", "in": "path", "type": "string", "required": True}],
        "help": "يضيف ردًا على تذكرة دعم مفتوحة لمحل أحلته أنت.",
    },
]

# THE PLATFORM'S OWN MECHANISM (see operations/app/user_actions.py, the first to use it). A
# route can be real and deliberately not an app control. THE `why` IS REQUIRED — without it this
# is a skip-list, and a skip-list is how a forgotten route stops being a fault and starts being a
# habit.
UNDECLARED_ROUTES: list[dict[str, str]] = [
    {"method": "POST", "path": "/api/v1/affiliates/apply",
     "why": "it creates the applicant an approved token would later belong to — the catalogue is "
            "fetched WITH a token, so a route that exists precisely because there is no token yet "
            "cannot appear in a list of what its holder may do"},
    {"method": "POST", "path": "/api/v1/affiliates/apply/request-otp",
     "why": "same reason as /apply, one step earlier: proving phone ownership before any account, "
            "let alone any token, exists"},
    {"method": "POST", "path": "/api/v1/affiliates/signin",
     "why": "it exchanges a phone and a password FOR a token; a caller who could fetch it as an "
            "action already has one"},
    {"method": "GET", "path": "/api/v1/affiliates/me/catalog",
     "why": "it IS the catalogue (the shop/admin aggregators' missing third sibling, "
            "affiliate_self.py::catalog) — a route the console calls to learn what a marketer "
            "may do, never a button a marketer presses himself, the same reason "
            "/api/v1/app/catalog and /api/v1/admin/catalog are not actions in their own lists "
            "either"},
    {"method": "POST", "path": "/api/v1/admin/withdrawals/{}/receipt",
     "why": "a multipart file upload — a shape the action schema's `params` cannot express "
            "(string/integer/number/boolean/enum/object/array only, no `file`). The GET twin "
            "(withdrawals.view_receipt, admin_actions.py) IS declared; uploading stays API-only "
            "until the panel grows a file-input param type"},
]
