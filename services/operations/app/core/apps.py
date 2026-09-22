"""What has this establishment actually bought — asked once, answered for the whole console.

THE DEFECT THIS CLOSES. Every screen that shows a paid surface had to decide for itself whether the
shop owned it, and none of them could: the console renders a lock from a CAPABILITY, which is about
the person's role. An owner holds `campaigns.manage` on every plan, so the lock never appeared for
the one person who would have paid to remove it. The only screen that knew better was «محلّي», and
only because the insights dashboard happened to return `entitlements` alongside its numbers — one
key, folded into an unrelated payload, for one screen.

ONE CALL, NOT ONE PER SCREEN. Five keys asked five times from five screens is five round trips to
billing on every navigation, and five different answers during a deploy. Asked here, together, the
console holds one list and every lock in the product is drawn from it.

────────────────────────────────────────────────────────────────────────────────────────────────
THIS IS A DISPLAY, AND IT ENFORCES NOTHING

Not a softness — a boundary. The gates are in the services that own the acts (campaigns' create and
tick, loyalty's earn and adjust, insights' dashboard), they are asked at the act, and they fail
closed. If this answer were tampered with, the buttons it draws would still be refused by the
service behind them.

WHICH IS WHY IT DOES NOT FAIL CLOSED. A billing outage here would paint «لم تشترِ» across apps the
shop pays for every month — the worst sentence in the product to show a paying customer, and it
would be shown to ALL of them at once. Instead the failure is reported as itself: `checked: false`,
no ownership claimed either way, and a screen that says «تعذّر التحقق» and offers to retry.
"""
from __future__ import annotations

import asyncio
import urllib.error
import urllib.parse
from typing import Any
# `is_base` lives with the subscribe rules because "carries the message meter" is a statement
# about the price list, not about this catalogue. Imported rather than repeated: two
# spellings of «this row is a base» is how the two drift apart.
from app.core.subscribe import is_base
from app.adapters import internal_http

# ── real, separately-nameable features (2026-09-11 CTO decision: "features, not services") ─────
#
# EVERY ENTRY IS REAL CODE, CITED TO THE EXACT MECHANISM — never a marketing adjective invented
# for this file. Same discipline, same wire shape (id/title/detail/icon/tone/shared_with/
# owned_by), as bookings-service's own `core/features.py` (the first pilot app) — see that file's
# docstring for the four tests a candidate feature has to pass. `shared_with`/`owned_by` are how a
# capability that is not this app's own code (the reminders engine) still renders the identical
# sentence wherever it is granted, from one authored source.
VISIT_FEATURES: tuple[dict[str, Any], ...] = (
    {"id": "visit.no_duplicates", "title": "يحافظ على دقة سجلاتك وتقاريرك",
     "detail": "لا تتكرر الزيارة نفسها حتى لو ضغط موظفك \"حفظ\" مرتين، فتبقى أرقامك موثوقة دائماً",
     "icon": "check-circle", "tone": "teal", "shared_with": [], "owned_by": "",
     # `Operations.record_visit`'s own idempotency-key read (core/operations.py:282-302) — one
     # indexed read, before the customer is even resolved, so a retried request never creates a
     # second visit OR a second customer.
     },
    {"id": "visit.works_offline", "title": "يواصل العمل معك أينما انقطع الاتصال",
     # NOT "افتح التطبيق بلا نت أبداً" — the page itself still needs a connection to load once.
     # What this is: the tablet's signal drops for thirty seconds several times a day in a
     # workshop/بنشر, mid-shift, and work must not stop for it — see console's own
     # `queue.ts` module docstring for the same distinction stated to a developer.
     "detail": "يحفظ الزيارة فور تسجيلها ويرسلها تلقائياً بمجرد عودة الاتصال",
     "icon": "cloud", "tone": "blue", "shared_with": [], "owned_by": "",
     # `apps/console/src/queue.ts` — a LOCAL WRITE FIRST, a request second: the screen confirms
     # "تم الحفظ ✓" the instant the visit lands in a local (browser-storage) queue, never when the
     # server answers, and the queue drains behind the operator with the SAME idempotency key on
     # every retry so a request that actually succeeded is never sent twice. `_sane_occurred_at`
     # (core/operations.py:692) is this feature's other half, server-side: it clamps a claimed
     # timestamp that is in the future or older than `max_backdate` (default 90 days) rather than
     # trusting a device clock that drifted while offline.
     },
    {"id": "visit.finds_by_plate", "title": "يتعرّف على عميلك من أول لحظة",
     "detail": "يبحث عنه برقم لوحة سيارته مباشرة، فتختصر عليه وعلى نفسك وقت الانتظار",
     "icon": "car", "tone": "violet", "shared_with": [], "owned_by": "",
     # `_resolve_asset` (core/operations.py:428-441) — a visit looked up/created by plate SCOPED
     # WITHIN the customer (two customers can share a transcribed plate), and every recorded visit
     # returns the customer's FULL list of known plates so the next search finds either car.
     },
    {"id": "visit.invoice_computed", "title": "يحفظ لك كل ريال من فاتورتك",
     "detail": "يجمع السعر تلقائياً من كتالوج خدماتك، فتبقى فاتورتك دقيقة دون حساب يدوي",
     "icon": "receipt", "tone": "amber", "shared_with": [], "owned_by": "",
     # `record_visit`'s own catalogue-priced total (core/operations.py:346-359) — summed from the
     # shop's own priced services when no till sends a total, retiring the old rule that
     # invoice-value point-earning needed a till integration at all (2026-09-08).
     },
    {"id": "visit.never_loses_a_visit", "title": "يحفظ لك كل عملية بيع",
     "detail": "حتى خدمة جديدة لم تُسجَّل بكتالوجك بعد، تُحفظ زيارتها فوراً وتضيفها لاحقاً",
     "icon": "shield-check", "tone": "teal", "shared_with": [], "owned_by": "",
     # `record_visit`'s unknown-service absorption (core/operations.py:307-335, integration path
     # only) — an unrecognised service id is folded into the tenant's catch-all and its real label
     # preserved, rather than the whole visit being refused: losing the visit loses the CUSTOMER
     # relationship entirely — no reminder, no points, ever — which is the worse loss by far.
     },
    {"id": "visit.instant_search", "title": "يختصر وقت وقوف عميلك أمامك",
     "detail": "تظهر النتائج فور كتابة أول حرف من اسمه أو رقمه",
     "icon": "search", "tone": "blue", "shared_with": [], "owned_by": "",
     # `GET /field/customers/suggest` (api/v1/field.py:418+) — a real prefix-match (terms) +
     # whole-token search (people) merged into one autocomplete list, branch-scoped from the
     # caller's own token rather than a filter the browser could choose for itself.
     },
    {"id": "reminders.learns_each_customer", "title": "يعيد إليك عميلك دون أي جهد منك",
     "detail": "يتعلّم موعد عودة كل عميل المعتاد، ويذكّره به في وقته تلقائياً",
     "icon": "bell", "tone": "rose", "shared_with": ["bookings"], "owned_by": "reminders",
     # NOT THIS SERVICE'S OWN CODE — the engine lives in `services/reminders/app/core/
     # adaptive.py`/`engagement.py`, and a shop owning EITHER تسجيل زيارة or الحجوزات gets the
     # exact same one (`subscribed_write` ORs `visit_licence`/`bookings_licence`).
     #
     # THE CANONICAL TEXT LIVES IN `services/reminders/app/core/features.py::SHARED_FEATURES` —
     # this copy exists only because services in this fleet do not import each other's code, and
     # `ci/check_shared_features_match.py` fails the build the moment this drifts from that
     # canonical wording (or from bookings-service's own copy) by so much as one character.
     },
)

CONTACTS_FEATURES: tuple[dict[str, Any], ...] = (
    {"id": "contacts.register_anywhere", "title": "يوسّع قاعدة عملائك من أول لحظة",
     "detail": "يكفي رقم جواله لتسجيله، حتى قبل أول زيارة له",
     "icon": "user-plus", "tone": "violet", "shared_with": [], "owned_by": "",
     # `Operations.ensure_customer` (core/operations.py:577-590) — resolve-or-create by phone,
     # the SAME backend act `record_visit` uses, built so `bookings` (and this free app) can get a
     # real customer id before there is any visit to attach one to.
     },
    {"id": "contacts.findable_immediately", "title": "يجعله جاهزاً للخدمة فوراً",
     "detail": "يصبح قابلاً للبحث لحظة تسجيله، قبل أول زيارة له",
     "icon": "search", "tone": "blue", "shared_with": [], "owned_by": "",
     # `ensure_customer` indexes the new customer for search IMMEDIATELY (api/v1/field.py:342-348),
     # unlike a customer who only appears once a first visit is recorded elsewhere.
     },
    # «عملائي»'s own «من تأخّر» tab (apps/console/src/screens/Customers.tsx) — merged into this
    # app's own feature list (2026-09-16, the owner's own instruction: «عملائي» IS «جهات الاتصال»,
    # one app not two) rather than repeated as a second, unattributed capability. THE ENGINE OWNS
    # THE DEFINITION of "overdue" (that screen's own note) — this reads `reminders.list_schedule`'s
    # pending, past-due entries and resolves them to real customers via
    # `operations.customers_by_refs`, never re-deriving a cycle/last-visit rule of its own.
    {"id": "contacts.finds_who_stopped_coming", "title": "يتابع عملاءك ويُنبّهك بمن انقطع",
     "detail": "يراقب موعد عودة كل عميل تلقائياً، ويُبرز من توقّف عن الحضور لتحتويه قبل أن يغادرك فعلاً",
     "icon": "alert-triangle", "tone": "amber", "shared_with": [], "owned_by": "",
     # NOT a copy of a reminders-authored sentence (unlike `reminders.learns_each_customer` above)
     # — this is «عملائي»'s OWN tab/join built on top of reminders' read, so it carries no
     # `shared_with`/`owned_by` attribution and is exempt from the shared-features byte-match CI
     # check that only applies to a literal shared copy.
     },
)

# التقييم — THE OWNER'S OWN FRAMING (2026-09-11): "يفهم عميله اللي مكمّل ليه مكمّل، واللي ما يكمل
# ليه قرر المغادرة... اهم تطبيق عشان يفهم الاحتياج الفعلي لعملاءه وسلوكهم ورغباتهم". Not "collects
# a star rating" — a direct read on WHY a customer stays or leaves, and a real workflow for acting
# on it before he actually leaves. Collection lives in `services/reminders` (rating_request.py,
# rating_settings.py, rating_cta.py); reading and acting on what comes back is this service's own
# code (`Operations.ratings`/`mark_rating_handled`, core/operations.py:447-468) — both cited below.
RATING_FEATURES: tuple[dict[str, Any], ...] = (
    {"id": "rating.understands_why_they_leave", "title": "يفهم ليش عميلك يرجع أو يهرب",
     "detail": "يسمع رأيه الصريح بعد كل زيارة، فتعرف بالضبط وين تكسب رضاه ووين تخسره",
     "icon": "star", "tone": "amber", "shared_with": [], "owned_by": "",
     # `Visit.rating`/`Visit.feedback_text` (core/models.py:399-409) — stars AND free-text kept
     # per visit, not a number alone; delivered as a real WhatsApp Flow
     # (services/reminders/app/core/rating_request.py) replacing the plain confirmation, never a
     # second message.
     },
    {"id": "rating.catches_unhappy_before_they_leave", "title": "يحافظ لك على عميلك القلقان",
     "detail": "أي تقييم سيئ يوصلك فوراً فتحتويه بنفسك، فيشعر عميلك أن صوته مسموع ويرجع لك",
     "icon": "shield-check", "tone": "teal", "shared_with": [], "owned_by": "",
     # `Operations.ratings`/`mark_rating_handled` (core/operations.py:447-468) — the console's
     # «التقييمات» tab: يُفلتَر بالنجوم أو بحالة المعالجة، ويُسجَّل صراحة متى وبأي ملاحظة تعامل
     # معها إنسان حقيقي — أبداً تلقائياً (Visit.rating_handled_at's own docstring).
     },
    {"id": "rating.right_moment_to_ask", "title": "يسأل عميلك ورأيه لسه طازج",
     "detail": "يصله السؤال بعد الزيارة مباشرة، فيجيبك بصدق قبل ما ينسى تفاصيلها",
     "icon": "clock", "tone": "blue", "shared_with": [], "owned_by": "",
     # `rating_settings.py` (services/reminders) — `delay_minutes` قابل للتعديل لكل منشأة (1
     # دقيقة إلى أسبوع)، لا رقم ثابت للمنصة كلها.
     },
    {"id": "rating.rewards_honest_feedback", "title": "يرفع نسبة استجابة عملائك لك",
     "detail": "يكافئ عميلك بنقاط على كل تقييم يشاركك به، فيتحول رأيه الصادق إلى عادة متكررة",
     "icon": "gift", "tone": "violet", "shared_with": [], "owned_by": "",
     # `rating_settings.py`'s own `points` field + `rating_cta.py::line` (services/reminders) —
     # الحافز يُذكر بلا ربطه برقم نجوم معيّن، عشان ما يحيّز إجابته. العميل نفسه يستفيد هنا، لا
     # الموظف فقط — رأيه يتحول لنقاط تُصرف بمحلك.
     },
    {"id": "rating.finds_your_hidden_gems_and_your_real_stars", "title": "يكشف لك نجوم فريقك الحقيقيين",
     "detail": "يقارن موظفيك بعدل — جودة الخدمة مع نشاطه الفعلي معاً — فتعرف من يستحق المكافأة فعلاً",
     "icon": "users", "tone": "indigo", "shared_with": [], "owned_by": "",
     # `Operations.staff_performance` (core/operations.py) + bookings-service's own
     # `BookingStore.no_show_summary` — GET /api/v1/field/staff/performance, gated
     # `operations.manage`. THE FAIRNESS ITSELF is the point (owner's own repeated correction this
     # session: raw-average ranking punishes a busy operator's larger sample unfairly) — quality
     # AND engagement rate AND volume are three separate numbers here, never blended into one
     # misleading score.
     },
    {"id": "rating.early_warning_before_it_costs_you", "title": "ينبهك بمجرد بدء تراجع أداء موظف",
     "detail": "يوصلك التنبيه أول ما يبدأ التراجع، فتتدارك الموقف بالتدريب قبل ما تخسر عملاءه",
     "icon": "bell", "tone": "warning", "shared_with": [], "owned_by": "",
     # `core/rating_alerts.py` — a rolling window of this operator's own most-recent RATED visits
     # (never a calendar period, never fewer than a real minimum sample), average below a fixed
     # threshold, sends an in-app notice (`InAppNotifier`) to whoever manages his branch. An early
     # signal that opens the door to coaching — never a silent verdict discovered weeks later,
     # after real customers have already stopped coming back.
     },
    {"id": "rating.exportable_report_for_the_whole_team", "title": "تقرير أداء جاهز تشاركه مع فريقك",
     "detail": "ملف Word أو PDF بأداء كل موظف، تطبعه لاجتماع الفريق أو ترسله لمن يتخذ القرار",
     "icon": "receipt", "tone": "blue", "shared_with": [], "owned_by": "",
     # `POST /api/v1/field/staff/performance/export` (core/staff_performance_render.py +
     # pdf_convert.py) — نفس أرقام لوحة المقارنة، بصيغة مستند حقيقي قابل للطباعة والمشاركة، لا
     # تصوير شاشة.
     },
)

MOBILE_REQUESTS_FEATURES: tuple[dict[str, Any], ...] = (
    # Standalone by the owner's own decision (2026-09-15): a shop with no other app at all can buy
    # this and take requests, entered by hand or over WhatsApp once that app is added later —
    # never a prerequisite either way (see deploy/seed/plans.json's own `plan.standalone` note
    # beside this row). Same "what does this get me" bar every other FEATURES tuple here holds.
    {"id": "mobile_requests.reaches_customers_who_never_visit", "title": "يوصلك لعملاء ما كانوا يجونك",
     "detail": "خدمتك تروح لعنده هو، بدل ما ينتظر يفضّى ويجيك — تكسب عميلاً ما كان ليصير عميلك",
     "icon": "map-pin", "tone": "violet", "shared_with": [], "owned_by": "",
     # core/mobile_requests.py's own `maps_link` — a real clickable pin, no مكتب حجوزات منفصل.
     },
    {"id": "mobile_requests.you_decide_every_request", "title": "أنت من يقرر كل طلب",
     "detail": "ما فيه قبول تلقائي — تراجع كل طلب بنفسك وتقرر تقبله أو ترفضه قبل أي التزام",
     "icon": "check-circle", "tone": "success", "shared_with": [], "owned_by": "",
     # PENDING حتى مراجعة بشرية — core/mobile_requests.py's own module docstring.
     },
    {"id": "mobile_requests.real_working_hours_only", "title": "لا وقت وهمي، فقط أوقات دوامك الحقيقية",
     "detail": "العميل يختار موعده من أوقات دوامك الفعلية — لا كلام حر يحتاج تخمين",
     "icon": "clock", "tone": "amber", "shared_with": [], "owned_by": "",
     # `validate_requested_time()` — نفس جدول ساعات العمل المستخدم بالحجوزات.
     },
    {"id": "mobile_requests.assign_who_you_want", "title": "توزّع الطلبات بيدك، بلا نظام يفرض عليك",
     "detail": "اختياري بالكامل — تسنِد كل طلب لمن تراه مناسباً، وتشوف حمل كل موظف قبل ما تقرر",
     "icon": "users", "tone": "blue", "shared_with": [], "owned_by": "",
     # `assign()` — never auto-routed, owner's own words: "طلبات تترص وانتهينا".
     },
    {"id": "mobile_requests.completed_visit_counts_like_any_other", "title": "الزيارة المكتملة تُحسب زي أي زيارة",
     "detail": "لما تعلّم الموعد «تم»، تنسجل زيارة حقيقية — نقاطك وتقاريرك تشتغل عليها تلقائياً",
     "icon": "check-circle", "tone": "success", "shared_with": ["feature.loyalty", "feature.insights.engine"],
     "owned_by": "",
     # `complete()` calls `record_visit()` مباشرة — نفس مسار أي زيارة أخرى.
     },
)

COUPONS_FEATURES: tuple[dict[str, Any], ...] = (
    # An earlier pass here listed the automatic-redemption mechanism, the privacy design, and the
    # per-attempt audit trail as "features". Cut (owner's own correction, 2026-09-14): those are
    # internal guarantees the engine keeps regardless, not something a shop chooses this app FOR.
    # A feature answers "what does this get me", stated as a business result — the same bar
    # RATING_FEATURES/VISIT_FEATURES/CONTACTS_FEATURES already hold above, now also enforced by
    # `ci/check_every_app_has_features.py` (existence only, never wording — that judgment stays a
    # human's at review time).
    {"id": "coupons.grows_your_customer_base", "title": "يوسّع قاعدة عملائك من محلات تثق بها",
     "detail": "محل يشتري منك يصير عميلك أيضاً بمنصتنا — علاقة تجارية جديدة بلا أي تكلفة إعلان",
     "icon": "user-plus", "tone": "violet", "shared_with": [], "owned_by": "",
     # `CouponService.grant` (core/coupons.py) — الخصم فعلياً على اشتراك المحل الثاني معنا.
     },
    {"id": "coupons.keeps_your_discount_worth_something", "title": "يحافظ على قيمة خصمك دائماً",
     "detail": "خصم غير متراكم، بمدة محددة — يبقى ذا قيمة حقيقية للمحل الذي منحته إياه",
     "icon": "check-circle", "tone": "success", "shared_with": [], "owned_by": "",
     # `Coupon.max_redemptions=1` + `_GRANT_WINDOW_SECONDS` (core/coupons.py) — مرة وحدة، شهر واحد.
     },
    {"id": "coupons.measures_the_partnership", "title": "يعطيك سجلاً كاملاً لكل محل منحته",
     "detail": "تعرف بالضبط كم خصم منحت، ولمين، ومتى — تقيس أثر تعاونك بأرقام حقيقية",
     "icon": "clock", "tone": "amber", "shared_with": [], "owned_by": "",
     # `CouponService.history`/`stats` — شاشة «تحالف استراتيجي» الخاصة بالتطبيق.
     },
    # ADDED (owner's own idea, 2026-09-15): the loop that makes this app pay for ITSELF, not just
    # the beneficiary. A shop that grants the discount is very often a SUPPLIER of the beneficiary
    # (the beneficiary reorders consumable stock from the granter) — a beneficiary that sells
    # through its own stock faster, because its own subscription just got cheaper and it can
    # afford to market harder, reorders sooner and more often. The granter's own turnover moves
    # because of a discount it gave away, not despite it.
    {"id": "coupons.speeds_up_your_own_turnover", "title": "يسرّع دوران بضاعتك أنت أيضاً",
     "detail": "الشريك اللي دعمته ينمو ويبيع أسرع، فيطلب منك أكثر — نجاحه يرجع عليك مبيعات حقيقية",
     "icon": "trending-up", "tone": "violet", "shared_with": [], "owned_by": "",
     },
)

# SHARE OF `feature.referral_partnership` — see docs/خطة-شراكة-استراتيجية-الإحالة.md and
# core/referral_partnership.py's own module docstring. NOT `coupons.py`: a completely different
# feature, financially unrelated — this one never touches money, pricing, or billing at all.
REFERRAL_PARTNERSHIP_FEATURES: tuple[dict[str, Any], ...] = (
    {"id": "referral.brings_you_ready_customers", "title": "يجلب لك عملاء جاهزين من محل تثق به",
     "detail": "عميل حقق شرطاً عند شريكك يصير مستحقاً لعرضك تلقائياً — بلا أي إثبات يحمله",
     "icon": "user-plus", "tone": "violet", "shared_with": [], "owned_by": ""},
    {"id": "referral.zero_manual_work", "title": "يكتشف الاستحقاق تلقائياً، بلا أي عمل يدوي",
     "detail": "يمر عبر نفس نقطة تسجيل الزيارة — لا شاشة إضافية، لا سؤال العميل عن شي",
     "icon": "check-circle", "tone": "success", "shared_with": [], "owned_by": ""},
    {"id": "referral.you_stay_in_control", "title": "الاتفاقية بموافقتك الصريحة دائماً",
     "detail": "لا تبدأ ولا تتوقف قبل أوانها إلا بموافقة الطرفين — أنت من يقرر شروطك",
     "icon": "clock", "tone": "amber", "shared_with": [], "owned_by": ""},
    {"id": "referral.real_numbers_not_guesses", "title": "أرقام حقيقية تبني عليها قرار التجديد",
     "detail": "كم إحالة أُرسلت، كم استُخدمت فعلاً، والاتجاه عبر الوقت — لمحلك أنت فقط",
     "icon": "trending-up", "tone": "violet", "shared_with": [], "owned_by": ""},
)

# ── the apps we sell ──────────────────────────────────────────────────────────────────────────
#
# THE KEY IS THE AUTHORITY, NOT THE PLAN NAME (§16.4.1). «الذكية» is a commercial word marketing
# changes; `feature.campaigns` is what the code asks. This list is what the console renders and
# what `ci/check_entitlements.py` compares against the price list, so an app sold and not listed
# here is an app nobody can see they own.
#
# `screen` is where the lock is drawn.
#
# AND `feature.api` IS NOT HERE, DELIBERATELY. It is not a base-included feature and not a sold
# app either — the owner's own call (2026-09-16) was to close the programmatic link entirely
# rather than price it or fold it into every app: `core/licence.py`'s `ClosedApiLicence` refuses
# every till, unconditionally, regardless of plan (`settings.API_LINK_ENABLED`, default `False`).
# A row here would draw a buy button for something nobody can buy at any price.
APPS: tuple[dict[str, Any], ...] = (
    {"key": "feature.campaigns", "name": "الحملات", "screen": "messages",
     "what": "يعيد إليك عملاءك على وشك مغادرتك، فيكبر إيرادك من قاعدة عملائك الحالية بدل الاعتماد "
             "على زبون جديد فقط."},
    {"key": "feature.loyalty", "name": "برنامج النقاط", "screen": "points",
     "what": "يبني ولاء عميلك لمحلك نفسه، لا لموظف بعينه — فيضمن رجوعه إليك دائماً أياً كان من "
             "يخدمه."},
    {"key": "feature.insights.engine", "name": "صفقات", "screen": "local",
     "what": "يحوّل بيانات محلك اليومية إلى نصيحة واضحة بمستوى محلل مبيعات مختص، يقودك كل يوم "
             "لأعلى فرصة ترفع دخلك."},
    {"key": "feature.bookings", "name": "الحجوزات", "screen": "bookings",
     "what": "يستثمر كل دقيقة في جدولك، فيرفع عدد العملاء الذين تخدمهم بنفس عدد موظفيك وساعاتهم."},
    {"key": "feature.rating", "name": "التقييم", "screen": "ratings",
     "what": "يحميك من خسارة عملاء دون علمك — يكشف مشكلة بموظف أو خدمة وتعالجها قبل أن تتفاقم.",
     "features": list(RATING_FEATURES)},
    {"key": "feature.whatsapp", "name": "بوت خدمة العملاء الذكي", "screen": "connect",
     "what": "يحوّل واتساب إلى مندوب مبيعات يعرف ذوق كل عميل، ويقترح عليه باقاتك وعروضك ونقاطه في "
             "الوقت المناسب، فيرفع متوسط فاتورتك."},
    # ADDED 2026-09-11 — ci/check_listed_apps_are_wired.py caught these two the same way it was
    # built to catch feature.rating/feature.whatsapp: both plan rows flipped to `listed: true`
    # (plans.json) the day «تسجيل زيارة»/«جهات الاتصال» shipped as standalone apps, and this tuple
    # was never updated to match — no shop, no admin, could see either existed to buy. Also the
    # first two rows here to carry a real `features` list (see `VISIT_FEATURES`/`CONTACTS_FEATURES`
    # above) — the older rows keep their single `what` line for now, unchanged in this pass.
    {"key": "feature.visit", "name": "تسجيل زيارة", "screen": "field",
     "what": "يجعل بيانات عملائك ملكاً لمحلك، تكبر معك مهما تغيّر فريق العمل.",
     "features": list(VISIT_FEATURES)},
    {"key": "feature.contacts", "name": "جهات الاتصال", "screen": "field",
     "what": "يبني لك قاعدة عملاء حقيقية من أول يوم لافتتاح محلك، تصبح أصلاً تسوّق عليه متى شئت.",
     "features": list(CONTACTS_FEATURES)},
    # SHOP-TO-SHOP COUPONS — see deploy/seed/plans.json's own note beside «كوبونات», and
    # docs/خطة-كوبونات-محل-لمحل.md for the full design. `screen: "coupons"` names the console
    # section a LATER pass builds (nav.ts tab + visit-screen checkbox) — declared here now, backend
    # first, so `ci/check_listed_apps_are_wired.py` never sees this row missing once the plan is
    # listed.
    {"key": "feature.partner_loyalty", "name": "ولاء الشركاء", "screen": "partner-loyalty",
     "what": "امنح محلاً آخر مسجّلاً عندنا خصماً حقيقياً على اشتراكه معنا — يُطبَّق تلقائياً عند "
             "تجديده القادم، ويقوّي علاقتك التجارية مع من تتعامل معهم.",
     "features": list(COUPONS_FEATURES)},
    # MOBILE/ON-THE-GO SERVICE REQUESTS — see core/mobile_requests.py's own module docstring for
    # the full design. STANDALONE (owner's own decision, 2026-09-15) — a shop with no other app at
    # all may buy this: requests can be added by the shop's own staff manually (POST /staff/
    # mobile-requests) from day one, and over WhatsApp too once that app is added later; neither
    # is ever required first.
    {"key": "feature.mobile_requests", "name": "خدمات متنقلة", "screen": "mobile-requests",
     "what": "خدمتك تروح لعنده هو — يطلب موعداً، تراجعه وتقرر، ثم تسجّله زيارة حقيقية بعد ما تتم "
             "فعلاً.",
     "features": list(MOBILE_REQUESTS_FEATURES)},
    # REFERRAL PARTNERSHIP — backend-only for now (this pass). See
    # docs/خطة-شراكة-استراتيجية-الإحالة.md and core/referral_partnership.py's own module docstring.
    # `screen: "referral-partnership"` names the console section a LATER, UI-only pass builds —
    # declared here now so `ci/check_listed_apps_are_wired.py` never sees this row missing once the
    # plan is listed (same posture `feature.coupons`'s own row took, above).
    {"key": "feature.referral_partnership", "name": "شراكة استراتيجية (إحالة عملاء)",
     "screen": "referral-partnership",
     "what": "عميل يحقق شرطاً عند محل تثق به يصير مستحقاً تلقائياً لعرضك — بموافقة الطرفين، بلا أي "
             "لمسة مالية منّا.",
     "features": list(REFERRAL_PARTNERSHIP_FEATURES)},
    # MOBILE AI ASSISTANT — on-device (apps/mobile only, Gemma 4 via flutter_gemma), no console
    # screen AT ALL, ever — unlike `feature.referral_partnership`'s own row above (a console UI
    # that landed LATER), this app's whole surface lives on the phone, by design (owner's own
    # words: "كل شي بتطبيق الجوال لانه كل شي في تطبيق الجوال"). `screen` still names a real,
    # stable id (not a console route) purely so `ci/check_listed_apps_are_wired.py`'s own
    # listed-row/registry-row pairing has something to match against — see plans.json's own note
    # on this row for the full pricing story (0 today, a real subscribe/cancel plan regardless).
    {"key": "feature.mobile_ai_assistant", "name": "المساعد الذكي (تطبيق الجوال)",
     "screen": "mobile-ai-assistant",
     "what": "يجاوبك ويرشدك داخل التطبيق بصوتك أو بالكتابة، فوراً وبلا انتظار."},
)

# BOTH ROWS ABOVE WERE MISSING FOR THE SAME REASON, FOUND THE SAME DAY: a plan's
# `listed: true` flip in plans.json and this tuple's own row are TWO HALVES of one change, and
# both `feature.rating` and `feature.whatsapp` had their plan flipped (priced, listed, sold —
# `بوت خدمة العملاء الذكي` at 19900, `التقييم` at 9900) while this file kept the OLD comment
# explaining why the row did not exist YET — never updated once the "yet" became "now". Neither
# app appeared anywhere a shop or an admin could see it, despite being fully built and sold.
# `ci/check_listed_apps_are_wired.py` is the gate that now catches exactly this drift — a listed,
# single-feature plan row with no matching entry here fails the build, so this cannot happen
# silently again.

KEYS: tuple[str, ...] = tuple(a["key"] for a in APPS)

# ── apps that cannot be DELIVERED at all without a connected WhatsApp number ──────────────────
#
# THE DISTINCTION FROM EVERY OTHER APP (see subscribe.py's own long note on why connecting is a
# NEXT STEP, never a gate). That reasoning holds for an app whose value survives an unconnected
# week — the field screen, the customers, the points, the indicators all work from the first
# minute. It does NOT hold for an app whose entire product IS a WhatsApp message: a campaign send
# with nowhere to send, a rating request nobody receives, an AI assistant with no channel to
# assist on. Selling one of these three unconnected is not "deferred delivery", it is selling
# nothing — the owner's own distinction (2026-09-20).
#
# `feature.whatsapp`   — بوت خدمة العملاء الذكي, IS the WhatsApp channel.
# `feature.rating`     — رسالة التقييم تصل عبر واتساب فقط، لا قناة بديلة اليوم.
# `feature.campaigns`  — الحملات ترسل رسائل واتساب تسويقية، هذا هو المنتج بالكامل.
#
# A NEW APP DECLARES ITSELF HERE, ONE LINE, THE SAME PASS IT SHIPS — never inferred from its name
# or screen, so the set stays exactly what someone actually decided rather than what looked right.
REQUIRES_WHATSAPP_KEYS: frozenset[str] = frozenset({
    "feature.whatsapp", "feature.rating", "feature.campaigns",
})


def requires_whatsapp_connection(keys: set[str] | frozenset[str]) -> bool:
    """Does buying (or already holding) any of these feature keys need a connected number to be
    worth anything at all?"""
    return bool(keys & REQUIRES_WHATSAPP_KEYS)


def licence_attr(key: str) -> str:
    """The `container` attribute a key's own `feature_licence.py` licence is wired under.

    ONE RULE, DERIVED, NEVER HAND-COPIED A SECOND TIME. `container.py` already names every wired
    licence by stripping the constant `"feature."` prefix and turning every remaining dot into an
    underscore (`feature.visit` → `visit_licence`, `feature.insights.engine` →
    `insights_engine_licence`) — this is that same rule, written once, so `api/subscribed.py`'s
    generic "does this shop hold ANY app at all" gate can be BUILT from `KEYS` above instead of
    carrying its own hand-typed tuple of attribute names next to it.

    THE BUG THIS REPLACES. `api/subscribed.py::_ANY_APP` used to be exactly such a hand-typed
    tuple, written the day the OR-gate first existed and never revisited when `feature.coupons`,
    `feature.insights.engine`, and `feature.mobile_requests` each shipped as their own standalone,
    no-prerequisite app afterward. Each of the three already had (and keeps) its own narrow,
    door-specific entitlement check elsewhere (`core/coupons.py::granter_is_subscribed`,
    `core/mobile_requests.py::is_subscribed`) — those were never broken. What silently drifted was
    the ONE list of apps allowed to satisfy an ordinary shop-management write (staff, branches,
    services, an offer redeemed): a shop paying for `feature.coupons` alone, with no other app,
    was wrongly refused that write, because its licence's attribute name was simply never added to
    the second list. Deriving the attribute name from `KEYS` instead of retyping it means a fourth
    future standalone app joins this gate for free, the moment it is wired onto the container —
    nothing in `subscribed.py` has to be remembered a second time.
    """
    return key.removeprefix("feature.").replace(".", "_") + "_licence"


CANNOT_ASK = "تعذّر التحقق من اشتراكك الآن — حاول بعد قليل."


class NullApps:
    """Answers from what a test put in it. Production requires the http driver — a console that
    cannot read entitlements would draw every lock open, on every screen, for every shop."""

    driver = "null"

    def __init__(self, owned: set[str] | None = None) -> None:
        self.owned: set[str] = set(owned or set())
        # A test that wants the outage path sets this. It is not "owns nothing": the two are
        # different answers and the whole point of `checked` is that they never merge.
        self.reachable = True

    async def held(self, tenant: str) -> tuple[set[str], bool]:
        if not self.reachable:
            return set(), False
        return set(self.owned), True


class HttpApps:
    """billing-service's entitlement check, asked once per key, concurrently."""

    driver = "http"

    def __init__(self, *, billing_url: str, check_path: str, token: str,
                 timeout: int = 8) -> None:
        self._url = billing_url.rstrip("/") + check_path
        self._token = token
        self._timeout = timeout

    def _ask(self, tenant: str, key: str) -> bool | None:
        """True, False, or None for «could not ask» — three answers, never two.

        Collapsing the third into False is precisely the bug this module exists to avoid: it turns
        an outage into a sentence telling a paying shop it has not paid.
        """
        query = urllib.parse.urlencode({"tenant": tenant, "key": key})
        try:
            # Built in adapters/internal_http.py, the one place this service attaches the token.
            out: dict[str, Any] = internal_http.get_json(
                f"{self._url}?{query}", self._token, self._timeout)
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
            return None
        return bool(out.get("allowed"))

    async def held(self, tenant: str) -> tuple[set[str], bool]:
        """(the keys held, whether every key got a real answer).

        CONCURRENTLY, in threads: these are five blocking stdlib calls and the console waits on all
        of them. Sequentially this is five timeouts deep on the one screen an owner opens when he
        is already unhappy about money.
        """
        if not tenant:
            # No establishment on the token is not a shop, and asking would be asking about
            # everybody at once. Answered, not errored: `checked` is true because nothing failed.
            return set(), True
        answers = await asyncio.gather(
            *(asyncio.to_thread(self._ask, tenant, key) for key in KEYS))
        held = {key for key, ok in zip(KEYS, answers) if ok is True}
        return held, all(a is not None for a in answers)


def build_apps(settings: Any) -> Any:
    """`http` when billing is wired, `null` otherwise — and main.py refuses null in production."""
    url = getattr(settings, "BILLING_SERVICE_URL", "") or ""
    path = getattr(settings, "BILLING_CHECK_PATH", "") or ""
    if not url or not path:
        return NullApps()
    return HttpApps(billing_url=url, check_path=path,
                    token=getattr(settings, "INTERNAL_SERVICE_TOKEN", "") or "",
                    timeout=int(getattr(settings, "PEER_TIMEOUT_SECONDS", 8) or 8))


def renewals_by_key(rows: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    """Every live subscription this shop holds, keyed by the app it pays for — `""` for the base.

    THE DATE WAS ALREADY IN HAND AND WAS THROWN AWAY. `/apps` fetched the whole subscription list,
    kept the base's renewal date and dropped every other row on the floor. So a shop paying for
    three things saw one date and discovered the other two on its card statement — the same defect
    family as every other value this product computes and never says out loud.

    THE ROW NAMES ITS OWN APP. `limits_snapshot` is what the plan granted, so the entitlement key
    inside it IS the app; nothing here enumerates the price list, and an app added tomorrow is
    carried by this without being mentioned. A row granting no key we sell is skipped rather than
    guessed at — a capacity pack is not an app and has no card to sit on.
    """
    out: dict[str, dict[str, Any]] = {}
    for row in rows or ():
        limits = row.get("limits_snapshot") or {}
        seen = {"status": row.get("status", ""), "renews_at": row.get("current_period_end", 0),
                "plan_id": row.get("plan_id", "")}
        if is_base(limits):
            out.setdefault("", seen)
            continue
        for key in KEYS:
            if key in limits:
                out.setdefault(key, seen)
    return out


def orphaned_dependents(rows: list[dict[str, Any]] | None, held: set[str]) -> list[str]:
    """Which subscription ids declare `plan.requires_any` and hold NONE of it any more — a
    dependent app (برنامج النقاط/التقييم/فرصي/الحملات) whose prerequisite (تسجيل زيارة/الحجوزات)
    was cancelled by ANY path, not just the console's own cascade button.

    A FEATURE, NOT A TASK (owner's own instruction, 2026-09-11) — deliberately NOT a scheduled,
    server-wide sweep. `apps()` (subscription.py) calls this on every ordinary read of a tenant's
    own apps — which is nearly every screen a shop opens — and cancels whatever this names right
    there. One tenant, the one already being read, at the moment somebody is actually looking; no
    new recurring job scanning every tenant whether or not anyone is.

    Skips a row already `cancel_at_period_end` — no point re-cancelling a cancellation already in
    flight, and it keeps this idempotent across repeated reads before billing's own sweep finishes
    the schedule.
    """
    from app.core.subscribe import requires_any
    out: list[str] = []
    for row in rows or ():
        if row.get("status") == "canceled" or row.get("cancel_at_period_end"):
            continue
        need = requires_any(row.get("limits_snapshot"))
        sub_id = str(row.get("id") or "")
        if need and sub_id and not (set(need) & held):
            out.append(sub_id)
    return out


def public(held: set[str], checked: bool, base: dict[str, Any] | None = None,
           renewals: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """The shape the console renders.

    `owned` is only ever claimed when we ASKED and were answered. On a failed check every app is
    reported unknown rather than unowned, and the screen has a third state to draw.

    `base` IS THE SUBSCRIPTION ITSELF — its plan and when it renews. It arrives from billing's
    subscription list (v0.16.7) rather than from an entitlement flag, which is the difference
    between «عندك أساس» and «اشتراكك يتجدّد في 12 سبتمبر»: the second is the first thing an owner
    opening this screen wants to know, and until that route existed we could not say it.
    """
    return {
        "checked": checked,
        "message": "" if checked else CANNOT_ASK,
        # `renews_at` PER APP, not for the base alone. It is `None` — not zero and not absent —
        # when this shop does not hold the app or billing could not be read, because «لا أعرف»
        # and «لا يتجدّد» are two different sentences and a screen must be able to tell them apart.
        "apps": [{**a, "owned": (a["key"] in held) if checked else None,
                  "renews_at": ((renewals or {}).get(a["key"], {}).get("renews_at") or None)
                               if checked else None}
                 for a in APPS],
        # The flat list, for the screens that only need «هل أملك هذا».
        "keys": sorted(held) if checked else [],
        "base": base,
    }
