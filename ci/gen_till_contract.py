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
#   python3 ci/gen_till_contract.py           # write docs/دليل-ربط-الكاشير.md
#   python3 ci/gen_till_contract.py --check   # fail if the file is stale (CI)
# =============================================================================
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TILL = ROOT / "services" / "operations" / "app" / "api" / "v1" / "till.py"
OUT = ROOT / "docs" / "دليل-ربط-الكاشير.md"

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
    "branch_id": "الفرع كما تعرفونه أنتم. نستقبله ولا نشترطه.",
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
                                        "نقاط العميل مرتين عند أول إعادة إرسال."},
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


def _row(model: str, field: str, typ: str, required: bool) -> str:
    why = WHY_BY_MODEL.get(model, {}).get(field) or WHY.get(field, "")
    return f"| `{field}` | {typ} | {'نعم' if required else 'لا'} | {why} |"


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
    add("## ما لا نرسله لكم أبداً")
    add("")
    add("**الاسم المستعار للعميل** (`subject_ref`): مفتاح ربطٍ بين خدماتنا، ولا حاجة لكم به — "
        "أنتم تعرفون عميلكم برقمه. ومعرّفٌ دائمٌ في قاعدة بيانات طرفٍ ثالث بلا غرضٍ يستعمله "
        "خطرٌ بلا مقابل.")
    add("")
    return "\n".join(lines) + "\n"


def main() -> int:
    body = render()
    if "--check" in sys.argv:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != body:
            print(f"{C_R}  ✗ {OUT.name} is stale — the till models changed and the vendor's "
                  f"document did not. Run: python3 ci/gen_till_contract.py{C_N}")
            return 1
        print(f"{C_G}  ✔ the POS integration document matches the routes it describes{C_N}")
        return 0
    OUT.write_text(body, encoding="utf-8", newline="\n")
    print(f"{C_G}  ✔ wrote {OUT.relative_to(ROOT)}{C_N}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
