"""Render a dispute-report item list into a real, RTL-correct, branded Word document —
`core/dispute_report.py` proves the DATA is right; this turns it into the actual .docx a person
hands to a lawyer. First proven out as a Claude-side ops-mcp tool (same content, ported here
verbatim) before this port into the real backend — see `core/dispute_report.py`'s own module
docstring for why that move happened.

EVERY TECHNIQUE HERE IS FROM docs/إنتاج-ملفات-Word-عربية.md (Raje3's own reference, project-
agnostic by its own header) — `finalize_rtl` is COPIED, not reimplemented from memory, because
its own comment explains exactly why a reordering would break silently (ECMA-376 child-element
order: an element out of place makes Word drop the whole rPr/pPr group, including w:rtl, with no
error). Anything downstream of that function is free to change; that function itself should not
be, without re-reading the reference it came from.

PDF: see `pdf_convert.py` in this same package — a best-effort `soffice --headless` shell-out,
refused plainly when no LibreOffice is on the container's PATH rather than silently skipped.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt

# ── finalize_rtl — VERBATIM from docs/إنتاج-ملفات-Word-عربية.md. Do not reorder these tuples. ────

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
WJ = "⁠"
_FONT = "Arial"


def ltr(s: str) -> str:
    """Wrap a compound number/identifier so it survives inside an Arabic run (e.g. a date, a
    UUID) — without this a bare digit run can visually reorder next to Arabic text."""
    return LRM + s + LRM


def glue(s: str) -> str:
    return re.sub(r"\[([A-Z][A-Z0-9_]*)\]", lambda m: "[" + WJ + m.group(1) + WJ + "]", s)


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


def _horizontal_rule(doc: Document) -> None:
    p = doc.add_paragraph()
    pPr = p._p.get_or_add_pPr()
    bdr = OxmlElement("w:pBdr")
    bot = OxmlElement("w:bottom")
    bot.set(qn("w:val"), "single")
    bot.set(qn("w:sz"), "6")
    bot.set(qn("w:space"), "1")
    bot.set(qn("w:color"), "C0C0C0")
    bdr.append(bot)
    pPr.append(bdr)


# ── the report itself ─────────────────────────────────────────────────────────────────────────

_SOURCE_TITLES_AR = {
    "backup": "النسخ الاحتياطي",
    "billing": "الفوترة والاشتراك",
    "staff": "الفروع والموظفون",
    "audit": "سجل التدقيق",
    "legal": "المستندات القانونية",
    "marketing": "التسويق والموافقات",
    # FIXED 2026-09-12, a real gap a QA audit found: "acceptance" is a real source
    # (contract_breach/suspended_tos scenarios both cite it) but had no label, so it rendered as
    # the raw English word inside an otherwise-Arabic legal document.
    "acceptance": "إثبات موافقة العميل على الشروط",
}


@dataclass(frozen=True)
class RenderItem:
    """The rendering layer's own minimal shape — deliberately NOT `dispute_report.ReportItem`,
    so this module never has to import ops_mcp's MCP-tool machinery just to format text. The
    caller (dispute_report.py, or a future CLI) converts its own items into this shape."""
    ts_label: str
    source: str
    label: str


def build_docx(*, scenario_title: str, tenant: str, items: list[RenderItem],
               out_path: str | Path, logo_path: str | Path | None = None,
               generated_at_label: str = "", warnings: list[str] | None = None) -> Path:
    """Build the branded .docx. `logo_path` is optional — `brand/logo/` holds no actual image
    file yet (checked: only a `.gitkeep`), so a missing/absent logo degrades to a text-only
    header rather than failing the whole report.

    `warnings` — added 2026-09-12, a real gap a QA audit found: `RunResult.errors` (one string per
    source that failed to answer, e.g. "legal: compliance-service unreachable") used to be read by
    nobody. The document itself now says so, in its own visible block, before anything else — a
    report that looks complete and authoritative while silently missing a whole evidence category
    is exactly the wrong failure mode for a LEGAL/COMPLIANCE document, where an unnoticed gap
    matters most.
    """
    doc = Document()

    sec = doc.sections[0]
    sec.page_width, sec.page_height = Inches(8.27), Inches(11.69)
    sec.left_margin = sec.right_margin = Inches(1.0)
    sec.top_margin = sec.bottom_margin = Inches(0.8)

    # ── header: logo (if any) + brand name, on one line ──────────────────────────────────────
    header_p = sec.header.paragraphs[0]
    if logo_path and Path(logo_path).is_file():
        header_p.add_run().add_picture(str(logo_path), height=Inches(0.4))
    hr = header_p.add_run("  راجِع" if logo_path and Path(logo_path).is_file() else "راجِع")
    hr.bold = True
    hr.font.size = Pt(11)
    hr.font.name = _FONT
    hr._r.get_or_add_rPr().get_or_add_rFonts().set(qn("w:cs"), _FONT)

    # ── footer: page number + generated-at date ───────────────────────────────────────────────
    footer_p = sec.footer.paragraphs[0]
    if generated_at_label:
        arabic_run(footer_p, f"أُنشئ بتاريخ: {ltr(generated_at_label)}", size=9)
        footer_p.add_run("    ")
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), "PAGE")
    footer_p._p.append(fld)

    # ── title block ────────────────────────────────────────────────────────────────────────────
    title_p = doc.add_paragraph()
    arabic_run(title_p, f"تقرير دفاع نزاعي — {scenario_title}", size=18, bold=True)

    subtitle_p = doc.add_paragraph()
    arabic_run(subtitle_p, "معرّف المنشأة (UUID): ", size=11, bold=True)
    arabic_run(subtitle_p, ltr(tenant), size=11)

    _horizontal_rule(doc)

    if warnings:
        warn_p = doc.add_paragraph()
        arabic_run(warn_p, "⚠ مصادر تعذّر الوصول إليها — هذا التقرير قد يكون ناقصاً:",
                  size=11, bold=True)
        for w in warnings:
            item_p = doc.add_paragraph()
            arabic_run(item_p, f"• {w}", size=10)
        _horizontal_rule(doc)

    if not items:
        p = doc.add_paragraph()
        arabic_run(p, "لا توجد أي سجلات لهذه المنشأة بالمصادر المطلوبة.", size=11)
        finalize_rtl(doc)
        out_path = Path(out_path)
        doc.save(out_path)
        return out_path

    # ── one table per source, in first-seen order ─────────────────────────────────────────────
    seen_sources: list[str] = []
    by_source: dict[str, list[RenderItem]] = {}
    for it in items:
        if it.source not in by_source:
            by_source[it.source] = []
            seen_sources.append(it.source)
        by_source[it.source].append(it)

    for source in seen_sources:
        heading_p = doc.add_paragraph()
        arabic_run(heading_p, _SOURCE_TITLES_AR.get(source, source), size=14, bold=True)

        table = doc.add_table(rows=1, cols=2)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        fixed_widths(table, [1.6, 4.8])
        hdr = table.rows[0].cells
        arabic_run(hdr[0].paragraphs[0], "التاريخ", size=10, bold=True)
        arabic_run(hdr[1].paragraphs[0], "التفصيل", size=10, bold=True)

        for it in by_source[source]:
            row = table.add_row().cells
            arabic_run(row[0].paragraphs[0], ltr(it.ts_label) if it.ts_label != "؟" else "؟", size=10)
            arabic_run(row[1].paragraphs[0], it.label, size=10)

        doc.add_paragraph()

    finalize_rtl(doc)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(out_path)
    return out_path
