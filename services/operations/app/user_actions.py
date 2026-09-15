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
        # ONE NAME, AND HE OWNS IT. The registry's rename is internal-only, so the owner's edit
        # comes here on his own token and we make the internal call — see the route.
        "id": "operations.set_shop_name", "label": "اسم المحل", "method": "PUT",
        "path": "/api/v1/staff/shop-name", "capability": "operations.manage",
        "group": "منشأتي",
        "help": "الاسم الذي يراه عميلك ويوقّع رسائلك. يُغيَّر متى شاء.",
    },
    {
        "id": "operations.ai_notes", "label": "ملاحظات المساعد الذكي", "method": "GET",
        "path": "/api/v1/staff/ai-notes", "capability": "operations.manage", "group": "منشأتي",
        # Absent from the catalog entirely while AI_NOTES_ENABLED is off — the route itself also
        # refuses/blanks (defense in depth), but hiding the control is what stops an owner writing
        # into a field that is quietly discarded.
        "help": "ما كتبه صاحب المحل ليساعد المساعد الآلي عبر واتساب يخدم عملاءه بمعلومات إضافية.",
    },
    {
        "id": "operations.set_ai_notes", "label": "تعديل ملاحظات المساعد الذكي", "method": "PUT",
        "path": "/api/v1/staff/ai-notes", "capability": "operations.manage", "group": "منشأتي",
        "help": "يُستخدم مباشرة لتوجيه الذكاء الاصطناعي — لا تكتب هنا بيانات شخصية لعملائك.",
    },
    {
        "id": "operations.ai_toggle", "label": "تشغيل المساعد الذكي", "method": "GET",
        "path": "/api/v1/staff/ai-toggle", "capability": "operations.read", "group": "منشأتي",
        "help": "هل المساعد الذكي عبر واتساب يرد الآن — منفصل تمامًا عن اشتراكك بالتطبيق.",
    },
    {
        "id": "operations.set_ai_toggle", "label": "تشغيل/إيقاف المساعد الذكي", "method": "PUT",
        "path": "/api/v1/staff/ai-toggle", "capability": "operations.manage", "group": "منشأتي",
        "params": [{"name": "enabled", "in": "body", "type": "boolean", "required": True}],
        "confirm": True,
        "help": "إيقافه يقفل المساعد الذكي تمامًا وكأنك غير مشترك فيه — دون إلغاء الاشتراك "
               "نفسه، وترجعه متى شئت.",
    },
    {
        "id": "operations.msg_word_limit", "label": "حد كلمات رسالة العميل", "method": "GET",
        "path": "/api/v1/staff/msg-word-limit", "capability": "operations.manage", "group": "منشأتي",
        # Absent from the catalog entirely while MSG_WORD_LIMIT_ENABLED is off — same reasoning as
        # ai_notes above.
        "help": "أطول رسالة يقبلها المساعد من العميل قبل أن يطلب منه اختصارها بلا استدعاء للذكاء "
                "الاصطناعي.",
    },
    {
        "id": "operations.set_msg_word_limit", "label": "تعديل حد كلمات رسالة العميل",
        "method": "PUT", "path": "/api/v1/staff/msg-word-limit",
        "capability": "operations.manage", "group": "منشأتي",
        "help": "بين 20 و300 كلمة — القيمة الافتراضية 100.",
    },
    {
        "id": "operations.my_operator_row", "label": "بياناتي كموظف", "method": "GET",
        "path": "/api/v1/staff/operators/me", "capability": "operations.read", "group": "الشاشة",
        "help": "قد لا تجد شيئاً — صاحب المحل نفسه ليس له صفّ موظف، وهذا رد طبيعي لا خلل.",
    },
    {
        "id": "operations.set_my_locale", "label": "لغتي", "method": "PATCH",
        "path": "/api/v1/staff/operators/me/locale", "capability": "operations.read", "group": "الشاشة",
        "help": "يغيّر لغة شاشات الميدان لهذا الموظف وحده — لا يمسّ أحداً غيره.",
    },
    {
        "id": "operations.catalogue", "label": "الخدمات", "method": "GET",
        "path": "/api/v1/field/catalogue", "capability": "operations.read", "group": "الشاشة",
        "help": "شبكة الخدمات والباقات. تبدأ فارغة، ويكتبها صاحب المحل بنفسه.",
    },
    {
        "id": "operations.get_field_service_image", "label": "صورة خدمة (للتسجيل)", "method": "GET",
        "path": "/api/v1/field/catalogue/services/{id}/image", "capability": "operations.read",
        "group": "الشاشة",
        "params": [{"name": "id", "in": "path", "type": "string", "required": True}],
        "help": "نفس صورة الخدمة، بصلاحية القراءة — لا يحتاجها إلا من يسجّل الزيارة.",
    },
    {
        "id": "operations.get_field_package_image", "label": "صورة باقة (للتسجيل)", "method": "GET",
        "path": "/api/v1/field/catalogue/packages/{id}/image", "capability": "operations.read",
        "group": "الشاشة",
        "params": [{"name": "id", "in": "path", "type": "string", "required": True}],
        "help": "نفس صورة الباقة، بصلاحية القراءة — لا يحتاجها إلا من يسجّل الزيارة.",
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
        # THE ACT THAT SPENDS AN OFFER, and it belongs to the VISIT (§5.6.2) — reminders judges
        # which offer applies, we record that it was applied. An offer that can be read and never
        # applied is a promise the counter cannot keep.
        "id": "operations.apply_offer", "label": "تطبيق العرض على الزيارة", "method": "POST",
        "path": "/api/v1/field/visits/{visit_id}/offer", "capability": "operations.record",
        "group": "الشاشة",
        "help": "نقرةٌ تُثبت أن العميل أخذه — ولا يُستهلك تلقائياً أبداً، وعرضٌ واحد لكل زيارة.",
        "params": [{"name": "visit_id", "in": "path", "type": "string", "required": True}],
    },
    {
        "id": "operations.privacy_requests", "label": "طلبات عملائي على بياناتهم", "method": "GET",
        "path": "/api/v1/field/privacy-requests", "capability": "operations.manage",
        "group": "Customers",
        "help": "ما طلبه عملاؤك من صفحاتهم: نسخة من بياناتهم أو حذفها. المنشأة هي المسؤولة نظاماً.",
    },
    {
        "id": "operations.close_privacy_request", "label": "أغلق الطلب", "method": "POST",
        "path": "/api/v1/field/privacy-requests/{request_id}/close",
        "capability": "operations.manage", "group": "Customers",
        "params": [{"name": "request_id", "in": "path", "type": "string", "required": True}],
        "confirm": True,
        "help": "يسجّل أنك أجبت العميل على طلبه. يبقى اسمك على الإجابة.",
    },
    {
        "id": "operations.erase_customer",
        "label": "حذف بيانات العميل",
        "method": "POST",
        "path": "/api/v1/field/customers/{customer_id}/erase",
        "capability": "operations.manage",
        "params": [{"name": "customer_id", "in": "path", "type": "string", "required": True}],
        "confirm": True,
        "danger": True,
        "group": "Customers",
        "help": "حذفٌ لا رجوع عنه لكل ما تحتفظ به المنصة عن هذا العميل، بناءً على طلبه هو.",
    },
    {
        # THE ONE EDIT AN OWNER NEEDED AND COULD NOT MAKE. The name arrives after five visits by
        # design (§4.3) and nothing could add it afterwards — a regular he recognised on sight
        # stayed «بلا اسم» on his screen for ever.
        "id": "operations.rename_customer", "label": "تسمية العميل", "method": "PATCH",
        "path": "/api/v1/field/customers/{customer_id}", "capability": "operations.record",
        "group": "العملاء",
        "params": [{"name": "customer_id", "in": "path", "type": "string", "required": True}],
        "help": "الاسم فقط — الرقم هوية العميل عند كل الأقسام ولا يُعدَّل.",
    },
    {
        "id": "operations.customer", "label": "سجل العميل", "method": "GET",
        "path": "/api/v1/field/customers/{id}", "capability": "operations.read",
        "group": "الشاشة",
        "params": [{"name": "id", "in": "path", "type": "string", "required": True}],
        "help": "سيارات العميل وزياراته الأخيرة، مقصورة على فرعك إن كان لزياراته فرع.",
    },
    {
        "id": "operations.customers_by_refs", "label": "عملاء من قائمة التذكيرات", "method": "POST",
        "path": "/api/v1/field/customers/resolve", "capability": "operations.read",
        "group": "الشاشة",
        # The join «عملائي» needs for its overdue tab. reminders answers with a pseudonym and holds
        # no names — deliberately — so the names are looked up where they already live.
        "help": "يحوّل الأسماء المستعارة القادمة من جدولة التذكيرات إلى عملاء هذه المنشأة. "
                "المنشأة من الجلسة لا من الطلب.",
    },
    {
        "id": "operations.ratings", "label": "التقييمات", "method": "GET",
        "path": "/api/v1/field/ratings", "capability": "operations.read",
        "group": "الشاشة",
        "help": "كل زيارة قيّمها عميل فعلياً — عبر تطبيق التقييم بعد الزيارة — قابلة للتصفية "
                "بعدد النجوم أو حالة المعالجة أو الفرع.",
    },
    {
        "id": "operations.mark_rating_handled", "label": "تمت المعالجة", "method": "PATCH",
        "path": "/api/v1/field/ratings/{visit_id}/handled", "capability": "operations.record",
        "group": "الشاشة",
        "params": [{"name": "visit_id", "in": "path", "type": "string", "required": True}],
        "help": "تسجّل إنك اطّلعت على هذا التقييم وتصرّفت حياله — لا يصير تلقائياً أبداً.",
    },
    {
        "id": "operations.staff_performance", "label": "أداء الموظفين", "method": "GET",
        "path": "/api/v1/field/staff/performance", "capability": "operations.manage",
        "group": "الشاشة",
        "params": [
            {"name": "since", "in": "query", "type": "integer", "required": True},
            {"name": "until", "in": "query", "type": "integer", "required": True},
            {"name": "branch_id", "in": "query", "type": "string", "required": False},
        ],
        "help": "لكل موظف خلال فترة محددة: عدد الزيارات، عدد التقييمات، متوسط تقييمه، ونسبة "
                "عدم حضور عملائه — تقارن أداء موظفيك ببعض. للمالك والمدير فقط.",
    },
    {
        "id": "operations.staff_performance_export", "label": "تصدير تقرير أداء الموظفين",
        "method": "POST", "path": "/api/v1/field/staff/performance/export",
        "capability": "operations.manage", "group": "الشاشة",
        "params": [
            {"name": "since", "in": "body", "type": "integer", "required": True},
            {"name": "until", "in": "body", "type": "integer", "required": True},
            {"name": "branch_id", "in": "body", "type": "string", "required": False},
            {"name": "file_format", "in": "body", "type": "string", "required": False},
        ],
        "help": "نفس تقرير أداء الموظفين، كملف Word أو PDF بتصميم البراند بدل شاشة — للمالك "
                "والمدير فقط.",
    },
    {
        "id": "operations.ensure_customer", "label": "تسجيل عميلة برقمها (بلا زيارة)", "method": "POST",
        "path": "/api/v1/field/customers/ensure", "capability": "operations.record",
        "group": "الشاشة",
        # bookings' console dialog: resolve-or-create the exact same way record_visit does, minus
        # the visit. Same capability as recording one — it is the same act.
        "help": "يحلّ العميلة برقم جوالها أو ينشئها إن لم توجد، بلا زيارة — تستعمله نافذة الحجز.",
    },
    {
        "id": "operations.customer_by_plate", "label": "بحث بلوحة السيارة", "method": "GET",
        "path": "/api/v1/field/customers/by-plate", "capability": "operations.read",
        "group": "الشاشة",
        "params": [{"name": "plate", "in": "query", "type": "string", "required": True}],
        # THE LOOKUP A VEHICLE SHOP STARTS FROM. The plate is on the bumper and the number of the
        # man who owns it is already ours; asking for it again is asking a question we can answer.
        # It was served and undeclared, which means no capability review ever saw it.
        "help": "يجيب صاحب السيارة من لوحتها. المنشأة من الجلسة لا من الطلب.",
    },
    {
        "id": "operations.customer_by_phone", "label": "بحث برقم كامل", "method": "GET",
        "path": "/api/v1/field/customers/by-phone", "capability": "operations.read",
        "group": "الشاشة",
        "params": [{"name": "phone", "in": "query", "type": "string", "required": True}],
        # The distinction that decides how the keypad is built, and it is measured rather than
        # assumed: this route is EXACT. Partial digits go to the suggest route below, because
        # search's whole-token match finds nothing for `96650` against `966501234567`.
        "help": "مطابقة تامة للرقم الكامل. البحث بأول الأرقام من لوحة المفاتيح يذهب إلى "
                "مسار الاقتراحات أدناه لا عبر هذا المسار.",
    },
    {
        "id": "operations.customer_suggest", "label": "اقتراحات بأول الأرقام", "method": "GET",
        "path": "/api/v1/field/customers/suggest", "capability": "operations.read",
        "group": "الشاشة",
        "params": [{"name": "prefix", "in": "query", "type": "string", "required": True}],
        # THE BRANCH IS RESOLVED HERE, WHICH IS THE WHOLE POINT OF THE ROUTE EXISTING (ط-3). The
        # console used to call search-service itself, and no route there knows what a branch is —
        # four typed digits handed a supervisor in Jeddah the Riyadh customers by name and number.
        "help": "قائمة اقتراحاتٍ من أول الأرقام أو اللوحة، مضيَّقةً على فرع القارئ من رمزه. "
                "«تعذّر البحث» غير «لا يوجد عميل»، والردّ يفرّق بينهما.",
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
        "id": "whatsapp.meta_config", "label": "إعدادات ربط ميتا", "method": "GET",
        "path": "/api/v1/whatsapp/config", "capability": "billing.self", "group": "حسابي",
        # WHAT THE CONSOLE NEEDS TO EVEN OPEN THE POPUP, read live from the operator-set sealed
        # values — never a build-time copy. See connect.py's own docstring on why it is safe for
        # this to travel over an ordinary authenticated call despite carrying no secret.
        "help": "معرّف تطبيق ميتا اللازم لفتح نافذة ربط واتساب.",
    },
    {
        "id": "whatsapp.register_number", "label": "تفعيل الإرسال", "method": "POST",
        "path": "/api/v1/whatsapp/connect/register", "capability": "billing.self",
        "group": "حسابي",
        # THE STEP THAT TURNS «مربوط» INTO «يرسل». Meta refuses to send from an unregistered
        # number, and the PIN is the business's own — so this is his act, retryable, and its three
        # refusals are three sentences.
        "help": "أدخل رمز التحقق بخطوتين لحساب واتساب أعمالك حتى يبدأ رقمك بالإرسال.",
    },
    {
        "id": "subscription.payment_state", "label": "حالة الدفع", "method": "GET",
        "path": "/api/v1/subscription/payment", "capability": "billing.self",
        "group": "الاشتراك",
        # THE SCREEN ASKS BEFORE IT SELLS. One key decides whether there is a live way to pay, and
        # a plans page that assumes there is hands out paid tiers for a button press.
        "help": "يقول للشاشة هل الدفع متاح، ومفتاح المتصفح العام إن كان.",
    },
    {
        "id": "subscription.apps", "label": "تطبيقاتي", "method": "GET",
        "path": "/api/v1/subscription/apps", "capability": "billing.self",
        "group": "الاشتراك",
        # ONE CALL FOR EVERY LOCK. Before this, a screen deciding whether to lock a paid surface
        # had only the CAPABILITY to go on — and an owner holds every capability on every plan, so
        # the lock never appeared for the person who would have paid to remove it.
        "help": "التطبيقات التي اشتريتها وما تفعله، ليعرف كل قسم أيعرض أم يقفل.",
    },
    {
        "id": "subscription.apps_static_features", "label": "مميزات تسجيل زيارة/جهات الاتصال/التقييم",
        "method": "GET", "path": "/api/v1/subscription/apps/static-features",
        "capability": "billing.self", "group": "الاشتراك",
        # NOT TENANT-SCOPED — same catalog for every caller (Depends(require_user) only, no
        # capability actually enforced), unlike its sibling `subscription.apps` right above which
        # answers what THIS shop owns. See the route's own docstring for why it exists: the admin
        # panel has no tenant to ask `/apps` about, and these three apps' features had no
        # standalone read the way the other five services' `.../features` routes already do.
        "help": "قائمة المميزات الحقيقية لتسجيل زيارة وجهات الاتصال والتقييم، بصياغة تسويقية قصيرة.",
    },
    {
        # `subscription.activate`, NOT `billing.subscribe` — which is what billing-service calls
        # ITS OWN subscribe action. Two services declaring one id is a collision the catalogue
        # cannot express: the console keys on the id, so one of them silently wins and the loser
        # is unreachable. And here the loser would have been OURS — the only path that enforces
        # "no paid subscription before WhatsApp is connected" (§6.2.1). The shop would have gone
        # straight to billing's raw subscribe and bought a product it cannot send with.
        "id": "subscription.activate", "label": "تفعيل الاشتراك", "method": "POST",
        "path": "/api/v1/subscription", "capability": "billing.self", "group": "حسابي",
        "help": "اختر باقتك وفعّلها. يشترط ربط واتساب قبل الاشتراك المدفوع، والتجربة معفاة.",
    },
    # ── the owner's own surface, moved here from admin_actions ─────────────────────────
    # api-gateway builds the establishment's app from THIS file and no other
    # (app_catalog.py, field="user_actions"). These sat in the platform console's catalogue,
    # so the owner's app would have rendered a nav with almost nothing in it — and the reflex
    # fix is to call the paths directly, which is exactly the rule the UI is built on. The
    # test for which file a route belongs in is whose data it is: `platform.*` is ours;
    # everything else belongs to the establishment.
    {
        "id": "operations.list_services", "label": "قائمة خدماتي ومنتجاتي", "method": "GET",
        "path": "/api/v1/field/catalogue", "capability": "operations.read", "group": "خدماتي ومنتجاتي",
        # A panel that can only ACT is half a panel: an owner needs to SEE a price before being
        # offered a button that changes it.
        "help": "الخدمات ومددها وأسعارها.",
    },
    {
        # THE OWNER'S LIST, distinct from `operations.catalogue` which is the field grid. It can
        # show what the shop has retired; the field grid must not.
        "id": "operations.manage_services", "label": "خدماتي ومنتجاتي — للإدارة", "method": "GET",
        "path": "/api/v1/staff/services", "capability": "operations.manage_services", "group": "خدماتي ومنتجاتي",
        "help": "يشمل الموقوفة عند طلبها، ليمكن إعادة تفعيلها.",
    },
    {
        "id": "operations.create_service", "label": "إضافة خدمة أو منتج", "method": "POST",
        "path": "/api/v1/staff/services", "capability": "operations.manage_services", "group": "خدماتي ومنتجاتي",
        "help": "مدة الدورة 0 تعني خدمة بلا دورة طبيعية — فلا تُنتج تذكيراً.",
    },
    {
        "id": "operations.update_service", "label": "تعديل خدمة أو منتج", "method": "PATCH",
        "path": "/api/v1/staff/services/{id}", "capability": "operations.manage_services",
        "group": "خدماتي ومنتجاتي", "confirm": True,
        "params": [{"name": "id", "in": "path", "type": "string", "required": True}],
        "help": "الإيقاف بـ active=false لا بالحذف — الحذف ييتّم كل زيارة تشير إليها.",
    },
    {
        "id": "operations.bulk_import_services", "label": "استيراد خدمات ومنتجات من ملف", "method": "POST",
        "path": "/api/v1/staff/services/bulk_import", "capability": "operations.manage_services",
        "group": "خدماتي ومنتجاتي", "confirm": True,
        "help": "ملف كامل يُرفض لو فيه أي صف خاطئ أو اسم مكرر — لا استيراد جزئي أبداً.",
    },
    {
        "id": "operations.list_packages", "label": "الباقات — للإدارة", "method": "GET",
        "path": "/api/v1/staff/packages", "capability": "operations.manage_services",
        "group": "خدماتي ومنتجاتي",
        "help": "يشمل الموقوفة عند طلبها، ليمكن إعادة تفعيلها.",
    },
    {
        "id": "operations.create_package", "label": "إنشاء باقة", "method": "POST",
        "path": "/api/v1/staff/packages", "capability": "operations.manage_services",
        "group": "خدماتي ومنتجاتي",
        "help": "خدمتان على الأقل، وسعر أكبر من صفر — لا يُشتق سعر الباقة من مكوّناتها أبداً.",
    },
    {
        "id": "operations.update_package", "label": "تعديل أو إيقاف باقة", "method": "PATCH",
        "path": "/api/v1/staff/packages/{id}", "capability": "operations.manage_services",
        "group": "خدماتي ومنتجاتي", "confirm": True,
        "params": [{"name": "id", "in": "path", "type": "string", "required": True}],
        "help": "الإيقاف بـ active=false لا بالحذف — الحذف ييتّم كل زيارة تشير إليها.",
    },
    {
        "id": "operations.upload_service_image", "label": "رفع صورة خدمة أو منتج", "method": "POST",
        "path": "/api/v1/staff/services/{id}/image", "capability": "operations.manage_services",
        "group": "خدماتي ومنتجاتي",
        "params": [{"name": "id", "in": "path", "type": "string", "required": True}],
        "help": "صورة واحدة بحد أقصى 5 ميجابايت — jpeg أو png أو webp.",
    },
    {
        "id": "operations.get_service_image", "label": "صورة خدمة أو منتج", "method": "GET",
        "path": "/api/v1/staff/services/{id}/image", "capability": "operations.manage_services",
        "group": "خدماتي ومنتجاتي",
        "params": [{"name": "id", "in": "path", "type": "string", "required": True}],
        "help": "يعرض الصورة المرفوعة حالياً، إن وُجدت.",
    },
    {
        "id": "operations.upload_package_image", "label": "رفع صورة باقة", "method": "POST",
        "path": "/api/v1/staff/packages/{id}/image", "capability": "operations.manage_services",
        "group": "خدماتي ومنتجاتي",
        "params": [{"name": "id", "in": "path", "type": "string", "required": True}],
        "help": "صورة واحدة بحد أقصى 5 ميجابايت — jpeg أو png أو webp.",
    },
    {
        "id": "operations.get_package_image", "label": "صورة باقة", "method": "GET",
        "path": "/api/v1/staff/packages/{id}/image", "capability": "operations.manage_services",
        "group": "خدماتي ومنتجاتي",
        "params": [{"name": "id", "in": "path", "type": "string", "required": True}],
        "help": "يعرض الصورة المرفوعة حالياً، إن وُجدت.",
    },
    {
        "id": "operations.list_operators", "label": "العاملون", "method": "GET",
        "path": "/api/v1/staff/operators", "capability": "operations.read", "group": "الفريق",
        "help": "فريقك في فرعك، لا فروع أخرى إن كان للمحل أكثر من فرع.",
    },
    {
        # SAME ROUTE, A SECOND DOOR — same shape as list_branches_for_bookings
        # right above: the Bookings screen calls `/staff/operators` unconditionally on mount to
        # attribute a booking and draw the staff picker, and a field operator holds `bookings.read`
        # but not `operations.read`. See staff.py::_READ_OPERATORS_FOR_BOOKINGS's own note.
        "id": "operations.list_operators_for_bookings", "label": "العاملون", "method": "GET",
        "path": "/api/v1/staff/operators", "capability": "bookings.read", "group": "الفريق",
        "help": "نفس قائمة الفريق، تُستخدم هنا لنسبة الحجز لعامل ورسم قائمة الفنيين بشاشة الحجوزات.",
    },
    {
        "id": "operations.create_operator", "label": "إضافة عامل", "method": "POST",
        "path": "/api/v1/staff/operators", "capability": "operations.manage", "group": "الفريق",
        "help": "الرمز نسبة لا تسجيل دخول: يُسأل عند الحفظ لينسب العمل لصاحبه.",
    },
    {
        "id": "operations.hire_member", "label": "توظيف بحساب", "method": "POST",
        "path": "/api/v1/staff/members", "capability": "operations.manage", "group": "الفريق",
        "help": "حسابٌ يدخل به بنفسه ودورٌ له — غير الرمز الرباعي الذي يُنسب به العمل على جهازٍ مشترك.",
    },
    {
        "id": "operations.update_operator", "label": "تعديل عامل", "method": "PATCH",
        "path": "/api/v1/staff/operators/{id}", "capability": "operations.manage",
        "group": "الفريق", "confirm": True,
        "params": [{"name": "id", "in": "path", "type": "string", "required": True}],
        "help": "فرعه هنا هو المرجع: الزيارة التي تسمّيه تُنسب إليه، لا إلى ما يرسله الجهاز.",
    },
    {
        "id": "operations.set_staff_hours", "label": "تخصيص دوام موظف", "method": "PUT",
        "path": "/api/v1/staff/operators/{id}/working-hours", "capability": "operations.manage",
        "group": "الفريق",
        "params": [{"name": "id", "in": "path", "type": "string", "required": True},
                   {"name": "weekly", "in": "body", "type": "object", "required": True}],
        "help": "يرث دوام المحل تلقائياً ما لم يُخصَّص له دوام هنا — ولا يمكن أن يتجاوز دوام المحل.",
    },
    {
        "id": "operations.clear_staff_hours", "label": "إعادة الدوام لدوام المحل", "method": "DELETE",
        "path": "/api/v1/staff/operators/{id}/working-hours", "capability": "operations.manage",
        "group": "الفريق",
        "params": [{"name": "id", "in": "path", "type": "string", "required": True}],
        "help": "يحذف دوام هذا العامل الخاص — يعود يعمل بنفس دوام المحل تلقائياً.",
    },
    {
        "id": "operations.shop_mode", "label": "نظام الفروع", "method": "GET",
        "path": "/api/v1/staff/mode", "capability": "operations.read", "group": "الفروع",
        "help": "هل المحل مركزي أم بفروع مستقلة، وهل التحويل بينهما متاح لك أصلاً.",
    },
    {
        "id": "operations.set_shop_mode", "label": "تغيير نظام الفروع", "method": "PUT",
        "path": "/api/v1/staff/mode", "capability": "operations.manage", "group": "الفروع",
        "confirm": True,
        "help": "من المركزي إلى المستقل قرارٌ يُتخذ مرة — والعودة تحتاج التواصل معنا.",
    },
    {
        "id": "operations.shop_vehicles", "label": "العمل على السيارات", "method": "GET",
        "path": "/api/v1/staff/vehicles", "capability": "operations.read", "group": "منشأتي",
        "help": "هل تسجيل الزيارة يعرض حقل رقم اللوحة والعدّاد لهذا المحل.",
    },
    {
        "id": "operations.whatsapp_flow_json", "label": "معاينة فلو واتساب", "method": "GET",
        "path": "/api/v1/whatsapp/flow-json", "capability": "operations.read", "group": "منشأتي",
        "params": [{"name": "name", "in": "query", "type": "string", "required": True}],
        # THE SAME READ «رسائلي» USES to render a Flow's real screens as an interactive preview —
        # see `connect.py::shop_whatsapp_flow_json`'s own comment on why this is not tenant-scoped.
        "help": "شاشات الفلو الحقيقية كما توّلدها notification-service — نفس ما يعرضه واتساب "
                "بالضبط، لمعاينة قالب فيه زر يفتح فلو.",
    },
    {
        "id": "operations.set_shop_vehicles", "label": "تغيير العمل على السيارات", "method": "PUT",
        "path": "/api/v1/staff/vehicles", "capability": "operations.manage", "group": "منشأتي",
        "params": [{"name": "tracks_vehicle", "in": "body", "type": "boolean",
                    "required": True}],
        "help": "إن كان العمل على السيارات ظهرت صفحة رقم اللوحة والعدّاد في تسجيل الزيارة.",
    },
    {
        "id": "operations.whatsapp_visit_registration", "label": "تسجيل الزيارة عبر واتساب",
        "method": "GET", "path": "/api/v1/staff/whatsapp-visit-registration",
        "capability": "operations.read", "group": "منشأتي",
        "help": "هل يقدر موظفوك يسجّلون الزيارة من واتساب مباشرة، بالإضافة لشاشة تسجيل الزيارة.",
    },
    {
        "id": "operations.set_whatsapp_visit_registration",
        "label": "تفعيل تسجيل الزيارة عبر واتساب", "method": "PUT",
        "path": "/api/v1/staff/whatsapp-visit-registration", "capability": "operations.manage",
        "group": "منشأتي",
        "params": [{"name": "enabled", "in": "body", "type": "boolean", "required": True}],
        "confirm": True,
        "help": "أي موظف عنده حساب دخول يقدر يسجّل زيارة من رقم واتساب الخاص فيه بدون كلمة "
               "مرور في تلك اللحظة — فرق عن شاشة تسجيل الزيارة اللي تطلب دخوله بكلمة المرور "
               "كل مرة.",
    },
    {
        "id": "operations.whatsapp_auto_register", "label": "تسجيل جهات الاتصال تلقائياً عبر واتساب",
        "method": "GET", "path": "/api/v1/staff/whatsapp-auto-register",
        "capability": "operations.read", "group": "منشأتي",
        "help": "هل يسجّل النظام تلقائياً أي رقم جديد يتواصل مع واتسابك ضمن جهات اتصالك.",
    },
    {
        "id": "operations.set_whatsapp_auto_register",
        "label": "تفعيل تسجيل جهات الاتصال تلقائياً عبر واتساب", "method": "PUT",
        "path": "/api/v1/staff/whatsapp-auto-register", "capability": "operations.manage",
        "group": "منشأتي",
        "params": [{"name": "enabled", "in": "body", "type": "boolean", "required": True}],
        "confirm": True,
        "help": "أي رقم جديد يراسل واتسابك يُحفظ تلقائياً ضمن جهات اتصالك، حتى بلا زيارة أو حجز.",
    },
    {
        "id": "operations.list_branches", "label": "الفروع", "method": "GET",
        "path": "/api/v1/staff/branches", "capability": "operations.read", "group": "الفروع",
        "help": "فروعك، وكم فرعاً تسمح به باقتك.",
    },
    {
        # SAME ROUTE, A SECOND DOOR — a field operator holds `bookings.read`
        # but not `operations.read`, and the Bookings screen genuinely needs his own branch to
        # even ask the server for a day's schedule (see staff.py::_READ_BRANCHES's own note on
        # why this is a real bug, not a missing feature). The gateway's own catalogue filter is a
        # single-capability membership test per entry, so a caller who needs the SAME read for a
        # DIFFERENT reason gets a second, separately-declared id rather than one entry two
        # audiences must each half-satisfy.
        "id": "operations.list_branches_for_bookings", "label": "الفروع", "method": "GET",
        "path": "/api/v1/staff/branches", "capability": "bookings.read", "group": "الفروع",
        "help": "نفس قائمة الفروع، تُستخدم هنا ليقدر عامل الفرع يجيب جدول يومه بشاشة الحجوزات.",
    },
    {
        "id": "operations.create_branch", "label": "إضافة فرع", "method": "POST",
        "path": "/api/v1/staff/branches", "capability": "operations.manage", "group": "الفروع",
        "help": "فرع جديد — يُحتسب ضمن عدد الفروع المسموح به في باقتك.",
    },
    {
        "id": "operations.update_branch", "label": "تعديل فرع", "method": "PATCH",
        "path": "/api/v1/staff/branches/{id}", "capability": "operations.manage",
        "group": "الفروع", "confirm": True,
        "params": [{"name": "id", "in": "path", "type": "string", "required": True}],
        "help": "الإغلاق بـ active=false لا بالحذف — الحذف يترك زيارات السنة الماضية بلا اسم فرع.",
    },
    {
        "id": "operations.grant_coupon", "label": "امنح كوبون خصم لمحل", "method": "POST",
        "path": "/api/v1/staff/coupons/grant", "capability": "operations.grant_coupon_direct",
        "group": "كوبونات",
        "help": "خصم على اشتراك محل آخر مسجّل عندنا، يُطبَّق تلقائياً عند أول تجديد قادم.",
    },
    {
        "id": "operations.coupon_history", "label": "سجل منح الكوبونات", "method": "GET",
        "path": "/api/v1/staff/coupons/history", "capability": "operations.grant_coupon",
        "group": "كوبونات", "help": "كل محاولة منح، ناجحة أو فاشلة، وسببها الحقيقي.",
    },
    {
        "id": "operations.coupon_stats", "label": "إحصائيات الكوبونات", "method": "GET",
        "path": "/api/v1/staff/coupons/stats", "capability": "operations.grant_coupon",
        "group": "كوبونات", "help": "عدد الخصومات هذا الشهر، وسقفك الحالي.",
    },
    {
        "id": "operations.coupon_check", "label": "تحقق سريع من رقم قبل المنح", "method": "GET",
        "path": "/api/v1/staff/coupons/check", "capability": "operations.grant_coupon",
        "group": "كوبونات",
        "params": [{"name": "phone", "in": "query", "type": "string", "required": True}],
        "help": "هل هذا الرقم محل مسجّل عندنا، وهل مُنح كوبوناً منك هذا الشهر بالفعل.",
    },
    {
        "id": "operations.coupon_preferences_get", "label": "إعداد خانة الكوبون بتسجيل الزيارة",
        "method": "GET", "path": "/api/v1/staff/coupons/preferences",
        "capability": "operations.grant_coupon", "group": "كوبونات",
        "help": "هل خانة منح الكوبون تظهر أثناء تسجيل الزيارة.",
    },
    {
        "id": "operations.coupon_preferences_set", "label": "تشغيل/إيقاف خانة الكوبون بتسجيل الزيارة",
        "method": "PATCH", "path": "/api/v1/staff/coupons/preferences",
        "capability": "operations.grant_coupon_direct", "group": "كوبونات",
        "help": "تحكّم كامل من صاحب المحل — تشغيل الخانة لا يعني إجباره على استخدامها.",
    },
    {
        "id": "operations.salla_install", "label": "اربط متجر سلة", "method": "GET",
        "path": "/api/v1/staff/salla/install", "capability": "billing.self", "group": "سلة",
        "help": "رابط لصفحة موافقة سلة — نفس صلاحية إدارة الاشتراك، ذاتية الخدمة من صاحب المحل.",
    },
    {
        "id": "operations.salla_disconnect", "label": "فك ربط متجر سلة", "method": "POST",
        "path": "/api/v1/staff/salla/disconnect", "capability": "billing.self", "group": "سلة",
        "help": "يزيل الربط فقط — أي تحالف مُنح سابقاً عبره يبقى كما هو.",
    },
    {
        "id": "operations.salla_status", "label": "حالة ربط سلة", "method": "GET",
        "path": "/api/v1/staff/salla/status", "capability": "billing.self", "group": "سلة",
        "help": "هل متجر سلة مربوط بهذا الحساب الآن، وأي متجر.",
    },
    {
        "id": "operations.mobile_requests_list", "label": "طلبات الخدمة المتنقلة", "method": "GET",
        "path": "/api/v1/staff/mobile-requests", "capability": "operations.mobile_requests_execute",
        "group": "خدمات متنقلة",
        "help": "قائمة الطلبات — معلّقة، مقبولة، أو الكل حسب الفلتر. الموظف الميداني يرى طلباته"
               " المُسنَدة فقط؛ المدير يرى الكل — نفس المسار، نطاق مختلف بحسب صلاحيته.",
        "params": [{"name": "status_filter", "in": "query", "type": "string", "required": False}],
    },
    {
        "id": "operations.mobile_request_create", "label": "إضافة طلب خدمة متنقلة يدوياً",
        "method": "POST", "path": "/api/v1/staff/mobile-requests",
        "capability": "operations.mobile_requests_manage", "group": "خدمات متنقلة",
        "help": "عميل اتصل أو حضر — يدخل المدير بياناته بنفسه، بدل انتظار طلب عبر واتساب. يدخل"
               " قائمة المراجعة العادية، بلا قبول تلقائي.",
    },
    {
        "id": "operations.mobile_request_risk", "label": "خطر عدم حضور الطلب", "method": "GET",
        "path": "/api/v1/staff/mobile-requests/{request_id}/risk",
        "capability": "operations.mobile_requests_manage", "group": "خدمات متنقلة",
        "help": "تحذير بسيط قبل القبول — لا يمنع ولا يفرض شيئاً.",
    },
    {
        "id": "operations.mobile_request_accept", "label": "قبول طلب خدمة متنقلة", "method": "POST",
        "path": "/api/v1/staff/mobile-requests/{request_id}/accept",
        "capability": "operations.mobile_requests_manage", "group": "خدمات متنقلة",
        "help": "بعدها التواصل والتنسيق يصير مباشرة بين المحل والعميل، خارج المنصة.",
    },
    {
        "id": "operations.mobile_request_reject", "label": "رفض طلب خدمة متنقلة", "method": "POST",
        "path": "/api/v1/staff/mobile-requests/{request_id}/reject",
        "capability": "operations.mobile_requests_manage", "group": "خدمات متنقلة",
        "help": "مع سبب اختياري، لو حبيت توثّقه.",
    },
    {
        "id": "operations.mobile_request_complete", "label": "الموعد تم", "method": "POST",
        "path": "/api/v1/staff/mobile-requests/{request_id}/complete",
        "capability": "operations.mobile_requests_execute", "group": "خدمات متنقلة",
        "help": "يسجّل زيارة حقيقية فوراً — نقاط الولاء وكل شيء آخر يُحسب تلقائياً. الموظف"
               " المُسنَد له الطلب فقط يقدر يسويها لطلبه؛ المدير يقدر على أي طلب.",
    },
    {
        "id": "operations.mobile_request_no_show", "label": "الموعد لم يتم", "method": "POST",
        "path": "/api/v1/staff/mobile-requests/{request_id}/no-show",
        "capability": "operations.mobile_requests_execute", "group": "خدمات متنقلة",
        "help": "لا زيارة تُسجَّل — يُحسب فقط في سجل عدم الحضور. نفس نطاق «الموعد تم».",
    },
    {
        "id": "operations.mobile_request_assign", "label": "إسناد طلب لموظف", "method": "POST",
        "path": "/api/v1/staff/mobile-requests/{request_id}/assign",
        "capability": "operations.mobile_requests_manage", "group": "خدمات متنقلة",
        "help": "اختياري بالكامل — تسمية من سينفّذ الطلب، ليعرف تحميل كل موظف ويقدر يوزّع بنفسه.",
    },
]


# Routes deliberately NOT rendered as app controls, each with the reason. The wiring gate reads
# this list and refuses an entry without a `why`.
UNDECLARED_ROUTES: list[dict[str, str]] = [
    {"method": "GET", "path": "/api/v1/account/me/locale",
     "why": "the platform-wide language preference (api/v1/__init__.py) needs NO capability at "
            "all — require_user only, deliberately, so an owner (who holds no operations.* "
            "capability of his own) can reach it too. Every entry below states a real capability "
            "the console's own action catalogue filters on; declaring one here would be false "
            "documentation of a check this route does not make. The console calls it directly "
            "(api.ts's getMyLocale), same as the two routes right below it"},
    {"method": "PATCH", "path": "/api/v1/account/me/locale",
     "why": "same reasoning as the GET immediately above — setMyLocale, no capability required"},
    {"method": "POST", "path": "/api/v1/signup",
     "why": "it creates the account a token would come from — an action is fetched WITH a token, "
            "so a signed-in owner's control list is the one place this must never appear"},
    {"method": "POST", "path": "/api/v1/signup/signin",
     "why": "it exchanges a phone and a password FOR a token; a caller who could fetch it as an "
            "action already has one"},
    {"method": "GET", "path": "/api/v1/till/customer",
     "why": "the same machine's route, in the other direction: a point-of-sale asks what the "
            "customer standing at it holds. No person presses it, and our own screens ask the "
            "field routes instead"},
    {"method": "POST", "path": "/api/v1/till/redeem",
     "why": "redemption from a till we do not own (§9.8). Our own screens redeem through loyalty "
            "directly with the operator's token; this exists for a cashier's software"},
    {"method": "POST", "path": "/api/v1/till/offer/apply",
     "why": "the cashier's software applies the offer to the visit it just posted, on a service "
            "account credential. Our own screens apply it through the field route with the "
            "operator's token; rendering this in a console would offer an owner a button that "
            "spends a discount against a visit his till has not recorded"},
    {"method": "POST", "path": "/api/v1/till/visits",
     "why": "a machine's route, not a control: it is called by a shop's point-of-sale on a service "
            "account credential, and no person ever presses it. Rendering it in a console would "
            "offer an owner a button that posts an invoice he does not have"},
    {"method": "POST", "path": "/api/v1/signup/claim",
     "why": "the owner of a shop his till company enrolled, opening it for the first time — he has "
            "no token yet, which is the whole reason this route exists"},
    {"method": "POST", "path": "/api/v1/signup/code",
     "why": "it asks for a code to prove a number that does not have an account yet — a caller who "
            "could fetch it as an action would already hold the token it exists to produce"},
    {"method": "POST", "path": "/api/v1/signup/verify",
     "why": "it spends that code; same reason, and the refusal it gives is identical for an unknown "
            "number and a wrong code"},
    {"method": "GET", "path": "/api/v1/till/status",
     "why": "the till's own connectivity/heartbeat read, on a service account credential — no "
            "person presses it, and our own screens have nothing that needs it"},
    {"method": "GET", "path": "/api/v1/till/branches",
     "why": "the till's own list of this shop's branches, same service-account door as "
            "/till/customer above — an owner picks a branch from /staff/branches instead"},
    {"method": "GET", "path": "/api/v1/till/bookings",
     "why": "a till reading today's bookings at the counter, same machine credential as every "
            "other till.py route; the console reads bookings through bookings-service directly"},
    {"method": "POST", "path": "/api/v1/till/bookings/{}/attend",
     "why": "the till marking a booking attended at the counter — same service-account door as "
            "the rest of this file"},
    {"method": "POST", "path": "/api/v1/till/operators/verify-pin",
     "why": "the till confirming an operator's PIN at the counter, on a service account "
            "credential — see staff.py's own module docstring on what a PIN is for"},
    {"method": "POST", "path": "/api/v1/till/rating-request",
     "why": "the till expediting a rating request at the counter, same machine credential as "
            "every other till.py route"},
    {"method": "POST", "path": "/api/v1/till/coupons/grant",
     "why": "an external store/site granting a shop-to-shop coupon from a real order, same "
            "service-account door as every other till.py route — the console reaches the same "
            "engine through /staff/coupons/grant instead"},
    {"method": "GET", "path": "/api/v1/salla/callback",
     "why": "Salla's own browser redirect back after the owner approves the consent screen — "
            "arrives with no Bearer token to check, same reasoning as signup's own unauthenticated "
            "pair; a signed-in owner starts a NEW install from operations.salla_install instead"},
    {"method": "POST", "path": "/api/v1/salla/webhook",
     "why": "Salla's own server calling us on a subscribed event, verified by HMAC signature "
            "instead of a Bearer token — see api/v1/salla.py's own module docstring"},
]
