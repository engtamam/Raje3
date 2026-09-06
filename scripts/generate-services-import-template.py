"""Generates apps/console/public/templates/services-import-template.xlsx — run once by hand
whenever the import columns change, never at build/runtime. Not a build step and not a service
dependency: this is the one place `openpyxl` is used in this whole repo, deliberately, to produce
a static file that ships as-is.

WHY A GENERATED FILE, NEVER HAND-EDITED. The column headers here must match one of the aliases
`apps/console/src/screens/ServicesImportDrawer.tsx::HEADER_ALIASES` maps back onto
`services/operations/app/api/v1/staff.py::ServiceImportRow`'s own field names (name, price,
duration_minutes, cycle_days, external_id, description) — a hand-edited spreadsheet drifting from
either is exactly the "a shop typed its own header row from memory" defect this template exists to
prevent, just moved to our own side.

REAL ARABIC WORDS, NOT THE FIELD NAMES. An owner who does not read English should never have to
type into a column literally named `duration_minutes` — the file he opens is the one place this
product's own "no engineer words reach a shop owner" rule was not yet being kept. `parseRows`'
alias table is what makes this safe: the English field names still parse too, so a shop with an
older download, or one who typed his own header row from memory of it, is not suddenly broken.

    python scripts/generate-services-import-template.py
"""
from __future__ import annotations

import pathlib

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.worksheet.worksheet import Worksheet

OUT = (pathlib.Path(__file__).resolve().parent.parent
       / "apps" / "console" / "public" / "templates" / "services-import-template.xlsx")

# Column order matches ServiceImportRow field order exactly. Header TEXT is Arabic — real words an
# owner reads, not the field name behind it — and each one is in ServicesImportDrawer.tsx's own
# HEADER_ALIASES table, which maps it back to the English key the parser actually reads.
HEADERS = ["الاسم", "السعر", "المدة (دقائق)", "دورة التكرار (أيام)", "معرّف خارجي", "الوصف"]
EXAMPLE_ROW = ["غسيل خارجي", "50", "30", "0", "", "غسيل كامل للسيارة من الخارج بالماء والصابون"]


def build() -> Workbook:
    wb = Workbook()
    ws: Worksheet = wb.active
    ws.title = "خدماتي ومنتجاتي"

    header_fill = PatternFill("solid", fgColor="EDEBFB")
    header_font = Font(bold=True)
    for col, text in enumerate(HEADERS, start=1):
        cell = ws.cell(row=1, column=col, value=text)
        cell.fill = header_fill
        cell.font = header_font

    for col, value in enumerate(EXAMPLE_ROW, start=1):
        ws.cell(row=2, column=col, value=value)

    # Generous, readable column widths — an owner opening this in a phone's spreadsheet app should
    # never have to widen a column before typing into it.
    widths = [24, 10, 16, 12, 14, 40]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[chr(ord("A") + i - 1)].width = w

    ws.freeze_panes = "A2"
    return wb


if __name__ == "__main__":
    wb = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    wb.save(OUT)
    print(f"wrote {OUT}")
