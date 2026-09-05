"""Generates apps/console/public/templates/services-import-template.xlsx — run once by hand
whenever the import columns change, never at build/runtime. Not a build step and not a service
dependency: this is the one place `openpyxl` is used in this whole repo, deliberately, to produce
a static file that ships as-is.

WHY A GENERATED FILE, NEVER HAND-EDITED. The column headers here must match
`services/operations/app/api/v1/staff.py::ServiceImportRow` and
`apps/console/src/screens/ServicesImportDrawer.tsx::parseRows` exactly (name, price,
duration_minutes, cycle_days, external_id, description) — a hand-edited spreadsheet drifting from
either is exactly the "a shop typed its own header row from memory" defect this template exists to
prevent, just moved to our own side.

    python scripts/generate-services-import-template.py
"""
from __future__ import annotations

import pathlib

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.worksheet.worksheet import Worksheet

OUT = (pathlib.Path(__file__).resolve().parent.parent
       / "apps" / "console" / "public" / "templates" / "services-import-template.xlsx")

# Column order matches ServiceImportRow field order exactly, header text matches parseRows' own
# lower-cased column lookups (csv.ts lower-cases every header before this file's own parser reads
# it, so the case shown here is only for the human — a differently-cased header still parses).
HEADERS = ["name", "price", "duration_minutes", "cycle_days", "external_id", "description"]
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
