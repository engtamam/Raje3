"""Render one or more services' ordered procedure protocol into a real, RTL-correct, branded
PDF/Word checklist — the owner's own instruction (2026-09-16): the shop hands this to a customer,
or prints it as a wall reference, so it must read as a professional document carrying the SHOP'S
OWN brand, not an internal report table and not this platform's own name.

SAME LOW-LEVEL TOOLCHAIN AS `staff_performance_render.py` (imported, not copied — same SERVICE, so
the cross-service "verbatim copy" convention `pdf_convert.py`'s own header explains does not apply
here; that convention is about never sharing a package ACROSS services, not about reuse within one).

WHY A DIFFERENT LAYOUT THAN THE STAFF-PERFORMANCE TABLE. That report is read by an owner comparing
numbers; this one is READ STEP BY STEP by whoever is doing the work, or handed to a customer as
proof of what was checked — a dense table is the wrong shape for either reader. Each step is its
own numbered row with room to breathe and a real checkbox glyph («☐») to physically tick, and a
critical step carries a visible «⚠ حرجة» tag rather than a bare severity column header nobody not
already fluent in the internal vocabulary would parse.

MULTIPLE SERVICES, ONE MERGED LIST — a customer booked several services at once (غسيل خارجي +
تلميع, say) gets ONE checklist, not one per service. A step the two share is printed exactly ONCE
(the caller, `api/v1/staff.py::export_procedure_checklist`, has already deduped it and decided
which service it is filed under) — this module only renders the "مشتركة مع: …" caption the caller
attaches to it (`step["also_in"]`), never re-derives the merge itself.

BRAND: shop name, not «راجِع». This document leaves the shop and is read by a customer or stuck on
a wall — printing our own platform's name on it would be exactly backwards. `shop_name` is the
tenant's own main-branch name (the best per-tenant display name this service can answer without a
peer hop — same resolution `api/internal.py::shop_name` already uses for the same reason). Falls
back to «راجِع» only when a shop genuinely has none set, so the header is never blank.

`logo_png`/`accent_color` COME FROM `core/tenant_branding.py` — a shop's own saved logo and colour
(the SAME two fields `AccountPanes.tsx`'s own `BrandCard` saves, owner's own instruction: "استخدمه
لو كان موجود، لا تفوّته حتى بتقرير الفريق"). Both are optional and degrade the same way an absent
`shop_name` does — a text-only header, a neutral-grey rule — never a failed export.

PDF: `pdf_convert.py` in this same package (best-effort `soffice --headless`, refused plainly with
no LibreOffice on PATH).
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt

from app.core.staff_performance_render import (
    _DEFAULT_RULE_COLOR, _FONT, _horizontal_rule, arabic_run, finalize_direction, fixed_widths, ltr,
    rule_color,
)
from app.core.print_i18n import is_rtl, label

# A real ceiling, not a guess — same reasoning `staff_performance_render.MAX_ROWS` gives: a
# protocol nobody would actually hand a customer this long still gets a document, capped, with a
# visible notice, rather than a silently truncated sheet.
MAX_STEPS = 100

_CRITICAL_RED = "B3261E"
_MUTED_GREY = "6B6B76"


def _severity_tag(p, severity: str, locale: str) -> None:
    if severity == "critical":
        arabic_run(p, label(locale, "checklist.critical_tag"), size=9, bold=True,
                  color=_CRITICAL_RED)


def build_procedure_checklist_docx(
    *, shop_name: str, service_names: list[str], steps: list[dict[str, Any]],
    out_path: str | Path, logo_png: bytes | None = None, accent_color: str = "",
    generated_at_label: str = "", locale: str = "ar",
) -> Path:
    """Build the branded .docx. `steps` is already resolved, ORDERED and DEDUPED by the caller
    (`api/v1/staff.py::export_procedure_checklist`) — this never re-orders, re-fetches or merges;
    each is `{id, text, severity, also_in: list[str]}` (`also_in` empty for a step that belongs to
    only one of `service_names`). `logo_png`/`accent_color` come from `core/tenant_branding.py`.

    `locale` PICKS THE DOCUMENT'S OWN LABELS (`print_i18n.py`) AND FLOW DIRECTION — `steps`'
    own `text` and `service_names` arrive ALREADY RESOLVED to this locale by the caller (via
    `core/translations.py::resolve`), never translated in this module; this module only ever
    renders what it is handed.
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
        header_p.add_run().add_picture(BytesIO(logo_png), height=Inches(0.4))
    hr = header_p.add_run(f"  {brand}" if logo_png else brand)
    hr.bold = True
    hr.font.size = Pt(11)
    hr.font.name = _FONT
    hr._r.get_or_add_rPr().get_or_add_rFonts().set(qn("w:cs"), _FONT)

    footer_p = sec.footer.paragraphs[0]
    if generated_at_label:
        arabic_run(footer_p, f"{label(locale, 'generated_at')}{ltr(generated_at_label)}", size=9)
        footer_p.add_run("    ")
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), "PAGE")
    footer_p._p.append(fld)

    # THE MASTHEAD — a cover strip naming every service this specific card covers, not a bare
    # title, since this page may be handed over on its own with no other context on it.
    eyebrow_p = doc.add_paragraph()
    arabic_run(eyebrow_p, label(locale, "checklist.eyebrow"), size=10, bold=True,
              color=color if color != _DEFAULT_RULE_COLOR else _MUTED_GREY)

    title_p = doc.add_paragraph()
    arabic_run(title_p, " + ".join(service_names) if service_names else "—", size=20, bold=True)

    if len(service_names) > 1:
        combo_p = doc.add_paragraph()
        arabic_run(combo_p, label(locale, "checklist.combined_note", n=ltr(str(len(service_names)))),
                  size=10, color=_MUTED_GREY)

    _horizontal_rule(doc, color)

    if not steps:
        p = doc.add_paragraph()
        arabic_run(p, label(locale, "checklist.empty"), size=11)
        finalize_direction(doc, rtl=is_rtl(locale))
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(out_path)
        return out_path

    truncated = len(steps) > MAX_STEPS
    if truncated:
        warn_p = doc.add_paragraph()
        arabic_run(warn_p, label(locale, "checklist.truncated", n=ltr(str(MAX_STEPS)),
                                 m=ltr(str(len(steps)))), size=10, bold=True)
        _horizontal_rule(doc, color)

    # ONE ROW PER STEP, NOT ONE COMPRESSED TABLE — a numbered circle, the step text, a real
    # checkbox glyph to physically tick, and (only when it applies) a critical tag on its own
    # line so it is never mistaken for part of the instruction text itself.
    table = doc.add_table(rows=0, cols=3)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    fixed_widths(table, [0.5, 5.3, 0.55])

    for i, step in enumerate(steps[:MAX_STEPS], start=1):
        row = table.add_row().cells

        num_p = row[0].paragraphs[0]
        num_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        arabic_run(num_p, ltr(str(i)), size=13, bold=True)

        text_p = row[1].paragraphs[0]
        arabic_run(text_p, step.get("text") or "—", size=12)
        if step.get("severity") == "critical":
            _severity_tag(text_p, "critical", locale)

        also_in = step.get("also_in") or []
        if also_in:
            shared_p = row[1].add_paragraph()
            arabic_run(shared_p, f"{label(locale, 'checklist.shared_with')}{'، '.join(also_in)}",
                      size=9, color=_MUTED_GREY)

        box_p = row[2].paragraphs[0]
        box_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        arabic_run(box_p, "☐", size=16)

        # A hairline UNDER each row (never a full grid) — separates steps without the report-table
        # look this is deliberately not.
        for cell in row:
            tcPr = cell._tc.get_or_add_tcPr()
            borders = OxmlElement("w:tcBorders")
            bottom = OxmlElement("w:bottom")
            bottom.set(qn("w:val"), "single")
            bottom.set(qn("w:sz"), "4")
            bottom.set(qn("w:color"), "DCDCE2")
            borders.append(bottom)
            tcPr.append(borders)
            cell.vertical_alignment = 1  # center

    # Strip the table's own default grid border — only the per-row hairlines above should show.
    tblPr = table._tbl.tblPr
    tblBorders = OxmlElement("w:tblBorders")
    for tag in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{tag}")
        el.set(qn("w:val"), "none")
        tblBorders.append(el)
    tblPr.append(tblBorders)

    finalize_direction(doc, rtl=is_rtl(locale))
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(out_path)
    return out_path
