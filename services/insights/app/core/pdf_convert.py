"""Best-effort .docx → .pdf, via LibreOffice headless — the only server-side converter that
handles `finalize_rtl`'s own OOXML correctly (a naive docx→pdf library would re-derive layout
from the paragraph text and lose the RTL fixes entirely). Refuses plainly when `soffice` is not
on PATH rather than silently returning the .docx renamed or skipping the step — a report that
was ASKED for as PDF and quietly arrived as .docx is a defect nobody notices until the moment it
matters.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class PdfConversionUnavailable(Exception):
    """No converter on this machine — the caller decides how to tell the operator."""


def convert_to_pdf(docx_path: str | Path, *, timeout: float = 60.0) -> Path:
    docx_path = Path(docx_path)
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        raise PdfConversionUnavailable(
            "لا يوجد محوّل PDF على هذا الخادم (LibreOffice غير مثبَّت) — نزّل ملف Word واحفظه PDF يدوياً.")

    out_dir = docx_path.parent
    try:
        subprocess.run(
            [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(out_dir), str(docx_path)],
            check=True, timeout=timeout, capture_output=True)
    except subprocess.CalledProcessError as exc:
        raise PdfConversionUnavailable(
            f"تعذّر تحويل الملف إلى PDF: {exc.stderr.decode(errors='replace')[:300]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise PdfConversionUnavailable("انتهت مهلة تحويل الملف إلى PDF.") from exc

    pdf_path = out_dir / (docx_path.stem + ".pdf")
    if not pdf_path.is_file():
        raise PdfConversionUnavailable("انتهى التحويل دون خطأ ظاهر، لكن الملف الناتج غير موجود.")
    return pdf_path
