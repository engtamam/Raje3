"""insights-004 (QA audit, 2026-09-12): a dispute-defense report used to render as if it were
complete even when a whole source failed to answer. `build_docx`'s own `warnings` param must show
up in the actual document, not just get accepted and dropped."""
from __future__ import annotations

import tempfile
from pathlib import Path

from docx import Document

from app.core.report_render import RenderItem, build_docx


def _all_text(path: Path) -> str:
    doc = Document(str(path))
    return "\n".join(p.text for p in doc.paragraphs)


def test_a_source_failure_is_visible_in_the_document():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "report.docx"
        build_docx(scenario_title="اختبار", tenant="t1", items=[],
                  out_path=out, warnings=["legal: compliance-service unreachable"])
        text = _all_text(out)
        assert "compliance-service unreachable" in text
        assert "تعذّر" in text or "⚠" in text


def test_no_warnings_means_no_warning_block_at_all():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "report.docx"
        build_docx(scenario_title="اختبار", tenant="t1",
                  items=[RenderItem(ts_label="2026-01-01", source="legal", label="بند")],
                  out_path=out, warnings=None)
        text = _all_text(out)
        assert "⚠" not in text


def test_multiple_source_failures_each_appear():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "report.docx"
        build_docx(scenario_title="اختبار", tenant="t1", items=[],
                  out_path=out, warnings=["legal: down", "audit: timeout"])
        text = _all_text(out)
        assert "legal: down" in text
        assert "audit: timeout" in text
