"""Generates apps/console/src/__fixtures__/services-import-with-images.xlsx — a REAL xlsx with
two real embedded pictures, one per data row, for xlsx_images.test.ts to parse against genuine
OOXML rather than a hand-written mock. Run once by hand whenever the fixture needs to change.

    python scripts/generate-xlsx-image-fixture.py
"""
from __future__ import annotations

import io
import pathlib

from openpyxl import Workbook
from openpyxl.drawing.image import Image
from PIL import Image as PILImage

OUT = (pathlib.Path(__file__).resolve().parent.parent
       / "apps" / "console" / "src" / "__fixtures__" / "services-import-with-images.xlsx")


def _solid_png(rgb: tuple[int, int, int]) -> bytes:
    buf = io.BytesIO()
    PILImage.new("RGB", (4, 4), rgb).save(buf, format="PNG")
    return buf.getvalue()


# Two real, valid, DIFFERENT PNGs — different bytes so a test can tell which picture landed on
# which row rather than merely proving "a picture arrived".
_PNG_RED = _solid_png((220, 20, 20))
_PNG_BLUE = _solid_png((20, 20, 220))


def build() -> Workbook:
    wb = Workbook()
    ws = wb.active
    ws.title = "خدماتي ومنتجاتي"
    ws.append(["name", "price", "duration_minutes", "cycle_days", "external_id", "description"])
    ws.append(["غسيل خارجي", "50", "30", "0", "", "الصف الأول"])
    ws.append(["تلميع", "80", "20", "0", "", "الصف الثاني"])

    img1 = Image(io.BytesIO(_PNG_RED))
    img1.anchor = "A2"   # the FIRST data row
    ws.add_image(img1)

    img2 = Image(io.BytesIO(_PNG_BLUE))
    img2.anchor = "A3"   # the SECOND data row
    ws.add_image(img2)

    return wb


if __name__ == "__main__":
    wb = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    wb.save(OUT)
    print(f"wrote {OUT}")
