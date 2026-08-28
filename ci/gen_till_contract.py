#!/usr/bin/env python3
# =============================================================================
# gen_till_contract.py — the integration document a POS vendor reads, GENERATED.
#
# A HAND-WRITTEN INTEGRATION DOC LIES, and it lies on a schedule: it is correct the week it is
# written and wrong from the first field anybody adds. The vendor then builds against the document
# rather than the API, ships, and the failure arrives months later as "your API is broken" — with
# their engineer holding our own page as evidence.
#
# So the fields come from the Pydantic models the routes actually validate, the paths from the
# manifest the gateway actually routes, and the prose — the parts a generator cannot know — from
# this file, next to the thing it explains.
#
# TWO OUTPUTS, ONE SOURCE. The Arabic guide (docs/دليل-ربط-الكاشير.md) is the shop-facing one — an
# owner reads it to understand what his till company is asking to connect. The English one
# (docs/pos-integration-guide.md) is the one their ENGINEER actually builds against — most POS/till
# vendors integrating with a Saudi platform still write their own technical docs and code in
# English regardless of the shop's language. Both are read from the exact same `models()`/`routes()`
# extraction, so neither can drift from the routes, or from each other, without CI catching it.
#
#   python3 ci/gen_till_contract.py           # write both docs
#   python3 ci/gen_till_contract.py --check   # fail if either file is stale (CI)
# =============================================================================
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TILL = ROOT / "services" / "operations" / "app" / "api" / "v1" / "till.py"
OUT = ROOT / "docs" / "دليل-ربط-الكاشير.md"
OUT_EN = ROOT / "docs" / "pos-integration-guide.md"

C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"

# The Arabic sentence for each field. A generator can read a name and a type; only a person can say
# why the field exists — and a table of names with no reasons is a table a vendor guesses from.
#
# KEYED BY MODEL AND FIELD, not by field alone. `name` on a visit is the customer's and `name` on
# an invoice line is the product's — a single table gave the line "اسمه إن كان عندكم", which is a
# sentence a vendor would read and then send us a person's name as a product.
WHY: dict[str, str] = {
    "phone": "رقم عميل المحل. بدونه لا يُعرف صاحب الزيارة ولا تصله رسالة.",
    "name": "اسمه إن كان عندكم. اختياري.",
    "plate": "لوحة المركبة — مطلوبة عملياً في البنشر والمغاسل والتنجيد.",
    "branch_id": "الفرع الذي وقعت فيه العملية. إلزاميّ، ويجب أن يكون فرعاً لدى المحل نفسه — نرفض ما لا نعرفه ونسمّيه لكم في الردّ.",
    "operator_id": "حساب الكاشير عندكم. يُسجَّل كما أُرسل — لا نبني نظام حسابات ثانياً.",
    "meter": "قراءة العدّاد، لقطاع المركبات.",
    "note": "ملاحظة حرة تظهر للمالك.",
    "lines": "أسطر الفاتورة. منها يُبنى كتالوج المحل تلقائياً، فأرسلوها كما هي.",
    "invoice_id": "رقم فاتورتكم. أفضل مفتاح لمنع التكرار لأنه معرّفكم أنتم للبيعة نفسها.",
    "idempotency_key": "مفتاحكم الخاص لمنع التكرار، إن كان لديكم واحد.",
    "occurred_at": "وقت البيعة بساعتكم (ثوانٍ). يُستعمل مفتاحاً للتكرار حين لا يوجد رقم فاتورة.",
    "product_id": "معرّف الصنف عندكم.",
    "qty": "الكمية.",
    "amount_minor": "المبلغ بالهللات — لا ريالات ولا كسور عشرية.",
    "reward_id": "معرّف المكافأة كما وصلكم من /till/customer.",
    "actor": "حساب الكاشير الذي سلّم المكافأة.",
    "visit_id": "معرّف الزيارة التي سُجِّلت عندنا للتوّ — عليها يُسجَّل استعمال العرض، لا على العرض نفسه.",
}

# Where a field name means two different things, the model decides.
WHY_BY_MODEL: dict[str, dict[str, str]] = {
    "TillLineIn": {"name": "اسم الصنف كما هو في فاتورتكم — منه نبني كتالوج المحل."},
    "TillRedeemIn": {"phone": "رقم العميل الذي يستبدل.",
                     "plate": "أو لوحته، إن كان التعريف عندكم باللوحة.",
                     # REQUIRED HERE and optional on a visit — the same field name, two different
                     # obligations, and a vendor reading "إن كان لديكم واحد" on a mandatory field
                     # would ship without it and double a customer's spent points.
                     "idempotency_key": "مفتاحكم لهذه العملية — إلزامي. بلا مفتاحٍ ثابت تُصرف "
                                        "نقاط العميل مرتين عند أول إعادة إرسال.",
                     # A REWARD فوق حدّ الموافقة يرفضه loyalty بلا اسم مدير — وهذا الحقل هو
                     # الطريقة الوحيدة لتزويده من كاشيرٍ متكامل.
                     "approved_by": "اسم أو معرّف المدير الذي وافق — مطلوبٌ فقط لمكافأةٍ فوق حدّ "
                                    "الموافقة بهذا المحل (يظهر لكم بحقل `needs_approval` من "
                                    "/till/customer). بلا هذا الحقل تُرفض تلك المكافآت دائماً."},
    "TillOfferIn": {"phone": "رقم العميل صاحب العرض.",
                    "plate": "أو لوحته، إن كان التعريف عندكم باللوحة.",
                    "actor": "حساب الكاشير الذي طبّق العرض."},
}

# The English counterpart of WHY, above — same field, same reason, said once more for the
# engineer who will actually be reading a Pydantic error message and this table side by side.
WHY_EN: dict[str, str] = {
    "phone": "The shop's customer's phone number. Without it we cannot attribute the visit or "
             "message them.",
    "name": "Their name, if you have it. Optional.",
    "plate": "Vehicle plate — used in practice by tyre shops, car washes and upholstery shops.",
    "branch_id": "The branch where this happened. Required, and must be a branch this shop "
                 "actually has — an id we don't recognise is rejected and named back to you.",
    "operator_id": "Your own cashier account id. Stored as sent — we do not build a second "
                   "accounts system.",
    "meter": "Odometer reading, for the vehicle sector.",
    "note": "A free-text note, visible to the owner.",
    "lines": "Invoice line items. The shop's catalogue is built from these automatically — send "
             "them as they are.",
    "invoice_id": "Your own invoice number. The best idempotency key, because it is your own "
                  "identifier for this exact sale.",
    "idempotency_key": "Your own idempotency key, if you have one.",
    "occurred_at": "When the sale happened, by your own clock (unix seconds). Used as the "
                   "idempotency key when there is no invoice number.",
    "product_id": "Your own product/item id.",
    "qty": "Quantity.",
    "amount_minor": "Amount in halalas — never riyals, never a decimal.",
    "reward_id": "The reward id, exactly as returned by GET /till/customer.",
    "actor": "The cashier account that handed the reward over.",
    "visit_id": "The id of the visit just recorded — the offer is stamped onto THIS, never onto "
               "the offer itself.",
}

WHY_BY_MODEL_EN: dict[str, dict[str, str]] = {
    "TillLineIn": {"name": "The product/service name exactly as on your invoice — the shop's "
                           "catalogue is built from this."},
    "TillRedeemIn": {"phone": "The phone number of the customer redeeming.",
                     "plate": "Or their plate, if that is how you identify customers.",
                     # REQUIRED HERE, optional on a visit — same field, two different
                     # obligations; an integrator who reads "optional" off the wrong model ships
                     # without it and a customer's points get spent twice.
                     "idempotency_key": "Your key for THIS operation — required. Without a "
                                        "stable key, a retry spends the customer's points a "
                                        "second time.",
                     "approved_by": "Name/id of the manager who approved this — required ONLY "
                                    "for a reward above this shop's approval threshold (flagged "
                                    "to you as `needs_approval` from GET /till/customer). "
                                    "Without it, those specific rewards are always refused."},
    "TillOfferIn": {"phone": "The phone number of the customer holding the offer.",
                    "plate": "Or their plate, if that is how you identify customers.",
                    "actor": "The cashier account that applied the offer."},
}


def models(text: str) -> dict[str, list[tuple[str, str, bool]]]:
    """name -> [(field, type, required)], read from the file the routes validate against."""
    out: dict[str, list[tuple[str, str, bool]]] = {}
    for block in re.split(r"\nclass ", text)[1:]:
        name = block.split("(", 1)[0].strip()
        if not name.startswith("Till"):
            continue
        fields: list[tuple[str, str, bool]] = []
        for line in block.splitlines():
            m = re.match(r"\s{4}(\w+):\s*([\w\[\]|. ]+?)\s*=\s*Field\((.*)$", line)
            if not m:
                continue
            field, typ, args = m.group(1), m.group(2).strip(), m.group(3)
            required = "default" not in args
            fields.append((field, typ, required))
        if fields:
            out[name] = fields
    return out


def routes(text: str) -> list[tuple[str, str]]:
    """[(METHOD, path)] for every route actually mounted on this router — read from the decorator,
    not from `render()`'s own prose.

    THIS IS THE HALF THE OLD GATE NEVER HAD (ك-10). `--check` compared the generated document to
    `render()`'s OWN output — so a document that hand-picked which endpoints to describe could
    drift from the router forever and `--check` would keep saying it matched, because the thing it
    matched was equally incomplete. `/till/offer/apply` shipped, was never added to `render()`, and
    the generator had no way to notice — it was never asked to look at the router at all.
    """
    return [(m.group(1).upper(), m.group(2))
           for m in re.finditer(r'@router\.(get|post|patch|delete)\("([^"]*)"', text)]


def _row(model: str, field: str, typ: str, required: bool) -> str:
    why = WHY_BY_MODEL.get(model, {}).get(field) or WHY.get(field, "")
    return f"| `{field}` | {typ} | {'نعم' if required else 'لا'} | {why} |"


def _row_en(model: str, field: str, typ: str, required: bool) -> str:
    why = WHY_BY_MODEL_EN.get(model, {}).get(field) or WHY_EN.get(field, "")
    return f"| `{field}` | {typ} | {'yes' if required else 'no'} | {why} |"


def render() -> str:
    text = TILL.read_text(encoding="utf-8")
    m = models(text)
    lines: list[str] = []
    add = lines.append

    add("# دليل ربط نقاط البيع — راجِع")
    add("")
    add("**هذا الملف مولَّد من الكود.** حقولُه مقروءة من النماذج التي تتحقّق منها المسارات "
        "فعلاً، لا مكتوبة بيد — لأن وثيقة ربطٍ مكتوبة بيد تصير كاذبة عند أول حقل يُضاف، "
        "ويبني المزوّد على الورقة بدل الواجهة.")
    add("")
    add("---")
    add("")
    add("## الاعتماد")
    add("")
    add("**اعتماد آلة واحد لكل محل** (OAuth2 client-credentials). المستأجر يُقرأ من الاعتماد "
        "نفسه ولا يُرسَل في الجسم — **ولا يوجد حقل له أصلاً**، فصندوقٌ لا يستطيع الكتابة في "
        "محلٍّ آخر حتى لو حاول.")
    add("")
    add("**وصلاحية واحدة:** `operations.record`. يسجّل زيارة ويقرأ ما يخصّ عميلها ويسلّم "
        "مكافأة — ولا يملك شيئاً غير ذلك.")
    add("")
    add("**وحدُّ الاستعلام نسبةٌ إلى الزيارات المسجَّلة، لا رقمٌ ثابت.** الاستعلام عن عميل "
        "يُرجع اسمه ورصيده — وهو ما يحتاجه الكاشير، وهو أيضاً ما يستخرج قاعدة العملاء كاملة "
        "إن تكرّر على الأرقام. فما تستطيعون الاستعلام عنه في اليوم مربوطٌ بما سجّلتموه من "
        "زيارات: النسبة سخيّة بحيث لا يبلغها صندوقٌ حقيقي مهما ازدحم، ولا تحتاجون فعل شيء. "
        "وإن بلغتموها فالردّ **429** برسالةٍ تشرح — لا 403، فالاعتماد سليم ولم يُلغَ.")
    add("")
    add("**وللتجربة:** نصنع لكم محلاً تجريبياً بنفس المسارات ونفس القواعد ونفس الرفض، "
        "وبلا مال: لا عمولة عليه ولا يُحسب عميلاً. **ولا اعتماد تجريبي خاص** — تجرّبون "
        "بالاعتماد نفسه الذي ستستعملونه، فما يثبت عندكم يعمل في الإنتاج.")
    add("")
    add("---")
    add("")

    add("## 1. إرسال الزيارات — `POST /api/v1/till/visits`")
    add("")
    add("**دفعة حتى 50 زيارة، والنتيجة لكل عنصر على حدة**: `accepted` أو `duplicate` أو "
        "`rejected` ومعه سببه. عنصرٌ مرفوض شأنكم أنتم بعد عددٍ محدود من المحاولات — "
        "**ولا يوقف ما خلفه في الطابور**.")
    add("")
    # HOW TO PAIR AN ANSWER WITH A SALE, WRITTEN DOWN (ك-7). Without this the integrator matches on
    # `idempotency_key` — and when they did not send one we derive it from the invoice number, so
    # the key in the answer is a string they never held. An SDK that cannot pair does the only two
    # things left to it, and both are wrong: re-post the whole batch, or drop it whole.
    add("**كيف تربطون كل نتيجة بما أرسلتم:** بـ`index` — موضع الزيارة في مصفوفة `visits` "
        "كما أرسلتموها أنتم (يبدأ من 0). النتائج مرتّبة عليه، وطولها يساوي عدد ما أرسلتم. "
        "لا تعتمدوا على `idempotency_key` في المطابقة: إن لم ترسلوه اشتققناه نحن من رقم "
        "الفاتورة، فيعود إليكم نصٌّ لم يكن بحوزتكم.")
    add("")
    add("### حقول الزيارة")
    add("")
    add("| الحقل | النوع | إلزامي | لماذا |")
    add("|---|---|---|---|")
    for field, typ, req in m.get("TillVisitIn", []):
        add(_row("TillVisitIn", field, typ, req))
    add("")
    add("### سطر الفاتورة")
    add("")
    add("| الحقل | النوع | إلزامي | لماذا |")
    add("|---|---|---|---|")
    for field, typ, req in m.get("TillLineIn", []):
        add(_row("TillLineIn", field, typ, req))
    add("")
    add("### منع التكرار — القاعدة الوحيدة التي لا تساهل فيها")
    add("")
    add("**كل زيارة يجب أن تحمل واحداً من ثلاثة:** `idempotency_key` أو `invoice_id` أو "
        "`occurred_at`. وبلا واحدٍ منها **تُرفض** برسالة تسمّي الثلاثة.")
    add("")
    add("والسبب: إعادةُ إرسالٍ بعد ردٍّ ضائع هي الحالة الطبيعية عندكم، وبلا مفتاحٍ ثابت "
        "تصير البيعة الواحدة زيارتين — **وتاريخُ العميل يتضاعف، وتذكيراته تتضاعف، ونقاطه "
        "تتضاعف**، ويسأل المالك لماذا يظهر من زاره مرة مرتين.")
    add("")
    add("---")
    add("")

    add("## 2. عميلٌ عند الكاشير — `GET /api/v1/till/customer`")
    add("")
    add("**بمعامل `phone` أو `plate`.** يردّ: هل هو عميل، واسمه، ورصيد نقاطه، وما يستطيع "
        "استبداله الآن، وكم يبقى لأقرب مكافأة.")
    add("")
    add("**وعميلٌ جديد ليس خطأً:** يردّ `found: false` لا 404 — فأول زيارة هي الحالة "
        "الطبيعية عند صندوق، لا عطلٌ يُسجَّل ويُعاد.")
    add("")
    add("**وثلاث حالات لا تختلط:** لا يوجد عميل · تعذّرت قراءة النقاط (`points_unavailable`) · "
        "لا برنامج نقاط في هذا المحل أصلاً (فلا يظهر قسم النقاط إطلاقاً). **وصفرٌ لا يُرسَل "
        "بدلاً من «تعذّرت القراءة»** — كاشيرٌ يقول «ما عندك نقاط» لعميلٍ عنده ثلاثمئة يخلق "
        "شكوى من عدم.")
    add("")
    add("---")
    add("")

    add("## 3. استبدال مكافأة — `POST /api/v1/till/redeem`")
    add("")
    add("| الحقل | النوع | إلزامي | لماذا |")
    add("|---|---|---|---|")
    for field, typ, req in m.get("TillRedeemIn", []):
        add(_row("TillRedeemIn", field, typ, req))
    add("")
    add("**والمفتاح مطلوب ولا قيمة افتراضية له**: مفتاحٌ نصنعه نحن يكون جديداً في كل إعادة "
        "محاولة، **واستبدالٌ مضاعف يصرف نقاط العميل مرتين**.")
    add("")
    add("**والرفض يعود بجملته** — «رصيده لا يكفي» يقرؤها الكاشير للعميل. وميّزوا بينه وبين "
        "`UNAVAILABLE`: الأول نهائي، والثاني يُعاد.")
    add("")
    add("**والرد يحمل مرجع العملية** ليُطبَع على الإيصال — فيصير الورق أثراً ثانياً.")
    add("")
    add("---")
    add("")

    add("## 4. تطبيق عرض على الزيارة — `POST /api/v1/till/offer/apply`")
    add("")
    add("**العرض الذي يحمله العميل يُطبَّق على الزيارة، لا يُخمَّن.** لا شيء يصرف عرضاً لأن "
        "زيارة وصلت — و`reminders` وحدها تقرّر أيّ عرضٍ ينطبق، لأنها الوحيدة العارفة بما "
        "أُرسل ونطاقه وانتهاءه.")
    add("")
    add("| الحقل | النوع | إلزامي | لماذا |")
    add("|---|---|---|---|")
    for field, typ, req in m.get("TillOfferIn", []):
        add(_row("TillOfferIn", field, typ, req))
    add("")
    add("**واحدٌ لكل زيارة**: تطبيقٌ ثانٍ على نفس الزيارة يعيد العرض نفسه ولا يصرف شيئاً "
        "إضافياً — نقرةٌ ثانية عند الكاشير نيّةٌ واحدة، لا عرضين.")
    add("")
    add("---")
    add("")
    add("## ما لا نرسله لكم أبداً")
    add("")
    add("**الاسم المستعار للعميل** (`subject_ref`): مفتاح ربطٍ بين خدماتنا، ولا حاجة لكم به — "
        "أنتم تعرفون عميلكم برقمه. ومعرّفٌ دائمٌ في قاعدة بيانات طرفٍ ثالث بلا غرضٍ يستعمله "
        "خطرٌ بلا مقابل.")
    add("")
    return "\n".join(lines) + "\n"


def render_en() -> str:
    """The engineer-facing counterpart of render() above — same models, same routes, same
    guarantee against drift, restructured as a plain technical reference (auth, endpoint,
    request, response, status codes) rather than the Arabic guide's owner-facing prose. Every
    example JSON body below is copied from a real response shape in till.py, not invented — see
    that file's own routes for the exact dict literals each example mirrors.
    """
    text = TILL.read_text(encoding="utf-8")
    m = models(text)
    lines: list[str] = []
    add = lines.append

    add("# Raje3 POS/Till Integration — API Reference")
    add("")
    add("**This file is generated from the code.** Every field table below is read from the "
        "Pydantic models the routes actually validate against, not typed by hand — a hand-"
        "written integration doc goes stale the moment a field changes, and an integrator who "
        "built against the page instead of the API finds out months later. The reasoning behind "
        "the design ('why') is written once, here, by a person; the fields and types are not.")
    add("")
    add("A parallel Arabic document (`دليل-ربط-الكاشير.md`) covers the same four endpoints for "
        "a shop owner reading over the integration; this one is the technical reference for the "
        "engineer actually implementing the client.")
    add("")
    add("---")
    add("")
    add("## Authentication")
    add("")
    add("**One machine credential per shop**, issued as an OAuth2 client-credentials grant. "
        "Send it as a normal Bearer token:")
    add("")
    add("```")
    add("Authorization: Bearer <your access token>")
    add("```")
    add("")
    add("**The tenant (shop) is read from the token itself, never from the request body** — "
        "there is no `tenant` field on any request below, on purpose. A credential minted for "
        "one shop is physically unable to name another one; there is no field to set.")
    add("")
    add("**One capability: `operations.record`.** It can record a visit, read what belongs to "
        "that visit's customer, and hand over a reward. Nothing else — not billing, not other "
        "shops, not any admin surface.")
    add("")
    add("**A token with no tenant claim is refused outright** (not widened to \"every shop\") — "
        "every endpoint below answers as if nothing was sent at all.")
    add("")
    add("**Sandbox:** we provision a real test shop on the exact same routes, the exact same "
        "rules and the exact same refusals — free, uncharged, not counted as a real customer. "
        "There is no separate sandbox credential: you test with the same credential you will run "
        "in production, so whatever passes in sandbox is proven to work for real.")
    add("")
    add("---")
    add("")
    add("## Rate limits")
    add("")
    add("**Customer lookups (`GET /customer`) are budgeted as a RATIO of visits you have "
        "actually recorded, not a fixed window.** A busy till that is genuinely recording sales "
        "never comes close to the ceiling; a credential making far more lookups than the visits "
        "it records does, because that is the one shape data extraction takes. Over the budget, "
        "the response is **`429`** with a message explaining why — never `403`: the credential "
        "is still valid and was never revoked.")
    add("")
    add("---")
    add("")

    add("## 1. Post visits — `POST /api/v1/till/visits`")
    add("")
    add("Batch of up to 50 visits. **The response reports a verdict per item** — `accepted`, "
        "`duplicate`, or `rejected` with a reason — never all-or-nothing: one permanently "
        "invalid item in a batch must never block the other 49 behind it in the same post.")
    add("")
    add("**Match each result back to what you sent by `index`** — the visit's position in the "
        "`visits` array you posted (0-based). Results are ordered by it and the list is exactly "
        "as long as what you sent. Do not match on `idempotency_key`: if you did not send one, "
        "we derive it from your invoice number, and the string that comes back was never one you "
        "held.")
    add("")
    add("### Visit fields")
    add("")
    add("| Field | Type | Required | Why |")
    add("|---|---|---|---|")
    for field, typ, req in m.get("TillVisitIn", []):
        add(_row_en("TillVisitIn", field, typ, req))
    add("")
    add("### Invoice line")
    add("")
    add("| Field | Type | Required | Why |")
    add("|---|---|---|---|")
    for field, typ, req in m.get("TillLineIn", []):
        add(_row_en("TillLineIn", field, typ, req))
    add("")
    add("### Deduplication — the one rule with no exception")
    add("")
    add("**Every visit must carry at least one of:** `idempotency_key`, `invoice_id`, or "
        "`occurred_at`. Without any of the three the visit is **rejected**, naming all three in "
        "the reason.")
    add("")
    add("Why: retrying after a lost reply is the normal case for a till, and without a stable "
        "key one sale becomes two visits — doubling the customer's history, their reminders, "
        "and their points.")
    add("")
    add("### Example request")
    add("")
    add("```http")
    add("POST /api/v1/till/visits")
    add("Authorization: Bearer <token>")
    add("Content-Type: application/json")
    add("")
    add("{")
    add('  "visits": [')
    add("    {")
    add('      "phone": "0501234567",')
    add('      "branch_id": "brn_main",')
    add('      "invoice_id": "INV-2026-00042",')
    add('      "lines": [')
    add('        {"product_id": "sku_wash_1", "name": "Full wash", "qty": 1, '
        '"amount_minor": 5000}')
    add("      ]")
    add("    }")
    add("  ]")
    add("}")
    add("```")
    add("")
    add("### Example response")
    add("")
    add("```json")
    add("{")
    add('  "accepted": 1,')
    add('  "total": 1,')
    add('  "results": [')
    add('    {"index": 0, "status": "accepted", "idempotency_key": "inv:<tenant>:INV-2026-00042"}')
    add("  ]")
    add("}")
    add("```")
    add("")
    add("A rejected item looks like:")
    add("")
    add("```json")
    add('{"index": 3, "status": "rejected", ')
    add('  "reason": "unknown branch_id «brn-typo» — send one of this shop\'s own branches"}')
    add("```")
    add("")
    add("---")
    add("")

    add("## 2. Look up a customer — `GET /api/v1/till/customer`")
    add("")
    add("Query with `phone` or `plate`. Answers whether they are a known customer, their name, "
        "visit count, points balance, and what they can redeem right now.")
    add("")
    add("**A new customer is `found: false`, never a 404** — a first-time customer is the "
        "ordinary case at a counter, not a fault to log and retry.")
    add("")
    add("**Three states that must not be conflated:** no such customer · points temporarily "
        "unreadable (`points_unavailable: true`) · no loyalty programme at this shop at all (the "
        "points section is simply absent). A `0` is never sent in place of \"could not read it\" "
        "— telling a customer holding 300 points that they have none creates a complaint over "
        "nothing.")
    add("")
    add("### Example: known customer, loyalty programme active")
    add("")
    add("```json")
    add("{")
    add('  "found": true,')
    add('  "name": "Ahmad",')
    add('  "visits": 12,')
    add('  "points": 340,')
    add('  "to_next_reward": 60,')
    add('  "manager_threshold": 500,')
    add('  "rewards": [')
    add('    {"id": "rwd_free_wash", "name": "Free wash", "cost": 300, "needs_approval": false}')
    add("  ]")
    add("}")
    add("```")
    add("")
    add("`needs_approval: true` on a reward means it is above this shop's manager-approval "
        "threshold — see `approved_by` on the redeem endpoint below.")
    add("")
    add("### Example: brand-new customer")
    add("")
    add('```json')
    add('{"found": false}')
    add('```')
    add("")
    add("### Example: customer known, points temporarily unreadable")
    add("")
    add('```json')
    add('{"found": true, "name": "Ahmad", "visits": 12, "points_unavailable": true}')
    add('```')
    add("")
    add("---")
    add("")

    add("## 3. Redeem a reward — `POST /api/v1/till/redeem`")
    add("")
    add("| Field | Type | Required | Why |")
    add("|---|---|---|---|")
    for field, typ, req in m.get("TillRedeemIn", []):
        add(_row_en("TillRedeemIn", field, typ, req))
    add("")
    add("**`idempotency_key` is required, with no default we can fill in for you** — a key we "
        "mint ourselves would be new on every retry, and a doubled redemption spends the "
        "customer's points twice.")
    add("")
    add("**A refusal comes back as a full sentence** — read it to the customer directly. "
        "Distinguish `REFUSED` (final — e.g. insufficient balance) from `UNAVAILABLE` (transient "
        "— retry).")
    add("")
    add("### Example request")
    add("")
    add("```json")
    add("{")
    add('  "phone": "0501234567",')
    add('  "reward_id": "rwd_free_wash",')
    add('  "idempotency_key": "redeem-2026-00042",')
    add('  "branch_id": "brn_main",')
    add('  "actor": "cashier_3"')
    add("}")
    add("```")
    add("")
    add("### Example responses")
    add("")
    add("```json")
    add("{")
    add('  "ok": true,')
    add('  "transaction_ref": "rdm_...",')
    add('  "discount_halalas": 5000,')
    add('  "reward_name": "Free wash",')
    add('  "cost": 300,')
    add('  "balance": 40,')
    add('  "duplicate": false')
    add("}")
    add("```")
    add("")
    add("`duplicate: true` means this exact `idempotency_key` was already redeemed — the SAME "
        "receipt is returned, nothing is spent a second time.")
    add("")
    add("```json")
    add('{"ok": false, "reason": "REFUSED", "message": "رصيده لا يكفي"}')
    add("```")
    add("")
    add("```json")
    add('{"ok": false, "reason": "NOT_FOUND", "message": "لا يوجد عميل بهذا الرقم."}')
    add("```")
    add("")
    add("`transaction_ref` is what the receipt must carry — print it on the paper receipt so it "
        "has a second trail.")
    add("")
    add("---")
    add("")

    add("## 4. Apply an offer to a visit — `POST /api/v1/till/offer/apply`")
    add("")
    add("**The offer the customer is holding is applied to the visit — never guessed.** "
        "Nothing spends an offer just because a visit arrived; `reminders` alone decides which "
        "offer applies, because it alone knows what was sent, its scope, and its expiry.")
    add("")
    add("| Field | Type | Required | Why |")
    add("|---|---|---|---|")
    for field, typ, req in m.get("TillOfferIn", []):
        add(_row_en("TillOfferIn", field, typ, req))
    add("")
    add("**One per visit** — a second apply on the same visit returns the SAME offer and spends "
        "nothing further: a second tap at the counter is one intention, not two discounts.")
    add("")
    add("### Example request")
    add("")
    add("```json")
    add('{"visit_id": "vis_...", "phone": "0501234567", "actor": "cashier_3"}')
    add("```")
    add("")
    add("### Example responses")
    add("")
    add("```json")
    add('{"applied": true, "offer": {"ref": "off_...", "text": "20% off your next wash", ')
    add('  "used_at": 1735689600}}')
    add("```")
    add("")
    add("```json")
    add('{"applied": false, "reason": "لا يوجد عرضٌ ساري يشمل هذه الزيارة"}')
    add("```")
    add("")
    add("---")
    add("")
    add("## What we never send you")
    add("")
    add("**The customer's pseudonym** (`subject_ref`): our own cross-service join key, which you "
        "have no use for — you identify your customer by the phone number you already hold. A "
        "durable cross-service identifier sitting in a third party's database with no purpose it "
        "serves is a risk with no matching benefit.")
    add("")
    return "\n".join(lines) + "\n"


def missing_routes(text: str, body: str) -> list[tuple[str, str]]:
    """Every mounted route whose full path string is absent from the rendered document (ك-10).

    Checked in BOTH modes, not only `--check` — a route added and documented in the same commit
    must still be caught if whoever wrote the prose typed the path wrong, and this is the one
    honest way to know: read the router, not `render()`'s idea of the router.
    """
    return [(method, path) for method, path in routes(text)
           if f"{method} /api/v1/till{path}" not in body]


def _sync_one(text: str, body: str, out: Path, *, render_fn_name: str) -> int:
    gaps = missing_routes(text, body)
    if gaps:
        named = ", ".join(f"{m} /api/v1/till{p}" for m, p in gaps)
        print(f"{C_R}  ✗ mounted but undocumented in {out.name}: {named} — add it to "
              f"{render_fn_name}() in ci/gen_till_contract.py before this can be generated or "
              f"checked{C_N}")
        return 1
    if "--check" in sys.argv:
        current = out.read_text(encoding="utf-8") if out.exists() else ""
        if current != body:
            print(f"{C_R}  ✗ {out.name} is stale — the till models changed and the vendor's "
                  f"document did not. Run: python3 ci/gen_till_contract.py{C_N}")
            return 1
        print(f"{C_G}  ✔ {out.name} matches the routes it describes{C_N}")
        return 0
    out.write_text(body, encoding="utf-8", newline="\n")
    print(f"{C_G}  ✔ wrote {out.relative_to(ROOT)}{C_N}")
    return 0


def main() -> int:
    text = TILL.read_text(encoding="utf-8")
    # BOTH DOCUMENTS, EVERY RUN — see the module header's own note on why there are two: the
    # Arabic guide for the shop owner, this English reference for the engineer who builds
    # against it. Either one going stale is the same defect, so neither is optional.
    r1 = _sync_one(text, render(), OUT, render_fn_name="render")
    r2 = _sync_one(text, render_en(), OUT_EN, render_fn_name="render_en")
    return r1 or r2


if __name__ == "__main__":
    sys.exit(main())
