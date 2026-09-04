# إنتاج ملفات Word عربية سليمة — الطريقة التقنية

مرجع عام لأي أداة أو سكربت يحتاج توليد مستندات Word (.docx) بالعربية باستخدام `python-docx`، بمعزل عن أي مجال تخصصي.

---

## القاعدة

عند طلب أي مستند Word (تقرير، رسالة، عقد، مذكرة، خطاب، دليل... إلخ)، استخدم `python-docx`.

**لكن المكتبة وحدها لا تُنتج عربية سليمة.** اكتب المحتوى عادياً بـ `add_paragraph` و`add_run`، ثم **طبّق دالة التصحيح أدناه قبل الحفظ**:

```python
doc = Document()
# ... اكتب المحتوى عادياً ...
finalize_rtl(doc)      # ← الخطوة الحاسمة
doc.save(path)
```

بدون هذه الخطوة، يفتح المستند في Word باتجاه من اليسار لليمين، والفقرات والجداول والترقيم كلها مقلوبة.

---

## دالة التصحيح

```python
import re
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

# ترتيب أبناء rPr وpPr وفق ECMA-376 — عنصر خارج ترتيبه
# يجعل Word يُهمل مجموعة الخصائص كاملةً فيسقط w:rtl صامتاً
_RPR = ("w:rStyle","w:rFonts","w:b","w:bCs","w:i","w:iCs","w:caps","w:smallCaps",
        "w:strike","w:dstrike","w:outline","w:shadow","w:emboss","w:imprint",
        "w:noProof","w:snapToGrid","w:vanish","w:webHidden","w:color","w:spacing",
        "w:w","w:kern","w:position","w:sz","w:szCs","w:highlight","w:u","w:effect",
        "w:bdr","w:shd","w:fitText","w:vertAlign","w:rtl","w:cs","w:em","w:lang",
        "w:eastAsianLayout","w:specVanish","w:oMath")

_PPR = ("w:pStyle","w:keepNext","w:keepLines","w:pageBreakBefore","w:framePr",
        "w:widowControl","w:numPr","w:suppressLineNumbers","w:pBdr","w:shd","w:tabs",
        "w:suppressAutoHyphens","w:kinsoku","w:wordWrap","w:overflowPunct",
        "w:topLinePunct","w:autoSpaceDE","w:autoSpaceDN","w:bidi","w:adjustRightInd",
        "w:snapToGrid","w:spacing","w:ind","w:contextualSpacing","w:mirrorIndents",
        "w:suppressOverlap","w:jc","w:textDirection","w:textAlignment",
        "w:textboxTightWrap","w:outlineLvl","w:divId","w:cnfStyle","w:rPr","w:sectPr",
        "w:pPrChange")

_after = lambda order, tag: order[order.index(tag)+1:]
_AR = re.compile(r"[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]")

def _ensure(parent, tag, successors):
    """يُدرج العنصر في موضعه من المخطط — مرة واحدة فقط."""
    if parent.find(qn(tag)) is not None:
        return False
    parent.insert_element_before(OxmlElement(tag), *successors)
    return True

def finalize_rtl(doc):
    stories = [doc.element.body]
    for sec in doc.sections:
        for part in (sec.header, sec.footer, sec.first_page_header,
                     sec.first_page_footer, sec.even_page_header, sec.even_page_footer):
            try: stories.append(part._element)
            except AttributeError: pass

    for story in stories:
        for p in story.iter(qn("w:p")):
            pPr = p.find(qn("w:pPr"))
            if pPr is None:
                pPr = OxmlElement("w:pPr"); p.insert(0, pPr)
            _ensure(pPr, "w:bidi", _after(_PPR, "w:bidi"))
            # w:jc: القيمتان left/right اسمان منطقيان تحت w:bidi —
            # و"right" تعني النهاية أي الهامش الأيسر. الصحيح "start".
            jc = pPr.find(qn("w:jc"))
            if jc is None:
                jc = OxmlElement("w:jc"); jc.set(qn("w:val"), "start")
                pPr.insert_element_before(jc, *_after(_PPR, "w:jc"))
            elif jc.get(qn("w:val")) in ("left", "right", "end"):
                jc.set(qn("w:val"), "start")

        for r in story.iter(qn("w:r")):
            rPr = r.find(qn("w:rPr"))
            if rPr is None:
                rPr = OxmlElement("w:rPr"); r.insert(0, rPr)
            # Word يقرأ حجم النص العربي من w:szCs لا w:sz — وافتراضه 10 نقاط
            sz = rPr.find(qn("w:sz"))
            if sz is not None and rPr.find(qn("w:szCs")) is None:
                cs = OxmlElement("w:szCs"); cs.set(qn("w:val"), sz.get(qn("w:val")))
                rPr.insert_element_before(cs, *_after(_RPR, "w:szCs"))
            # توأما العريض والمائل للنص المعقّد
            if rPr.find(qn("w:b")) is not None: _ensure(rPr, "w:bCs", _after(_RPR, "w:bCs"))
            if rPr.find(qn("w:i")) is not None: _ensure(rPr, "w:iCs", _after(_RPR, "w:iCs"))
            # w:rtl للأشطر العربية فقط — وسم شطر لاتيني يعكس محايداته
            txt = "".join(t.text or "" for t in r.iter(qn("w:t")))
            if _AR.search(txt):
                _ensure(rPr, "w:rtl", _after(_RPR, "w:rtl"))

    # الجداول: يقلب ترتيب الأعمدة ليبدأ الأول من اليمين
    for tbl in doc.element.body.iter(qn("w:tbl")):
        tblPr = tbl.find(qn("w:tblPr"))
        if tblPr is not None and tblPr.find(qn("w:bidiVisual")) is None:
            tblPr.insert(0, OxmlElement("w:bidiVisual"))

    # مستوى القسم ونمط Normal — ليعتبره Word ملفاً عربياً لا ملفاً فيه عربي
    for sec in doc.sections:
        _ensure(sec._sectPr, "w:bidi",
                ("w:rtlGutter","w:docGrid","w:printerSettings","w:sectPrChange"))
    try:
        n = doc.styles["Normal"]
        _ensure(n.element.get_or_add_pPr(), "w:bidi", _after(_PPR, "w:bidi"))
        _ensure(n.element.get_or_add_rPr(), "w:rtl", _after(_RPR, "w:rtl"))
    except KeyError:
        pass
```

---

## الخط — يُضبط عند الكتابة

`font.name` في python-docx يكتب `w:ascii` و`w:hAnsi` فقط. **العربية تحتاج `w:cs` أيضاً:**

```python
def arabic_run(p, text, size=12, bold=False, font="Arial"):
    r = p.add_run(text)
    r.bold = bold
    r.font.size = Pt(size)
    r.font.name = font
    rf = r._r.get_or_add_rPr().get_or_add_rFonts()
    for k in ("w:ascii", "w:hAnsi", "w:cs"):
        rf.set(qn(k), font)
    return r
```

---

## النص المختلط — يُعالَج عند الكتابة

رقم مثل `2-1-1` بلا حرف لاتيني قوي **ينعكس في الفقرة العربية** فيظهر `1-1-2`. أحطه بعلامة الاتجاه اليساري:

```python
LRM = "\u200e"   # علامة اتجاه يساري — عرضها صفر
def ltr(s):
    """للأرقام المركّبة والمعرّفات داخل نص عربي."""
    return LRM + s + LRM
```

**والنائب `[X]` (placeholder) ينكسر عبر سطرين** لأن Word يعدّ القوسين موضع كسر. الْصقهما برابط الكلمات:

```python
WJ = "\u2060"   # رابط كلمات — يمنع الكسر، عرضه صفر
def glue(s):
    return re.sub(r"\[([A-Z][A-Z0-9_]*)\]", lambda m: "["+WJ+m.group(1)+WJ+"]", s)
```

---

## إعداد الصفحة

```python
sec = doc.sections[0]
sec.page_width, sec.page_height = Inches(8.27), Inches(11.69)   # A4
sec.left_margin = sec.right_margin = Inches(1.0)
```

---

## الجداول — إن لزمت

بلا شبكة عرض صريحة، Word يضغط الأعمدة لحرف واحد:

```python
def fixed_widths(table, widths_in):
    table.autofit = False
    tblPr = table._tbl.tblPr
    total = int(sum(widths_in) * 1440)
    el = OxmlElement("w:tblW"); el.set(qn("w:w"), str(total)); el.set(qn("w:type"), "dxa")
    tblPr.append(el)
    lay = OxmlElement("w:tblLayout"); lay.set(qn("w:type"), "fixed")
    tblPr.append(lay)
    old = table._tbl.find(qn("w:tblGrid"))
    if old is not None: table._tbl.remove(old)
    grid = OxmlElement("w:tblGrid")
    for w in widths_in:
        gc = OxmlElement("w:gridCol"); gc.set(qn("w:w"), str(int(w*1440))); grid.append(gc)
    tblPr.addnext(grid)
```

---

## الرقم المتصدّر ينقلب

**العنوان الذي يبدأ برقم لاتيني يقفز الرقم فيه لليسار** — لأن الرقم محرف محايد في أول فقرة، فيلتقط اتجاه ما حوله لا اتجاه الفقرة.

```
❌ "1 · القسم الأول"   →  يُعرَض:  القسم الأول · 1
```

**و`\u200f` (RLM) قبله لا يحلّها دائماً.**

**والحل تحريري لا تقني:** رقّم بالكلمات العربية.

```
✅ "البند الأول — ..."
✅ "الفقرة الثانية — ..."
```

**والاستثناء:** الرقم داخل الجملة (لا في بدايتها) لا يتصدّرها — يُعالَج بـ`ltr()` كالمعتاد.

---

## نمطان بصريان يستحقان الحفظ

**اقتباس أو نص مميَّز — إطار بشريط جانبي:**

```python
p = doc.add_paragraph()
pPr = p._p.get_or_add_pPr()

shd = OxmlElement("w:shd")
shd.set(qn("w:val"), "clear"); shd.set(qn("w:fill"), "F2EDE4")
pPr.append(shd)

bdr = OxmlElement("w:pBdr")
el = OxmlElement("w:right")          # يمين في RTL = بداية السطر
el.set(qn("w:val"), "single"); el.set(qn("w:sz"), "18")
el.set(qn("w:space"), "6"); el.set(qn("w:color"), "8B1A1A")
bdr.append(el); pPr.append(bdr)
```

**يفصل النص المقتبس أو المميَّز عن باقي المحتوى** — فيجده القارئ بلمحة.

**فاصل أفقي — بلا صورة ولا جدول:**

```python
p = doc.add_paragraph()
pPr = p._p.get_or_add_pPr()
bdr = OxmlElement("w:pBdr")
bot = OxmlElement("w:bottom")
bot.set(qn("w:val"), "single"); bot.set(qn("w:sz"), "6")
bot.set(qn("w:space"), "1"); bot.set(qn("w:color"), "C0C0C0")
bdr.append(bot); pPr.append(bdr)
```

---

## قائمة الفحص قبل الحفظ

```
□ finalize_rtl(doc) طُبِّقت
□ الخط مضبوط بـ w:cs لا بـ font.name وحده
□ الأرقام المركّبة محاطة بـ LRM
□ النوائب (placeholders) ملصوقة بـ WJ
□ الأرقام لاتينية (0123) إن كانت هذه القاعدة مطلوبة، لا هندية (٠١٢٣)
□ لا عنوان يبدأ برقم لاتيني — الرقم المتصدّر ينقلب لليسار؛ استعمل الترقيم بالكلمات
```
