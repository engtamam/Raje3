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
        "help": "شبكة الخدمات. تبدأ فارغة، ويكتبها صاحب المحل بنفسه.",
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
    },
    {
        "id": "operations.delete_service_image", "label": "حذف صورة خدمة أو منتج", "method": "DELETE",
        "path": "/api/v1/staff/services/{id}/image", "capability": "operations.manage_services",
        "group": "خدماتي ومنتجاتي", "confirm": True,
        "params": [{"name": "id", "in": "path", "type": "string", "required": True}],
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
    },
    {
        "id": "operations.delete_package_image", "label": "حذف صورة باقة", "method": "DELETE",
        "path": "/api/v1/staff/packages/{id}/image", "capability": "operations.manage_services",
        "group": "خدماتي ومنتجاتي", "confirm": True,
        "params": [{"name": "id", "in": "path", "type": "string", "required": True}],
    },
    {
        "id": "operations.list_operators", "label": "العاملون", "method": "GET",
        "path": "/api/v1/staff/operators", "capability": "operations.read", "group": "الفريق",
    },
    {
        # SAME ROUTE, A SECOND DOOR — same shape as list_branches_for_bookings
        # right above: the Bookings screen calls `/staff/operators` unconditionally on mount to
        # attribute a booking and draw the staff picker, and a field operator holds `bookings.read`
        # but not `operations.read`. See staff.py::_READ_OPERATORS_FOR_BOOKINGS's own note.
        "id": "operations.list_operators_for_bookings", "label": "العاملون", "method": "GET",
        "path": "/api/v1/staff/operators", "capability": "bookings.read", "group": "الفريق",
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
    },
    {
        "id": "operations.shop_mode", "label": "نظام الفروع", "method": "GET",
        "path": "/api/v1/staff/mode", "capability": "operations.read", "group": "الفروع",
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
    },
    {
        "id": "operations.set_shop_vehicles", "label": "تغيير العمل على السيارات", "method": "PUT",
        "path": "/api/v1/staff/vehicles", "capability": "operations.manage", "group": "منشأتي",
        "params": [{"name": "tracks_vehicle", "in": "body", "type": "boolean",
                    "required": True}],
        "help": "إن كان العمل على السيارات ظهرت صفحة رقم اللوحة والعدّاد في تسجيل الزيارة.",
    },
    {
        "id": "operations.list_branches", "label": "الفروع", "method": "GET",
        "path": "/api/v1/staff/branches", "capability": "operations.read", "group": "الفروع",
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
    },
    {
        "id": "operations.create_branch", "label": "إضافة فرع", "method": "POST",
        "path": "/api/v1/staff/branches", "capability": "operations.manage", "group": "الفروع",
    },
    {
        "id": "operations.update_branch", "label": "تعديل فرع", "method": "PATCH",
        "path": "/api/v1/staff/branches/{id}", "capability": "operations.manage",
        "group": "الفروع", "confirm": True,
        "params": [{"name": "id", "in": "path", "type": "string", "required": True}],
        "help": "الإغلاق بـ active=false لا بالحذف — الحذف يترك زيارات السنة الماضية بلا اسم فرع.",
    },
]


# Routes deliberately NOT rendered as app controls, each with the reason. The wiring gate reads
# this list and refuses an entry without a `why`.
UNDECLARED_ROUTES: list[dict[str, str]] = [
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
]
