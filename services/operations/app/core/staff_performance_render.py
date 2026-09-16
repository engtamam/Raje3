"""Render the staff-performance comparison (core/operations.py::Operations.staff_performance,
api/v1/field.py's own `/staff/performance/export`) into a real, RTL-correct, branded Word document
— same low-level toolchain `services/insights/app/core/report_render.py` already proved out for the
dispute-defense report, a DIFFERENT layout on top of it (a multi-column comparison table, not a
grouped date/label list per source).

`finalize_rtl` and the small helpers below it are VERBATIM COPIES from
`services/insights/app/core/report_render.py` (itself verbatim from docs/إنتاج-ملفات-Word-عربية.md)
— do not reorder the `_RPR`/`_PPR` tuples; see that file's own header for exactly why a reordering
breaks silently (ECMA-376 child-element order). Only `build_staff_performance_docx` below is new.

PDF: see `pdf_convert.py` in this same package (also a verbatim copy) — a best-effort
`soffice --headless` shell-out, refused plainly when no LibreOffice is on the container's PATH.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt

# ── finalize_rtl — VERBATIM from report_render.py / docs/إنتاج-ملفات-Word-عربية.md. ──────────────

_RPR = ("w:rStyle", "w:rFonts", "w:b", "w:bCs", "w:i", "w:iCs", "w:caps", "w:smallCaps",
       "w:strike", "w:dstrike", "w:outline", "w:shadow", "w:emboss", "w:imprint",
       "w:noProof", "w:snapToGrid", "w:vanish", "w:webHidden", "w:color", "w:spacing",
       "w:w", "w:kern", "w:position", "w:sz", "w:szCs", "w:highlight", "w:u", "w:effect",
       "w:bdr", "w:shd", "w:fitText", "w:vertAlign", "w:rtl", "w:cs", "w:em", "w:lang",
       "w:eastAsianLayout", "w:specVanish", "w:oMath")

_PPR = ("w:pStyle", "w:keepNext", "w:keepLines", "w:pageBreakBefore", "w:framePr",
       "w:widowControl", "w:numPr", "w:suppressLineNumbers", "w:pBdr", "w:shd", "w:tabs",
       "w:suppressAutoHyphens", "w:kinsoku", "w:wordWrap", "w:overflowPunct",
       "w:topLinePunct", "w:autoSpaceDE", "w:autoSpaceDN", "w:bidi", "w:adjustRightInd",
       "w:snapToGrid", "w:spacing", "w:ind", "w:contextualSpacing", "w:mirrorIndents",
       "w:suppressOverlap", "w:jc", "w:textDirection", "w:textAlignment",
       "w:textboxTightWrap", "w:outlineLvl", "w:divId", "w:cnfStyle", "w:rPr", "w:sectPr",
       "w:pPrChange")

_after = lambda order, tag: order[order.index(tag) + 1:]                      # noqa: E731
_AR = re.compile(r"[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]")


def _ensure(parent, tag, successors):
    if parent.find(qn(tag)) is not None:
        return False
    parent.insert_element_before(OxmlElement(tag), *successors)
    return True


def finalize_rtl(doc: Document) -> None:
    stories = [doc.element.body]
    for sec in doc.sections:
        for part in (sec.header, sec.footer, sec.first_page_header,
                     sec.first_page_footer, sec.even_page_header, sec.even_page_footer):
            try:
                stories.append(part._element)
            except AttributeError:
                pass

    for story in stories:
        for p in story.iter(qn("w:p")):
            pPr = p.find(qn("w:pPr"))
            if pPr is None:
                pPr = OxmlElement("w:pPr")
                p.insert(0, pPr)
            _ensure(pPr, "w:bidi", _after(_PPR, "w:bidi"))
            jc = pPr.find(qn("w:jc"))
            if jc is None:
                jc = OxmlElement("w:jc")
                jc.set(qn("w:val"), "start")
                pPr.insert_element_before(jc, *_after(_PPR, "w:jc"))
            elif jc.get(qn("w:val")) in ("left", "right", "end"):
                jc.set(qn("w:val"), "start")

        for r in story.iter(qn("w:r")):
            rPr = r.find(qn("w:rPr"))
            if rPr is None:
                rPr = OxmlElement("w:rPr")
                r.insert(0, rPr)
            sz = rPr.find(qn("w:sz"))
            if sz is not None and rPr.find(qn("w:szCs")) is None:
                cs = OxmlElement("w:szCs")
                cs.set(qn("w:val"), sz.get(qn("w:val")))
                rPr.insert_element_before(cs, *_after(_RPR, "w:szCs"))
            if rPr.find(qn("w:b")) is not None:
                _ensure(rPr, "w:bCs", _after(_RPR, "w:bCs"))
            if rPr.find(qn("w:i")) is not None:
                _ensure(rPr, "w:iCs", _after(_RPR, "w:iCs"))
            txt = "".join(t.text or "" for t in r.iter(qn("w:t")))
            if _AR.search(txt):
                _ensure(rPr, "w:rtl", _after(_RPR, "w:rtl"))

    for tbl in doc.element.body.iter(qn("w:tbl")):
        tblPr = tbl.find(qn("w:tblPr"))
        if tblPr is not None and tblPr.find(qn("w:bidiVisual")) is None:
            tblPr.insert(0, OxmlElement("w:bidiVisual"))

    for sec in doc.sections:
        _ensure(sec._sectPr, "w:bidi",
               ("w:rtlGutter", "w:docGrid", "w:printerSettings", "w:sectPrChange"))
    try:
        n = doc.styles["Normal"]
        _ensure(n.element.get_or_add_pPr(), "w:bidi", _after(_PPR, "w:bidi"))
        _ensure(n.element.get_or_add_rPr(), "w:rtl", _after(_RPR, "w:rtl"))
    except KeyError:
        pass


# ── the small helpers the reference also documents ────────────────────────────────────────────

LRM = "‎"
_FONT = "Arial"


def ltr(s: str) -> str:
    """Wrap a compound number/identifier so it survives inside an Arabic run."""
    return LRM + s + LRM


def arabic_run(p, text: str, *, size: int = 12, bold: bool = False, color: str | None = None):
    r = p.add_run(text)
    r.bold = bold
    r.font.size = Pt(size)
    r.font.name = _FONT
    if color:
        from docx.shared import RGBColor
        r.font.color.rgb = RGBColor.from_string(color)
    rf = r._r.get_or_add_rPr().get_or_add_rFonts()
    for k in ("w:ascii", "w:hAnsi", "w:cs"):
        rf.set(qn(k), _FONT)
    return r


def fixed_widths(table, widths_in: list[float]) -> None:
    table.autofit = False
    tblPr = table._tbl.tblPr
    total = int(sum(widths_in) * 1440)
    el = OxmlElement("w:tblW")
    el.set(qn("w:w"), str(total))
    el.set(qn("w:type"), "dxa")
    tblPr.append(el)
    lay = OxmlElement("w:tblLayout")
    lay.set(qn("w:type"), "fixed")
    tblPr.append(lay)
    old = table._tbl.find(qn("w:tblGrid"))
    if old is not None:
        table._tbl.remove(old)
    grid = OxmlElement("w:tblGrid")
    for w in widths_in:
        gc = OxmlElement("w:gridCol")
        gc.set(qn("w:w"), str(int(w * 1440)))
        grid.append(gc)
    tblPr.addnext(grid)


_DEFAULT_RULE_COLOR = "C0C0C0"
_HEX6 = re.compile(r"^[0-9A-Fa-f]{6}$")


def rule_color(accent_color: str) -> str:
    """The shop's own accent (`core/tenant_branding.py`) when it is a real 6-digit hex colour,
    the neutral default otherwise — shared with `procedure_checklist_render.py` so both branded
    documents pick the same colour the same way. An operator-typed value from `AccountPanes.tsx`'s
    own colour picker is trusted for DISPLAY only (written into a border/font colour attribute,
    never interpreted as anything executable) — validated for SHAPE so a non-hex value cannot
    corrupt the document's own XML colour attribute."""
    v = accent_color.strip().lstrip("#")
    return v.upper() if _HEX6.match(v) else _DEFAULT_RULE_COLOR


def _horizontal_rule(doc: Document, color: str = _DEFAULT_RULE_COLOR) -> None:
    p = doc.add_paragraph()
    pPr = p._p.get_or_add_pPr()
    bdr = OxmlElement("w:pBdr")
    bot = OxmlElement("w:bottom")
    bot.set(qn("w:val"), "single")
    bot.set(qn("w:sz"), "10" if color != _DEFAULT_RULE_COLOR else "6")
    bot.set(qn("w:space"), "1")
    bot.set(qn("w:color"), color)
    bdr.append(bot)
    pPr.append(bdr)


# ── the report itself ─────────────────────────────────────────────────────────────────────────

# A REAL CEILING, NOT A GUESS AT "ENOUGH" — `services/insights/app/core/dispute_report.py`'s own
# `_AUDIT_MAX_PAGES` is the precedent this copies: a huge chain (hundreds of operators) still gets
# a document, capped, with a VISIBLE warning inside it rather than a silently truncated table or a
# refused export.
MAX_ROWS = 500


def build_staff_performance_docx(*, tenant: str, rows: list[dict[str, Any]],
                                 out_path: str | Path, logo_png: bytes | None = None,
                                 accent_color: str = "", shop_name: str = "",
                                 generated_at_label: str = "") -> Path:
    """Build the branded .docx. `rows` is `Operations.staff_performance`'s own merged shape
    (operator_id, operator_name, visits, ratings, average_rating, no_show_rate) — already sorted
    by average_rating descending by the caller, so this never re-sorts.

    `logo_png`/`accent_color`/`shop_name` come from `core/tenant_branding.py` (owner's own
    instruction, 2026-09-16: a shop's own saved logo/colour must appear on every document that
    leaves the building, «حتى بتقرير الفريق») — all optional, degrading to a text-only «راجِع»
    header exactly as before when a shop has none set.
    """
    doc = Document()
    color = rule_color(accent_color)

    sec = doc.sections[0]
    sec.page_width, sec.page_height = Inches(8.27), Inches(11.69)
    sec.left_margin = sec.right_margin = Inches(1.0)
    sec.top_margin = sec.bottom_margin = Inches(0.8)

    brand = shop_name.strip() if shop_name and shop_name.strip() else "راجِع"
    header_p = sec.header.paragraphs[0]
    if logo_png:
        from io import BytesIO
        header_p.add_run().add_picture(BytesIO(logo_png), height=Inches(0.4))
    hr = header_p.add_run(f"  {brand}" if logo_png else brand)
    hr.bold = True
    hr.font.size = Pt(11)
    hr.font.name = _FONT
    hr._r.get_or_add_rPr().get_or_add_rFonts().set(qn("w:cs"), _FONT)

    footer_p = sec.footer.paragraphs[0]
    if generated_at_label:
        arabic_run(footer_p, f"أُنشئ بتاريخ: {ltr(generated_at_label)}", size=9)
        footer_p.add_run("    ")
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), "PAGE")
    footer_p._p.append(fld)

    title_p = doc.add_paragraph()
    arabic_run(title_p, "تقرير أداء الموظفين", size=18, bold=True)

    subtitle_p = doc.add_paragraph()
    arabic_run(subtitle_p, "معرّف المنشأة (UUID): ", size=11, bold=True)
    arabic_run(subtitle_p, ltr(tenant), size=11)

    _horizontal_rule(doc, color)

    if not rows:
        p = doc.add_paragraph()
        arabic_run(p, "لا توجد بيانات أداء لهذه الفترة.", size=11)
        finalize_rtl(doc)
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(out_path)
        return out_path

    truncated = len(rows) > MAX_ROWS
    if truncated:
        warn_p = doc.add_paragraph()
        arabic_run(warn_p, f"⚠ هذا التقرير يعرض أعلى {MAX_ROWS} موظفاً فقط من أصل "
                          f"{ltr(str(len(rows)))} — رتّب حسب الفرع لتضييق النطاق.", size=10,
                  bold=True)
        _horizontal_rule(doc, color)

    table = doc.add_table(rows=1, cols=5)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    fixed_widths(table, [2.2, 1.0, 1.0, 1.15, 1.15])
    hdr = table.rows[0].cells
    for cell, label in zip(hdr, ("الموظف", "الزيارات", "التقييمات", "متوسط التقييم",
                                "نسبة عدم الحضور")):
        arabic_run(cell.paragraphs[0], label, size=10, bold=True)

    for row in rows[:MAX_ROWS]:
        cells = table.add_row().cells
        arabic_run(cells[0].paragraphs[0], row.get("operator_name") or "—", size=10)
        arabic_run(cells[1].paragraphs[0], ltr(str(row.get("visits", 0))), size=10)
        arabic_run(cells[2].paragraphs[0], ltr(str(row.get("ratings", 0))), size=10)
        avg = row.get("average_rating") or 0.0
        arabic_run(cells[3].paragraphs[0], ltr(f"{avg:.1f}") if row.get("ratings") else "—",
                  size=10)
        no_show_rate = row.get("no_show_rate") or 0.0
        arabic_run(cells[4].paragraphs[0], ltr(f"{no_show_rate * 100:.0f}%"), size=10)

    finalize_rtl(doc)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(out_path)
    return out_path
