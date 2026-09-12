"""`build_staff_performance_docx` — the report table itself, the empty-state message, and the
truncation warning. Same "read the real .docx back with python-docx and check its actual content"
discipline as the render function's own manual verification before this file existed.
"""
from __future__ import annotations

from pathlib import Path

from docx import Document

from app.core.staff_performance_render import MAX_ROWS, build_staff_performance_docx


def _rows(n: int) -> list[dict]:
    return [{"operator_id": f"op{i}", "operator_name": f"موظف {i}", "visits": 10, "ratings": 5,
             "average_rating": 4.0, "no_show_rate": 0.1} for i in range(n)]


def test_the_table_carries_every_row_and_the_right_header(tmp_path: Path):
    out = build_staff_performance_docx(
        tenant="t1", rows=_rows(2), out_path=tmp_path / "r.docx")
    doc = Document(str(out))
    assert len(doc.tables) == 1
    table = doc.tables[0]
    assert len(table.rows) == 3   # header + 2 operators
    header = [c.text for c in table.rows[0].cells]
    assert header == ["الموظف", "الزيارات", "التقييمات", "متوسط التقييم", "نسبة عدم الحضور"]


def test_an_unrated_operator_shows_a_dash_not_a_fake_zero_average(tmp_path: Path):
    rows = [{"operator_id": "op1", "operator_name": "سارة", "visits": 4, "ratings": 0,
             "average_rating": 0.0, "no_show_rate": 0.0}]
    out = build_staff_performance_docx(tenant="t1", rows=rows, out_path=tmp_path / "r.docx")
    table = Document(str(out)).tables[0]
    assert table.rows[1].cells[3].text.strip("‎") == "—"


def test_no_rows_produces_a_valid_file_with_the_no_data_sentence_not_a_refusal(tmp_path: Path):
    out = build_staff_performance_docx(tenant="t1", rows=[], out_path=tmp_path / "empty.docx")
    doc = Document(str(out))
    assert doc.tables == []
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "لا توجد بيانات أداء لهذه الفترة." in text


def test_more_than_the_row_ceiling_is_capped_with_a_visible_warning_not_a_silent_drop(tmp_path: Path):
    out = build_staff_performance_docx(
        tenant="t1", rows=_rows(MAX_ROWS + 5), out_path=tmp_path / "big.docx")
    doc = Document(str(out))
    table = doc.tables[0]
    assert len(table.rows) - 1 == MAX_ROWS   # header + exactly the cap, never more
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "⚠" in text and str(MAX_ROWS + 5).translate(
        str.maketrans("", "", "‎")) in text.replace("‎", "")


def test_exactly_at_the_ceiling_shows_no_warning(tmp_path: Path):
    out = build_staff_performance_docx(
        tenant="t1", rows=_rows(MAX_ROWS), out_path=tmp_path / "exact.docx")
    doc = Document(str(out))
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "⚠" not in text
